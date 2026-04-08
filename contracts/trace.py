"""StepTrace, ProductionTrace, TraceCollector — production tracing (§7, §29).

StepTrace captures a single production step's metrics.
ProductionTrace aggregates all steps for a job.
TraceCollector provides a context-manager API for collecting traces.

No Hermes-native types leak into these contracts (anti-drift #6).
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime
from typing import Generator
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class StepTrace(BaseModel):
    """Trace of a single production step.

    The `proof` field holds structured evidence of step success,
    e.g. {"nima_score": 6.8, "brand_voice_match": 0.92}.
    Populated by QA stages, tripwire scorers, guardrails.
    Feeds improvement loop for step-level correlation with operator approval.
    """

    trace_id: UUID = Field(default_factory=uuid4)
    step_name: str = Field(min_length=1)
    model: str = Field(default="gpt-5.4-mini", description="Anti-drift #54")
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    duration_ms: float = Field(default=0.0, ge=0.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    proof: dict[str, float | int | str | bool | None] | None = Field(
        default=None,
        description="Structured evidence of step success, JSONB-compatible",
    )
    error: str | None = None

    def to_jsonb(self) -> dict[str, object]:
        """Serialise to a JSONB-compatible dict for Postgres storage."""
        return self.model_dump(mode="json")


class ProductionTrace(BaseModel):
    """Aggregated trace for an entire job.

    Stored as JSONB on the jobs table's production_trace column.
    """

    job_id: str | None = None
    steps: list[StepTrace] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    @property
    def total_cost_usd(self) -> float:
        """Sum of all step costs."""
        return sum(step.cost_usd for step in self.steps)

    @property
    def total_duration_ms(self) -> float:
        """Sum of all step durations."""
        return sum(step.duration_ms for step in self.steps)

    @property
    def total_input_tokens(self) -> int:
        """Sum of all input tokens."""
        return sum(step.input_tokens for step in self.steps)

    @property
    def total_output_tokens(self) -> int:
        """Sum of all output tokens."""
        return sum(step.output_tokens for step in self.steps)

    def to_jsonb(self) -> dict[str, object]:
        """Serialise to a JSONB-compatible dict for Postgres storage."""
        data = self.model_dump(mode="json")
        # Include computed totals (properties aren't in model_dump)
        data["total_cost_usd"] = self.total_cost_usd
        data["total_duration_ms"] = self.total_duration_ms
        data["total_input_tokens"] = self.total_input_tokens
        data["total_output_tokens"] = self.total_output_tokens
        return data


class TraceCollector:
    """Collects StepTrace entries via a context-manager API.

    Usage::

        collector = TraceCollector(job_id="job-123")

        with collector.step("generate_copy") as trace:
            # ... do work ...
            trace.input_tokens = 500
            trace.output_tokens = 200
            trace.cost_usd = 0.001
            trace.model = "gpt-5.4-mini"
            trace.proof = {"brand_voice_match": 0.92}

        production_trace = collector.finalise()
    """

    def __init__(self, job_id: str | None = None) -> None:
        self._job_id = job_id
        self._steps: list[StepTrace] = []
        self._started_at = datetime.utcnow()

    @contextmanager
    def step(self, step_name: str) -> Generator[StepTrace, None, None]:
        """Context manager that times a production step.

        Yields a mutable StepTrace. On exit, duration_ms is set
        automatically from wall-clock time.
        """
        trace = StepTrace(step_name=step_name)
        start = time.monotonic()
        try:
            yield trace
        except Exception as exc:
            trace.error = str(exc)
            raise
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            trace.duration_ms = elapsed_ms
            self._steps.append(trace)

    def finalise(self) -> ProductionTrace:
        """Build the final ProductionTrace from collected steps."""
        return ProductionTrace(
            job_id=self._job_id,
            steps=list(self._steps),
            started_at=self._started_at,
            completed_at=datetime.utcnow(),
        )

    @property
    def steps(self) -> list[StepTrace]:
        """Read-only access to collected steps."""
        return list(self._steps)
