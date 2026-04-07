"""Tests for fal.ai URL upload utility."""
from __future__ import annotations

from unittest.mock import patch

from utils.storage import upload_to_fal


class TestUploadToFal:
    """upload_to_fal() returns a fal-hosted URL from raw bytes."""

    def test_returns_fal_url(self) -> None:
        with patch("utils.storage.fal_client") as mock_fal:
            mock_fal.upload.return_value = "https://fal.media/files/test/abc123.jpg"
            url = upload_to_fal(b"\xff\xd8\xff\xe0fake-jpeg", content_type="image/jpeg")
            assert url.startswith("https://")
            mock_fal.upload.assert_called_once()

    def test_passes_bytes_to_fal(self) -> None:
        with patch("utils.storage.fal_client") as mock_fal:
            mock_fal.upload.return_value = "https://fal.media/files/test/abc123.png"
            data = b"\x89PNGfake"
            upload_to_fal(data, content_type="image/png")
            call_args = mock_fal.upload.call_args[0]
            assert call_args[0] == data
