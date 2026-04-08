"""Layer 3 — Middleware chain tests.

Tests policy gates, quality gate validation layers, and guardrails
as a chain. Each test exercises a decision path through the middleware.

Complements (does NOT duplicate) existing tests:
  - test_policy.py covers individual gate mechanics in detail
  - test_workflows.py covers quality technique registration

This file tests middleware from the user-facing perspective:
"I submit a request — does it get allowed, blocked, or flagged?"
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from contracts.policy import PolicyAction
from middleware.policy import PolicyEvaluator, PolicyRequest


# ---------------------------------------------------------------------------
# 3a — Policy: allow active workflow
# ---------------------------------------------------------------------------


class TestPolicyAllowsActive:
    """Active workflows pass all four policy gates."""

    def test_poster_production_allowed(self, tmp_path: Path) -> None:
        """poster_production is in the active 'core' phase → allow."""
        evaluator = PolicyEvaluator(spans_db_path=tmp_path / "empty.db")
        request = PolicyRequest(
            capability="poster_production",
            job_id="job-001",
            client_id="test-client",
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.allow
        assert decision.gate == "all"

    def test_childrens_book_allowed(self, tmp_path: Path) -> None:
        """childrens_book_production is in active 'publishing' phase → allow."""
        evaluator = PolicyEvaluator(spans_db_path=tmp_path / "empty.db")
        request = PolicyRequest(
            capability="childrens_book_production",
            job_id="job-002",
            client_id="test-client",
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.allow


# ---------------------------------------------------------------------------
# 3b — Policy: block inactive workflow
# ---------------------------------------------------------------------------


class TestPolicyBlocksInactive:
    """Inactive-phase workflows are blocked by the phase gate."""

    def test_social_batch_blocked(self, tmp_path: Path) -> None:
        """social_batch is in inactive 'social' phase → block."""
        evaluator = PolicyEvaluator(spans_db_path=tmp_path / "empty.db")
        request = PolicyRequest(
            capability="social_batch",
            job_id="job-003",
            client_id="test-client",
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.block
        assert decision.gate == "phase"

    def test_invoice_blocked(self, tmp_path: Path) -> None:
        """invoice is in inactive 'extended_ops' phase → block."""
        evaluator = PolicyEvaluator(spans_db_path=tmp_path / "empty.db")
        request = PolicyRequest(
            capability="invoice",
            job_id="job-004",
            client_id="test-client",
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.block
        assert decision.gate == "phase"


# ---------------------------------------------------------------------------
# 3c — Policy: budget gate blocks over-limit
# ---------------------------------------------------------------------------


class TestPolicyBudgetGate:
    """Budget gate blocks when daily token usage exceeds limit."""

    def test_blocks_over_budget(self, tmp_path: Path) -> None:
        """Inject high token usage into spans.db → budget gate blocks."""
        spans_db = tmp_path / "spans.db"
        conn = sqlite3.connect(str(spans_db))
        conn.execute(
            """
            CREATE TABLE spans (
                step_id TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                duration_ms REAL NOT NULL,
                job_id TEXT,
                step_type TEXT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        # Insert 6M tokens worth of spans (limit is 5M)
        for i in range(6):
            conn.execute(
                "INSERT INTO spans VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (str(uuid.uuid4()), "gpt-5.4-mini", 500_000, 500_000, 0.5, 100.0, None, None),
            )
        conn.commit()
        conn.close()

        evaluator = PolicyEvaluator(spans_db_path=spans_db)
        request = PolicyRequest(
            capability="poster_production",
            job_id="job-005",
            client_id="test-client",
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.block
        assert decision.gate == "budget"

    def test_allows_under_budget(self, tmp_path: Path) -> None:
        """Empty spans.db → budget gate allows."""
        spans_db = tmp_path / "empty_spans.db"
        # No spans table = 0 usage, should allow
        evaluator = PolicyEvaluator(spans_db_path=spans_db)
        request = PolicyRequest(
            capability="poster_production",
            job_id="job-006",
            client_id="test-client",
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.allow


# ---------------------------------------------------------------------------
# 3d — Policy: cost gate degrades over ceiling
# ---------------------------------------------------------------------------


class TestPolicyCostGate:
    """Cost gate degrades (not blocks) when per-job cost exceeds ceiling."""

    def test_degrades_over_ceiling(self, tmp_path: Path) -> None:
        """running_cost_usd > 5.00 → degrade."""
        evaluator = PolicyEvaluator(spans_db_path=tmp_path / "empty.db")
        request = PolicyRequest(
            capability="poster_production",
            job_id="job-007",
            client_id="test-client",
            running_cost_usd=6.50,
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.degrade
        assert decision.gate == "cost"

    def test_allows_under_ceiling(self, tmp_path: Path) -> None:
        """running_cost_usd < 5.00 → allow."""
        evaluator = PolicyEvaluator(spans_db_path=tmp_path / "empty.db")
        request = PolicyRequest(
            capability="poster_production",
            job_id="job-008",
            client_id="test-client",
            running_cost_usd=2.50,
        )
        decision = evaluator.evaluate(request)
        assert decision.action == PolicyAction.allow


# ---------------------------------------------------------------------------
# 3e — Quality gate: input validation pass/fail
# ---------------------------------------------------------------------------


class TestQualityGateInputValidation:
    """Quality gate Layer 1 validates input data against schema."""

    def test_pass_with_valid_data(self) -> None:
        """All required fields present → passes."""
        from middleware.quality_gate import validate_input

        schema = {
            "title": {"type": "string", "required": True},
            "page_count": {"type": "integer", "required": True},
        }
        data = {"title": "Raya Poster", "page_count": 1}
        result = validate_input(data, schema)
        assert result.passed is True
        assert result.errors == []

    def test_fail_with_missing_required(self) -> None:
        """Missing required field → fails with error message."""
        from middleware.quality_gate import validate_input

        schema = {
            "title": {"type": "string", "required": True},
            "page_count": {"type": "integer", "required": True},
        }
        data = {"title": "Raya Poster"}
        result = validate_input(data, schema)
        assert result.passed is False
        assert any("page_count" in e for e in result.errors)

    def test_fail_with_wrong_type(self) -> None:
        """Wrong field type → fails."""
        from middleware.quality_gate import validate_input

        schema = {"count": {"type": "integer", "required": True}}
        data = {"count": "not_a_number"}
        result = validate_input(data, schema)
        assert result.passed is False


# ---------------------------------------------------------------------------
# 3f — Quality gate: content quality layer
# ---------------------------------------------------------------------------


class TestQualityGateContentQuality:
    """Quality gate Layer 4 checks language and tone."""

    def test_pass_clean_formal_content(self) -> None:
        """Clean formal text → passes."""
        from middleware.quality_gate import validate_content_quality

        result = validate_content_quality(
            content="We are pleased to present our quarterly report.",
            expected_languages=["en"],
            expected_tone="formal",
        )
        assert result.passed is True

    def test_fail_informal_in_formal_context(self) -> None:
        """Informal markers in formal context → flagged."""
        from middleware.quality_gate import validate_content_quality

        result = validate_content_quality(
            content="lol this quarterly report is fire bruh",
            expected_languages=["en"],
            expected_tone="formal",
        )
        assert result.passed is False
        assert any("informal" in e.lower() or "Informal" in e for e in result.errors)


# ---------------------------------------------------------------------------
# 3g — Guardrails: flag register mismatch (advisory, not blocking)
# ---------------------------------------------------------------------------


class TestGuardrailsAdvisory:
    """Guardrails flag issues but don't block production."""

    def test_bm_naturalness_flags_formal_markers(self) -> None:
        """BM text with overly formal markers → flagged."""
        from middleware.guardrails import check_bm_naturalness

        result = check_bm_naturalness(
            "Dengan ini dimaklumkan bahawa projek tersebut "
            "telah sebagaimana diperakui oleh pihak berkenaan."
        )
        assert result["flagged"] is True
        assert len(result["issues"]) > 0

    def test_bm_naturalness_clean_text(self) -> None:
        """Natural BM text → not flagged."""
        from middleware.guardrails import check_bm_naturalness

        result = check_bm_naturalness("Selamat datang ke kedai kami.")
        assert result["flagged"] is False

    @patch("middleware.guardrails.call_llm")
    def test_brand_voice_mismatch_flagged(self, mock_llm: MagicMock) -> None:
        """Brand voice check detects register mismatch → flagged."""
        import json

        mock_llm.return_value = {
            "content": json.dumps({
                "flagged": True,
                "issue": "Casual tone detected in formal context",
                "register_detected": "casual",
            }),
            "model": "gpt-5.4-mini",
            "input_tokens": 50,
            "output_tokens": 30,
            "cost_usd": 0.0001,
        }

        from middleware.guardrails import check_brand_voice

        result = check_brand_voice(
            copy="hey whats up, check out this new product yo",
            copy_register="formal",
        )
        assert result["flagged"] is True
        assert result["register_detected"] == "casual"

    def test_guardrail_mailbox_deduplication(self) -> None:
        """GuardrailMailbox deduplicates multiple flags of same type."""
        from middleware.guardrails import GuardrailMailbox

        mailbox = GuardrailMailbox()
        mailbox.add_flag(issue_type="register_mismatch", detail="Issue A")
        mailbox.add_flag(issue_type="register_mismatch", detail="Issue B")
        mailbox.add_flag(issue_type="bm_naturalness", detail="Issue C")

        items = mailbox.collect()
        assert len(items) == 2  # 2 unique issue types

        register_item = next(i for i in items if i["issue_type"] == "register_mismatch")
        assert register_item["count"] == 2
        assert len(register_item["details"]) == 2
