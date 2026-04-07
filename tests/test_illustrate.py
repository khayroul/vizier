"""Tests for the stateful illustration pipeline (S15b)."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
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
    LoRAConfig,
    NarrativeScaffold,
    PageScaffold,
    PageTurnEffect,
    PhysicalDescription,
    ReferenceImages,
    StyleLock,
    StyleNotes,
    TextImageRelationship,
    TextPlacementStrategy,
)
from tools.illustrate import (
    _ANCHOR_INTERVAL,
    IllustrationPipeline,
    build_illustration_prompt,
    run_creative_workshop,
    run_derivative_workshop,
    run_page_production,
    run_specimen_page,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_test_image(
    width: int = 1024,
    height: int = 1024,
    color: tuple[int, int, int] = (128, 128, 128),
) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _sample_character_bible() -> CharacterBible:
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
            face=FaceDetails(
                shape="round",
                eyes="large dark brown",
                nose="small",
                mouth="smiling",
            ),
            hair=HairDetails(style="black straight, shoulder length", colour="#1A1A1A"),
        ),
        clothing=ClothingDescription(default="light blue baju kurung with white headscarf"),
        style_notes=StyleNotes(
            art_style="soft watercolour, warm tones",
            line_weight="thin, delicate",
            colour_palette="warm earth tones, soft pastels",
            never=["scary imagery", "violence"],
            always=["headscarf", "warm lighting"],
        ),
        reference_images=ReferenceImages(front_view="/tmp/test_ref_front.jpg"),
    )


def _sample_style_lock() -> StyleLock:
    return StyleLock(
        art_style="soft watercolour",
        palette=["#264653", "#FFF8F0", "#E76F51"],
        typography="Plus Jakarta Sans",
        text_placement_strategy=TextPlacementStrategy.text_always_below,
    )


def _sample_page(page_num: int = 1) -> PageScaffold:
    return PageScaffold(
        page=page_num,
        word_target=30,
        emotional_beat="curiosity",
        characters_present=["aminah"],
        checkpoint_progress=f"Page {page_num}",
        text_image_relationship=TextImageRelationship.complementary,
        illustration_shows="Aminah walking through a morning market, stalls with colourful fruit",
        page_turn_effect=PageTurnEffect.continuation,
        composition_guide=CompositionGuide(
            camera="medium_shot",
            character_position="centre",
            background_detail="detailed",
            colour_temperature="warm",
            text_zone="bottom_third",
        ),
    )


def _setup_pipeline_with_refs(tmp_path: Path) -> IllustrationPipeline:
    """Create a pipeline with mocked character references."""
    img_bytes = _make_test_image()
    pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
    ref_path = tmp_path / "ref.jpg"
    ref_path.write_bytes(img_bytes)
    with patch("tools.illustrate.upload_to_fal", return_value="https://fal.media/anchor.jpg"):
        pipeline.set_character_references("aminah", [ref_path])
    return pipeline


# ---------------------------------------------------------------------------
# Task 4: Pipeline init and state
# ---------------------------------------------------------------------------


class TestPipelineInit:
    """IllustrationPipeline initialises with correct state."""

    def test_init_sets_style_lock(self) -> None:
        sl = _sample_style_lock()
        pipeline = IllustrationPipeline(style_lock=sl, job_id="test-job")
        assert pipeline.style_lock == sl

    def test_init_empty_references(self) -> None:
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test-job")
        assert pipeline.character_references == {}

    def test_init_no_previous_page(self) -> None:
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test-job")
        assert pipeline.previous_page_image is None

    def test_init_empty_scores(self) -> None:
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test-job")
        assert pipeline.consistency_scores == []

    def test_get_anchor_status_initial(self) -> None:
        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test-job")
        status = pipeline.get_anchor_status()
        assert status["pages_since_anchor"] == 0
        assert status["total_pages"] == 0
        assert status["avg_consistency"] == 0.0


# ---------------------------------------------------------------------------
# Task 5: Prompt builder
# ---------------------------------------------------------------------------


class TestBuildIllustrationPrompt:
    """Prompt is built from illustration_shows + composition + style, never page text."""

    def test_uses_illustration_shows(self) -> None:
        prompt = build_illustration_prompt(
            page=_sample_page(),
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        assert "morning market" in prompt
        assert "colourful fruit" in prompt

    def test_includes_composition_guide(self) -> None:
        prompt = build_illustration_prompt(
            page=_sample_page(),
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        assert "medium_shot" in prompt or "medium shot" in prompt
        assert "warm" in prompt

    def test_includes_style_lock_art_style(self) -> None:
        prompt = build_illustration_prompt(
            page=_sample_page(),
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        assert "watercolour" in prompt.lower()

    def test_includes_palette(self) -> None:
        prompt = build_illustration_prompt(
            page=_sample_page(),
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        assert "#264653" in prompt

    def test_includes_text_free_instruction(self) -> None:
        """Anti-drift #49: illustrations MUST be text-free."""
        prompt = build_illustration_prompt(
            page=_sample_page(),
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        lower = prompt.lower()
        assert "do not include any text" in lower

    def test_includes_character_style_notes(self) -> None:
        prompt = build_illustration_prompt(
            page=_sample_page(),
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        assert "headscarf" in prompt.lower() or "baju kurung" in prompt.lower()

    def test_never_includes_page_text(self) -> None:
        """Anti-drift #49: prompt from illustration_shows, not page text."""
        page_text = "Si Arnab tinggal di tepi sungai yang sangat cantik."
        prompt = build_illustration_prompt(
            page=_sample_page(),
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
        )
        assert page_text not in prompt


# ---------------------------------------------------------------------------
# Task 6: CLIP consistency verification
# ---------------------------------------------------------------------------


class TestVerifyConsistency:
    """CLIP consistency verification with position-aware cropping."""

    def test_identical_image_passes(self, tmp_path: Path) -> None:
        img_bytes = _make_test_image(color=(200, 100, 50))
        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(img_bytes)

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        pipeline.character_references = {"aminah": [ref_path]}
        pipeline._cache_reference_embeddings()

        passed, score = pipeline.verify_consistency(
            generated_bytes=img_bytes,
            characters_present=["aminah"],
            character_position="centre",
        )
        assert passed is True
        assert score > 0.95

    def test_threshold_controls_result(self, tmp_path: Path) -> None:
        img_bytes = _make_test_image()
        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(img_bytes)

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        pipeline.character_references = {"aminah": [ref_path]}
        pipeline._cache_reference_embeddings()

        passed, _score = pipeline.verify_consistency(
            generated_bytes=img_bytes,
            characters_present=["aminah"],
            character_position="centre",
            threshold=1.01,
        )
        assert passed is False

    def test_cached_embeddings_used(self, tmp_path: Path) -> None:
        img_bytes = _make_test_image()
        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(img_bytes)

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        pipeline.character_references = {"aminah": [ref_path]}
        pipeline._cache_reference_embeddings()

        assert "aminah" in pipeline.character_ref_embeddings
        assert len(pipeline.character_ref_embeddings["aminah"]) == 1
        assert len(pipeline.character_ref_embeddings["aminah"][0]) == 512

    def test_character_cropped_scores_more_stable_than_full_page(self, tmp_path: Path) -> None:
        """Character-cropped CLIP should be more stable when character is
        consistent but background varies (exit criterion)."""
        base = Image.new("RGB", (100, 100), color=(200, 100, 50))
        # Image A: blue border
        img_a = Image.new("RGB", (100, 100), color=(0, 0, 255))
        img_a.paste(base.crop((20, 20, 80, 80)), (20, 20))
        buf_a = BytesIO()
        img_a.save(buf_a, format="JPEG")
        # Image B: green border
        img_b = Image.new("RGB", (100, 100), color=(0, 255, 0))
        img_b.paste(base.crop((20, 20, 80, 80)), (20, 20))
        buf_b = BytesIO()
        img_b.save(buf_b, format="JPEG")

        ref_path = tmp_path / "ref.jpg"
        ref_path.write_bytes(buf_a.getvalue())

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        pipeline.character_references = {"aminah": [ref_path]}
        pipeline._cache_reference_embeddings()

        _, cropped_score = pipeline.verify_consistency(
            generated_bytes=buf_b.getvalue(),
            characters_present=["aminah"],
            character_position="centre",
        )
        # Full-page CLIP for comparison
        from utils.retrieval import encode_image

        emb_a = encode_image(buf_a.getvalue())
        emb_b = encode_image(buf_b.getvalue())
        full_score = sum(a * b for a, b in zip(emb_a, emb_b))

        # Cropped should be >= full page (centre is same, borders differ)
        assert cropped_score >= full_score - 0.05


# ---------------------------------------------------------------------------
# Task 7: Character reference generation
# ---------------------------------------------------------------------------


class TestGenerateCharacterReferences:
    """generate_character_references() produces 10+ candidates from CharacterBible."""

    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    @patch("tools.illustrate.upload_bytes")
    def test_generates_requested_count(
        self, mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen: MagicMock, tmp_path: Path,
    ) -> None:
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {
            "composition": "test prompt", "style": "", "brand": "",
            "technical": "", "text_content": "",
        }
        mock_upload.return_value = "vizier-assets/refs/test.jpg"

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        paths = pipeline.generate_character_references(
            character_bible=_sample_character_bible(),
            output_dir=tmp_path,
            count=10,
        )
        assert len(paths) == 10
        assert mock_gen.call_count == 10

    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    @patch("tools.illustrate.upload_bytes")
    def test_saves_images_to_disk(
        self, mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen: MagicMock, tmp_path: Path,
    ) -> None:
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {
            "composition": "test", "style": "", "brand": "",
            "technical": "", "text_content": "",
        }
        mock_upload.return_value = "vizier-assets/refs/test.jpg"

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        paths = pipeline.generate_character_references(
            character_bible=_sample_character_bible(),
            output_dir=tmp_path,
            count=3,
        )
        for path in paths:
            assert path.exists()
            assert path.stat().st_size > 0

    @patch("tools.illustrate.generate_image")
    @patch("tools.illustrate.expand_brief")
    @patch("tools.illustrate.upload_bytes")
    def test_prompt_uses_physical_description(
        self, mock_upload: MagicMock, mock_expand: MagicMock,
        mock_gen: MagicMock, tmp_path: Path,
    ) -> None:
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {
            "composition": "test", "style": "", "brand": "",
            "technical": "", "text_content": "",
        }
        mock_upload.return_value = "vizier-assets/refs/test.jpg"

        pipeline = IllustrationPipeline(style_lock=_sample_style_lock(), job_id="test")
        pipeline.generate_character_references(
            character_bible=_sample_character_bible(),
            output_dir=tmp_path,
            count=1,
        )
        brief_arg = mock_expand.call_args[0][0]
        assert "Aminah" in brief_arg
        assert "Malay" in brief_arg


# ---------------------------------------------------------------------------
# Task 8: illustrate_page()
# ---------------------------------------------------------------------------


_MOCK_PATCHES = [
    "tools.illustrate.upload_to_fal",
    "tools.illustrate.upload_bytes",
    "tools.illustrate.generate_image",
    "tools.illustrate.expand_brief",
]


class TestIllustratePage:
    """illustrate_page() generates text-free illustrations with consistency tracking."""

    @patch(_MOCK_PATCHES[0], return_value="https://fal.media/files/test/page.jpg")
    @patch(_MOCK_PATCHES[1], return_value="vizier-assets/pages/test.jpg")
    @patch(_MOCK_PATCHES[2])
    @patch(_MOCK_PATCHES[3])
    def test_uses_illustration_shows_not_page_text(
        self, mock_expand: MagicMock, mock_gen: MagicMock,
        _mock_upload: MagicMock, _mock_fal: MagicMock, tmp_path: Path,
    ) -> None:
        img_bytes = _make_test_image()
        mock_gen.return_value = img_bytes
        mock_expand.return_value = {
            "composition": "expanded prompt", "style": "", "brand": "",
            "technical": "", "text_content": "",
        }

        pipeline = _setup_pipeline_with_refs(tmp_path)
        result = pipeline.illustrate_page(
            page=_sample_page(page_num=1),
            character_bibles=[_sample_character_bible()],
            output_dir=tmp_path,
        )
        brief_arg = mock_expand.call_args[0][0]
        assert "morning market" in brief_arg
        assert isinstance(result, Path)

    @patch(_MOCK_PATCHES[0], return_value="https://fal.media/files/test/page.jpg")
    @patch(_MOCK_PATCHES[1], return_value="vizier-assets/pages/test.jpg")
    @patch(_MOCK_PATCHES[2])
    @patch(_MOCK_PATCHES[3])
    def test_anchor_reset_on_page_8(
        self, mock_expand: MagicMock, mock_gen: MagicMock,
        _mock_upload: MagicMock, _mock_fal: MagicMock, tmp_path: Path,
    ) -> None:
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {
            "composition": "prompt", "style": "", "brand": "",
            "technical": "", "text_content": "",
        }

        pipeline = _setup_pipeline_with_refs(tmp_path)
        pipeline.anchor_image_url = "https://fal.media/files/test/anchor.jpg"

        for page_num in range(1, 9):
            pipeline.illustrate_page(
                page=_sample_page(page_num=page_num),
                character_bibles=[_sample_character_bible()],
                output_dir=tmp_path,
            )

        # Page 8 (divisible by 8) triggers anchor reset, then increments to 1
        assert pipeline.pages_since_anchor == 1  # reset on page 8, then +1

    @patch(_MOCK_PATCHES[0], return_value="https://fal.media/files/test/page.jpg")
    @patch(_MOCK_PATCHES[1], return_value="vizier-assets/pages/test.jpg")
    @patch(_MOCK_PATCHES[2])
    @patch(_MOCK_PATCHES[3])
    def test_kontext_model_used(
        self, mock_expand: MagicMock, mock_gen: MagicMock,
        _mock_upload: MagicMock, _mock_fal: MagicMock, tmp_path: Path,
    ) -> None:
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {
            "composition": "prompt", "style": "", "brand": "",
            "technical": "", "text_content": "",
        }

        pipeline = _setup_pipeline_with_refs(tmp_path)
        pipeline.illustrate_page(
            page=_sample_page(),
            character_bibles=[_sample_character_bible()],
            output_dir=tmp_path,
        )
        gen_kwargs = mock_gen.call_args[1]
        assert gen_kwargs["model"] == "fal-ai/flux-pro/kontext"

    @patch(_MOCK_PATCHES[0], return_value="https://fal.media/files/test/prev.jpg")
    @patch(_MOCK_PATCHES[1], return_value="vizier-assets/pages/test.jpg")
    @patch(_MOCK_PATCHES[2])
    @patch(_MOCK_PATCHES[3])
    def test_previous_page_fed_to_kontext(
        self, mock_expand: MagicMock, mock_gen: MagicMock,
        _mock_upload: MagicMock, _mock_fal: MagicMock, tmp_path: Path,
    ) -> None:
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {
            "composition": "prompt", "style": "", "brand": "",
            "technical": "", "text_content": "",
        }

        pipeline = _setup_pipeline_with_refs(tmp_path)
        pipeline.illustrate_page(
            page=_sample_page(1),
            character_bibles=[_sample_character_bible()],
            output_dir=tmp_path,
        )
        pipeline.illustrate_page(
            page=_sample_page(2),
            character_bibles=[_sample_character_bible()],
            output_dir=tmp_path,
        )
        # Page 2's generate_image call should have image_url set
        second_call_kwargs = mock_gen.call_args_list[1][1]
        assert second_call_kwargs.get("image_url") is not None

    @patch(_MOCK_PATCHES[0], return_value="https://fal.media/files/test/page.jpg")
    @patch(_MOCK_PATCHES[1], return_value="vizier-assets/pages/test.jpg")
    @patch(_MOCK_PATCHES[2])
    @patch(_MOCK_PATCHES[3])
    def test_tracks_consistency_scores(
        self, mock_expand: MagicMock, mock_gen: MagicMock,
        _mock_upload: MagicMock, _mock_fal: MagicMock, tmp_path: Path,
    ) -> None:
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {
            "composition": "prompt", "style": "", "brand": "",
            "technical": "", "text_content": "",
        }

        pipeline = _setup_pipeline_with_refs(tmp_path)
        pipeline.illustrate_page(
            page=_sample_page(),
            character_bibles=[_sample_character_bible()],
            output_dir=tmp_path,
        )
        assert len(pipeline.consistency_scores) == 1
        assert pipeline.consistency_scores[0] > 0.0

    @patch(_MOCK_PATCHES[0], return_value="https://fal.media/files/test/page.jpg")
    @patch(_MOCK_PATCHES[1], return_value="vizier-assets/pages/test.jpg")
    @patch(_MOCK_PATCHES[2])
    @patch(_MOCK_PATCHES[3])
    def test_lora_trigger_word_in_prompt(
        self, mock_expand: MagicMock, mock_gen: MagicMock,
        _mock_upload: MagicMock, _mock_fal: MagicMock, tmp_path: Path,
    ) -> None:
        """If CharacterBible has LoRA config, trigger word appears in prompt."""
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {
            "composition": "prompt", "style": "", "brand": "",
            "technical": "", "text_content": "",
        }

        bible = _sample_character_bible().model_copy(
            update={"lora": LoRAConfig(
                character_lora_url="https://example.com/lora.safetensors",
                trigger_word="aminah_character",
                training_images=20,
            )},
        )

        pipeline = _setup_pipeline_with_refs(tmp_path)
        pipeline.illustrate_page(
            page=_sample_page(),
            character_bibles=[bible],
            output_dir=tmp_path,
        )
        # The raw brief passed to expand_brief should contain the trigger word
        brief_arg = mock_expand.call_args[0][0]
        assert "aminah_character" in brief_arg


# ---------------------------------------------------------------------------
# Task 9: Workshop flow
# ---------------------------------------------------------------------------


class TestCreativeWorkshopFlow:
    """Creative workshop -> specimen -> production -> assembly flow."""

    @patch(_MOCK_PATCHES[0], return_value="https://fal.media/files/test/img.jpg")
    @patch(_MOCK_PATCHES[1], return_value="vizier-assets/test.jpg")
    @patch(_MOCK_PATCHES[3])
    @patch(_MOCK_PATCHES[2])
    def test_full_flow_produces_images(
        self, mock_gen: MagicMock, mock_expand: MagicMock,
        _mock_upload: MagicMock, _mock_fal: MagicMock, tmp_path: Path,
    ) -> None:
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {
            "composition": "prompt", "style": "", "brand": "",
            "technical": "", "text_content": "",
        }

        scaffold = NarrativeScaffold.decompose(
            target_age=AgeGroup.age_5_7,
            page_count=3,
            pages=[_sample_page(i + 1) for i in range(3)],
        )

        pipeline = run_creative_workshop(
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
            job_id="test-job",
            output_dir=tmp_path,
            ref_count=2,
        )
        assert isinstance(pipeline, IllustrationPipeline)

        specimen = run_specimen_page(
            pipeline=pipeline,
            page=scaffold.pages[0],
            character_bibles=[_sample_character_bible()],
            output_dir=tmp_path,
        )
        assert specimen.exists()

        ctx = RollingContext(
            context_type="narrative", recent_window=8, medium_scope="not_needed",
        )
        images = run_page_production(
            pipeline=pipeline,
            scaffold=scaffold,
            character_bibles=[_sample_character_bible()],
            rolling_context=ctx,
            output_dir=tmp_path,
        )
        assert len(images) == 3
        assert ctx.current_step == 3

    @patch(_MOCK_PATCHES[0], return_value="https://fal.media/files/test/img.jpg")
    @patch(_MOCK_PATCHES[1], return_value="vizier-assets/test.jpg")
    @patch(_MOCK_PATCHES[3])
    @patch(_MOCK_PATCHES[2])
    def test_rolling_context_updated_per_page(
        self, mock_gen: MagicMock, mock_expand: MagicMock,
        _mock_upload: MagicMock, _mock_fal: MagicMock, tmp_path: Path,
    ) -> None:
        mock_gen.return_value = _make_test_image()
        mock_expand.return_value = {
            "composition": "prompt", "style": "", "brand": "",
            "technical": "", "text_content": "",
        }

        scaffold = NarrativeScaffold.decompose(
            target_age=AgeGroup.age_5_7,
            page_count=2,
            pages=[_sample_page(1), _sample_page(2)],
        )

        pipeline = run_creative_workshop(
            style_lock=_sample_style_lock(),
            character_bibles=[_sample_character_bible()],
            job_id="test-job",
            output_dir=tmp_path,
            ref_count=1,
        )

        ctx = RollingContext(
            context_type="narrative", recent_window=8, medium_scope="not_needed",
        )
        run_page_production(
            pipeline=pipeline,
            scaffold=scaffold,
            character_bibles=[_sample_character_bible()],
            rolling_context=ctx,
            output_dir=tmp_path,
        )

        entity_ids = [e.entity_id for e in ctx.entities]
        assert "aminah" in entity_ids


class TestDerivativeWorkshop:
    """Derivative workshop loads source StyleLock and proceeds to new content."""

    def test_inherits_style_lock(self) -> None:
        source_style = _sample_style_lock()
        pipeline = run_derivative_workshop(
            source_style_lock=source_style,
            job_id="derivative-job",
        )
        assert pipeline.style_lock == source_style
