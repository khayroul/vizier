"""BizOps tools — pipeline CRUD, client health, revenue summary.

All queries use the Postgres tables from migrations/extended.sql.
Model: GPT-5.4-mini for any LLM work (anti-drift #54).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from utils.database import get_cursor
from utils.spans import track_span

logger = logging.getLogger(__name__)

# Valid pipeline stages and allowed transitions
PIPELINE_STAGES = ["lead", "contacted", "proposal_sent", "negotiating", "won", "lost"]

_VALID_TRANSITIONS: dict[str, list[str]] = {
    "lead": ["contacted", "lost"],
    "contacted": ["proposal_sent", "lost"],
    "proposal_sent": ["negotiating", "lost"],
    "negotiating": ["won", "lost"],
    "won": [],
    "lost": [],
}


@track_span(step_type="bizops")
def update_pipeline(
    *,
    prospect_name: str,
    stage: str,
    pipeline_id: str | None = None,
    client_id: str | None = None,
    estimated_value_rm: float | None = None,
    source: str | None = None,
    notes: str | None = None,
    next_followup_at: datetime | None = None,
) -> dict[str, Any]:
    """Create or update a pipeline entry.

    If pipeline_id is None, creates a new entry at the given stage.
    If pipeline_id is provided, validates the stage transition.

    Raises:
        ValueError: If stage is invalid or transition is not allowed.
    """
    if stage not in PIPELINE_STAGES:
        raise ValueError(f"Invalid stage: {stage}. Valid: {PIPELINE_STAGES}")

    if pipeline_id is not None:
        with get_cursor() as cur:
            cur.execute("SELECT stage FROM pipeline WHERE id = %s", (pipeline_id,))
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Pipeline entry not found: {pipeline_id}")
            current_stage = row["stage"]
            if stage not in _VALID_TRANSITIONS.get(current_stage, []):
                raise ValueError(
                    f"Invalid stage transition: {current_stage} → {stage}. "
                    f"Allowed: {_VALID_TRANSITIONS.get(current_stage, [])}"
                )
            cur.execute(
                """
                UPDATE pipeline
                   SET stage = %s, prospect_name = %s, notes = COALESCE(%s, notes),
                       estimated_value_rm = COALESCE(%s, estimated_value_rm),
                       next_followup_at = COALESCE(%s, next_followup_at),
                       updated_at = now()
                 WHERE id = %s
                RETURNING id, prospect_name, stage, estimated_value_rm, created_at
                """,
                (
                    stage,
                    prospect_name,
                    notes,
                    estimated_value_rm,
                    next_followup_at,
                    pipeline_id,
                ),
            )
            row = cur.fetchone()
            assert row is not None
            return dict(row)
    else:
        new_id = str(uuid4())
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline
                  (id, client_id, prospect_name, stage, estimated_value_rm,
                   source, notes, next_followup_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, prospect_name, stage, estimated_value_rm, created_at
                """,
                (
                    new_id,
                    client_id,
                    prospect_name,
                    stage,
                    estimated_value_rm,
                    source,
                    notes,
                    next_followup_at,
                ),
            )
            row = cur.fetchone()
            assert row is not None
            return dict(row)


@track_span(step_type="bizops")
def get_client_health(client_id: str | None = None) -> list[dict[str, Any]]:
    """Return client health data: overdue invoices, last job timestamps.

    Overdue = status IN ('issued', 'partial') AND due_at < now().
    """
    if client_id:
        where_clause = "WHERE c.id = %s"
        params: tuple[Any, ...] = (client_id,)
    else:
        where_clause = ""
        params = ()

    query = f"""
        SELECT
            c.id AS client_id,
            c.name AS client_name,
            (SELECT MAX(j.created_at) FROM jobs j WHERE j.client_id = c.id)
                AS last_job_at,
            (SELECT COUNT(*) FROM invoices i
             WHERE i.client_id = c.id
               AND i.status IN ('issued', 'partial')
               AND i.due_at < now())
                AS overdue_invoices,
            (SELECT COALESCE(SUM(i.amount_rm), 0) FROM invoices i
             WHERE i.client_id = c.id
               AND i.status IN ('issued', 'partial')
               AND i.due_at < now())
                AS overdue_amount_rm,
            (SELECT p.stage FROM pipeline p
             WHERE p.client_id = c.id
             ORDER BY p.updated_at DESC LIMIT 1)
                AS pipeline_stage
        FROM clients c
        {where_clause}
        ORDER BY c.name
    """
    with get_cursor() as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


@track_span(step_type="bizops")
def get_revenue_summary(period: str = "month") -> dict[str, Any]:
    """Return revenue summary: invoiced, received, outstanding, overdue."""
    if period == "week":
        start = datetime.now() - timedelta(days=datetime.now().weekday())
    else:
        start = datetime.now().replace(day=1, hour=0, minute=0, second=0)

    with get_cursor() as cur:
        cur.execute(
            "SELECT COALESCE(SUM(amount_rm), 0) AS invoiced "
            "FROM invoices WHERE issued_at >= %s",
            (start,),
        )
        row = cur.fetchone()
        assert row is not None
        invoiced = row["invoiced"]

        cur.execute(
            "SELECT COALESCE(SUM(amount_rm), 0) AS received "
            "FROM payments WHERE received_at >= %s",
            (start,),
        )
        row = cur.fetchone()
        assert row is not None
        received = row["received"]

        cur.execute(
            "SELECT COALESCE(SUM(amount_rm), 0) AS outstanding "
            "FROM invoices WHERE status IN ('issued', 'partial')"
        )
        row = cur.fetchone()
        assert row is not None
        outstanding = row["outstanding"]

        cur.execute(
            "SELECT COALESCE(SUM(amount_rm), 0) AS overdue "
            "FROM invoices "
            "WHERE status IN ('issued', 'partial') AND due_at < now()"
        )
        row = cur.fetchone()
        assert row is not None
        overdue = row["overdue"]

    return {
        "period": period,
        "period_start": start.isoformat(),
        "invoiced_rm": float(invoiced),
        "received_rm": float(received),
        "outstanding_rm": float(outstanding),
        "overdue_rm": float(overdue),
    }


def morning_brief_data() -> dict[str, Any]:
    """Aggregate data for the morning brief (Vizier side).

    Called by tools/briefing.py which adds Steward data.
    """
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM jobs WHERE status = 'active'")
        row = cur.fetchone()
        assert row is not None
        active_jobs = row["cnt"]

        cur.execute(
            "SELECT COUNT(*) AS cnt FROM jobs "
            "WHERE status = 'completed' AND updated_at >= CURRENT_DATE"
        )
        row = cur.fetchone()
        assert row is not None
        completed_today = row["cnt"]

        cur.execute(
            "SELECT stage, COUNT(*) AS cnt FROM pipeline "
            "WHERE stage NOT IN ('won', 'lost') GROUP BY stage"
        )
        pipeline = {row["stage"]: row["cnt"] for row in cur.fetchall()}

    revenue = get_revenue_summary("month")

    return {
        "active_jobs": active_jobs,
        "completed_today": completed_today,
        "pipeline": pipeline,
        "revenue": revenue,
    }


def maghrib_summary_data() -> dict[str, Any]:
    """Aggregate data for Maghrib shutdown (Vizier side)."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM jobs "
            "WHERE status = 'completed' AND updated_at >= CURRENT_DATE"
        )
        row = cur.fetchone()
        assert row is not None
        completed = row["cnt"]

        cur.execute(
            "SELECT COALESCE(SUM(amount_rm), 0) AS collected "
            "FROM payments WHERE received_at >= CURRENT_DATE"
        )
        row = cur.fetchone()
        assert row is not None
        collected = row["collected"]

    return {
        "jobs_completed_today": completed,
        "revenue_collected_today_rm": float(collected),
    }
