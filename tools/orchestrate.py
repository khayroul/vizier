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
from tools.executor import ToolCallable, WorkflowExecutor
from utils.workflow_registry import get_workflow_family

logger = logging.getLogger(__name__)

_WORKFLOWS_DIR = Path("manifests/workflows")


class ReadinessError(Exception):
    """Raised when the spec is blocked by the readiness gate."""


class PolicyDenied(Exception):
    """Raised when the policy evaluator blocks the request."""


def run_governed(
    raw_input: str,
    client_id: str,
    job_id: str,
    tool_registry: dict[str, ToolCallable] | None = None,
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
    spec = ProvisionalArtifactSpec(
        client_id=client_id,
        artifact_family=family,
        language="en",
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

    job_context: dict[str, Any] = {
        "job_id": job_id,
        "client_id": client_id,
        "raw_input": raw_input,
        "routing": routing_result.model_dump(mode="json"),
        "readiness": readiness.model_dump(mode="json"),
    }

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

    # Step 5: Execute workflow
    workflow_path = _WORKFLOWS_DIR / f"{workflow_name}.yaml"
    executor = WorkflowExecutor(
        workflow_path=workflow_path,
        tool_registry=tool_registry,
        client_id=client_id,
    )
    result = executor.run(job_context=job_context)

    # Attach governance metadata
    result["routing"] = routing_result.model_dump(mode="json")
    result["readiness"] = readiness.model_dump(mode="json")
    result["policy"] = decision.model_dump(mode="json")

    return result
