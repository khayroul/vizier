"""ReadinessGate and RefinementLimits — spec readiness evaluation (§7.3, §9).

ReadinessGate evaluates whether a ProvisionalArtifactSpec is ready for production,
needs shaping, or is blocked.

RefinementLimits defines per-workflow bounds on refinement cycles.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from contracts.artifact_spec import ProvisionalArtifactSpec


class RefinementLimits(BaseModel):
    """Per-workflow bounds on the refinement loop (§9).

    Non-convergence detection: if readiness doesn't improve by 0.1
    across 2 cycles, flag as non-convergent.
    """

    max_cycles: int = Field(default=4, ge=1, le=10)
    max_unanswered_clarifications: int = Field(default=2, ge=0)
    max_prototype_rounds: int = Field(default=3, ge=0)
    cost_ceiling_usd: float = Field(
        default=5.0,
        ge=0.0,
        description="Max shaping cost before approval needed",
    )
    convergence_threshold: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum completeness improvement per 2 cycles"
            " to avoid non-convergence flag"
        ),
    )


class ReadinessResult(BaseModel):
    """Result of a readiness evaluation."""

    status: Literal["ready", "shapeable", "blocked"]
    completeness: float = Field(ge=0.0, le=1.0)
    missing_critical: list[str] = Field(default_factory=list)
    missing_nice_to_have: list[str] = Field(default_factory=list)
    reason: str = ""


def evaluate_readiness(
    spec: ProvisionalArtifactSpec,
    limits: RefinementLimits | None = None,
) -> ReadinessResult:
    """Evaluate whether a provisional spec is ready for production.

    Returns:
        ReadinessResult with status: ready, shapeable, or blocked.

    Logic:
        - blocked: missing critical fields that cannot be inferred
        - shapeable: has enough info to refine but not complete
        - ready: all critical fields present and completeness >= 0.8
    """
    missing_critical: list[str] = []
    missing_nice: list[str] = []

    # Critical fields — must be present for production
    if not spec.objective:
        missing_critical.append("objective")
    if not spec.format:
        missing_critical.append("delivery_format")

    # Nice-to-have fields — can be inferred or defaulted
    if not spec.tone:
        missing_nice.append("tone")
    if not spec.copy_register:
        missing_nice.append("copy_register")
    if not spec.dimensions:
        missing_nice.append("dimensions")
    if not spec.page_count:
        missing_nice.append("page_count")
    if not spec.brand_config_id:
        missing_nice.append("brand_config_id")

    # Calculate completeness
    # objective, format, tone, copy_register,
    # dimensions, page_count, brand_config
    total_fields = 7
    filled = total_fields - len(missing_critical) - len(missing_nice)
    completeness = filled / total_fields

    # Check limits
    limits = limits or RefinementLimits()
    if spec.cycle >= limits.max_cycles and missing_critical:
        return ReadinessResult(
            status="blocked",
            completeness=completeness,
            missing_critical=missing_critical,
            missing_nice_to_have=missing_nice,
            reason=(
            f"Max cycles ({limits.max_cycles}) reached"
            f" with critical fields missing: {missing_critical}"
        ),
        )

    # Determine status
    if not missing_critical and completeness >= 0.8:
        status: Literal["ready", "shapeable", "blocked"] = "ready"
        reason = (
            "All critical fields present"
            " and completeness threshold met"
        )
    elif missing_critical and not spec.objective and not spec.raw_brief:
        status = "blocked"
        reason = (
            "Cannot shape without objective or raw brief."
            f" Missing: {missing_critical}"
        )
    else:
        status = "shapeable"
        reason = (
            f"Missing critical: {missing_critical},"
            f" nice-to-have: {missing_nice}"
        )

    return ReadinessResult(
        status=status,
        completeness=completeness,
        missing_critical=missing_critical,
        missing_nice_to_have=missing_nice,
        reason=reason,
    )
