"""One-shot brief interpretation via GPT-5.4-mini structured output.

Ring 2 behavior — the extraction prompt and category vocabulary live here
and can be changed without modifying the Ring 1 InterpretedIntent contract.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from contracts.interpreted_intent import InterpretedIntent
from utils.call_llm import call_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a brief interpreter for a design production engine.
Given a raw production request, extract structured intent.

Output ONLY a JSON object with these exact keys:
- occasion: string (e.g. "hari_raya", "product_launch", "sale", "event", \
"awareness", "announcement", "community_event", "health", "maulidur_rasul", "")
- audience: string (e.g. "malay_families", "corporate", "general_public", \
"bargain_shoppers", "children", "")
- mood: string (e.g. "festive", "professional", "urgent", "playful", "formal", \
"premium", "caring", "serious", "")
- layout_hint: string (e.g. "full_bleed_hero", "split_layout", "minimal", "")
- text_density: "minimal" | "moderate" | "dense"
- cta_style: "high" | "medium" | "low" | "none"
- cultural_context: string (e.g. "islamic_festive", "chinese_new_year", \
"malaysian_corporate", "")
- must_include: list of strings the output MUST contain (dates, venues, prices, \
specific info from the brief)
- must_avoid: list of strings the output MUST NOT contain

If information is not in the brief, use empty string or empty list. Do not guess.
Extract must_include items from concrete details mentioned in the brief \
(dates, venues, prices, phone numbers, specific items)."""


@dataclass(frozen=True)
class InterpretationResult:
    """Result of brief interpretation with token metrics."""

    intent: InterpretedIntent
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


def interpret_brief(
    raw_input: str,
    *,
    model: str = "gpt-5.4-mini",
) -> InterpretationResult:
    """Extract structured intent from a raw brief via LLM.

    Returns InterpretationResult with typed intent and token metrics.
    Never raises — returns default intent on failure.
    """
    result = call_llm(
        stable_prefix=[{"role": "system", "content": _SYSTEM_PROMPT}],
        variable_suffix=[{"role": "user", "content": raw_input}],
        model=model,
        temperature=0.2,
        max_tokens=400,
        response_format={"type": "json_object"},
        operation_type="extract",
    )

    try:
        parsed = json.loads(result.get("content", "{}"))
        intent = InterpretedIntent.model_validate(parsed)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Brief interpretation failed to parse: %s", exc)
        intent = InterpretedIntent()

    return InterpretationResult(
        intent=intent,
        input_tokens=result.get("input_tokens", 0),
        output_tokens=result.get("output_tokens", 0),
        cost_usd=result.get("cost_usd", 0.0),
    )
