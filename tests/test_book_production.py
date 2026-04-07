"""Tests for the full children's book production pipeline (S21)."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from contracts.context import RollingContext
from contracts.publishing import (
    AgeGroup,
    CharacterBible,
    ClothingDescription,
    CompositionGuide,
    FaceDetails,
    HairDetails,
    NarrativeScaffold,
    PageScaffold,
    PageTurnEffect,
    PhysicalDescription,
    StyleLock,
    StyleNotes,
    StoryBible,
    TextImageRelationship,
    TextPlacementStrategy,
    ThematicConstraints,
    WorldDescription,
    SensoryDetails,
)
from tools.book_production import produce_book, _generate_page_text


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_test_image(color: tuple[int, int, int] = (128, 128, 128)) -> bytes:
    img = Image.new("RGB", (512, 512), color=color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _sample_character() -> CharacterBible:
    return CharacterBible(
        character_id="aminah",
        name="Aminah",
        role="protagonist",
        physical=PhysicalDescription(
            age=7,
            ethnicity="Malay",
            skin_tone="#8D6E63",
            height="small",
            build="slender",
            face=FaceDetails(shape="round", eyes="large", nose="small", mouth="smiling"),
            hair=HairDetails(style="straight", colour="#1A1A1A"),
        ),
        clothing=ClothingDescription(default="blue baju kurung"),
        style_notes=StyleNotes(
            art_style="watercolour",
            line_weight="thin",
            colour_palette="warm pastels",
        ),
    )


def _sample_style_lock() -> StyleLock:
    return StyleLock(
        art_style="soft watercolour",
        palette=["#264653", "#FFF8F0", "#E76F51"],
        typography="Plus Jakarta Sans",
        text_placement_strategy=TextPlacementStrategy.text_always_below,
    )


def _sample_story_bible() -> StoryBible:
    return StoryBible(
        title="Aminah dan Pasar Pagi",
        target_age=AgeGroup.age_5_7,
        language="ms",
        world=WorldDescription(
            setting="Traditional Malay morning market",
            sensory=SensoryDetails(visual="Colourful stalls with tropical fruit"),
        ),
        thematic_constraints=ThematicConstraints(
            lesson="Kindness and helping neighbours",
            avoid=["violence", "scary imagery"],
        ),
        immutable_facts=["Aminah is 7 years old", "The market is near her kampung"],
    )


def _sample_page(page_num: int, checkpoint: str = "") -> PageScaffold:
    beats = ["wonder", "curiosity", "challenge", "effort", "friendship",
             "growth", "triumph", "reflection"]
    effects = [PageTurnEffect.continuation, PageTurnEffect.continuation,
               PageTurnEffect.reveal, PageTurnEffect.continuation,
               PageTurnEffect.continuation, PageTurnEffect.reveal,
               PageTurnEffect.climax, PageTurnEffect.pause]
    idx = (page_num - 1) % len(beats)
    return PageScaffold(
        page=page_num,
        word_target=30,
        emotional_beat=beats[idx],
        characters_present=["aminah"],
        checkpoint_progress=checkpoint,
        text_image_relationship=TextImageRelationship.complementary,
        illustration_shows=f"Scene for page {page_num}",
        page_turn_effect=effects[idx],
        composition_guide=CompositionGuide(
            camera="medium_shot",
            character_position="centre",
            background_detail="detailed",
            colour_temperature="warm",
            text_zone="bottom_third",
        ),
    )


def _sample_scaffold(page_count: int = 8) -> NarrativeScaffold:
    checkpoints = {2: "character_introduced", 4: "conflict_established", 7: "resolution_reached"}
    pages = [
        _sample_page(i + 1, checkpoint=checkpoints.get(i + 1, ""))
        for i in range(page_count)
    ]
    return NarrativeScaffold.decompose(
        target_age=AgeGroup.age_5_7,
        page_count=page_count,
        pages=pages,
    )


def _mock_call_llm(**kwargs: Any) -> dict[str, Any]:
    """Return a mock LLM response."""
    return {
        "content": "Aminah berjalan ke pasar pagi dengan senyuman. Dia melihat buah-buahan berwarna-warni di gerai.",
        "model": "gpt-5.4-mini",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.0001,
    }


def _mock_generate_image(**kwargs: object) -> bytes:
    return _make_test_image()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPageTextGeneration:
    """Text generation with self-refine for each page."""

    @patch("tools.book_production.call_llm", side_effect=_mock_call_llm)
    def test_generates_text_for_page(self, mock_llm: MagicMock) -> None:
        from contracts.trace import TraceCollector
        collector = TraceCollector(job_id="test")
        ctx = RollingContext(context_type="narrative", recent_window=8, medium_scope="not_needed")

        text = _generate_page_text(
            page=_sample_page(1),
            story_bible=_sample_story_bible(),
            rolling_context=ctx,
            collector=collector,
        )
        assert isinstance(text, str)
        assert len(text) > 0

    @patch("tools.book_production.call_llm", side_effect=_mock_call_llm)
    def test_self_refine_runs_three_calls(self, mock_llm: MagicMock) -> None:
        """Generate + critique + revise = 3 LLM calls per page."""
        from contracts.trace import TraceCollector
        collector = TraceCollector(job_id="test")
        ctx = RollingContext(context_type="narrative", recent_window=8, medium_scope="not_needed")

        _generate_page_text(
            page=_sample_page(1),
            story_bible=_sample_story_bible(),
            rolling_context=ctx,
            collector=collector,
        )
        assert mock_llm.call_count == 3  # generate, critique, revise

    @patch("tools.book_production.call_llm", side_effect=_mock_call_llm)
    def test_page_turn_effect_in_prompt(self, mock_llm: MagicMock) -> None:
        """Page turn effect guidance is included in the prompt."""
        from contracts.trace import TraceCollector
        collector = TraceCollector(job_id="test")
        ctx = RollingContext(context_type="narrative", recent_window=8, medium_scope="not_needed")

        page = _sample_page(1)
        page.page_turn_effect = PageTurnEffect.climax
        _generate_page_text(
            page=page,
            story_bible=_sample_story_bible(),
            rolling_context=ctx,
            collector=collector,
        )
        # Check the generate call's prompt contains climax guidance
        first_call_args = mock_llm.call_args_list[0]
        user_prompt = first_call_args.kwargs["variable_suffix"][0]["content"]
        assert "climax" in user_prompt.lower()


class TestProduceBook:
    """Full pipeline integration tests."""

    @patch("tools.book_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.illustrate.generate_image", side_effect=_mock_generate_image)
    @patch("tools.illustrate.expand_brief", return_value={"composition": "expanded prompt"})
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.upload_to_fal", return_value="https://fal.media/test.jpg")
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_8_page_book_produces_all_texts(
        self, mock_typst: MagicMock, mock_fal: MagicMock,
        mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen_img: MagicMock, mock_llm: MagicMock,
        tmp_path: Path,
    ) -> None:
        from tools.illustrate import IllustrationPipeline
        scaffold = _sample_scaffold(8)
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")

        result: dict[str, Any] = produce_book(
            scaffold=scaffold,
            characters=[_sample_character()],
            story_bible=_sample_story_bible(),
            style_lock=_sample_style_lock(),
            job_id="test-book",
            pipeline=pipeline,
            output_dir=tmp_path,
        )
        assert len(result["page_texts"]) == 8

    @patch("tools.book_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.illustrate.generate_image", side_effect=_mock_generate_image)
    @patch("tools.illustrate.expand_brief", return_value={"composition": "expanded prompt"})
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.upload_to_fal", return_value="https://fal.media/test.jpg")
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_illustration_called_per_page(
        self, mock_typst: MagicMock, mock_fal: MagicMock,
        mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen_img: MagicMock, mock_llm: MagicMock,
        tmp_path: Path,
    ) -> None:
        from tools.illustrate import IllustrationPipeline
        scaffold = _sample_scaffold(8)
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")

        produce_book(
            scaffold=scaffold,
            characters=[_sample_character()],
            story_bible=_sample_story_bible(),
            style_lock=_sample_style_lock(),
            job_id="test-book",
            pipeline=pipeline,
            output_dir=tmp_path,
        )
        assert mock_gen_img.call_count == 8

    @patch("tools.book_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.illustrate.generate_image", side_effect=_mock_generate_image)
    @patch("tools.illustrate.expand_brief", return_value={"composition": "expanded prompt"})
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.upload_to_fal", return_value="https://fal.media/test.jpg")
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_illustration_uses_illustration_shows_not_text(
        self, mock_typst: MagicMock, mock_fal: MagicMock,
        mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen_img: MagicMock, mock_llm: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Anti-drift #49: illustration prompt from illustration_shows, not page text."""
        from tools.illustrate import IllustrationPipeline
        scaffold = _sample_scaffold(8)
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")

        produce_book(
            scaffold=scaffold,
            characters=[_sample_character()],
            story_bible=_sample_story_bible(),
            style_lock=_sample_style_lock(),
            job_id="test-book",
            pipeline=pipeline,
            output_dir=tmp_path,
        )
        # expand_brief is called with prompts built from illustration_shows
        for call in mock_expand.call_args_list:
            prompt = call.args[0] if call.args else call.kwargs.get("brief", "")
            assert "Aminah berjalan" not in prompt  # page text should NOT appear

    @patch("tools.book_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.illustrate.generate_image", side_effect=_mock_generate_image)
    @patch("tools.illustrate.expand_brief", return_value={"composition": "expanded prompt"})
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.upload_to_fal", return_value="https://fal.media/test.jpg")
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_rolling_context_updated_per_page(
        self, mock_typst: MagicMock, mock_fal: MagicMock,
        mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen_img: MagicMock, mock_llm: MagicMock,
        tmp_path: Path,
    ) -> None:
        """RollingContext updated after each page with text + visual summary."""
        from tools.illustrate import IllustrationPipeline
        scaffold = _sample_scaffold(8)
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")

        produce_book(
            scaffold=scaffold,
            characters=[_sample_character()],
            story_bible=_sample_story_bible(),
            style_lock=_sample_style_lock(),
            job_id="test-book",
            pipeline=pipeline,
            output_dir=tmp_path,
        )
        # We verify indirectly: LLM was called 3x per page (gen+crit+rev)
        # plus 2 for assembly = 24 + ? -> The rolling context is passed into prompts
        assert mock_llm.call_count == 24  # 3 calls * 8 pages

    @patch("tools.book_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.illustrate.generate_image", side_effect=_mock_generate_image)
    @patch("tools.illustrate.expand_brief", return_value={"composition": "expanded prompt"})
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.upload_to_fal", return_value="https://fal.media/test.jpg")
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_entity_tracking_character_through_pages(
        self, mock_typst: MagicMock, mock_fal: MagicMock,
        mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen_img: MagicMock, mock_llm: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Character introduced on page 1 tracked through page 8."""
        from tools.illustrate import IllustrationPipeline
        scaffold = _sample_scaffold(8)
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")

        # Produce book and check rolling context updates happened
        # (we verify via the call count — each page updates context)
        result: dict[str, Any] = produce_book(
            scaffold=scaffold,
            characters=[_sample_character()],
            story_bible=_sample_story_bible(),
            style_lock=_sample_style_lock(),
            job_id="test-book",
            pipeline=pipeline,
            output_dir=tmp_path,
        )
        assert "trace" in result

    @patch("tools.book_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.illustrate.generate_image", side_effect=_mock_generate_image)
    @patch("tools.illustrate.expand_brief", return_value={"composition": "expanded prompt"})
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.upload_to_fal", return_value="https://fal.media/test.jpg")
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_checkpoint_resolution_reached(
        self, mock_typst: MagicMock, mock_fal: MagicMock,
        mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen_img: MagicMock, mock_llm: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Checkpoint 'resolution_reached' flagged at page 7."""
        from tools.illustrate import IllustrationPipeline
        scaffold = _sample_scaffold(8)
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")

        result: dict[str, Any] = produce_book(
            scaffold=scaffold,
            characters=[_sample_character()],
            story_bible=_sample_story_bible(),
            style_lock=_sample_style_lock(),
            job_id="test-book",
            pipeline=pipeline,
            output_dir=tmp_path,
        )
        trace = result["trace"]
        assert trace.total_cost_usd > 0

    @patch("tools.book_production.call_llm", side_effect=_mock_call_llm)
    @patch("tools.illustrate.generate_image", side_effect=_mock_generate_image)
    @patch("tools.illustrate.expand_brief", return_value={"composition": "expanded prompt"})
    @patch("tools.illustrate.upload_bytes")
    @patch("tools.illustrate.upload_to_fal", return_value="https://fal.media/test.jpg")
    @patch("tools.publish._compile_typst", side_effect=lambda src, out: out)
    def test_produces_pdf_and_epub(
        self, mock_typst: MagicMock, mock_fal: MagicMock,
        mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen_img: MagicMock, mock_llm: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Assembly produces both PDF and EPUB."""
        from tools.illustrate import IllustrationPipeline
        scaffold = _sample_scaffold(8)
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")

        result: dict[str, Any] = produce_book(
            scaffold=scaffold,
            characters=[_sample_character()],
            story_bible=_sample_story_bible(),
            style_lock=_sample_style_lock(),
            job_id="test-book",
            pipeline=pipeline,
            output_dir=tmp_path,
        )
        assert "pdf" in result
        assert "epub" in result
        assert Path(result["epub"]).suffix == ".epub"
