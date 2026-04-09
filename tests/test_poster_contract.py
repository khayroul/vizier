"""Tests for PosterContentSchema Ring 1 contract."""
from __future__ import annotations

from contracts.poster import PosterContentSchema


class TestPosterContentSchema:
    def test_required_fields_only(self) -> None:
        schema = PosterContentSchema(
            headline="Grand Opening",
            body_text="Join us for an evening of celebration",
            cta="Register Now",
            background_image="/tmp/hero.jpg",
        )
        assert schema.headline == "Grand Opening"
        assert schema.kicker == ""
        assert schema.event_meta is None

    def test_full_schema_with_optional_slots(self) -> None:
        schema = PosterContentSchema(
            headline="Raya Sale",
            body_text="Up to 50% off",
            cta="Shop Now",
            background_image="/tmp/sale.jpg",
            subheadline="This weekend only",
            kicker="LIMITED TIME",
            offer_block={"discount": "50%", "validity": "April 10-12"},
            badge="SALE",
            footer="Terms apply. While stocks last.",
        )
        assert schema.badge == "SALE"
        assert schema.offer_block is not None
        assert schema.offer_block["discount"] == "50%"

    def test_backward_compat_to_legacy_dict(self) -> None:
        schema = PosterContentSchema(
            headline="Test",
            body_text="Body",
            cta="CTA",
            background_image="/tmp/img.jpg",
        )
        legacy = schema.to_legacy_dict()
        assert set(legacy.keys()) == {
            "headline", "subheadline", "cta", "body_text", "background_image",
        }

    def test_active_slots_returns_populated_only(self) -> None:
        schema = PosterContentSchema(
            headline="H",
            body_text="B",
            cta="C",
            background_image="/tmp/i.jpg",
            kicker="K",
        )
        active = schema.active_optional_slots()
        assert "kicker" in active
        assert "badge" not in active

    def test_empty_optional_slots(self) -> None:
        schema = PosterContentSchema(
            headline="H",
            body_text="B",
            cta="C",
            background_image="/tmp/i.jpg",
        )
        assert schema.active_optional_slots() == set()
