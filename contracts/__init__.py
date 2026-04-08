"""Governance contracts for Vizier.

All contracts defined here are imported by downstream sessions.
Policy is centralised in this package (anti-drift #4).
No Hermes-native types leak into these contracts (anti-drift #6).
"""

from __future__ import annotations

from contracts.artifact_spec import (
    ArtifactFamily,
    ArtifactSpec,
    DeliveryFormat,
    DeliveryRequirements,
    ProvisionalArtifactSpec,
    QARequirements,
    StructuralRequirements,
    StyleRequirements,
)
from contracts.context import (
    Checkpoint,
    ContextTierEntry,
    ImmutableFact,
    RollingContext,
    TrackedEntity,
)
from contracts.policy import PolicyAction, PolicyDecision
from contracts.publishing import (
    AGE_ARC_TEMPLATES,
    AGE_TYPOGRAPHY,
    AGE_WORD_TARGETS,
    AgeGroup,
    CharacterBible,
    CharacterRegistry,
    NarrativeScaffold,
    PageScaffold,
    PlanningObject,
    PlanningSection,
    StoryBible,
    StyleLock,
    TextImageRelationship,
    TextPlacementStrategy,
)
from contracts.readiness import (
    ReadinessResult,
    RefinementLimits,
    evaluate_readiness,
)
from contracts.routing import RoutingResult
from contracts.trace import ProductionTrace, StepTrace, TraceCollector

__all__ = [
    # artifact_spec
    "ArtifactFamily",
    "ArtifactSpec",
    "DeliveryFormat",
    "DeliveryRequirements",
    "ProvisionalArtifactSpec",
    "QARequirements",
    "StructuralRequirements",
    "StyleRequirements",
    # context
    "Checkpoint",
    "ContextTierEntry",
    "ImmutableFact",
    "RollingContext",
    "TrackedEntity",
    # policy
    "PolicyAction",
    "PolicyDecision",
    # publishing
    "AGE_ARC_TEMPLATES",
    "AGE_TYPOGRAPHY",
    "AGE_WORD_TARGETS",
    "AgeGroup",
    "CharacterBible",
    "CharacterRegistry",
    "NarrativeScaffold",
    "PageScaffold",
    "PlanningObject",
    "PlanningSection",
    "StyleLock",
    "StoryBible",
    "TextImageRelationship",
    "TextPlacementStrategy",
    # readiness
    "ReadinessResult",
    "RefinementLimits",
    "evaluate_readiness",
    # routing
    "RoutingResult",
    # trace
    "ProductionTrace",
    "StepTrace",
    "TraceCollector",
]
