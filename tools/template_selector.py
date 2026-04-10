"""Intent-aware template selection — scores templates against interpreted intent.

Ring 2 logic — the scoring weights and metadata are config-driven.
Template _meta.yaml files are the source of truth for template capabilities.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from contracts.interpreted_intent import InterpretedIntent

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "html"


@dataclass(frozen=True)
class TemplateMatch:
    """Result of template scoring."""

    template_name: str
    score: float
    reasons: tuple[str, ...] = ()


def _load_template_meta() -> dict[str, dict[str, Any]]:
    """Load all *_meta.yaml files from templates/html/."""
    meta: dict[str, dict[str, Any]] = {}
    for meta_path in sorted(_TEMPLATES_DIR.glob("*_meta.yaml")):
        template_name = meta_path.stem.replace("_meta", "")
        html_path = _TEMPLATES_DIR / f"{template_name}.html"
        if not html_path.exists():
            continue
        try:
            data = yaml.safe_load(meta_path.read_text()) or {}
            meta[template_name] = data
        except Exception as exc:
            logger.warning("Failed to load %s: %s", meta_path, exc)
    return meta


def select_template(
    intent: InterpretedIntent,
    *,
    active_slots: set[str] | None = None,
    client_style_hint: str = "",
) -> TemplateMatch:
    """Score all templates against intent and return best match.

    Scoring dimensions:
    - mood ↔ tone_fit (3.0 points for match)
    - occasion ↔ occasion_fit (3.0 points for match)
    - text_density ↔ density (1.5 points for match)
    - cta_style ↔ cta_prominence (1.0 points for match)
    - slot compatibility (+0.5 per supported slot, -1.0 per missing required slot)

    Falls back to poster_default when no metadata exists or intent is empty.
    """
    catalog = _load_template_meta()
    if not catalog:
        return TemplateMatch(template_name="poster_default", score=0.0)

    # If intent is essentially empty (no occasion, no mood, no audience, no industry),
    # prefer poster_default — scoring on density/cta defaults alone is noise.
    has_signal = bool(intent.occasion or intent.mood or intent.audience or intent.industry)
    if not has_signal and not active_slots:
        return TemplateMatch(template_name="poster_default", score=0.0)

    active_slots = active_slots or set()
    best = TemplateMatch(template_name="poster_default", score=0.0)

    for name, meta in catalog.items():
        score = 0.0
        reasons: list[str] = []

        # Mood ↔ tone_fit
        tone_fit = set(meta.get("tone_fit", []))
        if intent.mood and intent.mood in tone_fit:
            score += 3.0
            reasons.append(f"mood '{intent.mood}' matches tone_fit")
        elif "versatile" in tone_fit:
            score += 0.5

        # Occasion ↔ occasion_fit
        occasion_fit = set(meta.get("occasion_fit", []))
        if intent.occasion and intent.occasion in occasion_fit:
            score += 3.0
            reasons.append(f"occasion '{intent.occasion}' matches")

        # Text density ↔ density
        template_density = meta.get("density", "moderate")
        if intent.text_density == template_density:
            score += 1.5
            reasons.append("density matches")

        # CTA ↔ cta_prominence
        template_cta = meta.get("cta_prominence", "medium")
        if intent.cta_style == template_cta:
            score += 1.0

        # Industry ↔ industry_fit (2.5 points for match)
        industry_fit = set(meta.get("industry_fit", []))
        if intent.industry and industry_fit:
            if intent.industry in industry_fit:
                score += 2.5
                reasons.append(f"industry '{intent.industry}' matches industry_fit")
            elif "general" in industry_fit:
                score += 0.5  # Generic template, minor bonus

        # Slot compatibility
        supported = set(meta.get("supported_slots", []))
        if active_slots:
            overlap = active_slots & supported
            missing = active_slots - supported
            score += len(overlap) * 0.5
            score -= len(missing) * 1.0
            if missing:
                reasons.append(f"missing slots: {missing}")

        if score > best.score:
            best = TemplateMatch(
                template_name=name,
                score=score,
                reasons=tuple(reasons),
            )

    return best
