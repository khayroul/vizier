"""Tests for the poster production pipeline end-to-end fix.

Covers:
- Typst poster template compilation
- _parse_poster_copy (JSON + heuristic fallback)
- _load_client_style (with and without config)
- _deliver with poster workflow context
- _generate_poster output structure
- _image_generate local file save
- Plugin _extract_nested helper
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates" / "typst"
FONTS_DIR = REPO_ROOT / "assets" / "fonts"


@pytest.fixture()
def poster_copy_json() -> str:
    return json.dumps({
        "headline": "JAGALAH KEBERSIHAN",
        "subheadline": "Cerminan Disiplin",
        "cta": "MARI BERSAMA",
        "body_text": "Buang sampah\nPastikan kelas bersih",
    })


@pytest.fixture()
def poster_copy_labeled() -> str:
    return (
        "Headline: JAGALAH KEBERSIHAN\n"
        "Subheadline: Cerminan Disiplin\n"
        "CTA: MARI BERSAMA\n"
        "Body: Buang sampah di tempat yang disediakan"
    )


@pytest.fixture()
def tmp_image(tmp_path: Path) -> Path:
    """Create a minimal valid PNG file for testing."""
    import struct
    import zlib

    def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        raw = chunk_type + data
        return struct.pack(">I", len(data)) + raw + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)

    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1 RGB
    # Single pixel: filter byte 0 + RGB white (255,255,255)
    raw_row = b"\x00\xff\xff\xff"
    idat_data = zlib.compress(raw_row)

    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", ihdr_data)
    png += _png_chunk(b"IDAT", idat_data)
    png += _png_chunk(b"IEND", b"")

    img = tmp_path / "test_bg.png"
    img.write_bytes(png)
    return img


# ---------------------------------------------------------------------------
# Test: Typst poster template compiles
# ---------------------------------------------------------------------------


class TestPosterTemplate:
    """Verify the poster.typ template compiles with Typst."""

    def test_template_exists(self) -> None:
        template = TEMPLATES_DIR / "poster.typ"
        assert template.exists(), f"poster.typ not found at {template}"

    def test_compiles_with_defaults(self, tmp_path: Path) -> None:
        """Compile poster.typ with default inputs — no background image."""
        template = TEMPLATES_DIR / "poster.typ"
        output = tmp_path / "poster_default.pdf"
        env = {**os.environ, "TYPST_FONT_PATHS": str(FONTS_DIR)}
        result = subprocess.run(
            ["typst", "compile", "--root", "/", str(template), str(output)],
            capture_output=True, text=True, env=env, check=False,
        )
        assert result.returncode == 0, f"Typst failed: {result.stderr}"
        assert output.exists()
        assert output.stat().st_size > 0

    def test_compiles_with_inputs(self, tmp_path: Path, tmp_image: Path) -> None:
        """Compile poster.typ with all inputs provided."""
        template = TEMPLATES_DIR / "poster.typ"
        output = tmp_path / "poster_inputs.pdf"
        env = {**os.environ, "TYPST_FONT_PATHS": str(FONTS_DIR)}
        input_args = [
            "--input", f"background_image={tmp_image}",
            "--input", "headline=TEST HEADLINE",
            "--input", "subheadline=Test Subheadline",
            "--input", "cta=CLICK HERE",
            "--input", "body_text=Line one\nLine two\nLine three",
            "--input", "primary_color=#1a365d",
            "--input", "accent_color=#ed8936",
            "--input", "headline_font=Inter",
            "--input", "body_font=Inter",
        ]
        result = subprocess.run(
            ["typst", "compile", "--root", "/", *input_args, str(template), str(output)],
            capture_output=True, text=True, env=env, check=False,
        )
        assert result.returncode == 0, f"Typst failed: {result.stderr}"
        assert output.exists()
        assert output.stat().st_size > 0


# ---------------------------------------------------------------------------
# Test: _parse_poster_copy
# ---------------------------------------------------------------------------


class TestParsePosterCopy:
    """Test structured copy extraction from LLM output."""

    def test_json_input(self, poster_copy_json: str) -> None:
        from tools.registry import _parse_poster_copy

        result = _parse_poster_copy(poster_copy_json)
        assert result["headline"] == "JAGALAH KEBERSIHAN"
        assert result["subheadline"] == "Cerminan Disiplin"
        assert result["cta"] == "MARI BERSAMA"
        assert "Buang sampah" in result["body_text"]

    def test_json_with_markdown_fencing(self, poster_copy_json: str) -> None:
        from tools.registry import _parse_poster_copy

        fenced = f"```json\n{poster_copy_json}\n```"
        result = _parse_poster_copy(fenced)
        assert result["headline"] == "JAGALAH KEBERSIHAN"

    def test_labeled_fallback(self, poster_copy_labeled: str) -> None:
        from tools.registry import _parse_poster_copy

        result = _parse_poster_copy(poster_copy_labeled)
        assert result["headline"] == "JAGALAH KEBERSIHAN"
        assert result["subheadline"] == "Cerminan Disiplin"
        assert result["cta"] == "MARI BERSAMA"

    def test_unstructured_fallback(self) -> None:
        from tools.registry import _parse_poster_copy

        result = _parse_poster_copy("Just some random text for a poster")
        assert result["body_text"] == "Just some random text for a poster"
        assert result["headline"] == ""

    def test_empty_input(self) -> None:
        from tools.registry import _parse_poster_copy

        result = _parse_poster_copy("")
        # String slots are empty, dict slots are None
        assert result["headline"] == ""
        assert result["body_text"] == ""
        assert result["event_meta"] is None
        assert result["offer_block"] is None


# ---------------------------------------------------------------------------
# Test: _load_client_style
# ---------------------------------------------------------------------------


class TestLoadClientStyle:
    """Test client style loading with and without config files."""

    def test_default_style(self) -> None:
        from tools.registry import _load_client_style

        style = _load_client_style("nonexistent_client_xyz")
        assert "colors" in style
        assert "fonts" in style
        assert style["colors"]["primary"] == "#1a365d"
        assert style["fonts"]["headline"] == "Plus Jakarta Sans"

    def test_default_client(self) -> None:
        from tools.registry import _load_client_style

        style = _load_client_style("default")
        assert "colors" in style
        assert "fonts" in style


# ---------------------------------------------------------------------------
# Test: _deliver with poster context
# ---------------------------------------------------------------------------


class TestDeliver:
    """Test the delivery stage for poster workflows."""

    def test_non_implemented_workflow_returns_stub(self) -> None:
        """Non-implemented workflows return explicit stub status (fail-closed)."""
        from tools.registry import _deliver

        context: dict[str, Any] = {
            "job_context": {"routing": {"workflow": "ebook_production"}},
            "stage_results": [],
        }
        result = _deliver(context)
        assert result["status"] == "stub"
        assert "delivery_not_implemented" in result["output"]

    def test_document_workflow_routes_to_document_delivery(self) -> None:
        """document_production routes to _deliver_document, not stub."""
        from tools.registry import _deliver

        context: dict[str, Any] = {
            "job_context": {"routing": {"workflow": "document_production"}},
            "stage_results": [],
        }
        result = _deliver(context)
        # Should be error (no content), not stub
        assert result["status"] == "error"
        assert result["status"] != "stub"

    def test_poster_no_image(self) -> None:
        from tools.registry import _deliver

        context: dict[str, Any] = {
            "job_context": {"routing": {"workflow": "poster_production"}, "client_id": "default"},
            "stage_results": [{"output": "classified"}],
        }
        result = _deliver(context)
        assert result["status"] == "error"
        assert "no image" in result["output"]

    def test_poster_with_image_and_copy(self, tmp_image: Path, poster_copy_json: str) -> None:
        from tools.registry import _deliver

        context: dict[str, Any] = {
            "job_context": {
                "routing": {"workflow": "poster_production"},
                "client_id": "default",
            },
            "stage_results": [
                {"output": "classified"},
                {
                    "output": "image_generated",
                    "image_path": str(tmp_image),
                    "poster_copy": poster_copy_json,
                },
                {"output": {"score": 4.2}, "score": 4.2},
            ],
        }
        result = _deliver(context)
        # Should attempt PDF composition (may fail if Typst not in PATH during CI)
        assert "image_path" in result
        assert result["image_path"] == str(tmp_image)


# ---------------------------------------------------------------------------
# Test: _generate_poster output structure
# ---------------------------------------------------------------------------


class TestGeneratePoster:
    """Test that _generate_poster returns poster_copy key."""

    @patch("utils.call_llm.call_llm")
    def test_poster_copy_key_survives(self, mock_llm: MagicMock) -> None:
        from tools.registry import _generate_poster

        mock_llm.return_value = {"content": '{"headline": "TEST"}'}
        result = _generate_poster({"prompt": "test poster"})
        assert "poster_copy" in result
        assert result["poster_copy"] == '{"headline": "TEST"}'
        assert result["output"] == result["poster_copy"]


# ---------------------------------------------------------------------------
# Test: executor passes stage_results
# ---------------------------------------------------------------------------


class TestExecutorStageResults:
    """Verify the executor injects stage_results into context."""

    def test_stage_results_in_context(self) -> None:
        """Check that the executor code has the stage_results injection."""
        import ast

        executor_path = REPO_ROOT / "tools" / "executor.py"
        source = executor_path.read_text()
        assert 'context["stage_results"]' in source, (
            "executor.py must inject stage_results into context"
        )


# ---------------------------------------------------------------------------
# Test: plugin _extract_nested
# ---------------------------------------------------------------------------


class TestExtractNested:
    """Test the recursive nested dict walker."""

    @staticmethod
    def _load_plugin() -> Any:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "vizier_tools",
            Path.home() / ".hermes" / "plugins" / "vizier_tools" / "__init__.py",
        )
        assert spec is not None, "Could not find vizier_tools plugin"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    def test_top_level(self) -> None:
        mod = self._load_plugin()
        assert mod._extract_nested({"pdf_path": "/a.pdf"}, "pdf_path") == "/a.pdf"

    def test_nested_in_list(self) -> None:
        mod = self._load_plugin()
        data = {"stages": [{"a": 1}, {"pdf_path": "/b.pdf"}]}
        assert mod._extract_nested(data, "pdf_path") == "/b.pdf"

    def test_missing_key(self) -> None:
        mod = self._load_plugin()
        assert mod._extract_nested({"a": 1}, "missing") is None
