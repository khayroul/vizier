"""RoutingResult — stub contract for routing decisions.

S6 defines the data contract only. S11 fills in the routing logic.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RoutingResult(BaseModel):
    """Inspectable routing output stored on the job record (§8).

    Stub — S11 implements routing logic that produces this result.
    """

    routing_id: UUID = Field(default_factory=uuid4)
    job_id: str | None = None
    workflow: str = Field(description="Selected workflow name, e.g. 'poster_production'")
    model_preference: str = Field(default="gpt-5.4-mini", description="Anti-drift #54")
    image_model: str | None = Field(default=None, description="Selected image model if applicable")
    design_system: str | None = None
    fast_path: bool = Field(default=False, description="True if matched a fast-path pattern")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str = Field(default="", description="Why this route was chosen")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
