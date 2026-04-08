"""S16 — Briefing cron tests.

Covers: morning brief 3-gate check, Maghrib shutdown, silence detection.

Requires: running Postgres (vizier db).
"""

from __future__ import annotations

import os
from datetime import datetime, time
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.requires_db

os.environ.setdefault("DATABASE_URL", "postgres://localhost:5432/vizier")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")

from utils.database import get_cursor, run_migration


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema() -> None:
    """Run core + extended SQL."""
    base = Path(__file__).resolve().parent.parent / "migrations"
    for sql_file in ["core.sql", "extended.sql"]:
        sql_path = base / sql_file
        if sql_path.exists():
            run_migration(sql_path)


# ---------------------------------------------------------------------------
# 3-gate tests
# ---------------------------------------------------------------------------


def test_morning_brief_gate_skips_if_already_fired() -> None:
    """Morning brief does NOT fire if already fired today (gate 3 fails)."""
    from tools.briefing import _check_three_gates

    # Insert a daily_brief for today
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO steward_reviews (review_type, review_date) "
            "VALUES ('daily_brief', CURRENT_DATE)"
        )

    mock_times = {
        "subuh": time(5, 45),
        "zohor": time(13, 0),
        "asr": time(16, 25),
        "maghrib": time(19, 12),
        "isyak": time(20, 23),
    }

    with patch("tools.briefing.get_prayer_times", return_value=mock_times):
        with patch("tools.briefing.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 8, 8, 0)
            mock_dt.combine = datetime.combine
            gates = _check_three_gates()

    assert gates["gate3_not_fired_today"] is False
    assert gates["should_fire"] is False

    # Clean up
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM steward_reviews "
            "WHERE review_type = 'daily_brief' AND review_date = CURRENT_DATE"
        )


def test_morning_brief_gate_passes_with_new_data() -> None:
    """Morning brief fires when all 3 gates pass."""
    from tools.briefing import _check_three_gates

    # Ensure no daily_brief exists for today
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM steward_reviews "
            "WHERE review_type = 'daily_brief' AND review_date = CURRENT_DATE"
        )
        # Insert new data
        cur.execute(
            "INSERT INTO steward_inbox (raw_input, input_type) "
            "VALUES ('New data for brief test', 'text')"
        )

    mock_times = {
        "subuh": time(5, 45),
        "zohor": time(13, 0),
        "asr": time(16, 25),
        "maghrib": time(19, 12),
        "isyak": time(20, 23),
    }

    with patch("tools.briefing.get_prayer_times", return_value=mock_times):
        with patch("tools.briefing.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 8, 8, 0)
            mock_dt.combine = datetime.combine
            gates = _check_three_gates()

    assert gates["gate1_after_subuh"] is True
    assert gates["gate2_new_data"] is True
    assert gates["gate3_not_fired_today"] is True
    assert gates["should_fire"] is True


# ---------------------------------------------------------------------------
# Morning brief integration
# ---------------------------------------------------------------------------


def test_morning_brief_calls_feedback_check_silence() -> None:
    """Morning brief calls feedback_check_silence() and includes count."""
    from tools.briefing import morning_brief

    # Ensure gates pass
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM steward_reviews "
            "WHERE review_type = 'daily_brief' AND review_date = CURRENT_DATE"
        )

    mock_times = {
        "subuh": time(5, 45),
        "zohor": time(13, 0),
        "asr": time(16, 25),
        "maghrib": time(19, 12),
        "isyak": time(20, 23),
    }

    with patch("tools.briefing.get_prayer_times", return_value=mock_times):
        with patch("tools.briefing.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 8, 8, 0)
            mock_dt.combine = datetime.combine
            result = morning_brief()

    assert result is not None
    assert "silence_flagged" in result
    assert isinstance(result["silence_flagged"], int)


# ---------------------------------------------------------------------------
# Maghrib shutdown
# ---------------------------------------------------------------------------


def test_maghrib_shutdown_produces_summary() -> None:
    """Maghrib shutdown returns Vizier + Steward summaries."""
    from tools.briefing import maghrib_shutdown

    result = maghrib_shutdown()
    assert "vizier_summary" in result
    assert "steward_summary" in result
    assert "tomorrow_top_3" in result
    assert "active_tasks" in result["steward_summary"]
    assert "domain_heatmap" in result["steward_summary"]
