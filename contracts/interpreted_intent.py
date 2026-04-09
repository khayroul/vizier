"""Canonical structured parse of a raw production brief.

Ring 1 contract — the schema is stable.
Ring 2 behavior — the extraction prompt/categories are changeable config.
Ring 3 data — each job's stored row is runtime data.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class InterpretedIntent(BaseModel):
    """Structured intent extracted from a raw production request."""

    occasion: str = ""
    audience: str = ""
    mood: str = ""
    layout_hint: str = ""
    text_density: str = "moderate"  # minimal | moderate | dense
    cta_style: str = "medium"  # high | medium | low | none
    cultural_context: str = ""
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Serialize intent into a human-readable prompt fragment."""
        parts: list[str] = []
        if self.occasion:
            parts.append(f"Occasion: {self.occasion}")
        if self.audience:
            parts.append(f"Audience: {self.audience}")
        if self.mood:
            parts.append(f"Mood/tone: {self.mood}")
        if self.layout_hint:
            parts.append(f"Layout preference: {self.layout_hint}")
        if self.text_density:
            parts.append(f"Text density: {self.text_density}")
        if self.cta_style:
            parts.append(f"CTA prominence: {self.cta_style}")
        if self.cultural_context:
            parts.append(f"Cultural context: {self.cultural_context}")
        if self.must_include:
            parts.append(f"Must include: {', '.join(self.must_include)}")
        if self.must_avoid:
            parts.append(f"Must avoid: {', '.join(self.must_avoid)}")
        return "\n".join(parts)

    def to_jsonb(self) -> dict[str, object]:
        """Serialize for jobs.interpreted_intent JSONB column."""
        return self.model_dump(mode="json")
