"""Layer 5 — Full workflow E2E tests.

Raw input → delivered artifact, full chain (mock external calls):
  - Poster: input → route → policy → generate → score → store → trace
  - Document: input → route → research → outline → sections → deliver
  - Rework: feedback → analyze → revise → re-score → deliver

Uses a mock tool registry to avoid external HTTP calls while testing
the full orchestration chain (routing → readiness → policy → executor).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mock tool registry — replaces real tools with deterministic stubs
# ---------------------------------------------------------------------------


def _make_mock_tool(name: str, extra: dict[str, Any] | None = None) -> Any:
    """Create a mock tool that returns a standard ok response."""
    def tool_fn(context: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "ok",
            "output": f"{name}_completed",
            "input_tokens": 10,
            "output_tokens": 5,
            "cost_usd": 0.0001,
        }
        if extra:
            result.update(extra)
        return result
    tool_fn.__qualname__ = f"mock_{name}"
    return tool_fn


def _build_mock_registry() -> dict[str, Any]:
    """Build a complete mock tool registry for E2E tests."""
    registry: dict[str, Any] = {}
    # Core tools
    for name in [
        "classify_artifact", "deliver", "typst_render",
        "knowledge_retrieve", "knowledge_store", "generate_copy",
        "generate_poster", "generate_brochure", "generate_document",
        "generate_section", "generate_page_text", "generate_profile",
        "generate_proposal", "generate_invoice", "generate_episode",
        "generate_social_batch", "generate_caption", "generate_calendar",
        "visual_qa", "document_qa", "narrative_qa", "text_qa",
        "calendar_qa", "quality_gate", "platform_check",
        "character_workshop", "story_workshop", "scaffold_build",
        "character_verify", "web_search", "trend_analyse",
        "competitor_scan", "summarise", "refine_spec", "readiness_check",
        "ask_operator", "brand_extract", "swipe_index", "calibration_check",
        "onboard_client", "trace_insight", "creative_workshop",
        "rolling_summary", "section_tripwire", "character_consistency",
    ]:
        registry[name] = _make_mock_tool(name)

    # Image generate with image_path
    registry["image_generate"] = _make_mock_tool(
        "image_generate",
        {"image_path": "/tmp/test_image.png", "image_model": "flux.2"},
    )

    # Poster copy with poster_copy field
    registry["generate_poster"] = _make_mock_tool(
        "generate_poster",
        {"poster_copy": json.dumps({
            "headline": "Selamat Hari Raya",
            "subheadline": "Dari DMB",
            "cta": "Hubungi kami",
            "body_text": "Tawaran istimewa",
        })},
    )

    return registry


def _setup_spans_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a temporary spans.db for tests."""
    import utils.spans as spans_mod

    test_db = tmp_path / "spans.db"
    monkeypatch.setattr(spans_mod, "DB_PATH", test_db)
    spans_mod.init_db(test_db)
    return test_db


# ---------------------------------------------------------------------------
# 5a — Poster E2E: input → route → policy → generate → score → store → trace
# ---------------------------------------------------------------------------


class TestPosterE2E:
    """Full poster workflow: raw input through all layers to trace output."""

    def test_poster_full_chain_mocked(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Poster: route → policy → execute all stages → trace attached."""
        _setup_spans_db(tmp_path, monkeypatch)

        from contracts.routing import fast_path_route
        from middleware.policy import PolicyEvaluator, PolicyRequest
        from tools.executor import WorkflowExecutor

        # Step 1: Route
        routing = fast_path_route("buat poster Raya untuk DMB")
        assert routing is not None
        assert routing.workflow == "poster_production"
        assert routing.fast_path is True
        assert routing.token_cost == 0

        # Step 2: Policy
        evaluator = PolicyEvaluator(spans_db_path=tmp_path / "empty.db")
        decision = evaluator.evaluate(PolicyRequest(
            capability="poster_production",
            job_id="job-e2e-001",
            client_id="test-client",
        ))
        assert decision.action.value == "allow"

        # Step 3: Execute workflow with mock registry
        workflow_path = Path("manifests/workflows/poster_production.yaml")
        executor = WorkflowExecutor(
            workflow_path=workflow_path,
            tool_registry=_build_mock_registry(),
            client_id="test-client",
        )
        result = executor.run(job_context={
            "job_id": "job-e2e-001",
            "client_id": "test-client",
            "raw_input": "buat poster Raya untuk DMB",
            "routing": routing.model_dump(mode="json"),
        })

        # Verify output structure
        assert result["workflow"] == "poster_production"
        assert len(result["stages"]) >= 1
        assert "trace" in result
        trace = result["trace"]
        assert "steps" in trace
        assert len(trace["steps"]) >= 1

        # Verify every stage completed ok
        for stage in result["stages"]:
            assert stage["status"] == "ok"

    def test_fast_path_route_zero_tokens(self) -> None:
        """Poster fast-path routing uses zero tokens."""
        from contracts.routing import fast_path_route

        result = fast_path_route("buat poster Raya untuk DMB")
        assert result is not None
        assert result.token_cost == 0


# ---------------------------------------------------------------------------
# 5b — Document E2E: input → route → research → outline → sections → deliver
# ---------------------------------------------------------------------------


class TestDocumentE2E:
    """Full document workflow with mock tool registry."""

    def test_document_full_chain_mocked(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Document: route → execute stages → deliver → trace."""
        _setup_spans_db(tmp_path, monkeypatch)

        from contracts.routing import fast_path_route
        from middleware.policy import PolicyEvaluator, PolicyRequest
        from tools.executor import WorkflowExecutor

        # Step 1: Route — "write" matches document fast-path
        routing = fast_path_route("write a report for the project")
        assert routing is not None
        assert routing.workflow == "document_production"

        # Step 2: Policy
        evaluator = PolicyEvaluator(spans_db_path=tmp_path / "empty.db")
        decision = evaluator.evaluate(PolicyRequest(
            capability="document_production",
            job_id="job-doc-001",
            client_id="test-client",
        ))
        assert decision.action.value == "allow"

        # Step 3: Execute workflow
        workflow_path = Path("manifests/workflows/document_production.yaml")
        executor = WorkflowExecutor(
            workflow_path=workflow_path,
            tool_registry=_build_mock_registry(),
            client_id="test-client",
        )
        result = executor.run(job_context={
            "job_id": "job-doc-001",
            "client_id": "test-client",
            "raw_input": "write a report for the project",
            "routing": routing.model_dump(mode="json"),
        })

        assert result["workflow"] == "document_production"
        assert len(result["stages"]) >= 1
        assert "trace" in result


# ---------------------------------------------------------------------------
# 5c — Rework E2E: feedback → analyze → revise → re-score → deliver
# ---------------------------------------------------------------------------


class TestReworkE2E:
    """Rework workflow: take feedback, revise, re-deliver."""

    def test_rework_full_chain_mocked(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rework: route → trace insight → revise → quality gate → deliver."""
        _setup_spans_db(tmp_path, monkeypatch)

        from contracts.routing import fast_path_route
        from middleware.policy import PolicyEvaluator, PolicyRequest
        from tools.executor import WorkflowExecutor

        # Step 1: Route — "perbaiki" matches rework fast-path
        routing = fast_path_route("perbaiki warna terlalu gelap")
        assert routing is not None
        assert routing.workflow == "rework"

        # Step 2: Policy
        evaluator = PolicyEvaluator(spans_db_path=tmp_path / "empty.db")
        decision = evaluator.evaluate(PolicyRequest(
            capability="rework",
            job_id="job-rework-001",
            client_id="test-client",
        ))
        assert decision.action.value == "allow"

        # Step 3: Execute workflow
        workflow_path = Path("manifests/workflows/rework.yaml")
        executor = WorkflowExecutor(
            workflow_path=workflow_path,
            tool_registry=_build_mock_registry(),
            client_id="test-client",
        )
        result = executor.run(job_context={
            "job_id": "job-rework-001",
            "client_id": "test-client",
            "raw_input": "perbaiki warna terlalu gelap",
            "routing": routing.model_dump(mode="json"),
            "original_job_id": "job-e2e-001",
        })

        assert result["workflow"] == "rework"
        assert len(result["stages"]) >= 1
        assert "trace" in result


# ---------------------------------------------------------------------------
# 5d — run_governed() full chain
# ---------------------------------------------------------------------------


class TestRunGovernedE2E:
    """run_governed() chains route → readiness → policy → execute."""

    def test_run_governed_poster(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """run_governed() for a poster request produces a traced result."""
        _setup_spans_db(tmp_path, monkeypatch)

        from tools.orchestrate import run_governed

        result = run_governed(
            raw_input="buat poster Raya untuk DMB",
            client_id="test-client",
            job_id="job-governed-001",
            tool_registry=_build_mock_registry(),
        )

        # Verify full governance metadata attached
        assert "routing" in result
        assert result["routing"]["workflow"] == "poster_production"
        assert "readiness" in result
        assert "policy" in result
        assert result["policy"]["action"] == "allow"
        assert "stages" in result
        assert "trace" in result

    @patch("contracts.routing.call_llm")
    def test_run_governed_blocks_inactive_workflow(
        self,
        mock_llm: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """run_governed() raises PolicyDenied for inactive workflow."""
        _setup_spans_db(tmp_path, monkeypatch)

        # Mock LLM to route to an inactive workflow
        mock_llm.return_value = {
            "content": json.dumps({
                "workflow": "social_batch",
                "confidence": 0.9,
                "reason": "social content",
            }),
            "model": "gpt-5.4-mini",
            "input_tokens": 30,
            "output_tokens": 10,
            "cost_usd": 0.00003,
        }

        from tools.orchestrate import PolicyDenied, run_governed

        with pytest.raises(PolicyDenied, match="phase"):
            run_governed(
                raw_input="schedule social media posts for next week",
                client_id="test-client",
                job_id="job-blocked-001",
                tool_registry=_build_mock_registry(),
            )
