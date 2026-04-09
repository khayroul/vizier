"""Tests for brief interpreter tool."""
from __future__ import annotations

from unittest.mock import patch

from contracts.interpreted_intent import InterpretedIntent
from tools.brief_interpreter import InterpretationResult, interpret_brief


class TestBriefInterpreter:
    def test_interpret_returns_typed_intent(self) -> None:
        mock_response = {
            "content": (
                '{"occasion":"hari_raya","audience":"malay_families",'
                '"mood":"festive","layout_hint":"","text_density":"moderate",'
                '"cta_style":"medium","cultural_context":"islamic_festive",'
                '"must_include":["date","venue"],"must_avoid":[]}'
            ),
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
        }
        with patch("tools.brief_interpreter.call_llm", return_value=mock_response):
            result = interpret_brief(
                "Create a Hari Raya poster with date and venue",
            )

        assert isinstance(result, InterpretationResult)
        assert isinstance(result.intent, InterpretedIntent)
        assert result.intent.occasion == "hari_raya"
        assert "date" in result.intent.must_include
        assert result.input_tokens == 100

    def test_interpret_handles_malformed_json(self) -> None:
        mock_response = {
            "content": "not valid json {",
            "input_tokens": 50,
            "output_tokens": 20,
            "cost_usd": 0.0005,
        }
        with patch("tools.brief_interpreter.call_llm", return_value=mock_response):
            result = interpret_brief("Some brief")

        assert isinstance(result.intent, InterpretedIntent)
        assert result.intent.occasion == ""

    def test_interpret_minimal_brief_returns_sparse_intent(self) -> None:
        mock_response = {
            "content": (
                '{"occasion":"","audience":"","mood":"","layout_hint":"",'
                '"text_density":"moderate","cta_style":"medium",'
                '"cultural_context":"","must_include":[],"must_avoid":[]}'
            ),
            "input_tokens": 80,
            "output_tokens": 40,
            "cost_usd": 0.0008,
        }
        with patch("tools.brief_interpreter.call_llm", return_value=mock_response):
            result = interpret_brief("Poster for DMB")

        assert result.intent.text_density == "moderate"
        assert result.intent.occasion == ""

    def test_interpret_extracts_must_include_from_details(self) -> None:
        mock_response = {
            "content": (
                '{"occasion":"event","audience":"general_public",'
                '"mood":"formal","layout_hint":"","text_density":"moderate",'
                '"cta_style":"high","cultural_context":"",'
                '"must_include":["15 May 2026","Grand Hyatt KL","black tie"],'
                '"must_avoid":[]}'
            ),
            "input_tokens": 90,
            "output_tokens": 55,
            "cost_usd": 0.001,
        }
        with patch("tools.brief_interpreter.call_llm", return_value=mock_response):
            result = interpret_brief(
                "Annual gala dinner invitation poster. Black tie event, "
                "15 May 2026, Grand Hyatt KL."
            )

        assert len(result.intent.must_include) == 3
        assert "Grand Hyatt KL" in result.intent.must_include

    def test_result_carries_token_metrics(self) -> None:
        mock_response = {
            "content": '{"occasion":"sale","audience":"","mood":"urgent"}',
            "input_tokens": 120,
            "output_tokens": 60,
            "cost_usd": 0.0015,
        }
        with patch("tools.brief_interpreter.call_llm", return_value=mock_response):
            result = interpret_brief("Sale poster")

        assert result.input_tokens == 120
        assert result.output_tokens == 60
        assert result.cost_usd == 0.0015
