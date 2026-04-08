"""Layer 4 — Tool integration tests.

Tests that tools produce correct artifacts with mocked external calls.
Each test exercises a tool's full pipeline: input → processing → output.

External calls (LLM, fal.ai, MinIO) are mocked. Tool wiring is real.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: standard LLM mock response
# ---------------------------------------------------------------------------


def _mock_llm_response(content: str = "test output", **kwargs: Any) -> dict[str, Any]:
    """Build a standard call_llm return value."""
    return {
        "content": content,
        "model": "gpt-5.4-mini",
        "input_tokens": kwargs.get("input_tokens", 50),
        "output_tokens": kwargs.get("output_tokens", 30),
        "cost_usd": kwargs.get("cost_usd", 0.0001),
    }


# ---------------------------------------------------------------------------
# 4a — Poster pipeline: copy → image → scored → stored
# ---------------------------------------------------------------------------


class TestPosterPipeline:
    """Poster tool chain: generate copy, generate image, score, deliver."""

    @patch("utils.call_llm.call_llm")
    def test_generate_poster_returns_copy(self, mock_llm: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """generate_poster tool returns structured copy in poster_copy field."""
        import utils.spans as spans_mod

        test_db = tmp_path / "spans.db"
        monkeypatch.setattr(spans_mod, "DB_PATH", test_db)
        spans_mod.init_db(test_db)

        poster_json = json.dumps({
            "headline": "Selamat Hari Raya",
            "subheadline": "Dari keluarga DMB",
            "cta": "Hubungi kami",
            "body_text": "Tawaran istimewa Raya 2025",
        })
        mock_llm.return_value = _mock_llm_response(content=poster_json)

        from tools.registry import _generate_poster

        result = _generate_poster({"prompt": "buat poster Raya untuk DMB"})

        assert result["status"] == "ok"
        assert "poster_copy" in result
        assert result["poster_copy"] == poster_json

    def test_parse_poster_copy_json(self) -> None:
        """_parse_poster_copy extracts structured fields from JSON output."""
        from tools.registry import _parse_poster_copy

        copy_json = json.dumps({
            "headline": "Big Sale",
            "subheadline": "50% Off",
            "cta": "Buy Now",
            "body_text": "Limited time offer",
        })
        parsed = _parse_poster_copy(copy_json)
        assert parsed["headline"] == "Big Sale"
        assert parsed["cta"] == "Buy Now"

    def test_parse_poster_copy_heuristic_fallback(self) -> None:
        """_parse_poster_copy falls back to heuristic parsing for non-JSON."""
        from tools.registry import _parse_poster_copy

        copy_text = (
            "Headline: Raya 2025\n"
            "Subheadline: Celebrate with us\n"
            "CTA: Order now\n"
            "Body: Special offers for the festive season"
        )
        parsed = _parse_poster_copy(copy_text)
        assert parsed["headline"] == "Raya 2025"
        assert parsed["cta"] == "Order now"

    @patch("utils.call_llm.call_llm")
    def test_classify_artifact_returns_ok(self, mock_llm: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """classify_artifact tool returns status=ok with LLM output."""
        import utils.spans as spans_mod

        test_db = tmp_path / "spans.db"
        monkeypatch.setattr(spans_mod, "DB_PATH", test_db)
        spans_mod.init_db(test_db)

        mock_llm.return_value = _mock_llm_response(content="poster")

        from tools.registry import _classify_artifact

        result = _classify_artifact({"prompt": "buat poster Raya"})
        assert result["status"] == "ok"
        assert result["output"] == "poster"


# ---------------------------------------------------------------------------
# 4b — Research pipeline: query → sources → synthesized
# ---------------------------------------------------------------------------


class TestResearchPipeline:
    """Research tools chain: search → analyse → summarise."""

    def test_web_search_returns_ok(self) -> None:
        """web_search tool returns status=ok stub."""
        from tools.registry import _web_search

        result = _web_search({"query": "Raya 2025 trends"})
        assert result["status"] == "ok"

    def test_trend_analyse_returns_ok(self) -> None:
        """trend_analyse tool returns status=ok."""
        from tools.registry import _trend_analyse

        result = _trend_analyse({"query": "festive marketing"})
        assert result["status"] == "ok"

    @patch("utils.call_llm.call_llm")
    def test_summarise_returns_content(self, mock_llm: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """summarise tool returns LLM-generated summary."""
        import utils.spans as spans_mod

        test_db = tmp_path / "spans.db"
        monkeypatch.setattr(spans_mod, "DB_PATH", test_db)
        spans_mod.init_db(test_db)

        mock_llm.return_value = _mock_llm_response(
            content="Key trends: traditional motifs, vibrant colours, family themes."
        )

        from tools.registry import _summarise

        result = _summarise({"prompt": "summarise Raya marketing trends"})
        assert result["status"] == "ok"
        assert "trends" in result["output"].lower()


# ---------------------------------------------------------------------------
# 4c — Knowledge retrieval: query + client → ranked cards
# ---------------------------------------------------------------------------


class TestKnowledgeRetrieval:
    """Knowledge tools return expected contract shape."""

    def test_knowledge_retrieve_returns_cards_list(self) -> None:
        """knowledge_retrieve returns dict with 'cards' key."""
        from tools.registry import _knowledge_retrieve

        result = _knowledge_retrieve({"query": "DMB brand guidelines"})
        assert result["status"] == "ok"
        assert "cards" in result
        assert isinstance(result["cards"], list)

    def test_knowledge_store_returns_ok(self) -> None:
        """knowledge_store returns status=ok."""
        from tools.registry import _knowledge_store

        result = _knowledge_store({"card": {"title": "Brand Guide", "content": "..."}})
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# 4d — Invoice: line items → Typst → PDF bytes
# ---------------------------------------------------------------------------


class TestInvoiceRendering:
    """Invoice tool generates a PDF from line items via Typst."""

    def test_typst_render_with_source(self) -> None:
        """typst_render tool returns ok for non-empty source."""
        from tools.registry import _typst_render

        result = _typst_render({
            "typst_source": '#set page(width: 100pt)\n"Invoice"',
        })
        assert result["status"] == "ok"

    def test_typst_render_empty_source(self) -> None:
        """typst_render returns graceful message for empty source."""
        from tools.registry import _typst_render

        result = _typst_render({"typst_source": ""})
        assert result["status"] == "ok"
        assert "No Typst source" in result["output"]

    def test_real_typst_produces_pdf(self, tmp_path: Path) -> None:
        """End-to-end: write Typst source, compile, verify PDF header."""
        invoice_source = (
            '#set page(width: 210mm, height: 297mm, margin: 2cm)\n'
            '#set text(size: 11pt)\n'
            '= Invoice VIZ-2025-001\n'
            '#table(\n'
            '  columns: (1fr, auto, auto),\n'
            '  [*Description*], [*Qty*], [*Rate (RM)*],\n'
            '  [Poster Design], [2], [150.00],\n'
            '  [Brochure], [1], [300.00],\n'
            ')\n'
            '*Total: RM 600.00*\n'
        )
        typ_file = tmp_path / "invoice.typ"
        typ_file.write_text(invoice_source)
        pdf_file = tmp_path / "invoice.pdf"

        result = subprocess.run(
            ["typst", "compile", str(typ_file), str(pdf_file)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, f"typst compile failed: {result.stderr}"
        pdf_bytes = pdf_file.read_bytes()
        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 100  # non-trivial PDF


# ---------------------------------------------------------------------------
# 4e — Tool registry completeness
# ---------------------------------------------------------------------------


class TestToolRegistryCompleteness:
    """build_production_registry() includes all workflow YAML tool references."""

    def test_registry_covers_all_workflow_tools(self) -> None:
        """Every tool_name in workflow YAMLs has a registry entry."""
        import yaml

        from tools.registry import build_production_registry

        registry = build_production_registry()
        workflows_dir = Path(__file__).resolve().parent.parent / "manifests" / "workflows"

        missing: list[str] = []
        for yaml_file in sorted(workflows_dir.glob("*.yaml")):
            with yaml_file.open() as fh:
                wf = yaml.safe_load(fh)
            for stage in wf.get("stages", []):
                tool_name = stage.get("tool")
                if tool_name and tool_name not in registry:
                    missing.append(f"{yaml_file.stem}:{tool_name}")

        assert not missing, (
            f"Workflow tools missing from registry: {missing}. "
            "Add entries to tools/registry.py::build_production_registry()"
        )

    def test_all_registry_tools_callable(self) -> None:
        """Every registry entry is callable."""
        from tools.registry import build_production_registry

        registry = build_production_registry()
        for tool_name, tool_fn in registry.items():
            assert callable(tool_fn), f"Registry tool '{tool_name}' is not callable"
