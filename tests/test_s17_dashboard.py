"""S17 Dashboard — integration tests.

Tests PostgREST endpoints, dashboard views, and build output.
Requires: PostgREST running on port 3001, vizier database with data.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Generator

import httpx
import pytest

POSTGREST_URL = "http://localhost:3001"
DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"


# ---------- PostgREST endpoint tests ----------


@pytest.fixture(scope="module")
def client() -> Generator[httpx.Client, None, None]:
    with httpx.Client(base_url=POSTGREST_URL, timeout=10) as c:
        try:
            probe = c.get("/jobs", params={"limit": 1})
        except httpx.HTTPError as exc:
            pytest.skip(f"PostgREST not reachable at {POSTGREST_URL}: {exc}")

        content_type = probe.headers.get("content-type", "")
        if probe.status_code != 200 or "application/json" not in content_type:
            pytest.skip(
                f"PostgREST not available at {POSTGREST_URL} "
                f"(status={probe.status_code}, content_type={content_type!r})"
            )
        yield c


def test_postgrest_serves_jobs(client: httpx.Client) -> None:
    resp = client.get("/jobs", params={"limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "id" in data[0]
    assert "status" in data[0]
    assert "production_trace" in data[0]


def test_postgrest_serves_clients(client: httpx.Client) -> None:
    resp = client.get("/clients", params={"limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "name" in data[0]


def test_postgrest_serves_feedback(client: httpx.Client) -> None:
    resp = client.get("/feedback", params={"limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "feedback_status" in data[0]


def test_postgrest_serves_pipeline(client: httpx.Client) -> None:
    resp = client.get("/pipeline", params={"limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "stage" in data[0]


# ---------- Dashboard view tests ----------


def test_v_job_traces_columns(client: httpx.Client) -> None:
    resp = client.get("/v_job_traces", params={"limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    row = data[0]
    expected_cols = [
        "id", "client_id", "client_name", "job_type", "status",
        "step_count", "total_tokens", "total_cost_usd", "last_step",
        "raw_trace", "goal_chain",
    ]
    for col in expected_cols:
        assert col in row, f"Missing column: {col}"


def test_v_token_spend_daily_columns(client: httpx.Client) -> None:
    resp = client.get("/v_token_spend_daily", params={"limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    row = data[0]
    assert "day" in row
    assert "tokens" in row
    assert "cost_usd" in row
    assert "job_count" in row


def test_v_feedback_summary(client: httpx.Client) -> None:
    resp = client.get("/v_feedback_summary")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    row = data[0]
    assert "status" in row
    assert "count" in row


def test_v_pipeline_summary(client: httpx.Client) -> None:
    resp = client.get("/v_pipeline_summary")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    row = data[0]
    assert "stage" in row
    assert "count" in row
    assert "total_value_rm" in row


def test_v_pipeline_detail(client: httpx.Client) -> None:
    resp = client.get("/v_pipeline_detail", params={"limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    row = data[0]
    assert "prospect_name" in row
    assert "days_in_stage" in row


def test_v_token_spend_by_model(client: httpx.Client) -> None:
    resp = client.get("/v_token_spend_by_model", params={"limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    row = data[0]
    assert "model" in row
    assert "tokens" in row


def test_v_system_health(client: httpx.Client) -> None:
    resp = client.get("/v_system_health")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["active_jobs"] >= 0


def test_v_overdue_invoices(client: httpx.Client) -> None:
    resp = client.get("/v_overdue_invoices")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # May be empty — that's fine


# ---------- Dashboard build test ----------


def test_dashboard_builds_without_errors() -> None:
    """Verify the Vite production build completes successfully."""
    result = subprocess.run(
        ["bash", "-c", 'eval "$(/opt/homebrew/bin/brew shellenv)" && npx tsc --noEmit && npx vite build'],
        cwd=str(DASHBOARD_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"Build failed:\n{result.stderr}"
    dist = DASHBOARD_DIR / "dist"
    assert dist.exists(), "dist/ directory not created"
    index = dist / "index.html"
    assert index.exists(), "dist/index.html not found"


# ---------- Data integrity tests ----------


def test_feedback_excludes_anchor_set(client: httpx.Client) -> None:
    """v_feedback_summary should exclude anchor_set records (anti-drift #56)."""
    resp = client.get("/v_feedback_summary")
    data = resp.json()
    # The view filters WHERE anchor_set = false
    # Verify by comparing to raw count
    raw_resp = client.get("/feedback", params={"select": "id", "anchor_set": "eq.false"})
    raw_count = len(raw_resp.json())
    view_total = sum(r["count"] for r in data)
    assert view_total == raw_count


def test_production_trace_jsonb_flattened(client: httpx.Client) -> None:
    """v_job_traces should flatten production_trace JSONB into columns."""
    resp = client.get(
        "/v_job_traces",
        params={"production_trace": "not.is.null", "limit": 1},
    )
    # Use raw_trace filter instead
    resp = client.get(
        "/v_job_traces",
        params={"raw_trace": "not.is.null", "limit": 1},
    )
    data = resp.json()
    if len(data) > 0:
        row = data[0]
        assert row["step_count"] is not None
        assert isinstance(row["step_count"], int)
        assert row["raw_trace"] is not None  # raw JSONB still available
