"""Tests for shared embedding utility."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from utils.embeddings import embed_text, format_embedding


def test_embed_text_returns_float_list() -> None:
    """embed_text returns a list of 1536 floats."""
    fake_vector = [0.1] * 1536
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"embedding": fake_vector}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("utils.embeddings.httpx.post", return_value=mock_resp):
        result = embed_text("test text")

    assert isinstance(result, list)
    assert len(result) == 1536
    assert all(isinstance(v, float) for v in result)


def test_format_embedding_produces_pgvector_string() -> None:
    """format_embedding produces a pgvector-compatible string."""
    vector = [0.1, 0.2, 0.3]
    result = format_embedding(vector)
    assert result == "[0.1,0.2,0.3]"
    assert result.startswith("[")
    assert result.endswith("]")
