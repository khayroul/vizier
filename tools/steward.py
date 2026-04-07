"""Steward — GTD personal assistant tools.

ADHD-friendly: zero-friction capture, one-task-at-a-time /next,
streak tracking, domain balance. Separate Telegram bot, same engine.

Model: GPT-5.4-mini for all LLM work (anti-drift #54).
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4

from config.steward_domains import DOMAINS, HEATMAP_AMBER, HEATMAP_GREEN
from utils.call_llm import call_llm
from utils.database import get_cursor
from utils.prayer_times import get_prayer_times, is_after_prayer
from utils.spans import track_span

logger = logging.getLogger(__name__)


def capture_inbox(
    raw_input: str,
    input_type: str = "text",
    source_message_id: str | None = None,
) -> dict[str, Any]:
    """Zero-friction inbox capture. No LLM call — immediate storage."""
    inbox_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO steward_inbox (id, raw_input, input_type, source_message_id)
            VALUES (%s, %s, %s, %s)
            """,
            (inbox_id, raw_input, input_type, source_message_id),
        )
    return {"captured": True, "inbox_id": inbox_id}


@track_span(step_type="steward")
def process_inbox(limit: int = 5) -> list[dict[str, Any]]:
    """Process unprocessed inbox items via GPT-5.4-mini.

    Returns suggestions for tap-confirm UI.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, raw_input, input_type, created_at "
            "FROM steward_inbox "
            "WHERE processed = false "
            "ORDER BY created_at ASC LIMIT %s",
            (limit,),
        )
        items = [dict(row) for row in cur.fetchall()]

    if not items:
        return []

    suggestions = []
    for item in items:
        prompt = (
            "Extract a task from this inbox capture. Return JSON with:\n"
            "- title: concise task title (under 60 chars)\n"
            f"- domain: one of {json.dumps(DOMAINS)}\n"
            "- context: one of "
            '["home", "office", "errands", "phone", "computer", "anywhere"]\n'
            '- energy_level: one of ["high", "medium", "low"]\n'
            "- time_estimate_min: estimated minutes (integer)\n\n"
            f'Inbox text: "{item["raw_input"]}"\n\n'
            "Return ONLY valid JSON, no markdown."
        )

        response = call_llm(
            stable_prefix=[
                {
                    "role": "system",
                    "content": (
                        "You are Steward, a GTD task processor. "
                        "Extract actionable tasks from raw inbox captures. "
                        "Be concise and practical."
                    ),
                }
            ],
            variable_suffix=[{"role": "user", "content": prompt}],
            model="gpt-5.4-mini",
            temperature=0.3,
            max_tokens=256,
        )

        try:
            parsed = json.loads(response["content"])
        except (json.JSONDecodeError, KeyError):
            parsed = {
                "title": item["raw_input"][:60],
                "domain": "Career",
                "context": "anywhere",
                "energy_level": "medium",
                "time_estimate_min": 15,
            }

        if parsed.get("domain") not in DOMAINS:
            parsed["domain"] = "Career"

        suggestions.append(
            {
                "inbox_id": str(item["id"]),
                "raw_input": item["raw_input"],
                "suggestion": parsed,
            }
        )

    return suggestions


def confirm_processed(
    inbox_id: str,
    title: str,
    domain: str,
    context: str,
    energy: str,
    time_estimate: int,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Create a steward_task from a confirmed inbox item."""
    if domain not in DOMAINS:
        raise ValueError(f"Invalid domain: {domain}. Valid: {DOMAINS}")

    task_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "UPDATE steward_inbox SET processed = true, processed_at = now() "
            "WHERE id = %s",
            (inbox_id,),
        )
        cur.execute(
            """
            INSERT INTO steward_tasks
              (id, inbox_id, project_id, title, next_action, context,
               energy_level, time_estimate_min, domain, status)
            VALUES (%s, %s, %s, %s, true, %s, %s, %s, %s, 'active')
            RETURNING id, title, domain, context, energy_level, time_estimate_min
            """,
            (
                task_id,
                inbox_id,
                project_id,
                title,
                context,
                energy,
                time_estimate,
                domain,
            ),
        )
        row = cur.fetchone()
        assert row is not None
        return dict(row)


@track_span(step_type="steward")
def get_next(
    energy: str | None = None,
    domain: str | None = None,
) -> dict[str, Any] | None:
    """Recommend ONE task. Multiplicative scoring, energy/context as hard filters.

    After Asr, only low-energy tasks are eligible.
    """
    today = date.today()
    now = datetime.now()

    # Auto-determine energy from prayer time if not specified
    if energy is None:
        if is_after_prayer("asr"):
            energy = "low"
        elif is_after_prayer("zohor"):
            energy = "medium"

    # Build energy filter (hard gate)
    if energy == "low":
        energy_filter = ["low"]
    elif energy == "medium":
        energy_filter = ["low", "medium"]
    else:
        energy_filter = ["low", "medium", "high"]

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, title, domain, context, energy_level,
                   time_estimate_min, due_date, project_id, description
            FROM steward_tasks
            WHERE status = 'active'
              AND next_action = true
              AND (defer_until IS NULL OR defer_until <= %s)
              AND energy_level = ANY(%s)
            ORDER BY created_at ASC
            """,
            (today, energy_filter),
        )
        candidates = [dict(row) for row in cur.fetchall()]

    if not candidates:
        return None

    if domain:
        filtered = [c for c in candidates if c["domain"] == domain]
        if filtered:
            candidates = filtered

    # Compute domain neglect scores
    domain_last_done = _domain_last_activity()

    # Score each candidate (multiplicative)
    scored: list[tuple[float, dict[str, Any]]] = []
    for task in candidates:
        if task["due_date"]:
            days_left = (task["due_date"] - today).days
            deadline_score = max(0.1, 1.0 / max(1, days_left))
        else:
            deadline_score = 0.1

        task_domain = task["domain"] or "Career"
        last_active = domain_last_done.get(task_domain)
        if last_active is None:
            neglect_score = 2.0
        else:
            days_neglected = (today - last_active).days
            neglect_score = 1.0 + (days_neglected / 7.0)

        total_score = deadline_score * neglect_score
        scored.append((total_score, task))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_task = scored[0]

    # Build explanation
    reasons = _build_explanation(best_task, domain_last_done, today, now)

    return {
        **best_task,
        "explanation": ". ".join(reasons) if reasons else "Next available task",
        "score": best_score,
    }


def _domain_last_activity() -> dict[str, date]:
    """Return the last completion date for each domain."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT domain, MAX(completed_at::date) AS last_done "
            "FROM steward_tasks "
            "WHERE status = 'done' AND domain IS NOT NULL "
            "GROUP BY domain"
        )
        return {
            row["domain"]: row["last_done"]
            for row in cur.fetchall()
            if row["last_done"] is not None
        }


def _build_explanation(
    task: dict[str, Any],
    domain_last_done: dict[str, date],
    today: date,
    now: datetime,
) -> list[str]:
    """Build human-readable explanation for why this task was chosen."""
    reasons: list[str] = []

    if task["due_date"]:
        days_left = (task["due_date"] - today).days
        if days_left <= 0:
            reasons.append("Due today")
        elif days_left == 1:
            reasons.append("Due tomorrow")
        elif days_left <= 3:
            reasons.append(f"Due in {days_left} days")

    task_domain = task["domain"] or "Career"
    last_active = domain_last_done.get(task_domain)
    if last_active is None or (today - last_active).days >= 7:
        gap = (today - last_active).days if last_active else 0
        days_str = "never" if last_active is None else f"{gap} days"
        reasons.append(f"Domain: {task_domain} (neglected {days_str})")

    if task["time_estimate_min"]:
        reasons.append(f"~{task['time_estimate_min']} min")

    # Prayer time context
    prayer_times = get_prayer_times(today)
    for prayer_name in ["asr", "maghrib"]:
        prayer_t = prayer_times[prayer_name]
        minutes_until = (datetime.combine(today, prayer_t) - now).total_seconds() / 60
        if 0 < minutes_until < 60:
            reasons.append(f"{int(minutes_until)} min until {prayer_name.capitalize()}")
            break

    return reasons


def mark_done(
    task_id: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Mark a task as done. Update streak, return progress."""
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE steward_tasks
               SET status = 'done', completed_at = now(), completion_note = %s,
                   updated_at = now()
             WHERE id = %s
            RETURNING id, title, domain, streak_count, streak_last_date
            """,
            (note, task_id),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Task not found: {task_id}")

        task_title = row["title"]
        task_domain = row["domain"] or "Career"
        old_streak = row["streak_count"] or 0
        last_date = row["streak_last_date"]

        # Update streak
        today = date.today()
        yesterday = today - timedelta(days=1)
        if last_date in (yesterday, today):
            new_streak = old_streak + 1
        else:
            new_streak = 1

        cur.execute(
            "UPDATE steward_tasks SET streak_count = %s, streak_last_date = %s "
            "WHERE id = %s",
            (new_streak, today, task_id),
        )

        # Update project progress if linked
        cur.execute("SELECT project_id FROM steward_tasks WHERE id = %s", (task_id,))
        proj_row = cur.fetchone()
        if proj_row and proj_row["project_id"]:
            cur.execute(
                "UPDATE steward_projects "
                "SET completed_tasks = completed_tasks + 1, updated_at = now() "
                "WHERE id = %s",
                (proj_row["project_id"],),
            )

        # Today's completions for streak display
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM steward_tasks "
            "WHERE status = 'done' AND completed_at::date = CURRENT_DATE"
        )
        count_row = cur.fetchone()
        assert count_row is not None
        today_done = count_row["cnt"]

        # Domain progress (last 7 days)
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM steward_tasks "
            "WHERE status = 'done' AND domain = %s "
            "AND completed_at >= now() - interval '7 days'",
            (task_domain,),
        )
        count_row = cur.fetchone()
        assert count_row is not None
        domain_count = count_row["cnt"]

    return {
        "task_id": task_id,
        "title": task_title,
        "streak_count": today_done,
        "domain": task_domain,
        "domain_progress": f"{domain_count} tasks this week",
        "win_summary": f"{task_title} — done!",
    }


def get_snapshot() -> dict[str, Any]:
    """Return snapshot: active tasks, overdue, today's completions, domain heatmap."""
    today = date.today()
    week_ago = today - timedelta(days=7)

    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM steward_tasks WHERE status = 'active'")
        row = cur.fetchone()
        assert row is not None
        active = row["cnt"]

        cur.execute(
            "SELECT COUNT(*) AS cnt FROM steward_tasks "
            "WHERE status = 'active' AND due_date < %s",
            (today,),
        )
        row = cur.fetchone()
        assert row is not None
        overdue = row["cnt"]

        cur.execute(
            "SELECT COUNT(*) AS cnt FROM steward_tasks "
            "WHERE status = 'done' AND completed_at::date = CURRENT_DATE"
        )
        row = cur.fetchone()
        assert row is not None
        today_done = row["cnt"]

        cur.execute(
            "SELECT domain, COUNT(*) AS cnt FROM steward_tasks "
            "WHERE status = 'done' AND domain IS NOT NULL "
            "AND completed_at >= %s GROUP BY domain",
            (week_ago,),
        )
        domain_counts = {row["domain"]: row["cnt"] for row in cur.fetchall()}

    heatmap: dict[str, str] = {}
    for d in DOMAINS:
        count = domain_counts.get(d, 0)
        if count >= HEATMAP_GREEN:
            heatmap[d] = "green"
        elif count >= HEATMAP_AMBER:
            heatmap[d] = "amber"
        else:
            heatmap[d] = "red"

    return {
        "active_tasks": active,
        "overdue_tasks": overdue,
        "today_done": today_done,
        "domain_heatmap": heatmap,
        "current_streak": today_done,
    }


@track_span(step_type="steward")
def decompose_project(
    objective: str,
    domain: str | None = None,
) -> dict[str, Any]:
    """Decompose a project objective into tasks via GPT-5.4-mini."""
    if domain and domain not in DOMAINS:
        raise ValueError(f"Invalid domain: {domain}. Valid: {DOMAINS}")

    prompt = (
        "Break down this project objective into actionable tasks.\n"
        "Return JSON with:\n"
        '- "tasks": array of objects, each with:\n'
        '  - "title": concise task title\n'
        '  - "context": one of '
        '["home", "office", "errands", "phone", "computer", "anywhere"]\n'
        '  - "energy_level": one of ["high", "medium", "low"]\n'
        '  - "time_estimate_min": estimated minutes\n\n'
        f'Objective: "{objective}"\n'
        f"Domain: {domain or 'Career'}\n\n"
        "Return 4-8 tasks, ordered by logical sequence. Return ONLY valid JSON."
    )

    response = call_llm(
        stable_prefix=[
            {
                "role": "system",
                "content": (
                    "You are Steward, a GTD project planner. "
                    "Break objectives into specific, actionable tasks "
                    "with realistic estimates."
                ),
            }
        ],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.5,
        max_tokens=1024,
    )

    try:
        parsed = json.loads(response["content"])
        tasks = parsed.get("tasks", parsed) if isinstance(parsed, dict) else parsed
    except (json.JSONDecodeError, KeyError):
        tasks = [
            {
                "title": objective,
                "context": "anywhere",
                "energy_level": "medium",
                "time_estimate_min": 30,
            }
        ]

    project_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO steward_projects (id, title, objective, domain, status)
            VALUES (%s, %s, %s, %s, 'active')
            RETURNING id, title, objective, domain
            """,
            (project_id, objective[:100], objective, domain or "Career"),
        )
        row = cur.fetchone()
        assert row is not None
        project = dict(row)

    return {**project, "proposed_tasks": tasks}


def confirm_decomposition(
    project_id: str,
    tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create tasks linked to a project after operator confirmation."""
    created: list[dict[str, Any]] = []
    with get_cursor() as cur:
        cur.execute(
            "SELECT domain FROM steward_projects WHERE id = %s",
            (project_id,),
        )
        proj = cur.fetchone()
        proj_domain = proj["domain"] if proj else "Career"

        for task_data in tasks:
            task_id = str(uuid4())
            cur.execute(
                """
                INSERT INTO steward_tasks
                  (id, project_id, title, next_action, context,
                   energy_level, time_estimate_min, domain, status)
                VALUES (%s, %s, %s, true, %s, %s, %s, %s, 'active')
                RETURNING id, title, domain, context, energy_level, time_estimate_min
                """,
                (
                    task_id,
                    project_id,
                    task_data["title"],
                    task_data.get("context", "anywhere"),
                    task_data.get("energy_level", "medium"),
                    task_data.get("time_estimate_min", 15),
                    proj_domain,
                ),
            )
            task_row = cur.fetchone()
            assert task_row is not None
            created.append(dict(task_row))

        cur.execute(
            "UPDATE steward_projects "
            "SET total_tasks = %s, decomposed = true, "
            "    decomposition_approved = true, updated_at = now() "
            "WHERE id = %s",
            (len(tasks), project_id),
        )

    return created


def steward_brief_data() -> dict[str, Any]:
    """Aggregate Steward data for the morning brief.

    Returns: today's top 3 tasks, domain balance snapshot, streak.
    """
    snapshot = get_snapshot()

    top_tasks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for _ in range(3):
        task = get_next()
        if task is None or task["id"] in seen_ids:
            break
        top_tasks.append(
            {
                "title": task["title"],
                "domain": task["domain"],
                "time_estimate_min": task.get("time_estimate_min"),
                "explanation": task.get("explanation", ""),
            }
        )
        seen_ids.add(task["id"])

    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM steward_inbox WHERE processed = false")
        row = cur.fetchone()
        assert row is not None
        unprocessed = row["cnt"]

    return {
        "top_3_tasks": top_tasks,
        "unprocessed_inbox": unprocessed,
        "domain_heatmap": snapshot["domain_heatmap"],
        "active_tasks": snapshot["active_tasks"],
        "current_streak": snapshot["current_streak"],
    }
