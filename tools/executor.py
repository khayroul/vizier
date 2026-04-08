"""Generic workflow executor — runs any WorkflowPack YAML (§10).

Loads a workflow YAML, validates it, iterates stages with tracing,
applies tripwire critique-then-revise, quality techniques, rolling context,
creative workshop, client overrides, and reminder prompts.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
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


def _get_exemplar_context(job_context: dict[str, Any]) -> str | None:
    """Try to retrieve exemplar style tags for prompt injection.

    Queries the exemplars table for active exemplars matching this client
    and artifact family. Returns a style reference string, or None if no
    exemplars exist or the database is unavailable.

    Graceful: never raises — DB absence or empty table just skips injection.
    """
    client_id = job_context.get("client_id")
    artifact_family = job_context.get("artifact_family", "poster")
    if not client_id:
        return None
    try:
        from utils.database import get_cursor

        with get_cursor() as cur:
            cur.execute(
                "SELECT style_tags, artifact_family "
                "FROM exemplars "
                "WHERE client_id = %s AND status = 'active' "
                "AND artifact_family = %s "
                "ORDER BY created_at DESC LIMIT 3",
                (client_id, artifact_family),
            )
            rows = cur.fetchall()
        if not rows:
            return None
        tags: list[str] = []
        for row in rows:
            row_tags = row.get("style_tags")
            if row_tags:
                tags.extend(row_tags if isinstance(row_tags, list) else [row_tags])
        if not tags:
            return None
        unique_tags = list(dict.fromkeys(tags))  # preserve order, deduplicate
        return (
            f"[Exemplar style reference from past successful {artifact_family}s: "
            f"{', '.join(unique_tags[:10])}. "
            f"Match this proven style direction.]"
        )
    except Exception as exc:
        logger.debug("Exemplar injection skipped: %s", exc)
        return None


def apply_quality_techniques(
    prompt: str,
    techniques: QualityTechniquesConfig,
    stage_role: str,
    job_context: dict[str, Any] | None = None,
) -> str:
    """Modify prompt based on active quality techniques (§4.2).

    Loads persona files, domain vocab, exemplar references, adds diversity
    instructions.
    """
    parts: list[str] = []

    # Persona injection (§4.2 technique 5)
    if techniques.persona and stage_role == "production":
        persona_path = Path(techniques.persona)
        if persona_path.exists():
            parts.append(persona_path.read_text().strip())

    # Exemplar injection (§4.2 technique 4)
    if techniques.exemplar_injection and stage_role == "production" and job_context:
        exemplar_ctx = _get_exemplar_context(job_context)
        if exemplar_ctx:
            parts.append(exemplar_ctx)

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
    job_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run tripwire quality check with critique-then-revise.

    Anti-drift #21: uses critique with specific failing dimensions, NOT score-only.
    Anti-drift #38: no generic retry — critique must identify specific issues.

    Returns the (possibly revised) output.
    """
    tripwire = pack.tripwire
    if not tripwire.enabled:
        return output

    runtime_controls = dict((job_context or {}).get("runtime_controls") or {})
    max_retries = min(
        tripwire.max_retries,
        int(runtime_controls.get("max_tripwire_retries", tripwire.max_retries)),
    )
    require_quality_pass = bool(runtime_controls.get("require_quality_pass", True))

    for attempt in range(max_retries + 1):
        # Score via scorer function or default
        if scorer_fn is not None:
            score_result = scorer_fn({
                "output": output,
                "stage": stage_name,
                "threshold": tripwire.threshold,
                "feedback_template": tripwire.feedback_template,
                "job_context": job_context or {},
                "artifact_payload": output.get("_artifact_payload", {}),
            })
        else:
            # No scorer registered — pass through
            return output

        score = score_result.get("score", 5.0)
        output["_tripwire_score"] = score
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
            if require_quality_pass:
                output["status"] = "error"
                output["output"] = (
                    f"tripwire_failed: stage '{stage_name}' scored {score:.2f} "
                    "below threshold without actionable critique"
                )
            return output

        if attempt >= max_retries:
            # Max retries exhausted — escalate to operator
            logger.warning(
                "Tripwire exhausted %d retries for stage '%s'. "
                "Escalating to operator.",
                max_retries,
                stage_name,
            )
            output["_tripwire_escalated"] = True
            output["_tripwire_critique"] = critique
            if require_quality_pass:
                output["status"] = "error"
                output["output"] = (
                    f"tripwire_failed: stage '{stage_name}' scored {score:.2f} "
                    f"below threshold {tripwire.threshold:.2f} after {max_retries} retries"
                )
            return output

        # Revise with critique as input — merge revision into original
        # to preserve metadata (stage, image_path, poster_copy, etc.)
        if reviser_fn is not None:
            revised = reviser_fn({
                "original_output": output,
                "critique": critique,
                "stage": stage_name,
                "attempt": attempt + 1,
                "job_context": job_context or {},
                "artifact_payload": output.get("_artifact_payload", {}),
            })
            # Merge: revision fields override, but preserve keys the
            # reviser didn't return (artifact handles, stage name, costs)
            for key, value in revised.items():
                output[key] = value
            output["_tripwire_revised"] = True
            output["_tripwire_attempt"] = attempt + 1
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


class WorkflowExecutionError(Exception):
    """Raised when a workflow hits a terminal error or stub stage."""

    def __init__(self, message: str, result: dict[str, Any]) -> None:
        super().__init__(message)
        self.result = result


@lru_cache(maxsize=1)
def _get_production_registry_snapshot() -> dict[str, ToolCallable]:
    """Load the canonical production registry once for stub identity checks."""
    from tools.registry import build_production_registry

    return build_production_registry()


def _is_terminal_status(status: Any) -> bool:
    """Return True when a stage/tool status should stop execution."""
    return status in {"error", "stub"}


def _normalise_guardrail_text(value: Any) -> str | None:
    """Extract meaningful text from stage/tool payloads for guardrails."""
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            text = "\n".join(
                str(item).strip()
                for item in parsed.values()
                if isinstance(item, str) and item.strip()
            )

    lowered = text.lower()
    low_signal_markers = (
        "image_generated",
        "poster_delivered",
        "delivery_failed",
        "typst_rendered",
        "no typst source provided",
        "_completed",
    )
    if any(marker in lowered for marker in low_signal_markers):
        return None
    if len(text) < 12:
        return None
    return text


def _extract_guardrail_copy(stage_output: dict[str, Any]) -> str | None:
    """Find the best available textual content for generic guardrails."""
    candidate_keys = (
        "poster_copy",
        "brochure_copy",
        "document_content",
        "section_content",
        "page_text",
        "output",
    )

    for key in candidate_keys:
        text = _normalise_guardrail_text(stage_output.get(key))
        if text:
            return text

    tool_results = stage_output.get("_tool_results", {})
    if isinstance(tool_results, dict):
        for tool_result in tool_results.values():
            if not isinstance(tool_result, dict):
                continue
            for key in candidate_keys:
                text = _normalise_guardrail_text(tool_result.get(key))
                if text:
                    return text
    return None


_ARTIFACT_TEXT_KEYS = (
    "poster_copy",
    "brochure_copy",
    "document_content",
    "section_content",
    "page_text",
)


def _extract_artifact_text(payload: dict[str, Any]) -> str:
    """Return the highest-signal text content from an artifact payload."""
    for key in _ARTIFACT_TEXT_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    output_text = _normalise_guardrail_text(payload.get("output"))
    return output_text or ""


def _initialise_artifact_payload(job_context: dict[str, Any]) -> dict[str, Any]:
    """Seed the shared artifact payload from job context."""
    runtime_controls = dict(job_context.get("runtime_controls") or {})
    return {
        "artifact_family": job_context.get("artifact_family"),
        "client_id": job_context.get("client_id"),
        "client_name": job_context.get("client_name"),
        "language": job_context.get("language"),
        "client_default_language": job_context.get("client_default_language"),
        "copy_register": job_context.get("copy_register"),
        "brand_config": job_context.get("brand_config"),
        "template_name": job_context.get("template_name"),
        "platform": job_context.get("platform"),
        "design_system": job_context.get("design_system"),
        "quality_posture": job_context.get("quality_posture"),
        "budget_profile": job_context.get("budget_profile"),
        "runtime_controls": runtime_controls,
        "knowledge_cards_used": list(job_context.get("knowledge_cards_used", [])),
        "revision_count": 0,
        "tripwire_attempts": 0,
    }


def _merge_artifact_payload(
    payload: dict[str, Any],
    update: dict[str, Any],
    *,
    stage_name: str,
    tool_name: str | None = None,
) -> dict[str, Any]:
    """Merge tool/stage outputs into the canonical artifact payload."""
    merged = dict(payload)

    direct_keys = (
        "artifact_family",
        "client_id",
        "client_name",
        "language",
        "copy_register",
        "template_name",
        "platform",
        "design_system",
        "brand_config",
        "poster_copy",
        "brochure_copy",
        "document_content",
        "section_content",
        "page_text",
        "image_path",
        "image_model",
        "pdf_path",
        "png_path",
    )
    for key in direct_keys:
        value = update.get(key)
        if value not in (None, "", [], {}):
            merged[key] = value

    cards = update.get("cards")
    if isinstance(cards, list) and cards:
        used = list(merged.get("knowledge_cards_used", []))
        for card in cards:
            if not isinstance(card, dict):
                continue
            ref = (
                card.get("id")
                or card.get("title")
                or card.get("knowledge_card_id")
            )
            if ref is not None:
                ref_text = str(ref)
                if ref_text not in used:
                    used.append(ref_text)
        merged["knowledge_cards_used"] = used

    if "score" in update and stage_name == "qa":
        merged["quality_verdict"] = {
            "status": update.get("status", "ok"),
            "score": update.get("score"),
            "qa_threshold": update.get("qa_threshold"),
            "passed": update.get("status") != "error",
            "quality_summary": update.get("quality_summary"),
        }

    if "guardrail_flags" in update:
        merged["guardrail_flags"] = update.get("guardrail_flags", [])
        merged["guardrail_flag_count"] = len(update.get("guardrail_flags", []))

    if update.get("_tripwire_revised"):
        merged["revision_count"] = int(merged.get("revision_count", 0)) + 1
        merged["tripwire_attempts"] = max(
            int(merged.get("tripwire_attempts", 0)),
            int(update.get("_tripwire_attempt", 0)),
        )
        if tool_name:
            merged["tripwire_last_stage"] = stage_name

    text_content = _extract_artifact_text(merged)
    if text_content:
        merged["text_content"] = text_content

    return merged


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

        # Gate 3: block active workflows that depend on stub (unimplemented) tools
        from tools.registry import get_stub_tool_names

        stub_names = get_stub_tool_names()
        stub_deps = all_tool_names & stub_names
        if stub_deps:
            session = self.pack.requires_session or "a future session"
            raise StubWorkflowError(
                f"Workflow '{self.pack.name}' depends on stub tools "
                f"{sorted(stub_deps)} that aren't implemented yet. "
                f"Waiting for {session}."
            )

    def _is_canonical_stub_tool(self, tool_name: str, tool: ToolCallable) -> bool:
        """True when a stage is about to use an unresolved production-registry tool."""
        from tools.registry import get_stub_tool_names

        if tool_name not in get_stub_tool_names():
            return False
        return tool is _get_production_registry_snapshot().get(tool_name)

    def _infer_rework_failed_stage(
        self, original_trace: dict[str, Any] | None,
    ) -> str | None:
        """Infer the failing stage name from an original workflow trace."""
        trace = original_trace or {}

        stages = trace.get("stages", [])
        if isinstance(stages, list):
            for stage in stages:
                if not isinstance(stage, dict):
                    continue
                if _is_terminal_status(stage.get("status")) and stage.get("stage"):
                    return str(stage["stage"])

        steps = trace.get("steps", [])
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                name = step.get("step_name") or step.get("name")
                if step.get("error") and name:
                    return str(name)

        if isinstance(stages, list) and stages:
            candidate_names = [
                str(stage["stage"])
                for stage in stages
                if isinstance(stage, dict)
                and stage.get("stage")
                and stage.get("stage") not in {"delivery", "qa", "diagnose"}
            ]
            if candidate_names:
                return candidate_names[-1]

        if isinstance(steps, list) and steps:
            names = [
                step.get("step_name") or step.get("name")
                for step in steps
                if isinstance(step, dict)
            ]
            names = [str(name) for name in names if name]
            if names:
                return names[-1]

        return None

    def _prepare_rework_rerun(
        self,
        stage: StageDefinition,
        context: dict[str, Any],
    ) -> tuple[StageDefinition | None, dict[str, Any], dict[str, Any]]:
        """Hydrate the rework rerun stage from the original workflow trace."""
        job_context = dict(context.get("job_context") or {})
        original_trace = job_context.get("original_trace")
        diagnose_output = context.get("previous_output") or {}

        original_workflow = (
            diagnose_output.get("original_workflow")
            or job_context.get("original_workflow")
            or (original_trace or {}).get("workflow")
        )
        failed_stage = (
            diagnose_output.get("failed_stage")
            or job_context.get("failed_stage")
            or self._infer_rework_failed_stage(original_trace)
        )

        meta = {"stage": stage.name}
        if not original_workflow:
            return None, context, {
                **meta,
                "status": "error",
                "output": "rework_failed: cannot determine original workflow",
            }
        if not failed_stage:
            return None, context, {
                **meta,
                "status": "error",
                "output": (
                    f"rework_failed: cannot determine failing stage for "
                    f"workflow '{original_workflow}'"
                ),
                "original_workflow": original_workflow,
            }

        workflow_path = Path("manifests/workflows") / f"{original_workflow}.yaml"
        if not workflow_path.exists():
            return None, context, {
                **meta,
                "status": "error",
                "output": (
                    f"rework_failed: unknown original workflow "
                    f"'{original_workflow}'"
                ),
                "original_workflow": original_workflow,
                "failed_stage": failed_stage,
            }

        original_pack = load_workflow(workflow_path)
        original_stage = next(
            (item for item in original_pack.stages if item.name == failed_stage),
            None,
        )
        if original_stage is None:
            return None, context, {
                **meta,
                "status": "error",
                "output": (
                    f"rework_failed: stage '{failed_stage}' not found in "
                    f"workflow '{original_workflow}'"
                ),
                "original_workflow": original_workflow,
                "failed_stage": failed_stage,
            }

        feedback = (
            diagnose_output.get("feedback")
            or job_context.get("feedback")
            or job_context.get("raw_input", "")
        )
        prompt = original_stage.action
        if feedback:
            prompt = f"{prompt}\n\nRework feedback: {feedback}"

        rerun_context = dict(context)
        rerun_context["prompt"] = prompt
        rerun_context["job_context"] = {
            **job_context,
            "original_workflow": original_workflow,
            "failed_stage": failed_stage,
        }
        rerun_stage = original_stage.model_copy(
            update={
                "name": stage.name,
                "role": stage.role,
            }
        )
        return rerun_stage, rerun_context, {
            "rework_source_workflow": original_workflow,
            "rework_source_stage": failed_stage,
        }

    def _run_stage_guardrails(
        self,
        stage_output: dict[str, Any],
        collector: TraceCollector,
        job_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Run generic parallel guardrails for production stages with text output."""
        runtime_controls = dict(job_context.get("runtime_controls") or {})
        if (
            not self.pack.parallel_guardrails
            or not bool(runtime_controls.get("allow_parallel_guardrails", True))
        ):
            return stage_output

        copy_text = _extract_guardrail_copy(stage_output)
        if not copy_text:
            return stage_output

        from middleware.guardrails import run_parallel_guardrails

        with collector.step(f"{stage_output.get('stage', 'stage')}_guardrails") as trace:
            try:
                flags = run_parallel_guardrails(
                    copy=copy_text,
                    copy_register=str(job_context.get("copy_register", "neutral")),
                    brand_config=job_context.get("brand_config"),
                    language=str(job_context.get("language", "en")),
                )
                trace.proof = {
                    "stage": str(stage_output.get("stage", "")),
                    "flags_count": len(flags),
                }
            except Exception as exc:
                logger.warning(
                    "Parallel guardrails failed for stage '%s': %s",
                    stage_output.get("stage", ""),
                    exc,
                )
                trace.error = str(exc)
                flags = []

        stage_output["guardrail_flags"] = flags
        if flags:
            stage_output["_guardrail_flagged"] = True
        return stage_output

    def _resolve_stage_knowledge(
        self,
        stage: StageDefinition,
        context: dict[str, Any],
    ) -> tuple[str, list[dict[str, Any]]]:
        """Best-effort retrieval for declarative stage knowledge."""
        if not stage.knowledge:
            return "", []

        job_context = dict(context.get("job_context") or {})
        client_id = str(job_context.get("client_id", "default"))
        runtime_controls = job_context.get("runtime_controls", {})
        top_k = int(runtime_controls.get("knowledge_card_cap", 0) or 0)
        if top_k <= 0:
            return "", []

        query = str(job_context.get("raw_input") or context.get("prompt") or stage.action)

        try:
            from utils.embeddings import embed_text
            from utils.knowledge import assemble_context

            query_embedding = embed_text(
                query,
                job_id=job_context.get("job_id"),
            ) if query else None
            assembled = assemble_context(
                client_id=client_id,
                query=query,
                query_embedding=query_embedding,
                include_knowledge=True,
                top_k=top_k,
            )
        except Exception as exc:
            logger.debug("Stage knowledge injection skipped for %s: %s", stage.name, exc)
            return "", []

        snippets: list[str] = []
        client_config = assembled.get("client_config", {})
        if isinstance(client_config, dict) and {"client", "brand_pattern", "swipe"} & set(stage.knowledge):
            defaults = client_config.get("defaults", {})
            brand = client_config.get("brand", {})
            summary_parts: list[str] = []
            if client_config.get("client_name"):
                summary_parts.append(f"Client: {client_config['client_name']}")
            if defaults.get("copy_register"):
                summary_parts.append(f"Register: {defaults['copy_register']}")
            if defaults.get("style_hint"):
                summary_parts.append(f"Style hint: {defaults['style_hint']}")
            if brand.get("primary_color"):
                summary_parts.append(f"Primary colour: {brand['primary_color']}")
            if summary_parts:
                snippets.append("Client context:\n- " + "\n- ".join(summary_parts))

        knowledge_cards = assembled.get("knowledge_cards", [])
        selected_cards: list[dict[str, Any]] = []
        if isinstance(knowledge_cards, list):
            for card in knowledge_cards[:top_k]:
                if not isinstance(card, dict):
                    continue
                title = str(card.get("title") or "Untitled card")
                content = str(card.get("content") or "").strip()
                selected_cards.append(card)
                if content:
                    snippets.append(
                        f"Knowledge card — {title}:\n{content[:400]}"
                    )

        if not snippets:
            return "", selected_cards

        return "\n\n".join(snippets), selected_cards

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
            job_context = dict(context.get("job_context") or {})
            artifact_payload = dict(
                context.get("artifact_payload")
                or _initialise_artifact_payload(job_context)
            )

            # Build prompt: stage action + user's original brief
            raw_input = job_context.get("raw_input", "")
            base_prompt = context.get("prompt", stage.action)
            if raw_input and raw_input not in base_prompt:
                prompt = f"{stage.action}\n\nOriginal brief: {raw_input}"
            else:
                prompt = base_prompt

            knowledge_context, selected_cards = self._resolve_stage_knowledge(stage, context)
            if knowledge_context:
                prompt = f"{prompt}\n\nKnowledge context:\n{knowledge_context}"
                artifact_payload = _merge_artifact_payload(
                    artifact_payload,
                    {"cards": selected_cards},
                    stage_name=stage.name,
                )

            prompt = apply_quality_techniques(
                prompt, self.pack.quality_techniques, stage.role,
                job_context=job_context,
            )

            # Inject reminder prompt on production stages
            if (
                stage.role == "production"
                and self.pack.reminder_prompt
                and job_context
            ):
                reminder = resolve_reminder(
                    self.pack.reminder_prompt, job_context
                )
                prompt = prompt + "\n\n" + reminder

            # Inject rolling context if available
            if self.rolling_context:
                context["rolling_context"] = (
                    self.rolling_context.get_context_window()
                )

            # Run tools for this stage — chain outputs so later tools see
            # earlier tools' results (e.g. image_generate sees poster_copy
            # from generate_poster). Merge without clobbering populated keys.
            stage_output: dict[str, Any] = {
                "stage": stage.name,
                "output": "",
                "_tool_results": {},
                "_tool_metrics": [],
                "_artifact_payload": artifact_payload,
            }
            if selected_cards:
                stage_output["knowledge_cards_used"] = artifact_payload.get(
                    "knowledge_cards_used", [],
                )

            stage_input_tokens = 0
            stage_output_tokens = 0
            stage_cost_usd = 0.0

            for tool_name in stage.tools:
                try:
                    tool = self._resolve_tool(tool_name)
                except ToolNotFoundError:
                    trace.error = f"Tool '{tool_name}' not found in registry"
                    raise

                if self._is_canonical_stub_tool(tool_name, tool):
                    tool_result = {
                        "status": "stub",
                        "tool": tool_name,
                        "output": f"tool_not_implemented: {tool_name}",
                    }
                else:
                    # Chain: each tool sees the cumulative stage output so far
                    tool_context = {
                        **context,
                        "prompt": prompt,
                        "stage": stage.name,
                        "current_output": stage_output,
                        "previous_tool_result": stage_output,
                        "artifact_payload": artifact_payload,
                    }
                    tool_result = tool(tool_context)
                tool_results = stage_output.setdefault("_tool_results", {})
                if isinstance(tool_results, dict):
                    tool_results[tool_name] = dict(tool_result)

                tool_metrics = stage_output.setdefault("_tool_metrics", [])
                if isinstance(tool_metrics, list):
                    tool_metrics.append({
                        "tool": tool_name,
                        "status": tool_result.get("status", "ok"),
                        "input_tokens": int(tool_result.get("input_tokens", 0) or 0),
                        "output_tokens": int(tool_result.get("output_tokens", 0) or 0),
                        "cost_usd": float(tool_result.get("cost_usd", 0.0) or 0.0),
                    })

                stage_input_tokens += int(tool_result.get("input_tokens", 0) or 0)
                stage_output_tokens += int(tool_result.get("output_tokens", 0) or 0)
                stage_cost_usd += float(tool_result.get("cost_usd", 0.0) or 0.0)

                for key, value in tool_result.items():
                    if key in stage_output and stage_output[key] and not value:
                        continue  # don't overwrite populated key with empty
                    stage_output[key] = value

                artifact_payload = _merge_artifact_payload(
                    artifact_payload,
                    tool_result,
                    stage_name=stage.name,
                    tool_name=tool_name,
                )
                stage_output["_artifact_payload"] = artifact_payload
                if _is_terminal_status(stage_output.get("status")):
                    trace.error = str(
                        stage_output.get("output")
                        or f"Tool '{tool_name}' returned {stage_output.get('status')}"
                    )
                    break

            # If no tools, still produce output from context
            if not stage.tools:
                stage_output["output"] = f"Stage '{stage.name}' completed (no tools)"

            # Record trace metrics from tool results
            stage_output["input_tokens"] = stage_input_tokens
            stage_output["output_tokens"] = stage_output_tokens
            stage_output["cost_usd"] = stage_cost_usd

            trace.input_tokens = stage_input_tokens
            trace.output_tokens = stage_output_tokens
            trace.cost_usd = stage_cost_usd
            trace.proof = {
                "stage": stage.name,
                "role": stage.role,
                "tool_metrics": list(stage_output.get("_tool_metrics", [])),
                "knowledge_cards_used": list(
                    artifact_payload.get("knowledge_cards_used", []),
                ),
                "template_name": artifact_payload.get("template_name"),
                "design_system": artifact_payload.get("design_system"),
                "quality_posture": artifact_payload.get("quality_posture"),
                "budget_profile": artifact_payload.get("budget_profile"),
                "has_image_path": bool(artifact_payload.get("image_path")),
                "has_text_content": bool(_extract_artifact_text(artifact_payload)),
            }

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
        context: dict[str, Any] = {
            "job_context": job_context,
            "artifact_payload": _initialise_artifact_payload(job_context),
        }
        workflow_status = "ok"
        failed_stage: str | None = None

        for stage in self.pack.stages:
            # Expose cumulative results so downstream stages (e.g. delivery)
            # can access outputs from any prior stage, not just the previous one.
            context["stage_results"] = list(stage_results)

            # Run stage
            effective_stage = stage
            effective_context = context
            rework_meta: dict[str, Any] = {}
            if self.pack.name == "rework" and stage.name == "rerun" and not stage.tools:
                effective_stage, effective_context, rework_meta = (
                    self._prepare_rework_rerun(stage, context)
                )
                if effective_stage is None:
                    stage_output = rework_meta
                else:
                    stage_output = self._run_stage(
                        effective_stage, effective_context, collector,
                    )
                    for key, value in rework_meta.items():
                        stage_output.setdefault(key, value)
            else:
                stage_output = self._run_stage(stage, context, collector)

            if _is_terminal_status(stage_output.get("status")):
                workflow_status = str(stage_output.get("status"))
                failed_stage = str(stage_output.get("stage", stage.name))
                stage_results.append(stage_output)
                break

            if stage.role == "production":
                stage_output = self._run_stage_guardrails(
                    stage_output,
                    collector,
                    job_context,
                )
                context["artifact_payload"] = _merge_artifact_payload(
                    dict(context.get("artifact_payload") or {}),
                    stage_output,
                    stage_name=stage.name,
                )
                stage_output["_artifact_payload"] = dict(context["artifact_payload"])

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
                    job_context=job_context,
                )
                context["artifact_payload"] = _merge_artifact_payload(
                    dict(context.get("artifact_payload") or {}),
                    stage_output,
                    stage_name=stage.name,
                )
                stage_output["_artifact_payload"] = dict(context["artifact_payload"])
                if _is_terminal_status(stage_output.get("status")):
                    workflow_status = str(stage_output.get("status"))
                    failed_stage = str(stage_output.get("stage", stage.name))
                    stage_results.append(stage_output)
                    break

            # Rolling context update
            self._post_step_update(stage_output, stage.name)

            # Compress observation for next stage (§13.7)
            compressed = compress_observation(stage_output, stage.name)
            context["previous_stage"] = compressed
            context["previous_output"] = stage_output
            context["artifact_payload"] = stage_output.get(
                "_artifact_payload",
                context.get("artifact_payload"),
            )

            stage_results.append(stage_output)

        production_trace = collector.finalise()
        production_trace.steps_executed = [stage["stage"] for stage in stage_results]
        artifact_payload = dict(context.get("artifact_payload") or {})
        knowledge_cards_used = list(artifact_payload.get("knowledge_cards_used", []))
        for stage_result in stage_results:
            stage_cards = stage_result.get("knowledge_cards_used", [])
            if isinstance(stage_cards, list):
                for card in stage_cards:
                    if card not in knowledge_cards_used:
                        knowledge_cards_used.append(card)
            stage_payload = stage_result.get("_artifact_payload", {})
            if isinstance(stage_payload, dict):
                for card in stage_payload.get("knowledge_cards_used", []):
                    if card not in knowledge_cards_used:
                        knowledge_cards_used.append(card)
        production_trace.knowledge_cards_used = knowledge_cards_used
        production_trace.revision_count = int(artifact_payload.get("revision_count", 0))
        production_trace.template_used = (
            artifact_payload.get("template_name")
            if isinstance(artifact_payload.get("template_name"), str)
            else None
        )
        production_trace.design_system = (
            artifact_payload.get("design_system")
            if isinstance(artifact_payload.get("design_system"), str)
            else None
        )
        production_trace.runtime_controls = dict(job_context.get("runtime_controls") or {})
        production_trace.quality_summary = (
            artifact_payload.get("quality_verdict")
            if isinstance(artifact_payload.get("quality_verdict"), dict)
            else None
        )
        production_trace.artifact_summary = {
            "has_image_path": bool(artifact_payload.get("image_path")),
            "has_pdf_path": bool(artifact_payload.get("pdf_path")),
            "has_text_content": bool(_extract_artifact_text(artifact_payload)),
            "budget_profile": artifact_payload.get("budget_profile"),
            "quality_posture": artifact_payload.get("quality_posture"),
        }

        # Persist trace to database
        # (non-fatal: trace failures must not crash workflows)
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
            "status": workflow_status,
            "artifact_payload": artifact_payload,
        }
        if self.rolling_context:
            result["rolling_context"] = self.rolling_context.get_context_window()

        if failed_stage is not None:
            result["failed_stage"] = failed_stage
            result["error"] = stage_results[-1].get("output", "")
            raise WorkflowExecutionError(
                f"Workflow '{self.pack.name}' stopped at stage '{failed_stage}' "
                f"with status '{workflow_status}': {result['error']}",
                result=result,
            )

        if job_id:
            try:
                from tools.knowledge import record_outcome

                quality_summary = (
                    artifact_payload.get("quality_verdict")
                    if isinstance(artifact_payload.get("quality_verdict"), dict)
                    else {}
                )
                record_outcome(
                    job_id=job_id,
                    outcome_data={
                        "artifact_id": None,
                        "client_id": job_context.get("client_id"),
                        "first_pass_approved": int(
                            artifact_payload.get("revision_count", 0),
                        ) == 0,
                        "revision_count": int(
                            artifact_payload.get("revision_count", 0),
                        ),
                        "accepted_as_on_brand": bool(
                            (quality_summary or {}).get("passed", True),
                        ),
                        "human_feedback_summary": None,
                        "cost_summary": {
                            "total_cost_usd": production_trace.total_cost_usd,
                            "total_input_tokens": production_trace.total_input_tokens,
                            "total_output_tokens": production_trace.total_output_tokens,
                        },
                        "quality_summary": quality_summary,
                        "promote_to_exemplar": False,
                    },
                )
            except Exception as exc:
                logger.debug("Failed to record outcome for job %s: %s", job_id, exc)

        return result
