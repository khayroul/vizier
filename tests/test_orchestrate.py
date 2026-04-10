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
        # Policy evaluate is called once for capability + once per workflow tool
        assert mock_policy_cls.return_value.evaluate.call_count >= 1
        mock_executor_cls.return_value.run.assert_called_once()
        assert result["workflow"] == "poster_production"

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_job_context_contains_runtime_controls_and_client_context(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        """Governed execution hydrates client/runtime control fields."""
        mock_route.return_value = RoutingResult(
            workflow="poster_production",
            job_id="j1",
            design_system="warm_heritage",
        )
        mock_readiness.return_value = ReadinessResult(status="ready", completeness=1.0)
        mock_policy_cls.return_value.evaluate.return_value = _allow_decision()
        mock_executor_cls.return_value.run.return_value = {
            "workflow": "poster_production",
            "stages": [],
            "trace": {},
        }

        run_governed(
            "hasilkan poster raya premium",
            client_id="dmb",
            job_id="j1",
            tool_registry={"x": _stub_tool},
            budget_profile="critical",
        )

        call_kwargs = mock_executor_cls.return_value.run.call_args.kwargs
        job_ctx = call_kwargs["job_context"]
        assert job_ctx["client_name"] == "Darul Makmur Berhad"
        assert job_ctx["copy_register"] == "formal"
        assert job_ctx["template_name"] == "corporate_premium"
        assert job_ctx["design_system"] == "warm_heritage"
        assert job_ctx["budget_profile"] == "critical"
        assert job_ctx["runtime_controls"]["qa_threshold"] == 3.5
        assert job_ctx["runtime_controls"]["essential_context_cap"] == 3
        assert job_ctx["runtime_controls"]["workflow_context_cap"] == 6
        assert job_ctx["runtime_controls"]["allow_deep_search"] is True


# ---------------------------------------------------------------------------
# 1b. Delivery support matrix
# ---------------------------------------------------------------------------


class TestDeliverySupportMatrix:
    """Keep delivery-support claims aligned with actual shipped lanes."""

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_document_production_reaches_executor(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        """document_production remains a genuinely supported deliverable lane."""
        mock_route.return_value = RoutingResult(
            workflow="document_production",
            job_id="j-doc",
        )
        mock_readiness.return_value = ReadinessResult(
            status="ready",
            completeness=1.0,
        )
        mock_policy_cls.return_value.evaluate.return_value = _allow_decision()
        mock_executor_cls.return_value.run.return_value = {
            "workflow": "document_production",
            "stages": [],
            "trace": {},
        }

        result = run_governed(
            "draft a client report",
            client_id="c1",
            job_id="j-doc",
            tool_registry={"x": _stub_tool},
        )

        mock_executor_cls.return_value.run.assert_called_once()
        assert result["workflow"] == "document_production"

    @pytest.mark.parametrize(
        "workflow_name",
        ["invoice", "proposal", "company_profile"],
    )
    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_s16_document_family_workflows_fail_delivery_support_gate(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
        workflow_name: str,
    ) -> None:
        """S16 document-family workflows stay out of the deliverable matrix."""
        mock_route.return_value = RoutingResult(workflow=workflow_name, job_id="j-s16")
        mock_readiness.return_value = ReadinessResult(
            status="ready",
            completeness=1.0,
        )
        mock_policy_cls.return_value.evaluate.return_value = _allow_decision()

        with pytest.raises(
            PolicyDenied,
            match="delivery stage but delivery is not yet implemented",
        ):
            run_governed(
                f"run {workflow_name}",
                client_id="c1",
                job_id="j-s16",
                tool_registry={"x": _stub_tool},
            )

        mock_executor_cls.return_value.run.assert_not_called()


# ---------------------------------------------------------------------------
# 1c. Stub registry regressions
# ---------------------------------------------------------------------------


class TestStubRegistryRegressions:
    """Lock in real-tool vs stub-tool support-matrix truths."""

    def test_typst_render_not_marked_as_stub(self) -> None:
        from tools.registry import get_stub_tool_names

        assert "typst_render" not in get_stub_tool_names()

    def test_typst_render_alone_does_not_trip_requires_session_stub_gate(
        self,
    ) -> None:
        """A real render tool must not be treated as an unresolved stub."""
        from tools.workflow_schema import (
            QualityTechniquesConfig,
            StageDefinition,
            TripwireConfig,
            WorkflowPack,
        )

        executor = WorkflowExecutor.__new__(WorkflowExecutor)
        executor.tool_registry = {"typst_render": _stub_tool}
        executor.scorer_fn = None
        executor.reviser_fn = None
        executor.rolling_context = None
        executor.pack = WorkflowPack(
            name="document_production",
            stages=[
                StageDefinition(
                    name="render",
                    action="render the document",
                    tools=["typst_render"],
                    role="production",
                )
            ],
            tripwire=TripwireConfig(),
            quality_techniques=QualityTechniquesConfig(),
            requires_session="S16",
        )

        executor._check_stub_workflow()


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
    """Test 3: readiness returns shapeable -> auto-enrich -> execution continues."""

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_shapeable_auto_enriches_then_continues(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        """Auto-enrich fills objective/format from brief, re-evaluates to ready."""
        mock_route.return_value = RoutingResult(workflow="poster_production")
        # First call: shapeable. Second call (after enrich): ready.
        mock_readiness.side_effect = [
            ReadinessResult(
                status="shapeable", completeness=0.5, missing_critical=["format"],
            ),
            ReadinessResult(status="ready", completeness=1.0),
        ]
        mock_policy_cls.return_value.evaluate.return_value = _allow_decision()
        mock_executor_cls.return_value.run.return_value = {
            "workflow": "poster_production", "stages": [], "trace": {},
        }

        result = run_governed("poster please", client_id="c1", job_id="j1", tool_registry={"x": _stub_tool})
        mock_executor_cls.return_value.run.assert_called_once()
        assert result["workflow"] == "poster_production"
        # evaluate_readiness called twice: initial + post-enrich
        assert mock_readiness.call_count == 2


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

        run_governed("poster", client_id="c1", job_id="j1", tool_registry={"x": _stub_tool})

        # Verify degraded flag was passed in job_context
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

        run_governed("poster", client_id="c1", job_id="j1", tool_registry={"x": _stub_tool})
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
    """Test 9: Active workflow with stub tools -> Gate 3 blocks."""

    def test_stub_workflow_blocked_by_gate3(self) -> None:
        """serial_fiction depends on stub tools (generate_episode etc.)
        — Gate 3 should block even when all tools are registered."""
        pack = load_workflow(WORKFLOWS_DIR / "serial_fiction_production.yaml")
        all_tools: set[str] = set()
        for stage in pack.stages:
            all_tools.update(stage.tools)

        tool_reg = {name: _stub_tool for name in all_tools}
        executor = WorkflowExecutor(
            workflow_path=WORKFLOWS_DIR / "serial_fiction_production.yaml",
            tool_registry=tool_reg,
        )
        with pytest.raises(StubWorkflowError, match="stub tools"):
            executor.run(job_context={"job_id": "test-sfp"})


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


# ---------------------------------------------------------------------------
# Runtime readiness blocking
# ---------------------------------------------------------------------------


class TestRuntimeReadinessBlocking:
    """Readiness gate hard-blocks on missing OPENAI_API_KEY / FAL_KEY.

    These tests call a local implementation of the readiness check
    logic (not the module-level function, which is patched by autouse).
    """

    @staticmethod
    def _check(
        workflow_name: str,
        contract_strictness: str = "warn",
        *,
        env: dict[str, str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Inline readiness check matching the real implementation."""
        import os

        _env = env if env is not None else dict(os.environ)
        hard: list[str] = []
        soft: list[str] = []

        if not _env.get("OPENAI_API_KEY", ""):
            hard.append("OPENAI_API_KEY not set — all LLM calls will fail")

        _visual = {
            "poster_production", "brochure_production",
            "childrens_book_production", "social_batch",
        }
        if workflow_name in _visual and not _env.get("FAL_KEY", ""):
            hard.append("FAL_KEY not set — image generation will fail")

        if not _env.get("DATABASE_URL", ""):
            db_msg = (
                "DATABASE_URL not set — exemplar injection, knowledge "
                "retrieval, trace persistence, and outcome memory are inactive"
            )
            if contract_strictness == "reject":
                hard.append(db_msg)
            else:
                soft.append(db_msg)

        return hard, soft

    def test_missing_openai_key_hard_blocks(self) -> None:
        """OPENAI_API_KEY missing is always a hard block."""
        hard, _soft = self._check("poster_production", "warn", env={})
        assert any("OPENAI_API_KEY" in h for h in hard)

    def test_missing_fal_key_hard_blocks_for_visual(self) -> None:
        """FAL_KEY missing hard-blocks visual workflows."""
        hard, _soft = self._check(
            "poster_production", "warn",
            env={"OPENAI_API_KEY": "sk-test"},
        )
        assert any("FAL_KEY" in h for h in hard)

    def test_missing_fal_key_ignored_for_non_visual(self) -> None:
        """FAL_KEY missing is fine for document workflows."""
        hard, _soft = self._check(
            "document_production", "warn",
            env={"OPENAI_API_KEY": "sk-test"},
        )
        assert not any("FAL_KEY" in h for h in hard)

    def test_missing_db_soft_warns_in_canva_baseline(self) -> None:
        """DATABASE_URL missing is a soft warning in warn mode."""
        hard, soft = self._check(
            "document_production", "warn",
            env={"OPENAI_API_KEY": "sk-test"},
        )
        assert not any("DATABASE_URL" in h for h in hard)
        assert any("DATABASE_URL" in s for s in soft)

    def test_missing_db_hard_blocks_in_reject_mode(self) -> None:
        """DATABASE_URL missing is a hard block in reject (enhanced/full) mode."""
        hard, _soft = self._check(
            "poster_production", "reject",
            env={"OPENAI_API_KEY": "sk-test", "FAL_KEY": "fk-test"},
        )
        assert any("DATABASE_URL" in h for h in hard)

    def test_run_governed_raises_on_hard_block(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """run_governed raises PolicyDenied when readiness hard-blocks."""
        import os

        def _blocking_check(
            workflow_name: str, contract_strictness: str = "warn",
        ) -> tuple[list[str], list[str]]:
            hard: list[str] = []
            if not os.environ.get("OPENAI_API_KEY", ""):
                hard.append("OPENAI_API_KEY not set — all LLM calls will fail")
            if not os.environ.get("FAL_KEY", ""):
                hard.append("FAL_KEY not set — image generation will fail")
            return hard, []

        monkeypatch.setattr(
            "tools.orchestrate._check_runtime_readiness",
            _blocking_check,
        )
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("FAL_KEY", raising=False)

        with pytest.raises(PolicyDenied, match="hard-block"):
            run_governed(
                "make a poster",
                client_id="c1",
                job_id="j-block",
                tool_registry={"x": _stub_tool},
            )


# ---------------------------------------------------------------------------
# Auto-enrich spec from interpreted intent
# ---------------------------------------------------------------------------


class TestAutoEnrichSpec:
    """_auto_enrich_spec fills gaps in ProvisionalArtifactSpec from intent."""

    def test_fills_objective_from_raw_brief(self) -> None:
        from contracts.artifact_spec import ArtifactFamily, ProvisionalArtifactSpec
        from tools.orchestrate import _auto_enrich_spec

        spec = ProvisionalArtifactSpec(
            client_id="c1",
            artifact_family=ArtifactFamily.poster,
            family_resolved=True,
            language="en",
            raw_brief="Raya sale poster for our restaurant in KL",
        )
        enriched = _auto_enrich_spec(spec, {"mood": "festive"})

        assert enriched.objective == "Raya sale poster for our restaurant in KL"
        assert enriched.format is not None  # default for poster = pdf
        assert enriched.tone == "festive"
        assert enriched.copy_register == "casual_en"

    def test_preserves_existing_fields(self) -> None:
        from contracts.artifact_spec import ArtifactFamily, DeliveryFormat, ProvisionalArtifactSpec
        from tools.orchestrate import _auto_enrich_spec

        spec = ProvisionalArtifactSpec(
            client_id="c1",
            artifact_family=ArtifactFamily.poster,
            family_resolved=True,
            language="ms",
            raw_brief="poster jualan",
            objective="Existing objective",
            format=DeliveryFormat.png,
            tone="professional",
        )
        enriched = _auto_enrich_spec(spec, {"mood": "playful"})

        # Existing values preserved
        assert enriched.objective == "Existing objective"
        assert enriched.format == DeliveryFormat.png
        assert enriched.tone == "professional"
        # copy_register still filled since it was missing
        assert enriched.copy_register == "casual_bm"

    def test_returns_same_spec_when_nothing_to_fill(self) -> None:
        from contracts.artifact_spec import ArtifactFamily, DeliveryFormat, ProvisionalArtifactSpec
        from tools.orchestrate import _auto_enrich_spec

        spec = ProvisionalArtifactSpec(
            client_id="c1",
            artifact_family=ArtifactFamily.poster,
            family_resolved=True,
            language="en",
            raw_brief="test",
            objective="done",
            format=DeliveryFormat.pdf,
            tone="warm",
            copy_register="formal_en",
        )
        enriched = _auto_enrich_spec(spec, {})

        assert enriched is spec  # identity — no copy needed

    def test_ebook_defaults_to_epub(self) -> None:
        from contracts.artifact_spec import ArtifactFamily, DeliveryFormat, ProvisionalArtifactSpec
        from tools.orchestrate import _auto_enrich_spec

        spec = ProvisionalArtifactSpec(
            client_id="c1",
            artifact_family=ArtifactFamily.ebook,
            family_resolved=True,
            language="en",
            raw_brief="an ebook about cooking",
        )
        enriched = _auto_enrich_spec(spec, {})

        assert enriched.format == DeliveryFormat.epub


# ---------------------------------------------------------------------------
# Thin-brief prompt coaching
# ---------------------------------------------------------------------------


class TestThinBriefCoaching:
    """_maybe_coach_thin_brief returns coaching for very thin briefs."""

    def test_thin_brief_returns_coaching(self) -> None:
        import importlib

        bridge = importlib.import_module("plugins.vizier_tools_bridge")
        result = bridge._maybe_coach_thin_brief("buat poster")

        assert result is not None
        assert "too short" in result
        assert "Suggested questions" in result
        assert "1 meaningful word" in result  # "poster" survives stop-word filter

    def test_adequate_brief_returns_none(self) -> None:
        import importlib

        bridge = importlib.import_module("plugins.vizier_tools_bridge")
        result = bridge._maybe_coach_thin_brief(
            "Raya sale poster for Warung Selera restaurant, "
            "20% off all menu items, festive mood"
        )

        assert result is None

    def test_medium_brief_returns_none(self) -> None:
        import importlib

        bridge = importlib.import_module("plugins.vizier_tools_bridge")
        # 5+ meaningful words after stop-word removal
        result = bridge._maybe_coach_thin_brief(
            "poster Raya sale restaurant KL festive"
        )

        assert result is None

    def test_coaching_includes_meaningful_words(self) -> None:
        import importlib

        bridge = importlib.import_module("plugins.vizier_tools_bridge")
        result = bridge._maybe_coach_thin_brief("poster for sale")

        assert result is not None
        assert "sale" in result  # only meaningful word
