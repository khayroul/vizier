"""Publishing intelligence contracts (§42, §43.5).

CharacterBible, StoryBible, NarrativeScaffold, StyleLock, PlanningObject,
CharacterRegistry — shared contracts consumed by S15 (publishing lane).

S6 defines these. S15 consumes them. Do not redefine.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TextImageRelationship(StrEnum):
    """How text and illustration relate on a page (§42.3)."""

    symmetrical = "symmetrical"
    complementary = "complementary"
    contradictory = "contradictory"


class PageTurnEffect(StrEnum):
    """Effect of turning to this page (§42.3)."""

    continuation = "continuation"
    reveal = "reveal"
    pause = "pause"
    climax = "climax"


class TextPlacementStrategy(StrEnum):
    """Where text is placed relative to illustration (StyleLock)."""

    text_always_below = "text-always-below"
    text_on_left = "text-on-left"
    text_overlay_with_reserved_zone = "text-overlay-with-reserved-zone"


class AgeGroup(StrEnum):
    """Target age groups for children's publishing."""

    age_3_5 = "3-5"
    age_5_7 = "5-7"
    age_8_10 = "8-10"
    age_10_12 = "10-12"


# ---------------------------------------------------------------------------
# CharacterBible sub-models (§42.1)
# ---------------------------------------------------------------------------


class FaceDetails(BaseModel):
    """Facial features for character bible."""

    shape: str = Field(min_length=1)
    eyes: str = Field(min_length=1)
    nose: str = Field(min_length=1)
    mouth: str = Field(min_length=1)
    distinctive: str = Field(default="", description="Distinctive features like dimples, scars")


class HairDetails(BaseModel):
    """Hair details for character bible."""

    style: str = Field(min_length=1)
    colour: str = Field(min_length=1, description="Hex colour code")


class PhysicalDescription(BaseModel):
    """Physical description of a character (§42.1)."""

    age: int = Field(ge=0)
    ethnicity: str = Field(min_length=1)
    skin_tone: str = Field(min_length=4, description="Hex colour code, e.g. #8D6E63")
    height: str = Field(min_length=1)
    build: str = Field(min_length=1)
    face: FaceDetails
    hair: HairDetails


class ClothingVariant(BaseModel):
    """A clothing variant (school, festive, etc.)."""

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ClothingDescription(BaseModel):
    """Clothing for a character."""

    default: str = Field(min_length=1, description="Default outfit description")
    variants: list[ClothingVariant] = Field(default_factory=list)


class StyleNotes(BaseModel):
    """Art style notes for character rendering (§42.1)."""

    art_style: str = Field(min_length=1, description="e.g. 'soft watercolour, Studio Ghibli influence'")
    line_weight: str = Field(min_length=1, description="e.g. 'thin, delicate'")
    colour_palette: str = Field(min_length=1, description="e.g. 'warm earth tones, soft pastels'")
    never: list[str] = Field(default_factory=list, description="Things to never include")
    always: list[str] = Field(default_factory=list, description="Things to always include")


class ReferenceImages(BaseModel):
    """Operator-curated reference images for character consistency."""

    front_view: str | None = Field(default=None, description="Path to front view image")
    three_quarter: str | None = Field(default=None, description="Path to 3/4 view image")
    profile: str | None = Field(default=None, description="Path to profile view image")


class LoRAConfig(BaseModel):
    """Optional LoRA configuration for Tier 1 illustration consistency."""

    character_lora_url: str = Field(min_length=1)
    trigger_word: str = Field(min_length=1)
    training_images: int = Field(ge=1)
    training_cost: str = Field(default="")
    trained_at: str = Field(default="", description="ISO timestamp")


# ---------------------------------------------------------------------------
# CharacterBible (§42.1)
# ---------------------------------------------------------------------------


class CharacterBible(BaseModel):
    """Character bible for illustration consistency (§42.1).

    Characters cannot enter production without curated references.
    """

    character_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role: str = Field(min_length=1, description="protagonist, supporting, background")
    physical: PhysicalDescription
    clothing: ClothingDescription
    style_notes: StyleNotes
    reference_images: ReferenceImages = Field(default_factory=ReferenceImages)
    lora: LoRAConfig | None = None


# ---------------------------------------------------------------------------
# StoryBible (§42.2)
# ---------------------------------------------------------------------------


class SensoryDetails(BaseModel):
    """Sensory details for the story world."""

    visual: str = Field(min_length=1)
    auditory: str = Field(default="")
    olfactory: str = Field(default="")


class CulturalContext(BaseModel):
    """Cultural context for the story."""

    values: list[str] = Field(default_factory=list)
    practices: list[str] = Field(default_factory=list)
    religion: str = Field(default="")


class WorldDescription(BaseModel):
    """World description for the story bible."""

    setting: str = Field(min_length=1)
    sensory: SensoryDetails
    cultural_context: CulturalContext = Field(default_factory=CulturalContext)


class ThematicConstraints(BaseModel):
    """Thematic constraints for the story."""

    lesson: str = Field(min_length=1, description="Core lesson or theme")
    avoid: list[str] = Field(default_factory=list, description="Topics/themes to avoid")


class StoryBible(BaseModel):
    """Story bible defining the narrative world (§42.2).

    Separate from character bibles — characters inhabit the world
    the story bible defines. Immutable facts start empty and are
    captured and locked during production.
    """

    title: str = Field(min_length=1)
    target_age: AgeGroup
    language: str = Field(min_length=2, max_length=5)
    world: WorldDescription
    thematic_constraints: ThematicConstraints
    immutable_facts: list[str] = Field(
        default_factory=list,
        description="Populated during production, never contradicted",
    )
    domain_vocabulary: list[str] = Field(
        default_factory=list,
        description="Domain-specific vocabulary for this story",
    )


# ---------------------------------------------------------------------------
# NarrativeScaffold (§42.3)
# ---------------------------------------------------------------------------


class CompositionGuide(BaseModel):
    """Composition guide for an illustration (§42.3)."""

    camera: str = Field(min_length=1, description="e.g. close_up, medium_shot, wide_shot")
    character_position: str = Field(min_length=1, description="e.g. centre, left_third, right_third")
    background_detail: str = Field(min_length=1, description="minimal, medium, detailed")
    colour_temperature: str = Field(min_length=1, description="warm, cool, neutral")
    text_zone: str = Field(min_length=1, description="bottom_third, top_third, left_side, right_side")


class TypographyConstraints(BaseModel):
    """Typography constraints per age group (§42.3)."""

    min_font_size_pt: int = Field(ge=8)
    line_spacing_percent: int = Field(ge=100, description="e.g. 130 for 130%")
    max_lines_per_page: int = Field(ge=1)


class PageScaffold(BaseModel):
    """Per-page scaffolding within a NarrativeScaffold (§42.3).

    illustration_shows is the source for illustration prompts —
    NOT the page text (anti-drift #49, §42.3).
    """

    page: int = Field(ge=1)
    word_target: int = Field(ge=0)
    emotional_beat: str = Field(min_length=1)
    characters_present: list[str] = Field(default_factory=list)
    checkpoint_progress: str = Field(default="")
    text_image_relationship: TextImageRelationship
    illustration_shows: str = Field(
        min_length=1,
        description="Detailed description for illustration prompt. NOT derived from page text.",
    )
    page_turn_effect: PageTurnEffect
    composition_guide: CompositionGuide


# Age-calibrated word targets (§42.3)
AGE_WORD_TARGETS: dict[AgeGroup, tuple[int, int]] = {
    AgeGroup.age_3_5: (10, 20),
    AgeGroup.age_5_7: (20, 40),
    AgeGroup.age_8_10: (80, 120),
    AgeGroup.age_10_12: (120, 200),
}

# Age-calibrated typography (§42.3)
AGE_TYPOGRAPHY: dict[AgeGroup, TypographyConstraints] = {
    AgeGroup.age_3_5: TypographyConstraints(min_font_size_pt=20, line_spacing_percent=150, max_lines_per_page=3),
    AgeGroup.age_5_7: TypographyConstraints(min_font_size_pt=16, line_spacing_percent=140, max_lines_per_page=4),
    AgeGroup.age_8_10: TypographyConstraints(min_font_size_pt=14, line_spacing_percent=130, max_lines_per_page=8),
    AgeGroup.age_10_12: TypographyConstraints(min_font_size_pt=12, line_spacing_percent=130, max_lines_per_page=12),
}

# Arc templates by age group (§42.3)
AGE_ARC_TEMPLATES: dict[AgeGroup, str] = {
    AgeGroup.age_3_5: "discover → try → succeed",
    AgeGroup.age_5_7: "problem → attempt → fail → learn → succeed",
    AgeGroup.age_8_10: "multi-chapter arc with subplot",
    AgeGroup.age_10_12: "multiple characters, moral ambiguity",
}


class NarrativeScaffold(BaseModel):
    """Age-calibrated narrative decomposition (§42.3).

    Decomposes a story into per-page scaffolding with word targets,
    emotional beats, illustration guidance, and composition direction.
    """

    scaffold_id: UUID = Field(default_factory=uuid4)
    target_age: AgeGroup
    page_count: int = Field(ge=1)
    arc_template: str = Field(default="")
    typography: TypographyConstraints | None = None
    pages: list[PageScaffold] = Field(default_factory=list)

    @model_validator(mode="after")
    def set_defaults_from_age(self) -> NarrativeScaffold:
        """Set arc template and typography from age group if not provided."""
        if not self.arc_template:
            self.arc_template = AGE_ARC_TEMPLATES.get(self.target_age, "")
        if self.typography is None:
            self.typography = AGE_TYPOGRAPHY.get(self.target_age)
        return self

    @model_validator(mode="after")
    def validate_pages(self) -> NarrativeScaffold:
        """Validate page count matches pages list if pages are provided."""
        if self.pages and len(self.pages) != self.page_count:
            raise ValueError(
                f"page_count ({self.page_count}) does not match "
                f"number of pages ({len(self.pages)})"
            )
        return self

    @classmethod
    def decompose(
        cls,
        target_age: AgeGroup,
        page_count: int,
        pages: list[PageScaffold],
    ) -> NarrativeScaffold:
        """Create a scaffold by decomposing a story into pages.

        Args:
            target_age: Target age group.
            page_count: Number of pages.
            pages: Per-page scaffolding.

        Returns:
            A fully constructed NarrativeScaffold.
        """
        return cls(
            target_age=target_age,
            page_count=page_count,
            pages=pages,
        )


# ---------------------------------------------------------------------------
# StyleLock (§42.6 step 9)
# ---------------------------------------------------------------------------


class StyleLock(BaseModel):
    """Locked illustration parameters for visual coherence.

    Set during creative workshop step 9, inherited by derivative projects.
    Illustrations are ALWAYS text-free — text overlaid by Typst (anti-drift #49).
    """

    art_style: str = Field(min_length=1)
    palette: list[str] = Field(min_length=1, description="Colour palette as hex or named colours")
    typography: str = Field(min_length=1, description="Typography specification")
    text_placement_strategy: TextPlacementStrategy


# ---------------------------------------------------------------------------
# PlanningObject (§7.1)
# ---------------------------------------------------------------------------


class PlanningSection(BaseModel):
    """A section within a planning object (chapter, page, scene)."""

    section_id: str = Field(min_length=1)
    section_type: str = Field(description="chapter, page, scene, section")
    title: str = Field(default="")
    order: int = Field(ge=0)
    scaffold_page: int | None = Field(
        default=None,
        ge=1,
        description="Link to NarrativeScaffold page number",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="IDs of sections that must be produced before this one",
    )
    status: Literal["pending", "in_progress", "completed", "blocked"] = "pending"


class PlanningObject(BaseModel):
    """Compound artifact decomposition (§7.1).

    Breaks a compound artifact (book, ebook, serial) into producible sections.
    Connected to NarrativeScaffold — each section can reference a scaffold page.
    """

    planning_id: UUID = Field(default_factory=uuid4)
    artifact_family: str = Field(min_length=1)
    title: str = Field(min_length=1)
    sections: list[PlanningSection] = Field(min_length=1)
    scaffold_id: UUID | None = Field(
        default=None,
        description="Reference to the NarrativeScaffold this planning object uses",
    )

    @property
    def total_sections(self) -> int:
        return len(self.sections)

    @property
    def completed_sections(self) -> int:
        return sum(1 for section in self.sections if section.status == "completed")


# ---------------------------------------------------------------------------
# CharacterRegistry (§7.1)
# ---------------------------------------------------------------------------


class CharacterRegistry(BaseModel):
    """Tracks all characters across a project for consistency.

    Used to ensure character references are valid and consistent
    across all pages/chapters in a publishing project.
    """

    project_id: str = Field(min_length=1)
    characters: dict[str, CharacterBible] = Field(
        default_factory=dict,
        description="Keyed by character_id",
    )

    def register(self, character: CharacterBible) -> None:
        """Register or update a character."""
        self.characters[character.character_id] = character

    def get(self, character_id: str) -> CharacterBible | None:
        """Get a character by ID."""
        return self.characters.get(character_id)

    def validate_references(self, character_ids: list[str]) -> list[str]:
        """Check that all referenced character IDs exist in the registry.

        Returns list of missing character IDs.
        """
        return [cid for cid in character_ids if cid not in self.characters]
