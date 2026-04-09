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
from typing import Any, cast
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
        from tools.executor import ToolCallable, WorkflowExecutor
        from tools.workflow_schema import StageDefinition

        captured_contexts: list[dict[str, Any]] = []

        def tool_a(ctx: dict[str, Any]) -> dict[str, Any]:
            captured_contexts.append(dict(ctx))
            return {"status": "ok", "output": "from_tool_a", "key_a": "value_a"}

        def tool_b(ctx: dict[str, Any]) -> dict[str, Any]:
            captured_contexts.append(dict(ctx))
            return {"status": "ok", "output": "from_tool_b"}

        registry = cast(dict[str, Any], {"tool_a": tool_a, "tool_b": tool_b})

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

        run_governed(
            "make a poster",
            client_id="c1",
            job_id="j1",
            tool_registry=cast(dict[str, Any], {"x": lambda ctx: {"status": "ok"}}),
        )

        # Check the job_context arg passed to executor.run()
        call_args = mock_executor_cls.return_value.run.call_args
        job_ctx = call_args.kwargs.get("job_context") or call_args[1].get("job_context")
        assert job_ctx["artifact_family"] == "poster"
        assert "language" in job_ctx

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_job_context_contains_budget_profile_and_brand_fields(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        """Brand-aware job context includes runtime controls and client defaults."""
        from contracts.readiness import ReadinessResult
        from contracts.routing import RoutingResult
        from contracts.policy import PolicyAction, PolicyDecision
        from tools.orchestrate import run_governed

        mock_route.return_value = RoutingResult(
            workflow="poster_production",
            job_id="j1",
            design_system="warm_heritage",
        )
        mock_readiness.return_value = ReadinessResult(
            status="ready", completeness=1.0
        )
        mock_policy_cls.return_value.evaluate.return_value = PolicyDecision(
            action=PolicyAction.allow, reason="ok", gate="all",
            job_id="j1", client_id="dmb", capability="poster_production",
        )
        mock_executor_cls.return_value.run.return_value = {
            "workflow": "poster_production", "stages": [], "trace": {},
        }

        run_governed(
            "hasilkan poster raya premium",
            client_id="dmb",
            job_id="j1",
            budget_profile="critical",
            tool_registry=cast(dict[str, Any], {"x": lambda ctx: {"status": "ok"}}),
        )

        job_ctx = mock_executor_cls.return_value.run.call_args.kwargs["job_context"]
        assert job_ctx["budget_profile"] == "critical"
        assert job_ctx["client_name"] == "Darul Makmur Berhad"
        assert job_ctx["template_name"] == "corporate_premium"
        assert job_ctx["runtime_controls"]["knowledge_card_cap"] == 6
        assert job_ctx["runtime_controls"]["essential_context_cap"] == 3
        assert job_ctx["runtime_controls"]["workflow_context_cap"] == 6
        assert job_ctx["runtime_controls"]["allow_deep_search"] is True


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

        run_governed(
            "make a poster",
            client_id="c1",
            job_id="j1",
            tool_registry=cast(dict[str, Any], {"x": lambda ctx: {"status": "ok"}}),
        )

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


# ---------------------------------------------------------------------------
# 5b.6 — Generic executor semantics
# ---------------------------------------------------------------------------


class TestGenericExecutorSemantics:
    """Generic executor enforces terminal statuses and guardrails."""

    def test_guardrails_run_for_generic_production_stage(self) -> None:
        """WorkflowExecutor invokes parallel guardrails on production output."""
        from tools.executor import ToolCallable, WorkflowExecutor
        from tools.workflow_schema import load_workflow

        def classify_tool(context: dict[str, Any]) -> dict[str, Any]:
            return {"status": "ok", "output": "poster"}

        def copy_tool(context: dict[str, Any]) -> dict[str, Any]:
            return {
                "status": "ok",
                "output": "copy_ready",
                "poster_copy": "Headline with enough words for guardrails",
            }

        def image_tool(context: dict[str, Any]) -> dict[str, Any]:
            return {
                "status": "ok",
                "output": "image_ready",
                "image_path": "/tmp/poster.png",
            }

        def qa_tool(context: dict[str, Any]) -> dict[str, Any]:
            return {"status": "ok", "output": "qa_passed"}

        def deliver_tool(context: dict[str, Any]) -> dict[str, Any]:
            return {"status": "ok", "output": "delivered"}

        executor = WorkflowExecutor(
            workflow_path=Path("manifests/workflows/poster_production.yaml"),
            tool_registry={
                "classify_artifact": classify_tool,
                "generate_poster": copy_tool,
                "image_generate": image_tool,
                "visual_qa": qa_tool,
                "deliver": deliver_tool,
            },
        )

        with patch(
            "middleware.guardrails.run_parallel_guardrails",
            return_value=[{"issue_type": "register_mismatch", "detail": "tone drift"}],
        ) as mock_guardrails:
            result = executor.run(job_context={"job_id": "guardrails-001"})

        mock_guardrails.assert_called_once()
        production_stage = next(
            stage for stage in result["stages"] if stage["stage"] == "production"
        )
        assert production_stage["guardrail_flags"][0]["issue_type"] == "register_mismatch"

    def test_canonical_stub_tool_stops_active_workflow(self) -> None:
        """Active workflows stop instead of succeeding through production stubs."""
        from tools.executor import WorkflowExecutionError, WorkflowExecutor
        from tools.registry import build_production_registry

        registry = build_production_registry()
        registry["classify_artifact"] = lambda ctx: {
            "status": "ok",
            "output": "research",
        }

        executor = WorkflowExecutor(
            workflow_path=Path("manifests/workflows/research.yaml"),
            tool_registry=registry,
        )

        with pytest.raises(WorkflowExecutionError, match="research") as exc:
            executor.run(job_context={"job_id": "stub-stop-001"})

        result = exc.value.result
        assert result["status"] == "stub"
        assert result["failed_stage"] == "gather"

    def test_stage_knowledge_is_injected_into_prompt_and_trace(self) -> None:
        """Declarative stage knowledge becomes live prompt/runtime context."""
        from tools.executor import ToolCallable, WorkflowExecutor
        from tools.workflow_schema import (
            QualityTechniquesConfig,
            StageDefinition,
            TripwireConfig,
            WorkflowPack,
        )

        captured_prompts: list[str] = []

        def tool(ctx: dict[str, Any]) -> dict[str, Any]:
            captured_prompts.append(str(ctx["prompt"]))
            return {"status": "ok", "output": "copy_ready", "poster_copy": "Headline"}

        executor = WorkflowExecutor.__new__(WorkflowExecutor)
        executor.tool_registry = {"generate_poster": cast(ToolCallable, tool)}
        executor.scorer_fn = None
        executor.reviser_fn = None
        executor.rolling_context = None
        executor.pack = WorkflowPack(
            name="knowledge_test",
            stages=[StageDefinition(
                name="production",
                action="make a poster",
                tools=["generate_poster"],
                role="production",
                knowledge=["client", "swipe"],
            )],
            tripwire=TripwireConfig(enabled=False),
            quality_techniques=QualityTechniquesConfig(),
        )

        with patch(
            "utils.embeddings.embed_text",
            return_value=[0.1, 0.2],
        ), patch(
            "utils.knowledge.assemble_context",
            return_value={
                "client_config": {
                    "client_name": "Demo Client",
                    "defaults": {"copy_register": "formal", "style_hint": "premium"},
                    "brand": {"primary_color": "#123456"},
                },
                "knowledge_cards": [
                    {"id": "card-1", "title": "Brand CTA", "content": "CTA must be visible."},
                ],
                "essential_cards": [
                    {"id": "card-0", "title": "Seasonal Mood", "content": "Warm festive season."},
                ],
                "workflow_cards": [
                    {"id": "card-1", "title": "Brand CTA", "content": "CTA must be visible."},
                ],
                "context_layers": {
                    "identity_loaded": True,
                    "seasonal_loaded": True,
                    "essential_cards_count": 1,
                    "workflow_cards_count": 1,
                    "deep_search_invoked": False,
                },
            },
        ):
            result = executor.run(job_context={
                "job_id": "knowledge-001",
                "client_id": "demo",
                "runtime_controls": {
                    "identity_context_cap": 4,
                    "essential_context_cap": 1,
                    "workflow_context_cap": 2,
                    "knowledge_card_cap": 2,
                },
            })

        assert "Knowledge context" in captured_prompts[0]
        assert "CTA must be visible" in captured_prompts[0]
        assert "Essential knowledge" in captured_prompts[0]
        assert "Identity context" in captured_prompts[0]
        stage = result["stages"][0]
        assert stage["knowledge_cards_used"] == ["card-0", "card-1"]
        assert stage["context_layers"]["essential_cards_count"] == 1
        assert stage["context_layers"]["workflow_cards_count"] == 1
        assert result["trace"]["knowledge_cards_used"] == ["card-0", "card-1"]
        assert result["trace"]["context_layer_summary"]["identity_loaded"] is True
        assert result["trace"]["context_layer_summary"]["essential_cards_count"] == 1
        assert result["trace"]["context_layer_summary"]["workflow_cards_count"] == 1

    def test_visual_qa_blocks_low_quality_artifacts(self) -> None:
        """Registry visual QA fails closed when the real artifact does not pass."""
        from tools.registry import _visual_qa

        with patch(
            "tools.visual_pipeline.evaluate_visual_artifact",
            return_value={
                "passed": False,
                "weighted_score": 2.8,
                "qa_threshold": 3.2,
                "nima_score": 3.9,
                "nima_action": "regenerate",
                "critique": {"cta_visibility": {"score": 2.0, "issues": ["CTA hidden"]}},
                "guardrail_flags": [],
                "input_tokens": 40,
                "output_tokens": 20,
                "cost_usd": 0.01,
            },
        ):
            result = _visual_qa({
                "job_context": {
                    "client_id": "dmb",
                    "artifact_family": "poster",
                    "language": "ms",
                    "copy_register": "formal",
                    # Disable retries so test stays focused on fail-closed behaviour.
                    "runtime_controls": {"qa_threshold": 3.2, "qa_max_retries": 0},
                },
                "artifact_payload": {
                    "image_path": "/tmp/poster.png",
                    "poster_copy": "Headline",
                    "template_name": "poster_default",
                },
            })

        assert result["status"] == "error"
        assert result["score"] == 2.8
        assert result["qa_threshold"] == 3.2

    def test_visual_qa_critique_then_revise_regenerates(
        self, tmp_path: Path,
    ) -> None:
        """QA revision loop regenerates image with critique and re-evaluates."""
        from tools.registry import _visual_qa

        fail_result = {
            "passed": False,
            "weighted_score": 2.5,
            "qa_threshold": 3.2,
            "nima_score": 3.5,
            "nima_action": "accept",
            "critique": {
                "layout_balance": {
                    "score": 2.0,
                    "issues": ["Image is off-centre"],
                },
            },
            "guardrail_flags": [],
            "input_tokens": 40,
            "output_tokens": 20,
            "cost_usd": 0.01,
        }
        pass_result = {
            **fail_result,
            "passed": True,
            "weighted_score": 3.8,
        }
        call_count = {"n": 0}

        def _eval_side_effect(**kwargs: object) -> dict[str, object]:
            call_count["n"] += 1
            if call_count["n"] == 1:
                return fail_result  # type: ignore[return-value]
            return pass_result  # type: ignore[return-value]

        revised_img = tmp_path / "revised.png"
        revised_img.write_bytes(b"\x89PNG" + b"\x00" * 60)

        with (
            patch(
                "tools.visual_pipeline.evaluate_visual_artifact",
                side_effect=_eval_side_effect,
            ),
            patch(
                "tools.image.generate_image",
                return_value=b"\x89PNG" + b"\x00" * 60,
            ),
            patch(
                "tools.image.select_image_model",
                return_value="fal-ai/flux/dev",
            ),
        ):
            result = _visual_qa({
                "job_context": {
                    "client_id": "dmb",
                    "artifact_family": "poster",
                    "language": "en",
                    "copy_register": "neutral",
                    "runtime_controls": {
                        "qa_threshold": 3.2,
                        "qa_max_retries": 1,
                    },
                },
                "artifact_payload": {
                    "image_path": "/tmp/poster.png",
                    "poster_copy": "Headline",
                    "template_name": "poster_default",
                },
            })

        assert result["status"] == "ok"
        assert result["score"] == 3.8
        assert call_count["n"] == 2

    def test_delivery_uses_resolved_template_and_job_output_dir(self, tmp_path: Path) -> None:
        """Poster delivery resolves template aliases and isolates outputs by job."""
        from tools.registry import _deliver

        expected_pdf = tmp_path / "poster_default.pdf"
        expected_pdf.write_text("pdf")

        with patch(
            "tools.publish.assemble_poster_pdf",
            return_value=expected_pdf,
        ) as mock_assemble:
            result = _deliver({
                "job_context": {
                    "job_id": "job-123",
                    "client_id": "dmb",
                    "template_name": "corporate_premium",
                    "routing": {"workflow": "poster_production"},
                },
                "artifact_payload": {
                    "image_path": "/tmp/poster.png",
                    "poster_copy": "{\"headline\": \"Sale\"}",
                    "quality_verdict": {"passed": True},
                },
                "stage_results": [],
            })

        assert result["status"] == "ok"
        assert result["template_name"] == "poster_default"
        assert mock_assemble.call_args.kwargs["template_name"] == "poster_default"
        assert mock_assemble.call_args.kwargs["output_dir"].name == "job-123"
