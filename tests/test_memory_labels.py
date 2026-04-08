"""Unit tests for heuristic memory labels and label-aware retrieval behavior."""

from __future__ import annotations

from unittest.mock import patch


def test_classify_memory_labels_assigns_expected_labels() -> None:
    from utils.memory_labels import classify_memory_labels

    labels = classify_memory_labels(
        title="DMB Raya launch defaults",
        content="Always keep the CTA visible for the festive campaign audience.",
        card_type="client",
        domain="marketing",
        tags=["brand", "promotion"],
    )

    assert "identity" in labels
    assert "campaign" in labels
    assert "constraint" in labels
    assert "audience" in labels


def test_retrieve_knowledge_boosts_label_overlap() -> None:
    from utils.knowledge import retrieve_knowledge

    semantic_results = [
        {
            "id": "card-a",
            "title": "General process note",
            "content": "Pipeline checklist",
            "memory_labels": ["process"],
            "context_prefix": "ctx",
        },
        {
            "id": "card-b",
            "title": "Raya campaign guidance",
            "content": "Festive campaign audience insight",
            "memory_labels": ["campaign", "audience"],
            "context_prefix": "ctx",
        },
    ]

    reranked = [
        {**semantic_results[0], "relevance_score": 0.9, "rrf_score": 0.9},
        {**semantic_results[1], "relevance_score": 0.8, "rrf_score": 0.8},
    ]

    with patch(
        "utils.knowledge._retrieve_by_embedding_raw",
        return_value=semantic_results,
    ), patch(
        "utils.knowledge._search_fts",
        return_value=[],
    ), patch(
        "utils.knowledge._generate_query_variants",
        return_value=["Raya campaign for families"],
    ), patch(
        "utils.knowledge._rerank_with_llm",
        return_value=reranked,
    ):
        results = retrieve_knowledge(
            client_id="demo-client",
            query="Raya campaign for families",
            query_embedding=[0.1, 0.2],
            top_k=2,
        )

    assert results[0]["id"] == "card-b"
    assert results[0]["label_overlap_count"] >= 1
    assert "query_labels" in results[0]


def test_assemble_context_surfaces_query_labels() -> None:
    from utils.knowledge import assemble_context

    with patch(
        "utils.knowledge.retrieve_knowledge",
        return_value=[],
    ):
        ctx = assemble_context(
            client_id="demo",
            query="Raya campaign for families",
            include_knowledge=True,
            top_k=2,
        )

    assert "query_labels" in ctx
    assert "query_labels" in ctx["context_layers"]
