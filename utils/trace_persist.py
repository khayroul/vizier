"""TraceCollector Postgres persistence — wires ProductionTrace to jobs table.

Imports TraceCollector and ProductionTrace from contracts.trace (S6).
Persists the finalised trace as JSONB in the jobs.production_trace column.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from contracts.trace import ProductionTrace, TraceCollector

from utils.database import get_cursor

logger = logging.getLogger(__name__)


def persist_trace(job_id: str | UUID, trace: ProductionTrace) -> None:
    """Write a finalised ProductionTrace to the jobs table.

    Args:
        job_id: The UUID of the job (string or UUID).
        trace: The finalised ProductionTrace from TraceCollector.finalise().
    """
    trace_json = json.dumps(trace.to_jsonb(), default=str)
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
               SET production_trace = %s::jsonb,
                   updated_at = now()
             WHERE id = %s
            """,
            (trace_json, str(job_id)),
        )
        if cur.rowcount == 0:
            logger.warning("persist_trace: no job found with id=%s", job_id)
        else:
            logger.info("Persisted trace for job %s (%d steps)", job_id, len(trace.steps))


def load_trace(job_id: str | UUID) -> ProductionTrace | None:
    """Load a ProductionTrace from the jobs table.

    Returns None if the job has no trace stored.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT production_trace FROM jobs WHERE id = %s",
            (str(job_id),),
        )
        row = cur.fetchone()
        if row is None or row["production_trace"] is None:
            return None
        return ProductionTrace.model_validate(row["production_trace"])


def collect_and_persist(job_id: str | UUID, collector: TraceCollector) -> ProductionTrace:
    """Finalise a TraceCollector and persist to Postgres in one call.

    Returns the finalised ProductionTrace.
    """
    trace = collector.finalise()
    persist_trace(job_id, trace)
    return trace
