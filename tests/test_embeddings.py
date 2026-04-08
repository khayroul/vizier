"""Tests for shared embedding utility."""
from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

from utils.embeddings import embed_text, format_embedding


def test_embed_text_returns_float_list() -> None:
    """embed_text returns a list of 1536 floats."""
    fake_vector = [0.1] * 1536
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [{"embedding": fake_vector}],
        "usage": {"total_tokens": 10},
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("utils.embeddings.httpx.post", return_value=mock_resp), \
         patch("utils.embeddings.record_span") as mock_span:
        result = embed_text("test text")

    assert isinstance(result, list)
    assert len(result) == 1536
    assert all(isinstance(v, float) for v in result)
    # Verify span was recorded
    mock_span.assert_called_once()


def test_embed_text_records_span_with_correct_metadata() -> None:
    """embed_text records a span with model, tokens, cost, and step_type."""
    fake_vector = [0.1] * 1536
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [{"embedding": fake_vector}],
        "usage": {"total_tokens": 42},
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("utils.embeddings.httpx.post", return_value=mock_resp), \
         patch("utils.embeddings.record_span") as mock_span:
        embed_text("test text", job_id="job-123")

    call_kwargs = mock_span.call_args[1]
    assert call_kwargs["model"] == "text-embedding-3-small"
    assert call_kwargs["input_tokens"] == 42
    assert call_kwargs["output_tokens"] == 0
    assert call_kwargs["step_type"] == "embedding"
    assert call_kwargs["job_id"] == "job-123"
    # Cost = 42 * 0.02 / 1_000_000
    assert abs(call_kwargs["cost_usd"] - 42 * 0.02 / 1_000_000) < 1e-12


def test_embed_text_records_span_without_job_id() -> None:
    """embed_text records span even when job_id is not provided."""
    fake_vector = [0.1] * 1536
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [{"embedding": fake_vector}],
        "usage": {"total_tokens": 5},
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("utils.embeddings.httpx.post", return_value=mock_resp), \
         patch("utils.embeddings.record_span") as mock_span:
        embed_text("test")

    call_kwargs = mock_span.call_args[1]
    assert call_kwargs["job_id"] is None


def test_format_embedding_produces_pgvector_string() -> None:
    """format_embedding produces a pgvector-compatible string."""
    vector = [0.1, 0.2, 0.3]
    result = format_embedding(vector)
    assert result == "[0.1,0.2,0.3]"
    assert result.startswith("[")
    assert result.endswith("]")
