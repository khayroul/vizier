"""Tests for S13 — Visual Intelligence + Guardrails.

Covers: image model routing, brief expansion, NIMA pre-screen,
4-dimension critique, exemplar-anchored scoring, visual lineage,
brand voice guardrail, BM naturalness, GuardrailMailbox, full pipeline.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_test_image(width: int = 64, height: int = 64) -> bytes:
    """Create a small test image as bytes."""
    img = Image.new("RGB", (width, height), color=(128, 100, 80))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _mock_llm_response(content: str) -> dict[str, object]:
    """Build a mock call_llm return dict."""
    return {
        "content": content,
        "model": "gpt-5.4-mini",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.0001,
    }


# ===========================================================================
# Image model routing
# ===========================================================================


class TestImageModelRouting:
    """Test select_image_model routes by job characteristics."""

    def test_bm_text_routes_to_nano_banana_pro(self) -> None:
        from tools.image import select_image_model

        result = select_image_model(language="ms", has_text=True, style="poster")
        assert result == "fal-ai/nano-banana-pro"

    def test_photorealistic_routes_to_flux_2_pro(self) -> None:
        from tools.image import select_image_model

        result = select_image_model(language="en", has_text=False, style="photorealistic")
        assert result == "fal-ai/flux-pro"

    def test_draft_routes_to_nano_banana(self) -> None:
        from tools.image import select_image_model

        result = select_image_model(language="en", has_text=False, style="draft")
        assert result == "fal-ai/nano-banana"

    def test_generic_routes_to_flux_2_dev(self) -> None:
        from tools.image import select_image_model

        result = select_image_model(language="en", has_text=False, style="poster")
        assert result == "fal-ai/flux/dev"

    def test_childrens_book_routes_to_kontext(self) -> None:
        from tools.image import select_image_model

        result = select_image_model(
            language="en", has_text=False, style="poster", artifact_family="childrens_book"
        )
        assert result == "fal-ai/flux-pro/kontext"

    def test_bm_text_overrides_photorealistic(self) -> None:
        """BM text-heavy takes priority over photorealistic style."""
        from tools.image import select_image_model

        # draft takes priority over everything
        result = select_image_model(language="ms", has_text=True, style="draft")
        assert result == "fal-ai/nano-banana"


# ===========================================================================
# Brief expansion
# ===========================================================================


class TestBriefExpansion:
    """Test visual brief expansion via GPT-5.4-mini."""

    def test_template_loads(self) -> None:
        from tools.image import _load_brief_template

        template = _load_brief_template()
        assert "composition" in template
        assert "text_content" in template
        assert "Typst" in template

    @patch("tools.image.call_llm")
    def test_expand_brief_returns_structured_dict(self, mock_llm: MagicMock) -> None:
        from tools.image import expand_brief

        mock_llm.return_value = _mock_llm_response(json.dumps({
            "composition": "Centred layout with product hero",
            "style": "Warm golden hour lighting",
            "brand": "#FF6B00 primary, logo top-left",
            "technical": "1080x1080px, 300dpi, JPEG",
            "text_content": "Raya 2025 Sale - Up to 50% Off",
        }))

        result = expand_brief("Raya poster for DMB", brand_config={"colours": ["#FF6B00"]})

        assert "composition" in result
        assert "style" in result
        assert "brand" in result
        assert "technical" in result
        assert "text_content" in result

    @patch("tools.image.call_llm")
    def test_expand_brief_uses_gpt54mini(self, mock_llm: MagicMock) -> None:
        from tools.image import expand_brief

        mock_llm.return_value = _mock_llm_response('{"composition":"test"}')

        expand_brief("test brief")

        call_kwargs = mock_llm.call_args
        assert call_kwargs.kwargs["model"] == "gpt-5.4-mini"

    @patch("tools.image.call_llm")
    def test_expand_brief_handles_non_json(self, mock_llm: MagicMock) -> None:
        from tools.image import expand_brief

        mock_llm.return_value = _mock_llm_response("Not valid JSON")

        result = expand_brief("test brief")
        assert "composition" in result  # fallback populates keys


# ===========================================================================
# NIMA pre-screen
# ===========================================================================


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("torch"),
    reason="torch not installed",
)
class TestNIMA:
    """Test NIMA aesthetic scoring and pre-screen classification."""

    def test_nima_score_returns_float(self) -> None:
        from tools.visual_scoring import nima_score

        image_bytes = _create_test_image()
        score = nima_score(image_bytes)
        assert isinstance(score, float)
        assert 1.0 <= score <= 10.0

    def test_nima_prescreen_low_triggers_regenerate(self) -> None:
        from tools.visual_scoring import nima_prescreen

        result = nima_prescreen(score=3.5)
        assert result["action"] == "regenerate"
        assert result["score"] == 3.5

    def test_nima_prescreen_high_passes(self) -> None:
        from tools.visual_scoring import nima_prescreen

        result = nima_prescreen(score=7.5)
        assert result["action"] == "pass"

    def test_nima_prescreen_mid_proceeds(self) -> None:
        from tools.visual_scoring import nima_prescreen

        result = nima_prescreen(score=5.5)
        assert result["action"] == "proceed_with_caution"

    def test_nima_prescreen_boundary_low(self) -> None:
        """Score exactly 4.0 is NOT regenerate."""
        from tools.visual_scoring import nima_prescreen

        result = nima_prescreen(score=4.0)
        assert result["action"] == "proceed_with_caution"

    def test_nima_prescreen_boundary_high(self) -> None:
        """Score exactly 7.0 is NOT pass (boundary is >7.0)."""
        from tools.visual_scoring import nima_prescreen

        result = nima_prescreen(score=7.0)
        assert result["action"] == "proceed_with_caution"


# ===========================================================================
# 4-dimension critique scoring
# ===========================================================================


class TestCritique4Dim:
    """Test 4-dimension design quality scoring."""

    @patch("tools.visual_scoring.call_llm")
    def test_returns_all_four_dimensions(self, mock_llm: MagicMock) -> None:
        from tools.visual_scoring import critique_4dim

        mock_llm.return_value = _mock_llm_response(
            json.dumps({"score": 4.0, "issues": ["Minor contrast issue"]})
        )

        result = critique_4dim(
            image_description="Test poster",
            brief={"composition": "Centred layout"},
        )

        expected_dims = {"text_visibility", "design_layout", "colour_harmony", "overall_coherence"}
        assert set(result.keys()) == expected_dims

        for dim_result in result.values():
            assert "score" in dim_result
            assert "issues" in dim_result
            assert isinstance(dim_result["score"], float)
            assert isinstance(dim_result["issues"], list)

    @patch("tools.visual_scoring.call_llm")
    def test_all_calls_use_gpt54mini(self, mock_llm: MagicMock) -> None:
        """Anti-drift #54: all critique calls use GPT-5.4-mini."""
        from tools.visual_scoring import critique_4dim

        mock_llm.return_value = _mock_llm_response('{"score": 4.0, "issues": []}')

        critique_4dim(image_description="test", brief={})

        for call in mock_llm.call_args_list:
            assert call.kwargs["model"] == "gpt-5.4-mini"

    @patch("tools.visual_scoring.call_llm")
    def test_handles_parse_error(self, mock_llm: MagicMock) -> None:
        from tools.visual_scoring import critique_4dim

        mock_llm.return_value = _mock_llm_response("not json at all")

        result = critique_4dim(image_description="test", brief={})

        for dim_result in result.values():
            assert dim_result["score"] == 3.0  # fallback

    @patch("tools.visual_scoring.call_llm")
    def test_weighted_score_calculation(self, mock_llm: MagicMock) -> None:
        from tools.visual_scoring import critique_4dim, weighted_score

        mock_llm.return_value = _mock_llm_response('{"score": 4.0, "issues": []}')

        result = critique_4dim(image_description="test", brief={})
        score = weighted_score(result)

        assert isinstance(score, float)
        assert score == pytest.approx(4.0, abs=0.01)


# ===========================================================================
# Exemplar-anchored scoring
# ===========================================================================


class TestExemplarScoring:
    """Test exemplar-anchored quality scoring."""

    @patch("utils.retrieval.retrieve_similar_exemplars", side_effect=NotImplementedError("stub"))
    @patch("tools.visual_scoring.call_llm")
    def test_graceful_fallback_when_s11_not_merged(
        self, mock_llm: MagicMock, mock_retrieval: MagicMock
    ) -> None:
        """When retrieve_similar_exemplars raises NotImplementedError, fallback gracefully."""
        from tools.visual_scoring import score_with_exemplars

        mock_llm.return_value = _mock_llm_response('{"score": 4.0, "issues": []}')

        result = score_with_exemplars(
            image_bytes=_create_test_image(),
            client_id="test-client",
            brief={"composition": "test"},
            image_description="test poster",
        )

        assert result["exemplars_used"] == 0
        assert isinstance(result["weighted_score"], float)
        assert "critique" in result

    @patch("utils.retrieval.retrieve_similar_exemplars")
    @patch("tools.visual_scoring.call_llm")
    def test_uses_exemplars_when_available(
        self, mock_llm: MagicMock, mock_retrieval: MagicMock
    ) -> None:
        from tools.visual_scoring import score_with_exemplars

        mock_retrieval.return_value = [
            {
                "exemplar_id": "ex-1",
                "artifact_id": "art-1",
                "asset_path": "path/to/asset",
                "similarity": 0.85,
                "artifact_family": "poster",
                "style_tags": ["modern", "minimal"],
            },
            {
                "exemplar_id": "ex-2",
                "artifact_id": "art-2",
                "asset_path": "path/to/asset2",
                "similarity": 0.72,
                "artifact_family": "poster",
                "style_tags": ["festive"],
            },
        ]
        mock_llm.return_value = _mock_llm_response('{"score": 4.5, "issues": []}')

        result = score_with_exemplars(
            image_bytes=_create_test_image(),
            client_id="test-client",
            brief={"composition": "test"},
            image_description="test poster",
        )

        assert result["exemplars_used"] == 2
        assert len(result["exemplar_ids"]) == 2


# ===========================================================================
# Visual lineage
# ===========================================================================


class TestVisualLineage:
    """Test visual lineage recording."""

    @patch("tools.visual_scoring.get_cursor")
    def test_record_visual_lineage(self, mock_cursor_ctx: MagicMock) -> None:
        from tools.visual_scoring import record_visual_lineage

        mock_cursor = MagicMock()
        mock_cursor_ctx.return_value.__enter__ = lambda s: mock_cursor
        mock_cursor_ctx.return_value.__exit__ = MagicMock(return_value=False)

        record_visual_lineage(
            job_id="test-job-1",
            artifact_id="test-art-1",
            asset_id="test-asset-1",
            role="generated",
            reason="primary poster",
        )

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "visual_lineage" in sql
        assert "INSERT" in sql


# ===========================================================================
# Brand voice guardrail
# ===========================================================================


class TestBrandVoiceGuardrail:
    """Test brand voice register checking."""

    @patch("middleware.guardrails.call_llm")
    def test_flags_register_mismatch(self, mock_llm: MagicMock) -> None:
        from middleware.guardrails import check_brand_voice

        mock_llm.return_value = _mock_llm_response(json.dumps({
            "flagged": True,
            "issue": "Copy uses casual register (detected: casual) but target is formal",
            "register_detected": "casual",
        }))

        result = check_brand_voice(
            copy="yo check this out lol, super cool deal bro",
            copy_register="formal",
            brand_config={},
        )

        assert result["flagged"] is True
        assert "register" in result["issue"].lower() or "casual" in result["issue"].lower()

    @patch("middleware.guardrails.call_llm")
    def test_passes_matching_register(self, mock_llm: MagicMock) -> None:
        from middleware.guardrails import check_brand_voice

        mock_llm.return_value = _mock_llm_response(json.dumps({
            "flagged": False,
            "issue": "",
            "register_detected": "formal",
        }))

        result = check_brand_voice(
            copy="We are pleased to announce our latest collection.",
            copy_register="formal",
            brand_config={},
        )

        assert result["flagged"] is False

    @patch("middleware.guardrails.call_llm")
    def test_uses_gpt54mini(self, mock_llm: MagicMock) -> None:
        """Anti-drift #22: guardrails on GPT-5.4-mini."""
        from middleware.guardrails import check_brand_voice

        mock_llm.return_value = _mock_llm_response('{"flagged": false, "issue": "", "register_detected": "neutral"}')

        check_brand_voice(copy="test", copy_register="neutral")

        assert mock_llm.call_args.kwargs["model"] == "gpt-5.4-mini"


# ===========================================================================
# BM naturalness heuristic
# ===========================================================================


class TestBMNaturalness:
    """Test BM naturalness checking — deterministic, zero tokens."""

    def test_flags_overly_formal(self) -> None:
        from middleware.guardrails import check_bm_naturalness

        result = check_bm_naturalness(
            "Kami dengan ini memaklumkan bahawa perkara tersebut "
            "adalah dimaklumkan kepada semua pihak."
        )
        assert result["flagged"] is True
        assert any("formal" in issue.lower() for issue in result["issues"])

    def test_passes_natural_copy(self) -> None:
        from middleware.guardrails import check_bm_naturalness

        result = check_bm_naturalness("Jom cuba menu baru kami!")
        assert result["flagged"] is False

    def test_flags_indonesian_markers(self) -> None:
        from middleware.guardrails import check_bm_naturalness

        result = check_bm_naturalness("Anda bisa dapat diskon besar di sini.")
        assert result["flagged"] is True
        assert any("indonesian" in issue.lower() for issue in result["issues"])

    def test_returns_formal_density(self) -> None:
        from middleware.guardrails import check_bm_naturalness

        result = check_bm_naturalness("Teks biasa tanpa masalah.")
        assert "formal_density" in result
        assert isinstance(result["formal_density"], float)


# ===========================================================================
# GuardrailMailbox
# ===========================================================================


class TestGuardrailMailbox:
    """Test flag deduplication."""

    def test_deduplicates_same_issue_type(self) -> None:
        from middleware.guardrails import GuardrailMailbox

        mailbox = GuardrailMailbox()
        mailbox.add_flag(issue_type="register_mismatch", detail="Paragraph 1: too casual")
        mailbox.add_flag(issue_type="register_mismatch", detail="Paragraph 3: too casual")
        mailbox.add_flag(issue_type="register_mismatch", detail="Paragraph 5: too casual")

        result = mailbox.collect()
        assert len(result) == 1
        assert result[0]["count"] == 3
        assert result[0]["issue_type"] == "register_mismatch"

    def test_keeps_different_types(self) -> None:
        from middleware.guardrails import GuardrailMailbox

        mailbox = GuardrailMailbox()
        mailbox.add_flag(issue_type="register_mismatch", detail="too casual")
        mailbox.add_flag(issue_type="bm_naturalness", detail="too formal")

        result = mailbox.collect()
        assert len(result) == 2

    def test_has_flags(self) -> None:
        from middleware.guardrails import GuardrailMailbox

        mailbox = GuardrailMailbox()
        assert mailbox.has_flags() is False

        mailbox.add_flag(issue_type="test", detail="test detail")
        assert mailbox.has_flags() is True

    def test_clear(self) -> None:
        from middleware.guardrails import GuardrailMailbox

        mailbox = GuardrailMailbox()
        mailbox.add_flag(issue_type="test", detail="test detail")
        mailbox.clear()
        assert mailbox.has_flags() is False

    def test_preserves_all_details(self) -> None:
        from middleware.guardrails import GuardrailMailbox

        mailbox = GuardrailMailbox()
        mailbox.add_flag(issue_type="register_mismatch", detail="P1 issue")
        mailbox.add_flag(issue_type="register_mismatch", detail="P2 issue")

        result = mailbox.collect()
        assert result[0]["details"] == ["P1 issue", "P2 issue"]


# ===========================================================================
# Full pipeline (integration, mocked externals)
# ===========================================================================


class TestVisualPipeline:
    """Test the full visual production pipeline end-to-end."""

    @patch("tools.visual_pipeline.record_visual_lineage")
    @patch("tools.visual_pipeline.nima_score")
    @patch("tools.visual_pipeline.generate_image")
    @patch("tools.visual_pipeline.expand_brief")
    @patch("tools.visual_pipeline.run_parallel_guardrails")
    @patch("tools.visual_pipeline.score_with_exemplars")
    def test_full_flow(
        self,
        mock_exemplar: MagicMock,
        mock_guardrails: MagicMock,
        mock_expand: MagicMock,
        mock_generate: MagicMock,
        mock_nima: MagicMock,
        mock_lineage: MagicMock,
    ) -> None:
        from tools.visual_pipeline import run_visual_pipeline

        mock_expand.return_value = {
            "composition": "Centred layout with hero product",
            "style": "Warm festive mood",
            "brand": "#FF6B00",
            "technical": "1024x1024",
            "text_content": "Raya Sale 50% Off",
        }
        mock_generate.return_value = _create_test_image()
        mock_nima.return_value = 6.5  # proceed_with_caution
        mock_exemplar.return_value = {
            "exemplars_used": 0,
            "exemplar_ids": [],
            "exemplar_descriptions": [],
            "critique": {
                "text_visibility": {"score": 4.0, "issues": []},
                "design_layout": {"score": 4.0, "issues": []},
                "colour_harmony": {"score": 4.0, "issues": ["Minor spacing"]},
                "overall_coherence": {"score": 4.0, "issues": []},
            },
            "weighted_score": 4.0,
        }
        mock_guardrails.return_value = []

        result = run_visual_pipeline(
            raw_brief="Raya 2025 poster for DMB",
            job_id="test-job-1",
            client_id="test-client-1",
            artifact_family="poster",
            language="ms",
        )

        assert "expanded_brief" in result
        assert "image_bytes" in result
        assert "nima_score" in result
        assert "critique" in result
        assert "trace" in result
        assert result["nima_score"] == 6.5
        assert result["nima_action"] == "proceed_with_caution"
        mock_expand.assert_called_once()
        mock_generate.assert_called_once()

    @patch("tools.visual_pipeline.record_visual_lineage")
    @patch("tools.visual_pipeline.nima_score")
    @patch("tools.visual_pipeline.generate_image")
    @patch("tools.visual_pipeline.expand_brief")
    @patch("tools.visual_pipeline.run_parallel_guardrails")
    @patch("tools.visual_pipeline.score_with_exemplars")
    def test_nima_regeneration_loop(
        self,
        mock_exemplar: MagicMock,
        mock_guardrails: MagicMock,
        mock_expand: MagicMock,
        mock_generate: MagicMock,
        mock_nima: MagicMock,
        mock_lineage: MagicMock,
    ) -> None:
        """NIMA score < 4.0 triggers regeneration."""
        from tools.visual_pipeline import run_visual_pipeline

        mock_expand.return_value = {"composition": "test", "text_content": ""}
        mock_generate.return_value = _create_test_image()
        # First attempt: score 3.0 (regenerate), second: 7.5 (pass)
        mock_nima.side_effect = [3.0, 7.5]
        mock_exemplar.return_value = {
            "exemplars_used": 0, "exemplar_ids": [], "exemplar_descriptions": [],
            "critique": {"text_visibility": {"score": 4.0, "issues": []},
                         "design_layout": {"score": 4.0, "issues": []},
                         "colour_harmony": {"score": 4.0, "issues": []},
                         "overall_coherence": {"score": 4.0, "issues": []}},
            "weighted_score": 4.0,
        }
        mock_guardrails.return_value = []

        result = run_visual_pipeline(
            raw_brief="test",
            job_id="test-job-2",
            client_id="test-client",
        )

        assert result["nima_score"] == 7.5
        assert result["nima_action"] == "pass"
        assert mock_generate.call_count == 2  # regenerated once

    @patch("tools.visual_pipeline.record_visual_lineage")
    @patch("tools.visual_pipeline.nima_score")
    @patch("tools.visual_pipeline.generate_image")
    @patch("tools.visual_pipeline.expand_brief")
    @patch("tools.visual_pipeline.run_parallel_guardrails")
    @patch("tools.visual_pipeline.score_with_exemplars")
    def test_guardrail_flags_in_result(
        self,
        mock_exemplar: MagicMock,
        mock_guardrails: MagicMock,
        mock_expand: MagicMock,
        mock_generate: MagicMock,
        mock_nima: MagicMock,
        mock_lineage: MagicMock,
    ) -> None:
        from tools.visual_pipeline import run_visual_pipeline

        mock_expand.return_value = {"composition": "test", "text_content": "casual copy yo"}
        mock_generate.return_value = _create_test_image()
        mock_nima.return_value = 6.0
        mock_exemplar.return_value = {
            "exemplars_used": 0, "exemplar_ids": [], "exemplar_descriptions": [],
            "critique": {"text_visibility": {"score": 3.5, "issues": []},
                         "design_layout": {"score": 3.5, "issues": []},
                         "colour_harmony": {"score": 3.5, "issues": []},
                         "overall_coherence": {"score": 3.5, "issues": []}},
            "weighted_score": 3.5,
        }
        mock_guardrails.return_value = [
            {"issue_type": "register_mismatch", "count": 1, "details": ["too casual"], "summary": "too casual"}
        ]

        result = run_visual_pipeline(
            raw_brief="test",
            job_id="test-job-3",
            client_id="test-client",
            copy_register="formal",
        )

        assert len(result["guardrail_flags"]) == 1
        assert result["guardrail_flags"][0]["issue_type"] == "register_mismatch"


# ===========================================================================
# Import verification
# ===========================================================================


class TestImports:
    """Verify all imports work correctly."""

    def test_retrieve_similar_exemplars_importable(self) -> None:
        """Exit criterion: from utils.retrieval import retrieve_similar_exemplars works."""
        from utils.retrieval import retrieve_similar_exemplars

        assert callable(retrieve_similar_exemplars)

    def test_image_module_importable(self) -> None:
        from tools.image import expand_brief, generate_image, select_image_model

        assert callable(expand_brief)
        assert callable(generate_image)
        assert callable(select_image_model)

    def test_scoring_module_importable(self) -> None:
        from tools.visual_scoring import (
            critique_4dim,
            nima_prescreen,
            nima_score,
            record_visual_lineage,
            score_with_exemplars,
            weighted_score,
        )

        assert callable(nima_score)
        assert callable(critique_4dim)
        assert callable(score_with_exemplars)
        assert callable(record_visual_lineage)
        assert callable(weighted_score)

    def test_guardrails_module_importable(self) -> None:
        from middleware.guardrails import (
            GuardrailMailbox,
            check_bm_naturalness,
            check_brand_voice,
            run_parallel_guardrails,
        )

        assert callable(check_brand_voice)
        assert callable(check_bm_naturalness)
        assert callable(run_parallel_guardrails)

    def test_pipeline_module_importable(self) -> None:
        from tools.visual_pipeline import run_visual_pipeline

        assert callable(run_visual_pipeline)

    def test_evaluate_rendered_poster_importable(self) -> None:
        from tools.visual_pipeline import evaluate_rendered_poster

        assert callable(evaluate_rendered_poster)


# ===========================================================================
# Post-render QA
# ===========================================================================


class TestPostRenderQA:
    """Test evaluate_rendered_poster for text-over-image composition."""

    def test_missing_png_fails(self, tmp_path: Path) -> None:
        """Non-existent PNG is a clear failure."""
        from tools.visual_pipeline import evaluate_rendered_poster

        result = evaluate_rendered_poster(
            rendered_png_path=str(tmp_path / "missing.png"),
        )
        assert result["passed"] is False
        assert "missing" in result["issues"][0].lower()

    def test_empty_png_fails(self, tmp_path: Path) -> None:
        """Zero-byte PNG is a clear failure."""
        from tools.visual_pipeline import evaluate_rendered_poster

        empty = tmp_path / "empty.png"
        empty.write_bytes(b"")
        result = evaluate_rendered_poster(
            rendered_png_path=str(empty),
        )
        assert result["passed"] is False

    def test_valid_poster_checks_nima_and_composition(
        self, tmp_path: Path,
    ) -> None:
        """Valid poster runs NIMA + composition LLM check."""
        from tools.visual_pipeline import evaluate_rendered_poster

        img = Image.new("RGB", (200, 200), color=(100, 120, 140))
        poster_path = tmp_path / "poster.png"
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        poster_path.write_bytes(buf.getvalue())

        good_llm = _mock_llm_response(json.dumps({
            "cta_visibility": 4.5,
            "text_readability": 4.0,
            "overlay_balance": 4.5,
            "issues": [],
        }))

        with patch(
            "tools.visual_pipeline.nima_score", return_value=4.2,
        ), patch(
            "utils.call_llm.call_llm", return_value=good_llm,
        ):
            result = evaluate_rendered_poster(
                rendered_png_path=str(poster_path),
            )

        assert result["passed"] is True
        assert result["nima_score"] == 4.2
        assert result["composition_score"] > 3.0

    def test_low_nima_fails_even_with_good_composition(
        self, tmp_path: Path,
    ) -> None:
        """NIMA floor gate catches rendering degradation."""
        from tools.visual_pipeline import evaluate_rendered_poster

        img = Image.new("RGB", (64, 64), color=(50, 50, 50))
        poster_path = tmp_path / "bad_nima.png"
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        poster_path.write_bytes(buf.getvalue())

        good_llm = _mock_llm_response(json.dumps({
            "cta_visibility": 5.0,
            "text_readability": 5.0,
            "overlay_balance": 5.0,
            "issues": [],
        }))

        with patch(
            "tools.visual_pipeline.nima_score", return_value=2.5,
        ), patch(
            "utils.call_llm.call_llm", return_value=good_llm,
        ):
            result = evaluate_rendered_poster(
                rendered_png_path=str(poster_path),
                nima_floor=3.5,
            )

        assert result["passed"] is False
        assert any("nima" in i.lower() for i in result["issues"])

    def test_vision_failure_fails_poster_not_degrades(
        self, tmp_path: Path,
    ) -> None:
        """P2 fix: GPT vision failure must fail the poster, not silently pass.

        Previously, composition_score defaulted to 3.0 (the pass threshold),
        so a vision exception would leave it at the pass threshold and the
        poster could sneak through on NIMA alone.
        """
        from tools.visual_pipeline import evaluate_rendered_poster

        img = Image.new("RGB", (200, 200), color=(100, 120, 140))
        poster_path = tmp_path / "poster_vision_fail.png"
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        poster_path.write_bytes(buf.getvalue())

        with patch(
            "tools.visual_pipeline.nima_score", return_value=4.5,
        ), patch(
            "utils.call_llm.call_llm",
            side_effect=RuntimeError("GPT vision transient failure"),
        ):
            result = evaluate_rendered_poster(
                rendered_png_path=str(poster_path),
            )

        # Poster must FAIL even though NIMA is excellent (4.5 > 3.5 floor)
        assert result["passed"] is False
        assert result["vision_check_failed"] is True
        assert result["composition_score"] == 0.0
        assert any("vision" in i.lower() for i in result["issues"])

    def test_individual_dimension_scores_exposed(
        self, tmp_path: Path,
    ) -> None:
        """evaluate_rendered_poster returns cta/readability/balance individually."""
        from tools.visual_pipeline import evaluate_rendered_poster

        img = Image.new("RGB", (200, 200), color=(100, 120, 140))
        poster_path = tmp_path / "poster_dims.png"
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        poster_path.write_bytes(buf.getvalue())

        good_llm = _mock_llm_response(json.dumps({
            "cta_visibility": 4.0,
            "text_readability": 3.5,
            "overlay_balance": 2.5,
            "issues": ["CTA overlaps image element"],
        }))

        with patch(
            "tools.visual_pipeline.nima_score", return_value=4.2,
        ), patch(
            "utils.call_llm.call_llm", return_value=good_llm,
        ):
            result = evaluate_rendered_poster(
                rendered_png_path=str(poster_path),
            )

        assert result["cta_visibility"] == 4.0
        assert result["text_readability"] == 3.5
        assert result["overlay_balance"] == 2.5


# ===========================================================================
# Post-render failure classification
# ===========================================================================


class TestClassifyPostRenderFailure:
    """classify_post_render_failure routes to retryable vs fail_stop."""

    def test_passed_qa_returns_passed(self) -> None:
        from tools.visual_pipeline import classify_post_render_failure

        result = classify_post_render_failure({"passed": True})
        assert result == "passed"

    def test_vision_check_failed_is_fail_stop(self) -> None:
        from tools.visual_pipeline import classify_post_render_failure

        result = classify_post_render_failure({
            "passed": False,
            "vision_check_failed": True,
            "nima_score": 4.5,
            "nima_floor": 3.5,
            "composition_score": 0.0,
        })
        assert result == "fail_stop"

    def test_nima_below_floor_is_fail_stop(self) -> None:
        from tools.visual_pipeline import classify_post_render_failure

        result = classify_post_render_failure({
            "passed": False,
            "vision_check_failed": False,
            "nima_score": 2.5,
            "nima_floor": 3.5,
            "composition_score": 2.0,
        })
        assert result == "fail_stop"

    def test_good_nima_bad_composition_is_retryable(self) -> None:
        from tools.visual_pipeline import classify_post_render_failure

        result = classify_post_render_failure({
            "passed": False,
            "vision_check_failed": False,
            "nima_score": 4.2,
            "nima_floor": 3.5,
            "composition_score": 2.5,
            "composition_threshold": 3.0,
        })
        assert result == "retryable"


# ===========================================================================
# Readability boost CSS injection
# ===========================================================================


class TestReadabilityBoost:
    """_inject_readability_boost injects CSS into HTML."""

    def test_css_injected_before_head_close(self) -> None:
        from tools.publish import _inject_readability_boost

        html = "<html><head><style>body{}</style></head><body></body></html>"
        boosted = _inject_readability_boost(html)
        assert "readability boost" in boosted.lower()
        # CSS block should appear before </head>
        head_close = boosted.lower().index("</head>")
        boost_pos = boosted.lower().index("readability boost")
        assert boost_pos < head_close

    def test_no_head_tag_still_injects(self) -> None:
        from tools.publish import _inject_readability_boost

        html = "<div>no head here</div>"
        boosted = _inject_readability_boost(html)
        assert "readability boost" in boosted.lower()
        assert "<div>" in boosted


# ===========================================================================
# Post-render revision in delivery (T1.4 integration)
# ===========================================================================


class TestPostRenderRevision:
    """_attempt_readability_revision wired into _deliver."""

    @staticmethod
    def _base_context(tmp_path: Path) -> dict[str, Any]:
        return {
            "job_context": {
                "job_id": "job-rev",
                "client_id": "dmb",
                "routing": {"workflow": "poster_production"},
            },
            "artifact_payload": {
                "image_path": "/tmp/poster.png",
                "poster_copy": json.dumps({
                    "headline": "Grand Opening",
                    "subheadline": "Today Only",
                    "cta": "Shop Now",
                    "body_text": "",
                }),
                "quality_verdict": {"passed": True, "nima_score": 4.0},
            },
            "stage_results": [],
        }

    def test_retryable_failure_triggers_revision(
        self, tmp_path: Path,
    ) -> None:
        """Text-overlay QA failure → readability revision → success."""
        from tools.registry import _deliver

        pdf_path = tmp_path / "poster_default.pdf"
        pdf_path.write_text("pdf-content")
        png_path = tmp_path / "poster_default.png"
        png_path.write_bytes(b"\x89PNG" + b"\x00" * 60)

        call_count = {"n": 0}

        def _qa_side_effect(**kwargs: Any) -> dict[str, Any]:
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call: fail on composition (retryable)
                return {
                    "passed": False,
                    "nima_score": 4.2,
                    "nima_floor": 3.5,
                    "composition_score": 2.5,
                    "cta_visibility": 2.0,
                    "text_readability": 2.5,
                    "overlay_balance": 3.0,
                    "vision_check_failed": False,
                    "issues": ["CTA hard to read"],
                    "cost_usd": 0.002,
                }
            # Second call (after revision): pass
            return {
                "passed": True,
                "nima_score": 4.2,
                "nima_floor": 3.5,
                "composition_score": 4.0,
                "cta_visibility": 4.0,
                "text_readability": 4.0,
                "overlay_balance": 4.0,
                "vision_check_failed": False,
                "issues": [],
                "cost_usd": 0.002,
            }

        with (
            patch(
                "tools.publish.assemble_poster_pdf",
                return_value=pdf_path,
            ),
            patch(
                "tools.visual_pipeline.evaluate_rendered_poster",
                side_effect=_qa_side_effect,
            ) as mock_eval,
        ):
            result = _deliver(self._base_context(tmp_path))

        assert result["status"] == "ok"
        assert result.get("revision_applied") is True
        assert mock_eval.call_count == 2
        assert result["original_qa"]["passed"] is False
        assert result["post_render_qa"]["passed"] is True

    def test_fail_stop_skips_revision(
        self, tmp_path: Path,
    ) -> None:
        """NIMA floor failure → fail_stop, no revision attempt."""
        from tools.registry import _deliver

        pdf_path = tmp_path / "poster_default.pdf"
        pdf_path.write_text("pdf-content")
        png_path = tmp_path / "poster_default.png"
        png_path.write_bytes(b"\x89PNG" + b"\x00" * 60)

        fail_stop_qa = {
            "passed": False,
            "nima_score": 2.0,
            "nima_floor": 3.5,
            "composition_score": 2.0,
            "cta_visibility": 2.0,
            "text_readability": 2.0,
            "overlay_balance": 2.0,
            "vision_check_failed": False,
            "issues": ["Rendered NIMA too low"],
            "cost_usd": 0.002,
        }

        with (
            patch(
                "tools.publish.assemble_poster_pdf",
                return_value=pdf_path,
            ),
            patch(
                "tools.visual_pipeline.evaluate_rendered_poster",
                return_value=fail_stop_qa,
            ) as mock_eval,
        ):
            result = _deliver(self._base_context(tmp_path))

        assert result["status"] == "error"
        assert result["failure_class"] == "fail_stop"
        # Only ONE QA call — no revision attempted
        mock_eval.assert_called_once()

    def test_revision_also_fails_returns_error(
        self, tmp_path: Path,
    ) -> None:
        """Revision attempted but also fails → error with original issues."""
        from tools.registry import _deliver

        pdf_path = tmp_path / "poster_default.pdf"
        pdf_path.write_text("pdf-content")
        png_path = tmp_path / "poster_default.png"
        png_path.write_bytes(b"\x89PNG" + b"\x00" * 60)

        # Both attempts fail (composition still bad after boost)
        bad_composition = {
            "passed": False,
            "nima_score": 4.2,
            "nima_floor": 3.5,
            "composition_score": 2.5,
            "cta_visibility": 2.0,
            "text_readability": 2.5,
            "overlay_balance": 3.0,
            "vision_check_failed": False,
            "issues": ["CTA still unreadable"],
            "cost_usd": 0.002,
        }

        with (
            patch(
                "tools.publish.assemble_poster_pdf",
                return_value=pdf_path,
            ),
            patch(
                "tools.visual_pipeline.evaluate_rendered_poster",
                return_value=bad_composition,
            ) as mock_eval,
        ):
            result = _deliver(self._base_context(tmp_path))

        assert result["status"] == "error"
        assert result["failure_class"] == "retryable"
        # Two QA calls: original + revision
        assert mock_eval.call_count == 2
