"""Day 6: Full governed path integration test — poster_production.

Exercises the REAL governed pipeline with only external APIs mocked:
  route → readiness → policy → execute → trace → verify

Components under test (real, not mocked):
  - contracts.routing.route() — fast-path + LLM fallback
  - contracts.readiness.evaluate_readiness() — spec validation
  - middleware.policy.PolicyEvaluator — 4-gate policy chain
  - tools.executor.WorkflowExecutor — stage-by-stage execution
  - tools.orchestrate.run_governed() — full orchestrator chain
  - contracts.trace.TraceCollector — step/token/cost collection

External mocks:
  - utils.call_llm.call_llm — all LLM calls (routing, generation, QA)
  - tools.image.fal_client — image generation
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from contracts.artifact_spec import ArtifactFamily, ProvisionalArtifactSpec
from contracts.policy import PolicyAction
from contracts.readiness import evaluate_readiness
from contracts.routing import route
from middleware.policy import PolicyEvaluator, PolicyRequest
from tools.executor import WorkflowExecutor
from tools.workflow_schema import load_workflow
from utils.workflow_registry import get_deliverable_workflows


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _spans_db(tmp_path: Path) -> Path:
    """Empty spans.db for budget gate — zero usage."""
    db_path = tmp_path / "spans.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS spans (
            step_id TEXT PRIMARY KEY, model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
            cost_usd REAL NOT NULL, duration_ms REAL NOT NULL,
            job_id TEXT, step_type TEXT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def _policy_evaluator(_spans_db: Path) -> PolicyEvaluator:
    """PolicyEvaluator wired to real phase.yaml + empty spans."""
    return PolicyEvaluator(
        config_path=Path("config/phase.yaml"),
        spans_db_path=_spans_db,
    )


def _mock_call_llm(**kwargs: Any) -> dict[str, Any]:
    """Universal LLM mock that returns sensible responses by operation_type."""
    stable_prefix = kwargs.get("stable_prefix", [])
    system_content = stable_prefix[0].get("content", "") if stable_prefix else ""

    # Routing classifier
    if "routing classifier" in system_content.lower():
        return {
            "content": json.dumps({
                "workflow": "poster_production",
                "confidence": 0.9,
                "artifact_family": "poster",
                "reason": "Poster request",
            }),
            "model": "gpt-5.4-mini",
            "input_tokens": 80,
            "output_tokens": 40,
            "cost_usd": 0.0001,
        }

    # Brief expansion / generation
    if "expand" in system_content.lower() or "brief" in system_content.lower():
        return {
            "content": json.dumps({
                "composition": "Corporate poster with brand colours",
                "style": "Modern professional",
                "brand": "Standard corporate palette",
                "technical": "1080x1080px",
                "text_content": "Welcome to our event",
            }),
            "model": "gpt-5.4-mini",
            "input_tokens": 100,
            "output_tokens": 60,
            "cost_usd": 0.0002,
        }

    # Quality scoring
    if "score" in system_content.lower() or "quality" in system_content.lower():
        return {
            "content": json.dumps({"score": 4.2, "issues": []}),
            "model": "gpt-5.4-mini",
            "input_tokens": 120,
            "output_tokens": 30,
            "cost_usd": 0.0001,
        }

    # Brand voice
    if "brand voice" in system_content.lower():
        return {
            "content": json.dumps({
                "flagged": False,
                "issue": "",
                "register_detected": "formal",
            }),
            "model": "gpt-5.4-mini",
            "input_tokens": 60,
            "output_tokens": 20,
            "cost_usd": 0.0001,
        }

    # Default
    return {
        "content": "OK",
        "model": "gpt-5.4-mini",
        "input_tokens": 50,
        "output_tokens": 10,
        "cost_usd": 0.0001,
    }


# ---------------------------------------------------------------------------
# Step 1: Routing
# ---------------------------------------------------------------------------


class TestGovernedPathRouting:
    """Real routing — fast-path and LLM fallback both work."""

    def test_fast_path_routes_poster(self) -> None:
        result = route("create a poster for our annual event")
        assert result.workflow == "poster_production"
        assert result.fast_path is True
        assert result.token_cost == 0

    @patch("contracts.routing.call_llm", side_effect=_mock_call_llm)
    def test_llm_fallback_routes_correctly(self, mock_llm: MagicMock) -> None:
        # Brief without any artifact keywords to force LLM fallback
        result = route("I need something for the corporate campaign launch")
        assert result.workflow == "poster_production"
        assert result.fast_path is False
        assert result.token_cost > 0

    def test_routing_result_has_required_fields(self) -> None:
        result = route("design a poster")
        assert result.workflow is not None
        # job_id is None from fast-path (assigned by orchestrator, not router)
        assert isinstance(result.fast_path, bool)


# ---------------------------------------------------------------------------
# Step 2: Readiness
# ---------------------------------------------------------------------------


class TestGovernedPathReadiness:
    """Real readiness gate — evaluates spec completeness."""

    def test_minimal_spec_is_shapeable(self) -> None:
        spec = ProvisionalArtifactSpec(
            client_id="test-client",
            artifact_family=ArtifactFamily.poster,
            language="en",
            raw_brief="create a poster for our annual event",
        )
        result = evaluate_readiness(spec)
        assert result.status in {"shapeable", "ready"}
        assert result.completeness >= 0.0
        assert isinstance(result.missing_critical, list)

    def test_spec_with_objective_is_shapeable(self) -> None:
        """A spec with objective but missing delivery_format is shapeable."""
        spec = ProvisionalArtifactSpec(
            client_id="test-client",
            artifact_family=ArtifactFamily.poster,
            family_resolved=True,
            language="en",
            raw_brief="1080x1080 poster for annual gala",
            dimensions="1080x1080",
            tone="formal",
            objective="Promote annual gala event",
        )
        result = evaluate_readiness(spec)
        # Not blocked — shapeable or better
        assert result.status in {"ready", "shapeable"}
        assert "delivery_format" in result.missing_critical or result.status == "ready"


# ---------------------------------------------------------------------------
# Step 3: Policy
# ---------------------------------------------------------------------------


class TestGovernedPathPolicy:
    """Real policy evaluator — all gates with real config/phase.yaml."""

    def test_poster_production_allowed(
        self, _policy_evaluator: PolicyEvaluator
    ) -> None:
        decision = _policy_evaluator.evaluate(
            PolicyRequest(
                capability="poster_production",
                job_id="test-job",
                client_id="test-client",
            )
        )
        assert decision.action == PolicyAction.allow
        assert decision.gate == "all"
        # Day 3 guarantee: constraints snapshot present
        assert "gates_evaluated" in decision.constraints
        assert len(decision.constraints["gates_evaluated"]) == 4

    def test_inactive_phase_blocked(
        self, _policy_evaluator: PolicyEvaluator
    ) -> None:
        decision = _policy_evaluator.evaluate(
            PolicyRequest(capability="social_batch")
        )
        assert decision.action == PolicyAction.block
        assert decision.gate == "phase"


# ---------------------------------------------------------------------------
# Step 4: Execution + Trace
# ---------------------------------------------------------------------------


class TestGovernedPathExecution:
    """Real workflow executor with mocked tool implementations."""

    def test_poster_workflow_executes_all_stages(self) -> None:
        """WorkflowExecutor runs all 4 poster stages and produces trace."""

        def mock_tool(context: dict[str, Any]) -> dict[str, Any]:
            return {
                "status": "ok",
                "output": f"mock_{context.get('stage', 'unknown')}",
                "input_tokens": 50,
                "output_tokens": 25,
                "cost_usd": 0.0001,
            }

        executor = WorkflowExecutor(
            workflow_path="manifests/workflows/poster_production.yaml",
            tool_registry={
                "classify_artifact": mock_tool,
                "generate_poster": mock_tool,
                "image_generate": mock_tool,
                "visual_qa": mock_tool,
                "deliver": mock_tool,
            },
        )

        result = executor.run(job_context={
            "job_id": "test-governed-path",
            "client_id": "test-client",
            "artifact_family": "poster",
        })

        assert result["workflow"] == "poster_production"
        assert len(result["stages"]) == 4

        # Trace produced
        trace = result["trace"]
        assert trace is not None
        stage_names = [s["step_name"] for s in trace["steps"]]
        assert "intake" in stage_names
        assert "production" in stage_names
        assert "qa" in stage_names
        assert "delivery" in stage_names

        # Every step has timing
        for step in trace["steps"]:
            assert step["duration_ms"] >= 0


# ---------------------------------------------------------------------------
# Step 5: Deliverability
# ---------------------------------------------------------------------------


class TestGovernedPathDeliverability:
    """Verify poster_production is marked deliverable in YAML."""

    def test_poster_is_deliverable(self) -> None:
        deliverable = get_deliverable_workflows()
        assert "poster_production" in deliverable

    def test_poster_manifest_has_delivery_stage(self) -> None:
        pack = load_workflow("manifests/workflows/poster_production.yaml")
        has_delivery = any(s.role == "delivery" for s in pack.stages)
        assert has_delivery


# ---------------------------------------------------------------------------
# Step 6: Full chain — connects all links
# ---------------------------------------------------------------------------


class TestGovernedPathFullChain:
    """Single test connecting route → readiness → policy → execute → trace.

    Proves the full governed path holds together with real components.
    """

    @patch("middleware.policy.persist_policy_decision")
    def test_full_poster_governed_chain(
        self,
        mock_persist_policy: MagicMock,
        _policy_evaluator: PolicyEvaluator,
    ) -> None:
        # --- 1. Route ---
        routing_result = route("create a poster for our launch event")
        assert routing_result.workflow == "poster_production"

        # --- 2. Readiness ---
        family = ArtifactFamily.poster
        spec = ProvisionalArtifactSpec(
            client_id="test-client",
            artifact_family=family,
            family_resolved=True,
            language="en",
            raw_brief="create a poster for our launch event",
            objective="Promote product launch",
        )
        readiness = evaluate_readiness(spec)
        assert readiness.status in {"ready", "shapeable"}

        # --- 3. Policy ---
        decision = _policy_evaluator.evaluate(
            PolicyRequest(
                capability=routing_result.workflow,
                job_id=routing_result.job_id,
                client_id="test-client",
            )
        )
        assert decision.action == PolicyAction.allow
        # Policy decision was persisted
        assert mock_persist_policy.called
        persisted_decision = mock_persist_policy.call_args[0][0]
        assert persisted_decision.action == PolicyAction.allow
        assert "gates_evaluated" in persisted_decision.constraints

        # --- 4. Execute ---
        call_count: dict[str, int] = {}

        def counting_tool(context: dict[str, Any]) -> dict[str, Any]:
            stage = context.get("stage", "unknown")
            call_count[stage] = call_count.get(stage, 0) + 1
            return {
                "status": "ok",
                "output": f"executed_{stage}",
                "input_tokens": 50,
                "output_tokens": 25,
                "cost_usd": 0.0001,
            }

        executor = WorkflowExecutor(
            workflow_path="manifests/workflows/poster_production.yaml",
            tool_registry={
                "classify_artifact": counting_tool,
                "generate_poster": counting_tool,
                "image_generate": counting_tool,
                "visual_qa": counting_tool,
                "deliver": counting_tool,
            },
        )

        result = executor.run(job_context={
            "job_id": routing_result.job_id,
            "client_id": "test-client",
            "artifact_family": family.value,
            "language": "en",
            "routing": routing_result.model_dump(mode="json"),
            "readiness": readiness.model_dump(mode="json"),
            "policy": decision.model_dump(mode="json"),
        })

        # --- 5. Verify trace ---
        assert result["workflow"] == "poster_production"
        assert len(result["stages"]) == 4

        trace = result["trace"]
        assert trace is not None
        assert len(trace["steps"]) >= 4

        total_input = sum(s["input_tokens"] for s in trace["steps"])
        total_output = sum(s["output_tokens"] for s in trace["steps"])
        assert total_input > 0
        assert total_output > 0

        # --- 6. Verify governance metadata can be attached ---
        result["routing"] = routing_result.model_dump(mode="json")
        result["readiness"] = readiness.model_dump(mode="json")
        result["policy"] = decision.model_dump(mode="json")

        assert result["routing"]["workflow"] == "poster_production"
        assert result["readiness"]["status"] in {"ready", "shapeable"}
        assert result["policy"]["action"] == "allow"

        # --- 7. Verify every stage was called ---
        assert len(call_count) == 4, (
            f"Expected 4 unique stages, got {len(call_count)}: {call_count}"
        )


# ---------------------------------------------------------------------------
# Step 7: run_governed() — real orchestrator chain
# ---------------------------------------------------------------------------


class TestRunGoverned:
    """Exercise run_governed() directly to catch gate-level regressions.

    These tests mock LLM + image APIs but run the real orchestrator,
    including delivery gate, runtime readiness, and policy evaluation.
    """

    @patch("tools.orchestrate._ensure_job_row")
    @patch("tools.orchestrate._update_job_status")
    @patch("tools.orchestrate._persist_interpreted_intent")
    @patch("tools.brief_interpreter.call_llm", side_effect=_mock_call_llm)
    @patch("middleware.policy.persist_policy_decision")
    def test_poster_through_run_governed(
        self,
        _mock_persist_policy: MagicMock,
        _mock_brief_llm: MagicMock,
        _mock_persist_intent: MagicMock,
        _mock_update_status: MagicMock,
        _mock_ensure_job: MagicMock,
    ) -> None:
        """run_governed() completes a poster job with mock tools."""
        from tools.orchestrate import run_governed

        def mock_tool(context: dict[str, Any]) -> dict[str, Any]:
            return {
                "status": "ok",
                "output": f"mock_{context.get('stage', 'unknown')}",
                "input_tokens": 50,
                "output_tokens": 25,
                "cost_usd": 0.0001,
            }

        result = run_governed(
            raw_input="create a poster for our annual event",
            client_id="test-client",
            job_id="test-governed-poster",
            tool_registry={
                "classify_artifact": mock_tool,
                "generate_poster": mock_tool,
                "image_generate": mock_tool,
                "visual_qa": mock_tool,
                "deliver": mock_tool,
            },
        )

        assert result["workflow"] == "poster_production"
        assert result["routing"]["workflow"] == "poster_production"
        assert result["readiness"]["status"] in {"ready", "shapeable"}
        assert result["policy"]["action"] == "allow"

    @patch("tools.orchestrate._ensure_job_row")
    @patch("tools.orchestrate._update_job_status")
    @patch("tools.orchestrate._persist_interpreted_intent")
    @patch("tools.brief_interpreter.call_llm", side_effect=_mock_call_llm)
    @patch("middleware.policy.persist_policy_decision")
    def test_rework_not_blocked_by_delivery_gate(
        self,
        _mock_persist_policy: MagicMock,
        _mock_brief_llm: MagicMock,
        _mock_persist_intent: MagicMock,
        _mock_update_status: MagicMock,
        _mock_ensure_job: MagicMock,
    ) -> None:
        """Rework has a delivery stage but inherits deliverability — must not block."""
        from tools.orchestrate import run_governed

        def mock_tool(context: dict[str, Any]) -> dict[str, Any]:
            return {
                "status": "ok",
                "output": f"mock_{context.get('stage', 'unknown')}",
                "input_tokens": 50,
                "output_tokens": 25,
                "cost_usd": 0.0001,
            }

        # Verify rework passes the delivery gate (P1 regression).
        # The executor will fail at the rerun stage because there's no
        # real original workflow to re-run, but the important assertion
        # is that we get past the delivery gate without PolicyDenied.
        from tools.orchestrate import PolicyDenied

        try:
            result = run_governed(
                raw_input="rework the last deliverable — fix the headline alignment",
                client_id="test-client",
                job_id="test-governed-rework",
                tool_registry={
                    "trace_insight": mock_tool,
                    "quality_gate": mock_tool,
                    "deliver": mock_tool,
                },
            )
            # If it completes, verify routing
            assert result["workflow"] == "rework"
            assert result["routing"]["workflow"] == "rework"
            assert result["policy"]["action"] == "allow"
        except PolicyDenied:
            raise AssertionError(
                "Rework was blocked by the delivery gate — "
                "inherits_delivery should exempt it"
            )
        except Exception as exc:
            # Any other error (e.g. WorkflowExecutionError from missing
            # original_workflow) is fine — it means we got past the gates
            assert "PolicyDenied" not in type(exc).__name__
