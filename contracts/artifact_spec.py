"""ArtifactSpec and ProvisionalArtifactSpec — production contracts for Vizier.

ArtifactSpec is the fully validated specification an artifact must satisfy.
ProvisionalArtifactSpec is a less-strict version used during refinement (§9).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ArtifactFamily(StrEnum):
    """Supported artifact families (from config/artifact_taxonomy.yaml)."""

    poster = "poster"
    document = "document"
    brochure = "brochure"
    childrens_book = "childrens_book"
    ebook = "ebook"
    social_post = "social_post"
    invoice = "invoice"
    proposal = "proposal"
    company_profile = "company_profile"
    serial_fiction = "serial_fiction"
    content_calendar = "content_calendar"


class DeliveryFormat(StrEnum):
    """Supported delivery formats."""

    pdf = "pdf"
    png = "png"
    jpg = "jpg"
    epub = "epub"
    html = "html"


# ---------------------------------------------------------------------------
# Nested models
# ---------------------------------------------------------------------------


class StructuralRequirements(BaseModel):
    """Structural requirements for the artifact."""

    artifact_family: ArtifactFamily
    language: str = Field(min_length=2, max_length=5, description="ISO language code or BM/EN")
    page_count: int | None = Field(default=None, ge=1)
    dimensions: str | None = Field(default=None, description="e.g. '1080x1080', 'A4'")
    sections: list[str] | None = None


class StyleRequirements(BaseModel):
    """Style requirements for the artifact."""

    tone: str | None = Field(default=None, description="e.g. 'formal', 'casual', 'playful'")
    copy_register: str | None = Field(default=None, description="e.g. 'formal_bm', 'casual_bm'")
    brand_config_id: str | None = None
    persona_id: str | None = None
    design_system: str | None = None


class QARequirements(BaseModel):
    """Quality assurance requirements."""

    tripwire_threshold: float = Field(default=3.0, ge=1.0, le=5.0)
    max_retries: int = Field(default=2, ge=0, le=5)
    guardrails: list[str] = Field(default_factory=list)
    quality_techniques: list[str] = Field(default_factory=list)


class DeliveryRequirements(BaseModel):
    """Delivery requirements."""

    format: DeliveryFormat
    resolution_dpi: int | None = Field(default=None, ge=72)
    due_date: datetime | None = None
    recipient: str | None = None


# ---------------------------------------------------------------------------
# ArtifactSpec — fully validated production contract
# ---------------------------------------------------------------------------


class ArtifactSpec(BaseModel):
    """Fully validated artifact specification.

    This is the production contract that an artifact must satisfy.
    Created after refinement is complete and readiness gate returns 'ready'.
    Immutable once created — rework corrects execution, not spec (§9.1).
    Frozen: mutation raises ValidationError at runtime.
    """

    model_config = ConfigDict(frozen=True)

    spec_id: UUID = Field(default_factory=uuid4)
    client_id: str = Field(min_length=1)
    job_id: str | None = None
    revision: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    structural: StructuralRequirements
    style: StyleRequirements = Field(default_factory=StyleRequirements)
    qa: QARequirements = Field(default_factory=QARequirements)
    delivery: DeliveryRequirements

    objective: str = Field(min_length=1, description="What this artifact should achieve")
    context: str | None = Field(default=None, description="Additional context for production")
    model_preference: str = Field(default="gpt-5.4-mini", description="Anti-drift #54: GPT-5.4-mini Month 1-2")

    @model_validator(mode="after")
    def validate_completeness(self) -> ArtifactSpec:
        """Reject specs missing required fields."""
        if not self.structural.artifact_family:
            raise ValueError("artifact_family is required")
        if not self.structural.language:
            raise ValueError("language is required")
        if not self.objective:
            raise ValueError("objective is required")
        return self


# ---------------------------------------------------------------------------
# ProvisionalArtifactSpec — used during refinement (§9)
# ---------------------------------------------------------------------------


class ProvisionalArtifactSpec(BaseModel):
    """Less strict spec used during the refinement loop.

    Tracks confidence, completeness, and shaping viability scores.
    Promoted to ArtifactSpec via explicit promote() method when ready.
    """

    spec_id: UUID = Field(default_factory=uuid4)
    client_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    cycle: int = Field(default=0, ge=0)

    # Partial structural — family and language required, rest optional
    artifact_family: ArtifactFamily
    family_resolved: bool = Field(
        default=False,
        description="True once artifact_family has been classified, not just defaulted",
    )
    language: str = Field(min_length=2, max_length=5)
    page_count: int | None = None
    dimensions: str | None = None

    # Partial style
    tone: str | None = None
    copy_register: str | None = None
    brand_config_id: str | None = None

    # Delivery
    format: DeliveryFormat | None = None
    due_date: datetime | None = None

    # Free-form
    objective: str | None = None
    context: str | None = None
    raw_brief: str | None = Field(default=None, description="Original unstructured brief from client")

    # Scoring (0.0 - 1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    shaping_viability: float = Field(default=0.0, ge=0.0, le=1.0)

    # Missing fields analysis
    missing_critical: list[str] = Field(default_factory=list)
    missing_nice_to_have: list[str] = Field(default_factory=list)

    readiness: Literal["ready", "shapeable", "blocked"] = "shapeable"

    def promote(self) -> ArtifactSpec:
        """Promote to a full ArtifactSpec.

        Raises ValueError if not ready.
        """
        if self.readiness != "ready":
            raise ValueError(
                f"Cannot promote spec with readiness '{self.readiness}'. "
                "Must be 'ready'."
            )
        if not self.objective:
            raise ValueError("Cannot promote without an objective")
        if not self.format:
            raise ValueError("Cannot promote without a delivery format")

        return ArtifactSpec(
            spec_id=self.spec_id,
            client_id=self.client_id,
            structural=StructuralRequirements(
                artifact_family=self.artifact_family,
                language=self.language,
                page_count=self.page_count,
                dimensions=self.dimensions,
            ),
            style=StyleRequirements(
                tone=self.tone,
                copy_register=self.copy_register,
                brand_config_id=self.brand_config_id,
            ),
            delivery=DeliveryRequirements(
                format=self.format,
                due_date=self.due_date,
            ),
            objective=self.objective,
            context=self.context,
        )
