"""Knowledge retrieval with lost-in-the-middle reordering.

Queries knowledge_cards by client_id + embedding similarity.
Applies lost-in-the-middle reordering (§22.2): best → position 1,
second-best → last, remaining fill middle positions.
Filters by document_set membership when available.

Lazy retrieval (§13.3): always inject client brand config + seasonal context,
inject knowledge cards only when relevant to artifact type.
"""

from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

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
        "raya_aidilfitri": {"months": [3, 4], "label": "Hari Raya Aidilfitri season", "mood": "festive, warm, family"},
        "raya_haji": {"months": [6, 7], "label": "Hari Raya Haji season", "mood": "devotional, respectful"},
        "merdeka": {"months": [8, 9], "label": "Merdeka / Malaysia Day season", "mood": "patriotic, proud, united"},
        "deepavali": {"months": [10, 11], "label": "Deepavali season", "mood": "bright, joyful, colourful"},
        "christmas_year_end": {"months": [12, 1], "label": "Year-end / Christmas season", "mood": "celebratory, reflective"},
        "cny": {"months": [1, 2], "label": "Chinese New Year season", "mood": "prosperous, festive, red-gold"},
        "default": {"months": [], "label": "General season", "mood": "professional, warm"},
    }

    for name, info in seasons.items():
        if name == "default":
            continue
        if month in info["months"]:
            return {"season": name, "label": info["label"], "mood": info["mood"]}

    return {"season": "default", "label": "General season", "mood": "professional, warm"}


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
    query_embedding: list[float] | None = None,
    document_set_id: str | None = None,
    top_k: int = 5,
    min_score: float = 0.65,
) -> list[dict[str, Any]]:
    """Query knowledge_cards by client_id + embedding similarity.

    Returns up to top_k cards with lost-in-the-middle reordering applied.
    Filters by document_set membership when document_set_id is provided.

    Args:
        client_id: Client identifier.
        query_embedding: 1536-dim embedding vector for similarity search.
            If None, returns cards by recency (no semantic ranking).
        document_set_id: Optional document set to filter by.
        top_k: Maximum number of cards to return.
        min_score: Minimum cosine similarity threshold (default 0.65).
    """
    if query_embedding is not None:
        return _retrieve_by_embedding(
            client_id, query_embedding, document_set_id, top_k, min_score,
        )
    return _retrieve_by_recency(client_id, document_set_id, top_k)


def _retrieve_by_embedding(
    client_id: str,
    query_embedding: list[float],
    document_set_id: str | None,
    top_k: int,
    min_score: float,
) -> list[dict[str, Any]]:
    """Semantic search against knowledge_cards using pgvector."""
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    if document_set_id:
        query = """
            SELECT kc.id, kc.title, kc.content, kc.card_type, kc.tags,
                   kc.domain, kc.confidence,
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
        params = (embedding_str, client_id, document_set_id, embedding_str, min_score, top_k)
    else:
        query = """
            SELECT kc.id, kc.title, kc.content, kc.card_type, kc.tags,
                   kc.domain, kc.confidence,
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

    cards = [dict(row) for row in rows]
    return lost_in_middle_reorder(cards)


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
# Context assembly (lazy retrieval — §13.3)
# ---------------------------------------------------------------------------


def assemble_context(
    client_id: str,
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
            query_embedding=query_embedding,
            document_set_id=document_set_id,
            top_k=top_k,
        )

    return {
        "client_config": client_config,
        "seasonal": seasonal,
        "knowledge_cards": knowledge_cards,
    }
