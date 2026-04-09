"""Tests for InterpretedIntent Ring 1 contract."""
from __future__ import annotations

from contracts.interpreted_intent import InterpretedIntent


class TestInterpretedIntentValidation:
    def test_minimal_valid_intent(self) -> None:
        intent = InterpretedIntent(
            occasion="product_launch",
            audience="general_public",
            mood="professional",
        )
        assert intent.occasion == "product_launch"
        assert intent.must_include == []
        assert intent.must_avoid == []

    def test_full_intent(self) -> None:
        intent = InterpretedIntent(
            occasion="hari_raya",
            audience="malay_families",
            mood="festive",
            layout_hint="full_bleed_hero",
            text_density="moderate",
            cta_style="prominent",
            cultural_context="islamic_festive",
            must_include=["date", "venue"],
            must_avoid=["alcohol"],
        )
        assert intent.cultural_context == "islamic_festive"
        assert len(intent.must_include) == 2

    def test_to_prompt_context_returns_string(self) -> None:
        intent = InterpretedIntent(
            occasion="sale",
            audience="bargain_shoppers",
            mood="urgent",
        )
        ctx = intent.to_prompt_context()
        assert "sale" in ctx
        assert "urgent" in ctx
        assert isinstance(ctx, str)

    def test_to_jsonb_round_trip(self) -> None:
        intent = InterpretedIntent(
            occasion="event",
            must_include=["date", "venue"],
        )
        data = intent.to_jsonb()
        restored = InterpretedIntent.model_validate(data)
        assert restored.occasion == "event"
        assert restored.must_include == ["date", "venue"]

    def test_default_values(self) -> None:
        intent = InterpretedIntent()
        assert intent.occasion == ""
        assert intent.text_density == "moderate"
        assert intent.cta_style == "medium"
        assert intent.must_include == []

    def test_empty_prompt_context_for_defaults(self) -> None:
        intent = InterpretedIntent()
        ctx = intent.to_prompt_context()
        # Only text_density and cta_style have defaults, so they appear
        assert "moderate" in ctx
        assert "medium" in ctx
