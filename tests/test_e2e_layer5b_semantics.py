"""Layer 5b — Production-registry semantics tests.

Unlike Layer 5 (which uses mock registries to test orchestration wiring),
these tests use the REAL production registry to verify actual stage dataflow,
non-stub delivery, tripwire activation, tool-gate enforcement, and
guardrail execution.

External calls (LLM, fal.ai) are still mocked at the HTTP level, but the
registry tools, executor, and middleware run their real code paths.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_spans_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import utils.spans as spans_mod

    test_db = tmp_path / "spans.db"
    monkeypatch.setattr(spans_mod, "DB_PATH", test_db)
    spans_mod.init_db(test_db)
    return test_db


def _mock_openai_response(content: str = "mock") -> MagicMock:
    """Build a mock httpx response for OpenAI."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    return resp


# ---------------------------------------------------------------------------
# 5b.1 — Multi-tool stage context chaining
# ---------------------------------------------------------------------------


class TestMultiToolContextChaining:
    """Later tools in a stage see earlier tools' outputs."""

    def test_second_tool_receives_first_tool_output(self) -> None:
        """In a 2-tool stage, tool 2 sees tool 1's output via current_output."""
        from contracts.trace import TraceCollector
        from tools.executor import WorkflowExecutor
        from tools.workflow_schema import StageDefinition

        captured_contexts: list[dict[str, Any]] = []

        def tool_a(ctx: dict[str, Any]) -> dict[str, Any]:
            captured_contexts.append(dict(ctx))
            return {"status": "ok", "output": "from_tool_a", "key_a": "value_a"}

        def tool_b(ctx: dict[str, Any]) -> dict[str, Any]:
            captured_contexts.append(dict(ctx))
            return {"status": "ok", "output": "from_tool_b"}

        registry = {"tool_a": tool_a, "tool_b": tool_b}

        # Build a minimal workflow with a 2-tool stage
        executor = WorkflowExecutor.__new__(WorkflowExecutor)
        executor.tool_registry = registry
        executor.scorer_fn = None
        executor.reviser_fn = None
        executor.rolling_context = None

        from tools.workflow_schema import (
            QualityTechniquesConfig,
            TripwireConfig,
            WorkflowPack,
        )

        executor.pack = WorkflowPack(
            name="test_workflow",
            description="test",
            stages=[StageDefinition(
                name="multi_tool_stage",
                action="test both tools",
                tools=["tool_a", "tool_b"],
                role="production",
            )],
            tripwire=TripwireConfig(),
            quality_techniques=QualityTechniquesConfig(),
        )

        result = executor.run(job_context={"job_id": "test"})

        # tool_b should have received tool_a's output via current_output
        assert len(captured_contexts) == 2
        tool_b_ctx = captured_contexts[1]
        assert "current_output" in tool_b_ctx
        # key_a is unique to tool_a — proves tool_b can see tool_a's data
        assert tool_b_ctx["current_output"]["key_a"] == "value_a"
        # previous_tool_result also carries tool_a's output
        assert tool_b_ctx["previous_tool_result"]["key_a"] == "value_a"


# ---------------------------------------------------------------------------
# 5b.2 — Delivery fail-closed for non-poster workflows
# ---------------------------------------------------------------------------


class TestDeliveryFailClosed:
    """Non-poster workflows get explicit stub status, not false positive."""

    def test_document_delivery_returns_stub(self) -> None:
        """Document workflow delivery returns stub status."""
        from tools.registry import _deliver

        result = _deliver({
            "job_context": {"routing": {"workflow": "document_production"}},
            "stage_results": [],
        })
        assert result["status"] == "stub"
        assert "not_implemented" in result["output"]

    def test_ebook_delivery_returns_stub(self) -> None:
        """eBook workflow delivery returns stub status."""
        from tools.registry import _deliver

        result = _deliver({
            "job_context": {"routing": {"workflow": "ebook_production"}},
            "stage_results": [],
        })
        assert result["status"] == "stub"


# ---------------------------------------------------------------------------
# 5b.3 — artifact_family and language in job_context
# ---------------------------------------------------------------------------


class TestArtifactFamilyPropagation:
    """run_governed injects artifact_family and language into job_context."""

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_job_context_contains_artifact_family(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        """job_context passed to executor.run() includes artifact_family."""
        from contracts.readiness import ReadinessResult
        from contracts.routing import RoutingResult
        from contracts.policy import PolicyAction, PolicyDecision
        from tools.orchestrate import run_governed

        mock_route.return_value = RoutingResult(
            workflow="poster_production", job_id="j1"
        )
        mock_readiness.return_value = ReadinessResult(
            status="ready", completeness=1.0
        )
        mock_policy_cls.return_value.evaluate.return_value = PolicyDecision(
            action=PolicyAction.allow, reason="ok", gate="all",
            job_id="j1", client_id="c1", capability="poster_production",
        )
        mock_executor_cls.return_value.run.return_value = {
            "workflow": "poster_production", "stages": [], "trace": {},
        }

        run_governed("make a poster", client_id="c1", job_id="j1",
                     tool_registry={"x": lambda ctx: {"status": "ok"}})

        # Check the job_context arg passed to executor.run()
        call_args = mock_executor_cls.return_value.run.call_args
        job_ctx = call_args.kwargs.get("job_context") or call_args[1].get("job_context")
        assert job_ctx["artifact_family"] == "poster"
        assert "language" in job_ctx


# ---------------------------------------------------------------------------
# 5b.4 — Per-tool policy gate enforcement
# ---------------------------------------------------------------------------


class TestPerToolPolicyGate:
    """Policy evaluator is called for each tool in the workflow."""

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_policy_checked_per_tool(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        """Policy evaluate is called once per workflow + once per tool."""
        from contracts.readiness import ReadinessResult
        from contracts.routing import RoutingResult
        from contracts.policy import PolicyAction, PolicyDecision
        from tools.orchestrate import run_governed

        mock_route.return_value = RoutingResult(
            workflow="poster_production", job_id="j1"
        )
        mock_readiness.return_value = ReadinessResult(
            status="ready", completeness=1.0
        )
        mock_policy_cls.return_value.evaluate.return_value = PolicyDecision(
            action=PolicyAction.allow, reason="ok", gate="all",
            job_id="j1", client_id="c1", capability="poster_production",
        )
        mock_executor_cls.return_value.run.return_value = {
            "workflow": "poster_production", "stages": [], "trace": {},
        }

        run_governed("make a poster", client_id="c1", job_id="j1",
                     tool_registry={"x": lambda ctx: {"status": "ok"}})

        # Should be called > 1 (capability + tools)
        eval_calls = mock_policy_cls.return_value.evaluate.call_count
        assert eval_calls > 1, (
            f"Policy evaluate called {eval_calls} time(s), "
            "expected >1 (capability + per-tool checks)"
        )

        # At least one call should include a tool_name
        calls_with_tools = [
            c for c in mock_policy_cls.return_value.evaluate.call_args_list
            if c.args[0].tool_name is not None
        ]
        assert len(calls_with_tools) >= 1


# ---------------------------------------------------------------------------
# 5b.5 — Tripwire scorer/reviser wired into production registry
# ---------------------------------------------------------------------------


class TestTripwireWiring:
    """Production registry includes tripwire scorer and reviser."""

    def test_registry_has_tripwire_scorer(self) -> None:
        """_tripwire_scorer is in the production registry."""
        from tools.registry import build_production_registry

        registry = build_production_registry()
        assert "_tripwire_scorer" in registry
        assert callable(registry["_tripwire_scorer"])

    def test_registry_has_tripwire_reviser(self) -> None:
        """_tripwire_reviser is in the production registry."""
        from tools.registry import build_production_registry

        registry = build_production_registry()
        assert "_tripwire_reviser" in registry
        assert callable(registry["_tripwire_reviser"])

    @patch("utils.call_llm.call_llm")
    def test_scorer_returns_score_and_critique(
        self, mock_llm: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Tripwire scorer calls LLM and returns structured score+critique."""
        _setup_spans_db(tmp_path, monkeypatch)
        mock_llm.return_value = {
            "content": json.dumps({
                "score": 4.2,
                "critique": {
                    "relevance": 4, "completeness": 5,
                    "clarity": 4, "accuracy": 4,
                    "issues": [],
                },
            }),
            "model": "gpt-5.4-mini",
            "input_tokens": 50,
            "output_tokens": 30,
            "cost_usd": 0.0001,
        }

        from tools.registry import _tripwire_scorer

        result = _tripwire_scorer({
            "output": {"output": "Some generated content"},
            "stage": "generate_poster",
            "threshold": 3.0,
        })
        assert "score" in result
        assert result["score"] == 4.2
        assert "critique" in result
