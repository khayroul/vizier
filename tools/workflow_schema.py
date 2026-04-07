"""WorkflowPack YAML schema — Pydantic models for workflow definitions (§10).

Validates all 16 workflow YAML files. Enforces model lock (anti-drift #54):
every model_preference entry must be gpt-5.4-mini during Month 1-2.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class StageDefinition(BaseModel):
    """A single stage in a workflow pipeline."""

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    tools: list[str] = Field(default_factory=list)
    knowledge: list[str] = Field(default_factory=list)
    action: str = Field(min_length=1)
    section_tripwire: bool = False


class TripwireConfig(BaseModel):
    """Tripwire quality gate configuration (§37.1)."""

    enabled: bool = True
    scorer_model: str = Field(default="gpt-5.4-mini")
    scorer_fallback: str = Field(default="gpt-5.4-mini")
    latency_threshold_ms: int = Field(default=5000, gt=0)
    threshold: float = Field(default=3.0, ge=1.0, le=5.0)
    max_retries: int = Field(default=2, ge=0, le=5)
    feedback_template: str = Field(default="")


class GuardrailDefinition(BaseModel):
    """Parallel guardrail subagent definition (§37.2)."""

    name: str = Field(min_length=1)
    model: str = Field(default="gpt-5.4-mini")
    check: str = Field(min_length=1)


class QualityTechniquesConfig(BaseModel):
    """Quality technique activation per workflow (§4.2)."""

    self_refine: Literal["per_section", "on_prompt", False] = False
    exemplar_injection: bool = False
    contrastive_examples: bool = False
    critique_chain: list[str] = Field(default_factory=list)
    persona: str | None = None
    domain_vocab: str | None = None
    diversity_instruction: str | None = None


class RollingContextConfig(BaseModel):
    """Rolling context configuration for long-form workflows (§43)."""

    recent_window: int = Field(default=5, ge=1)
    medium_scope: Literal["arc", "week", "section", "quarter", "not_needed"] = "arc"
    entity_tracking: bool = True
    checkpoint_targets: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# WorkflowPack — top-level schema
# ---------------------------------------------------------------------------

_MONTH_1_2_MODEL = "gpt-5.4-mini"


class WorkflowPack(BaseModel):
    """Schema for a single workflow YAML file (§10).

    Enforces anti-drift #54: all model_preference values = gpt-5.4-mini.
    """

    name: str = Field(min_length=1)
    posture: Literal["production", "research", "refinement", "onboarding"] = "production"

    # Model routing — all gpt-5.4-mini Month 1-2
    model_preference: dict[str, str] = Field(default_factory=dict)
    image_model_preference: dict[str, str] = Field(default_factory=dict)

    # Stages
    stages: list[StageDefinition] = Field(min_length=1)

    # Quality
    quality_techniques: QualityTechniquesConfig = Field(
        default_factory=QualityTechniquesConfig,
    )
    tripwire: TripwireConfig = Field(default_factory=TripwireConfig)
    parallel_guardrails: list[GuardrailDefinition] = Field(default_factory=list)

    # Scoring
    scorer_model: str = Field(default=_MONTH_1_2_MODEL)
    scorer_fallback: str = Field(default=_MONTH_1_2_MODEL)
    latency_threshold_ms: int = Field(default=5000, gt=0)

    # Context
    context_strategy: Literal["simple", "rolling_summary", "aggressive"] = "simple"
    rolling_context: RollingContextConfig | None = None

    # Publishing
    creative_workshop: bool | Literal["derivative"] = False
    derivative_source: str | None = None
    section_tripwire: bool = False

    # Plan integration
    plan_enabled: bool = False

    # Reminder prompt (tech scout injection)
    reminder_prompt: str | None = None

    # Extended workflow stub metadata
    requires_session: str | None = Field(
        default=None,
        description="Session that must ship before this workflow can run",
    )

    @model_validator(mode="after")
    def enforce_model_lock(self) -> WorkflowPack:
        """Anti-drift #54: all model_preference values must be gpt-5.4-mini."""
        for key, value in self.model_preference.items():
            if value != _MONTH_1_2_MODEL:
                msg = (
                    f"model_preference['{key}'] = '{value}' violates anti-drift #54. "
                    f"All text models must be '{_MONTH_1_2_MODEL}' during Month 1-2."
                )
                raise ValueError(msg)

        if self.scorer_model != _MONTH_1_2_MODEL:
            msg = f"scorer_model must be '{_MONTH_1_2_MODEL}', got '{self.scorer_model}'"
            raise ValueError(msg)

        if self.scorer_fallback != _MONTH_1_2_MODEL:
            msg = f"scorer_fallback must be '{_MONTH_1_2_MODEL}', got '{self.scorer_fallback}'"
            raise ValueError(msg)

        for guardrail in self.parallel_guardrails:
            if guardrail.model != _MONTH_1_2_MODEL:
                msg = (
                    f"parallel_guardrails['{guardrail.name}'].model = '{guardrail.model}' "
                    f"violates anti-drift #22/#54."
                )
                raise ValueError(msg)

        if self.tripwire.scorer_model != _MONTH_1_2_MODEL:
            msg = f"tripwire.scorer_model must be '{_MONTH_1_2_MODEL}'"
            raise ValueError(msg)

        if self.tripwire.scorer_fallback != _MONTH_1_2_MODEL:
            msg = f"tripwire.scorer_fallback must be '{_MONTH_1_2_MODEL}'"
            raise ValueError(msg)

        return self

    @model_validator(mode="after")
    def validate_derivative(self) -> WorkflowPack:
        """derivative_source required when creative_workshop == 'derivative'."""
        if self.creative_workshop == "derivative" and not self.derivative_source:
            msg = "derivative_source is required when creative_workshop is 'derivative'"
            raise ValueError(msg)
        return self


def load_workflow(path: str | Path) -> WorkflowPack:
    """Load and validate a WorkflowPack YAML file."""
    path = Path(path)
    with path.open() as fh:
        raw = yaml.safe_load(fh)
    return WorkflowPack(**raw)
