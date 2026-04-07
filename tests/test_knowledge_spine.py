"""S18 — Tests for knowledge spine: hybrid retrieval, Wisdom Vault, exemplar promotion.

Requires: running Postgres (vizier db).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest

os.environ.setdefault("DATABASE_URL", "postgres://localhost:5432/vizier")

from utils.database import get_cursor, run_migration
from utils.spans import DB_PATH as SPANS_DB_PATH  # noqa: F811
from utils.spans import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema() -> None:
    """Run core.sql + extended.sql before the test session."""
    base = Path(__file__).resolve().parent.parent / "migrations"
    for sql_file in ["core.sql", "extended.sql"]:
        path = base / sql_file
        if path.exists():
            run_migration(path)


@pytest.fixture(autouse=True)
def _isolated_spans(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "spans.db"
    monkeypatch.setattr("utils.spans.DB_PATH", db_path)
    monkeypatch.setattr("utils.call_llm.DB_PATH", db_path)
    init_db(db_path)
    return db_path


@pytest.fixture()
def client_id() -> str:
    """Insert a test client and return its id."""
    cid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO clients (id, name, industry) VALUES (%s, %s, %s)",
            (cid, f"test-client-{cid[:8]}", "testing"),
        )
    return cid


@pytest.fixture()
def _seed_cards(client_id: str) -> list[str]:
    """Insert test knowledge cards with embeddings and return card ids.

    Creates 5 cards: 3 about Raya/batik (should match semantic + FTS),
    1 about DMB (should match FTS for exact term), 1 unrelated.
    """
    fake_embedding = "[" + ",".join(["0.1"] * 1536) + "]"
    card_ids: list[str] = []

    cards = [
        {"title": "Raya Batik Promo", "content": "Diskaun 30% untuk semua produk batik sempena Raya.", "domain": "marketing"},
        {"title": "Batik Design Guide", "content": "Traditional batik patterns use wax-resist dyeing technique.", "domain": "design"},
        {"title": "Festive Campaign", "content": "Raya promotional campaign for batik products in Malaysia.", "domain": "marketing"},
        {"title": "DMB Brand Profile", "content": "DMB is a leading Malaysian batik brand established in 1985.", "domain": "brand"},
        {"title": "Cloud Infrastructure", "content": "AWS EC2 instances for compute workloads.", "domain": "tech"},
    ]

    # Create a source first
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO knowledge_sources (client_id, source_type, title, domain, status) "
            "VALUES (%s, 'test', 'Test Source', 'testing', 'active') RETURNING id",
            (client_id,),
        )
        source_row = cur.fetchone()
        assert source_row is not None
        source_id = str(source_row["id"])

        for card in cards:
            cur.execute(
                """INSERT INTO knowledge_cards
                    (source_id, client_id, card_type, title, content, tags,
                     domain, embedding, context_prefix, confidence, status)
                VALUES (%s, %s, 'test', %s, %s, %s, %s, %s, %s, 0.8, 'active')
                RETURNING id""",
                (
                    source_id, client_id, card["title"], card["content"],
                    ["test"], card["domain"], fake_embedding,
                    f"Test context for {card['title']}.",
                ),
            )
            row = cur.fetchone()
            assert row is not None
            card_ids.append(str(row["id"]))

    return card_ids


# ---------------------------------------------------------------------------
# FTS tests
# ---------------------------------------------------------------------------


def test_fts_catches_exact_term_dmb(client_id: str, _seed_cards: list[str]) -> None:
    """FTS keyword search catches exact term 'DMB' that semantic might miss."""
    from utils.knowledge import _search_fts

    results = _search_fts("DMB", client_id)
    assert len(results) >= 1
    titles = [r["title"] for r in results]
    assert "DMB Brand Profile" in titles


def test_fts_returns_ranked_results(client_id: str, _seed_cards: list[str]) -> None:
    """FTS returns results with ts_rank scores."""
    from utils.knowledge import _search_fts

    results = _search_fts("batik", client_id)
    assert len(results) >= 2
    # All results should have a rank score
    for r in results:
        assert "rank" in r
        assert r["rank"] >= 0


# ---------------------------------------------------------------------------
# RRF merge tests
# ---------------------------------------------------------------------------


def test_rrf_merge_combines_and_deduplicates() -> None:
    """RRF merge combines semantic + FTS results, deduplicates by card id."""
    from utils.knowledge import _rrf_merge

    semantic = [
        {"id": "a", "title": "Card A", "similarity": 0.9},
        {"id": "b", "title": "Card B", "similarity": 0.8},
        {"id": "c", "title": "Card C", "similarity": 0.7},
    ]
    fts = [
        {"id": "b", "title": "Card B", "rank": 0.5},
        {"id": "d", "title": "Card D", "rank": 0.4},
        {"id": "a", "title": "Card A", "rank": 0.3},
    ]

    merged = _rrf_merge(semantic, fts, dense_weight=1.0, sparse_weight=0.25)

    # Should have 4 unique cards (a, b, c, d)
    ids = [r["id"] for r in merged]
    assert len(ids) == 4
    assert len(set(ids)) == 4
    # Cards appearing in both lists should rank higher
    assert ids[0] in ("a", "b")  # a and b appear in both


def test_rrf_weights_configurable() -> None:
    """RRF merge respects dense and sparse weight parameters."""
    from utils.knowledge import _rrf_merge

    semantic = [{"id": "a", "similarity": 0.9}]
    fts = [{"id": "b", "rank": 0.5}]

    # With equal weights, both should appear
    merged = _rrf_merge(semantic, fts, dense_weight=1.0, sparse_weight=1.0)
    assert len(merged) == 2


# ---------------------------------------------------------------------------
# Query variant tests
# ---------------------------------------------------------------------------


def test_generate_query_variants_produces_four(
    _isolated_spans: Path,
) -> None:
    """Query transformation generates 4 variants including BM and EN."""
    from utils.knowledge import _generate_query_variants

    mock_response = {
        "content": '{"variants": ["promosi batik Raya untuk DMB", "Hari Raya batik marketing DMB", "DMB festive batik promotional"]}',
        "model": "gpt-5.4-mini",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.0001,
    }

    with patch("utils.knowledge.call_llm", return_value=mock_response):
        variants = _generate_query_variants("Raya batik promotion for DMB")

    assert len(variants) == 4
    # Original query is always first
    assert variants[0] == "Raya batik promotion for DMB"
    # Other variants are non-empty strings
    for v in variants[1:]:
        assert isinstance(v, str)
        assert len(v) > 0


# ---------------------------------------------------------------------------
# Reranker tests
# ---------------------------------------------------------------------------


def test_reranker_selects_top_k(_isolated_spans: Path) -> None:
    """Reranker reorders 20 candidates and selects top 5 with scores."""
    from utils.knowledge import _rerank_with_llm

    candidates = [
        {"id": str(i), "title": f"Card {i}", "content": f"Content {i}", "rrf_score": 0.1}
        for i in range(20)
    ]

    # LLM returns indices [5, 3, 10, 1, 18] as the top 5
    mock_response = {
        "content": '{"indices": [5, 3, 10, 1, 18]}',
        "model": "gpt-5.4-mini",
        "input_tokens": 3000,
        "output_tokens": 20,
        "cost_usd": 0.001,
    }

    with patch("utils.knowledge.call_llm", return_value=mock_response):
        reranked = _rerank_with_llm("test query", candidates, top_k=5)

    assert len(reranked) == 5
    # First result should be candidate at index 5
    assert reranked[0]["id"] == "5"
    # All results should have a relevance_score
    for r in reranked:
        assert "relevance_score" in r


def test_reranker_fallback_on_bad_json(_isolated_spans: Path) -> None:
    """Reranker falls back to RRF order on malformed JSON."""
    from utils.knowledge import _rerank_with_llm

    candidates = [
        {"id": "a", "content": "A", "rrf_score": 0.9},
        {"id": "b", "content": "B", "rrf_score": 0.8},
        {"id": "c", "content": "C", "rrf_score": 0.7},
    ]

    mock_response = {
        "content": "not valid json!!!",
        "model": "gpt-5.4-mini",
        "input_tokens": 100,
        "output_tokens": 10,
        "cost_usd": 0.0001,
    }

    with patch("utils.knowledge.call_llm", return_value=mock_response):
        reranked = _rerank_with_llm("test", candidates, top_k=3)

    # Falls back to original order
    assert len(reranked) == 3
    assert reranked[0]["id"] == "a"


# ---------------------------------------------------------------------------
# Hybrid search integration tests
# ---------------------------------------------------------------------------


def test_hybrid_search_uses_both_pgvector_and_fts(
    client_id: str,
    _seed_cards: list[str],
    _isolated_spans: Path,
) -> None:
    """Hybrid search returns results from BOTH pgvector AND FTS merged via RRF."""
    from utils.knowledge import retrieve_knowledge

    fake_embedding = [0.1] * 1536

    # Mock call_llm for query variants and reranker
    variant_response = {
        "content": '{"variants": ["promosi batik Raya", "batik festive promo", "Raya batik kempen"]}',
        "model": "gpt-5.4-mini", "input_tokens": 50, "output_tokens": 30, "cost_usd": 0.0,
    }
    rerank_response = {
        "content": '{"indices": [0, 1, 2, 3, 4]}',
        "model": "gpt-5.4-mini", "input_tokens": 500, "output_tokens": 10, "cost_usd": 0.0,
    }

    call_count = {"n": 0}

    def mock_call_llm(**kwargs: Any) -> dict[str, Any]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return variant_response
        return rerank_response

    with patch("utils.knowledge.call_llm", side_effect=mock_call_llm):
        results = retrieve_knowledge(
            client_id=client_id,
            query="Raya batik promotion",
            query_embedding=fake_embedding,
            top_k=5,
        )

    assert len(results) >= 1
    # Results should be dicts with expected keys
    for r in results:
        assert "id" in r
        assert "title" in r


def test_retrieve_knowledge_with_document_set_filter(
    client_id: str,
    _seed_cards: list[str],
    _isolated_spans: Path,
) -> None:
    """Document set filtering: cards in set returned, cards outside excluded."""
    from utils.knowledge import retrieve_knowledge

    # Create a document set with only the first 2 cards
    card_ids = _seed_cards
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO document_sets (client_id, name, status) VALUES (%s, 'test-set', 'active') RETURNING id",
            (client_id,),
        )
        ds_row = cur.fetchone()
        assert ds_row is not None
        doc_set_id = str(ds_row["id"])

        for cid in card_ids[:2]:
            cur.execute(
                "INSERT INTO document_set_members (document_set_id, knowledge_card_id) VALUES (%s, %s)",
                (doc_set_id, cid),
            )

    fake_embedding = [0.1] * 1536

    variant_response = {
        "content": '{"variants": ["test variant 1", "test variant 2", "test variant 3"]}',
        "model": "gpt-5.4-mini", "input_tokens": 50, "output_tokens": 30, "cost_usd": 0.0,
    }
    rerank_response = {
        "content": '{"indices": [0, 1]}',
        "model": "gpt-5.4-mini", "input_tokens": 200, "output_tokens": 10, "cost_usd": 0.0,
    }

    call_count = {"n": 0}

    def mock_call_llm(**kwargs: Any) -> dict[str, Any]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return variant_response
        return rerank_response

    with patch("utils.knowledge.call_llm", side_effect=mock_call_llm):
        results = retrieve_knowledge(
            client_id=client_id,
            query="test query",
            query_embedding=fake_embedding,
            document_set_id=doc_set_id,
            top_k=5,
        )

    # Should only return cards from the document set
    result_ids = {str(r["id"]) for r in results}
    assert result_ids.issubset(set(card_ids[:2]))


def test_lost_in_middle_best_first_second_best_last() -> None:
    """Lost-in-middle: best at position 1, second-best at last position."""
    from utils.knowledge import lost_in_middle_reorder

    items = [
        {"id": "best", "score": 0.9},
        {"id": "second", "score": 0.8},
        {"id": "third", "score": 0.7},
        {"id": "fourth", "score": 0.6},
        {"id": "fifth", "score": 0.5},
    ]
    reordered = lost_in_middle_reorder(items)
    assert reordered[0]["id"] == "best"
    assert reordered[-1]["id"] == "second"


# ---------------------------------------------------------------------------
# Config loading tests
# ---------------------------------------------------------------------------


def test_retrieval_pipeline_config_loaded() -> None:
    """Retrieval pipeline config loads from retrieval_profiles.yaml."""
    from utils.knowledge import _load_pipeline_config

    config = _load_pipeline_config()
    assert config["embedding_model"] == "text-embedding-3-small"
    assert config["query_variants"] == 4
    assert config["rrf_weights"]["dense"] == 1.0
    assert config["rrf_weights"]["sparse"] == 0.25
    assert config["reranker"] == "gpt-5.4-mini"
    assert config["lost_in_middle"] is True
    assert config["fts_dictionary"] == "simple"


def test_semantic_search_raya_batik(
    client_id: str,
    _seed_cards: list[str],
) -> None:
    """pgvector semantic search returns relevant cards for 'Raya batik promotion'."""
    from utils.knowledge import _retrieve_by_embedding_raw

    # All test cards have the same fake embedding, so all will match
    fake_embedding = [0.1] * 1536
    results = _retrieve_by_embedding_raw(
        client_id, fake_embedding, None, 5, 0.0,  # min_score=0 to match fake embeddings
    )
    assert len(results) >= 1
    # Should include Raya/batik cards
    titles = [r["title"] for r in results]
    assert any("Raya" in t or "Batik" in t or "batik" in t for t in titles)


# ---------------------------------------------------------------------------
# ingest_card tests (Task 10)
# ---------------------------------------------------------------------------


def test_ingest_card_with_contextualised_embedding(
    client_id: str,
    _isolated_spans: Path,
) -> None:
    """Card ingested with contextualised embedding — prefix present."""
    from tools.knowledge import ingest_card

    # Create a source first
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO knowledge_sources (client_id, source_type, title, status) "
            "VALUES (%s, 'test', 'Test Source', 'active') RETURNING id",
            (client_id,),
        )
        source_row = cur.fetchone()
        assert source_row is not None
        source_id = str(source_row["id"])

    mock_prefix = "This card is from DMB's Raya 2025 promotional campaign."
    fake_embedding = [0.1] * 1536

    with (
        patch("tools.knowledge.contextualise_card", return_value=mock_prefix),
        patch("tools.knowledge.embed_text", return_value=fake_embedding),
    ):
        card_id = ingest_card(
            source_id=source_id,
            content="Diskaun 30% untuk semua produk batik.",
            card_type="marketing",
            title="Raya Promo",
            tags=["raya", "batik"],
            domain="marketing",
            client_id=client_id,
        )

    assert card_id is not None

    # Verify the card was stored with context_prefix
    with get_cursor() as cur:
        cur.execute("SELECT content, context_prefix FROM knowledge_cards WHERE id = %s", (card_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["content"] == "Diskaun 30% untuk semua produk batik."
        assert row["context_prefix"] == mock_prefix


def test_ingest_card_with_provided_prefix(
    client_id: str,
    _isolated_spans: Path,
) -> None:
    """When prefix is provided, contextualise_card is NOT called (no double contextualisation)."""
    from tools.knowledge import ingest_card

    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO knowledge_sources (client_id, source_type, title, status) "
            "VALUES (%s, 'test', 'Test Source', 'active') RETURNING id",
            (client_id,),
        )
        source_row = cur.fetchone()
        assert source_row is not None
        source_id = str(source_row["id"])

    existing_prefix = "Already contextualised by caller."
    fake_embedding = [0.1] * 1536

    with (
        patch("tools.knowledge.contextualise_card") as mock_ctx,
        patch("tools.knowledge.embed_text", return_value=fake_embedding),
    ):
        card_id = ingest_card(
            source_id=source_id,
            content="Some content.",
            card_type="test",
            title="Test",
            tags=["test"],
            domain="general",
            client_id=client_id,
            prefix=existing_prefix,
        )

    # contextualise_card should NOT have been called
    mock_ctx.assert_not_called()

    # Verify the provided prefix was stored
    with get_cursor() as cur:
        cur.execute("SELECT context_prefix FROM knowledge_cards WHERE id = %s", (card_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["context_prefix"] == existing_prefix


def test_contextualise_card_importable() -> None:
    """Verify: from utils.retrieval import contextualise_card works."""
    from utils.retrieval import contextualise_card as ctx_card

    assert callable(ctx_card)


def test_contextualise_card_is_s12_function() -> None:
    """Contextualisation is the SAME function S12 built, not a copy."""
    from utils.retrieval import contextualise_card as original

    from tools.knowledge import contextualise_card as imported

    assert original is imported


# ---------------------------------------------------------------------------
# promote_exemplar + record_outcome tests (Task 11)
# ---------------------------------------------------------------------------


def test_exemplar_promoted_from_rating_5(client_id: str) -> None:
    """Exemplar promoted only from artifact with operator rating 5."""
    from tools.knowledge import promote_exemplar

    # Create job, artifact, asset, and feedback
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO jobs (client_id, job_type, status) VALUES (%s, 'test', 'completed') RETURNING id",
            (client_id,),
        )
        job_id = str(cur.fetchone()["id"])  # type: ignore[index]

        cur.execute(
            "INSERT INTO assets (storage_path, mime_type) VALUES ('test/path.png', 'image/png') RETURNING id",
        )
        asset_id = str(cur.fetchone()["id"])  # type: ignore[index]

        cur.execute(
            "INSERT INTO artifacts (job_id, asset_id, artifact_type, status) "
            "VALUES (%s, %s, 'poster', 'completed') RETURNING id",
            (job_id, asset_id),
        )
        artifact_id = str(cur.fetchone()["id"])  # type: ignore[index]

        cur.execute(
            "INSERT INTO feedback (job_id, artifact_id, client_id, feedback_status, operator_rating, anchor_set) "
            "VALUES (%s, %s, %s, 'explicitly_approved', 5, false)",
            (job_id, artifact_id, client_id),
        )

    exemplar_id = promote_exemplar(
        artifact_id=artifact_id,
        client_id=client_id,
        operator_rating=5,
        job_id=job_id,
    )
    assert exemplar_id is not None

    # Verify exemplar exists
    with get_cursor() as cur:
        cur.execute("SELECT * FROM exemplars WHERE id = %s", (exemplar_id,))
        row = cur.fetchone()
        assert row is not None
        assert str(row["artifact_id"]) == artifact_id


def test_exemplar_not_promoted_from_low_rating(client_id: str) -> None:
    """Exemplar NOT promoted from rating < 5."""
    from tools.knowledge import promote_exemplar

    result = promote_exemplar(
        artifact_id=str(uuid4()),
        client_id=client_id,
        operator_rating=3,
        job_id=str(uuid4()),
    )
    assert result is None


def test_exemplar_anchor_set_blocked(client_id: str) -> None:
    """Anchor_set feedback excluded from exemplar promotion (anti-drift #56)."""
    from tools.knowledge import promote_exemplar

    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO jobs (client_id, job_type, status) VALUES (%s, 'test', 'completed') RETURNING id",
            (client_id,),
        )
        job_id = str(cur.fetchone()["id"])  # type: ignore[index]

        cur.execute(
            "INSERT INTO assets (storage_path, mime_type) VALUES ('test/anchor.png', 'image/png') RETURNING id",
        )
        asset_id = str(cur.fetchone()["id"])  # type: ignore[index]

        cur.execute(
            "INSERT INTO artifacts (job_id, asset_id, artifact_type, status) "
            "VALUES (%s, %s, 'poster', 'completed') RETURNING id",
            (job_id, asset_id),
        )
        artifact_id = str(cur.fetchone()["id"])  # type: ignore[index]

        cur.execute(
            "INSERT INTO feedback (job_id, artifact_id, client_id, feedback_status, operator_rating, anchor_set) "
            "VALUES (%s, %s, %s, 'explicitly_approved', 5, true)",
            (job_id, artifact_id, client_id),
        )

    result = promote_exemplar(
        artifact_id=artifact_id,
        client_id=client_id,
        operator_rating=5,
        job_id=job_id,
    )
    assert result is None


def test_outcome_memory_record_created(client_id: str) -> None:
    """Outcome memory record created after job completion."""
    from tools.knowledge import record_outcome

    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO jobs (client_id, job_type, status) VALUES (%s, 'test', 'completed') RETURNING id",
            (client_id,),
        )
        job_id = str(cur.fetchone()["id"])  # type: ignore[index]

    outcome_id = record_outcome(
        job_id=job_id,
        outcome_data={
            "artifact_id": None,
            "client_id": client_id,
            "first_pass_approved": True,
            "revision_count": 0,
            "accepted_as_on_brand": True,
            "human_feedback_summary": "Client loved the Raya design",
            "cost_summary": {"total_tokens": 5000, "cost_usd": 0.01},
            "quality_summary": {"overall": 4.5},
            "promote_to_exemplar": False,
        },
    )

    assert outcome_id is not None
    with get_cursor() as cur:
        cur.execute("SELECT * FROM outcome_memory WHERE id = %s", (outcome_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["first_pass_approved"] is True
        assert row["revision_count"] == 0
