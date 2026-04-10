"""Layer 2 — Single-function primitive tests.

Each primitive is tested in isolation with mocked external calls.
Focuses on return contracts and correct wiring.

Complements (does NOT duplicate) existing unit tests:
  - test_spans.py covers @track_span decorator internals
  - test_embeddings.py covers embed_text span recording
  - test_routing.py covers fast_path_route patterns
  - test_contracts.py covers evaluate_readiness edge cases
  - test_ring_enforcement.py covers get_workflow_family registry lookups

This file tests the primitives from an E2E "user perspective" — given
standard input, does the function return the expected shape?
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from contracts.artifact_spec import (
    ArtifactFamily,
    DeliveryFormat,
    ProvisionalArtifactSpec,
)
from contracts.readiness import ReadinessResult, evaluate_readiness
from utils.workflow_registry import get_workflow_family


# ---------------------------------------------------------------------------
# 2a — call_llm() returns standard response dict
# ---------------------------------------------------------------------------


class TestCallLLMPrimitive:
    """call_llm() returns the standard response contract."""

    @patch("utils.call_llm._post_with_retry")
    def test_returns_content_string(self, mock_post: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """call_llm returns dict with 'content' as a string."""
        import utils.spans as spans_mod

        test_db = tmp_path / "spans.db"
        monkeypatch.setattr(spans_mod, "DB_PATH", test_db)
        spans_mod.init_db(test_db)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello from GPT"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_post.return_value = mock_resp

        from utils.call_llm import call_llm

        result = call_llm(
            stable_prefix=[{"role": "system", "content": "You are a test."}],
            variable_suffix=[{"role": "user", "content": "Say hello"}],
            model="gpt-5.4-mini",
        )

        assert isinstance(result, dict)
        assert result["content"] == "Hello from GPT"
        assert result["model"] == "gpt-5.4-mini"
        assert isinstance(result["input_tokens"], int)
        assert isinstance(result["output_tokens"], int)
        assert isinstance(result["cost_usd"], float)

    @patch("utils.call_llm._post_with_retry")
    def test_cost_calculation_nonzero(self, mock_post: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """call_llm calculates nonzero cost for nonzero tokens."""
        import utils.spans as spans_mod

        test_db = tmp_path / "spans.db"
        monkeypatch.setattr(spans_mod, "DB_PATH", test_db)
        spans_mod.init_db(test_db)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "test"}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
        }
        mock_post.return_value = mock_resp

        from utils.call_llm import call_llm

        result = call_llm(
            stable_prefix=[{"role": "system", "content": "test"}],
            variable_suffix=[{"role": "user", "content": "test"}],
        )

        assert result["cost_usd"] > 0.0


# ---------------------------------------------------------------------------
# 2b — embed_text() returns float vector
# ---------------------------------------------------------------------------


class TestEmbedTextPrimitive:
    """embed_text() returns a 1536-dim float list."""

    @patch("utils.embeddings.httpx.post")
    @patch("utils.embeddings.record_span")
    def test_returns_float_vector(self, mock_span: MagicMock, mock_post: MagicMock) -> None:
        """embed_text returns list of 1536 floats."""
        fake_embedding = [0.1] * 1536
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [{"embedding": fake_embedding}],
            "usage": {"total_tokens": 8},
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from utils.embeddings import embed_text

        result = embed_text("hello world")

        assert isinstance(result, list)
        assert len(result) == 1536
        assert all(isinstance(v, float) for v in result)


# ---------------------------------------------------------------------------
# 2c — record_span() persists to SQLite
# ---------------------------------------------------------------------------


class TestRecordSpanPrimitive:
    """record_span() writes to the spans table and is retrievable."""

    def test_persists_and_reads_back(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Write a span, read it back, verify all fields."""
        import utils.spans as spans_mod

        test_db = tmp_path / "spans.db"
        monkeypatch.setattr(spans_mod, "DB_PATH", test_db)
        spans_mod.init_db(test_db)

        step_id = str(uuid.uuid4())
        spans_mod.record_span(
            step_id=step_id,
            model="gpt-5.4-mini",
            input_tokens=200,
            output_tokens=100,
            cost_usd=0.00009,
            duration_ms=456.7,
            job_id="job-xyz",
            step_type="generation",
        )

        conn = sqlite3.connect(str(test_db))
        try:
            row = conn.execute(
                "SELECT * FROM spans WHERE step_id = ?", (step_id,)
            ).fetchone()
            assert row is not None
            # row: step_id, model, input_tokens, output_tokens,
            #      cost_usd, duration_ms, job_id, step_type, timestamp
            assert row[1] == "gpt-5.4-mini"
            assert row[2] == 200
            assert row[3] == 100
            assert row[6] == "job-xyz"
            assert row[7] == "generation"
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# 2d — get_workflow_family() correct mapping
# ---------------------------------------------------------------------------


class TestGetWorkflowFamily:
    """get_workflow_family() returns correct artifact family names."""

    @pytest.mark.parametrize(
        "workflow,expected_family",
        [
            ("poster_production", "poster"),
            ("document_production", "document"),
            ("childrens_book_production", "childrens_book"),
            ("ebook_production", "ebook"),
            ("research", "document"),
            ("refinement", "document"),
        ],
    )
    def test_known_workflows(self, workflow: str, expected_family: str) -> None:
        assert get_workflow_family(workflow) == expected_family

    def test_unknown_workflow_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="Unknown workflow"):
            get_workflow_family("nonexistent_workflow_xyz")


# ---------------------------------------------------------------------------
# 2e — evaluate_readiness() ready / shapeable / blocked
# ---------------------------------------------------------------------------


class TestEvaluateReadiness:
    """evaluate_readiness() classifies specs correctly."""

    def test_ready_when_all_critical_present(self) -> None:
        """Spec with all 8 scored fields → ready."""
        spec = ProvisionalArtifactSpec(
            client_id="test-client",
            artifact_family=ArtifactFamily.poster,
            family_resolved=True,
            language="en",
            objective="Raya 2025 poster for DMB",
            format=DeliveryFormat.pdf,
            tone="formal",
            copy_register="formal_bm",
            brand_config_id="dmb-brand",
            dimensions="1080x1080",
            page_count=1,
            raw_brief="Make a Raya poster",
        )
        result = evaluate_readiness(spec)
        assert isinstance(result, ReadinessResult)
        assert result.status == "ready"
        assert result.completeness >= 0.8

    def test_shapeable_when_missing_format(self) -> None:
        """Spec with objective but no format → shapeable."""
        spec = ProvisionalArtifactSpec(
            client_id="test-client",
            artifact_family=ArtifactFamily.poster,
            language="en",
            objective="Raya 2025 poster",
            raw_brief="Make a poster",
        )
        result = evaluate_readiness(spec)
        assert result.status == "shapeable"

    def test_blocked_when_no_objective_and_no_brief(self) -> None:
        """Spec with nothing useful → blocked."""
        spec = ProvisionalArtifactSpec(
            client_id="test-client",
            artifact_family=ArtifactFamily.document,
            language="en",
        )
        result = evaluate_readiness(spec)
        assert result.status == "blocked"


# ---------------------------------------------------------------------------
# 2f — fast_path_route() routes "make a poster" correctly
# ---------------------------------------------------------------------------


class TestFastPathRoute:
    """fast_path_route() maps common phrases to workflows."""

    def test_poster_routes_to_poster_production(self) -> None:
        """'buat poster' triggers poster_production fast-path."""
        from contracts.routing import fast_path_route

        result = fast_path_route("buat poster untuk Raya")
        assert result is not None
        assert result.workflow == "poster_production"
        assert result.fast_path is True
        assert result.token_cost == 0
        assert result.confidence == 1.0

    def test_unknown_input_returns_none(self) -> None:
        """Unrecognizable input returns None (falls to LLM route)."""
        from contracts.routing import fast_path_route

        result = fast_path_route("xyzzyz nonsense gibberish")
        assert result is None

    def test_research_routes_correctly(self) -> None:
        """'research trends' triggers research fast-path."""
        from contracts.routing import fast_path_route

        result = fast_path_route("research trend analysis for market")
        assert result is not None
        assert result.workflow == "research"
