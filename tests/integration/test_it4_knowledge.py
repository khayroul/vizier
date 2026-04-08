"""IT-4: Knowledge Retrieval Pipeline Integration Test.

Validates: S18 knowledge spine + S12 retrieval utilities + S10a database.

Pipeline: query → 4 variants (BM + EN) → hybrid search (pgvector + FTS) →
RRF merge → LLM reranking → lost-in-middle reordering → contextual prefixes.

Uses real Postgres (pgvector + FTS), mocks call_llm and embed_text.
"""

from __future__ import annotations

import math
import os
import uuid
from typing import Any
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.requires_db

from utils.database import get_cursor
from utils.embeddings import format_embedding
from utils.knowledge import (
    _generate_query_variants,
    _rerank_with_llm,
    _retrieve_by_embedding_raw,
    _rrf_merge,
    _search_fts,
    assemble_context,
    lost_in_middle_reorder,
    retrieve_knowledge,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DIM = 1536


def _make_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Deterministic embedding helpers
# ---------------------------------------------------------------------------


def _base_embedding() -> list[float]:
    """A normalised 1536-dim vector used as the 'query' embedding.

    All ones / sqrt(1536) — unit-length so cosine similarity is meaningful.
    """
    norm = math.sqrt(_DIM)
    return [1.0 / norm] * _DIM


def _similar_embedding(offset: int = 0, similarity_target: float = 0.95) -> list[float]:
    """Return a 1536-dim vector with predictable cosine similarity to _base_embedding.

    Perturbs dimensions [offset : offset+perturbation_count] to reduce similarity.
    Higher offset → different perturbation zone → different vector.
    """
    base = _base_embedding()
    # Perturb a small block to reduce similarity while keeping unit length
    perturbation_count = max(1, int(_DIM * (1.0 - similarity_target)))
    vec = list(base)
    for i in range(perturbation_count):
        idx = (offset + i) % _DIM
        vec[idx] = -vec[idx]  # flip sign — reduces dot product
    # Re-normalise
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec]


def _dissimilar_embedding() -> list[float]:
    """Return a vector with negative components — low cosine similarity to _base_embedding.

    _base_embedding is all-positive uniform, so a vector that alternates
    positive and negative will have near-zero dot product.
    """
    vec = [(-1.0) ** i for i in range(_DIM)]
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec]


# ---------------------------------------------------------------------------
# Test card data
# ---------------------------------------------------------------------------

_CARDS = [
    {
        "title": "Raya 2025 Campaign Theme",
        "content": "Tema kempen Raya 2025: Keluarga Bahagia. Sasaran utama keluarga Melayu kelas menengah. DMB batik collection.",
        "card_type": "fact",
        "tags": ["raya", "2025", "dmb", "batik"],
        "domain": "marketing",
    },
    {
        "title": "DMB Batik Promotion Strategy",
        "content": "DMB batik promotion for Raya uses warm colours, traditional motifs. Target audience: women 25-45.",
        "card_type": "fact",
        "tags": ["dmb", "batik", "promotion", "raya"],
        "domain": "marketing",
    },
    {
        "title": "Raya Batik Colour Palette",
        "content": "Warna batik Raya: hijau tua (#1B4332), emas (#D4A843), merah maroon. Batik DMB signature.",
        "card_type": "brand_pattern",
        "tags": ["batik", "raya", "colour", "dmb"],
        "domain": "design",
    },
    {
        "title": "DMB Brand Voice Guidelines",
        "content": "Nada formal tetapi mesra. Bahasa campuran BM-EN untuk audience muda. DMB brand positioning.",
        "card_type": "brand_pattern",
        "tags": ["dmb", "brand", "voice"],
        "domain": "marketing",
    },
    {
        "title": "Batik Production Process",
        "content": "Batik tulis DMB uses hand-drawn wax-resist dyeing on premium cotton. Raya collection features floral motifs.",
        "card_type": "fact",
        "tags": ["batik", "production", "dmb", "raya"],
        "domain": "product",
    },
    {
        "title": "Office Supplies Inventory",
        "content": "Printer toner levels low. Reorder A4 paper by Friday. Stapler needs replacement.",
        "card_type": "fact",
        "tags": ["office", "supplies"],
        "domain": "operations",
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_client():
    """Create a test client. Cleaned up after test."""
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    client_id = _make_uuid()
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO clients (id, name, industry, brand_config, brand_mood, status)
            VALUES (%s, %s, 'textile', '{"primary_color": "#1B4332"}'::jsonb, %s, 'active')
            """,
            (client_id, f"TEST_IT4_{client_id[:8]}", ["warm", "traditional"]),
        )
    yield {"id": client_id}
    # Cleanup
    try:
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM document_set_members WHERE knowledge_card_id IN "
                "(SELECT id FROM knowledge_cards WHERE client_id = %s)",
                (client_id,),
            )
            cur.execute("DELETE FROM knowledge_cards WHERE client_id = %s", (client_id,))
            cur.execute("DELETE FROM knowledge_sources WHERE client_id = %s", (client_id,))
            cur.execute("DELETE FROM document_sets WHERE client_id = %s", (client_id,))
            cur.execute("DELETE FROM clients WHERE id = %s", (client_id,))
    except Exception:
        pass


@pytest.fixture()
def knowledge_source(test_client: dict[str, str]) -> dict[str, str]:
    """Create a knowledge_sources record for card ingestion."""
    source_id = _make_uuid()
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_sources (id, client_id, source_type, title, domain, language, status)
            VALUES (%s, %s, 'manual', 'DMB Raya 2025 Campaign', 'marketing', 'bm', 'active')
            """,
            (source_id, test_client["id"]),
        )
    return {"id": source_id, "client_id": test_client["id"]}


@pytest.fixture()
def seeded_knowledge_cards(
    test_client: dict[str, str],
    knowledge_source: dict[str, str],
) -> list[dict[str, Any]]:
    """Seed 6 cards with deterministic embeddings and context prefixes.

    Cards 0-4 are Raya/batik/DMB related (similar embeddings to query).
    Card 5 is irrelevant (dissimilar embedding).
    """
    cards: list[dict[str, Any]] = []
    client_id = test_client["id"]
    source_id = knowledge_source["id"]

    for idx, card_data in enumerate(_CARDS):
        card_id = _make_uuid()
        # Relevant cards get similar embeddings; irrelevant card gets dissimilar
        if idx < len(_CARDS) - 1:
            emb = _similar_embedding(offset=idx * 10, similarity_target=0.92 - idx * 0.03)
        else:
            emb = _dissimilar_embedding()

        emb_str = format_embedding(emb)
        prefix = f"Context: DMB Raya 2025 batik campaign card about {card_data['title'].lower()}."

        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO knowledge_cards
                    (id, source_id, client_id, card_type, title, content, tags,
                     domain, embedding, context_prefix, confidence, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0.8, 'active')
                """,
                (
                    card_id, source_id, client_id, card_data["card_type"],
                    card_data["title"], card_data["content"], card_data["tags"],
                    card_data["domain"], emb_str, prefix,
                ),
            )

        cards.append({
            "id": card_id,
            "title": card_data["title"],
            "content": card_data["content"],
            "tags": card_data["tags"],
            "embedding": emb,
            "is_relevant": idx < len(_CARDS) - 1,
        })

    return cards


@pytest.fixture()
def mock_query_embedding() -> list[float]:
    """Deterministic query embedding (same as _base_embedding)."""
    return _base_embedding()


@pytest.fixture()
def test_document_set(
    test_client: dict[str, str],
    seeded_knowledge_cards: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a document set containing only the first 3 cards."""
    ds_id = _make_uuid()
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO document_sets (id, client_id, name, description, status)
            VALUES (%s, %s, 'Raya Batik Set', 'Cards for Raya batik campaign', 'active')
            """,
            (ds_id, test_client["id"]),
        )
        for card in seeded_knowledge_cards[:3]:
            cur.execute(
                """
                INSERT INTO document_set_members (document_set_id, knowledge_card_id)
                VALUES (%s, %s)
                """,
                (ds_id, card["id"]),
            )
    return {
        "id": ds_id,
        "card_ids": [c["id"] for c in seeded_knowledge_cards[:3]],
    }


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_call_llm_variants(**kwargs: Any) -> dict[str, str]:
    """Mock call_llm for query variant generation."""
    return {
        "content": '{"variants": ["promosi batik Raya DMB", "Raya batik marketing DMB", "kempen Raya DMB batik"]}',
    }


def _mock_call_llm_rerank(**kwargs: Any) -> dict[str, str]:
    """Mock call_llm for reranking — return indices in reverse-ish order."""
    return {"content": '{"indices": [2, 0, 4, 1, 3]}'}


def _mock_call_llm_contextualise(**kwargs: Any) -> dict[str, str]:
    """Mock call_llm for contextualise_card."""
    return {"content": "Context: DMB Raya 2025 batik promotion campaign targeting Malay families."}


def _mock_call_llm_dispatch(**kwargs: Any) -> dict[str, str]:
    """Route mock call_llm based on the system prompt content."""
    messages = kwargs.get("stable_prefix") or kwargs.get("messages") or []
    system_content = ""
    for msg in messages:
        if msg.get("role") == "system":
            system_content = msg.get("content", "")
            break

    if "query variants" in system_content.lower() or "search query" in system_content.lower():
        return _mock_call_llm_variants(**kwargs)
    if "relevance judge" in system_content.lower():
        return _mock_call_llm_rerank(**kwargs)
    if "context prefix" in system_content.lower():
        return _mock_call_llm_contextualise(**kwargs)

    # Default: return empty JSON
    return {"content": "{}"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCardIngestion:
    """Test 1: Card ingestion with embedding and FTS."""

    def test_card_ingestion_with_embedding(
        self, seeded_knowledge_cards: list[dict[str, Any]], test_client: dict[str, str],
    ) -> None:
        """Ingested cards have embedding, search_vector, and context_prefix populated."""
        card_ids = [c["id"] for c in seeded_knowledge_cards]

        with get_cursor() as cur:
            cur.execute(
                """
                SELECT id, embedding, search_vector, context_prefix
                FROM knowledge_cards
                WHERE client_id = %s AND id = ANY(%s::uuid[])
                """,
                (test_client["id"], card_ids),
            )
            rows = cur.fetchall()

        assert len(rows) == len(_CARDS), f"Expected {len(_CARDS)} cards, got {len(rows)}"

        for row in rows:
            assert row["embedding"] is not None, f"Card {row['id']} missing embedding"
            assert row["search_vector"] is not None, f"Card {row['id']} missing search_vector"
            assert row["context_prefix"] is not None, f"Card {row['id']} missing context_prefix"
            assert len(row["context_prefix"]) > 0, f"Card {row['id']} has empty context_prefix"


class TestFTSSearch:
    """Tests 2-3: Full-text search with BM and EN queries."""

    def test_fts_search_bm_query(
        self, seeded_knowledge_cards: list[dict[str, Any]], test_client: dict[str, str],
    ) -> None:
        """FTS with Bahasa Melayu query returns relevant cards."""
        results = _search_fts("Raya batik DMB kempen", test_client["id"], None, 10)

        assert len(results) > 0, "BM query should return results"
        for result in results:
            assert "rank" in result, "FTS results must have rank field"
            assert result["rank"] > 0, "Matching results must have positive rank"

        # Raya/batik/DMB cards should appear
        titles = {r["title"] for r in results}
        assert any("Raya" in t or "Batik" in t or "DMB" in t for t in titles), (
            f"Expected Raya/Batik/DMB cards, got titles: {titles}"
        )

    def test_fts_search_en_query(
        self, seeded_knowledge_cards: list[dict[str, Any]], test_client: dict[str, str],
    ) -> None:
        """FTS with English query also returns results ('simple' dictionary handles both)."""
        results = _search_fts("Raya batik promotion DMB", test_client["id"], None, 10)

        assert len(results) > 0, "EN query should return results with 'simple' dictionary"
        titles = {r["title"] for r in results}
        assert any("Raya" in t or "Batik" in t or "DMB" in t for t in titles)

    def test_fts_irrelevant_query_returns_fewer(
        self, seeded_knowledge_cards: list[dict[str, Any]], test_client: dict[str, str],
    ) -> None:
        """FTS with irrelevant query returns no Raya/batik results."""
        results = _search_fts("printer toner paper stapler", test_client["id"], None, 10)

        # Should return the office supplies card, not the Raya cards
        raya_titles = [r["title"] for r in results if "Raya" in r["title"] or "Batik" in r["title"]]
        assert len(raya_titles) == 0, f"Irrelevant query should not match Raya cards: {raya_titles}"


class TestEmbeddingSimilaritySearch:
    """Test 4: pgvector cosine similarity search."""

    def test_embedding_similarity_search(
        self,
        seeded_knowledge_cards: list[dict[str, Any]],
        test_client: dict[str, str],
        mock_query_embedding: list[float],
    ) -> None:
        """Semantic search returns cards sorted by cosine similarity."""
        results = _retrieve_by_embedding_raw(
            test_client["id"], mock_query_embedding, None, 10, 0.5,
        )

        assert len(results) > 0, "Embedding search should return results"

        # Check similarity scores are present and sorted descending
        similarities = [r["similarity"] for r in results]
        assert all(isinstance(s, float) for s in similarities)
        assert similarities == sorted(similarities, reverse=True), (
            "Results must be sorted by similarity descending"
        )

        # The irrelevant card (dissimilar embedding) should not appear at min_score=0.5
        irrelevant_card = seeded_knowledge_cards[-1]
        result_ids = {str(r["id"]) for r in results}
        assert irrelevant_card["id"] not in result_ids, (
            "Dissimilar card should be filtered out by min_score"
        )


class TestQueryVariantGeneration:
    """Test 5: Query variant generation via mocked LLM."""

    @patch("utils.knowledge.call_llm", side_effect=_mock_call_llm_variants)
    def test_query_variant_generation(self, mock_llm: Any) -> None:
        """Generates 4 variants: [original, BM, EN expansion, paraphrase]."""
        variants = _generate_query_variants("Raya batik promotion DMB")

        assert len(variants) == 4, f"Expected 4 variants, got {len(variants)}"
        assert variants[0] == "Raya batik promotion DMB", "First variant must be original query"
        assert all(isinstance(v, str) for v in variants)
        assert all(len(v) > 0 for v in variants)
        mock_llm.assert_called_once()


class TestRRFMerge:
    """Test 6: Reciprocal Rank Fusion merge."""

    def test_rrf_merge_combines_results(self) -> None:
        """RRF merge combines semantic and FTS results with proper scoring."""
        shared_id = _make_uuid()
        semantic_only_id = _make_uuid()
        fts_only_id = _make_uuid()

        semantic = [
            {"id": shared_id, "title": "Shared Card", "content": "shared"},
            {"id": semantic_only_id, "title": "Semantic Only", "content": "semantic"},
        ]
        fts = [
            {"id": shared_id, "title": "Shared Card", "content": "shared"},
            {"id": fts_only_id, "title": "FTS Only", "content": "fts"},
        ]

        merged = _rrf_merge(semantic, fts, dense_weight=1.0, sparse_weight=0.25)

        result_ids = [str(r["id"]) for r in merged]
        assert shared_id in result_ids, "Shared card must appear"
        assert semantic_only_id in result_ids, "Semantic-only card must appear"
        assert fts_only_id in result_ids, "FTS-only card must appear"

        # Shared card should rank highest (appears in both)
        assert str(merged[0]["id"]) == shared_id, (
            "Card in both result sets should have highest RRF score"
        )

        # All results must have rrf_score
        for item in merged:
            assert "rrf_score" in item, "Each merged result must have rrf_score"
            assert isinstance(item["rrf_score"], float)


class TestLLMReranker:
    """Test 7: LLM-based reranking."""

    @patch("utils.knowledge.call_llm", side_effect=_mock_call_llm_rerank)
    def test_llm_reranker(self, mock_llm: Any) -> None:
        """Reranker reorders candidates per LLM-returned indices."""
        candidates = [
            {"id": _make_uuid(), "title": f"Card {i}", "content": f"content {i}"}
            for i in range(6)
        ]

        reranked = _rerank_with_llm("Raya batik promotion DMB", candidates, top_k=5)

        assert len(reranked) == 5, f"Expected 5 results, got {len(reranked)}"

        # Check reordering matches mock indices [2, 0, 4, 1, 3]
        expected_order = [2, 0, 4, 1, 3]
        for rank, idx in enumerate(expected_order):
            assert reranked[rank]["title"] == f"Card {idx}", (
                f"Position {rank} should be Card {idx}, got {reranked[rank]['title']}"
            )

        # Each result should have relevance_score
        for item in reranked:
            assert "relevance_score" in item
            assert isinstance(item["relevance_score"], float)

    def test_reranker_fallback_when_fewer_than_top_k(self) -> None:
        """When candidates <= top_k, reranker returns all with scores (no LLM call)."""
        candidates = [
            {"id": _make_uuid(), "title": f"Card {i}", "content": f"content {i}"}
            for i in range(3)
        ]

        # No mock needed — should not call LLM when len(candidates) <= top_k
        reranked = _rerank_with_llm("query", candidates, top_k=5)

        assert len(reranked) == 3
        for item in reranked:
            assert "relevance_score" in item


class TestLostInMiddleReorder:
    """Test 8: Lost-in-the-middle reordering."""

    def test_lost_in_middle_reorder(self) -> None:
        """Most relevant at start and end, least relevant in middle."""
        items = [{"rank": i, "title": f"Item {i}"} for i in range(5)]
        # Input order: 0 (best) → 4 (worst)

        reordered = lost_in_middle_reorder(items)

        assert len(reordered) == 5
        # Best (rank 0) at position 0
        assert reordered[0]["rank"] == 0, "Best item must be at position 0"
        # Second-best (rank 1) at last position
        assert reordered[-1]["rank"] == 1, "Second-best must be at last position"
        # Middle positions have remaining items
        middle_ranks = [r["rank"] for r in reordered[1:-1]]
        assert sorted(middle_ranks) == [2, 3, 4], "Middle should contain remaining items"

    def test_lost_in_middle_two_items(self) -> None:
        """Two items returned as-is (no middle to fill)."""
        items = [{"rank": 0}, {"rank": 1}]
        reordered = lost_in_middle_reorder(items)
        assert reordered == items

    def test_lost_in_middle_single_item(self) -> None:
        """Single item returned as-is."""
        items = [{"rank": 0}]
        reordered = lost_in_middle_reorder(items)
        assert reordered == items


class TestFullRetrievalPipeline:
    """Test 9: End-to-end retrieval pipeline."""

    @patch("utils.knowledge.call_llm", side_effect=_mock_call_llm_dispatch)
    def test_full_retrieval_pipeline(
        self,
        mock_llm: Any,
        seeded_knowledge_cards: list[dict[str, Any]],
        test_client: dict[str, str],
        mock_query_embedding: list[float],
    ) -> None:
        """Full pipeline: variants → hybrid search → RRF → rerank → lost-in-middle."""
        results = retrieve_knowledge(
            client_id=test_client["id"],
            query="Raya batik promotion DMB",
            query_embedding=mock_query_embedding,
            top_k=5,
        )

        assert len(results) > 0, "Pipeline should return results"
        assert len(results) <= 5, f"top_k=5 but got {len(results)} results"

        # Every returned card must have context_prefix
        for card in results:
            assert card.get("context_prefix") is not None, (
                f"Card {card.get('id')} missing context_prefix"
            )
            assert len(card["context_prefix"]) > 0

        # The irrelevant card should not appear
        irrelevant_id = seeded_knowledge_cards[-1]["id"]
        result_ids = {str(r["id"]) for r in results}
        assert irrelevant_id not in result_ids, "Irrelevant card should be excluded"

    @patch("utils.knowledge.call_llm", side_effect=_mock_call_llm_dispatch)
    def test_pipeline_includes_fts_only_matches(
        self,
        mock_llm: Any,
        seeded_knowledge_cards: list[dict[str, Any]],
        test_client: dict[str, str],
    ) -> None:
        """Cards matchable only by FTS (not by embedding) also appear via hybrid search.

        Uses an embedding that doesn't match any cards, but query text matches via FTS.
        """
        # Use dissimilar embedding — no semantic matches at min_score=0.65
        bad_embedding = _dissimilar_embedding()

        results = retrieve_knowledge(
            client_id=test_client["id"],
            query="Raya batik promotion DMB",
            query_embedding=bad_embedding,
            top_k=5,
        )

        # FTS should still contribute results even though embedding matches nothing
        assert len(results) > 0, (
            "FTS should contribute results even when embedding similarity is low"
        )


class TestDocumentSetFiltering:
    """Test 10: Document set membership filtering."""

    def test_document_set_filtering(
        self,
        seeded_knowledge_cards: list[dict[str, Any]],
        test_client: dict[str, str],
        test_document_set: dict[str, Any],
        mock_query_embedding: list[float],
    ) -> None:
        """Only cards in the document set are returned."""
        ds_card_ids = set(test_document_set["card_ids"])

        results = _retrieve_by_embedding_raw(
            test_client["id"],
            mock_query_embedding,
            test_document_set["id"],
            top_k=10,
            min_score=0.5,
        )

        result_ids = {str(r["id"]) for r in results}
        # All returned cards must be in the document set
        assert result_ids.issubset(ds_card_ids), (
            f"Results {result_ids - ds_card_ids} are not in document set"
        )

    def test_document_set_fts_filtering(
        self,
        seeded_knowledge_cards: list[dict[str, Any]],
        test_client: dict[str, str],
        test_document_set: dict[str, Any],
    ) -> None:
        """FTS also respects document set filtering."""
        ds_card_ids = set(test_document_set["card_ids"])

        results = _search_fts(
            "Raya batik DMB", test_client["id"], test_document_set["id"], 10,
        )

        result_ids = {str(r["id"]) for r in results}
        assert result_ids.issubset(ds_card_ids), (
            f"FTS results {result_ids - ds_card_ids} are not in document set"
        )

    @patch("utils.knowledge.call_llm", side_effect=_mock_call_llm_dispatch)
    def test_full_pipeline_with_document_set(
        self,
        mock_llm: Any,
        seeded_knowledge_cards: list[dict[str, Any]],
        test_client: dict[str, str],
        test_document_set: dict[str, Any],
        mock_query_embedding: list[float],
    ) -> None:
        """Full pipeline respects document_set_id filter."""
        ds_card_ids = set(test_document_set["card_ids"])

        results = retrieve_knowledge(
            client_id=test_client["id"],
            query="Raya batik promotion DMB",
            query_embedding=mock_query_embedding,
            document_set_id=test_document_set["id"],
            top_k=5,
        )

        result_ids = {str(r["id"]) for r in results}
        assert result_ids.issubset(ds_card_ids), (
            "Full pipeline with document_set_id must only return set members"
        )


class TestContextAssembly:
    """Test 11: Context assembly for production prompt injection."""

    @patch("utils.knowledge.call_llm", side_effect=_mock_call_llm_dispatch)
    def test_context_assembly(
        self,
        mock_llm: Any,
        seeded_knowledge_cards: list[dict[str, Any]],
        test_client: dict[str, str],
        mock_query_embedding: list[float],
    ) -> None:
        """assemble_context returns structured context with knowledge cards."""
        ctx = assemble_context(
            client_id=test_client["id"],
            query="Raya batik promotion DMB",
            query_embedding=mock_query_embedding,
            top_k=5,
        )

        assert "client_config" in ctx
        assert "seasonal" in ctx
        assert "knowledge_cards" in ctx
        assert isinstance(ctx["knowledge_cards"], list)

        # Seasonal context should have season info
        assert "season" in ctx["seasonal"]
        assert "label" in ctx["seasonal"]

    @patch("utils.knowledge.call_llm", side_effect=_mock_call_llm_dispatch)
    def test_context_assembly_without_knowledge(
        self,
        mock_llm: Any,
        test_client: dict[str, str],
    ) -> None:
        """assemble_context with include_knowledge=False skips card retrieval."""
        ctx = assemble_context(
            client_id=test_client["id"],
            include_knowledge=False,
        )

        assert ctx["knowledge_cards"] == []
        assert "seasonal" in ctx


class TestNoResults:
    """Test 12: Graceful handling of no-match scenarios."""

    def test_retrieval_with_no_results(
        self, seeded_knowledge_cards: list[dict[str, Any]], test_client: dict[str, str],
    ) -> None:
        """Query with embedding that doesn't match any seeded card returns empty list."""
        # Negate the dissimilar embedding — this won't match the relevant cards
        # (which are near _base_embedding) OR the irrelevant card (which uses
        # _dissimilar_embedding). Cosine similarity ≈ -1 with the irrelevant card.
        neg_dissimilar = [-v for v in _dissimilar_embedding()]
        results = _retrieve_by_embedding_raw(
            test_client["id"], neg_dissimilar, None, 10, 0.9,
        )
        assert results == [], f"Expected empty results, got {len(results)}"

    @patch("utils.knowledge.call_llm", side_effect=_mock_call_llm_dispatch)
    def test_full_pipeline_no_results(
        self, mock_llm: Any, test_client: dict[str, str],
    ) -> None:
        """Pipeline with no seeded cards returns empty list gracefully."""
        # test_client has no cards (seeded_knowledge_cards not used)
        bad_embedding = _dissimilar_embedding()
        results = retrieve_knowledge(
            client_id=test_client["id"],
            query="completely unrelated query about quantum physics",
            query_embedding=bad_embedding,
            top_k=5,
        )
        assert isinstance(results, list)
        # May be empty or not — depends on FTS. No error is the key assertion.


class TestContextPrefixOnReturnedCards:
    """Test 13: Context prefix present on all retrieved cards."""

    @patch("utils.knowledge.call_llm", side_effect=_mock_call_llm_dispatch)
    def test_context_prefix_on_returned_cards(
        self,
        mock_llm: Any,
        seeded_knowledge_cards: list[dict[str, Any]],
        test_client: dict[str, str],
        mock_query_embedding: list[float],
    ) -> None:
        """All cards returned by retrieve_knowledge have non-empty context_prefix."""
        results = retrieve_knowledge(
            client_id=test_client["id"],
            query="Raya batik promotion DMB",
            query_embedding=mock_query_embedding,
            top_k=5,
        )

        assert len(results) > 0, "Should have results to check"
        for card in results:
            assert "context_prefix" in card, f"Card {card.get('id')} missing context_prefix key"
            assert card["context_prefix"] is not None, (
                f"Card {card.get('id')} has None context_prefix"
            )
            assert len(card["context_prefix"]) > 0, (
                f"Card {card.get('id')} has empty context_prefix"
            )

    def test_ingested_cards_have_context_prefix_in_db(
        self,
        seeded_knowledge_cards: list[dict[str, Any]],
        test_client: dict[str, str],
    ) -> None:
        """Verify context_prefix is stored in the database for all seeded cards."""
        card_ids = [c["id"] for c in seeded_knowledge_cards]
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, context_prefix FROM knowledge_cards WHERE id = ANY(%s::uuid[])",
                (card_ids,),
            )
            rows = cur.fetchall()

        for row in rows:
            assert row["context_prefix"] is not None
            assert len(row["context_prefix"]) > 0


class TestIngestCardFunction:
    """Test card ingestion via the canonical ingest_card tool."""

    @patch("tools.knowledge.embed_text", return_value=_base_embedding())
    @patch("tools.knowledge.contextualise_card", return_value="Test context prefix for DMB Raya campaign.")
    def test_ingest_card_creates_complete_record(
        self,
        mock_ctx: Any,
        mock_embed: Any,
        knowledge_source: dict[str, str],
        test_client: dict[str, str],
    ) -> None:
        """ingest_card creates a card with embedding, context_prefix, labels, and search_vector."""
        from tools.knowledge import ingest_card

        card_id = ingest_card(
            source_id=knowledge_source["id"],
            content="DMB batik Raya 2025 promotional material for middle-class families.",
            card_type="fact",
            title="DMB Raya Promo",
            tags=["dmb", "raya", "batik"],
            domain="marketing",
            client_id=test_client["id"],
        )

        assert card_id is not None

        with get_cursor() as cur:
            cur.execute(
                "SELECT embedding, context_prefix, memory_labels, search_vector, content FROM knowledge_cards WHERE id = %s",
                (card_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["embedding"] is not None, "Embedding must be populated"
        assert row["context_prefix"] == "Test context prefix for DMB Raya campaign."
        assert "campaign" in (row["memory_labels"] or [])
        assert row["search_vector"] is not None, "search_vector (tsvector) must be populated"
        assert row["content"] == "DMB batik Raya 2025 promotional material for middle-class families."
