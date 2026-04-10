"""Governed execution entry point — chains route, readiness, policy, execute.

Ensures that ``evaluate_readiness()`` and ``PolicyEvaluator.evaluate()``
run before ``WorkflowExecutor.run()`` for every production request.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from contracts.artifact_spec import ArtifactFamily, ProvisionalArtifactSpec
from contracts.policy import PolicyAction
from contracts.readiness import ReadinessResult, evaluate_readiness
from contracts.routing import RoutingResult, route
from middleware.policy import PolicyEvaluator, PolicyRequest
from middleware.runtime_controls import resolve_runtime_controls
from tools.executor import ToolCallable, WorkflowExecutor
from utils.workflow_registry import (
    get_deliverable_workflows,
    get_workflow_family,
    inherits_delivery,
)

logger = logging.getLogger(__name__)

_WORKFLOWS_DIR = Path("manifests/workflows")


_MALAY_MARKERS = {
    "saya", "mahu", "untuk", "dengan", "dan", "yang", "ini", "itu",
    "buat", "poster", "kempen", "tulis", "laporan", "sila", "tolong",
    "hasilkan", "reka", "bentuk", "perbaiki", "cuba", "semula",
}


def _detect_brief_language(text: str) -> str:
    """Lightweight Malay vs English detection from brief text.

    Uses word overlap with common Malay function words. Falls back to 'en'.
    ISO 639-1: 'ms' for Malay, 'en' for English.
    """
    words = set(text.lower().split())
    malay_hits = len(words & _MALAY_MARKERS)
    return "ms" if malay_hits >= 2 else "en"


class ReadinessError(Exception):
    """Raised when the spec is blocked by the readiness gate."""


class PolicyDenied(Exception):
    """Raised when the policy evaluator blocks the request."""


def _is_valid_uuid(value: str) -> bool:
    """Check if a string looks like a valid UUID (required for jobs.id column)."""
    import re
    return bool(re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        value.lower(),
    ))


def _ensure_job_row(
    job_id: str,
    client_id: str,
    raw_input: str,
    hermes_session_id: str | None,
) -> None:
    """Create or update the jobs row so downstream persistence has a real FK target.

    Uses INSERT ... ON CONFLICT to be idempotent. Sets status='running'.
    Skips gracefully if job_id is not a valid UUID (e.g. in test contexts).
    """
    if not _is_valid_uuid(job_id):
        logger.debug("Skipping job row creation for non-UUID job_id: %s", job_id)
        return

    try:
        from utils.database import get_cursor

        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (id, client_id, raw_input, hermes_session_id, status)
                VALUES (%(job_id)s, %(client_id)s, %(raw_input)s,
                        %(hermes_session_id)s, 'running')
                ON CONFLICT (id) DO UPDATE SET
                    status = 'running',
                    hermes_session_id = COALESCE(
                        EXCLUDED.hermes_session_id, jobs.hermes_session_id
                    ),
                    updated_at = now()
                """,
                {
                    "job_id": job_id,
                    "client_id": client_id,
                    "raw_input": raw_input[:2000] if raw_input else "",
                    "hermes_session_id": hermes_session_id,
                },
            )
    except Exception:
        logger.warning("Failed to ensure job row for %s", job_id, exc_info=True)


def _update_job_status(job_id: str, status: str) -> None:
    """Update job status to 'completed' or 'failed'."""
    if not _is_valid_uuid(job_id):
        return

    try:
        from utils.database import get_cursor

        with get_cursor() as cur:
            cur.execute(
                "UPDATE jobs SET status = %s, updated_at = now() WHERE id = %s",
                (status, job_id),
            )
    except Exception:
        logger.warning("Failed to update job %s status to %s", job_id, status, exc_info=True)


def _persist_interpreted_intent(
    job_id: str, intent_data: dict[str, object],
) -> None:
    """Persist canonical interpreted intent to jobs.interpreted_intent JSONB column.

    Called once after brief interpretation succeeds. This is the single source
    of truth for the structured parse used at runtime — downstream tools
    (copy generation, template selection, visual elaboration, adherence scoring)
    all consume this same intent from job_context, and this function ensures
    it survives in the database for reproducibility and offline analysis.
    """
    if not _is_valid_uuid(job_id) or not intent_data:
        return

    try:
        import json

        from utils.database import get_cursor

        with get_cursor() as cur:
            cur.execute(
                "UPDATE jobs SET interpreted_intent = %s, updated_at = now() WHERE id = %s",
                (json.dumps(intent_data, default=str), job_id),
            )
    except Exception:
        logger.warning(
            "Failed to persist interpreted intent for %s", job_id, exc_info=True,
        )


def _check_runtime_readiness(
    workflow_name: str,
    contract_strictness: str = "warn",
) -> tuple[list[str], list[str]]:
    """Pre-flight check for critical runtime dependencies.

    Returns:
        (hard_blocks, soft_warnings):
            hard_blocks: Issues that MUST stop execution (empty = proceed).
            soft_warnings: Degradations logged but non-blocking.

    Blocking policy:
        - OPENAI_API_KEY missing → always hard-block (every workflow needs LLM)
        - FAL_KEY missing → hard-block for visual workflows
        - DATABASE_URL missing → hard-block when contract_strictness == "reject"
          (enhanced/full posture), soft-warn otherwise (canva_baseline)
    """
    import os

    hard_blocks: list[str] = []
    soft_warnings: list[str] = []

    # 1. LLM API key — always required, nothing works without it
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        hard_blocks.append(
            "OPENAI_API_KEY not set — all LLM calls will fail"
        )

    # 2. Image generation backend (for visual workflows)
    _VISUAL_WORKFLOWS = frozenset({
        "poster_production", "brochure_production",
        "childrens_book_production", "social_batch",
    })
    if workflow_name in _VISUAL_WORKFLOWS:
        fal_key = os.environ.get("FAL_KEY", "")
        if not fal_key:
            hard_blocks.append(
                "FAL_KEY not set — image generation will fail"
            )

    # 3. Database availability — controls exemplar injection, knowledge
    # retrieval, trace persistence, and outcome memory.
    # Hard-block in strict quality modes; soft-warn in canva_baseline.
    db_url = os.environ.get("DATABASE_URL", "")
    db_issue = ""
    if not db_url:
        db_issue = (
            "DATABASE_URL not set — exemplar injection, knowledge "
            "retrieval, trace persistence, and outcome memory are inactive"
        )
    else:
        try:
            from utils.database import get_connection

            conn = get_connection()
            conn.close()
        except Exception:
            db_issue = (
                "DATABASE_URL set but Postgres unreachable — "
                "DB-backed features will silently no-op"
            )

    if db_issue:
        if contract_strictness == "reject":
            hard_blocks.append(db_issue)
        else:
            soft_warnings.append(db_issue)

    return hard_blocks, soft_warnings


def run_governed(
    raw_input: str,
    client_id: str,
    job_id: str,
    tool_registry: dict[str, ToolCallable] | None = None,
    *,
    quality_posture: str | None = None,
    budget_profile: str | None = None,
    platform: str | None = None,
    reference_image_path: str | None = None,
    reference_image_url: str | None = None,
    reference_notes: str | None = None,
    hermes_session_id: str | None = None,
    media_manifest: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Run the full governed execution chain.

    Steps:
        1. Route — determine workflow from input.
        2. Readiness — check if spec is ready, shapeable, or blocked.
        3. Policy — phase gate, tool gate, budget gate, cost gate.
        4. Execute — run the workflow with the tool registry.

    Args:
        raw_input: The operator's request text.
        client_id: Client identifier.
        job_id: Job identifier.
        tool_registry: Tool name -> callable mapping. If None, uses
            ``build_production_registry()``.

    Returns:
        dict with workflow results.

    Raises:
        ReadinessError: If spec is blocked.
        PolicyDenied: If policy evaluator blocks the request.
    """
    # Step 0: Ensure job row exists (hardening 1.2)
    _ensure_job_row(job_id, client_id, raw_input, hermes_session_id)

    # Step 1: Route
    routing_result: RoutingResult = route(raw_input, client_id=client_id, job_id=job_id)
    workflow_name = routing_result.workflow
    logger.info(
        "Governed: routed to '%s' (fast_path=%s, confidence=%.2f)",
        workflow_name,
        routing_result.fast_path,
        routing_result.confidence,
    )

    # Step 1.5: Interpret brief (hardening 2.3)
    interpreted_intent_data: dict[str, object] = {}
    try:
        from tools.brief_interpreter import interpret_brief

        interpretation = interpret_brief(raw_input)
        interpreted_intent_data = interpretation.intent.to_jsonb()
        # Persist canonical intent to DB for reproducibility (P1 fix)
        _persist_interpreted_intent(job_id, interpreted_intent_data)
    except Exception:
        logger.warning("Brief interpretation failed for job %s", job_id, exc_info=True)

    # Step 2: Readiness gate
    # Workflow was already routed + validated — family lookup must succeed.
    # If it fails, it's a config corruption bug worth surfacing, not hiding.
    family = ArtifactFamily(get_workflow_family(workflow_name))
    language = _detect_brief_language(raw_input)
    spec = ProvisionalArtifactSpec(
        client_id=client_id,
        artifact_family=family,
        family_resolved=True,  # family from validated workflow lookup
        language=language,
        raw_brief=raw_input,
    )
    readiness: ReadinessResult = evaluate_readiness(spec)

    if readiness.status == "blocked":
        raise ReadinessError(
            f"Spec blocked by readiness gate: {readiness.reason}. "
            f"Missing critical fields: {readiness.missing_critical}"
        )

    if readiness.status == "shapeable":
        logger.warning(
            "Governed: spec is shapeable (completeness=%.2f). "
            "Continuing with partial spec. Missing: %s",
            readiness.completeness,
            readiness.missing_critical,
        )

    # Step 3: Policy evaluation
    evaluator = PolicyEvaluator()
    policy_request = PolicyRequest(
        capability=workflow_name,
        job_id=job_id,
        client_id=client_id,
    )
    decision = evaluator.evaluate(policy_request)

    runtime_context = resolve_runtime_controls(
        client_id,
        quality_posture=quality_posture,
        budget_profile=budget_profile,
    )

    job_context: dict[str, Any] = {
        "job_id": job_id,
        "client_id": client_id,
        "raw_input": raw_input,
        "artifact_family": family.value,
        "language": spec.language,
        "client_default_language": runtime_context["language"],
        "routing": routing_result.model_dump(mode="json"),
        "readiness": readiness.model_dump(mode="json"),
        "design_system": routing_result.design_system,
        **runtime_context,
    }
    if interpreted_intent_data:
        job_context["interpreted_intent"] = interpreted_intent_data
        # If routing didn't select a design system (no client_id), use
        # inferred industry from brief interpretation to find one.
        if not routing_result.design_system:
            inferred_industry = str(interpreted_intent_data.get("industry", ""))
            if inferred_industry:
                try:
                    from contracts.routing import select_design_systems

                    # Build a synthetic client config from inferred fields
                    inferred_mood = str(interpreted_intent_data.get("mood", ""))
                    top_systems = select_design_systems(
                        client_id=None,
                        artifact_family=family.value,
                        override_industry=[inferred_industry],
                        override_mood=[inferred_mood] if inferred_mood else None,
                    )
                    if top_systems:
                        job_context["design_system"] = top_systems[0]
                        logger.info(
                            "Inferred design system from industry '%s': %s",
                            inferred_industry,
                            top_systems[0].get("name", "?") if isinstance(top_systems[0], dict) else top_systems[0],
                        )
                except Exception:
                    logger.debug(
                        "Design system inference from industry failed",
                        exc_info=True,
                    )
    if hermes_session_id:
        job_context["hermes_session_id"] = hermes_session_id
    if platform:
        job_context["platform"] = platform
    if reference_image_path:
        job_context["reference_image_path"] = reference_image_path
    if reference_image_url:
        job_context["reference_image_url"] = reference_image_url
    if reference_notes:
        job_context["reference_notes"] = reference_notes
    if media_manifest:
        job_context["media_manifest"] = media_manifest

    if decision.action == PolicyAction.block:
        raise PolicyDenied(
            f"Policy blocked: {decision.reason} (gate={decision.gate})"
        )

    if decision.action == PolicyAction.degrade:
        job_context["degraded"] = True
        logger.warning("Governed: policy degrading — %s", decision.reason)

    if decision.action == PolicyAction.escalate:
        job_context["escalate"] = True
        logger.warning("Governed: policy escalating — %s", decision.reason)

    # Step 4: Build registry if not provided
    if tool_registry is None:
        from tools.registry import build_production_registry

        tool_registry = build_production_registry()

    # Step 5: Pre-flight tool gate — validate all workflow tools against policy
    workflow_path = _WORKFLOWS_DIR / f"{workflow_name}.yaml"
    from tools.workflow_schema import load_workflow

    pack = load_workflow(workflow_path)
    for stage in pack.stages:
        for tool_name in stage.tools:
            tool_decision = evaluator.evaluate(PolicyRequest(
                capability=workflow_name,
                tool_name=tool_name,
                job_id=job_id,
                client_id=client_id,
            ))
            if tool_decision.action == PolicyAction.block:
                raise PolicyDenied(
                    f"Tool '{tool_name}' in stage '{stage.name}' blocked by policy: "
                    f"{tool_decision.reason} (gate={tool_decision.gate})"
                )

    # Step 5b: Runtime readiness — verify critical dependencies
    # Resolve contract strictness from quality posture to decide blocking policy.
    from middleware.quality_posture import get_quality_posture

    resolved_posture_name = str(
        job_context.get("quality_posture") or "canva_baseline"
    )
    try:
        posture_cfg = get_quality_posture(resolved_posture_name)
        strictness = posture_cfg.contract_strictness
    except Exception:
        strictness = "warn"

    hard_blocks, soft_warnings = _check_runtime_readiness(
        workflow_name, contract_strictness=strictness,
    )
    if hard_blocks:
        raise PolicyDenied(
            f"Runtime readiness hard-block for '{workflow_name}': "
            + "; ".join(hard_blocks)
        )
    if soft_warnings:
        job_context["runtime_degradations"] = soft_warnings
        logger.warning(
            "Governed: runtime degradations for '%s': %s",
            workflow_name,
            soft_warnings,
        )

    # Step 5c: Delivery support — fail early for non-deliverable workflows.
    # Reads deliverable: true/false from config/workflow_registry.yaml.
    # NOTE: flipping deliverable to true also requires a matching delivery
    # path in tools/registry.py _deliver() — YAML alone is not sufficient.
    # Workflows with inherits_delivery: true (e.g. rework) skip this gate
    # entirely — the original workflow is resolved at runtime in _deliver().
    # This means unsupported reworks defer failure to the delivery stage
    # rather than failing fast here. Acceptable because rework targets
    # previously-delivered artifacts, so the original lane is deliverable.
    deliverable_workflows = get_deliverable_workflows()
    has_delivery_stage = any(
        stage.role == "delivery" for stage in pack.stages
    )
    if (
        has_delivery_stage
        and workflow_name not in deliverable_workflows
        and not inherits_delivery(workflow_name)
    ):
        raise PolicyDenied(
            f"Workflow '{workflow_name}' has a delivery stage but delivery "
            f"is not yet implemented for this workflow type. "
            f"Only {sorted(deliverable_workflows)} can deliver final artifacts. "
            f"The system would waste tokens generating content that cannot "
            f"be rendered to a final PDF/PNG."
        )

    # Step 6: Execute workflow with tripwire scorer/reviser if available
    scorer_fn = tool_registry.get("_tripwire_scorer")
    reviser_fn = tool_registry.get("_tripwire_reviser")
    executor = WorkflowExecutor(
        workflow_path=workflow_path,
        tool_registry=tool_registry,
        client_id=client_id,
        scorer_fn=scorer_fn,
        reviser_fn=reviser_fn,
    )
    try:
        result = executor.run(job_context=job_context)
    except Exception:
        _update_job_status(job_id, "failed")
        raise

    _update_job_status(job_id, "completed")

    # Attach governance metadata
    result["routing"] = routing_result.model_dump(mode="json")
    result["readiness"] = readiness.model_dump(mode="json")
    result["policy"] = decision.model_dump(mode="json")

    return result
