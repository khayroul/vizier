"""Per-workflow content gates and language-aware coaching question generation.

Ring 2 behavior — gate definitions and question templates are changeable config.
The coaching contracts (Ring 1) live in contracts/coaching.py.

Content gates replace the word-count heuristic with semantic checks:
- Poster: needs promotion/event + at least one of date/price/contact
- Document: needs topic + purpose + audience
- Brochure: needs product + audience + benefits
"""
from __future__ import annotations

import logging
from typing import Any

from contracts.coaching import CoachingQuestion, CoachingResponse
from contracts.interpreted_intent import InterpretedIntent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language detection (lightweight heuristic)
# ---------------------------------------------------------------------------

_MALAY_MARKERS = frozenset({
    "buat", "nak", "saya", "untuk", "dan", "ini", "itu", "yang",
    "tolong", "sila", "boleh", "dengan", "atau", "dari", "ada",
    "perlu", "mahu", "restoran", "kedai", "jualan", "promosi",
    "poster", "dokumen", "risalah", "acara",
})


def detect_language(text: str) -> str:
    """Detect whether the brief is primarily Malay or English.

    Returns 'ms' for Malay, 'en' for English.
    """
    words = set(text.lower().split())
    malay_count = len(words & _MALAY_MARKERS)
    return "ms" if malay_count >= 2 else "en"


# ---------------------------------------------------------------------------
# Question templates by language
# ---------------------------------------------------------------------------

_QUESTION_TEMPLATES: dict[str, dict[str, dict[str, Any]]] = {
    "ms": {
        "occasion": {
            "question": "Apa promosi atau acara?",
            "why": "Poster tanpa promosi spesifik kurang impak",
            "suggestions": ["Jualan Raya", "Grand Opening", "Menu Baru"],
        },
        "key_details": {
            "question": "Apa maklumat penting yang perlu ada?",
            "why": "Pelanggan perlu tahu harga, tarikh, atau lokasi",
            "suggestions": ["Diskaun 30%", "1-30 April", "Lot 23, SS15"],
        },
        "audience": {
            "question": "Siapa sasaran utama?",
            "why": "Reka bentuk berubah mengikut sasaran",
            "suggestions": ["Keluarga", "Pelajar", "Profesional"],
        },
        "topic": {
            "question": "Apa topik utama dokumen ini?",
            "why": "Dokumen perlu fokus yang jelas",
            "suggestions": ["Latihan guru", "Cadangan projek", "Laporan tahunan"],
        },
        "purpose": {
            "question": "Apa tujuan dokumen ini?",
            "why": "Nada dan format bergantung pada tujuan",
            "suggestions": ["Cadangan kepada pelanggan", "Laporan dalaman", "Bahan pemasaran"],
        },
        "product": {
            "question": "Apa produk atau perkhidmatan utama?",
            "why": "Risalah perlu fokus pada tawaran utama",
            "suggestions": ["Rumah teres", "Pakej spa", "Kursus bahasa"],
        },
        "benefits": {
            "question": "Apa kelebihan utama untuk pelanggan?",
            "why": "Risalah yang baik menekankan manfaat, bukan ciri",
            "suggestions": ["Harga mampu milik", "Lokasi strategik", "Jaminan kualiti"],
        },
    },
    "en": {
        "occasion": {
            "question": "What event or promotion is this for?",
            "why": "Posters without a specific promotion lack impact",
            "suggestions": ["Raya Sale", "Grand Opening", "New Menu"],
        },
        "key_details": {
            "question": "What key information must appear?",
            "why": "Customers need to know price, date, or location",
            "suggestions": ["30% Discount", "April 1-30", "Lot 23, SS15"],
        },
        "audience": {
            "question": "Who is the target audience?",
            "why": "Design language changes by audience",
            "suggestions": ["Families", "Students", "Professionals"],
        },
        "topic": {
            "question": "What is the main topic of this document?",
            "why": "Documents need a clear focus",
            "suggestions": ["Teacher training", "Project proposal", "Annual report"],
        },
        "purpose": {
            "question": "What is the purpose of this document?",
            "why": "Tone and format depend on the purpose",
            "suggestions": ["Client proposal", "Internal report", "Marketing material"],
        },
        "product": {
            "question": "What product or service is featured?",
            "why": "Brochures need to focus on the main offering",
            "suggestions": ["Terrace houses", "Spa packages", "Language courses"],
        },
        "benefits": {
            "question": "What are the key benefits for customers?",
            "why": "Good brochures emphasize benefits, not features",
            "suggestions": ["Affordable pricing", "Strategic location", "Quality guarantee"],
        },
    },
}


# ---------------------------------------------------------------------------
# Content gate definitions
# ---------------------------------------------------------------------------

def _has_occasion(intent: InterpretedIntent) -> bool:
    """Check if intent has an occasion/event/promotion."""
    return bool(intent.occasion)


def _has_key_details(intent: InterpretedIntent) -> bool:
    """Check if intent has at least one concrete detail (date, price, contact)."""
    return len(intent.must_include) >= 1


def _has_audience(intent: InterpretedIntent) -> bool:
    """Check if intent has audience info."""
    return bool(intent.audience)


def _has_topic_from_brief(brief: str) -> bool:
    """Check if the brief has enough substance to infer a topic.

    A brief with 3+ meaningful words (after stop-word removal) implies a topic.
    """
    stop_words = frozenset({
        "a", "an", "the", "i", "me", "my", "we", "our", "you", "your",
        "to", "of", "in", "for", "on", "at", "by", "with", "from",
        "and", "or", "but", "not", "no", "so", "if", "do", "can",
        "saya", "nak", "mahu", "buat", "dan", "ini", "itu", "yang",
        "untuk", "tolong", "sila", "boleh",
        "please", "make", "create", "generate", "design", "help",
    })
    words = brief.lower().split()
    meaningful = [w for w in words if w not in stop_words and len(w) > 1]
    return len(meaningful) >= 3


def _has_purpose(intent: InterpretedIntent) -> bool:
    """Check if intent implies a purpose (mood or industry context)."""
    return bool(intent.mood or intent.industry)


def _check_poster_gate(
    intent: InterpretedIntent, brief: str
) -> list[str]:
    """Return list of missing field names for poster gate."""
    missing: list[str] = []

    has_promo = _has_occasion(intent)
    has_details = _has_key_details(intent)

    if not has_promo and not has_details:
        # Need at least occasion OR key_details
        missing.append("occasion")
        missing.append("key_details")
    elif not has_promo:
        # Has details but no occasion — acceptable, but suggest
        pass
    elif not has_details:
        # Has occasion but no details — acceptable, but suggest
        pass

    return missing


def _check_document_gate(
    intent: InterpretedIntent, brief: str
) -> list[str]:
    """Return list of missing field names for document gate."""
    missing: list[str] = []

    if not _has_topic_from_brief(brief):
        missing.append("topic")
    if not _has_purpose(intent):
        missing.append("purpose")
    if not _has_audience(intent):
        missing.append("audience")

    return missing


def _check_brochure_gate(
    intent: InterpretedIntent, brief: str
) -> list[str]:
    """Return list of missing field names for brochure gate."""
    missing: list[str] = []

    if not _has_topic_from_brief(brief):
        missing.append("product")
    if not _has_audience(intent):
        missing.append("audience")
    if not _has_key_details(intent):
        missing.append("benefits")

    return missing


_GATE_CHECKERS: dict[str, Any] = {
    "poster": _check_poster_gate,
    "brochure": _check_brochure_gate,
    "document": _check_document_gate,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_coaching_questions(
    missing_fields: list[str],
    language: str,
) -> list[CoachingQuestion]:
    """Build CoachingQuestion list from missing fields and language.

    Args:
        missing_fields: Fields that the content gate flagged as missing.
        language: 'ms' for Malay, 'en' for English.

    Returns:
        List of CoachingQuestion with language-appropriate text.
    """
    lang = language if language in _QUESTION_TEMPLATES else "en"
    templates = _QUESTION_TEMPLATES[lang]

    questions: list[CoachingQuestion] = []
    for field_name in missing_fields:
        template = templates.get(field_name)
        if template is None:
            continue
        questions.append(
            CoachingQuestion(
                field=field_name,
                question=template["question"],
                why=template["why"],
                suggestions=template["suggestions"],
                priority="critical",
            )
        )
    return questions


def check_content_gate(
    workflow: str,
    intent: InterpretedIntent,
    brief: str,
) -> CoachingResponse:
    """Check whether a brief passes the content gate for a workflow.

    Args:
        workflow: Workflow name (poster, document, brochure, etc.).
        intent: Parsed InterpretedIntent from the brief.
        brief: Raw brief text.

    Returns:
        CoachingResponse with status 'ready' or 'needs_detail'.
    """
    language = detect_language(brief)

    # Build the "understood" dict from intent
    understood: dict[str, str] = {}
    if intent.industry:
        understood["industry"] = intent.industry
    if intent.occasion:
        understood["occasion"] = intent.occasion
    if intent.mood:
        understood["mood"] = intent.mood
    if intent.audience:
        understood["audience"] = intent.audience
    if intent.cultural_context:
        understood["cultural_context"] = intent.cultural_context

    # Detect workflow from brief if not specified
    effective_workflow = workflow.lower().strip()

    # Get the gate checker
    checker = _GATE_CHECKERS.get(effective_workflow)
    if checker is None:
        # Unknown workflow — pass through (no gate)
        return CoachingResponse(
            status="ready",
            understood=understood,
            questions=[],
        )

    missing = checker(intent, brief)

    if not missing:
        return CoachingResponse(
            status="ready",
            understood=understood,
            questions=[],
        )

    questions = build_coaching_questions(missing, language)

    return CoachingResponse(
        status="needs_detail",
        understood=understood,
        questions=questions,
    )
