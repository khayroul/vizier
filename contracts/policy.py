"""PolicyDecision — centralised policy decisions for Vizier (§7.2).

Policy is centralised in contracts/ (anti-drift #4).
The PolicyEvaluator in middleware/policy.py consumes these decisions.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PolicyAction(StrEnum):
    """Actions a policy gate can take."""

    allow = "allow"
    block = "block"
    degrade = "degrade"
    escalate = "escalate"


class PolicyDecision(BaseModel):
    """Result of a policy evaluation.

    Every policy check produces one of these, logged to the policy_logs table.
    """

    decision_id: UUID = Field(default_factory=uuid4)
    action: PolicyAction
    reason: str = Field(
        min_length=1,
        description="Human-readable reason for the decision",
    )
    gate: str = Field(
        min_length=1,
        description="Which gate produced this: budget, tool, phase, cost",
    )
    job_id: str | None = None
    client_id: str | None = None
    capability: str | None = Field(
        default=None,
        description="What was being evaluated, e.g. 'poster_production'",
    )
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="Audit-grade structured constraints imposed by this decision",
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
