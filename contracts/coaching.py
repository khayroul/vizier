"""Coaching contracts for structured brief intelligence responses.

Ring 1 contract — the schema is stable.
These contracts flow between the Hermes bridge and the production pipeline.
Hermes formats them for the user; Vizier produces them as pure data.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CoachingQuestion(BaseModel):
    """A single coaching question with context and suggestions.

    Designed for one-bounce coaching: ask once with concrete suggestions,
    produce on second call regardless. Never ask twice.
    """

    field: str = Field(description="Which spec field this fills (occasion, key_details, audience, etc.)")
    question: str = Field(description="The actual question text, in the user's detected language")
    why: str = Field(description="Why this matters for quality — shown to user for transparency")
    suggestions: list[str] = Field(
        default_factory=list,
        description="2-3 concrete options (not open-ended). Empty for free-text fields.",
    )
    priority: Literal["critical", "nice_to_have"] = Field(
        description="critical = content gate blocker, nice_to_have = quality improvement",
    )


class CoachingResponse(BaseModel):
    """Structured coaching response returned instead of flat text.

    When status is 'needs_detail', Hermes formats the questions naturally
    and asks the user. When status is 'ready', the brief can proceed
    directly to production.
    """

    status: Literal["needs_detail", "ready"] = Field(
        description="needs_detail = ask user, ready = proceed to production",
    )
    understood: dict[str, str] = Field(
        default_factory=dict,
        description="What we already inferred from the brief (show-don't-ask pattern)",
    )
    questions: list[CoachingQuestion] = Field(
        default_factory=list,
        description="Questions to ask (empty when status=ready)",
    )
