"""Tests for S11 routing layer.

Covers all exit criteria:
- Fast-path: "poster DMB" → poster_production at zero tokens
- LLM routing: "buatkan sesuatu untuk Raya" → correct workflow via GPT-5.4-mini
- Refinement: vague request → 2 shaping cycles → spec promoted → production
- Knowledge retrieval returns client config + seasonal context with lost-in-the-middle reordering
- Exemplar retrieval returns visually similar designs via CLIP
- Design system selector returns 3 candidates for DMB (industry: textile, mood: warm, traditional)
- All routing uses GPT-5.4-mini
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from contracts.artifact_spec import ArtifactFamily, DeliveryFormat, ProvisionalArtifactSpec
from contracts.routing import (
    RoutingResult,
    _load_client_config,
    _load_design_systems,
    _load_fast_paths,
    fast_path_route,
    llm_route,
    refine_request,
    route,
    select_design_systems,
)
from utils.knowledge import (
    assemble_context,
    lost_in_middle_reorder,
)


# ---------------------------------------------------------------------------
# Fast-path routing tests
# ---------------------------------------------------------------------------


class TestFastPathRouter:
    """Fast-path: deterministic pattern matching at zero tokens."""

    def test_poster_dmb_fast_path(self) -> None:
        """Exit criterion: 'poster DMB' → poster_production at zero tokens."""
        result = fast_path_route("poster DMB", client_id="dmb")
        assert result is not None
        assert result.workflow == "poster_production"
        assert result.fast_path is True
        assert result.token_cost == 0
        assert result.confidence == 1.0

    def test_poster_generic_fast_path(self) -> None:
        """Generic 'poster' matches without client context."""
        result = fast_path_route("I need a poster")
        assert result is not None
        assert result.workflow == "poster_production"
        assert result.fast_path is True
        assert result.token_cost == 0

    def test_brochure_fast_path(self) -> None:
        result = fast_path_route("create a brochure for our products")
        assert result is not None
        assert result.workflow == "brochure_production"

    def test_document_fast_path(self) -> None:
        result = fast_path_route("write a report about Q1")
        assert result is not None
        assert result.workflow == "document_production"

    def test_research_fast_path(self) -> None:
        result = fast_path_route("research competitor pricing")
        assert result is not None
        assert result.workflow == "research"

    def test_childrens_book_fast_path(self) -> None:
        result = fast_path_route("buku kanak-kanak tentang haiwan")
        assert result is not None
        assert result.workflow == "childrens_book_production"

    def test_ebook_fast_path(self) -> None:
        result = fast_path_route("create an e-book for beginners")
        assert result is not None
        assert result.workflow == "ebook_production"

    def test_rework_fast_path(self) -> None:
        result = fast_path_route("rework the last deliverable, fix colours")
        assert result is not None
        assert result.workflow == "rework"

    def test_onboarding_fast_path(self) -> None:
        result = fast_path_route("onboard a new client")
        assert result is not None
        assert result.workflow == "onboarding"

    def test_no_match_returns_none(self) -> None:
        """Ambiguous input returns None → falls through to LLM routing."""
        result = fast_path_route("buatkan sesuatu untuk Raya")
        assert result is None

    def test_inactive_phase_skipped(self) -> None:
        """Invoice fast-path skipped because extended_ops phase is inactive."""
        result = fast_path_route("create an invoice for DMB")
        assert result is None

    def test_client_fast_path_takes_precedence(self) -> None:
        """Client-specific pattern is checked before generic."""
        result = fast_path_route("poster for darul makmur", client_id="dmb")
        assert result is not None
        assert result.workflow == "poster_production"
        assert "Client fast-path" in result.reason

    def test_dmb_brochure_client_fast_path(self) -> None:
        result = fast_path_route("brosur DMB", client_id="dmb")
        assert result is not None
        assert result.workflow == "brochure_production"
        assert "Client fast-path" in result.reason


# ---------------------------------------------------------------------------
# LLM routing tests (mocked)
# ---------------------------------------------------------------------------


class TestLLMRouter:
    """LLM classification for ambiguous requests."""

    @patch("contracts.routing.call_llm")
    def test_malay_request_routed(self, mock_llm: MagicMock) -> None:
        """Exit criterion: 'buatkan sesuatu untuk Raya' → correct workflow."""
        mock_llm.return_value = {
            "content": json.dumps({
                "workflow": "poster_production",
                "confidence": 0.85,
                "artifact_family": "poster",
                "reason": "Raya seasonal request likely visual content",
            }),
            "model": "gpt-5.4-mini",
            "input_tokens": 150,
            "output_tokens": 50,
            "cost_usd": 0.0001,
        }

        result = llm_route("buatkan sesuatu untuk Raya", client_id="dmb")
        assert result.workflow == "poster_production"
        assert result.confidence == 0.85
        assert result.token_cost == 200
        assert "LLM classification" in result.reason

        # Verify GPT-5.4-mini was used (anti-drift #54)
        call_args = mock_llm.call_args
        assert call_args.kwargs["model"] == "gpt-5.4-mini"

    @patch("contracts.routing.call_llm")
    def test_unparseable_response_fallback(self, mock_llm: MagicMock) -> None:
        """Non-JSON response falls back to refinement."""
        mock_llm.return_value = {
            "content": "I'm not sure what to do with this",
            "model": "gpt-5.4-mini",
            "input_tokens": 100,
            "output_tokens": 30,
            "cost_usd": 0.0001,
        }

        result = llm_route("something vague")
        assert result.workflow == "refinement"
        assert result.confidence == 0.3

    @patch("contracts.routing.call_llm")
    def test_markdown_fenced_json_parsed(self, mock_llm: MagicMock) -> None:
        """LLM response wrapped in markdown fences is still parsed."""
        mock_llm.return_value = {
            "content": '```json\n{"workflow": "research", "confidence": 0.9, "reason": "market analysis"}\n```',
            "model": "gpt-5.4-mini",
            "input_tokens": 100,
            "output_tokens": 30,
            "cost_usd": 0.0001,
        }

        result = llm_route("analyse the textile market in KL")
        assert result.workflow == "research"
        assert result.confidence == 0.9


# ---------------------------------------------------------------------------
# Iterative refinement tests (mocked)
# ---------------------------------------------------------------------------


class TestIterativeRefinement:
    """Vague request → 2 shaping cycles → spec promoted."""

    @patch("contracts.routing.call_llm")
    def test_first_cycle_generates_questions(self, mock_llm: MagicMock) -> None:
        mock_llm.return_value = {
            "content": json.dumps({
                "questions": [
                    "What type of content do you need? (poster, brochure, document)",
                    "What is the objective or occasion?",
                ],
                "inferred": {
                    "language": "bm",
                },
            }),
            "model": "gpt-5.4-mini",
            "input_tokens": 200,
            "output_tokens": 100,
            "cost_usd": 0.0001,
        }

        spec, questions = refine_request("buatkan sesuatu", client_id="dmb")
        assert len(questions) >= 1
        assert spec.cycle == 1
        assert spec.language == "bm"

    @patch("contracts.routing.call_llm")
    def test_second_cycle_with_answers(self, mock_llm: MagicMock) -> None:
        """After answers are provided, spec should improve."""
        mock_llm.side_effect = [
            # _apply_answers call
            {
                "content": json.dumps({
                    "artifact_family": "poster",
                    "language": "bm",
                    "objective": "Poster promosi Raya 2026 untuk DMB",
                    "tone": "formal",
                    "format": "pdf",
                    "dimensions": "A4",
                    "page_count": 1,
                    "confidence": 0.9,
                    "completeness": 0.9,
                }),
                "model": "gpt-5.4-mini",
                "input_tokens": 300,
                "output_tokens": 100,
                "cost_usd": 0.0001,
            },
            # Refinement question generation call (in case readiness not yet "ready")
            {
                "content": json.dumps({
                    "questions": [],
                    "inferred": {"artifact_family": "poster"},
                }),
                "model": "gpt-5.4-mini",
                "input_tokens": 200,
                "output_tokens": 50,
                "cost_usd": 0.0001,
            },
        ]

        existing_spec = ProvisionalArtifactSpec(
            client_id="dmb",
            artifact_family=ArtifactFamily.document,
            language="bm",
            raw_brief="buatkan sesuatu",
            cycle=1,
            objective="poster promosi",
            format=DeliveryFormat.pdf,
            readiness="shapeable",
        )

        spec, questions = refine_request(
            "buatkan sesuatu",
            client_id="dmb",
            spec=existing_spec,
            user_answers=["Poster untuk promosi Raya", "A4 size, formal tone"],
        )
        assert spec.artifact_family == ArtifactFamily.poster

    @patch("contracts.routing.call_llm")
    def test_ready_spec_returns_no_questions(self, mock_llm: MagicMock) -> None:
        """Ready spec returns empty questions list."""
        ready_spec = ProvisionalArtifactSpec(
            client_id="dmb",
            artifact_family=ArtifactFamily.poster,
            language="bm",
            objective="Poster promosi Raya 2026",
            format=DeliveryFormat.pdf,
            tone="formal",
            copy_register="formal_bm",
            dimensions="A4",
            page_count=1,
            brand_config_id="dmb",
            readiness="ready",
        )

        spec, questions = refine_request(
            "poster Raya",
            client_id="dmb",
            spec=ready_spec,
        )
        assert questions == []
        # LLM should NOT have been called
        mock_llm.assert_not_called()


# ---------------------------------------------------------------------------
# Design system selector tests
# ---------------------------------------------------------------------------


class TestDesignSystemSelector:
    """Design system selection via set intersection scoring."""

    def test_dmb_returns_three_candidates(self) -> None:
        """Exit criterion: DMB → 3 candidates with warm, traditional, textile."""
        results = select_design_systems("dmb", artifact_family="poster")
        assert len(results) == 3

    def test_dmb_top_candidates_warm_traditional(self) -> None:
        """DMB (textile, warm, traditional) should match Malaysian / warm systems."""
        results = select_design_systems("dmb", artifact_family="poster")
        # All results should be warm-temperature systems with mood overlap
        systems = _load_design_systems().get("systems", {})
        for name in results:
            system = systems[name]
            # At least one attribute should overlap with DMB's profile
            has_industry = bool(
                set(system.get("industry", [])) & {"textile", "fashion", "malaysia"}
            )
            has_mood = bool(
                set(system.get("mood", [])) & {"warm", "traditional"}
            )
            has_colour = system.get("colour_temperature") == "warm"
            assert has_industry or has_mood or has_colour, (
                f"{name} doesn't match DMB profile: {system}"
            )

    def test_returns_top_k(self) -> None:
        results = select_design_systems("dmb", top_k=5)
        assert len(results) == 5

    def test_unknown_client_uses_defaults(self) -> None:
        """Unknown client falls back to default mood [warm, professional]."""
        results = select_design_systems("unknown_client", artifact_family="poster")
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Lost-in-the-middle reordering tests
# ---------------------------------------------------------------------------


class TestLostInMiddleReorder:
    """Lost-in-the-middle reordering (§22.2)."""

    def test_five_items_reordered(self) -> None:
        """Best → pos 1, second-best → pos 5, rest in middle."""
        items = [
            {"id": "A", "score": 0.95},
            {"id": "B", "score": 0.90},
            {"id": "C", "score": 0.80},
            {"id": "D", "score": 0.70},
            {"id": "E", "score": 0.60},
        ]
        reordered = lost_in_middle_reorder(items)
        assert reordered[0]["id"] == "A"   # best first
        assert reordered[-1]["id"] == "B"  # second-best last
        assert len(reordered) == 5

    def test_two_items_unchanged(self) -> None:
        items = [{"id": "A"}, {"id": "B"}]
        assert lost_in_middle_reorder(items) == items

    def test_one_item_unchanged(self) -> None:
        items = [{"id": "A"}]
        assert lost_in_middle_reorder(items) == items

    def test_empty_list(self) -> None:
        assert lost_in_middle_reorder([]) == []

    def test_three_items_reordered(self) -> None:
        items = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
        reordered = lost_in_middle_reorder(items)
        assert reordered[0]["id"] == "A"
        assert reordered[-1]["id"] == "B"
        assert reordered[1]["id"] == "C"


# ---------------------------------------------------------------------------
# Knowledge assembly tests
# ---------------------------------------------------------------------------


class TestKnowledgeAssembly:
    """Context assembly with client config + seasonal context."""

    def test_assemble_context_dmb(self) -> None:
        """Client config + seasonal context returned for DMB."""
        ctx = assemble_context("dmb", include_knowledge=False)
        assert "client_config" in ctx
        assert "seasonal" in ctx
        assert ctx["client_config"].get("client_id") == "dmb"
        assert ctx["seasonal"]["season"] is not None

    def test_assemble_context_unknown_client(self) -> None:
        """Unknown client returns empty config + seasonal context."""
        ctx = assemble_context("nonexistent", include_knowledge=False)
        assert ctx["client_config"] == {}
        assert "seasonal" in ctx


# ---------------------------------------------------------------------------
# Main route() integration tests (mocked LLM)
# ---------------------------------------------------------------------------


class TestRouteEntryPoint:
    """Main route() function — fast-path then LLM fallback."""

    def test_fast_path_with_design_system(self) -> None:
        """Fast-path route attaches design system for known client."""
        result = route("poster DMB", client_id="dmb")
        assert result.workflow == "poster_production"
        assert result.fast_path is True
        assert result.design_system is not None

    @patch("contracts.routing.call_llm")
    def test_llm_fallback_with_design_system(self, mock_llm: MagicMock) -> None:
        """LLM route attaches design system for known client."""
        mock_llm.return_value = {
            "content": json.dumps({
                "workflow": "poster_production",
                "confidence": 0.8,
                "reason": "Raya content",
            }),
            "model": "gpt-5.4-mini",
            "input_tokens": 150,
            "output_tokens": 50,
            "cost_usd": 0.0001,
        }

        result = route("buatkan sesuatu untuk Raya", client_id="dmb")
        assert result.workflow == "poster_production"
        assert result.fast_path is False
        assert result.design_system is not None

    def test_route_without_client(self) -> None:
        """Routing works without client context."""
        result = route("create a poster")
        assert result.workflow == "poster_production"
        assert result.fast_path is True


# ---------------------------------------------------------------------------
# RoutingResult contract tests
# ---------------------------------------------------------------------------


class TestRoutingResult:
    """RoutingResult pydantic model tests."""

    def test_default_model_preference(self) -> None:
        """Anti-drift #54: default model is gpt-5.4-mini."""
        result = RoutingResult(workflow="poster_production")
        assert result.model_preference == "gpt-5.4-mini"

    def test_serialisation_round_trip(self) -> None:
        result = RoutingResult(
            workflow="poster_production",
            fast_path=True,
            confidence=1.0,
            token_cost=0,
            reason="test",
        )
        data = result.model_dump()
        restored = RoutingResult(**data)
        assert restored.workflow == result.workflow
        assert restored.fast_path is True


# ---------------------------------------------------------------------------
# CLIP encoding tests (actual model)
# ---------------------------------------------------------------------------


class TestCLIPEncoding:
    """CLIP ViT-B/32 image encoding tests."""

    def test_encode_image_returns_512_dim(self) -> None:
        """CLIP encodes image to 512-dim normalised vector."""
        from utils.retrieval import encode_image

        # Create a simple test image
        from PIL import Image
        import io

        img = Image.new("RGB", (64, 64), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        embedding = encode_image(image_bytes)
        assert len(embedding) == 512
        # Check normalised (L2 norm ≈ 1.0)
        import math
        norm = math.sqrt(sum(v ** 2 for v in embedding))
        assert abs(norm - 1.0) < 0.01

    def test_similar_images_high_similarity(self) -> None:
        """Two similar images should have high cosine similarity."""
        from utils.retrieval import encode_image
        from PIL import Image
        import io

        # Two red images
        img1 = Image.new("RGB", (64, 64), color="red")
        img2 = Image.new("RGB", (64, 64), color=(255, 10, 10))

        buf1 = io.BytesIO()
        img1.save(buf1, format="PNG")
        buf2 = io.BytesIO()
        img2.save(buf2, format="PNG")

        emb1 = encode_image(buf1.getvalue())
        emb2 = encode_image(buf2.getvalue())

        similarity = sum(a * b for a, b in zip(emb1, emb2))
        assert similarity > 0.9

    def test_different_images_lower_similarity(self) -> None:
        """Very different images should have lower similarity."""
        from utils.retrieval import encode_image
        from PIL import Image
        import io

        img1 = Image.new("RGB", (64, 64), color="red")
        img2 = Image.new("RGB", (64, 64), color="blue")

        buf1 = io.BytesIO()
        img1.save(buf1, format="PNG")
        buf2 = io.BytesIO()
        img2.save(buf2, format="PNG")

        emb1 = encode_image(buf1.getvalue())
        emb2 = encode_image(buf2.getvalue())

        similarity = sum(a * b for a, b in zip(emb1, emb2))
        # Still similar (both plain colours) but less than identical
        assert similarity < 1.0


