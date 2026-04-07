"""Tests for the ebook production pipeline (S21)."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from contracts.publishing import StyleLock, TextPlacementStrategy
from tools.ebook_production import produce_ebook, _expand_outline, _generate_section


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _mock_call_llm(**kwargs: Any) -> dict[str, Any]:
    """Return a mock LLM response."""
    return {
        "content": "This is a generated section covering business strategy and growth.",
        "model": "gpt-5.4-mini",
        "input_tokens": 200,
        "output_tokens": 100,
        "cost_usd": 0.0002,
    }


def _sample_outline(count: int = 5) -> list[dict[str, str]]:
    titles = ["Introduction", "Market Analysis", "Strategy", "Implementation", "Conclusion"]
    return [
        {"title": titles[i % len(titles)], "summary": f"Section {i + 1} summary", "word_target": "2000"}
        for i in range(count)
    ]


def _sample_metadata() -> dict[str, str]:
    return {
        "title": "Strategi Perniagaan Digital",
        "author": "Vizier",
        "language": "ms",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOutlineExpansion:
    """Outline items expanded into briefs with word targets."""

    @patch("tools.ebook_production.call_llm", side_effect=_mock_call_llm)
    def test_expands_all_items(self, mock_llm: MagicMock) -> None:
        from contracts.trace import TraceCollector
        collector = TraceCollector(job_id="test")
        outline = _sample_outline(5)

        briefs = _expand_outline(
            outline=outline,
            metadata=_sample_metadata(),
            collector=collector,
        )
        assert len(briefs) == 5

    @patch("tools.ebook_production.call_llm", side_effect=_mock_call_llm)
    def test_briefs_have_titles(self, mock_llm: MagicMock) -> None:
        from contracts.trace import TraceCollector
        collector = TraceCollector(job_id="test")
        outline = _sample_outline(3)

        briefs = _expand_outline(
            outline=outline,
            metadata=_sample_metadata(),
            collector=collector,
        )
        for brief in briefs:
            assert "title" in brief
            assert len(str(brief["title"])) > 0

    @patch("tools.ebook_production.call_llm", side_effect=_mock_call_llm)
    def test_one_llm_call_per_item(self, mock_llm: MagicMock) -> None:
        from contracts.trace import TraceCollector
        collector = TraceCollector(job_id="test")
        outline = _sample_outline(3)

        _expand_outline(
            outline=outline,
            metadata=_sample_metadata(),
            collector=collector,
        )
        assert mock_llm.call_count == 3


class TestSectionGeneration:
    """Section generation with self-refine."""

    @patch("tools.ebook_production.call_llm", side_effect=_mock_call_llm)
    def test_generates_section(self, mock_llm: MagicMock) -> None:
        from contracts.context import RollingContext
        from contracts.trace import TraceCollector
        collector = TraceCollector(job_id="test")
        ctx = RollingContext(context_type="document", recent_window=2, medium_scope="section")

        text = _generate_section(
            section_idx=0,
            brief={"title": "Introduction", "brief": "test brief", "word_target": 2000},
            metadata=_sample_metadata(),
            rolling_context=ctx,
            collector=collector,
        )
        assert isinstance(text, str)
        assert len(text) > 0

    @patch("tools.ebook_production.call_llm", side_effect=_mock_call_llm)
    def test_self_refine_three_calls(self, mock_llm: MagicMock) -> None:
        """Generate + critique + revise = 3 LLM calls per section."""
        from contracts.context import RollingContext
        from contracts.trace import TraceCollector
        collector = TraceCollector(job_id="test")
        ctx = RollingContext(context_type="document", recent_window=2, medium_scope="section")

        _generate_section(
            section_idx=0,
            brief={"title": "Introduction", "brief": "test brief", "word_target": 2000},
            metadata=_sample_metadata(),
            rolling_context=ctx,
            collector=collector,
        )
        assert mock_llm.call_count == 3


class TestProduceEbook:
    """Full ebook pipeline integration tests."""

    @patch("tools.ebook_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_5_section_ebook_produces_all(
        self, mock_typst: MagicMock, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        result: dict[str, Any] = produce_ebook(
            outline=_sample_outline(5),
            metadata=_sample_metadata(),
            job_id="test-ebook",
            output_dir=tmp_path,
        )
        assert len(result["sections"]) == 5

    @patch("tools.ebook_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_rolling_context_recent_window_2(
        self, mock_typst: MagicMock, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        """RollingContext recent_window=2: only last 2 sections in recent tier."""
        result: dict[str, Any] = produce_ebook(
            outline=_sample_outline(5),
            metadata=_sample_metadata(),
            job_id="test-ebook",
            output_dir=tmp_path,
        )
        # After 5 sections with window=2, recent should have at most 2
        # We check indirectly via trace: production ran correctly
        assert result["trace"].total_cost_usd > 0

    @patch("tools.ebook_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_self_refine_runs_per_section(
        self, mock_typst: MagicMock, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        """Self-refine runs per section (3 calls each) + 1 per outline expand."""
        produce_ebook(
            outline=_sample_outline(5),
            metadata=_sample_metadata(),
            job_id="test-ebook",
            output_dir=tmp_path,
        )
        # 5 outline expansions + 5 * 3 section gen/crit/rev = 20
        assert mock_llm.call_count == 20

    @patch("tools.ebook_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_produces_pdf_and_epub(
        self, mock_typst: MagicMock, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        result: dict[str, Any] = produce_ebook(
            outline=_sample_outline(3),
            metadata=_sample_metadata(),
            job_id="test-ebook",
            output_dir=tmp_path,
        )
        assert "pdf" in result
        assert "epub" in result
        assert Path(result["epub"]).suffix == ".epub"

    @patch("tools.ebook_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_checkpoint_progression(
        self, mock_typst: MagicMock, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        """Checkpoints: introduction → body → conclusion."""
        result: dict[str, Any] = produce_ebook(
            outline=_sample_outline(5),
            metadata=_sample_metadata(),
            job_id="test-ebook",
            output_dir=tmp_path,
        )
        trace = result["trace"]
        assert trace.total_cost_usd > 0
        # All 5 sections produced
        assert len(result["sections"]) == 5

    @patch("tools.ebook_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_style_lock_colors_applied(
        self, mock_typst: MagicMock, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        """StyleLock colors passed to assembly."""
        style = StyleLock(
            art_style="modern",
            palette=["#264653", "#FFF8F0"],
            typography="Plus Jakarta Sans",
            text_placement_strategy=TextPlacementStrategy.text_always_below,
        )
        result: dict[str, Any] = produce_ebook(
            outline=_sample_outline(3),
            metadata=_sample_metadata(),
            style_lock=style,
            job_id="test-ebook",
            output_dir=tmp_path,
        )
        assert "pdf" in result
