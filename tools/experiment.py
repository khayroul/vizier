"""Experiment framework for self-improvement loop.

Built by S19. Manages A/B experiments: create, tag jobs, record results,
evaluate winners. The operator approves experiments via /test and promotes
winners via /promote.

All text tasks use GPT-5.4-mini (anti-drift #54).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from utils.database import get_cursor

logger = logging.getLogger(__name__)


def create_experiment(proposal: dict[str, Any]) -> str:
    """Insert a new experiment from an improvement proposal. Returns experiment_id."""
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO experiments (
                name, hypothesis, experiment_type,
                control_config, experiment_config,
                target_artifact_type, target_client_id,
                sample_size, proposed_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                proposal.get("name", proposal.get("observation", "unnamed")),
                proposal.get("hypothesis", proposal.get("observation", "")),
                proposal.get("experiment_type", "prompt_variation"),
                json.dumps(proposal.get("control_config", {})),
                json.dumps(proposal.get("experiment_config", {})),
                proposal.get("target_artifact_type"),
                proposal.get("target_client_id"),
                proposal.get("sample_size", 10),
                proposal.get("proposed_by", "pattern_detector"),
            ),
        )
        row = cur.fetchone()
        assert row is not None
        experiment_id = str(row["id"])

    logger.info("Created experiment %s", experiment_id)
    return experiment_id


def tag_job(job_id: str, experiment_id: str, arm: str) -> None:
    """Assign a job to an experiment arm (control or experiment)."""
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO experiment_results (job_id, experiment_id, arm)
            VALUES (%s, %s, %s)
            """,
            (job_id, experiment_id, arm),
        )

        # Increment arm counter
        count_col = "control_count" if arm == "control" else "experiment_count"
        cur.execute(
            f"""
            UPDATE experiments SET {count_col} = {count_col} + 1
            WHERE id = %s
            """,
            (experiment_id,),
        )

        # Mark as running if still pending
        cur.execute(
            """
            UPDATE experiments SET status = 'running'
            WHERE id = %s AND status = 'pending'
            """,
            (experiment_id,),
        )


def should_assign_experiment(
    job_id: str,
    artifact_type: str,
    client_id: str | None = None,
) -> dict[str, Any] | None:
    """Check for a running experiment matching this job.

    Returns {experiment_id, arm} if the job should be assigned,
    or None if no matching experiment needs more samples.
    Uses round-robin: assigns to whichever arm has fewer jobs.
    """
    with get_cursor() as cur:
        query = """
            SELECT id, control_count, experiment_count, sample_size
            FROM experiments
            WHERE status IN ('pending', 'running')
              AND target_artifact_type = %s
        """
        params: list[Any] = [artifact_type]

        if client_id:
            query += " AND (target_client_id = %s OR target_client_id IS NULL)"
            params.append(client_id)
        else:
            query += " AND target_client_id IS NULL"

        query += " ORDER BY created_at ASC LIMIT 1"
        cur.execute(query, params)
        row = cur.fetchone()

    if not row:
        return None

    control = row["control_count"] or 0
    experiment = row["experiment_count"] or 0
    sample_size = row["sample_size"] or 10

    # Both arms full — no assignment
    if control >= sample_size and experiment >= sample_size:
        return None

    # Round-robin: assign to arm with fewer jobs
    arm = "control" if control <= experiment else "experiment"

    return {
        "experiment_id": str(row["id"]),
        "arm": arm,
    }


def record_result(
    experiment_id: str,
    job_id: str,
    rating: int | None,
    approved: bool,
    tokens: int,
    cost: float,
) -> None:
    """Record outcome for a job in an experiment. Triggers evaluation if complete."""
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE experiment_results
            SET operator_rating = %s,
                first_pass_approved = %s,
                token_count = %s,
                cost_usd = %s
            WHERE experiment_id = %s AND job_id = %s
            """,
            (rating, approved, tokens, cost, experiment_id, job_id),
        )

        # Check if both arms reached sample_size
        cur.execute(
            """
            SELECT sample_size, control_count, experiment_count
            FROM experiments
            WHERE id = %s
            """,
            (experiment_id,),
        )
        exp = cur.fetchone()

    if exp:
        sample = exp["sample_size"] or 10
        ctrl_done = (exp["control_count"] or 0) >= sample
        exp_done = (exp["experiment_count"] or 0) >= sample
        if ctrl_done and exp_done:
            evaluate_experiment(experiment_id)


def evaluate_experiment(experiment_id: str) -> dict[str, Any]:
    """Compare control vs experiment arms and determine winner.

    Experiment wins if approval_rate >= control AND cost <= control * 1.1.
    Updates experiment record with results.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT arm, first_pass_approved, token_count, cost_usd, operator_rating
            FROM experiment_results
            WHERE experiment_id = %s
              AND first_pass_approved IS NOT NULL
            """,
            (experiment_id,),
        )
        rows = cur.fetchall()

    control = [r for r in rows if r["arm"] == "control"]
    experiment = [r for r in rows if r["arm"] == "experiment"]

    control_approved = sum(1 for r in control if r["first_pass_approved"])
    experiment_approved = sum(1 for r in experiment if r["first_pass_approved"])

    control_rate = control_approved / max(len(control), 1)
    experiment_rate = experiment_approved / max(len(experiment), 1)

    control_cost = (
        sum(r["cost_usd"] or 0 for r in control) / max(len(control), 1)
    )
    experiment_cost = (
        sum(r["cost_usd"] or 0 for r in experiment) / max(len(experiment), 1)
    )

    # Winner logic: experiment must match/beat approval AND not cost >10% more
    if experiment_rate >= control_rate and experiment_cost <= control_cost * 1.1:
        winner = "experiment"
    elif control_rate > experiment_rate:
        winner = "control"
    else:
        winner = "inconclusive"

    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE experiments
            SET status = 'complete',
                control_approval_rate = %s,
                experiment_approval_rate = %s,
                control_avg_cost = %s,
                experiment_avg_cost = %s,
                winner = %s,
                completed_at = now()
            WHERE id = %s
            """,
            (
                control_rate,
                experiment_rate,
                control_cost,
                experiment_cost,
                winner,
                experiment_id,
            ),
        )

        # Fetch experiment name for summary
        cur.execute("SELECT name FROM experiments WHERE id = %s", (experiment_id,))
        name_row = cur.fetchone()

    summary = {
        "experiment_id": experiment_id,
        "name": name_row["name"] if name_row else "unknown",
        "control_approved": control_approved,
        "control_total": len(control),
        "experiment_approved": experiment_approved,
        "experiment_total": len(experiment),
        "control_avg_cost": round(control_cost, 4),
        "experiment_avg_cost": round(experiment_cost, 4),
        "winner": winner,
    }

    logger.info("Experiment %s complete: winner=%s", experiment_id, winner)
    return summary
