"""Shared text embedding utility.

Wraps OpenAI text-embedding-3-small API. Extracted from tools/research.py
so all modules share one embedding function.
"""
from __future__ import annotations

import os

import httpx


def embed_text(text: str) -> list[float]:
    """Generate 1536-dim embedding via text-embedding-3-small.

    Returns raw float list, reusable for both DB insertion
    and in-memory similarity computation.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        json={"model": "text-embedding-3-small", "input": text},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]  # type: ignore[no-any-return]


def format_embedding(embedding: list[float]) -> str:
    """Format float list as pgvector-compatible string '[0.1,0.2,...]'."""
    return "[" + ",".join(str(v) for v in embedding) + "]"
