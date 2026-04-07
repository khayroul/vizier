"""Parallel guardrails — brand voice, BM naturalness, GuardrailMailbox.

All guardrails run on GPT-5.4-mini (anti-drift #22, #54).
Guardrails are ADVISORY, not blocking — the QA stage decides whether to act (section 37.2).
Flags deduplicated by GuardrailMailbox before QA stage processes them.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any

from utils.call_llm import call_llm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brand voice guardrail (section 37.2)
# ---------------------------------------------------------------------------

_BRAND_VOICE_PREFIX: list[dict[str, str]] = [
    {
        "role": "system",
        "content": (
            "You are a brand voice consistency checker. Given copy text and a target "
            "register (formal/casual/neutral), determine if the copy matches. "
            "Return JSON: {\"flagged\": true/false, \"issue\": \"description if flagged\", "
            "\"register_detected\": \"formal/casual/neutral\"}"
        ),
    },
]


def check_brand_voice(
    *,
    copy: str,
    copy_register: str,
    brand_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check if copy matches the target brand voice register.

    Args:
        copy: The copy text to check.
        copy_register: Target register ('formal', 'casual', 'neutral').
        brand_config: Optional brand configuration for context.

    Returns:
        Dict with flagged (bool), issue (str), register_detected (str).
    """
    brand_context = ""
    if brand_config:
        brand_context = f"\nBrand context: {brand_config.get('brand_voice', 'not specified')}"

    user_msg = (
        f"Target register: {copy_register}{brand_context}\n\n"
        f"Copy to check:\n{copy}"
    )

    result = call_llm(
        stable_prefix=_BRAND_VOICE_PREFIX,
        variable_suffix=[{"role": "user", "content": user_msg}],
        model="gpt-5.4-mini",
        temperature=0.2,
        max_tokens=200,
        response_format={"type": "json_object"},
    )

    import json

    try:
        parsed = json.loads(result["content"])
        return {
            "flagged": bool(parsed.get("flagged", False)),
            "issue": str(parsed.get("issue", "")),
            "register_detected": str(parsed.get("register_detected", "unknown")),
        }
    except json.JSONDecodeError:
        logger.warning("Brand voice check returned non-JSON")
        return {"flagged": False, "issue": "", "register_detected": "unknown"}


# ---------------------------------------------------------------------------
# BM naturalness heuristic (section 7.4, Layer 1)
# ---------------------------------------------------------------------------

# Overly formal / Indonesian-sounding markers in BM text
_BM_FORMAL_MARKERS = [
    "dengan ini",         # "hereby"
    "sebagaimana",        # "as per" (formal)
    "merujuk kepada",     # "referring to" (bureaucratic)
    "adalah dimaklumkan", # "it is informed" (gov-speak)
    "sehubungan itu",     # "in connection with that"
    "bersama-sama ini",   # "herewith"
    "tertakluk kepada",   # "subject to" (legal)
    "diperakui",          # "certified" (officialese)
]

# Indonesian words commonly confused with BM
_INDONESIAN_MARKERS = [
    "anda",   # ID: you (BM: awak/kamu)
    "bisa",   # ID: can (BM: boleh)
    "kalau",  # ID-leaning: if (BM prefers: jika/sekiranya for formal, kalau OK casual)
    "cuma",   # ID-leaning: only (BM: sahaja/hanya)
    "sangat", # ID-leaning for "very" (BM often uses "amat" or "sungguh" formally)
]


def check_bm_naturalness(text: str) -> dict[str, Any]:
    """Check BM copy for overly formal or Indonesian-sounding patterns.

    Uses deterministic heuristics (zero tokens, zero cost).

    Args:
        text: BM text to check.

    Returns:
        Dict with flagged (bool), issues (list[str]), formal_density (float).
    """
    text_lower = text.lower()
    issues: list[str] = []

    # Check formal markers
    formal_found = [m for m in _BM_FORMAL_MARKERS if m in text_lower]
    if formal_found:
        issues.append(f"Overly formal markers: {', '.join(formal_found)}")

    # Check Indonesian markers
    indo_found = [m for m in _INDONESIAN_MARKERS if re.search(rf"\b{m}\b", text_lower)]
    if indo_found:
        issues.append(f"Indonesian-sounding words: {', '.join(indo_found)}")

    # Sentence length check — average > 25 words suggests overly formal
    sentences = [s.strip() for s in re.split(r"[.!?]", text) if s.strip()]
    if sentences:
        avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_words > 25:
            issues.append(f"Average sentence length too high: {avg_words:.1f} words")

    # Passive voice density — high passive = formal/bureaucratic
    passive_patterns = re.findall(r"\bdi\w+kan\b", text_lower)
    if len(passive_patterns) > 3:
        issues.append(f"High passive voice density: {len(passive_patterns)} passive constructions")

    formal_density = (len(formal_found) + len(indo_found)) / max(len(text.split()), 1)

    return {
        "flagged": len(issues) > 0,
        "issues": issues,
        "formal_density": round(formal_density, 3),
    }


# ---------------------------------------------------------------------------
# GuardrailMailbox — deduplication (section 37.2)
# ---------------------------------------------------------------------------


class GuardrailMailbox:
    """Collects guardrail flags and deduplicates by issue type.

    Multiple flags about the same issue type are merged into a single
    actionable item with a count and all details preserved.
    """

    def __init__(self) -> None:
        self._flags: defaultdict[str, list[str]] = defaultdict(list)

    def add_flag(self, *, issue_type: str, detail: str) -> None:
        """Add a guardrail flag.

        Args:
            issue_type: Category of the issue (e.g. 'register_mismatch', 'bm_naturalness').
            detail: Specific description of this occurrence.
        """
        self._flags[issue_type].append(detail)

    def collect(self) -> list[dict[str, Any]]:
        """Return deduplicated flags as actionable items.

        Returns:
            List of dicts, each with issue_type, count, details, and summary.
        """
        items: list[dict[str, Any]] = []
        for issue_type, details in self._flags.items():
            items.append({
                "issue_type": issue_type,
                "count": len(details),
                "details": details,
                "summary": details[0] if len(details) == 1 else f"{len(details)} occurrences",
            })
        return items

    def has_flags(self) -> bool:
        """Check if any flags have been collected."""
        return len(self._flags) > 0

    def clear(self) -> None:
        """Clear all collected flags."""
        self._flags.clear()


# ---------------------------------------------------------------------------
# Parallel guardrails runner (section 37.2)
# ---------------------------------------------------------------------------


def run_parallel_guardrails(
    *,
    copy: str,
    copy_register: str = "neutral",
    brand_config: dict[str, Any] | None = None,
    language: str = "en",
) -> list[dict[str, Any]]:
    """Run all applicable guardrails and return deduplicated flags.

    Guardrails run sequentially in Month 1-2 (async in future).
    All LLM guardrails use GPT-5.4-mini (anti-drift #22).

    Args:
        copy: The text to check.
        copy_register: Target register ('formal', 'casual', 'neutral').
        brand_config: Optional brand configuration.
        language: ISO 639-1 language code.

    Returns:
        List of deduplicated guardrail flags.
    """
    mailbox = GuardrailMailbox()

    # Brand voice check (LLM-based)
    voice_result = check_brand_voice(
        copy=copy,
        copy_register=copy_register,
        brand_config=brand_config,
    )
    if voice_result["flagged"]:
        mailbox.add_flag(
            issue_type="register_mismatch",
            detail=voice_result["issue"],
        )

    # BM naturalness check (heuristic, zero tokens)
    if language == "ms":
        bm_result = check_bm_naturalness(copy)
        if bm_result["flagged"]:
            for issue in bm_result["issues"]:
                mailbox.add_flag(issue_type="bm_naturalness", detail=issue)

    return mailbox.collect()
