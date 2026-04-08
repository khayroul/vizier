"""S16 — Steward tests.

Covers: domain constants, prayer times, inbox capture, /next, /done,
/snapshot, /project decomposition, domain balance.

Requires: running Postgres (vizier db).
"""

from __future__ import annotations

import json
import os
from datetime import date, time
from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = pytest.mark.requires_db

os.environ.setdefault("DATABASE_URL", "postgres://localhost:5432/vizier")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")

from utils.database import get_cursor, run_migration

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema() -> None:
    """Run core.sql + extended.sql to guarantee all tables exist."""
    base = Path(__file__).resolve().parent.parent / "migrations"
    for sql_file in ["core.sql", "extended.sql"]:
        sql_path = base / sql_file
        if sql_path.exists():
            run_migration(sql_path)


@pytest.fixture()
def active_task() -> str:
    """Create an active task and return its id."""
    task_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO steward_tasks
              (id, title, next_action, context, energy_level,
               time_estimate_min, domain, status)
            VALUES (%s, 'Test task for next', true, 'computer', 'medium',
                    15, 'Career', 'active')
            """,
            (task_id,),
        )
    return task_id


# ---------------------------------------------------------------------------
# Domain constants tests
# ---------------------------------------------------------------------------


def test_domains_are_21_unique_strings() -> None:
    """Domain constants: exactly 21 unique non-empty strings."""
    from config.steward_domains import DOMAINS

    assert len(DOMAINS) == 21
    assert len(set(DOMAINS)) == 21
    for domain in DOMAINS:
        assert isinstance(domain, str)
        assert len(domain) > 0


# ---------------------------------------------------------------------------
# Prayer times tests
# ---------------------------------------------------------------------------


def test_prayer_times_returns_five_prayers() -> None:
    """Prayer times: returns dict with 5 prayer times for a given date."""
    from utils.prayer_times import get_prayer_times

    times = get_prayer_times(date(2026, 4, 8))
    assert "subuh" in times
    assert "zohor" in times
    assert "asr" in times
    assert "maghrib" in times
    assert "isyak" in times
    for prayer_time in times.values():
        assert isinstance(prayer_time, time)


def test_prayer_times_subuh_before_asr() -> None:
    """Subuh is always before Asr."""
    from utils.prayer_times import get_prayer_times

    times = get_prayer_times(date(2026, 4, 8))
    assert times["subuh"] < times["asr"]


# ---------------------------------------------------------------------------
# Inbox capture tests
# ---------------------------------------------------------------------------


def test_capture_inbox_zero_tokens() -> None:
    """capture_inbox stores text and returns immediately, no LLM call."""
    from tools.steward import capture_inbox

    result = capture_inbox(raw_input="Buy groceries for Ramadan")
    assert result["captured"] is True
    assert result["inbox_id"] is not None

    with get_cursor() as cur:
        cur.execute(
            "SELECT raw_input, processed FROM steward_inbox WHERE id = %s",
            (result["inbox_id"],),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["raw_input"] == "Buy groceries for Ramadan"
        assert row["processed"] is False


def test_capture_inbox_with_source_message() -> None:
    """capture_inbox stores source_message_id."""
    from tools.steward import capture_inbox

    result = capture_inbox(
        raw_input="Call Ahmad about the proposal",
        input_type="text",
        source_message_id="tg-msg-12345",
    )
    with get_cursor() as cur:
        cur.execute(
            "SELECT source_message_id FROM steward_inbox WHERE id = %s",
            (result["inbox_id"],),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["source_message_id"] == "tg-msg-12345"


# ---------------------------------------------------------------------------
# /next tests
# ---------------------------------------------------------------------------


def test_get_next_returns_one_task(active_task: str) -> None:
    """get_next returns exactly ONE task with explanation."""
    from tools.steward import get_next

    result = get_next()
    assert result is not None
    assert "title" in result
    assert "explanation" in result
    assert isinstance(result["explanation"], str)


def test_get_next_filters_low_energy(active_task: str) -> None:
    """get_next with energy=low only returns low-energy tasks."""
    from tools.steward import get_next

    low_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO steward_tasks
              (id, title, next_action, context, energy_level,
               time_estimate_min, domain, status)
            VALUES (%s, 'Low energy task', true, 'anywhere', 'low',
                    5, 'Health', 'active')
            """,
            (low_id,),
        )

    result = get_next(energy="low")
    assert result is not None
    assert result["energy_level"] == "low"


# ---------------------------------------------------------------------------
# /done tests
# ---------------------------------------------------------------------------


def test_mark_done_updates_streak(active_task: str) -> None:
    """mark_done completes task and returns streak + domain progress."""
    from tools.steward import mark_done

    result = mark_done(active_task, note="Learned something new")
    assert result["task_id"] == active_task
    assert result["streak_count"] >= 1
    assert "domain" in result
    assert "domain_progress" in result
    assert "win_summary" in result

    with get_cursor() as cur:
        cur.execute(
            "SELECT status, completion_note FROM steward_tasks WHERE id = %s",
            (active_task,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["status"] == "done"
        assert row["completion_note"] == "Learned something new"


# ---------------------------------------------------------------------------
# /snapshot tests
# ---------------------------------------------------------------------------


def test_get_snapshot_returns_domain_heatmap() -> None:
    """get_snapshot returns active tasks, overdue, heatmap, streak."""
    from tools.steward import get_snapshot

    result = get_snapshot()
    assert "active_tasks" in result
    assert "overdue_tasks" in result
    assert "today_done" in result
    assert "domain_heatmap" in result
    assert isinstance(result["domain_heatmap"], dict)
    assert len(result["domain_heatmap"]) == 21


# ---------------------------------------------------------------------------
# Domain balance tests
# ---------------------------------------------------------------------------


def test_domain_balance_nudges_neglected() -> None:
    """get_next prioritises tasks in neglected domains."""
    from tools.steward import get_next

    with get_cursor() as cur:
        # Clean slate: remove all existing tasks so prior test runs
        # don't pollute scoring (e.g. completed Finance tasks from
        # previous runs would negate the neglect boost).
        cur.execute("DELETE FROM steward_tasks")

        # Complete some Career tasks to make it "active"
        for i in range(3):
            tid = str(uuid4())
            cur.execute(
                "INSERT INTO steward_tasks "
                "(id, title, next_action, domain, status, energy_level, completed_at) "
                "VALUES (%s, %s, false, 'Career', 'done', 'medium', now())",
                (tid, f"Career task {i}"),
            )

        # Create active tasks in Career and Finance (neglected)
        career_id = str(uuid4())
        cur.execute(
            "INSERT INTO steward_tasks "
            "(id, title, next_action, domain, status, energy_level, "
            "time_estimate_min, context) "
            "VALUES (%s, 'Career task', true, 'Career', 'active', 'medium', "
            "15, 'computer')",
            (career_id,),
        )

        finance_id = str(uuid4())
        cur.execute(
            "INSERT INTO steward_tasks "
            "(id, title, next_action, domain, status, energy_level, "
            "time_estimate_min, context) "
            "VALUES (%s, 'Finance task', true, 'Finance', 'active', 'medium', "
            "15, 'computer')",
            (finance_id,),
        )

    result = get_next(energy="high")
    assert result is not None
    # Finance should score higher due to domain neglect
    assert result["domain"] == "Finance"


# ---------------------------------------------------------------------------
# /project tests
# ---------------------------------------------------------------------------


def test_decompose_project_creates_project() -> None:
    """decompose_project creates a project record in DB."""
    from unittest.mock import patch

    from tools.steward import decompose_project

    mock_tasks = json.dumps(
        {
            "tasks": [
                {
                    "title": "Research KDP guidelines",
                    "context": "computer",
                    "energy_level": "medium",
                    "time_estimate_min": 30,
                }
            ],
        }
    )
    mock_llm_response = {"content": mock_tasks}
    with patch("tools.steward.call_llm", return_value=mock_llm_response):
        result = decompose_project(
            objective="Set up KDP publishing pipeline",
            domain="Career",
        )
    assert "proposed_tasks" in result
    assert isinstance(result["proposed_tasks"], list)
    assert len(result["proposed_tasks"]) >= 1
    assert result["id"] is not None

    with get_cursor() as cur:
        cur.execute(
            "SELECT title, domain FROM steward_projects WHERE id = %s",
            (str(result["id"]),),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["domain"] == "Career"


def test_confirm_decomposition_creates_tasks() -> None:
    """confirm_decomposition creates tasks linked to project."""
    from unittest.mock import patch

    from tools.steward import confirm_decomposition, decompose_project

    mock_tasks = json.dumps(
        {
            "tasks": [
                {
                    "title": "Research topic",
                    "context": "computer",
                    "energy_level": "medium",
                    "time_estimate_min": 30,
                }
            ],
        }
    )
    mock_llm_response = {"content": mock_tasks}
    with patch("tools.steward.call_llm", return_value=mock_llm_response):
        project = decompose_project(
            objective="Test project decomposition",
            domain="Learning",
        )

    tasks = [
        {
            "title": "Research topic",
            "context": "computer",
            "energy_level": "medium",
            "time_estimate_min": 30,
        },
        {
            "title": "Write outline",
            "context": "computer",
            "energy_level": "high",
            "time_estimate_min": 45,
        },
    ]

    created = confirm_decomposition(str(project["id"]), tasks)
    assert len(created) == 2
    assert created[0]["domain"] == "Learning"

    with get_cursor() as cur:
        cur.execute(
            "SELECT total_tasks, decomposed FROM steward_projects WHERE id = %s",
            (str(project["id"]),),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["total_tasks"] == 2
        assert row["decomposed"] is True
