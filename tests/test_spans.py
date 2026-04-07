"""Tests for S7 — Local Spans + Memory Routing."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.spans import (
    DB_PATH,
    init_db,
    record_memory_routing,
    record_span,
    track_span,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the spans DB to a temp directory for test isolation."""
    db_path = tmp_path / "spans.db"
    monkeypatch.setattr("utils.spans.DB_PATH", db_path)
    monkeypatch.setattr("utils.call_llm.DB_PATH", db_path)
    monkeypatch.setattr("utils.diagnostics.DB_PATH", db_path)
    monkeypatch.setattr("utils.idle_alarm.DB_PATH", db_path)
    init_db(db_path)
    return db_path


def _conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# 1. Spans table + decorator
# ---------------------------------------------------------------------------


class TestSpansTable:
    """Span decorator captures model, tokens, cost, duration, job_id."""

    def test_tables_created(self, _isolated_db: Path) -> None:
        conn = _conn(_isolated_db)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "spans" in tables
        assert "memory_routing_log" in tables

    def test_record_span_writes_row(self, _isolated_db: Path) -> None:
        record_span(
            step_id="step-1",
            model="gpt-5.4-mini",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            duration_ms=120.5,
            job_id="job-abc",
        )
        conn = _conn(_isolated_db)
        row = conn.execute("SELECT * FROM spans WHERE step_id='step-1'").fetchone()
        conn.close()
        assert row is not None
        assert row["model"] == "gpt-5.4-mini"
        assert row["input_tokens"] == 100
        assert row["output_tokens"] == 50
        assert row["cost_usd"] == pytest.approx(0.001)
        assert row["duration_ms"] == pytest.approx(120.5)
        assert row["job_id"] == "job-abc"

    def test_record_span_nullable_job_id(self, _isolated_db: Path) -> None:
        record_span(
            step_id="step-idle",
            model="gpt-5.4-mini",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0001,
            duration_ms=50.0,
        )
        conn = _conn(_isolated_db)
        row = conn.execute(
            "SELECT job_id FROM spans WHERE step_id='step-idle'"
        ).fetchone()
        conn.close()
        assert row["job_id"] is None

    def test_memory_routing_log(self, _isolated_db: Path) -> None:
        record_memory_routing(
            operation="summarise",
            model_used="gpt-5.4-mini",
            tokens=200,
        )
        conn = _conn(_isolated_db)
        row = conn.execute("SELECT * FROM memory_routing_log").fetchone()
        conn.close()
        assert row is not None
        assert row["operation"] == "summarise"
        assert row["model_used"] == "gpt-5.4-mini"
        assert row["tokens"] == 200


class TestTrackSpanDecorator:
    """@track_span works bare and with arguments."""

    def test_bare_decorator(self, _isolated_db: Path) -> None:
        @track_span
        def my_func() -> dict:
            return {
                "content": "hello",
                "model": "gpt-5.4-mini",
                "input_tokens": 50,
                "output_tokens": 25,
                "cost_usd": 0.0005,
            }

        result = my_func()
        assert result["content"] == "hello"

        conn = _conn(_isolated_db)
        row = conn.execute("SELECT * FROM spans").fetchone()
        conn.close()
        assert row is not None
        assert row["model"] == "gpt-5.4-mini"
        assert row["input_tokens"] == 50
        assert row["output_tokens"] == 25
        assert row["duration_ms"] > 0

    def test_decorator_with_model_arg(self, _isolated_db: Path) -> None:
        @track_span(model="gpt-5.4-mini")
        def my_func() -> dict:
            return {
                "content": "hi",
                "model": "gpt-5.4-mini",
                "input_tokens": 10,
                "output_tokens": 5,
                "cost_usd": 0.0001,
            }

        my_func()
        conn = _conn(_isolated_db)
        row = conn.execute("SELECT * FROM spans").fetchone()
        conn.close()
        assert row["model"] == "gpt-5.4-mini"

    def test_decorator_captures_job_id_kwarg(self, _isolated_db: Path) -> None:
        @track_span
        def my_func(*, job_id: str | None = None) -> dict:
            return {
                "content": "ok",
                "model": "gpt-5.4-mini",
                "input_tokens": 1,
                "output_tokens": 1,
                "cost_usd": 0.0,
            }

        my_func(job_id="job-123")
        conn = _conn(_isolated_db)
        row = conn.execute("SELECT * FROM spans").fetchone()
        conn.close()
        assert row["job_id"] == "job-123"

    def test_decorator_measures_duration(self, _isolated_db: Path) -> None:
        @track_span
        def slow_func() -> dict:
            time.sleep(0.05)
            return {
                "content": "",
                "model": "gpt-5.4-mini",
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            }

        slow_func()
        conn = _conn(_isolated_db)
        row = conn.execute("SELECT * FROM spans").fetchone()
        conn.close()
        assert row["duration_ms"] >= 40  # at least 40ms


# ---------------------------------------------------------------------------
# 2. call_llm message structure
# ---------------------------------------------------------------------------


class TestCallLlm:
    """call_llm structures stable prefix + variable suffix."""

    def test_openai_message_structure(self) -> None:
        from utils.call_llm import build_openai_request

        req = build_openai_request(
            stable_prefix=[
                {"role": "system", "content": "You are Vizier."},
                {"role": "system", "content": "Client config: DMB Raya."},
            ],
            variable_suffix=[
                {"role": "user", "content": "Generate a poster headline."},
            ],
            model="gpt-5.4-mini",
            temperature=0.7,
            max_tokens=4096,
        )
        # Stable prefix comes first, then variable suffix
        messages = req["messages"]
        assert messages[0]["content"] == "You are Vizier."
        assert messages[1]["content"] == "Client config: DMB Raya."
        assert messages[2]["content"] == "Generate a poster headline."
        assert req["model"] == "gpt-5.4-mini"

    def test_anthropic_cache_control_headers(self) -> None:
        from utils.call_llm import build_anthropic_request

        body, headers = build_anthropic_request(
            stable_prefix=[
                {"role": "system", "content": "You are Vizier."},
                {"role": "system", "content": "Client config: DMB Raya."},
            ],
            variable_suffix=[
                {"role": "user", "content": "Generate a poster headline."},
            ],
            model="claude-sonnet-4-6",
            temperature=0.7,
            max_tokens=4096,
        )
        # System messages should have cache_control
        for block in body["system"]:
            assert "cache_control" in block, (
                "Stable prefix blocks must have cache_control"
            )
            assert block["cache_control"] == {"type": "ephemeral"}

        # Token-efficient tools header for Claude 4
        assert "anthropic-beta" in headers
        assert "token-efficient-tools" in headers["anthropic-beta"]

    def test_anthropic_variable_suffix_no_cache(self) -> None:
        from utils.call_llm import build_anthropic_request

        body, _ = build_anthropic_request(
            stable_prefix=[{"role": "system", "content": "Persona."}],
            variable_suffix=[{"role": "user", "content": "Job content."}],
            model="claude-sonnet-4-6",
            temperature=0.7,
            max_tokens=4096,
        )
        # Variable suffix messages should NOT have cache_control
        for msg in body["messages"]:
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    assert "cache_control" not in block
            else:
                assert "cache_control" not in msg

    def test_call_llm_returns_standard_dict(self) -> None:
        """call_llm returns {content, model, input_tokens, output_tokens, cost_usd}."""
        from utils.call_llm import call_llm

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "model": "gpt-5.4-mini",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
            },
        }

        with patch("utils.call_llm.httpx.post", return_value=mock_response):
            result = call_llm(
                stable_prefix=[{"role": "system", "content": "Persona."}],
                variable_suffix=[{"role": "user", "content": "Hi."}],
            )

        assert "content" in result
        assert "model" in result
        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "cost_usd" in result
        assert result["content"] == "Hello!"
        assert result["model"] == "gpt-5.4-mini"
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 20


# ---------------------------------------------------------------------------
# 3. Diagnostic queries
# ---------------------------------------------------------------------------


class TestDiagnostics:
    """5 diagnostic queries return results on test data."""

    def _seed_spans(self, db_path: Path) -> None:
        """Insert test span data with recent timestamps."""
        conn = _conn(db_path)
        spans = [
            ("s1", "gpt-5.4-mini", 100, 50, 0.001, 120.0, "job-1", "generation", "now"),
            ("s2", "gpt-5.4-mini", 200, 100, 0.002, 200.0, "job-1", "scoring", "now"),
            ("s3", "gpt-5.4-mini", 50, 25, 0.0005, 80.0, "job-2", "generation", "now"),
            ("s4", "gpt-5.4-mini", 300, 150, 0.003, 500.0, None, "routing", "now"),
            ("s5", "gpt-5.4-mini", 75, 30, 0.0008, 90.0, None, "memory", "now"),
        ]
        for span in spans:
            conn.execute(
                """INSERT INTO spans
                   (step_id, model, input_tokens, output_tokens, cost_usd,
                    duration_ms, job_id, step_type, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime(?))""",
                span,
            )
        conn.commit()
        conn.close()

    def test_cost_by_model(self, _isolated_db: Path) -> None:
        from utils.diagnostics import cost_by_model

        self._seed_spans(_isolated_db)
        results = cost_by_model(_isolated_db)
        assert len(results) > 0
        assert results[0]["model"] == "gpt-5.4-mini"
        assert results[0]["total_cost"] == pytest.approx(0.0073, abs=0.0001)

    def test_avg_latency_by_step_type(self, _isolated_db: Path) -> None:
        from utils.diagnostics import avg_latency_by_step_type

        self._seed_spans(_isolated_db)
        results = avg_latency_by_step_type(_isolated_db)
        assert len(results) > 0
        types = {r["step_type"] for r in results}
        assert "generation" in types

    def test_token_burn_by_job(self, _isolated_db: Path) -> None:
        from utils.diagnostics import token_burn_by_job

        self._seed_spans(_isolated_db)
        results = token_burn_by_job(_isolated_db)
        assert len(results) > 0
        job_ids = {r["job_id"] for r in results}
        assert "job-1" in job_ids

    def test_idle_burn_detection(self, _isolated_db: Path) -> None:
        from utils.diagnostics import idle_burn_detection

        self._seed_spans(_isolated_db)
        results = idle_burn_detection(_isolated_db)
        assert len(results) == 2  # s4 and s5 have no job_id

    def test_cost_per_client_query(self) -> None:
        from utils.diagnostics import cost_per_client_query

        query = cost_per_client_query()
        assert isinstance(query, str)
        assert "client" in query.lower()
        assert "cost" in query.lower()
        assert "JOIN" in query or "join" in query


# ---------------------------------------------------------------------------
# 4. Idle alarm
# ---------------------------------------------------------------------------


class TestIdleAlarm:
    """Idle token alarm fires on spans without job_id."""

    def test_alarm_fires_above_threshold(self, _isolated_db: Path) -> None:
        from utils.idle_alarm import check_idle_burn

        # Insert 12 idle spans (above default threshold of 10)
        conn = _conn(_isolated_db)
        for i in range(12):
            conn.execute(
                """INSERT INTO spans
                   (step_id, model, input_tokens, output_tokens, cost_usd,
                    duration_ms, job_id, timestamp)
                   VALUES (?, 'gpt-5.4-mini', 10, 5, 0.0001, 50.0, NULL,
                           datetime('now'))""",
                (f"idle-{i}",),
            )
        conn.commit()
        conn.close()

        alert = check_idle_burn(_isolated_db)
        assert alert is not None
        assert alert["count"] == 12
        assert alert["exceeds_threshold"] is True

    def test_no_alarm_below_threshold(self, _isolated_db: Path) -> None:
        from utils.idle_alarm import check_idle_burn

        # Insert 3 idle spans (below threshold)
        conn = _conn(_isolated_db)
        for i in range(3):
            conn.execute(
                """INSERT INTO spans
                   (step_id, model, input_tokens, output_tokens, cost_usd,
                    duration_ms, job_id, timestamp)
                   VALUES (?, 'gpt-5.4-mini', 10, 5, 0.0001, 50.0, NULL,
                           datetime('now'))""",
                (f"ok-{i}",),
            )
        conn.commit()
        conn.close()

        alert = check_idle_burn(_isolated_db)
        assert alert is not None
        assert alert["count"] == 3
        assert alert["exceeds_threshold"] is False

    def test_excludes_spans_with_job_id(self, _isolated_db: Path) -> None:
        from utils.idle_alarm import check_idle_burn

        conn = _conn(_isolated_db)
        # 15 spans WITH job_id — should not count
        for i in range(15):
            conn.execute(
                """INSERT INTO spans
                   (step_id, model, input_tokens, output_tokens, cost_usd,
                    duration_ms, job_id, timestamp)
                   VALUES (?, 'gpt-5.4-mini', 10, 5, 0.0001, 50.0, 'job-x',
                           datetime('now'))""",
                (f"busy-{i}",),
            )
        conn.commit()
        conn.close()

        alert = check_idle_burn(_isolated_db)
        assert alert is not None
        assert alert["count"] == 0
        assert alert["exceeds_threshold"] is False
