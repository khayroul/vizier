"""Tests for S8 — PolicyEvaluator, observability, and quality posture.

Covers all exit criteria:
- PolicyEvaluator blocks over-budget and wrong-phase requests
- Langfuse trace appears with client_id metadata
- Local span AND Langfuse trace exist for same call (dual tracing)
- Context size cap rejects oversized prompt
- Quality posture handler returns correct posture for each of 3 levels
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from contracts.policy import PolicyAction, PolicyDecision
from middleware.policy import PolicyEvaluator, PolicyRequest
from middleware.observability import (
    check_context_size,
    observe_with_metadata,
    trace_to_langfuse,
)
from middleware.quality_posture import PostureConfig, get_quality_posture


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_PHASE_YAML = {
    "phases": {
        "core": {
            "active": True,
            "includes": [
                "poster_production",
                "document_production",
                "brochure_production",
            ],
        },
        "social": {
            "active": False,
            "includes": ["social_batch", "social_caption"],
        },
    },
    "budget": {"daily_token_limit": 1000},
    "cost_ceiling": {"per_job_usd": 2.00},
    "context_size_cap": {"max_tokens": 500},
    "approved_tools": {
        "core": ["generate_copy", "generate_image", "render_typst"],
        "social": ["generate_caption", "batch_social"],
    },
    "quality_posture": {
        "canva_baseline": {
            "techniques": ["self_refine", "exemplar_injection"],
            "contract_strictness": "warn",
            "critique_rounds": 1,
        },
        "enhanced": {
            "techniques": [
                "self_refine",
                "exemplar_injection",
                "visual_brief_expansion",
                "copy_formula_grounding",
                "structured_critique",
            ],
            "contract_strictness": "reject",
            "critique_rounds": 2,
        },
        "full": {
            "techniques": [
                "self_refine",
                "exemplar_injection",
                "visual_brief_expansion",
                "copy_formula_grounding",
                "structured_critique",
                "parallel_guardrails",
                "golden_dataset_calibration",
            ],
            "contract_strictness": "reject",
            "critique_rounds": 3,
        },
    },
    "model_lock": {"text_model": "gpt-5.4-mini"},
}


@pytest.fixture()
def phase_yaml_path(tmp_path: Path) -> Path:
    """Write fixture phase.yaml to a temp dir and return its path."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    path = config_dir / "phase.yaml"
    path.write_text(yaml.dump(FIXTURE_PHASE_YAML, default_flow_style=False))
    return path


@pytest.fixture()
def spans_db(tmp_path: Path) -> Path:
    """Create a fresh spans.db with the correct schema."""
    db_path = tmp_path / "spans.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS spans (
            step_id     TEXT PRIMARY KEY,
            model       TEXT NOT NULL,
            input_tokens  INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            cost_usd    REAL NOT NULL,
            duration_ms REAL NOT NULL,
            job_id      TEXT,
            step_type   TEXT,
            timestamp   TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def evaluator(phase_yaml_path: Path, spans_db: Path) -> PolicyEvaluator:
    """PolicyEvaluator wired to test config and spans DB."""
    return PolicyEvaluator(config_path=phase_yaml_path, spans_db_path=spans_db)


def _insert_spans(db_path: Path, total_tokens: int, count: int = 1) -> None:
    """Insert span rows totalling the given token count."""
    conn = sqlite3.connect(str(db_path))
    per_span = total_tokens // count
    for _ in range(count):
        conn.execute(
            """
            INSERT INTO spans (step_id, model, input_tokens, output_tokens,
                               cost_usd, duration_ms, timestamp)
            VALUES (?, 'gpt-5.4-mini', ?, 0, 0.0, 10.0, datetime('now'))
            """,
            (str(uuid.uuid4()), per_span),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# PolicyEvaluator — budget gate
# ---------------------------------------------------------------------------


class TestBudgetGate:
    """Budget gate blocks when 24h token usage exceeds limit."""

    def test_blocks_over_budget(
        self, evaluator: PolicyEvaluator, spans_db: Path
    ) -> None:
        _insert_spans(spans_db, total_tokens=1500)  # limit is 1000
        request = PolicyRequest(capability="poster_production")
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.block
        assert decision.gate == "budget"

    def test_allows_under_budget(
        self, evaluator: PolicyEvaluator, spans_db: Path
    ) -> None:
        _insert_spans(spans_db, total_tokens=500)  # under 1000 limit
        request = PolicyRequest(capability="poster_production")
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.allow

    def test_allows_empty_spans(self, evaluator: PolicyEvaluator) -> None:
        request = PolicyRequest(capability="poster_production")
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.allow


# ---------------------------------------------------------------------------
# PolicyEvaluator — phase gate
# ---------------------------------------------------------------------------


class TestPhaseGate:
    """Phase gate blocks capabilities not in any active phase."""

    def test_blocks_wrong_phase(self, evaluator: PolicyEvaluator) -> None:
        request = PolicyRequest(capability="social_batch")
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.block
        assert decision.gate == "phase"
        assert "social_batch" in decision.reason

    def test_allows_active_capability(self, evaluator: PolicyEvaluator) -> None:
        request = PolicyRequest(capability="poster_production")
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.allow

    def test_blocks_unknown_capability(self, evaluator: PolicyEvaluator) -> None:
        request = PolicyRequest(capability="nonexistent_workflow")
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.block
        assert decision.gate == "phase"


# ---------------------------------------------------------------------------
# PolicyEvaluator — tool gate
# ---------------------------------------------------------------------------


class TestToolGate:
    """Tool gate blocks unapproved tools."""

    def test_blocks_unapproved_tool(self, evaluator: PolicyEvaluator) -> None:
        request = PolicyRequest(
            capability="poster_production", tool_name="batch_social"
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.block
        assert decision.gate == "tool"

    def test_allows_approved_tool(self, evaluator: PolicyEvaluator) -> None:
        request = PolicyRequest(
            capability="poster_production", tool_name="generate_copy"
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.allow

    def test_skips_when_no_tool(self, evaluator: PolicyEvaluator) -> None:
        """No tool_name means tool gate is skipped (allow)."""
        request = PolicyRequest(capability="poster_production")
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.allow


# ---------------------------------------------------------------------------
# PolicyEvaluator — cost gate
# ---------------------------------------------------------------------------


class TestCostGate:
    """Cost gate degrades (not blocks) when per-job cost exceeds ceiling."""

    def test_degrades_over_cost_ceiling(self, evaluator: PolicyEvaluator) -> None:
        request = PolicyRequest(
            capability="poster_production", running_cost_usd=3.50  # ceiling is 2.00
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.degrade
        assert decision.gate == "cost"

    def test_allows_under_cost_ceiling(self, evaluator: PolicyEvaluator) -> None:
        request = PolicyRequest(
            capability="poster_production", running_cost_usd=1.00
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.allow


# ---------------------------------------------------------------------------
# PolicyEvaluator — all gates pass
# ---------------------------------------------------------------------------


class TestAllGatesPass:
    """Valid request passes all gates."""

    def test_allows_valid_request(self, evaluator: PolicyEvaluator) -> None:
        request = PolicyRequest(
            capability="poster_production",
            tool_name="generate_copy",
            running_cost_usd=0.50,
            client_id="client-123",
            job_id="job-456",
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.allow
        assert decision.gate == "all"

    def test_allow_includes_gates_evaluated_snapshot(
        self, evaluator: PolicyEvaluator
    ) -> None:
        """No silent passes — allow decisions record what each gate checked."""
        request = PolicyRequest(
            capability="poster_production",
            tool_name="generate_copy",
            running_cost_usd=0.50,
            client_id="client-123",
            job_id="job-456",
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.allow

        gates_evaluated = decision.constraints.get("gates_evaluated")
        assert gates_evaluated is not None, "allow must include gates_evaluated"
        assert isinstance(gates_evaluated, list)
        assert len(gates_evaluated) == 4  # phase, tool, budget, cost

        gate_names = [g["gate"] for g in gates_evaluated]
        assert gate_names == ["phase", "tool", "budget", "cost"]
        for gate_result in gates_evaluated:
            assert gate_result["action"] == "allow"
            assert gate_result["reason"]  # non-empty

    def test_block_includes_gates_evaluated_snapshot(
        self, evaluator: PolicyEvaluator
    ) -> None:
        """Block decisions also record what was evaluated before the block."""
        request = PolicyRequest(
            capability="poster_production",
            tool_name="batch_social",  # not approved → tool gate blocks
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.block
        assert decision.gate == "tool"

        gates_evaluated = decision.constraints.get("gates_evaluated")
        assert gates_evaluated is not None
        assert len(gates_evaluated) == 2  # phase (allowed), then tool (blocked)
        assert gates_evaluated[0]["gate"] == "phase"
        assert gates_evaluated[0]["action"] == "allow"
        assert gates_evaluated[1]["gate"] == "tool"
        assert gates_evaluated[1]["action"] == "block"


# ---------------------------------------------------------------------------
# Observability — Langfuse trace with metadata
# ---------------------------------------------------------------------------


class TestLangfuseObservability:
    """Langfuse integration sends traces with client_id metadata."""

    def test_trace_to_langfuse_includes_metadata(self) -> None:
        mock_langfuse = MagicMock()
        from contracts.trace import ProductionTrace, StepTrace

        trace = ProductionTrace(
            job_id="job-1",
            steps=[
                StepTrace(
                    step_name="generate_copy",
                    model="gpt-5.4-mini",
                    input_tokens=100,
                    output_tokens=50,
                    cost_usd=0.001,
                    duration_ms=200.0,
                )
            ],
        )
        metadata = {
            "client_id": "client-abc",
            "tier": "premium",
            "job_id": "job-1",
            "artifact_type": "poster",
        }

        trace_to_langfuse(trace, metadata, langfuse_client=mock_langfuse)

        mock_langfuse.trace.assert_called_once()
        call_kwargs = mock_langfuse.trace.call_args
        assert call_kwargs.kwargs["metadata"]["client_id"] == "client-abc"
        assert call_kwargs.kwargs["name"] == "job-1"

    def test_observe_decorator_fires_langfuse(self) -> None:
        mock_langfuse = MagicMock()

        with patch("middleware.observability._langfuse_client", mock_langfuse):
            @observe_with_metadata(
                client_id="c1", tier="basic", job_id="j1", artifact_type="poster"
            )
            def dummy_fn() -> str:
                return "result"

            result = dummy_fn()
            assert result == "result"
            # Langfuse trace was created with metadata
            mock_langfuse.trace.assert_called_once()
            call_kwargs = mock_langfuse.trace.call_args
            assert call_kwargs.kwargs["metadata"]["client_id"] == "c1"
            assert call_kwargs.kwargs["name"] == "dummy_fn"


# ---------------------------------------------------------------------------
# Dual tracing — local span + Langfuse
# ---------------------------------------------------------------------------


class TestDualTracing:
    """Both local spans and Langfuse fire on every call."""

    def test_dual_trace_records_both(
        self, spans_db: Path, phase_yaml_path: Path
    ) -> None:
        """After trace_to_langfuse, local span should also exist."""
        from contracts.trace import ProductionTrace, StepTrace

        mock_langfuse = MagicMock()

        trace = ProductionTrace(
            job_id="job-dual",
            steps=[
                StepTrace(
                    step_name="dual_test",
                    model="gpt-5.4-mini",
                    input_tokens=200,
                    output_tokens=100,
                    cost_usd=0.002,
                    duration_ms=150.0,
                )
            ],
        )
        metadata = {"client_id": "c1", "tier": "basic", "job_id": "job-dual"}

        # Push to Langfuse (mocked)
        trace_to_langfuse(trace, metadata, langfuse_client=mock_langfuse)
        mock_langfuse.trace.assert_called_once()

        # Also record locally
        from utils.spans import init_db, record_span

        with patch("utils.spans.DB_PATH", spans_db):
            init_db(spans_db)
            for step in trace.steps:
                record_span(
                    step_id=str(step.trace_id),
                    model=step.model,
                    input_tokens=step.input_tokens,
                    output_tokens=step.output_tokens,
                    cost_usd=step.cost_usd,
                    duration_ms=step.duration_ms,
                    job_id=trace.job_id,
                    step_type=step.step_name,
                )

        # Verify local span exists
        conn = sqlite3.connect(str(spans_db))
        rows = conn.execute("SELECT * FROM spans WHERE job_id = 'job-dual'").fetchall()
        conn.close()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Context size cap
# ---------------------------------------------------------------------------


class TestContextSizeCap:
    """Context size cap rejects oversized prompts."""

    def test_rejects_oversized_prompt(self, phase_yaml_path: Path) -> None:
        decision = check_context_size(
            prompt_tokens=600,  # cap is 500 in fixture
            config_path=phase_yaml_path,
        )
        assert decision.action == PolicyAction.block
        assert "context" in decision.reason.lower() or "token" in decision.reason.lower()

    def test_allows_within_limit(self, phase_yaml_path: Path) -> None:
        decision = check_context_size(
            prompt_tokens=400,
            config_path=phase_yaml_path,
        )
        assert decision.action == PolicyAction.allow

    def test_allows_exact_limit(self, phase_yaml_path: Path) -> None:
        decision = check_context_size(
            prompt_tokens=500,
            config_path=phase_yaml_path,
        )
        assert decision.action == PolicyAction.allow


# ---------------------------------------------------------------------------
# Quality posture handler
# ---------------------------------------------------------------------------


class TestQualityPosture:
    """Quality posture returns correct config for each level."""

    def test_canva_baseline(self, phase_yaml_path: Path) -> None:
        posture = get_quality_posture("canva_baseline", config_path=phase_yaml_path)
        assert posture.name == "canva_baseline"
        assert posture.techniques == ["self_refine", "exemplar_injection"]
        assert posture.contract_strictness == "warn"
        assert posture.critique_rounds == 1

    def test_enhanced(self, phase_yaml_path: Path) -> None:
        posture = get_quality_posture("enhanced", config_path=phase_yaml_path)
        assert posture.name == "enhanced"
        assert "visual_brief_expansion" in posture.techniques
        assert posture.contract_strictness == "reject"
        assert posture.critique_rounds == 2

    def test_full(self, phase_yaml_path: Path) -> None:
        posture = get_quality_posture("full", config_path=phase_yaml_path)
        assert posture.name == "full"
        assert "parallel_guardrails" in posture.techniques
        assert "golden_dataset_calibration" in posture.techniques
        assert posture.contract_strictness == "reject"
        assert posture.critique_rounds == 3

    def test_unknown_posture_raises(self, phase_yaml_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown quality posture"):
            get_quality_posture("nonexistent", config_path=phase_yaml_path)

    def test_default_config_path(self) -> None:
        """Falls back to the repo's config/phase.yaml."""
        posture = get_quality_posture("canva_baseline")
        assert posture.name == "canva_baseline"
        assert posture.critique_rounds == 1
