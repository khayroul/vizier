"""Knowledge retrieval with hybrid search pipeline.

Pipeline: query variants → pgvector semantic + Postgres FTS → RRF merge →
LLM reranking (GPT-5.4-mini) → lost-in-the-middle reordering.

Queries knowledge_cards by client_id + embedding similarity + FTS.
Applies lost-in-the-middle reordering (§22.2): best → position 1,
second-best → last, remaining fill middle positions.
Filters by document_set membership when available.

Lazy retrieval (§13.3): always inject client brand config + seasonal context,
inject knowledge cards only when relevant to artifact type.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from utils.call_llm import call_llm
from utils.database import get_cursor

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


# ---------------------------------------------------------------------------
# Client config + seasonal context (always injected, ~250 tokens)
# ---------------------------------------------------------------------------


def _load_client_config(client_id: str) -> dict[str, Any]:
    """Load client YAML config. Returns empty dict if not found."""
    path = _CONFIG_DIR / "clients" / f"{client_id}.yaml"
    if not path.exists():
        return {}
    with path.open() as fh:
        return yaml.safe_load(fh) or {}  # type: ignore[no-any-return]


@lru_cache(maxsize=1)
def _load_seasonal_context() -> dict[str, Any]:
    """Load seasonal context (deterministic, ~50 tokens).

    Returns current season info based on Malaysian calendar.
    """
    now = datetime.utcnow()
    month = now.month

    # Malaysian seasonal context
    seasons: dict[str, dict[str, Any]] = {
        "raya_aidilfitri": {
            "months": [3, 4],
            "label": "Hari Raya Aidilfitri season",
            "mood": "festive, warm, family",
        },
        "raya_haji": {
            "months": [6, 7],
            "label": "Hari Raya Haji season",
            "mood": "devotional, respectful",
        },
        "merdeka": {
            "months": [8, 9],
            "label": "Merdeka / Malaysia Day season",
            "mood": "patriotic, proud, united",
        },
        "deepavali": {
            "months": [10, 11],
            "label": "Deepavali season",
            "mood": "bright, joyful, colourful",
        },
        "christmas_year_end": {
            "months": [12, 1],
            "label": "Year-end / Christmas season",
            "mood": "celebratory, reflective",
        },
        "cny": {
            "months": [1, 2],
            "label": "Chinese New Year season",
            "mood": "prosperous, festive, red-gold",
        },
        "default": {
            "months": [],
            "label": "General season",
            "mood": "professional, warm",
        },
    }

    for name, info in seasons.items():
        if name == "default":
            continue
        if month in info["months"]:
            return {
                "season": name,
                "label": info["label"],
                "mood": info["mood"],
            }

    return {
        "season": "default",
        "label": "General season",
        "mood": "professional, warm",
    }


# ---------------------------------------------------------------------------
# Lost-in-the-middle reordering
# ---------------------------------------------------------------------------


def lost_in_middle_reorder(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reorder items so most relevant are at start and end (§22.2).

    Input must be sorted by relevance descending.
    Position 1: best. Last position: second-best. Middle: rest.

    This counteracts LLMs' tendency to underweight middle context.
    """
    if len(items) <= 2:
        return items

    reordered: list[dict[str, Any]] = [items[0]]  # best → first
    middle = items[2:]  # remaining go in the middle
    reordered.extend(middle)
    reordered.append(items[1])  # second-best → last
    return reordered


# ---------------------------------------------------------------------------
# Knowledge card retrieval
# ---------------------------------------------------------------------------


def retrieve_knowledge(
    client_id: str,
    query: str = "",
    query_embedding: list[float] | None = None,
    document_set_id: str | None = None,
    top_k: int = 5,
    min_score: float = 0.65,
) -> list[dict[str, Any]]:
    """Query knowledge_cards via hybrid search (pgvector + FTS + RRF).

    Pipeline: query variants → semantic + FTS per variant →
    RRF merge → LLM reranking → lost-in-middle reordering.

    Falls back to recency if no embedding provided.

    Args:
        client_id: Client identifier.
        query: Natural language query text for FTS and variant generation.
        query_embedding: 1536-dim embedding vector for similarity search.
            If None, returns cards by recency (no semantic ranking).
        document_set_id: Optional document set to filter by.
        top_k: Maximum number of cards to return.
        min_score: Minimum cosine similarity threshold (default 0.65).
    """
    if query_embedding is None:
        return _retrieve_by_recency(client_id, document_set_id, top_k)

    config = _load_pipeline_config()
    rrf_w = config.get("rrf_weights", {"dense": 1.0, "sparse": 0.25})
    n_candidates = config.get("reranker_candidates", 20)
    n_top = config.get("reranker_top_k", top_k)

    # Semantic search (embedding-based, same for all variants)
    semantic = _retrieve_by_embedding_raw(
        client_id, query_embedding, document_set_id, n_candidates, min_score,
    )

    # Generate query variants for FTS
    variants = _generate_query_variants(query) if query else [query]

    # Hybrid: merge semantic + FTS per variant
    all_merged: list[dict[str, Any]] = []
    for variant in variants:
        fts = (
            _search_fts(variant, client_id, document_set_id, n_candidates)
            if variant
            else []
        )
        merged = _rrf_merge(
            semantic,
            fts,
            rrf_w.get("dense", 1.0),
            rrf_w.get("sparse", 0.25),
        )
        all_merged.extend(merged)

    # Deduplicate across variants
    best: dict[str, dict[str, Any]] = {}
    for item in all_merged:
        cid = str(item["id"])
        existing_score = best[cid].get("rrf_score", 0) if cid in best else 0
        if cid not in best or item.get("rrf_score", 0) > existing_score:
            best[cid] = item
    deduped = sorted(
        best.values(),
        key=lambda x: x.get("rrf_score", 0),
        reverse=True,
    )

    # Rerank
    query_text = variants[0] if variants else query
    reranked = _rerank_with_llm(query_text, deduped[:n_candidates], n_top)

    # Lost-in-middle
    return lost_in_middle_reorder(reranked[:top_k])


def _retrieve_by_embedding_raw(
    client_id: str,
    query_embedding: list[float],
    document_set_id: str | None,
    top_k: int,
    min_score: float,
) -> list[dict[str, Any]]:
    """Semantic search against knowledge_cards using pgvector.

    Returns raw results WITHOUT lost-in-middle reordering
    (reordering happens at the pipeline level after RRF merge).
    """
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    if document_set_id:
        query = """
            SELECT kc.id, kc.title, kc.content, kc.card_type, kc.tags,
                   kc.domain, kc.confidence, kc.context_prefix,
                   1 - (kc.embedding <=> %s::vector) AS similarity
            FROM knowledge_cards kc
            JOIN document_set_members dsm ON dsm.knowledge_card_id = kc.id
            WHERE kc.client_id = %s
              AND kc.status = 'active'
              AND dsm.document_set_id = %s
              AND 1 - (kc.embedding <=> %s::vector) >= %s
            ORDER BY similarity DESC
            LIMIT %s
        """
        params = (
            embedding_str, client_id, document_set_id,
            embedding_str, min_score, top_k,
        )
    else:
        query = """
            SELECT kc.id, kc.title, kc.content, kc.card_type, kc.tags,
                   kc.domain, kc.confidence, kc.context_prefix,
                   1 - (kc.embedding <=> %s::vector) AS similarity
            FROM knowledge_cards kc
            WHERE kc.client_id = %s
              AND kc.status = 'active'
              AND 1 - (kc.embedding <=> %s::vector) >= %s
            ORDER BY similarity DESC
            LIMIT %s
        """
        params = (embedding_str, client_id, embedding_str, min_score, top_k)

    with get_cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    return [dict(row) for row in rows]


def _retrieve_by_recency(
    client_id: str,
    document_set_id: str | None,
    top_k: int,
) -> list[dict[str, Any]]:
    """Fallback retrieval by recency when no embedding is provided."""
    if document_set_id:
        query = """
            SELECT kc.id, kc.title, kc.content, kc.card_type, kc.tags,
                   kc.domain, kc.confidence
            FROM knowledge_cards kc
            JOIN document_set_members dsm ON dsm.knowledge_card_id = kc.id
            WHERE kc.client_id = %s
              AND kc.status = 'active'
              AND dsm.document_set_id = %s
            ORDER BY kc.created_at DESC
            LIMIT %s
        """
        params = (client_id, document_set_id, top_k)
    else:
        query = """
            SELECT kc.id, kc.title, kc.content, kc.card_type, kc.tags,
                   kc.domain, kc.confidence
            FROM knowledge_cards kc
            WHERE kc.client_id = %s
              AND kc.status = 'active'
            ORDER BY kc.created_at DESC
            LIMIT %s
        """
        params = (client_id, top_k)

    with get_cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# FTS search (Task 5)
# ---------------------------------------------------------------------------


def _search_fts(
    query: str,
    client_id: str,
    document_set_id: str | None = None,
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """Full-text search against knowledge_cards using tsvector.

    Uses 'simple' dictionary for mixed BM/EN content.
    Filters by document_set_id if provided, else by client_id.
    """
    if document_set_id:
        sql = """
            SELECT kc.id, kc.title, kc.content, kc.card_type, kc.tags,
                   kc.domain, kc.confidence, kc.context_prefix,
                   ts_rank(kc.search_vector, plainto_tsquery('simple', %s)) AS rank
            FROM knowledge_cards kc
            JOIN document_set_members dsm ON dsm.knowledge_card_id = kc.id
            WHERE kc.client_id = %s
              AND kc.status = 'active'
              AND dsm.document_set_id = %s
              AND kc.search_vector @@ plainto_tsquery('simple', %s)
            ORDER BY rank DESC
            LIMIT %s
        """
        params = (query, client_id, document_set_id, query, top_k)
    else:
        sql = """
            SELECT kc.id, kc.title, kc.content, kc.card_type, kc.tags,
                   kc.domain, kc.confidence, kc.context_prefix,
                   ts_rank(kc.search_vector, plainto_tsquery('simple', %s)) AS rank
            FROM knowledge_cards kc
            WHERE kc.client_id = %s
              AND kc.status = 'active'
              AND kc.search_vector @@ plainto_tsquery('simple', %s)
            ORDER BY rank DESC
            LIMIT %s
        """
        params = (query, client_id, query, top_k)

    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# RRF merge (Task 6)
# ---------------------------------------------------------------------------

_RRF_K = 60  # standard RRF constant


def _rrf_merge(
    semantic_results: list[dict[str, Any]],
    fts_results: list[dict[str, Any]],
    dense_weight: float = 1.0,
    sparse_weight: float = 0.25,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion merge of semantic and FTS results.

    score = dense_weight / (k + rank_in_semantic) + sparse_weight / (k + rank_in_fts)
    Deduplicates by card id, keeping the merged score.
    """
    scores: dict[str, float] = {}
    card_data: dict[str, dict[str, Any]] = {}

    for rank, item in enumerate(semantic_results):
        card_id = str(item["id"])
        rrf_score = dense_weight / (_RRF_K + rank + 1)
        scores[card_id] = scores.get(card_id, 0.0) + rrf_score
        card_data[card_id] = item

    for rank, item in enumerate(fts_results):
        card_id = str(item["id"])
        rrf_score = sparse_weight / (_RRF_K + rank + 1)
        scores[card_id] = scores.get(card_id, 0.0) + rrf_score
        if card_id not in card_data:
            card_data[card_id] = item

    sorted_ids = sorted(
        scores, key=lambda cid: scores[cid], reverse=True,
    )
    return [
        {**card_data[cid], "rrf_score": scores[cid]}
        for cid in sorted_ids
    ]


# ---------------------------------------------------------------------------
# Query variant generation (Task 7)
# ---------------------------------------------------------------------------

_QUERY_VARIANT_PREFIX: list[dict[str, str]] = [
    {
        "role": "system",
        "content": (
            "You generate search query variants for a "
            "Malaysian marketing knowledge base. "
            "Given a query, produce exactly 3 variants:\n"
            "1. Bahasa Melayu translation\n"
            "2. English synonym expansion (different words, same meaning)\n"
            "3. Combined paraphrase (mix of BM/EN terms)\n"
            'Return JSON: {"variants": ["variant1", "variant2", "variant3"]}'
        ),
    },
]


def _generate_query_variants(query: str, n: int = 4) -> list[str]:
    """Generate query variants via GPT-5.4-mini for multi-lingual retrieval.

    Returns [original, BM_translation, EN_expansion, combined_paraphrase].
    On LLM failure, returns [original] as fallback.
    """
    try:
        result = call_llm(
            stable_prefix=_QUERY_VARIANT_PREFIX,
            variable_suffix=[{"role": "user", "content": query}],
            model="gpt-5.4-mini",
            temperature=0.5,
            max_tokens=200,
            response_format={"type": "json_object"},
            operation_type="extract",
        )
        raw = result["content"].strip()
        parsed = json.loads(raw)
        variants = (
            parsed.get("variants", parsed)
            if isinstance(parsed, dict)
            else parsed
        )
        if isinstance(variants, list):
            return [query, *[str(v) for v in variants[:n - 1]]]
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Query variant generation failed, using original query only")

    return [query]


# ---------------------------------------------------------------------------
# LLM reranker (Task 8)
# ---------------------------------------------------------------------------

_RERANK_PREFIX: list[dict[str, str]] = [
    {
        "role": "system",
        "content": (
            "You are a relevance judge. Given a query and "
            "numbered candidate documents, "
            "return the indices (0-based) of the most relevant "
            "documents, ordered by relevance (most relevant first). "
            'Return JSON: {"indices": [0, 3, 7, ...]}'
        ),
    },
]


def _rerank_with_llm(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Score candidates jointly with query via GPT-5.4-mini.

    On JSON parse failure, falls back to input order (RRF-merged).
    """
    if len(candidates) <= top_k:
        return [
            {**c, "relevance_score": 1.0 - (idx * 0.1)}
            for idx, c in enumerate(candidates)
        ]

    numbered = "\n".join(
        f"[{i}] {c.get('title', '')} — {c.get('content', '')[:200]}"
        for i, c in enumerate(candidates)
    )
    user_msg = (
        f"Query: {query}\n\nCandidates:\n{numbered}"
        f"\n\nReturn top {top_k} indices."
    )

    try:
        result = call_llm(
            stable_prefix=_RERANK_PREFIX,
            variable_suffix=[{"role": "user", "content": user_msg}],
            model="gpt-5.4-mini",
            temperature=0.0,
            max_tokens=100,
            response_format={"type": "json_object"},
            operation_type="classify",
        )
        parsed = json.loads(result["content"].strip())
        indices = parsed.get("indices", parsed) if isinstance(parsed, dict) else parsed
        if isinstance(indices, list):
            reranked: list[dict[str, Any]] = []
            for rank, idx in enumerate(indices[:top_k]):
                if isinstance(idx, int) and 0 <= idx < len(candidates):
                    candidate = {**candidates[idx]}
                    candidate["relevance_score"] = 1.0 - (rank * 0.1)
                    reranked.append(candidate)
            if reranked:
                return reranked
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Reranker JSON parse failed, falling back to RRF order")

    # Fallback: return top_k in original order (immutable)
    return [
        {**c, "relevance_score": 1.0 - (idx * 0.1)}
        for idx, c in enumerate(candidates[:top_k])
    ]


# ---------------------------------------------------------------------------
# Pipeline config loading
# ---------------------------------------------------------------------------


def _load_pipeline_config() -> dict[str, Any]:
    """Load retrieval_pipeline config from retrieval_profiles.yaml."""
    path = _CONFIG_DIR / "retrieval_profiles.yaml"
    with path.open() as fh:
        data = yaml.safe_load(fh)
    return data.get("retrieval_pipeline", {})  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Context assembly (lazy retrieval — §13.3)
# ---------------------------------------------------------------------------


def assemble_context(
    client_id: str,
    query: str = "",
    query_embedding: list[float] | None = None,
    document_set_id: str | None = None,
    include_knowledge: bool = True,
    top_k: int = 5,
) -> dict[str, Any]:
    """Assemble production context for a job.

    Always includes client config + seasonal context.
    Optionally includes knowledge cards (lazy retrieval).

    Returns dict with keys: client_config, seasonal, knowledge_cards.
    """
    client_config = _load_client_config(client_id)
    seasonal = _load_seasonal_context()

    knowledge_cards: list[dict[str, Any]] = []
    if include_knowledge:
        knowledge_cards = retrieve_knowledge(
            client_id=client_id,
            query=query,
            query_embedding=query_embedding,
            document_set_id=document_set_id,
            top_k=top_k,
        )

    return {
        "client_config": client_config,
        "seasonal": seasonal,
        "knowledge_cards": knowledge_cards,
    }
