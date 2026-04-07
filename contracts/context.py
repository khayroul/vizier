"""RollingContext — generic sequential production coherence contract (§43).

One contract, many applications: narrative, campaign, document, client, social.
Maintains three-tier rolling summary with entity tracking and checkpoint alignment.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class TrackedEntity(BaseModel):
    """An entity (character, product, location, etc.) tracked across steps."""

    entity_id: str = Field(min_length=1)
    entity_type: str = Field(description="character, product, location, claim, price, etc.")
    name: str
    state: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Current state of the entity — updated after each step",
    )
    introduced_at: int = Field(ge=0, description="Step index where entity first appeared")
    last_updated_at: int = Field(ge=0, description="Step index where entity was last updated")


class ImmutableFact(BaseModel):
    """A fact that can never be contradicted once established."""

    fact: str = Field(min_length=1)
    established_at: int = Field(ge=0, description="Step index where fact was established")
    source: str = Field(default="", description="Where this fact came from")


class Checkpoint(BaseModel):
    """A target state the sequence must reach."""

    description: str = Field(min_length=1)
    target_step: int | None = Field(default=None, ge=0, description="Step by which this should be reached")
    reached: bool = False
    reached_at: int | None = None


class ContextTierEntry(BaseModel):
    """An entry in a context tier (recent, medium, or long_term)."""

    step_index: int = Field(ge=0)
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# RollingContext
# ---------------------------------------------------------------------------


ContextType = Literal["narrative", "campaign", "document", "client", "social"]
MediumScope = Literal["arc", "week", "section", "quarter", "not_needed"]


class RollingContext(BaseModel):
    """Generic sequential coherence contract (§43).

    Applications:
        - Novel (30 chapters): recent_window=2, medium_scope=arc
        - Children's book (8 pages): recent_window=8, medium_scope=not_needed
        - Campaign (14 posts): recent_window=3, medium_scope=week
        - Proposal (10 sections): recent_window=2, medium_scope=section
        - Client memory (50+ jobs): recent_window=5, medium_scope=quarter
        - Social comments: recent_window=5, medium_scope=week
    """

    context_id: UUID = Field(default_factory=uuid4)
    context_type: ContextType

    # Three-tier rolling summary
    recent: list[ContextTierEntry] = Field(default_factory=list, description="Full fidelity")
    medium: list[ContextTierEntry] = Field(default_factory=list, description="Beat level")
    long_term: list[ContextTierEntry] = Field(default_factory=list, description="Compressed permanent")

    # Entity and fact tracking
    entities: list[TrackedEntity] = Field(default_factory=list)
    immutable_facts: list[ImmutableFact] = Field(default_factory=list)

    # Target states
    checkpoints: list[Checkpoint] = Field(default_factory=list)

    # Configuration
    recent_window: int = Field(default=5, ge=1, description="Max items in recent tier at full fidelity")
    medium_scope: MediumScope = Field(default="arc")
    compression_model: str = Field(default="gpt-5.4-mini", description="Anti-drift #54")

    # Internal counter
    current_step: int = Field(default=0, ge=0)

    def update(self, content: str) -> None:
        """Add a new step's content to the context.

        Manages tier promotion: when recent exceeds recent_window,
        oldest entries move to medium tier. Increments current_step.
        """
        entry = ContextTierEntry(step_index=self.current_step, content=content)
        self.recent.append(entry)
        self.current_step += 1

        # Promote oldest recent entries to medium when window exceeded
        while len(self.recent) > self.recent_window:
            promoted = self.recent.pop(0)
            self.medium.append(promoted)

    def compress(self) -> None:
        """Compress medium tier entries into long_term.

        In production, this calls the compression_model to summarise.
        Here we implement the structural contract — actual LLM compression
        is wired by S7/S8.
        """
        if not self.medium:
            return

        # Merge all medium entries into a single long_term entry
        combined = " | ".join(entry.content for entry in self.medium)
        compressed_entry = ContextTierEntry(
            step_index=self.medium[-1].step_index,
            content=f"[compressed] {combined}",
        )
        self.long_term.append(compressed_entry)
        self.medium.clear()

    def add_entity(self, entity: TrackedEntity) -> None:
        """Add or update a tracked entity."""
        for idx, existing in enumerate(self.entities):
            if existing.entity_id == entity.entity_id:
                self.entities[idx] = entity
                return
        self.entities.append(entity)

    def add_immutable_fact(self, fact: str, source: str = "") -> None:
        """Add an immutable fact that can never be contradicted."""
        self.immutable_facts.append(
            ImmutableFact(
                fact=fact,
                established_at=self.current_step,
                source=source,
            )
        )

    def get_context_window(self) -> dict[str, list[dict[str, object]]]:
        """Return the full context for injection into a production prompt.

        Returns all three tiers as serialised dicts.
        """
        return {
            "recent": [entry.model_dump(mode="json") for entry in self.recent],
            "medium": [entry.model_dump(mode="json") for entry in self.medium],
            "long_term": [entry.model_dump(mode="json") for entry in self.long_term],
            "entities": [entity.model_dump(mode="json") for entity in self.entities],
            "immutable_facts": [fact.model_dump(mode="json") for fact in self.immutable_facts],
            "checkpoints": [cp.model_dump(mode="json") for cp in self.checkpoints],
        }
