"""Tests for coaching contracts, content gates, and bridge integration."""
from __future__ import annotations

import json

import pytest

from contracts.coaching import CoachingQuestion, CoachingResponse


class TestCoachingResponseContract:
    """CoachingResponse serializes and validates correctly."""

    def test_needs_detail_response(self) -> None:
        response = CoachingResponse(
            status="needs_detail",
            understood={"type": "Poster", "industry": "Food/Restaurant", "language": "Malay"},
            questions=[
                CoachingQuestion(
                    field="occasion",
                    question="Apa promosi atau acara?",
                    why="Poster tanpa promosi spesifik kurang impak",
                    suggestions=["Jualan Raya", "Grand Opening", "Menu Baru"],
                    priority="critical",
                ),
            ],
        )
        assert response.status == "needs_detail"
        assert len(response.questions) == 1
        assert response.questions[0].priority == "critical"

    def test_ready_response(self) -> None:
        response = CoachingResponse(
            status="ready",
            understood={"type": "Poster", "industry": "Food", "occasion": "Raya sale"},
            questions=[],
        )
        assert response.status == "ready"
        assert len(response.questions) == 0

    def test_serializes_to_json(self) -> None:
        response = CoachingResponse(
            status="needs_detail",
            understood={"type": "Poster"},
            questions=[
                CoachingQuestion(
                    field="occasion",
                    question="What event?",
                    why="Posters need a focal event",
                    suggestions=["Sale", "Launch"],
                    priority="critical",
                ),
            ],
        )
        raw = response.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["status"] == "needs_detail"
        assert len(parsed["questions"]) == 1
        assert parsed["questions"][0]["field"] == "occasion"

    def test_roundtrip(self) -> None:
        original = CoachingResponse(
            status="needs_detail",
            understood={"industry": "food"},
            questions=[
                CoachingQuestion(
                    field="key_details",
                    question="Apa maklumat penting?",
                    why="Pelanggan perlu tahu harga/tarikh",
                    suggestions=["Diskaun 30%", "1-30 April"],
                    priority="critical",
                ),
                CoachingQuestion(
                    field="audience",
                    question="Siapa sasaran?",
                    why="Design language changes by audience",
                    suggestions=["Families", "Students"],
                    priority="nice_to_have",
                ),
            ],
        )
        raw = original.model_dump_json()
        restored = CoachingResponse.model_validate_json(raw)
        assert restored.status == original.status
        assert len(restored.questions) == 2
        assert restored.questions[0].field == "occasion" or restored.questions[0].field == "key_details"

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(Exception):
            CoachingResponse(
                status="invalid_status",  # type: ignore[arg-type]
                understood={},
                questions=[],
            )

    def test_invalid_priority_rejected(self) -> None:
        with pytest.raises(Exception):
            CoachingQuestion(
                field="test",
                question="test",
                why="test",
                suggestions=[],
                priority="urgent",  # type: ignore[arg-type]
            )


class TestCoachingQuestion:
    """CoachingQuestion validates fields correctly."""

    def test_suggestions_list(self) -> None:
        question = CoachingQuestion(
            field="occasion",
            question="What event?",
            why="Posters need events",
            suggestions=["Raya", "CNY", "Merdeka"],
            priority="critical",
        )
        assert len(question.suggestions) == 3

    def test_empty_suggestions_allowed(self) -> None:
        question = CoachingQuestion(
            field="notes",
            question="Anything else?",
            why="Catch-all",
            suggestions=[],
            priority="nice_to_have",
        )
        assert question.suggestions == []


# ---------------------------------------------------------------------------
# Content gate tests (Task 12)
# ---------------------------------------------------------------------------

from contracts.interpreted_intent import InterpretedIntent
from tools.coaching import check_content_gate, build_coaching_questions


class TestContentGatePoster:
    """Poster content gate detects missing promotion/details."""

    def test_thin_poster_fails_gate(self) -> None:
        """'buat poster restoran' has no occasion or key details."""
        intent = InterpretedIntent(industry="food")
        result = check_content_gate("poster", intent, "buat poster restoran")
        assert result.status == "needs_detail"
        assert any(q.field == "occasion" for q in result.questions)

    def test_complete_poster_passes_gate(self) -> None:
        """Full brief with occasion + details passes."""
        intent = InterpretedIntent(
            industry="food",
            occasion="hari_raya",
            must_include=["Diskaun 30%", "1-30 April"],
        )
        result = check_content_gate(
            "poster",
            intent,
            "buat poster restoran jualan raya diskaun 30% 1-30 april",
        )
        assert result.status == "ready"

    def test_poster_with_product_and_date_passes(self) -> None:
        """Product + date (no occasion) still passes poster gate."""
        intent = InterpretedIntent(
            industry="food",
            must_include=["Menu Baru", "15 April"],
        )
        result = check_content_gate(
            "poster",
            intent,
            "buat poster restoran menu baru 15 april",
        )
        assert result.status == "ready"


class TestContentGateDocument:
    """Document content gate needs topic + purpose + audience."""

    def test_thin_document_fails(self) -> None:
        intent = InterpretedIntent()
        result = check_content_gate("document", intent, "buat dokumen")
        assert result.status == "needs_detail"

    def test_complete_document_passes(self) -> None:
        intent = InterpretedIntent(
            industry="education",
            audience="teachers",
            mood="professional",
        )
        result = check_content_gate(
            "document",
            intent,
            "buat proposal latihan guru untuk sekolah rendah",
        )
        assert result.status == "ready"


class TestContentGateBrochure:
    """Brochure gate needs product + audience + benefits."""

    def test_thin_brochure_fails(self) -> None:
        intent = InterpretedIntent(industry="real_estate")
        result = check_content_gate("brochure", intent, "buat brochure rumah")
        assert result.status == "needs_detail"


class TestCoachingQuestionLanguage:
    """Questions should be in detected language."""

    def test_malay_brief_gets_malay_questions(self) -> None:
        intent = InterpretedIntent(industry="food")
        result = check_content_gate("poster", intent, "buat poster restoran")
        # Malay brief → at least one question should be in Malay
        all_questions_text = " ".join(q.question for q in result.questions)
        # Check for Malay words (apa, untuk, siapa)
        malay_markers = ["apa", "untuk", "siapa", "promosi", "acara", "sasaran"]
        has_malay = any(m in all_questions_text.lower() for m in malay_markers)
        assert has_malay, f"Expected Malay questions, got: {all_questions_text}"

    def test_english_brief_gets_english_questions(self) -> None:
        intent = InterpretedIntent(industry="tech")
        result = check_content_gate("poster", intent, "make a poster for tech company")
        all_questions_text = " ".join(q.question for q in result.questions)
        english_markers = ["what", "which", "who", "event", "promotion"]
        has_english = any(m in all_questions_text.lower() for m in english_markers)
        assert has_english, f"Expected English questions, got: {all_questions_text}"


# ---------------------------------------------------------------------------
# Bridge integration tests (Task 13)
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock, patch


class TestBridgeCoaching:
    """Tests for the upgraded _maybe_coach_thin_brief in the bridge."""

    def test_very_thin_brief_returns_coaching_json(self) -> None:
        """'buat poster' (0 meaningful words) → CoachingResponse JSON."""
        from plugins.vizier_tools_bridge import _maybe_coach_thin_brief

        result = _maybe_coach_thin_brief("buat poster")
        assert result is not None
        parsed = json.loads(result)
        assert parsed["status"] == "needs_detail"
        assert len(parsed["questions"]) > 0

    def test_complete_brief_returns_none(self) -> None:
        """Fully detailed brief → None (proceed to production)."""
        from plugins.vizier_tools_bridge import _maybe_coach_thin_brief

        mock_result = MagicMock()
        mock_result.intent = InterpretedIntent(
            industry="food",
            occasion="hari_raya",
            must_include=["Diskaun 30%", "1-30 April"],
        )
        with patch(
            "tools.brief_interpreter.interpret_brief",
            return_value=mock_result,
        ):
            result = _maybe_coach_thin_brief(
                "buat poster restoran jualan raya diskaun 30% 1-30 april"
            )
        assert result is None

    def test_medium_brief_missing_details_returns_coaching(self) -> None:
        """Medium brief with enough words but missing critical info → coaching."""
        from plugins.vizier_tools_bridge import _maybe_coach_thin_brief

        mock_result = MagicMock()
        mock_result.intent = InterpretedIntent(industry="food")
        with patch(
            "tools.brief_interpreter.interpret_brief",
            return_value=mock_result,
        ):
            result = _maybe_coach_thin_brief(
                "buat poster untuk restoran saya di SS15"
            )
        # Has 5+ words but no occasion/promotion → should coach
        assert result is not None
        parsed = json.loads(result)
        assert parsed["status"] == "needs_detail"

    def test_coaching_response_has_understood_field(self) -> None:
        """CoachingResponse includes what was understood from the brief."""
        from plugins.vizier_tools_bridge import _maybe_coach_thin_brief

        mock_result = MagicMock()
        mock_result.intent = InterpretedIntent(industry="food", mood="festive")
        with patch(
            "tools.brief_interpreter.interpret_brief",
            return_value=mock_result,
        ):
            result = _maybe_coach_thin_brief(
                "buat poster restoran untuk raya"
            )
        assert result is not None
        parsed = json.loads(result)
        assert "industry" in parsed["understood"]
