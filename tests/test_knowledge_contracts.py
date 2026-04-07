"""Tests for knowledge contracts."""
from __future__ import annotations

from contracts.knowledge import PipelineConfig, RetrievedCard, SearchResult


def test_retrieved_card_from_dict() -> None:
    card = RetrievedCard(
        card_id="abc-123",
        title="Raya promo",
        content="30% discount on batik",
        context_prefix="This card is from DMB's Raya campaign.",
        score=0.85,
        source="hybrid",
        domain="marketing",
        tags=["raya", "batik"],
    )
    assert card.card_id == "abc-123"
    assert card.score == 0.85


def test_retrieved_card_optional_prefix() -> None:
    card = RetrievedCard(
        card_id="abc-123",
        title="Test",
        content="content",
        context_prefix=None,
        score=0.7,
        source="semantic",
        domain=None,
        tags=[],
    )
    assert card.context_prefix is None
    assert card.domain is None


def test_pipeline_config() -> None:
    config = PipelineConfig(
        embedding_model="text-embedding-3-small",
        embedding_dim=1536,
        min_score=0.65,
        rrf_weights={"dense": 1.0, "sparse": 0.25},
        reranker="gpt-5.4-mini",
        reranker_candidates=20,
        reranker_top_k=5,
        query_variants=4,
        lost_in_middle=True,
        fts_dictionary="simple",
    )
    assert config.query_variants == 4
    assert config.rrf_weights["dense"] == 1.0


def test_search_result() -> None:
    card = RetrievedCard(
        card_id="x", title="t", content="c", context_prefix=None,
        score=0.8, source="semantic", domain=None, tags=[],
    )
    config = PipelineConfig(
        embedding_model="text-embedding-3-small", embedding_dim=1536, min_score=0.65,
        rrf_weights={"dense": 1.0, "sparse": 0.25}, reranker="gpt-5.4-mini",
        reranker_candidates=20, reranker_top_k=5, query_variants=4,
        lost_in_middle=True, fts_dictionary="simple",
    )
    result = SearchResult(cards=[card], query_variants=["q1"], pipeline_config=config)
    assert len(result.cards) == 1
