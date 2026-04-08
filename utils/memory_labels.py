"""Lightweight heuristic memory classification for knowledge artifacts.

This keeps classification cheap and deterministic so Vizier can add first-pass
structure to cards and retrieval without introducing a second memory stack.
"""

from __future__ import annotations

from typing import Iterable


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    return any(needle in text for needle in needles)


def classify_memory_labels(
    *,
    content: str = "",
    title: str = "",
    card_type: str = "",
    domain: str = "",
    tags: list[str] | None = None,
    allow_fact_fallback: bool = True,
) -> list[str]:
    """Assign heuristic memory labels to a card-like text blob."""
    tags = tags or []
    lowered_tags = [str(tag).strip().lower() for tag in tags if str(tag).strip()]
    text = " ".join(
        part for part in [
            title.strip().lower(),
            content.strip().lower(),
            card_type.strip().lower(),
            domain.strip().lower(),
            " ".join(lowered_tags),
        ] if part
    )

    labels: list[str] = []

    def add(label: str) -> None:
        if label not in labels:
            labels.append(label)

    if card_type in {"client", "brand_pattern"} or _contains_any(
        text,
        ["brand", "identity", "typography", "colour", "color", "font", "logo"],
    ):
        add("identity")

    if _contains_any(
        text,
        ["tone", "style", "register", "layout", "visual", "headline", "cta", "copy"],
    ):
        add("style")

    if _contains_any(
        text,
        ["must", "must not", "do not", "cannot", "avoid", "required", "never", "always"],
    ):
        add("constraint")

    if _contains_any(
        text,
        ["approved", "rejected", "selected", "chosen", "decision", "decide"],
    ):
        add("decision")

    if _contains_any(
        text,
        ["workflow", "process", "pipeline", "production", "step", "onboarding", "defaults"],
    ):
        add("process")

    if _contains_any(
        text,
        ["campaign", "promo", "promotion", "launch", "sale", "event", "raya", "festive"],
    ):
        add("campaign")

    if _contains_any(
        text,
        ["audience", "customer", "family", "parents", "students", "executives", "middle-class"],
    ):
        add("audience")

    if _contains_any(
        text,
        ["202", "january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december", "season"],
    ):
        add("temporal")

    if not labels and allow_fact_fallback and text:
        add("fact")

    return labels


def classify_query_labels(query: str) -> list[str]:
    """Classify a retrieval query without forcing a fallback label."""
    return classify_memory_labels(content=query, allow_fact_fallback=False)
