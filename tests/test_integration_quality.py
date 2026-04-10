"""Cross-session integration tests (anti-drift #60).

These tests verify that quality intelligence components work together
across session boundaries. Each test exercises a chain of components
built by different sessions.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from contracts.coaching import CoachingResponse
from contracts.interpreted_intent import InterpretedIntent
from tools.coaching import check_content_gate
from tools.template_selector import select_template


class TestFoodBriefFullChain:
    """Food brief → food template → food coaching → production (full chain)."""

    def test_food_brief_gets_food_coaching_then_food_template(self) -> None:
        """Malay food brief → coaching with food questions → complete brief → food template."""
        # Step 1: Thin food brief triggers coaching
        thin_intent = InterpretedIntent(industry="food")
        coaching_result = check_content_gate("poster", thin_intent, "buat poster restoran")

        assert coaching_result.status == "needs_detail"
        assert any(q.field == "occasion" for q in coaching_result.questions)

        # Step 2: After user adds details, gate passes
        complete_intent = InterpretedIntent(
            industry="food",
            occasion="hari_raya",
            mood="festive",
            must_include=["Diskaun 30%", "1-30 April"],
        )
        ready_result = check_content_gate(
            "poster",
            complete_intent,
            "buat poster restoran jualan raya diskaun 30% 1-30 april",
        )
        assert ready_result.status == "ready"

        # Step 3: Template selector prefers food-tagged template
        mock_meta = {
            "poster_food_festive": {
                "tone_fit": ["festive"],
                "occasion_fit": ["hari_raya", "sale"],
                "density": "moderate",
                "cta_prominence": "high",
                "supported_slots": ["hero_image", "headline", "price"],
                "industry_fit": ["food", "retail"],
            },
            "poster_tech_minimal": {
                "tone_fit": ["professional"],
                "occasion_fit": ["product_launch"],
                "density": "minimal",
                "cta_prominence": "low",
                "supported_slots": ["hero_image", "headline"],
                "industry_fit": ["tech"],
            },
        }

        with patch("tools.template_selector._load_template_meta", return_value=mock_meta):
            template = select_template(complete_intent)

        assert template.template_name == "poster_food_festive"
        assert any("industry" in r.lower() for r in template.reasons)


class TestCalibratedThresholdChangesQA:
    """Changing nima_thresholds.yaml → changes nima_prescreen → changes QA."""

    def test_nima_config_drives_prescreen(self) -> None:
        """Loading different config changes nima_prescreen behavior."""
        from tools.visual_scoring import nima_prescreen

        # Default config: regenerate < 4.0, pass > 7.0
        result_default = nima_prescreen(5.0)
        assert result_default["action"] == "proceed_with_caution"

        # Custom config: lower thresholds
        custom_config = {"nima": {"regenerate_below": 2.0, "pass_above": 4.5}}
        result_custom = nima_prescreen(5.0, config=custom_config)
        assert result_custom["action"] == "pass"  # 5.0 > 4.5

        # Custom config: higher thresholds
        strict_config = {"nima": {"regenerate_below": 6.0, "pass_above": 9.0}}
        result_strict = nima_prescreen(5.0, config=strict_config)
        assert result_strict["action"] == "regenerate"  # 5.0 < 6.0


class TestCoachingSurfacesIndustryQuestions:
    """Malay restaurant brief → Malay coaching questions with food suggestions."""

    def test_food_brief_coaching_chain(self) -> None:
        """Food brief → content gate → Malay questions with food-relevant suggestions."""
        intent = InterpretedIntent(industry="food")
        result = check_content_gate("poster", intent, "buat poster restoran")

        assert result.status == "needs_detail"
        assert result.understood.get("industry") == "food"

        # Questions should be in Malay (brief is Malay)
        occasion_q = next(
            (q for q in result.questions if q.field == "occasion"),
            None,
        )
        assert occasion_q is not None
        # Malay question markers
        assert any(
            m in occasion_q.question.lower()
            for m in ["apa", "promosi", "acara"]
        ), f"Expected Malay question, got: {occasion_q.question}"

        # Suggestions should be culturally relevant
        all_suggestions = [s for q in result.questions for s in q.suggestions]
        assert len(all_suggestions) > 0

    def test_coaching_patterns_enrich_refinement(self) -> None:
        """Industry coaching patterns from D8 are loadable and non-empty."""
        from contracts.routing import _get_industry_coaching_context

        for industry in ["food", "fashion", "tech", "education", "retail"]:
            context = _get_industry_coaching_context(industry)
            assert len(context) > 0, f"Empty context for industry: {industry}"
            assert industry in context.lower()


class TestBridgeCoachingIntegration:
    """Bridge layer coaching produces valid CoachingResponse JSON."""

    def test_bridge_thin_brief_valid_json(self) -> None:
        """Bridge returns valid CoachingResponse JSON for thin briefs."""
        from plugins.vizier_tools_bridge import _maybe_coach_thin_brief

        result = _maybe_coach_thin_brief("buat poster")
        assert result is not None

        # Must be valid JSON
        parsed = json.loads(result)

        # Must be a valid CoachingResponse
        response = CoachingResponse.model_validate(parsed)
        assert response.status == "needs_detail"
        assert len(response.questions) > 0

    def test_bridge_complete_brief_proceeds(self) -> None:
        """Bridge returns None for briefs that pass content gate."""
        from plugins.vizier_tools_bridge import _maybe_coach_thin_brief

        mock_result = MagicMock()
        mock_result.intent = InterpretedIntent(
            industry="food",
            occasion="hari_raya",
            must_include=["Diskaun 30%", "1-30 April"],
        )
        with patch(
            "tools.brief_interpreter.interpret_brief",
            return_value=mock_result,
        ):
            result = _maybe_coach_thin_brief(
                "buat poster restoran jualan raya diskaun 30% semua menu 1-30 april"
            )
        assert result is None
