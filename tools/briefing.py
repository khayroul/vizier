"""Briefing module — morning brief + Maghrib shutdown.

Cross-cutting crons that synthesize Vizier (BizOps) and Steward data.
Implements 3-gate cron requirement (anti-drift #29).
Calls feedback_check_silence() for DEV-007 compliance.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from tools.bizops import maghrib_summary_data, morning_brief_data
from tools.steward import get_next, get_snapshot, steward_brief_data
from utils.database import get_cursor
from utils.prayer_times import get_prayer_times
from utils.spans import track_span

logger = logging.getLogger(__name__)


def _check_three_gates() -> dict[str, Any]:
    """Check the 3 gates for morning brief (anti-drift #29).

    Gate 1: Current time is after today's Subuh prayer.
    Gate 2: New data exists since last morning brief.
    Gate 3: Morning brief hasn't already fired today.
    """
    today = date.today()
    now = datetime.now()
    prayer_times = get_prayer_times(today)

    # Gate 1: After Subuh
    subuh_dt = datetime.combine(today, prayer_times["subuh"])
    gate1 = now >= subuh_dt

    # Gate 3: Not already fired today
    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM steward_reviews "
            "WHERE review_type = 'daily_brief' AND review_date = %s",
            (today,),
        )
        row = cur.fetchone()
        assert row is not None
        gate3 = row["cnt"] == 0

    # Gate 2: New data since last brief
    gate2 = False
    with get_cursor() as cur:
        cur.execute(
            "SELECT MAX(created_at) AS last_brief FROM steward_reviews "
            "WHERE review_type = 'daily_brief'"
        )
        row = cur.fetchone()
        last_brief = row["last_brief"] if row else None

        if last_brief is None:
            gate2 = True
        else:
            # Check key tables for new data since last brief
            # Each table uses a different timestamp column
            table_ts: dict[str, str] = {
                "jobs": "created_at",
                "invoices": "issued_at",
                "payments": "received_at",
                "steward_inbox": "created_at",
            }
            for table, ts_col in table_ts.items():
                cur.execute(
                    f"SELECT MAX({ts_col}) AS latest FROM {table}"  # noqa: S608
                )
                latest_row = cur.fetchone()
                if (
                    latest_row
                    and latest_row["latest"]
                    and latest_row["latest"] > last_brief
                ):
                    gate2 = True
                    break

    return {
        "gate1_after_subuh": gate1,
        "gate2_new_data": gate2,
        "gate3_not_fired_today": gate3,
        "should_fire": gate1 and gate2 and gate3,
    }


@track_span(step_type="briefing")
def morning_brief() -> dict[str, Any]:
    """Generate the morning brief if all 3 gates pass.

    Calls feedback_check_silence() for DEV-007.
    Records the brief in steward_reviews.
    """
    gates = _check_three_gates()
    if not gates["should_fire"]:
        logger.info("Morning brief skipped — gates: %s", gates)
        return {"fired": False, "gates": gates, "silence_flagged": 0}

    # DEV-007: Call feedback_check_silence
    with get_cursor() as cur:
        cur.execute("SELECT feedback_check_silence()")
        row = cur.fetchone()
        assert row is not None
        silence_count = row["feedback_check_silence"]

    vizier_data = morning_brief_data()
    steward_data = steward_brief_data()

    brief_text = _generate_brief_text(vizier_data, steward_data, silence_count)

    # Record the brief
    today = date.today()
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO steward_reviews
              (review_type, review_date, completion_stats, domain_scores)
            VALUES ('daily_brief', %s, %s::jsonb, %s::jsonb)
            """,
            (today, '{"type": "morning_brief"}', "{}"),
        )

    return {
        "fired": True,
        "gates": gates,
        "silence_flagged": silence_count,
        "vizier": vizier_data,
        "steward": steward_data,
        "brief_text": brief_text,
    }


def _generate_brief_text(
    vizier: dict[str, Any],
    steward: dict[str, Any],
    silence_count: int,
) -> str:
    """Format the morning brief as readable text."""
    lines = ["Assalamualaikum. Morning brief:\n"]

    lines.append(f"Active jobs: {vizier['active_jobs']}")
    if vizier["revenue"]:
        rev = vizier["revenue"]
        lines.append(
            f"Revenue (month): RM {rev['invoiced_rm']:,.2f} invoiced, "
            f"RM {rev['received_rm']:,.2f} received"
        )
        if rev["overdue_rm"] > 0:
            lines.append(f"Overdue: RM {rev['overdue_rm']:,.2f}")
    if vizier["pipeline"]:
        lines.append(f"Pipeline: {vizier['pipeline']}")

    lines.append(f"\nInbox: {steward['unprocessed_inbox']} unprocessed")
    lines.append(f"Active tasks: {steward['active_tasks']}")
    if steward["top_3_tasks"]:
        lines.append("\nToday's focus:")
        for i, task in enumerate(steward["top_3_tasks"], 1):
            est = (
                f" (~{task['time_estimate_min']}min)"
                if task.get("time_estimate_min")
                else ""
            )
            lines.append(f"  {i}. {task['title']}{est}")

    if silence_count > 0:
        lines.append(f"\n{silence_count} feedback item(s) flagged as silent")

    return "\n".join(lines)


@track_span(step_type="briefing")
def maghrib_shutdown() -> dict[str, Any]:
    """Maghrib shutdown: Vizier production + Steward personal + tomorrow's top 3."""
    vizier_data = maghrib_summary_data()
    steward_snapshot = get_snapshot()

    tomorrow_tasks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _ in range(3):
        task = get_next()
        if task is None or task["id"] in seen:
            break
        tomorrow_tasks.append(
            {
                "title": task["title"],
                "domain": task["domain"],
            }
        )
        seen.add(task["id"])

    return {
        "vizier_summary": vizier_data,
        "steward_summary": {
            "active_tasks": steward_snapshot["active_tasks"],
            "today_done": steward_snapshot["today_done"],
            "domain_heatmap": steward_snapshot["domain_heatmap"],
        },
        "tomorrow_top_3": tomorrow_tasks,
    }
