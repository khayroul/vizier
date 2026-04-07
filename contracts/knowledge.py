"""Knowledge spine contracts.

Pydantic models for retrieval pipeline return types.
"""
from __future__ import annotations

from pydantic import BaseModel


class RetrievedCard(BaseModel):
    """A knowledge card returned by the retrieval pipeline."""

    card_id: str
    title: str
    content: str
    context_prefix: str | None
    score: float
    source: str  # "semantic" | "keyword" | "hybrid"
    domain: str | None
    tags: list[str]


class PipelineConfig(BaseModel):
    """Retrieval pipeline configuration loaded from YAML."""

    embedding_model: str
    embedding_dim: int
    min_score: float
    rrf_weights: dict[str, float]
    reranker: str
    reranker_candidates: int
    reranker_top_k: int
    query_variants: int
    lost_in_middle: bool
    fts_dictionary: str


class SearchResult(BaseModel):
    """Result of a full knowledge search pipeline run."""

    cards: list[RetrievedCard]
    query_variants: list[str]
    pipeline_config: PipelineConfig
