"""Tests for intent-aware template selector."""
from __future__ import annotations

from contracts.interpreted_intent import InterpretedIntent
from tools.template_selector import select_template


class TestTemplateSelector:
    def test_festive_brief_does_not_default(self) -> None:
        intent = InterpretedIntent(
            occasion="hari_raya",
            mood="festive",
            text_density="moderate",
        )
        result = select_template(intent)
        assert result.template_name != ""
        assert result.score > 0

    def test_sale_brief_selects_promo_grid(self) -> None:
        intent = InterpretedIntent(
            occasion="sale",
            mood="urgent",
            text_density="moderate",
            cta_style="high",
        )
        result = select_template(intent, active_slots={"offer_block", "badge"})
        assert result.template_name == "poster_promo_grid"

    def test_minimal_brief_falls_back_to_default(self) -> None:
        intent = InterpretedIntent()
        result = select_template(intent)
        assert result.template_name == "poster_default"

    def test_different_moods_produce_different_templates(self) -> None:
        festive = select_template(
            InterpretedIntent(mood="festive", occasion="hari_raya"),
        )
        premium = select_template(
            InterpretedIntent(mood="premium", occasion="announcement"),
        )
        urgent = select_template(
            InterpretedIntent(mood="urgent", occasion="sale"),
            active_slots={"offer_block"},
        )
        templates = {festive.template_name, premium.template_name, urgent.template_name}
        assert len(templates) >= 2, f"Expected variety, got: {templates}"

    def test_formal_event_selects_floating_card(self) -> None:
        intent = InterpretedIntent(
            occasion="event",
            mood="formal",
            text_density="moderate",
            cta_style="medium",
        )
        result = select_template(intent, active_slots={"event_meta", "footer"})
        assert result.template_name == "poster_floating_card"

    def test_premium_announcement_selects_minimal(self) -> None:
        intent = InterpretedIntent(
            occasion="announcement",
            mood="premium",
            text_density="minimal",
            cta_style="low",
        )
        result = select_template(intent)
        # Must pick a minimal-density, premium-toned template (original or D4-derived)
        assert any("density" in r.lower() for r in result.reasons)
        assert any("tone" in r.lower() or "premium" in r.lower() for r in result.reasons)

    def test_dense_formal_selects_stacked_type(self) -> None:
        intent = InterpretedIntent(
            occasion="awareness",
            mood="serious",
            text_density="dense",
            cta_style="low",
        )
        result = select_template(
            intent, active_slots={"footer", "disclaimer"},
        )
        assert result.template_name == "poster_stacked_type"

    def test_score_is_positive_for_matched_template(self) -> None:
        intent = InterpretedIntent(
            occasion="product_launch",
            mood="professional",
        )
        result = select_template(intent)
        assert result.score > 0

    def test_reasons_populated_on_match(self) -> None:
        intent = InterpretedIntent(
            occasion="sale",
            mood="urgent",
        )
        result = select_template(intent)
        assert len(result.reasons) > 0
