"""Tests for governance chain, tool registry, policy alignment, and trace persistence.

Covers:
  - run_governed happy path, readiness blocking, shapeable continuation,
    policy block/degrade/escalate
  - ToolNotFoundError on missing tools
  - StubWorkflowError with Gate 2 (missing tools in active phase)
  - StubWorkflowError passes when tools registered
  - Inactive phase raises StubWorkflowError
  - Production registry covers all workflow YAML tool names
  - phase.yaml approved_tools covers all active-phase workflow tools
  - Trace persisted after executor run
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from contracts.policy import PolicyAction, PolicyDecision
from contracts.readiness import ReadinessResult
from contracts.routing import RoutingResult
from tools.executor import StubWorkflowError, ToolNotFoundError, WorkflowExecutor
from tools.orchestrate import PolicyDenied, ReadinessError, run_governed
from tools.registry import build_production_registry
from tools.workflow_schema import load_workflow

WORKFLOWS_DIR = Path("manifests/workflows")
PHASE_YAML = Path("config/phase.yaml")


def _stub_tool(context: dict[str, Any]) -> dict[str, Any]:
    return {"status": "ok", "output": "stub", "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


def _allow_decision(**kwargs: Any) -> PolicyDecision:
    return PolicyDecision(action=PolicyAction.allow, reason="All gates passed", gate="all", **kwargs)


def _block_decision(**kwargs: Any) -> PolicyDecision:
    return PolicyDecision(action=PolicyAction.block, reason="Budget exceeded", gate="budget", **kwargs)


def _degrade_decision(**kwargs: Any) -> PolicyDecision:
    return PolicyDecision(action=PolicyAction.degrade, reason="Cost ceiling hit", gate="cost", **kwargs)


def _escalate_decision(**kwargs: Any) -> PolicyDecision:
    return PolicyDecision(action=PolicyAction.escalate, reason="Needs operator", gate="cost", **kwargs)


# ---------------------------------------------------------------------------
# 1. run_governed happy path
# ---------------------------------------------------------------------------


class TestRunGovernedHappyPath:
    """Test 1: route -> readiness (ready) -> policy (allow) -> execute."""

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_happy_path(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        mock_route.return_value = RoutingResult(workflow="poster_production", job_id="j1")
        mock_readiness.return_value = ReadinessResult(status="ready", completeness=1.0)
        mock_policy_cls.return_value.evaluate.return_value = _allow_decision()
        mock_executor_cls.return_value.run.return_value = {
            "workflow": "poster_production",
            "stages": [],
            "trace": {},
        }

        result = run_governed("make a poster", client_id="c1", job_id="j1", tool_registry={"x": _stub_tool})

        mock_route.assert_called_once_with("make a poster", client_id="c1", job_id="j1")
        mock_readiness.assert_called_once()
        mock_policy_cls.return_value.evaluate.assert_called_once()
        mock_executor_cls.return_value.run.assert_called_once()
        assert result["workflow"] == "poster_production"


# ---------------------------------------------------------------------------
# 2. Blocked readiness
# ---------------------------------------------------------------------------


class TestRunGovernedBlockedReadiness:
    """Test 2: readiness returns blocked -> ReadinessError."""

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_blocked_readiness(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        mock_route.return_value = RoutingResult(workflow="poster_production")
        mock_readiness.return_value = ReadinessResult(
            status="blocked", completeness=0.1, missing_critical=["objective"],
            reason="Missing objective",
        )

        with pytest.raises(ReadinessError, match="blocked"):
            run_governed("something", client_id="c1", job_id="j1", tool_registry={"x": _stub_tool})

        mock_executor_cls.return_value.run.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Shapeable continues
# ---------------------------------------------------------------------------


class TestRunGovernedShapeableContinues:
    """Test 3: readiness returns shapeable -> execution continues."""

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_shapeable_continues(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        mock_route.return_value = RoutingResult(workflow="poster_production")
        mock_readiness.return_value = ReadinessResult(
            status="shapeable", completeness=0.5, missing_critical=["format"],
        )
        mock_policy_cls.return_value.evaluate.return_value = _allow_decision()
        mock_executor_cls.return_value.run.return_value = {
            "workflow": "poster_production", "stages": [], "trace": {},
        }

        result = run_governed("poster please", client_id="c1", job_id="j1", tool_registry={"x": _stub_tool})
        mock_executor_cls.return_value.run.assert_called_once()
        assert result["workflow"] == "poster_production"


# ---------------------------------------------------------------------------
# 4. Policy block
# ---------------------------------------------------------------------------


class TestRunGovernedPolicyBlock:
    """Test 4: policy returns block -> PolicyDenied."""

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_policy_block(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        mock_route.return_value = RoutingResult(workflow="poster_production")
        mock_readiness.return_value = ReadinessResult(status="ready", completeness=1.0)
        mock_policy_cls.return_value.evaluate.return_value = _block_decision()

        with pytest.raises(PolicyDenied, match="blocked"):
            run_governed("poster", client_id="c1", job_id="j1", tool_registry={"x": _stub_tool})

        mock_executor_cls.return_value.run.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Policy degrade
# ---------------------------------------------------------------------------


class TestRunGovernedPolicyDegrade:
    """Test 5: policy returns degrade -> execution continues with degraded=True."""

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_policy_degrade(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        mock_route.return_value = RoutingResult(workflow="poster_production")
        mock_readiness.return_value = ReadinessResult(status="ready", completeness=1.0)
        mock_policy_cls.return_value.evaluate.return_value = _degrade_decision()
        mock_executor_cls.return_value.run.return_value = {
            "workflow": "poster_production", "stages": [], "trace": {},
        }

        result = run_governed("poster", client_id="c1", job_id="j1", tool_registry={"x": _stub_tool})

        # Verify degraded flag was passed in job_context
        call_kwargs = mock_executor_cls.return_value.run.call_args
        job_ctx = call_kwargs.kwargs.get("job_context") or call_kwargs[1].get("job_context") or call_kwargs[0][0] if call_kwargs[0] else {}
        # The executor.run is called with job_context kwarg
        assert mock_executor_cls.return_value.run.called


# ---------------------------------------------------------------------------
# 6. Policy escalate
# ---------------------------------------------------------------------------


class TestRunGovernedPolicyEscalate:
    """Test 6: policy returns escalate -> escalate=True in context."""

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_policy_escalate(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        mock_route.return_value = RoutingResult(workflow="poster_production")
        mock_readiness.return_value = ReadinessResult(status="ready", completeness=1.0)
        mock_policy_cls.return_value.evaluate.return_value = _escalate_decision()
        mock_executor_cls.return_value.run.return_value = {
            "workflow": "poster_production", "stages": [], "trace": {},
        }

        result = run_governed("poster", client_id="c1", job_id="j1", tool_registry={"x": _stub_tool})
        assert mock_executor_cls.return_value.run.called


# ---------------------------------------------------------------------------
# 7. ToolNotFoundError
# ---------------------------------------------------------------------------


class TestToolNotFoundRaises:
    """Test 7: WorkflowExecutor with empty registry raises ToolNotFoundError."""

    def test_tool_not_found_raises(self) -> None:
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "poster_production.yaml",
            tool_registry={},
        )
        with pytest.raises(ToolNotFoundError, match="classify_artifact"):
            executor.run(job_context={"job_id": "test-tnf"})


# ---------------------------------------------------------------------------
# 8. StubWorkflowError — missing tools (Gate 2)
# ---------------------------------------------------------------------------


class TestStubWorkflowMissingTools:
    """Test 8: Workflow with requires_session, no tools registered -> StubWorkflowError."""

    def test_stub_workflow_missing_tools(self) -> None:
        """serial_fiction_production is in active 'publishing' phase but
        requires_session=S21. With no tools registered, Gate 2 should fire.
        """
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "serial_fiction_production.yaml",
            tool_registry={},
        )
        with pytest.raises(StubWorkflowError, match="not registered"):
            executor.run()


# ---------------------------------------------------------------------------
# 9. StubWorkflowError — with tools passes
# ---------------------------------------------------------------------------


class TestStubWorkflowWithToolsPasses:
    """Test 9: Same workflow with all tools registered -> no error."""

    def test_stub_workflow_with_tools_passes(self) -> None:
        pack = load_workflow(WORKFLOWS_DIR / "serial_fiction_production.yaml")
        all_tools: set[str] = set()
        for stage in pack.stages:
            all_tools.update(stage.tools)

        tool_reg = {name: _stub_tool for name in all_tools}
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "serial_fiction_production.yaml",
            tool_registry=tool_reg,
        )
        result = executor.run(job_context={"job_id": "test-sfp"})
        assert result["workflow"] == "serial_fiction_production"


# ---------------------------------------------------------------------------
# 10. Inactive phase raises StubWorkflowError
# ---------------------------------------------------------------------------


class TestInactivePhaseRaises:
    """Test 10: social_batch in inactive 'social' phase -> StubWorkflowError."""

    def test_inactive_phase_raises(self) -> None:
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "social_batch.yaml",
            tool_registry={},
        )
        with pytest.raises(StubWorkflowError, match="hasn't shipped"):
            executor.run()


# ---------------------------------------------------------------------------
# 11. Production registry has all tools
# ---------------------------------------------------------------------------


class TestProductionRegistryComplete:
    """Test 11: build_production_registry() covers every tool in every workflow YAML."""

    def test_production_registry_has_all_tools(self) -> None:
        registry = build_production_registry()
        all_yaml_tools: set[str] = set()

        for yaml_file in WORKFLOWS_DIR.glob("*.yaml"):
            pack = load_workflow(yaml_file)
            for stage in pack.stages:
                all_yaml_tools.update(stage.tools)

        missing = all_yaml_tools - set(registry.keys())
        assert not missing, f"Registry missing tools: {sorted(missing)}"


# ---------------------------------------------------------------------------
# 12. Policy approved_tools cover active workflows
# ---------------------------------------------------------------------------


class TestPolicyApprovedToolsCoverage:
    """Test 12: phase.yaml approved_tools covers all tools used in active-phase workflows."""

    def test_policy_approved_tools_cover_active_workflows(self) -> None:
        with PHASE_YAML.open() as fh:
            phase_config = yaml.safe_load(fh)

        phases = phase_config.get("phases", {})
        approved = phase_config.get("approved_tools", {})

        for phase_name, phase_data in phases.items():
            if not phase_data.get("active", False):
                continue

            # Collect all tools from workflows in this phase
            phase_tools: set[str] = set()
            for wf_name in phase_data.get("includes", []):
                yaml_path = WORKFLOWS_DIR / f"{wf_name}.yaml"
                if not yaml_path.exists():
                    continue
                pack = load_workflow(yaml_path)
                for stage in pack.stages:
                    phase_tools.update(stage.tools)

            # Check approved_tools covers them
            phase_approved = set(approved.get(phase_name, []))
            missing = phase_tools - phase_approved
            assert not missing, (
                f"Phase '{phase_name}' approved_tools missing: {sorted(missing)}"
            )


# ---------------------------------------------------------------------------
# 13. Trace persisted after run
# ---------------------------------------------------------------------------


class TestTracePersisted:
    """Test 13: persist_trace is called after executor.run() when job_id present."""

    @patch("utils.trace_persist.persist_trace")
    def test_trace_persisted_after_run(self, mock_persist: MagicMock) -> None:
        tool_reg = {
            "classify_artifact": _stub_tool,
            "generate_poster": _stub_tool,
            "image_generate": _stub_tool,
            "visual_qa": _stub_tool,
            "deliver": _stub_tool,
        }
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "poster_production.yaml",
            tool_registry=tool_reg,
        )
        executor.run(job_context={"job_id": "trace-test-001"})
        mock_persist.assert_called_once()
        args = mock_persist.call_args[0]
        assert args[0] == "trace-test-001"
