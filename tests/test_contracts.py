"""Tests for S6 governance contracts.

Covers all exit criteria:
- ArtifactSpec validates and rejects incomplete specs
- ReadinessGate returns correct status for 3 test inputs (ready, shapeable, blocked)
- TraceCollector captures step name, tokens, cost, duration
- StepTrace proof field accepts dict
- RollingContext initialises, accepts updates, compresses tiers
- CharacterBible validates against sample character data
- StoryBible validates against sample story bible data
- NarrativeScaffold decomposes 8-page children's book age 5-7
- StyleLock includes text_placement_strategy
- PlanningObject connected to NarrativeScaffold
"""

from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from contracts.artifact_spec import (
    ArtifactFamily,
    ArtifactSpec,
    DeliveryFormat,
    DeliveryRequirements,
    ProvisionalArtifactSpec,
    StructuralRequirements,
)
from contracts.context import (
    Checkpoint,
    RollingContext,
    TrackedEntity,
)
from contracts.policy import PolicyAction, PolicyDecision
from contracts.publishing import (
    AGE_WORD_TARGETS,
    AgeGroup,
    CharacterBible,
    CharacterRegistry,
    ClothingDescription,
    ClothingVariant,
    CompositionGuide,
    FaceDetails,
    HairDetails,
    NarrativeScaffold,
    PageScaffold,
    PageTurnEffect,
    PhysicalDescription,
    PlanningObject,
    PlanningSection,
    ReferenceImages,
    StyleLock,
    StyleNotes,
    StoryBible,
    TextImageRelationship,
    TextPlacementStrategy,
    ThematicConstraints,
    WorldDescription,
    SensoryDetails,
    CulturalContext,
)
from contracts.readiness import (
    RefinementLimits,
    evaluate_readiness,
)
from contracts.routing import RoutingResult
from contracts.trace import StepTrace, TraceCollector


# ===================================================================
# ArtifactSpec
# ===================================================================


class TestArtifactSpec:
    """ArtifactSpec validates and rejects incomplete specs."""

    def test_valid_spec(self) -> None:
        spec = ArtifactSpec(
            client_id="client-001",
            structural=StructuralRequirements(
                artifact_family=ArtifactFamily.poster,
                language="BM",
                dimensions="1080x1080",
            ),
            delivery=DeliveryRequirements(format=DeliveryFormat.png),
            objective="Create a Raya promotional poster",
        )
        assert spec.client_id == "client-001"
        assert spec.structural.artifact_family == ArtifactFamily.poster
        assert spec.model_preference == "gpt-5.4-mini"

    def test_rejects_missing_objective(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactSpec(
                client_id="client-001",
                structural=StructuralRequirements(
                    artifact_family=ArtifactFamily.poster,
                    language="BM",
                ),
                delivery=DeliveryRequirements(format=DeliveryFormat.png),
                objective="",  # empty string fails min_length=1
            )

    def test_rejects_missing_client_id(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactSpec(
                client_id="",  # empty string fails min_length=1
                structural=StructuralRequirements(
                    artifact_family=ArtifactFamily.poster,
                    language="BM",
                ),
                delivery=DeliveryRequirements(format=DeliveryFormat.png),
                objective="Test objective",
            )

    def test_rejects_missing_language(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactSpec(
                client_id="client-001",
                structural=StructuralRequirements(
                    artifact_family=ArtifactFamily.poster,
                    language="",  # empty fails min_length=2
                ),
                delivery=DeliveryRequirements(format=DeliveryFormat.png),
                objective="Test objective",
            )

    def test_revision_starts_at_1(self) -> None:
        spec = ArtifactSpec(
            client_id="client-001",
            structural=StructuralRequirements(
                artifact_family=ArtifactFamily.document,
                language="EN",
            ),
            delivery=DeliveryRequirements(format=DeliveryFormat.pdf),
            objective="Create a report",
        )
        assert spec.revision == 1


class TestProvisionalArtifactSpec:
    """ProvisionalArtifactSpec and promotion."""

    def test_promote_when_ready(self) -> None:
        provisional = ProvisionalArtifactSpec(
            client_id="client-001",
            artifact_family=ArtifactFamily.poster,
            language="BM",
            objective="Create a poster",
            format=DeliveryFormat.png,
            readiness="ready",
        )
        spec = provisional.promote()
        assert isinstance(spec, ArtifactSpec)
        assert spec.objective == "Create a poster"

    def test_promote_fails_when_not_ready(self) -> None:
        provisional = ProvisionalArtifactSpec(
            client_id="client-001",
            artifact_family=ArtifactFamily.poster,
            language="BM",
            readiness="shapeable",
        )
        with pytest.raises(ValueError, match="Cannot promote"):
            provisional.promote()

    def test_promote_fails_without_objective(self) -> None:
        provisional = ProvisionalArtifactSpec(
            client_id="client-001",
            artifact_family=ArtifactFamily.poster,
            language="BM",
            format=DeliveryFormat.png,
            readiness="ready",
        )
        with pytest.raises(ValueError, match="Cannot promote without an objective"):
            provisional.promote()


# ===================================================================
# ReadinessGate
# ===================================================================


class TestReadinessGate:
    """ReadinessGate returns correct status for 3 test inputs."""

    def test_ready(self) -> None:
        """Spec with all fields filled returns 'ready'."""
        spec = ProvisionalArtifactSpec(
            client_id="client-001",
            artifact_family=ArtifactFamily.poster,
            language="BM",
            objective="Create a promotional poster",
            format=DeliveryFormat.png,
            tone="casual",
            copy_register="casual_bm",
            dimensions="1080x1080",
            page_count=1,
            brand_config_id="brand-001",
        )
        result = evaluate_readiness(spec)
        assert result.status == "ready"
        assert result.completeness >= 0.8
        assert len(result.missing_critical) == 0

    def test_shapeable(self) -> None:
        """Spec with some fields missing returns 'shapeable'."""
        spec = ProvisionalArtifactSpec(
            client_id="client-001",
            artifact_family=ArtifactFamily.brochure,
            language="EN",
            objective="Create a brochure",
            raw_brief="We need a brochure for our product launch",
        )
        result = evaluate_readiness(spec)
        assert result.status == "shapeable"
        assert len(result.missing_critical) > 0

    def test_blocked(self) -> None:
        """Spec with no objective and no raw_brief returns 'blocked'."""
        spec = ProvisionalArtifactSpec(
            client_id="client-001",
            artifact_family=ArtifactFamily.poster,
            language="BM",
        )
        result = evaluate_readiness(spec)
        assert result.status == "blocked"
        assert "objective" in result.missing_critical

    def test_blocked_by_max_cycles(self) -> None:
        """Spec at max cycles with critical fields missing returns 'blocked'."""
        limits = RefinementLimits(max_cycles=4)
        spec = ProvisionalArtifactSpec(
            client_id="client-001",
            artifact_family=ArtifactFamily.poster,
            language="BM",
            cycle=4,
            raw_brief="Some brief",
        )
        result = evaluate_readiness(spec, limits)
        assert result.status == "blocked"


# ===================================================================
# TraceCollector
# ===================================================================


class TestTraceCollector:
    """TraceCollector captures step name, tokens, cost, duration."""

    def test_captures_step_trace(self) -> None:
        collector = TraceCollector(job_id="job-123")

        with collector.step("generate_copy") as trace:
            trace.input_tokens = 500
            trace.output_tokens = 200
            trace.cost_usd = 0.001
            trace.model = "gpt-5.4-mini"
            time.sleep(0.01)

        assert len(collector.steps) == 1
        step = collector.steps[0]
        assert step.step_name == "generate_copy"
        assert step.input_tokens == 500
        assert step.output_tokens == 200
        assert step.cost_usd == 0.001
        assert step.duration_ms > 0

    def test_multiple_steps(self) -> None:
        collector = TraceCollector(job_id="job-456")

        with collector.step("research") as trace:
            trace.input_tokens = 100
            trace.cost_usd = 0.0001

        with collector.step("generate") as trace:
            trace.input_tokens = 500
            trace.output_tokens = 300
            trace.cost_usd = 0.002

        production_trace = collector.finalise()
        assert len(production_trace.steps) == 2
        assert production_trace.total_cost_usd == pytest.approx(0.0021)
        assert production_trace.total_input_tokens == 600
        assert production_trace.job_id == "job-456"
        assert production_trace.completed_at is not None

    def test_captures_errors(self) -> None:
        collector = TraceCollector()
        with pytest.raises(RuntimeError, match="test error"):
            with collector.step("failing_step") as trace:
                trace.input_tokens = 50
                raise RuntimeError("test error")

        assert len(collector.steps) == 1
        assert collector.steps[0].error == "test error"
        assert collector.steps[0].duration_ms > 0

    def test_serialises_to_jsonb(self) -> None:
        collector = TraceCollector(job_id="job-789")
        with collector.step("qa_check") as trace:
            trace.cost_usd = 0.0005

        production_trace = collector.finalise()
        jsonb = production_trace.to_jsonb()
        assert isinstance(jsonb, dict)
        assert jsonb["job_id"] == "job-789"
        assert isinstance(jsonb["steps"], list)
        assert len(jsonb["steps"]) == 1


# ===================================================================
# StepTrace proof field
# ===================================================================


class TestStepTraceProof:
    """StepTrace proof field accepts dict and serialises to JSONB-compatible dict."""

    def test_proof_accepts_dict(self) -> None:
        trace = StepTrace(
            step_name="quality_check",
            proof={"nima_score": 6.8, "brand_voice_match": 0.92},
        )
        assert trace.proof is not None
        assert trace.proof["nima_score"] == 6.8
        assert trace.proof["brand_voice_match"] == 0.92

    def test_proof_none_by_default(self) -> None:
        trace = StepTrace(step_name="generate")
        assert trace.proof is None

    def test_proof_serialises_to_jsonb(self) -> None:
        trace = StepTrace(
            step_name="guardrail",
            proof={"claim_verified": True, "score": 4.2, "note": "passed"},
        )
        jsonb = trace.to_jsonb()
        assert isinstance(jsonb, dict)
        assert jsonb["proof"]["claim_verified"] is True
        assert jsonb["proof"]["score"] == 4.2

    def test_proof_with_none_values(self) -> None:
        trace = StepTrace(
            step_name="check",
            proof={"score": 3.5, "override": None},
        )
        assert trace.proof is not None
        assert trace.proof["override"] is None


# ===================================================================
# RollingContext
# ===================================================================


class TestRollingContext:
    """RollingContext initialises, accepts updates, compresses tiers."""

    def test_initialises_with_config(self) -> None:
        ctx = RollingContext(
            context_type="narrative",
            recent_window=3,
            medium_scope="arc",
            compression_model="gpt-5.4-mini",
        )
        assert ctx.context_type == "narrative"
        assert ctx.recent_window == 3
        assert len(ctx.recent) == 0
        assert len(ctx.medium) == 0
        assert len(ctx.long_term) == 0

    def test_update_adds_to_recent(self) -> None:
        ctx = RollingContext(
            context_type="narrative",
            recent_window=3,
        )
        ctx.update("Page 1: Ahmad discovers batik tools")
        assert len(ctx.recent) == 1
        assert ctx.current_step == 1

    def test_update_promotes_to_medium(self) -> None:
        ctx = RollingContext(
            context_type="campaign",
            recent_window=2,
        )
        ctx.update("Post 1: Product launch announcement")
        ctx.update("Post 2: Feature highlight")
        ctx.update("Post 3: Customer testimonial")
        # recent_window=2, so first entry should be promoted to medium
        assert len(ctx.recent) == 2
        assert len(ctx.medium) == 1
        assert ctx.current_step == 3

    def test_compress_moves_medium_to_long_term(self) -> None:
        ctx = RollingContext(
            context_type="document",
            recent_window=1,
        )
        ctx.update("Section 1")
        ctx.update("Section 2")
        ctx.update("Section 3")
        # medium should have entries from promotion
        assert len(ctx.medium) == 2
        ctx.compress()
        assert len(ctx.medium) == 0
        assert len(ctx.long_term) == 1
        assert "[compressed]" in ctx.long_term[0].content

    def test_entity_tracking(self) -> None:
        ctx = RollingContext(context_type="narrative", recent_window=5)
        entity = TrackedEntity(
            entity_id="ahmad",
            entity_type="character",
            name="Ahmad",
            state={"mood": "curious"},
            introduced_at=0,
            last_updated_at=0,
        )
        ctx.add_entity(entity)
        assert len(ctx.entities) == 1
        # Update the same entity
        updated = TrackedEntity(
            entity_id="ahmad",
            entity_type="character",
            name="Ahmad",
            state={"mood": "frustrated"},
            introduced_at=0,
            last_updated_at=2,
        )
        ctx.add_entity(updated)
        assert len(ctx.entities) == 1
        assert ctx.entities[0].state["mood"] == "frustrated"

    def test_immutable_facts(self) -> None:
        ctx = RollingContext(context_type="narrative", recent_window=5)
        ctx.add_immutable_fact("Ahmad is 8 years old", source="character_bible")
        assert len(ctx.immutable_facts) == 1
        assert ctx.immutable_facts[0].fact == "Ahmad is 8 years old"

    def test_get_context_window(self) -> None:
        ctx = RollingContext(context_type="narrative", recent_window=2)
        ctx.update("Page 1")
        ctx.update("Page 2")
        ctx.add_immutable_fact("Test fact")
        ctx.checkpoints.append(
            Checkpoint(description="Ahmad succeeds", target_step=7)
        )
        window = ctx.get_context_window()
        assert "recent" in window
        assert "medium" in window
        assert "long_term" in window
        assert "entities" in window
        assert "immutable_facts" in window
        assert "checkpoints" in window
        assert len(window["recent"]) == 2


# ===================================================================
# CharacterBible
# ===================================================================


class TestCharacterBible:
    """CharacterBible validates against sample character data."""

    @pytest.fixture()
    def sample_character(self) -> CharacterBible:
        return CharacterBible(
            character_id="ahmad",
            name="Ahmad",
            role="protagonist",
            physical=PhysicalDescription(
                age=8,
                ethnicity="Malay",
                skin_tone="#8D6E63",
                height="120cm, slightly short for age",
                build="slim but not skinny",
                face=FaceDetails(
                    shape="round",
                    eyes="large, dark brown, curious expression",
                    nose="small, button",
                    mouth="wide smile, gap between front teeth",
                    distinctive="dimple on left cheek",
                ),
                hair=HairDetails(
                    style="short, straight, parted left",
                    colour="#1A1A1A",
                ),
            ),
            clothing=ClothingDescription(
                default="blue baju Melayu with gold buttons, white seluar",
                variants=[
                    ClothingVariant(name="school", description="white shirt, dark blue shorts, black shoes"),
                    ClothingVariant(name="festive", description="green baju Melayu with songkok"),
                ],
            ),
            style_notes=StyleNotes(
                art_style="soft watercolour, Studio Ghibli influence",
                line_weight="thin, delicate",
                colour_palette="warm earth tones, soft pastels",
                never=["realistic/photographic", "sharp lines", "dark shadows"],
                always=["gentle lighting", "warm undertones"],
            ),
            reference_images=ReferenceImages(
                front_view="assets/characters/ahmad_front.png",
                three_quarter="assets/characters/ahmad_3q.png",
                profile="assets/characters/ahmad_profile.png",
            ),
        )

    def test_validates_sample_character(self, sample_character: CharacterBible) -> None:
        assert sample_character.character_id == "ahmad"
        assert sample_character.name == "Ahmad"
        assert sample_character.physical.age == 8
        assert sample_character.physical.skin_tone == "#8D6E63"
        assert sample_character.physical.face.distinctive == "dimple on left cheek"
        assert len(sample_character.clothing.variants) == 2
        assert len(sample_character.style_notes.never) == 3

    def test_rejects_missing_name(self) -> None:
        with pytest.raises(ValidationError):
            CharacterBible(
                character_id="test",
                name="",  # fails min_length=1
                role="protagonist",
                physical=PhysicalDescription(
                    age=8,
                    ethnicity="Malay",
                    skin_tone="#8D6E63",
                    height="120cm",
                    build="slim",
                    face=FaceDetails(shape="round", eyes="brown", nose="small", mouth="small"),
                    hair=HairDetails(style="short", colour="#000"),
                ),
                clothing=ClothingDescription(default="outfit"),
                style_notes=StyleNotes(
                    art_style="watercolour",
                    line_weight="thin",
                    colour_palette="warm",
                ),
            )

    def test_optional_lora(self, sample_character: CharacterBible) -> None:
        assert sample_character.lora is None


# ===================================================================
# StoryBible
# ===================================================================


class TestStoryBible:
    """StoryBible validates against sample story bible data."""

    @pytest.fixture()
    def sample_story_bible(self) -> StoryBible:
        return StoryBible(
            title="Ahmad Belajar Membatik",
            target_age=AgeGroup.age_5_7,
            language="BM",
            world=WorldDescription(
                setting="Kampung di Terengganu, masa kini",
                sensory=SensoryDetails(
                    visual="Rumah kayu, halaman luas, pokok kelapa, kain batik digantung kering",
                    auditory="Bunyi ayam berkokok, angin laut, suara nenek bercerita",
                    olfactory="Bau lilin panas, pewarna batik, nasi lemak pagi",
                ),
                cultural_context=CulturalContext(
                    values=["kesabaran", "hormat orang tua", "warisan budaya"],
                    practices=["batik-making process", "kampung community life"],
                    religion="Islamic context — natural, not preachy",
                ),
            ),
            thematic_constraints=ThematicConstraints(
                lesson="Patience and respecting tradition lead to beautiful results",
                avoid=["violence", "fear", "disrespect to elders", "modern technology focus"],
            ),
        )

    def test_validates_sample_bible(self, sample_story_bible: StoryBible) -> None:
        assert sample_story_bible.title == "Ahmad Belajar Membatik"
        assert sample_story_bible.target_age == AgeGroup.age_5_7
        assert sample_story_bible.language == "BM"
        assert sample_story_bible.world.setting == "Kampung di Terengganu, masa kini"
        assert len(sample_story_bible.world.cultural_context.values) == 3
        assert len(sample_story_bible.thematic_constraints.avoid) == 4

    def test_immutable_facts_start_empty(self, sample_story_bible: StoryBible) -> None:
        assert sample_story_bible.immutable_facts == []

    def test_rejects_missing_title(self) -> None:
        with pytest.raises(ValidationError):
            StoryBible(
                title="",  # fails min_length=1
                target_age=AgeGroup.age_5_7,
                language="BM",
                world=WorldDescription(
                    setting="Test",
                    sensory=SensoryDetails(visual="Test"),
                ),
                thematic_constraints=ThematicConstraints(lesson="Test"),
            )


# ===================================================================
# NarrativeScaffold
# ===================================================================


class TestNarrativeScaffold:
    """NarrativeScaffold decomposes 8-page children's book age 5-7."""

    @pytest.fixture()
    def eight_page_scaffold(self) -> NarrativeScaffold:
        """Create an 8-page scaffold for age 5-7."""
        word_min, word_max = AGE_WORD_TARGETS[AgeGroup.age_5_7]  # 20-40
        word_mid = (word_min + word_max) // 2

        pages = [
            PageScaffold(
                page=1,
                word_target=word_mid,
                emotional_beat="curiosity",
                characters_present=["ahmad"],
                checkpoint_progress="Ahmad arrives at nenek's house",
                text_image_relationship=TextImageRelationship.symmetrical,
                illustration_shows=(
                    "Ahmad's small figure approaching a traditional kampung house. "
                    "Colourful batik cloths hang on a line in the yard. "
                    "Nenek waves from the doorway."
                ),
                page_turn_effect=PageTurnEffect.continuation,
                composition_guide=CompositionGuide(
                    camera="wide_shot",
                    character_position="centre",
                    background_detail="detailed",
                    colour_temperature="warm",
                    text_zone="bottom_third",
                ),
            ),
            PageScaffold(
                page=2,
                word_target=word_mid,
                emotional_beat="wonder",
                characters_present=["ahmad", "nenek"],
                checkpoint_progress="Ahmad sees batik tools for the first time",
                text_image_relationship=TextImageRelationship.complementary,
                illustration_shows=(
                    "Close-up of batik tools laid out on a wooden table: "
                    "canting, wax pot, colourful dyes. Ahmad's eyes wide."
                ),
                page_turn_effect=PageTurnEffect.continuation,
                composition_guide=CompositionGuide(
                    camera="close_up",
                    character_position="left_third",
                    background_detail="minimal",
                    colour_temperature="warm",
                    text_zone="bottom_third",
                ),
            ),
            PageScaffold(
                page=3,
                word_target=word_mid,
                emotional_beat="frustration",
                characters_present=["ahmad", "nenek"],
                checkpoint_progress="Ahmad's first failed attempt — wax drips",
                text_image_relationship=TextImageRelationship.complementary,
                illustration_shows=(
                    "Ahmad's small hands gripping the canting too tightly, "
                    "wax dripping onto the wrong part of the white fabric. "
                    "His face scrunched in frustration."
                ),
                page_turn_effect=PageTurnEffect.continuation,
                composition_guide=CompositionGuide(
                    camera="close_up",
                    character_position="centre",
                    background_detail="medium",
                    colour_temperature="cool",
                    text_zone="bottom_third",
                ),
            ),
            PageScaffold(
                page=4,
                word_target=word_mid,
                emotional_beat="sadness",
                characters_present=["ahmad"],
                checkpoint_progress="Ahmad considers giving up",
                text_image_relationship=TextImageRelationship.complementary,
                illustration_shows=(
                    "Ahmad sitting alone on the porch steps, "
                    "chin on hands, staring at a perfectly patterned batik "
                    "cloth drying nearby — the contrast of failure and mastery."
                ),
                page_turn_effect=PageTurnEffect.pause,
                composition_guide=CompositionGuide(
                    camera="medium_shot",
                    character_position="right_third",
                    background_detail="medium",
                    colour_temperature="cool",
                    text_zone="bottom_third",
                ),
            ),
            PageScaffold(
                page=5,
                word_target=word_mid,
                emotional_beat="encouragement",
                characters_present=["ahmad", "nenek"],
                checkpoint_progress="Nenek teaches patience",
                text_image_relationship=TextImageRelationship.complementary,
                illustration_shows=(
                    "Nenek's weathered hands gently guiding Ahmad's "
                    "smaller hands on the canting. Both smiling. "
                    "Warm golden light from a window."
                ),
                page_turn_effect=PageTurnEffect.reveal,
                composition_guide=CompositionGuide(
                    camera="close_up",
                    character_position="centre",
                    background_detail="minimal",
                    colour_temperature="warm",
                    text_zone="bottom_third",
                ),
            ),
            PageScaffold(
                page=6,
                word_target=word_mid,
                emotional_beat="determination",
                characters_present=["ahmad"],
                checkpoint_progress="Ahmad tries again with patience",
                text_image_relationship=TextImageRelationship.complementary,
                illustration_shows=(
                    "Ahmad concentrating, tongue out slightly, "
                    "carefully drawing a simple flower pattern. "
                    "The wax line is wobbly but complete."
                ),
                page_turn_effect=PageTurnEffect.continuation,
                composition_guide=CompositionGuide(
                    camera="close_up",
                    character_position="centre",
                    background_detail="minimal",
                    colour_temperature="warm",
                    text_zone="bottom_third",
                ),
            ),
            PageScaffold(
                page=7,
                word_target=word_mid,
                emotional_beat="joy",
                characters_present=["ahmad", "nenek"],
                checkpoint_progress="Ahmad succeeds — his first batik piece",
                text_image_relationship=TextImageRelationship.symmetrical,
                illustration_shows=(
                    "Ahmad holding up a small square of fabric with a "
                    "simple but recognisable flower pattern in bright colours. "
                    "Nenek clapping, beaming with pride."
                ),
                page_turn_effect=PageTurnEffect.climax,
                composition_guide=CompositionGuide(
                    camera="medium_shot",
                    character_position="centre",
                    background_detail="medium",
                    colour_temperature="warm",
                    text_zone="bottom_third",
                ),
            ),
            PageScaffold(
                page=8,
                word_target=word_mid,
                emotional_beat="pride",
                characters_present=["ahmad", "nenek"],
                checkpoint_progress="Ahmad's batik hangs alongside nenek's",
                text_image_relationship=TextImageRelationship.complementary,
                illustration_shows=(
                    "Wide shot: Ahmad's small batik cloth hanging on the line "
                    "next to nenek's large, intricate piece. Both blowing in "
                    "the breeze. Ahmad and nenek holding hands, backs to viewer."
                ),
                page_turn_effect=PageTurnEffect.pause,
                composition_guide=CompositionGuide(
                    camera="wide_shot",
                    character_position="centre",
                    background_detail="detailed",
                    colour_temperature="warm",
                    text_zone="bottom_third",
                ),
            ),
        ]

        return NarrativeScaffold.decompose(
            target_age=AgeGroup.age_5_7,
            page_count=8,
            pages=pages,
        )

    def test_has_8_pages(self, eight_page_scaffold: NarrativeScaffold) -> None:
        assert eight_page_scaffold.page_count == 8
        assert len(eight_page_scaffold.pages) == 8

    def test_age_appropriate_word_targets(self, eight_page_scaffold: NarrativeScaffold) -> None:
        word_min, word_max = AGE_WORD_TARGETS[AgeGroup.age_5_7]
        for page in eight_page_scaffold.pages:
            assert word_min <= page.word_target <= word_max

    def test_all_pages_have_text_image_relationship(self, eight_page_scaffold: NarrativeScaffold) -> None:
        for page in eight_page_scaffold.pages:
            assert page.text_image_relationship in TextImageRelationship

    def test_all_pages_have_illustration_shows(self, eight_page_scaffold: NarrativeScaffold) -> None:
        for page in eight_page_scaffold.pages:
            assert len(page.illustration_shows) > 0

    def test_all_pages_have_page_turn_effect(self, eight_page_scaffold: NarrativeScaffold) -> None:
        for page in eight_page_scaffold.pages:
            assert page.page_turn_effect in PageTurnEffect

    def test_all_pages_have_composition_guide(self, eight_page_scaffold: NarrativeScaffold) -> None:
        for page in eight_page_scaffold.pages:
            guide = page.composition_guide
            assert guide.camera
            assert guide.character_position
            assert guide.background_detail
            assert guide.colour_temperature
            assert guide.text_zone

    def test_arc_template_set(self, eight_page_scaffold: NarrativeScaffold) -> None:
        assert "problem" in eight_page_scaffold.arc_template
        assert "succeed" in eight_page_scaffold.arc_template

    def test_typography_constraints_set(self, eight_page_scaffold: NarrativeScaffold) -> None:
        assert eight_page_scaffold.typography is not None
        assert eight_page_scaffold.typography.min_font_size_pt == 16
        assert eight_page_scaffold.typography.line_spacing_percent == 140
        assert eight_page_scaffold.typography.max_lines_per_page == 4

    def test_page_count_mismatch_rejected(self) -> None:
        """Scaffold rejects if page_count doesn't match pages list."""
        with pytest.raises(ValidationError, match="page_count"):
            NarrativeScaffold(
                target_age=AgeGroup.age_5_7,
                page_count=3,
                pages=[
                    PageScaffold(
                        page=1,
                        word_target=30,
                        emotional_beat="joy",
                        text_image_relationship=TextImageRelationship.symmetrical,
                        illustration_shows="A happy scene",
                        page_turn_effect=PageTurnEffect.continuation,
                        composition_guide=CompositionGuide(
                            camera="wide",
                            character_position="centre",
                            background_detail="medium",
                            colour_temperature="warm",
                            text_zone="bottom",
                        ),
                    ),
                ],
            )


# ===================================================================
# StyleLock
# ===================================================================


class TestStyleLock:
    """StyleLock includes text_placement_strategy field."""

    def test_includes_text_placement_strategy(self) -> None:
        lock = StyleLock(
            art_style="soft watercolour, Studio Ghibli influence",
            palette=["#8D6E63", "#FFE0B2", "#4CAF50"],
            typography="Nunito 16pt, warm tones",
            text_placement_strategy=TextPlacementStrategy.text_always_below,
        )
        assert lock.text_placement_strategy == TextPlacementStrategy.text_always_below

    def test_all_placement_strategies(self) -> None:
        for strategy in TextPlacementStrategy:
            lock = StyleLock(
                art_style="test",
                palette=["#000"],
                typography="test",
                text_placement_strategy=strategy,
            )
            assert lock.text_placement_strategy == strategy


# ===================================================================
# PlanningObject
# ===================================================================


class TestPlanningObject:
    """PlanningObject connected to NarrativeScaffold."""

    def test_connected_to_scaffold(self) -> None:
        scaffold = NarrativeScaffold(
            target_age=AgeGroup.age_5_7,
            page_count=2,
            pages=[
                PageScaffold(
                    page=1,
                    word_target=30,
                    emotional_beat="curiosity",
                    text_image_relationship=TextImageRelationship.symmetrical,
                    illustration_shows="A scene of wonder",
                    page_turn_effect=PageTurnEffect.continuation,
                    composition_guide=CompositionGuide(
                        camera="wide_shot",
                        character_position="centre",
                        background_detail="detailed",
                        colour_temperature="warm",
                        text_zone="bottom_third",
                    ),
                ),
                PageScaffold(
                    page=2,
                    word_target=30,
                    emotional_beat="joy",
                    text_image_relationship=TextImageRelationship.complementary,
                    illustration_shows="A joyful conclusion",
                    page_turn_effect=PageTurnEffect.climax,
                    composition_guide=CompositionGuide(
                        camera="medium_shot",
                        character_position="centre",
                        background_detail="medium",
                        colour_temperature="warm",
                        text_zone="bottom_third",
                    ),
                ),
            ],
        )

        planning = PlanningObject(
            artifact_family="childrens_book",
            title="Ahmad Belajar Membatik",
            scaffold_id=scaffold.scaffold_id,
            sections=[
                PlanningSection(
                    section_id="page-1",
                    section_type="page",
                    title="Arriving at Nenek's",
                    order=0,
                    scaffold_page=1,
                ),
                PlanningSection(
                    section_id="page-2",
                    section_type="page",
                    title="The Conclusion",
                    order=1,
                    scaffold_page=2,
                ),
            ],
        )
        assert planning.scaffold_id == scaffold.scaffold_id
        assert planning.total_sections == 2
        assert planning.completed_sections == 0

    def test_section_progress(self) -> None:
        planning = PlanningObject(
            artifact_family="ebook",
            title="Test Book",
            sections=[
                PlanningSection(section_id="ch1", section_type="chapter", order=0, status="completed"),
                PlanningSection(section_id="ch2", section_type="chapter", order=1, status="in_progress"),
                PlanningSection(section_id="ch3", section_type="chapter", order=2, status="pending"),
            ],
        )
        assert planning.total_sections == 3
        assert planning.completed_sections == 1


# ===================================================================
# PolicyDecision
# ===================================================================


class TestPolicyDecision:
    """PolicyDecision basic validation."""

    def test_all_actions(self) -> None:
        for action in PolicyAction:
            decision = PolicyDecision(
                action=action,
                reason=f"Test reason for {action}",
                gate="budget",
            )
            assert decision.action == action

    def test_constraints(self) -> None:
        decision = PolicyDecision(
            action=PolicyAction.degrade,
            reason="Budget exceeded",
            gate="cost",
            constraints={"max_retries": 1, "skip_guardrails": True},
        )
        assert decision.constraints["max_retries"] == 1


# ===================================================================
# RoutingResult
# ===================================================================


class TestRoutingResult:
    """RoutingResult stub validation."""

    def test_default_model(self) -> None:
        result = RoutingResult(workflow="poster_production")
        assert result.model_preference == "gpt-5.4-mini"

    def test_fast_path(self) -> None:
        result = RoutingResult(
            workflow="poster_production",
            fast_path=True,
            reason="Matched poster fast-path pattern",
        )
        assert result.fast_path is True


# ===================================================================
# CharacterRegistry
# ===================================================================


class TestCharacterRegistry:
    """CharacterRegistry tracks characters across a project."""

    def test_register_and_get(self) -> None:
        registry = CharacterRegistry(project_id="proj-001")
        char = CharacterBible(
            character_id="ahmad",
            name="Ahmad",
            role="protagonist",
            physical=PhysicalDescription(
                age=8,
                ethnicity="Malay",
                skin_tone="#8D6E63",
                height="120cm",
                build="slim",
                face=FaceDetails(shape="round", eyes="brown", nose="small", mouth="smile"),
                hair=HairDetails(style="short", colour="#1A1A1A"),
            ),
            clothing=ClothingDescription(default="baju Melayu"),
            style_notes=StyleNotes(art_style="watercolour", line_weight="thin", colour_palette="warm"),
        )
        registry.register(char)
        assert registry.get("ahmad") is not None
        assert registry.get("nonexistent") is None

    def test_validate_references(self) -> None:
        registry = CharacterRegistry(project_id="proj-001")
        char = CharacterBible(
            character_id="ahmad",
            name="Ahmad",
            role="protagonist",
            physical=PhysicalDescription(
                age=8,
                ethnicity="Malay",
                skin_tone="#8D6E63",
                height="120cm",
                build="slim",
                face=FaceDetails(shape="round", eyes="brown", nose="small", mouth="smile"),
                hair=HairDetails(style="short", colour="#1A1A1A"),
            ),
            clothing=ClothingDescription(default="baju Melayu"),
            style_notes=StyleNotes(art_style="watercolour", line_weight="thin", colour_palette="warm"),
        )
        registry.register(char)
        missing = registry.validate_references(["ahmad", "nenek"])
        assert missing == ["nenek"]
