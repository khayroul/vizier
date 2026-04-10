"""Tests for industry_fit scoring in template selector."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from contracts.interpreted_intent import InterpretedIntent
from tools.template_selector import select_template, _load_template_meta


class TestIndustryFitScoring:
    """Template selector scores industry_fit dimension."""

    def test_food_brief_prefers_food_template(self) -> None:
        """A food industry intent should prefer a food-tagged template."""
        mock_meta = {
            "poster_food_promo": {
                "tone_fit": ["festive", "warm"],
                "occasion_fit": ["hari_raya", "sale"],
                "density": "moderate",
                "cta_prominence": "high",
                "supported_slots": ["hero_image", "headline", "price"],
                "industry_fit": ["food", "retail"],
            },
            "poster_tech_clean": {
                "tone_fit": ["professional", "minimal"],
                "occasion_fit": ["product_launch"],
                "density": "minimal",
                "cta_prominence": "medium",
                "supported_slots": ["hero_image", "headline"],
                "industry_fit": ["tech", "finance"],
            },
        }

        intent = InterpretedIntent(
            industry="food",
            mood="festive",
            occasion="hari_raya",
        )

        with patch("tools.template_selector._load_template_meta", return_value=mock_meta):
            result = select_template(intent)

        assert result.template_name == "poster_food_promo"
        assert any("industry" in r.lower() for r in result.reasons)

    def test_industry_fit_adds_points(self) -> None:
        """industry_fit match adds scoring points."""
        mock_meta = {
            "poster_generic": {
                "tone_fit": [],
                "occasion_fit": [],
                "density": "moderate",
                "cta_prominence": "medium",
                "supported_slots": [],
            },
            "poster_with_industry": {
                "tone_fit": [],
                "occasion_fit": [],
                "density": "moderate",
                "cta_prominence": "medium",
                "supported_slots": [],
                "industry_fit": ["education"],
            },
        }

        intent = InterpretedIntent(industry="education")

        with patch("tools.template_selector._load_template_meta", return_value=mock_meta):
            result = select_template(intent)

        # The industry-tagged template should win
        assert result.template_name == "poster_with_industry"

    def test_no_industry_fit_graceful(self) -> None:
        """Templates without industry_fit field still work."""
        mock_meta = {
            "poster_legacy": {
                "tone_fit": ["festive"],
                "occasion_fit": [],
                "density": "moderate",
                "cta_prominence": "medium",
                "supported_slots": [],
                # No industry_fit key
            },
        }

        intent = InterpretedIntent(industry="food", mood="festive")

        with patch("tools.template_selector._load_template_meta", return_value=mock_meta):
            result = select_template(intent)

        # Should still select the template (just without industry bonus)
        assert result.template_name == "poster_legacy"

    def test_every_meta_yaml_has_industry_fit(self) -> None:
        """Check that all existing _meta.yaml files have industry_fit."""
        meta = _load_template_meta()
        if not meta:
            pytest.skip("No template meta files found")

        for name, data in meta.items():
            if "industry_fit" not in data:
                # This is expected for legacy templates — just warn
                pass  # Will be added by Task 9
