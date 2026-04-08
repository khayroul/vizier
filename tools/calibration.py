"""Drift detection, exemplar optimisation, and prompt variation testing.

Built by S19. Implements §15.10 drift detection (anchor set re-scoring,
velocity decay, external benchmark ingestion) and §15.7 optimisation
techniques (exemplar set optimisation, prompt variation testing).

70% cut line: detection FUNCTIONS are built, but the monthly cron is NOT.
Needs 10-15 anchor set examples from Month 1 production.

All text tasks use GPT-5.4-mini (anti-drift #54).
Anti-drift #56: anchor_set records never enter improvement loop.
"""

from __future__ import annotations

import json
import logging
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from utils.call_llm import call_llm
from utils.database import get_cursor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Drift Detection (§15.10)
# ---------------------------------------------------------------------------


def score_anchor_set() -> dict[str, Any]:
    """Re-score anchor set examples using current scorer + rubric.

    Compares current scores against original operator_rating.
    Alert threshold: drift > 0.5.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT f.id, f.job_id, f.operator_rating, f.raw_text AS feedback_text,
                   j.job_type AS artifact_type, j.production_trace
            FROM feedback f
            JOIN jobs j ON j.id = f.job_id
            WHERE f.anchor_set = true
              AND f.operator_rating IS NOT NULL
            """
        )
        anchors = cur.fetchall()

    if not anchors:
        return {
            "anchor_count": 0,
            "original_avg": 0.0,
            "current_avg": 0.0,
            "drift": 0.0,
            "drifted_items": [],
        }

    original_scores: list[float] = []
    current_scores: list[float] = []
    drifted: list[dict[str, Any]] = []

    for anchor in anchors:
        original = anchor["operator_rating"]
        original_scores.append(float(original))

        # Re-score via GPT-5.4-mini
        current = _rescore_anchor(anchor)
        current_scores.append(current)

        if abs(current - original) > 0.5:
            drifted.append({
                "feedback_id": str(anchor["id"]),
                "job_id": str(anchor["job_id"]),
                "original_rating": original,
                "current_score": current,
                "delta": round(current - original, 2),
            })

    original_avg = sum(original_scores) / len(original_scores)
    current_avg = sum(current_scores) / len(current_scores)

    return {
        "anchor_count": len(anchors),
        "original_avg": round(original_avg, 2),
        "current_avg": round(current_avg, 2),
        "drift": round(abs(current_avg - original_avg), 2),
        "drifted_items": drifted,
    }


def _rescore_anchor(anchor: dict[str, Any]) -> float:
    """Score a single anchor example using GPT-5.4-mini."""
    trace = anchor.get("production_trace") or {}
    if isinstance(trace, str):
        trace = json.loads(trace)

    prompt = (
        f"Rate this {anchor.get('artifact_type', 'unknown')} production output "
        f"on a scale of 1-5.\n\n"
        f"Feedback text: {anchor.get('feedback_text', 'N/A')}\n"
        f"Production trace summary: {json.dumps(trace)[:500]}\n\n"
        f"Respond with ONLY a number 1-5."
    )

    result = call_llm(
        stable_prefix=[{
            "role": "system",
            "content": "You are a production quality scorer.",
        }],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.1,
        max_tokens=10,
    )

    try:
        score = float(result["content"].strip())
        return max(1.0, min(5.0, score))
    except (ValueError, KeyError):
        return 3.0  # Default middle score on parse failure


def check_velocity_decay(window_jobs: int = 100) -> dict[str, Any]:
    """Check if improvement proposals have stalled.

    Counts proposals generated in the last N completed jobs.
    Alerts if 0 proposals in 100+ jobs.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS total_jobs
            FROM jobs WHERE status = 'completed'
            """
        )
        total_row = cur.fetchone()
        total_jobs = total_row["total_jobs"] if total_row else 0

        # Count experiments (proxies for proposals) in the last window
        cur.execute(
            """
            SELECT COUNT(*) AS proposal_count
            FROM experiments
            WHERE created_at >= (
                SELECT created_at FROM jobs
                WHERE status = 'completed'
                ORDER BY created_at DESC
                OFFSET %s LIMIT 1
            )
            """,
            (window_jobs,),
        )
        proposal_row = cur.fetchone()
        proposals = proposal_row["proposal_count"] if proposal_row else 0

    # Expected rate: ~3-5 proposals per 50 jobs Month 1-3
    expected_rate = 0.06  # 3 per 50
    actual_rate = proposals / max(window_jobs, 1)
    alert = proposals == 0 and total_jobs >= window_jobs

    return {
        "total_jobs": total_jobs,
        "proposals_in_window": proposals,
        "expected_rate": expected_rate,
        "actual_rate": round(actual_rate, 4),
        "alert": alert,
    }


def ingest_external_benchmark(image_data: bytes, metadata: dict[str, Any]) -> str:
    """Create a feedback record tagged as external benchmark.

    These records are EXCLUDED from improvement loop pattern detection.
    They exist only as a reality check (§15.10).
    """
    with get_cursor() as cur:
        # Create a minimal job to attach feedback to
        cur.execute(
            """
            INSERT INTO feedback (
                job_id, feedback_status, benchmark_source, raw_text
            ) VALUES (
                %s, 'awaiting', 'external', %s
            )
            RETURNING id
            """,
            (
                metadata.get("job_id"),
                metadata.get("description", "External benchmark example"),
            ),
        )
        row = cur.fetchone()
        assert row is not None
        feedback_id = str(row["id"])

    logger.info("Ingested external benchmark: %s", feedback_id)
    return feedback_id


# ---------------------------------------------------------------------------
# Exemplar Set Optimisation (§15.7)
# ---------------------------------------------------------------------------


class ExemplarOptimiser:
    """Find the optimal combination of k exemplars for maximum quality."""

    def optimise_exemplar_set(
        self,
        artifact_type: str,
        client_id: str,
        k: int = 3,
        n_trials: int = 10,
    ) -> dict[str, Any]:
        """Try n_trials random k-combinations, score each, keep best.

        Requires 20+ exemplars for the artifact_type.
        """
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT id, artifact_id, style_tags
                FROM exemplars
                WHERE artifact_type = %s AND client_id = %s AND status = 'active'
                """,
                (artifact_type, client_id),
            )
            exemplars = cur.fetchall()

        if len(exemplars) < max(k, 20):
            return {
                "error": f"Need 20+ exemplars, found {len(exemplars)}",
                "best_set": [],
                "score": 0.0,
                "trial_scores": [],
                "improvement_over_default": 0.0,
            }

        # Load held-out test cases
        test_cases = _load_test_cases(artifact_type)

        trial_scores: list[dict[str, Any]] = []
        best_score = -1.0
        best_set: list[str] = []

        for _ in range(n_trials):
            combo = random.sample(exemplars, k)
            combo_ids = [str(e["id"]) for e in combo]
            score = self._score_combination(combo, test_cases)
            trial_scores.append({"exemplar_ids": combo_ids, "score": score})
            if score > best_score:
                best_score = score
                best_set = combo_ids

        # Score default (first k exemplars) for comparison
        default_score = self._score_combination(exemplars[:k], test_cases)
        improvement = best_score - default_score

        return {
            "best_set": best_set,
            "score": round(best_score, 3),
            "trial_scores": trial_scores,
            "improvement_over_default": round(improvement, 3),
        }

    def _score_combination(
        self,
        exemplars: Sequence[dict[str, Any]],
        test_cases: list[dict[str, Any]],
    ) -> float:
        """Score a combination of exemplars against test cases via GPT-5.4-mini."""
        tags = []
        for ex in exemplars:
            ex_tags = ex.get("style_tags") or []
            if isinstance(ex_tags, str):
                ex_tags = [ex_tags]
            tags.extend(ex_tags)

        prompt = (
            "Rate the diversity and coverage of this exemplar set (1-5).\n\n"
            f"Exemplar style tags: {json.dumps(tags)}\n"
            f"Test case count: {len(test_cases)}\n\n"
            "Respond with ONLY a number 1-5."
        )

        result = call_llm(
            stable_prefix=[{
                "role": "system",
                "content": "You are a design quality evaluator.",
            }],
            variable_suffix=[{"role": "user", "content": prompt}],
            model="gpt-5.4-mini",
            temperature=0.2,
            max_tokens=10,
        )

        try:
            return float(result["content"].strip())
        except (ValueError, KeyError):
            return 3.0


# ---------------------------------------------------------------------------
# Prompt Variation Testing (§15.7)
# ---------------------------------------------------------------------------


class PromptVariationTester:
    """Generate and test prompt variants against held-out examples."""

    def test_prompt_variations(
        self,
        template_path: str,
        artifact_type: str,
        n_variants: int = 3,
    ) -> dict[str, Any]:
        """Generate n_variants via GPT-5.4-mini and score each.

        Requires 20+ rated examples for the artifact_type.
        """
        path = Path(template_path)
        if not path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        current_template = path.read_text(encoding="utf-8")
        test_cases = _load_test_cases(artifact_type)

        if len(test_cases) < 1:
            return {
                "error": "No test cases found",
                "current_score": 0.0,
                "variants": [],
            }

        # Score current template
        current_score = self._score_template(current_template, test_cases)

        # Generate variants
        variants: list[dict[str, Any]] = []
        for i in range(n_variants):
            variant_content = self._generate_variant(current_template, i)
            variant_score = self._score_template(variant_content, test_cases)
            variants.append({
                "content": variant_content,
                "score": variant_score,
            })

        variants.sort(key=lambda v: v["score"], reverse=True)
        best = variants[0] if variants else {"content": "", "score": 0.0}

        return {
            "current_score": current_score,
            "variants": variants,
            "best_variant": best["content"],
            "improvement": round(best["score"] - current_score, 3),
        }

    def _generate_variant(self, template: str, index: int) -> str:
        """Generate a single prompt variant via GPT-5.4-mini."""
        result = call_llm(
            stable_prefix=[{
                "role": "system",
                "content": "You are a prompt engineer. Rewrite the given template "
                           "preserving its intent but varying structure and phrasing.",
            }],
            variable_suffix=[{
                "role": "user",
                "content": (
                    f"Rewrite this template "
                    f"(variant {index + 1}):\n\n"
                    f"{template[:2000]}"
                ),
            }],
            model="gpt-5.4-mini",
            temperature=0.8,
            max_tokens=2048,
        )
        return result["content"]

    def _score_template(
        self, template: str, test_cases: list[dict[str, Any]]
    ) -> float:
        """Score a template against test cases via GPT-5.4-mini."""
        cases_summary = json.dumps(test_cases[:5])[:1000]
        prompt = (
            "Rate this prompt template's quality for the given test cases (1-5).\n\n"
            f"Template:\n{template[:1500]}\n\n"
            f"Test cases:\n{cases_summary}\n\n"
            "Respond with ONLY a number 1-5."
        )

        result = call_llm(
            stable_prefix=[{
                "role": "system",
                "content": "You are a prompt quality evaluator.",
            }],
            variable_suffix=[{"role": "user", "content": prompt}],
            model="gpt-5.4-mini",
            temperature=0.2,
            max_tokens=10,
        )

        try:
            return float(result["content"].strip())
        except (ValueError, KeyError):
            return 3.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_test_cases(artifact_type: str) -> list[dict[str, Any]]:
    """Load evaluation test cases from config/evaluations/ for this artifact type."""
    eval_dir = Path("config/evaluations")
    if not eval_dir.exists():
        return []

    test_cases: list[dict[str, Any]] = []
    for path in eval_dir.glob(f"{artifact_type}*.yaml"):
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        if content and "test_cases" in content:
            test_cases.extend(content["test_cases"])

    return test_cases
