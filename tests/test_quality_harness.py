"""Tests for offline quality harness."""
from __future__ import annotations

from unittest.mock import patch

from tools.quality_harness import evaluate_brief, load_benchmark_briefs, run_harness


class TestQualityHarness:
    def test_load_benchmark_briefs_returns_list(self) -> None:
        briefs = load_benchmark_briefs()
        assert isinstance(briefs, list)
        assert len(briefs) >= 10
        assert all("id" in b for b in briefs)
        assert all("raw_input" in b for b in briefs)

    def test_evaluate_brief_with_mocked_llm(self) -> None:
        mock_response = {
            "content": (
                '{"occasion":"hari_raya","audience":"malay_families",'
                '"mood":"festive","layout_hint":"","text_density":"moderate",'
                '"cta_style":"medium","cultural_context":"islamic_festive",'
                '"must_include":["date","venue","dress code"],"must_avoid":[]}'
            ),
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
        }
        brief = {
            "id": "bench_festive_raya",
            "raw_input": "Create a Hari Raya open house poster",
            "expected": {
                "occasion": "hari_raya",
                "mood": "festive",
                "must_include": ["date", "venue", "dress code"],
                "required_slots": ["headline", "body_text", "cta", "event_meta"],
            },
        }
        with patch("tools.brief_interpreter.call_llm", return_value=mock_response):
            result = evaluate_brief(brief)

        assert result["brief_id"] == "bench_festive_raya"
        assert result["aggregate_score"] > 0
        assert result["template"] != ""
        assert "intent_scores" in result

    def test_evaluate_brief_scores_occasion_correctly(self) -> None:
        mock_response = {
            "content": '{"occasion":"sale","mood":"urgent"}',
            "input_tokens": 50,
            "output_tokens": 30,
            "cost_usd": 0.0005,
        }
        brief = {
            "id": "test_sale",
            "raw_input": "50% off sale poster",
            "expected": {"occasion": "sale", "mood": "urgent"},
        }
        with patch("tools.brief_interpreter.call_llm", return_value=mock_response):
            result = evaluate_brief(brief)

        assert result["intent_scores"]["occasion_accuracy"] == 5.0
        assert result["intent_scores"]["mood_accuracy"] == 5.0

    def test_run_harness_single_brief(self) -> None:
        mock_response = {
            "content": '{"occasion":"","mood":"","text_density":"moderate"}',
            "input_tokens": 50,
            "output_tokens": 30,
            "cost_usd": 0.0005,
        }
        with patch("tools.brief_interpreter.call_llm", return_value=mock_response):
            summary = run_harness(brief_id="bench_minimal_brief")

        assert summary["total_briefs"] == 1
        assert summary["successful"] == 1
        assert "median_score" in summary

    def test_run_harness_unknown_brief(self) -> None:
        summary = run_harness(brief_id="nonexistent_brief")
        assert "error" in summary
