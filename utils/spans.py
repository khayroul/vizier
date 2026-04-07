"""Local spans table and @track_span decorator for Vizier observability.

LibSQL (SQLite-compatible) spans capture every LLM call's model, tokens,
cost, and duration.  This is the first tracing layer — Langfuse (S8) is
additive.  Anti-drift #20.
"""

from __future__ import annotations

import functools
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# Default database path — overridden in tests via monkeypatch
DB_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "spans.db"

F = TypeVar("F")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Return a connection to the spans database."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Create spans and memory_routing_log tables if they don't exist."""
    conn = _get_connection(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spans (
                step_id     TEXT PRIMARY KEY,
                model       TEXT NOT NULL,
                input_tokens  INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost_usd    REAL NOT NULL,
                duration_ms REAL NOT NULL,
                job_id      TEXT,
                step_type   TEXT,
                timestamp   TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_routing_log (
                id          TEXT PRIMARY KEY,
                operation   TEXT NOT NULL,
                model_used  TEXT NOT NULL,
                tokens      INTEGER NOT NULL,
                timestamp   TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def record_span(
    *,
    step_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    duration_ms: float,
    job_id: str | None = None,
    step_type: str | None = None,
) -> None:
    """Insert a single span row."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO spans
                (step_id, model, input_tokens, output_tokens,
                 cost_usd, duration_ms, job_id, step_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                step_id,
                model,
                input_tokens,
                output_tokens,
                cost_usd,
                duration_ms,
                job_id,
                step_type,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def record_memory_routing(
    *,
    operation: str,
    model_used: str,
    tokens: int,
) -> None:
    """Insert a memory routing log entry."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO memory_routing_log (id, operation, model_used, tokens)
            VALUES (?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), operation, model_used, tokens),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def track_span(
    func: Any = None,
    *,
    model: str = "gpt-5.4-mini",
    step_type: str | None = None,
) -> Any:
    """Record a span for every decorated call.

    Works as both ``@track_span`` and ``@track_span(model="gpt-5.4-mini")``.

    If the wrapped function returns a dict with standard response keys
    (``model``, ``input_tokens``, ``output_tokens``, ``cost_usd``), those
    values are written to the span.  Otherwise the decorator falls back to
    the ``model`` parameter and zeros.
    """

    def _decorator(fn: Any) -> Any:
        @functools.wraps(fn)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            step_id = str(uuid.uuid4())
            start = time.perf_counter()

            result = fn(*args, **kwargs)

            duration_ms = (time.perf_counter() - start) * 1000

            # Extract metrics from a standard response dict
            actual_model = model
            input_tokens = 0
            output_tokens = 0
            cost_usd = 0.0
            job_id: str | None = kwargs.get("job_id")  # type: ignore[assignment]

            if isinstance(result, dict):
                actual_model = result.get("model", model)
                input_tokens = result.get("input_tokens", 0)
                output_tokens = result.get("output_tokens", 0)
                cost_usd = result.get("cost_usd", 0.0)

            record_span(
                step_id=step_id,
                model=actual_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                duration_ms=duration_ms,
                job_id=str(job_id) if job_id is not None else None,
                step_type=step_type,
            )

            return result

        return _wrapper

    # Allow bare @track_span (no parentheses)
    if func is not None:
        return _decorator(func)
    return _decorator
