"""Poster content schema with required and optional slots.

Ring 1 contract — slot names and types are stable.
Ring 2 metadata — template _meta.yaml declares which optional slots it supports.
Ring 3 data — filled content for a specific run.
"""
from __future__ import annotations

from pydantic import BaseModel


class PosterContentSchema(BaseModel):
    """Full poster content schema with required and optional slots."""

    # Required (every template must render these if provided)
    headline: str
    body_text: str
    cta: str
    background_image: str

    # Optional (templates declare support via _meta.yaml)
    subheadline: str = ""
    kicker: str = ""  # small text above headline — date, category, label
    event_meta: dict[str, str] | None = None  # date, time, venue, dress_code
    offer_block: dict[str, str] | None = None  # discount, original_price, sale_price, validity
    badge: str = ""  # corner badge: NEW, SALE, LIMITED
    price: str = ""
    footer: str = ""  # fine print, address, contact
    disclaimer: str = ""
    # logo_treatment deferred — no templates consume it yet.
    # Re-add when at least one template's CSS responds to the value.
    secondary_cta: str = ""

    def to_legacy_dict(self) -> dict[str, str]:
        """Backward compat: return the original 4+1 field dict for existing templates."""
        return {
            "headline": self.headline,
            "subheadline": self.subheadline,
            "cta": self.cta,
            "body_text": self.body_text,
            "background_image": self.background_image,
        }

    def active_optional_slots(self) -> set[str]:
        """Return names of optional slots that have non-empty values."""
        optional_fields = {
            "subheadline", "kicker", "event_meta", "offer_block", "badge",
            "price", "footer", "disclaimer", "secondary_cta",
        }
        active: set[str] = set()
        for name in optional_fields:
            val = getattr(self, name)
            if val:  # truthy: non-empty string, non-None dict
                active.add(name)
        return active
