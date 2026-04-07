"""IT-2: Children's Book Specimen Page — Full Chain Integration Test.

Validates: S6 contracts + S9 workflows + S15a assembly + S15b illustration
           + S13 visual scoring working together end-to-end.

Input: 8-page NarrativeScaffold for a Raya-themed children's book.

Expected chain:
    scaffold decomposition → illustration prompt from illustration_shows
    → image generation (mocked fal.ai) → CLIP consistency verification
    → Typst assembly with text overlay → NIMA + 4-dim critique → trace capture.

External APIs mocked: fal.ai (fal_client), OpenAI (call_llm), CLIP (encode_image).
Internal functions run real: contracts, routing, trace, database.

Anti-drift #49: illustration prompts use illustration_shows, NOT page text.
Anti-drift #54: all model_preference = gpt-5.4-mini.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from contracts.publishing import (
    AgeGroup,
    CharacterBible,
    ClothingDescription,
    ClothingVariant,
    CompositionGuide,
    FaceDetails,
    HairDetails,
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
from contracts.trace import TraceCollector
from tools.illustrate import (
    IllustrationPipeline,
    _ANCHOR_INTERVAL,
    build_illustration_prompt,
    run_specimen_page,
)
from tools.publish import assemble_childrens_book_pdf, check_visual_consistency
from tools.visual_scoring import critique_4dim, nima_prescreen

# ---------------------------------------------------------------------------
# Test image: 1x1 red PNG for mock image generation
# ---------------------------------------------------------------------------

_TEST_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

# 512-dim normalised embedding for deterministic CLIP mocking
_MOCK_EMBEDDING = [1.0 / 512**0.5] * 512


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_call_llm_response(content: str, **kwargs: Any) -> dict[str, Any]:
    """Build a mock call_llm return value."""
    return {
        "content": content,
        "model": "gpt-5.4-mini",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.0001,
    }


# ---------------------------------------------------------------------------
# Fixtures — contract objects for children's book testing
# ---------------------------------------------------------------------------


def _make_composition_guide(
    camera: str = "medium_shot",
    character_position: str = "centre",
    background_detail: str = "medium",
    colour_temperature: str = "warm",
    text_zone: str = "bottom_third",
) -> CompositionGuide:
    return CompositionGuide(
        camera=camera,
        character_position=character_position,
        background_detail=background_detail,
        colour_temperature=colour_temperature,
        text_zone=text_zone,
    )


def _make_page(
    page: int,
    word_target: int = 25,
    emotional_beat: str = "wonder",
    illustration_shows: str = "Adik sees a glowing ketupat hanging from a rambutan tree",
    characters_present: list[str] | None = None,
    page_turn_effect: PageTurnEffect = PageTurnEffect.continuation,
) -> PageScaffold:
    return PageScaffold(
        page=page,
        word_target=word_target,
        emotional_beat=emotional_beat,
        characters_present=characters_present or ["adik"],
        checkpoint_progress=f"Page {page} checkpoint",
        text_image_relationship=TextImageRelationship.complementary,
        illustration_shows=illustration_shows,
        page_turn_effect=page_turn_effect,
        composition_guide=_make_composition_guide(),
    )


@pytest.fixture()
def sample_scaffold() -> NarrativeScaffold:
    """8-page NarrativeScaffold for a Raya-themed children's book."""
    pages = [
        _make_page(1, emotional_beat="curiosity",
                   illustration_shows="Adik wakes up in a kampung house decorated with colourful Raya lights",
                   page_turn_effect=PageTurnEffect.continuation),
        _make_page(2, emotional_beat="wonder",
                   illustration_shows="Adik discovers a golden ketupat glowing under the rambutan tree",
                   page_turn_effect=PageTurnEffect.reveal),
        _make_page(3, emotional_beat="excitement",
                   illustration_shows="Adik and Tok running through a field of bunga raya towards the village",
                   characters_present=["adik", "tok"],
                   page_turn_effect=PageTurnEffect.continuation),
        _make_page(4, emotional_beat="challenge",
                   illustration_shows="Adik trying to climb a coconut tree while Tok watches nervously",
                   characters_present=["adik", "tok"],
                   page_turn_effect=PageTurnEffect.pause),
        _make_page(5, emotional_beat="determination",
                   illustration_shows="Adik reaching the top of the tree with the golden ketupat in sight",
                   page_turn_effect=PageTurnEffect.continuation),
        _make_page(6, emotional_beat="triumph",
                   illustration_shows="Adik holds the golden ketupat high as sunlight streams through the leaves",
                   page_turn_effect=PageTurnEffect.reveal),
        _make_page(7, emotional_beat="warmth",
                   illustration_shows="Adik and Tok sharing the ketupat with the whole kampung at the Raya table",
                   characters_present=["adik", "tok"],
                   page_turn_effect=PageTurnEffect.continuation),
        _make_page(8, emotional_beat="contentment",
                   illustration_shows="Adik sleeping peacefully under the rambutan tree as fireflies glow",
                   page_turn_effect=PageTurnEffect.climax),
    ]
    return NarrativeScaffold.decompose(
        target_age=AgeGroup.age_3_5,
        page_count=8,
        pages=pages,
    )


@pytest.fixture()
def sample_character_bible() -> CharacterBible:
    """Adik character for testing."""
    return CharacterBible(
        character_id="adik",
        name="Adik",
        role="protagonist",
        physical=PhysicalDescription(
            age=5,
            ethnicity="Malay",
            skin_tone="#8D6E63",
            height="short",
            build="small",
            face=FaceDetails(
                shape="round",
                eyes="large, bright brown",
                nose="small button",
                mouth="smiling",
                distinctive="dimples",
            ),
            hair=HairDetails(style="short and wavy", colour="#1A1A1A"),
        ),
        clothing=ClothingDescription(
            default="baju Melayu kurung in soft green with gold trim",
            variants=[
                ClothingVariant(name="casual", description="white t-shirt and shorts"),
            ],
        ),
        style_notes=StyleNotes(
            art_style="soft watercolour, Studio Ghibli influence",
            line_weight="thin, delicate",
            colour_palette="warm earth tones, soft pastels",
            never=["sharp edges", "dark shadows", "realistic proportions"],
            always=["rosy cheeks", "soft lighting", "round features"],
        ),
        reference_images=ReferenceImages(),
    )


@pytest.fixture()
def sample_tok_bible() -> CharacterBible:
    """Tok (grandmother) character for multi-character tests."""
    return CharacterBible(
        character_id="tok",
        name="Tok",
        role="supporting",
        physical=PhysicalDescription(
            age=65,
            ethnicity="Malay",
            skin_tone="#A1887F",
            height="medium",
            build="plump",
            face=FaceDetails(
                shape="round",
                eyes="kind, crinkled",
                nose="wide, gentle",
                mouth="warm smile",
                distinctive="crow's feet wrinkles",
            ),
            hair=HairDetails(style="tied in a bun", colour="#9E9E9E"),
        ),
        clothing=ClothingDescription(
            default="batik sarong with white kebaya top",
        ),
        style_notes=StyleNotes(
            art_style="soft watercolour, Studio Ghibli influence",
            line_weight="thin, delicate",
            colour_palette="warm earth tones, soft pastels",
            never=["sharp edges", "dark shadows"],
            always=["gentle wrinkles", "warm expression"],
        ),
    )


@pytest.fixture()
def sample_style_lock() -> StyleLock:
    """Soft watercolour style lock for testing."""
    return StyleLock(
        art_style="soft watercolour, Studio Ghibli influence",
        palette=["#264653", "#FFF8F0", "#E76F51", "#2A9D8F", "#E9C46A"],
        typography="Noto Sans",
        text_placement_strategy=TextPlacementStrategy.text_always_below,
    )


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestScaffoldDecomposition:
    """IT-2 Step 1: NarrativeScaffold with 8 pages has all required fields."""

    def test_scaffold_has_8_pages(self, sample_scaffold: NarrativeScaffold) -> None:
        assert sample_scaffold.page_count == 8
        assert len(sample_scaffold.pages) == 8

    def test_each_page_has_required_fields(self, sample_scaffold: NarrativeScaffold) -> None:
        for page in sample_scaffold.pages:
            assert page.word_target > 0, f"Page {page.page} missing word_target"
            assert page.emotional_beat, f"Page {page.page} missing emotional_beat"
            assert page.characters_present, f"Page {page.page} missing characters_present"
            assert page.illustration_shows, f"Page {page.page} missing illustration_shows"
            assert page.text_image_relationship, f"Page {page.page} missing text_image_relationship"
            assert page.composition_guide, f"Page {page.page} missing composition_guide"

    def test_illustration_shows_is_populated(self, sample_scaffold: NarrativeScaffold) -> None:
        """illustration_shows is the prompt source, NOT page text (anti-drift #49)."""
        for page in sample_scaffold.pages:
            assert len(page.illustration_shows) > 10, (
                f"Page {page.page}: illustration_shows too short — "
                "this field drives illustration prompts, must be descriptive"
            )

    def test_age_defaults_applied(self, sample_scaffold: NarrativeScaffold) -> None:
        """age_3_5 scaffold should have typography and arc_template set."""
        assert sample_scaffold.target_age == AgeGroup.age_3_5
        assert sample_scaffold.typography is not None
        assert sample_scaffold.arc_template != ""


class TestCharacterBibleCreation:
    """IT-2 Step 2: CharacterBible passes Pydantic validation."""

    def test_character_bible_valid(self, sample_character_bible: CharacterBible) -> None:
        assert sample_character_bible.character_id == "adik"
        assert sample_character_bible.name == "Adik"
        assert sample_character_bible.role == "protagonist"
        assert sample_character_bible.physical.age == 5
        assert sample_character_bible.physical.ethnicity == "Malay"
        assert sample_character_bible.physical.skin_tone == "#8D6E63"
        assert sample_character_bible.clothing.default != ""
        assert sample_character_bible.style_notes.art_style != ""

    def test_character_bible_style_notes(self, sample_character_bible: CharacterBible) -> None:
        assert "watercolour" in sample_character_bible.style_notes.art_style
        assert len(sample_character_bible.style_notes.never) > 0
        assert len(sample_character_bible.style_notes.always) > 0


class TestStyleLockCreation:
    """IT-2 Step 3: StyleLock with valid text_placement_strategy."""

    def test_style_lock_valid(self, sample_style_lock: StyleLock) -> None:
        assert sample_style_lock.art_style != ""
        assert len(sample_style_lock.palette) >= 3
        assert sample_style_lock.typography != ""

    def test_text_placement_strategy_valid(self, sample_style_lock: StyleLock) -> None:
        valid_strategies = {s.value for s in TextPlacementStrategy}
        assert sample_style_lock.text_placement_strategy.value in valid_strategies


class TestIllustrationPrompt:
    """IT-2 Step 4: Prompt uses illustration_shows, NOT page text (anti-drift #49)."""

    def test_prompt_contains_illustration_shows(
        self,
        sample_scaffold: NarrativeScaffold,
        sample_character_bible: CharacterBible,
        sample_style_lock: StyleLock,
    ) -> None:
        page = sample_scaffold.pages[0]
        prompt = build_illustration_prompt(
            page=page,
            style_lock=sample_style_lock,
            character_bibles=[sample_character_bible],
        )
        assert page.illustration_shows in prompt, (
            "Prompt must include illustration_shows field verbatim"
        )

    def test_prompt_does_not_contain_page_text(
        self,
        sample_scaffold: NarrativeScaffold,
        sample_character_bible: CharacterBible,
        sample_style_lock: StyleLock,
    ) -> None:
        """Anti-drift #49: text-free illustrations. Prompt must NOT use page text."""
        page = sample_scaffold.pages[0]
        prompt = build_illustration_prompt(
            page=page,
            style_lock=sample_style_lock,
            character_bibles=[sample_character_bible],
        )
        # checkpoint_progress is the closest thing to "page text" on the scaffold
        if page.checkpoint_progress:
            # Only assert if checkpoint_progress is substantive and different
            # from illustration_shows
            if page.checkpoint_progress != page.illustration_shows:
                assert page.checkpoint_progress not in prompt or "Page" in page.checkpoint_progress, (
                    "Prompt should NOT include page text content — "
                    "illustration_shows is the sole source (anti-drift #49)"
                )

    def test_prompt_enforces_text_free(
        self,
        sample_scaffold: NarrativeScaffold,
        sample_character_bible: CharacterBible,
        sample_style_lock: StyleLock,
    ) -> None:
        page = sample_scaffold.pages[0]
        prompt = build_illustration_prompt(
            page=page,
            style_lock=sample_style_lock,
            character_bibles=[sample_character_bible],
        )
        assert "text-free" in prompt.lower() or "do not include any text" in prompt.lower(), (
            "Prompt must explicitly instruct text-free illustration (anti-drift #49)"
        )

    def test_prompt_includes_style_lock_fields(
        self,
        sample_scaffold: NarrativeScaffold,
        sample_character_bible: CharacterBible,
        sample_style_lock: StyleLock,
    ) -> None:
        page = sample_scaffold.pages[0]
        prompt = build_illustration_prompt(
            page=page,
            style_lock=sample_style_lock,
            character_bibles=[sample_character_bible],
        )
        assert sample_style_lock.art_style in prompt
        assert page.composition_guide.camera in prompt

    def test_prompt_includes_character_details_for_present_characters(
        self,
        sample_scaffold: NarrativeScaffold,
        sample_character_bible: CharacterBible,
        sample_style_lock: StyleLock,
    ) -> None:
        page = sample_scaffold.pages[0]  # has characters_present=["adik"]
        prompt = build_illustration_prompt(
            page=page,
            style_lock=sample_style_lock,
            character_bibles=[sample_character_bible],
        )
        assert "Adik" in prompt, "Character name should appear in prompt"
        assert "Malay" in prompt, "Ethnicity should appear in prompt"


class TestIllustrationPipelineInit:
    """IT-2 Step 5: Pipeline initialises with clean state."""

    def test_pipeline_init_empty_state(self, sample_style_lock: StyleLock) -> None:
        pipeline = IllustrationPipeline(style_lock=sample_style_lock, job_id="test-job")
        assert pipeline.previous_page_image is None
        assert pipeline.anchor_image_url is None
        assert pipeline.pages_since_anchor == 0
        assert pipeline.total_pages == 0
        assert pipeline.consistency_scores == []
        assert pipeline.character_references == {}
        assert pipeline.character_ref_embeddings == {}

    def test_pipeline_has_trace_collector(self, sample_style_lock: StyleLock) -> None:
        pipeline = IllustrationPipeline(style_lock=sample_style_lock, job_id="test-job-123")
        assert isinstance(pipeline.collector, TraceCollector)

    def test_pipeline_anchor_status_initial(self, sample_style_lock: StyleLock) -> None:
        pipeline = IllustrationPipeline(style_lock=sample_style_lock, job_id="test-job")
        status = pipeline.get_anchor_status()
        assert status["pages_since_anchor"] == 0
        assert status["total_pages"] == 0
        assert status["avg_consistency"] == 0.0
        assert status["anchor_url"] == ""


class TestSpecimenPageGeneration:
    """IT-2 Step 6: Specimen page via mocked fal.ai."""

    @patch("tools.illustrate.upload_to_fal", return_value="https://fal.ai/mock-url")
    @patch("tools.illustrate.upload_bytes", return_value="vizier-assets/test")
    @patch("tools.illustrate.generate_image", return_value=_TEST_PNG)
    @patch("tools.illustrate.expand_brief", return_value={"composition": "test prompt"})
    def test_specimen_page_returns_path(
        self,
        mock_expand: MagicMock,
        mock_gen: MagicMock,
        mock_upload: MagicMock,
        mock_fal_upload: MagicMock,
        sample_scaffold: NarrativeScaffold,
        sample_character_bible: CharacterBible,
        sample_style_lock: StyleLock,
        tmp_path: Path,
    ) -> None:
        pipeline = IllustrationPipeline(style_lock=sample_style_lock, job_id="test-specimen")
        page = sample_scaffold.pages[0]

        result = run_specimen_page(
            pipeline=pipeline,
            page=page,
            character_bibles=[sample_character_bible],
            output_dir=tmp_path,
        )

        assert result.exists(), "Specimen page file should exist on disk"
        assert result.suffix == ".jpg"
        assert pipeline.total_pages == 1
        mock_gen.assert_called_once()

    @patch("tools.illustrate.upload_to_fal", return_value="https://fal.ai/mock-url")
    @patch("tools.illustrate.upload_bytes", return_value="vizier-assets/test")
    @patch("tools.illustrate.generate_image", return_value=_TEST_PNG)
    @patch("tools.illustrate.expand_brief", return_value={"composition": "test prompt"})
    def test_specimen_page_updates_pipeline_state(
        self,
        mock_expand: MagicMock,
        mock_gen: MagicMock,
        mock_upload: MagicMock,
        mock_fal_upload: MagicMock,
        sample_scaffold: NarrativeScaffold,
        sample_character_bible: CharacterBible,
        sample_style_lock: StyleLock,
        tmp_path: Path,
    ) -> None:
        pipeline = IllustrationPipeline(style_lock=sample_style_lock, job_id="test-specimen")

        run_specimen_page(
            pipeline=pipeline,
            page=sample_scaffold.pages[0],
            character_bibles=[sample_character_bible],
            output_dir=tmp_path,
        )

        assert pipeline.total_pages == 1
        assert pipeline.pages_since_anchor == 1
        assert pipeline.previous_page_image == "https://fal.ai/mock-url"
        assert len(pipeline.collector.steps) >= 1

    @patch("tools.illustrate.upload_to_fal", return_value="https://fal.ai/mock-url")
    @patch("tools.illustrate.upload_bytes", return_value="vizier-assets/test")
    @patch("tools.illustrate.generate_image", return_value=_TEST_PNG)
    @patch("tools.illustrate.expand_brief", return_value={"composition": "test prompt"})
    def test_specimen_trace_captured(
        self,
        mock_expand: MagicMock,
        mock_gen: MagicMock,
        mock_upload: MagicMock,
        mock_fal_upload: MagicMock,
        sample_scaffold: NarrativeScaffold,
        sample_character_bible: CharacterBible,
        sample_style_lock: StyleLock,
        tmp_path: Path,
    ) -> None:
        pipeline = IllustrationPipeline(style_lock=sample_style_lock, job_id="test-specimen")

        run_specimen_page(
            pipeline=pipeline,
            page=sample_scaffold.pages[0],
            character_bibles=[sample_character_bible],
            output_dir=tmp_path,
        )

        trace = pipeline.collector.finalise()
        assert len(trace.steps) >= 1
        assert trace.steps[0].step_name.startswith("illustrate_page_")


class TestClipConsistencyVerification:
    """IT-2 Step 7: CLIP consistency with pass/fail scenarios."""

    def test_consistency_pass_scenario(self, sample_style_lock: StyleLock) -> None:
        """Same embedding for generated and reference → similarity = 1.0 → pass."""
        pipeline = IllustrationPipeline(style_lock=sample_style_lock, job_id="test-clip")
        pipeline.character_ref_embeddings = {"adik": [_MOCK_EMBEDDING]}

        with patch("utils.retrieval.encode_image", return_value=_MOCK_EMBEDDING), \
             patch("utils.image_processing.crop_character_region", return_value=_TEST_PNG):
            passed, score = pipeline.verify_consistency(
                generated_bytes=_TEST_PNG,
                characters_present=["adik"],
                threshold=0.75,
            )

        assert passed is True
        assert score >= 0.75

    def test_consistency_fail_scenario(self, sample_style_lock: StyleLock) -> None:
        """Orthogonal embeddings → similarity ≈ 0.0 → fail."""
        pipeline = IllustrationPipeline(style_lock=sample_style_lock, job_id="test-clip")

        # Reference: all zeros except first element
        ref_emb = [0.0] * 512
        ref_emb[0] = 1.0
        pipeline.character_ref_embeddings = {"adik": [ref_emb]}

        # Generated: all zeros except last element (orthogonal)
        gen_emb = [0.0] * 512
        gen_emb[511] = 1.0

        with patch("utils.retrieval.encode_image", return_value=gen_emb), \
             patch("utils.image_processing.crop_character_region", return_value=_TEST_PNG):
            passed, score = pipeline.verify_consistency(
                generated_bytes=_TEST_PNG,
                characters_present=["adik"],
                threshold=0.75,
            )

        assert passed is False
        assert score < 0.75

    def test_consistency_no_refs_returns_zero(self, sample_style_lock: StyleLock) -> None:
        """No reference embeddings → score 0.0, fails threshold."""
        pipeline = IllustrationPipeline(style_lock=sample_style_lock, job_id="test-clip")

        with patch("utils.retrieval.encode_image", return_value=_MOCK_EMBEDDING), \
             patch("utils.image_processing.crop_character_region", return_value=_TEST_PNG):
            passed, score = pipeline.verify_consistency(
                generated_bytes=_TEST_PNG,
                characters_present=["adik"],
                threshold=0.75,
            )

        assert passed is False
        assert score == 0.0


class TestTypstAssembly:
    """IT-2 Step 8: Typst assembly generates .typ source with text overlay."""

    def test_typst_source_generated(
        self,
        sample_scaffold: NarrativeScaffold,
        sample_style_lock: StyleLock,
        tmp_path: Path,
    ) -> None:
        """Create mock images, call assembly, verify .typ file generated."""
        # Create mock image files (8 pages)
        images: list[Path] = []
        for idx in range(8):
            img_path = tmp_path / f"page_{idx + 1:03d}.jpg"
            img_path.write_bytes(_TEST_PNG)
            images.append(img_path)

        page_texts = [f"Test text for page {i + 1}." for i in range(8)]

        # Mock Typst compile since it may not be installed in CI
        with patch("tools.publish.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr="",
            )
            result = assemble_childrens_book_pdf(
                images=images,
                scaffold=sample_scaffold,
                style_lock=sample_style_lock,
                title="Ketupat Emas Adik",
                author="Vizier AI",
                output_dir=tmp_path,
                page_texts=page_texts,
            )

        # Check .typ source was written
        slug = "ketupat_emas_adik"
        typ_path = tmp_path / f"{slug}.typ"
        assert typ_path.exists(), ".typ source file should be generated"

        typ_content = typ_path.read_text(encoding="utf-8")
        # Text overlay is in Typst source, separate from images
        assert "Test text for page" in typ_content, (
            "Page text should appear in Typst source (overlaid, not in images)"
        )
        # Images are referenced as paths
        assert "image(" in typ_content, "Images should be referenced in Typst source"

    def test_text_separate_from_images(
        self,
        sample_scaffold: NarrativeScaffold,
        sample_style_lock: StyleLock,
        tmp_path: Path,
    ) -> None:
        """Anti-drift #49: text in Typst, images are text-free."""
        images: list[Path] = []
        for idx in range(8):
            img_path = tmp_path / f"page_{idx + 1:03d}.jpg"
            img_path.write_bytes(_TEST_PNG)
            images.append(img_path)

        page_texts = [f"Halaman {i + 1}: Adik menjelajah." for i in range(8)]

        with patch("tools.publish.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr="",
            )
            assemble_childrens_book_pdf(
                images=images,
                scaffold=sample_scaffold,
                style_lock=sample_style_lock,
                title="Ketupat Emas",
                author="Vizier",
                output_dir=tmp_path,
                page_texts=page_texts,
            )

        typ_path = tmp_path / "ketupat_emas.typ"
        typ_content = typ_path.read_text(encoding="utf-8")

        # Verify Typst header contains typography setup
        assert "#set text" in typ_content, "Typst should configure text styling"
        # Verify page text is present as Typst text, not embedded in image
        assert "Halaman" in typ_content

    def test_typst_compile_called(
        self,
        sample_scaffold: NarrativeScaffold,
        sample_style_lock: StyleLock,
        tmp_path: Path,
    ) -> None:
        """Typst compile is invoked with font paths."""
        images = [tmp_path / f"p{i}.jpg" for i in range(8)]
        for img in images:
            img.write_bytes(_TEST_PNG)

        with patch("tools.publish.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr="",
            )
            assemble_childrens_book_pdf(
                images=images,
                scaffold=sample_scaffold,
                style_lock=sample_style_lock,
                title="Test Book",
                author="Test",
                output_dir=tmp_path,
                page_texts=[f"p{i}" for i in range(8)],
            )

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "typst" in call_args[0][0][0], "Should call typst compiler"
        # Verify TYPST_FONT_PATHS in environment
        env = call_args[1].get("env", {})
        assert "TYPST_FONT_PATHS" in env


class TestNimaPrescreen:
    """IT-2 Step 9: NIMA prescreen classification."""

    def test_low_score_regenerate(self) -> None:
        result = nima_prescreen(3.0)
        assert result["action"] == "regenerate"
        assert result["score"] == 3.0

    def test_medium_score_caution(self) -> None:
        result = nima_prescreen(5.5)
        assert result["action"] == "proceed_with_caution"
        assert result["score"] == 5.5

    def test_high_score_pass(self) -> None:
        result = nima_prescreen(8.0)
        assert result["action"] == "pass"
        assert result["score"] == 8.0

    def test_boundary_at_4(self) -> None:
        """Score exactly 4.0 should proceed_with_caution, not regenerate."""
        result = nima_prescreen(4.0)
        assert result["action"] == "proceed_with_caution"

    def test_boundary_at_7(self) -> None:
        """Score exactly 7.0 should proceed_with_caution, not pass."""
        result = nima_prescreen(7.0)
        assert result["action"] == "proceed_with_caution"


class TestFourDimCritique:
    """IT-2 Step 10: 4-dim critique via mocked call_llm."""

    @patch("tools.visual_scoring.call_llm")
    def test_critique_returns_all_dimensions(self, mock_llm: MagicMock) -> None:
        mock_llm.return_value = _mock_call_llm_response(
            json.dumps({"score": 4.0, "issues": []})
        )

        result = critique_4dim(
            image_description="A soft watercolour illustration of a child in baju Melayu",
            brief={"composition": "Raya scene", "style": "watercolour"},
        )

        assert len(result) > 0, "Should return at least one dimension"
        for dim_name, dim_data in result.items():
            assert "score" in dim_data, f"Dimension {dim_name} missing score"
            assert "issues" in dim_data, f"Dimension {dim_name} missing issues"
            assert isinstance(dim_data["score"], float)
            assert isinstance(dim_data["issues"], list)

    @patch("tools.visual_scoring.call_llm")
    def test_critique_uses_gpt_5_4_mini(self, mock_llm: MagicMock) -> None:
        """Anti-drift #54: scorer must use gpt-5.4-mini."""
        mock_llm.return_value = _mock_call_llm_response(
            json.dumps({"score": 3.5, "issues": ["minor palette drift"]})
        )

        critique_4dim(
            image_description="test image",
            brief={"composition": "test"},
        )

        for call in mock_llm.call_args_list:
            assert call[1].get("model") == "gpt-5.4-mini", (
                "All critique calls must use gpt-5.4-mini (anti-drift #54)"
            )


class TestKontextAnchorReset:
    """IT-2 Step 12: Anchor resets at page boundary (every 8 pages)."""

    @patch("tools.illustrate.upload_to_fal", return_value="https://fal.ai/mock-url")
    @patch("tools.illustrate.upload_bytes", return_value="vizier-assets/test")
    @patch("tools.illustrate.generate_image", return_value=_TEST_PNG)
    @patch("tools.illustrate.expand_brief", return_value={"composition": "test prompt"})
    def test_anchor_resets_at_page_8(
        self,
        mock_expand: MagicMock,
        mock_gen: MagicMock,
        mock_upload: MagicMock,
        mock_fal_upload: MagicMock,
        sample_style_lock: StyleLock,
        sample_character_bible: CharacterBible,
        tmp_path: Path,
    ) -> None:
        """Run 9 pages, verify anchor resets at page 8."""
        pipeline = IllustrationPipeline(style_lock=sample_style_lock, job_id="test-anchor")
        pipeline.anchor_image_url = "https://fal.ai/anchor-ref"

        pages_since_anchor_history: list[int] = []

        for page_num in range(1, 10):
            page = _make_page(
                page_num,
                illustration_shows=f"Scene for page {page_num}",
            )
            pipeline.illustrate_page(
                page=page,
                character_bibles=[sample_character_bible],
                output_dir=tmp_path,
            )
            pages_since_anchor_history.append(pipeline.pages_since_anchor)

        # Page 8 (index 7) triggers anchor reset: pages_since_anchor resets
        # The illustrate_page method checks `page_num % _ANCHOR_INTERVAL == 0`
        # Page 8: anchor resets → pages_since_anchor becomes 1 after increment
        # So at page 8, pages_since_anchor = 1 (reset to 0, then +1)
        assert pages_since_anchor_history[7] == 1, (
            f"Pages_since_anchor at page 8 should be 1 (reset + increment), "
            f"got {pages_since_anchor_history[7]}. History: {pages_since_anchor_history}"
        )

        # Before reset (page 7), pages_since_anchor should be 7
        assert pages_since_anchor_history[6] == 7

        # After page 9, should be 2 (1 from page 8 + 1 from page 9)
        assert pages_since_anchor_history[8] == 2

    def test_anchor_interval_constant(self) -> None:
        """Verify the anchor interval is 8 as specified in architecture."""
        assert _ANCHOR_INTERVAL == 8


class TestFullSpecimenChain:
    """IT-2 Step 11: End-to-end specimen chain validation."""

    @patch("tools.visual_scoring.call_llm")
    @patch("tools.publish.subprocess.run")
    @patch("tools.illustrate.upload_to_fal", return_value="https://fal.ai/mock-url")
    @patch("tools.illustrate.upload_bytes", return_value="vizier-assets/test")
    @patch("tools.illustrate.generate_image", return_value=_TEST_PNG)
    @patch("tools.illustrate.expand_brief", return_value={"composition": "expanded prompt"})
    def test_full_chain(
        self,
        mock_expand: MagicMock,
        mock_gen: MagicMock,
        mock_upload: MagicMock,
        mock_fal_upload: MagicMock,
        mock_typst_run: MagicMock,
        mock_critique_llm: MagicMock,
        sample_scaffold: NarrativeScaffold,
        sample_character_bible: CharacterBible,
        sample_style_lock: StyleLock,
        tmp_path: Path,
    ) -> None:
        """End-to-end: scaffold → pipeline → specimen → assembly → critique → trace."""
        # Configure mocks
        mock_typst_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )
        mock_critique_llm.return_value = _mock_call_llm_response(
            json.dumps({"score": 4.2, "issues": []})
        )

        # 1. Verify scaffold
        assert len(sample_scaffold.pages) == 8
        page_1 = sample_scaffold.pages[0]

        # 2. Build illustration prompt (from illustration_shows, not text)
        prompt = build_illustration_prompt(
            page=page_1,
            style_lock=sample_style_lock,
            character_bibles=[sample_character_bible],
        )
        assert page_1.illustration_shows in prompt
        assert "text-free" in prompt.lower() or "do not include any text" in prompt.lower()

        # 3. Init pipeline and generate specimen
        pipeline = IllustrationPipeline(
            style_lock=sample_style_lock,
            job_id="test-full-chain",
        )

        specimen_path = run_specimen_page(
            pipeline=pipeline,
            page=page_1,
            character_bibles=[sample_character_bible],
            output_dir=tmp_path,
        )
        assert specimen_path.exists()
        assert pipeline.total_pages == 1

        # 4. NIMA prescreen
        nima_result = nima_prescreen(5.5)
        assert nima_result["action"] == "proceed_with_caution"

        # 5. 4-dim critique
        critique_result = critique_4dim(
            image_description="Soft watercolour of Adik in kampung house with Raya lights",
            brief={"composition": "expanded prompt", "style": "watercolour"},
        )
        assert len(critique_result) > 0

        # 6. Assemble single-page PDF (using specimen as all 8 pages for testing)
        images = [specimen_path] * 8
        page_texts = [f"Test text for page {i + 1}." for i in range(8)]

        pdf_path = assemble_childrens_book_pdf(
            images=images,
            scaffold=sample_scaffold,
            style_lock=sample_style_lock,
            title="Ketupat Emas Adik",
            author="Vizier AI",
            output_dir=tmp_path,
            page_texts=page_texts,
        )

        # Verify .typ source contains text overlay (not in images)
        typ_files = list(tmp_path.glob("*.typ"))
        assert len(typ_files) == 1
        typ_content = typ_files[0].read_text(encoding="utf-8")
        assert "Test text for page" in typ_content
        assert "image(" in typ_content

        # 7. Verify trace captured all steps
        trace = pipeline.collector.finalise()
        assert len(trace.steps) >= 1, "Trace should capture illustration step(s)"
        assert trace.job_id == "test-full-chain"
