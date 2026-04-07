"""Five SQL diagnostic queries against the local spans table.

Queries:
1. Total cost by model (last 24h / 7d / 30d)
2. Average latency by step type
3. Token burn by job
4. Idle burn detection (spans without job_id)
5. Cost per client (returns query string — join needs jobs table from S10a)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from utils.spans import DB_PATH


def _conn(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# 1. Total cost by model
# ---------------------------------------------------------------------------


def cost_by_model(
    db_path: Path | None = None,
    period: str = "30d",
) -> list[dict[str, Any]]:
    """Total cost grouped by model for the given period.

    Args:
        db_path: Override database path (used in tests).
        period: One of ``"24h"``, ``"7d"``, ``"30d"``.
    """
    interval_map = {"24h": "-1 day", "7d": "-7 days", "30d": "-30 days"}
    interval = interval_map.get(period, "-30 days")

    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """
            SELECT model,
                   SUM(cost_usd)        AS total_cost,
                   SUM(input_tokens)     AS total_input_tokens,
                   SUM(output_tokens)    AS total_output_tokens,
                   COUNT(*)              AS span_count
            FROM spans
            WHERE timestamp >= datetime('now', ?)
            GROUP BY model
            ORDER BY total_cost DESC
            """,
            (interval,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 2. Average latency by step type
# ---------------------------------------------------------------------------


def avg_latency_by_step_type(
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Average duration_ms grouped by step_type."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """
            SELECT step_type,
                   AVG(duration_ms) AS avg_duration_ms,
                   COUNT(*)         AS span_count
            FROM spans
            WHERE step_type IS NOT NULL
            GROUP BY step_type
            ORDER BY avg_duration_ms DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 3. Token burn by job
# ---------------------------------------------------------------------------


def token_burn_by_job(
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Total tokens and cost per job_id."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """
            SELECT job_id,
                   SUM(input_tokens)  AS total_input,
                   SUM(output_tokens) AS total_output,
                   SUM(cost_usd)      AS total_cost,
                   COUNT(*)           AS span_count
            FROM spans
            WHERE job_id IS NOT NULL
            GROUP BY job_id
            ORDER BY total_cost DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. Idle burn detection
# ---------------------------------------------------------------------------


def idle_burn_detection(
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return all spans that have no associated job_id (idle burn)."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """
            SELECT step_id, model, input_tokens, output_tokens,
                   cost_usd, duration_ms, step_type, timestamp
            FROM spans
            WHERE job_id IS NULL
            ORDER BY timestamp DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 5. Cost per client (query string — needs jobs table from S10a)
# ---------------------------------------------------------------------------


def cost_per_client_query() -> str:
    """Return SQL query string for cost-per-client.

    This query requires the ``jobs`` table (created by S10a) which links
    ``job_id`` to ``client_id``.  Until S10a ships, this returns the
    query string without execution.
    """
    return """
        SELECT j.client_id,
               SUM(s.cost_usd)        AS total_cost,
               SUM(s.input_tokens)    AS total_input_tokens,
               SUM(s.output_tokens)   AS total_output_tokens,
               COUNT(*)               AS span_count
        FROM spans s
        JOIN jobs j ON s.job_id = j.job_id
        WHERE s.job_id IS NOT NULL
        GROUP BY j.client_id
        ORDER BY total_cost DESC
    """
