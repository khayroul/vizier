"""IT-1: Poster from Vague Brief — Full Chain Integration Test.

Validates: S11 routing → S6 contracts → S9 workflow executor → S13 visual pipeline
           → S7 tracing → S10a persistence.

Input: "buatkan poster Raya untuk DMB" (vague BM brief)

External APIs mocked: call_llm (OpenAI), generate_image (fal.ai), fal_client.
Internal functions run real: routing, workflow executor, trace, database.

BUG FINDING: The spec expects this input to trigger LLM routing because it's
"vague BM". However, fast_path_route matches on the word "poster" in the input,
so route() resolves via fast-path at zero tokens. The vagueness is correctly
handled DOWNSTREAM by the readiness gate (returns "shapeable"), not by routing.
This test documents both the actual behavior and an alternative LLM-path test.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.requires_db

from contracts.artifact_spec import (
    ArtifactFamily,
    ArtifactSpec,
    DeliveryFormat,
    DeliveryRequirements,
    ProvisionalArtifactSpec,
    QARequirements,
    StructuralRequirements,
    StyleRequirements,
)
from contracts.readiness import evaluate_readiness
from contracts.routing import RoutingResult, route
from contracts.trace import TraceCollector
from tools.executor import WorkflowExecutor
from tools.workflow_schema import load_workflow
from utils.database import get_cursor
from utils.trace_persist import collect_and_persist, load_trace, persist_trace

# ---------------------------------------------------------------------------
# Test image: 1x1 red PNG for mock image generation
# ---------------------------------------------------------------------------

_TEST_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_call_llm_response(content: str, **kwargs: Any) -> dict[str, Any]:
    """Build a mock call_llm return value."""
    return {
        "content": content,
        "model": "gpt-5.4-mini",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.0001,
    }


def _make_llm_side_effect(**kwargs: Any) -> dict[str, Any]:
    """Contextual mock for call_llm based on operation_type or content."""
    stable_prefix = kwargs.get("stable_prefix", [])
    variable_suffix = kwargs.get("variable_suffix", [])
    operation_type = kwargs.get("operation_type")
    response_format = kwargs.get("response_format")

    # Detect what kind of LLM call this is from the system prompt
    system_content = ""
    if stable_prefix:
        system_content = stable_prefix[0].get("content", "")

    user_content = ""
    if variable_suffix:
        user_content = variable_suffix[0].get("content", "")

    # Routing classification
    if "routing classifier" in system_content.lower():
        return _mock_call_llm_response(json.dumps({
            "workflow": "poster_production",
            "confidence": 0.85,
            "artifact_family": "poster",
            "reason": "BM poster request for Raya campaign",
        }))

    # Brief expansion
    if "expand" in system_content.lower() or "brief" in system_content.lower():
        return _mock_call_llm_response(json.dumps({
            "composition": "Festive Raya poster with green and gold theme",
            "style": "Traditional Malay festive design with modern touches",
            "brand": "DMB corporate colours: dark green #1B4332, gold #D4A843",
            "technical": "1080x1080px, CMYK-safe, 300dpi",
            "text_content": "Selamat Hari Raya Aidilfitri dari DMB",
        }))

    # Refinement
    if "refinement" in system_content.lower() or "shaping" in system_content.lower():
        return _mock_call_llm_response(json.dumps({
            "questions": ["What dimensions do you need?", "Any specific Raya motifs?"],
            "inferred": {
                "artifact_family": "poster",
                "language": "bm",
                "tone": "formal",
                "objective": "Poster Raya untuk kempen DMB 2025",
            },
        }))

    # Quality scoring / critique
    if "score" in system_content.lower() or "quality" in system_content.lower():
        return _mock_call_llm_response(json.dumps({
            "score": 4.0,
            "issues": [],
        }))

    # Brand voice check
    if "brand voice" in system_content.lower():
        return _mock_call_llm_response(json.dumps({
            "flagged": False,
            "issue": "",
            "register_detected": "formal",
        }))

    # Default: generic response
    return _mock_call_llm_response("OK")


class TestRoutingBehavior:
    """IT-1 Step 3-4: Verify routing for vague BM brief."""

    def test_vague_bm_brief_routes_via_fast_path(self) -> None:
        """BUG/FINDING: 'buatkan poster Raya untuk DMB' matches fast-path on 'poster'.

        The spec expected LLM routing for this vague input, but the fast-path
        pattern 'poster|banner|flyer|visual|graphic' catches it first.
        This is architecturally correct — vagueness is handled by readiness gate,
        not by routing. Documenting as a spec-vs-implementation mismatch.
        """
        result = route("buatkan poster Raya untuk DMB")
        assert result.workflow == "poster_production"
        # FINDING: This resolves via fast-path, not LLM
        assert result.fast_path is True, (
            "SPEC MISMATCH: Spec expected LLM routing for this vague input, "
            "but fast-path matches on 'poster' keyword. "
            "See architecture: vagueness handled by readiness gate, not routing."
        )
        assert result.token_cost == 0

    @patch("contracts.routing.call_llm", side_effect=_make_llm_side_effect)
    def test_genuinely_vague_brief_routes_via_llm(self, mock_llm: MagicMock) -> None:
        """A brief without artifact keywords correctly triggers LLM routing.

        Using input that doesn't match any fast-path pattern.
        """
        result = route("saya perlukan sesuatu untuk kempen Raya DMB")
        assert result.fast_path is False, (
            "A brief without artifact keywords should not match fast-path"
        )
        assert result.workflow == "poster_production"
        assert result.token_cost > 0, "LLM routing should consume tokens"
        mock_llm.assert_called_once()


class TestReadinessGate:
    """IT-1 Step 7-8: Readiness evaluation on vague brief."""

    def test_vague_brief_is_shapeable(self) -> None:
        """A vague brief with just artifact_family + language returns 'shapeable'."""
        spec = ProvisionalArtifactSpec(
            client_id="dmb",
            artifact_family=ArtifactFamily.poster,
            language="bm",
            raw_brief="buatkan poster Raya untuk DMB",
        )
        result = evaluate_readiness(spec)
        assert result.status == "shapeable", (
            f"Expected 'shapeable' for vague brief, got '{result.status}'. "
            f"Reason: {result.reason}"
        )
        assert "objective" in result.missing_critical

    @patch("contracts.routing.call_llm")
    def test_refinement_improves_spec(self, mock_llm: MagicMock) -> None:
        """One refinement cycle calls LLM and increments cycle counter."""
        # Configure mock to return refinement-compatible JSON
        mock_llm.return_value = {
            "content": json.dumps({
                "questions": ["What dimensions do you need?", "Any specific Raya motifs?"],
                "inferred": {
                    "artifact_family": "poster",
                    "language": "bm",
                    "tone": "formal",
                    "objective": "Poster Raya untuk kempen DMB 2025",
                },
            }),
            "model": "gpt-5.4-mini",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.0001,
        }

        from contracts.routing import refine_request

        spec, questions = refine_request(
            raw_input="buatkan poster Raya untuk DMB",
            client_id="dmb",
        )

        # LLM was called for refinement
        assert mock_llm.called, "call_llm should be invoked for refinement"
        # Cycle incremented
        assert spec.cycle == 1
        # Questions returned from LLM
        assert len(questions) >= 1, (
            f"Expected >= 1 question from refinement, got {len(questions)}"
        )


class TestWorkflowExecution:
    """IT-1 Step 9: Execute poster_production workflow with mocked externals."""

    @patch("tools.image.fal_client")
    @patch("utils.call_llm.httpx")
    def test_workflow_executor_runs_all_stages(
        self, mock_httpx: MagicMock, mock_fal: MagicMock, test_job
    ) -> None:
        """WorkflowExecutor runs all 4 stages and produces a trace."""
        # Mock tools that the workflow stages reference
        def mock_tool(context: dict[str, Any]) -> dict[str, Any]:
            return {
                "status": "ok",
                "output": f"Mock output for stage {context.get('stage', 'unknown')}",
                "input_tokens": 50,
                "output_tokens": 25,
                "cost_usd": 0.0001,
            }

        tool_registry = {
            "classify_artifact": mock_tool,
            "generate_poster": mock_tool,
            "image_generate": mock_tool,
            "visual_qa": mock_tool,
            "deliver": mock_tool,
        }

        executor = WorkflowExecutor(
            workflow_path="manifests/workflows/poster_production.yaml",
            tool_registry=tool_registry,
        )

        result = executor.run(job_context={
            "job_id": test_job["id"],
            "client_name": "DMB",
            "copy_register": "formal",
            "platform": "instagram",
        })

        assert result["workflow"] == "poster_production"
        assert len(result["stages"]) == 4, (
            f"poster_production has 4 stages, executor ran {len(result['stages'])}"
        )

        # Verify trace was collected
        trace = result["trace"]
        assert trace is not None
        assert len(trace["steps"]) == 4
        stage_names = [step["step_name"] for step in trace["steps"]]
        assert "intake" in stage_names
        assert "production" in stage_names
        assert "qa" in stage_names
        assert "delivery" in stage_names


class TestTraceCollection:
    """IT-1 Step 10: TraceCollector captures steps with proof dicts."""

    def test_trace_collector_captures_steps(self) -> None:
        """TraceCollector records multiple steps with timing and proof."""
        collector = TraceCollector(job_id="test-job-123")

        with collector.step("routing") as trace:
            trace.input_tokens = 0
            trace.output_tokens = 0
            trace.proof = {"method": "fast_path", "confidence": 1.0}

        with collector.step("production") as trace:
            trace.input_tokens = 500
            trace.output_tokens = 200
            trace.cost_usd = 0.001
            trace.proof = {"model": "gpt-5.4-mini"}

        with collector.step("scoring") as trace:
            trace.input_tokens = 300
            trace.output_tokens = 100
            trace.proof = {"nima_score": 6.8, "brand_voice_match": 0.92}

        production_trace = collector.finalise()
        assert len(production_trace.steps) == 3
        assert production_trace.steps[0].step_name == "routing"
        assert production_trace.steps[2].proof["nima_score"] == 6.8
        assert production_trace.total_input_tokens == 800
        assert production_trace.total_output_tokens == 300

    def test_step_trace_has_duration(self) -> None:
        """Each StepTrace has duration_ms auto-set by context manager."""
        collector = TraceCollector(job_id="test-dur")
        with collector.step("test_step") as trace:
            _ = sum(range(1000))  # tiny bit of work
        assert collector.steps[0].duration_ms > 0


class TestTracePersistence:
    """IT-1 Step 13: Trace persisted to database."""

    def test_persist_trace_writes_to_jobs(self, test_job) -> None:
        """persist_trace() writes ProductionTrace JSONB to jobs table."""
        collector = TraceCollector(job_id=test_job["id"])
        with collector.step("test_persist") as trace:
            trace.input_tokens = 100
            trace.proof = {"test": True}

        production_trace = collector.finalise()
        persist_trace(test_job["id"], production_trace)

        loaded = load_trace(test_job["id"])
        assert loaded is not None
        assert len(loaded.steps) == 1
        assert loaded.steps[0].step_name == "test_persist"
        assert loaded.steps[0].input_tokens == 100

    def test_collect_and_persist_round_trip(self, test_job) -> None:
        """collect_and_persist() finalises + stores in one call."""
        collector = TraceCollector(job_id=test_job["id"])
        with collector.step("routing") as trace:
            trace.proof = {"fast_path": True}
        with collector.step("production") as trace:
            trace.input_tokens = 500

        returned_trace = collect_and_persist(test_job["id"], collector)
        assert len(returned_trace.steps) == 2

        # Verify it's in the DB
        loaded = load_trace(test_job["id"])
        assert loaded is not None
        assert len(loaded.steps) == 2


class TestVisualPipelineComponents:
    """IT-1 Step 11-12: NIMA and critique functions are callable."""

    def test_nima_prescreen_categorises_scores(self) -> None:
        """nima_prescreen returns correct action for score ranges."""
        from tools.visual_scoring import nima_prescreen

        assert nima_prescreen(3.0)["action"] == "regenerate"
        assert nima_prescreen(5.5)["action"] == "proceed_with_caution"
        assert nima_prescreen(8.0)["action"] == "pass"

    @patch("tools.visual_scoring.call_llm", side_effect=_make_llm_side_effect)
    def test_critique_4dim_called_with_correct_params(
        self, mock_llm: MagicMock
    ) -> None:
        """critique_4dim calls GPT-5.4-mini for each quality dimension."""
        from tools.visual_scoring import critique_4dim

        results = critique_4dim(
            image_description="Test poster with green and gold Raya theme",
            brief={
                "composition": "Festive Raya poster",
                "style": "Traditional Malay",
            },
        )

        assert isinstance(results, dict)
        # Each dimension should have a score and issues list
        for dim_name, dim_result in results.items():
            assert "score" in dim_result
            assert "issues" in dim_result
            assert isinstance(dim_result["score"], float)
            assert isinstance(dim_result["issues"], list)

        # Verify GPT-5.4-mini was used (check call args)
        for call_args in mock_llm.call_args_list:
            assert call_args.kwargs.get("model") == "gpt-5.4-mini"

    def test_select_image_model_routing(self) -> None:
        """select_image_model routes correctly by job characteristics."""
        from tools.image import select_image_model

        # BM text-heavy → nano-banana-pro
        assert "nano-banana" in select_image_model(language="ms", has_text=True)
        # Photorealistic → flux-pro
        assert "flux-pro" in select_image_model(style="photorealistic")
        # Draft → nano-banana (free)
        assert "nano-banana" in select_image_model(style="draft")
        # Children's book → kontext
        assert "kontext" in select_image_model(artifact_family="childrens_book")
        # Default → flux/dev
        assert "flux/dev" in select_image_model()


class TestFeedbackCreation:
    """IT-1 Step 15: Feedback record created with awaiting status."""

    def test_feedback_created_awaiting(
        self, test_client, test_job, test_artifact
    ) -> None:
        """A delivered artifact gets a feedback record with status='awaiting'."""
        feedback_id = str(uuid.uuid4())
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status)
                VALUES (%s, %s, %s, %s, 'awaiting')
                """,
                (feedback_id, test_job["id"], test_artifact["id"], test_client["id"]),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT feedback_status, delivered_at FROM feedback WHERE id = %s",
                (feedback_id,),
            )
            row = cur.fetchone()

        assert row["feedback_status"] == "awaiting"
        assert row["delivered_at"] is not None, "delivered_at should be auto-set by trigger"


class TestVisualLineage:
    """IT-1 Step 16: Visual lineage recording."""

    def test_visual_lineage_recorded(self, db_cursor, test_job) -> None:
        """record_visual_lineage writes to the visual_lineage table."""
        from tools.visual_scoring import record_visual_lineage

        record_visual_lineage(
            job_id=test_job["id"],
            role="generated",
            reason="Primary poster via flux/dev",
        )

        with get_cursor() as cur:
            cur.execute(
                "SELECT role, selection_reason FROM visual_lineage WHERE job_id = %s",
                (test_job["id"],),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["role"] == "generated"
        assert "flux/dev" in row["selection_reason"]


class TestObservabilityGap:
    """IT-1 Step 14: Langfuse/observability — documents missing modules.

    BUG: middleware/observability.py and middleware/policy.py are NOT on main.
    They exist on the S8 branch but haven't been merged yet.
    trace_to_langfuse() and dual_trace() cannot be tested until S8 merges.
    """

    def test_observability_module_not_on_main(self) -> None:
        """KNOWN GAP: middleware/observability.py not yet merged to main.

        S8 branch has dual_trace() and trace_to_langfuse() but they are not
        available on main. This blocks IT-1 steps 14 (Langfuse verification).
        """
        observability_path = Path("middleware/observability.py")
        if not observability_path.exists():
            pytest.skip(
                "middleware/observability.py not on main — S8 branch not merged. "
                "trace_to_langfuse() and dual_trace() untestable until merge."
            )

    def test_policy_module_not_on_main(self) -> None:
        """KNOWN GAP: middleware/policy.py not yet merged to main.

        S8 branch has PolicyEvaluator but it's not available on main.
        Policy gate evaluation cannot be tested until S8 merges.
        """
        policy_path = Path("middleware/policy.py")
        if not policy_path.exists():
            pytest.skip(
                "middleware/policy.py not on main — S8 branch not merged. "
                "PolicyEvaluator untestable until merge."
            )


class TestEndToEndChain:
    """IT-1: Full chain from routing through trace persistence."""

    @patch("tools.visual_scoring.call_llm", side_effect=_make_llm_side_effect)
    @patch("middleware.guardrails.call_llm", side_effect=_make_llm_side_effect)
    def test_full_poster_chain(
        self,
        mock_guardrails_llm: MagicMock,
        mock_scoring_llm: MagicMock,
        test_client,
        test_job,
    ) -> None:
        """End-to-end: route → load workflow → execute → trace → persist.

        Mocks all LLM calls and image generation. Verifies the chain connects.
        """
        # Step 3: Route
        routing_result = route("buatkan poster Raya untuk DMB")
        assert routing_result.workflow == "poster_production"

        # Step 5: Load workflow
        pack = load_workflow("manifests/workflows/poster_production.yaml")
        assert pack.name == "poster_production"

        # Step 6: Create ArtifactSpec
        spec = ArtifactSpec(
            client_id=test_client["id"],
            job_id=test_job["id"],
            structural=StructuralRequirements(
                artifact_family=ArtifactFamily.poster,
                language="bm",
                dimensions="1080x1080",
            ),
            style=StyleRequirements(
                tone="formal",
                copy_register="formal_bm",
                design_system="corporate_premium",
            ),
            qa=QARequirements(
                tripwire_threshold=3.5,
                max_retries=2,
            ),
            delivery=DeliveryRequirements(
                format=DeliveryFormat.png,
                resolution_dpi=300,
            ),
            objective="Poster Raya 2025 untuk kempen DMB",
        )
        assert spec.model_preference == "gpt-5.4-mini"

        # Step 9: Execute workflow with mocked tools
        def mock_tool(context: dict[str, Any]) -> dict[str, Any]:
            return {
                "status": "ok",
                "output": f"Mocked {context.get('stage', '?')}",
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
            "job_id": test_job["id"],
            "client_name": "DMB",
            "copy_register": "formal",
            "platform": "instagram",
        })

        # Step 10: Verify trace
        trace_data = result["trace"]
        assert len(trace_data["steps"]) == 4
        for step in trace_data["steps"]:
            assert "step_name" in step
            assert "duration_ms" in step

        # Step 13: Persist trace
        from contracts.trace import ProductionTrace

        trace = ProductionTrace.model_validate(trace_data)
        persist_trace(test_job["id"], trace)

        # Verify persistence round-trip
        loaded = load_trace(test_job["id"])
        assert loaded is not None
        assert len(loaded.steps) == 4

        # Store routing result on job
        routing_json = json.dumps(routing_result.model_dump(mode="json"), default=str)
        with get_cursor() as cur:
            cur.execute(
                "UPDATE jobs SET routing_result = %s::jsonb, status = 'completed' WHERE id = %s",
                (routing_json, test_job["id"]),
            )
            cur.execute(
                "SELECT routing_result, production_trace, status FROM jobs WHERE id = %s",
                (test_job["id"],),
            )
            row = cur.fetchone()

        assert row["status"] == "completed"
        assert row["routing_result"]["workflow"] == "poster_production"
        assert row["production_trace"] is not None
