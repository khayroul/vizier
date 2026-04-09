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
from utils.workflow_registry import get_workflow_family

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

    # Step 2: Readiness gate
    try:
        family = ArtifactFamily(get_workflow_family(workflow_name))
    except (KeyError, ValueError):
        family = ArtifactFamily.document
    language = _detect_brief_language(raw_input)
    spec = ProvisionalArtifactSpec(
        client_id=client_id,
        artifact_family=family,
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
