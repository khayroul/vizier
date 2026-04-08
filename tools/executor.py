"""Generic workflow executor — runs any WorkflowPack YAML (§10).

Loads a workflow YAML, validates it, iterates stages with tracing,
applies tripwire critique-then-revise, quality techniques, rolling context,
creative workshop, client overrides, and reminder prompts.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Protocol

import yaml

from contracts.context import RollingContext
from contracts.trace import TraceCollector
from tools.workflow_schema import (
    QualityTechniquesConfig,
    StageDefinition,
    WorkflowPack,
    load_workflow,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool registry protocol
# ---------------------------------------------------------------------------


class ToolCallable(Protocol):
    """Protocol for workflow tools — any callable matching this signature."""

    def __call__(self, context: dict[str, Any]) -> dict[str, Any]: ...



# ---------------------------------------------------------------------------
# Phase gate — check if workflow is allowed
# ---------------------------------------------------------------------------

_PHASE_CONFIG_PATH = Path("config/phase.yaml")


def _load_phase_config() -> dict[str, Any]:
    """Load phase.yaml to check which workflows are active."""
    if not _PHASE_CONFIG_PATH.exists():
        return {}
    with _PHASE_CONFIG_PATH.open() as fh:
        return yaml.safe_load(fh) or {}


def _is_workflow_active(workflow_name: str, phase_config: dict[str, Any]) -> bool:
    """Check if a workflow is in any active phase."""
    phases = phase_config.get("phases", {})
    for phase_data in phases.values():
        if not phase_data.get("active", False):
            continue
        includes = phase_data.get("includes", [])
        if workflow_name in includes:
            return True
    return False


# ---------------------------------------------------------------------------
# Client config overrides
# ---------------------------------------------------------------------------

_CLIENTS_DIR = Path("config/clients")


def load_client_overrides(client_id: str) -> dict[str, Any]:
    """Load workflow_overrides from config/clients/{id}.yaml.

    Returns empty dict if no overrides found.
    """
    path = _CLIENTS_DIR / f"{client_id}.yaml"
    if not path.exists():
        return {}
    with path.open() as fh:
        raw = yaml.safe_load(fh) or {}
    return raw.get("workflow_overrides", {})


def _merge_overrides(pack: WorkflowPack, overrides: dict[str, Any]) -> WorkflowPack:
    """Merge client overrides onto workflow defaults.

    Override fields: tripwire, quality_techniques, parallel_guardrails.
    Missing overrides = use workflow defaults.
    """
    if not overrides:
        return pack

    data = pack.model_dump()

    if "tripwire" in overrides:
        data["tripwire"] = {**data["tripwire"], **overrides["tripwire"]}
    if "quality_techniques" in overrides:
        data["quality_techniques"] = {
            **data["quality_techniques"],
            **overrides["quality_techniques"],
        }
    if "parallel_guardrails" in overrides:
        data["parallel_guardrails"] = overrides["parallel_guardrails"]

    return WorkflowPack(**data)


# ---------------------------------------------------------------------------
# Reminder prompt resolution
# ---------------------------------------------------------------------------


def resolve_reminder(template: str, job_context: dict[str, Any]) -> str:
    """Resolve {variable} placeholders in reminder_prompt from job context."""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(job_context.get(key, f"{{{key}}}"))

    return re.sub(r"\{(\w+)\}", _replace, template)


# ---------------------------------------------------------------------------
# Quality techniques
# ---------------------------------------------------------------------------


def apply_quality_techniques(
    prompt: str,
    techniques: QualityTechniquesConfig,
    stage_role: str,
) -> str:
    """Modify prompt based on active quality techniques (§4.2).

    Loads persona files, domain vocab, adds diversity instructions.
    """
    parts: list[str] = []

    # Persona injection (§4.2 technique 5)
    if techniques.persona and stage_role == "production":
        persona_path = Path(techniques.persona)
        if persona_path.exists():
            parts.append(persona_path.read_text().strip())

    # Domain vocabulary injection (§4.2 technique 8)
    if techniques.domain_vocab and stage_role == "production":
        vocab_path = Path(techniques.domain_vocab)
        if vocab_path.exists():
            parts.append(f"[Domain vocabulary: {vocab_path.read_text().strip()}]")

    # Self-refine instruction (§4.2 technique 1)
    if techniques.self_refine and stage_role == "production":
        parts.append(
            "[Self-refine: After generating, critique your output for specific "
            "issues, then revise to address them before finalising.]"
        )

    # Contrastive examples (§4.2 technique 7)
    if techniques.contrastive_examples and stage_role == "production":
        parts.append(
            "[Contrastive: Review the provided good/bad exemplar pair. "
            "Stay on the good side of the quality boundary.]"
        )

    # Diversity instruction
    if techniques.diversity_instruction and stage_role == "production":
        parts.append(f"[{techniques.diversity_instruction}]")

    # Critique chain dimensions
    if techniques.critique_chain and stage_role == "qa":
        dims = ", ".join(techniques.critique_chain)
        parts.append(f"[Evaluate on these dimensions: {dims}]")

    if parts:
        return "\n\n".join(parts) + "\n\n" + prompt
    return prompt


# ---------------------------------------------------------------------------
# Tripwire — critique-then-revise (§37.1, anti-drift #21, #38)
# ---------------------------------------------------------------------------


def run_tripwire(
    output: dict[str, Any],
    pack: WorkflowPack,
    stage_name: str,
    *,
    scorer_fn: ToolCallable | None = None,
    reviser_fn: ToolCallable | None = None,
) -> dict[str, Any]:
    """Run tripwire quality check with critique-then-revise.

    Anti-drift #21: uses critique with specific failing dimensions, NOT score-only.
    Anti-drift #38: no generic retry — critique must identify specific issues.

    Returns the (possibly revised) output.
    """
    tripwire = pack.tripwire
    if not tripwire.enabled:
        return output

    for attempt in range(tripwire.max_retries + 1):
        # Score via scorer function or default
        if scorer_fn is not None:
            score_result = scorer_fn({
                "output": output,
                "stage": stage_name,
                "threshold": tripwire.threshold,
                "feedback_template": tripwire.feedback_template,
            })
        else:
            # No scorer registered — pass through
            return output

        score = score_result.get("score", 5.0)
        if score >= tripwire.threshold:
            return output

        # Below threshold — need critique-then-revise
        critique = score_result.get("critique", {})
        if not critique:
            logger.warning(
                "Tripwire scorer returned no critique for stage '%s' "
                "(score=%.1f < threshold=%.1f). Cannot revise without specifics.",
                stage_name,
                score,
                tripwire.threshold,
            )
            return output

        if attempt >= tripwire.max_retries:
            # Max retries exhausted — escalate to operator
            logger.warning(
                "Tripwire exhausted %d retries for stage '%s'. "
                "Escalating to operator.",
                tripwire.max_retries,
                stage_name,
            )
            output["_tripwire_escalated"] = True
            output["_tripwire_critique"] = critique
            return output

        # Revise with critique as input
        if reviser_fn is not None:
            output = reviser_fn({
                "original_output": output,
                "critique": critique,
                "stage": stage_name,
                "attempt": attempt + 1,
            })
        else:
            return output

    return output


# ---------------------------------------------------------------------------
# Observation masking (§13.7) — compress stage output for next stage
# ---------------------------------------------------------------------------


def compress_observation(output: dict[str, Any], stage_name: str) -> str:
    """Compress a stage's output to a summary for context passing.

    Keeps reasoning trace, summarises observation data.
    """
    content = output.get("output", "")
    if isinstance(content, str) and len(content) > 500:
        return f"[{stage_name} summary: {content[:200]}...]"
    return f"[{stage_name}: {content}]"


# ---------------------------------------------------------------------------
# Workflow executor
# ---------------------------------------------------------------------------


class StubWorkflowError(Exception):
    """Raised when executor hits a workflow whose tools aren't built yet."""


class ToolNotFoundError(Exception):
    """Raised when a workflow references a tool not in the registry."""


class WorkflowExecutor:
    """Generic executor for any WorkflowPack YAML.

    Usage::

        executor = WorkflowExecutor(
            workflow_path="manifests/workflows/poster_production.yaml",
            tool_registry={"classify_artifact": my_tool, ...},
        )
        result = executor.run(job_context={"client_name": "DMB", ...})
    """

    def __init__(
        self,
        workflow_path: str | Path,
        tool_registry: dict[str, ToolCallable] | None = None,
        client_id: str | None = None,
        scorer_fn: ToolCallable | None = None,
        reviser_fn: ToolCallable | None = None,
    ) -> None:
        self.pack = load_workflow(workflow_path)
        self.tool_registry = tool_registry or {}
        self.scorer_fn = scorer_fn
        self.reviser_fn = reviser_fn

        # Apply client overrides
        if client_id:
            overrides = load_client_overrides(client_id)
            self.pack = _merge_overrides(self.pack, overrides)

        # Initialise rolling context if needed
        self.rolling_context: RollingContext | None = None
        if self.pack.context_strategy == "rolling_summary":
            rc_config = self.pack.rolling_context
            self.rolling_context = RollingContext(
                context_type="narrative",
                recent_window=rc_config.recent_window if rc_config else 5,
                medium_scope=rc_config.medium_scope if rc_config else "arc",
            )

    def _check_stub_workflow(self) -> None:
        """Check if this workflow requires an unshipped session.

        Gate 1: workflow must be in an active phase.
        Gate 2: if requires_session is set, verify that stage tools are
                actually registered (not just that the phase is active).
        """
        if not self.pack.requires_session:
            return

        # Gate 1: workflow must be in an active phase
        phase_config = _load_phase_config()
        if not _is_workflow_active(self.pack.name, phase_config):
            session = self.pack.requires_session
            raise StubWorkflowError(
                f"Workflow '{self.pack.name}' requires tools from {session} "
                f"which hasn't shipped yet. Enable in config/phase.yaml "
                f"after {session} completes."
            )

        # Gate 2: verify stage tools are actually registered
        all_tool_names: set[str] = set()
        for stage in self.pack.stages:
            all_tool_names.update(stage.tools)

        missing = all_tool_names - set(self.tool_registry.keys())
        if missing:
            session = self.pack.requires_session
            raise StubWorkflowError(
                f"Workflow '{self.pack.name}' is in an active phase but "
                f"tools {sorted(missing)} from {session} are not registered. "
                f"Register tools before running this workflow."
            )

    def _resolve_tool(self, tool_name: str) -> ToolCallable:
        """Look up a tool from the registry; raise if missing."""
        tool = self.tool_registry.get(tool_name)
        if tool is None:
            raise ToolNotFoundError(
                f"Tool '{tool_name}' not found in registry. "
                f"Available tools: {sorted(self.tool_registry.keys())}"
            )
        return tool

    def _run_stage(
        self,
        stage: StageDefinition,
        context: dict[str, Any],
        collector: TraceCollector,
    ) -> dict[str, Any]:
        """Execute a single workflow stage within a trace step."""
        with collector.step(stage.name) as trace:
            # Build prompt with quality techniques
            prompt = context.get("prompt", stage.action)
            prompt = apply_quality_techniques(
                prompt, self.pack.quality_techniques, stage.role
            )

            # Inject reminder prompt on production stages
            if (
                stage.role == "production"
                and self.pack.reminder_prompt
                and context.get("job_context")
            ):
                reminder = resolve_reminder(
                    self.pack.reminder_prompt, context["job_context"]
                )
                prompt = prompt + "\n\n" + reminder

            # Inject rolling context if available
            if self.rolling_context:
                context["rolling_context"] = (
                    self.rolling_context.get_context_window()
                )

            # Run tools for this stage
            stage_output: dict[str, Any] = {"stage": stage.name, "output": ""}
            for tool_name in stage.tools:
                try:
                    tool = self._resolve_tool(tool_name)
                except ToolNotFoundError:
                    trace.error = f"Tool '{tool_name}' not found in registry"
                    raise
                tool_result = tool({**context, "prompt": prompt, "stage": stage.name})
                stage_output.update(tool_result)

            # If no tools, still produce output from context
            if not stage.tools:
                stage_output["output"] = f"Stage '{stage.name}' completed (no tools)"

            # Record trace metrics from tool results
            trace.input_tokens = stage_output.get("input_tokens", 0)
            trace.output_tokens = stage_output.get("output_tokens", 0)
            trace.cost_usd = stage_output.get("cost_usd", 0.0)

        return stage_output

    def _post_step_update(self, stage_output: dict[str, Any], stage_name: str) -> None:
        """Fire rolling summary update after stage completes (§13.7)."""
        if self.rolling_context and self.pack.context_strategy == "rolling_summary":
            summary = compress_observation(stage_output, stage_name)
            self.rolling_context.update(summary)

    def run(self, job_context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute the full workflow.

        Args:
            job_context: Job-specific data (client_name, copy_register, etc.)
                         Used for reminder_prompt variable resolution.

        Returns:
            dict with keys: workflow, stages, trace, rolling_context (if any).
        """
        self._check_stub_workflow()

        job_context = job_context or {}
        collector = TraceCollector(job_id=job_context.get("job_id"))
        stage_results: list[dict[str, Any]] = []
        context: dict[str, Any] = {"job_context": job_context}

        for stage in self.pack.stages:
            # Expose cumulative results so downstream stages (e.g. delivery)
            # can access outputs from any prior stage, not just the previous one.
            context["stage_results"] = list(stage_results)

            # Run stage
            stage_output = self._run_stage(stage, context, collector)

            # Tripwire check (per-stage if section_tripwire, or per-workflow)
            if stage.section_tripwire or (
                self.pack.tripwire.enabled and stage.role == "production"
            ):
                stage_output = run_tripwire(
                    stage_output,
                    self.pack,
                    stage.name,
                    scorer_fn=self.scorer_fn,
                    reviser_fn=self.reviser_fn,
                )

            # Rolling context update
            self._post_step_update(stage_output, stage.name)

            # Compress observation for next stage (§13.7)
            compressed = compress_observation(stage_output, stage.name)
            context["previous_stage"] = compressed
            context["previous_output"] = stage_output

            stage_results.append(stage_output)

        production_trace = collector.finalise()

        # Persist trace to database (non-fatal — trace failures must not crash workflows)
        job_id = job_context.get("job_id")
        if job_id and production_trace:
            try:
                from utils.trace_persist import persist_trace

                persist_trace(job_id, production_trace)
            except Exception as exc:
                logger.warning("Failed to persist trace for job %s: %s", job_id, exc)

        result: dict[str, Any] = {
            "workflow": self.pack.name,
            "stages": stage_results,
            "trace": production_trace.to_jsonb(),
        }
        if self.rolling_context:
            result["rolling_context"] = self.rolling_context.get_context_window()

        return result
