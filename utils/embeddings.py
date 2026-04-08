"""Shared text embedding utility.

Wraps OpenAI text-embedding-3-small API. Extracted from tools/research.py
so all modules share one embedding function.

Every embedding call is metered via ``record_span()`` so token spend
appears in the unified span table and dashboard views.
"""
from __future__ import annotations

import logging
import os
import time
import uuid

import httpx

from utils.spans import record_span

logger = logging.getLogger(__name__)

# Pricing: text-embedding-3-small = $0.02 per 1M tokens
_EMBEDDING_COST_PER_TOKEN = 0.02 / 1_000_000
_EMBEDDING_MODEL = "text-embedding-3-small"


def embed_text(text: str, *, job_id: str | None = None) -> list[float]:
    """Generate 1536-dim embedding via text-embedding-3-small.

    Returns raw float list, reusable for both DB insertion
    and in-memory similarity computation.

    Every call is recorded as a span with model, token count,
    and cost so no embedding usage goes unmetered.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    start = time.perf_counter()
    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        json={"model": _EMBEDDING_MODEL, "input": text},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    duration_ms = (time.perf_counter() - start) * 1000

    # Extract token usage from response
    total_tokens = data.get("usage", {}).get("total_tokens", 0)
    cost_usd = total_tokens * _EMBEDDING_COST_PER_TOKEN

    # Record span — embeddings are input-only (no output tokens)
    record_span(
        step_id=str(uuid.uuid4()),
        model=_EMBEDDING_MODEL,
        input_tokens=total_tokens,
        output_tokens=0,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        job_id=job_id,
        step_type="embedding",
    )

    return data["data"][0]["embedding"]  # type: ignore[no-any-return]


def format_embedding(embedding: list[float]) -> str:
    """Format float list as pgvector-compatible string '[0.1,0.2,...]'."""
    return "[" + ",".join(str(v) for v in embedding) + "]"
