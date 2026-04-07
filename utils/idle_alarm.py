"""Idle token burn alarm.

Checks for spans without a ``job_id`` in the last hour.  If the count
exceeds a configurable threshold, a warning is logged.

This is a callable function for now — cron integration comes in S16.
Anti-drift #29 (3-gate cron triggers) applies to the future cron version.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from utils.spans import DB_PATH

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = 10


def check_idle_burn(
    db_path: Path | None = None,
    threshold: int = _DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """Check for idle token burn in the last hour.

    Returns a dict with ``count`` (number of idle spans) and
    ``exceeds_threshold`` (bool).  Logs a warning when the threshold
    is exceeded.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS idle_count
            FROM spans
            WHERE job_id IS NULL
              AND timestamp >= datetime('now', '-1 hour')
            """
        ).fetchone()

        count: int = row["idle_count"] if row else 0
        exceeds = count > threshold

        if exceeds:
            logger.warning(
                "Idle token burn detected: %d spans without job_id in the last hour "
                "(threshold: %d)",
                count,
                threshold,
            )

        return {"count": count, "exceeds_threshold": exceeds}
    finally:
        conn.close()
