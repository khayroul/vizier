"""Self-improvement loop: pattern detection, failure analysis, rule management.

Built by S19. Analyses production traces to detect approval correlations,
cost outliers, and step value. Generates improvement proposals for operator
review. All text tasks use GPT-5.4-mini (anti-drift #54).

Anti-drift enforcement:
  - #56: anchor_set=true feedback excluded from all pattern detection
  - #13: silence_flagged / unresponsive feedback excluded from quality calcs
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from utils.call_llm import call_llm
from utils.database import get_cursor

logger = logging.getLogger(__name__)

_RULES_DIR = Path("config/improvement_rules")


# ---------------------------------------------------------------------------
# Pattern Detection
# ---------------------------------------------------------------------------


class PatternDetector:
    """Deterministic pattern detection from production traces (§15.2)."""

    # Base WHERE clause that enforces anti-drift #56 and #13
    _QUALITY_FILTER = """
        j.status = 'completed'
        AND (f.anchor_set IS NULL OR f.anchor_set = false)
        AND f.feedback_status NOT IN ('silence_flagged', 'unresponsive')
    """

    def detect_approval_correlations(
        self,
        artifact_type: str,
        min_jobs: int = 20,
    ) -> list[dict[str, Any]]:
        """Find features that correlate with first-pass approval.

        SQL aggregation — no LLM calls. Groups completed jobs by
        artifact_type, compares approved vs not-approved traces.
        Excludes anchor_set and silence/unresponsive feedback.
        """
        with get_cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    j.id,
                    j.job_type,
                    j.client_id,
                    j.production_trace,
                    om.first_pass_approved,
                    om.quality_summary
                FROM jobs j
                JOIN outcome_memory om ON om.job_id = j.id
                JOIN feedback f ON f.job_id = j.id
                WHERE j.job_type = %s
                  AND {self._QUALITY_FILTER}
                """,
                (artifact_type,),
            )
            rows = cur.fetchall()

        if len(rows) < min_jobs:
            return []

        approved = [r for r in rows if r["first_pass_approved"]]
        rejected = [r for r in rows if not r["first_pass_approved"]]

        if not approved or not rejected:
            return []

        correlations: list[dict[str, Any]] = []

        # Extract trace keys present in approved vs rejected
        approved_keys = _extract_trace_keys(approved)
        rejected_keys = _extract_trace_keys(rejected)

        all_keys = approved_keys.keys() | rejected_keys.keys()
        for key in all_keys:
            rate_with = approved_keys.get(key, 0) / max(len(approved), 1)
            rate_without = rejected_keys.get(key, 0) / max(len(rejected), 1)
            delta = rate_with - rate_without
            if abs(delta) > 0.15:
                correlations.append({
                    "pattern": key,
                    "approval_rate_with": round(rate_with, 3),
                    "approval_rate_without": round(rate_without, 3),
                    "sample_size": len(rows),
                    "confidence": _confidence_level(len(rows)),
                })

        return correlations

    def detect_cost_outliers(
        self,
        artifact_type: str,
        threshold_multiplier: float = 2.0,
    ) -> list[dict[str, Any]]:
        """Find jobs costing 2x+ median for their artifact type."""
        with get_cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    j.id AS job_id,
                    j.production_trace,
                    om.cost_summary
                FROM jobs j
                JOIN outcome_memory om ON om.job_id = j.id
                JOIN feedback f ON f.job_id = j.id
                WHERE j.job_type = %s
                  AND {self._QUALITY_FILTER}
                  AND om.cost_summary IS NOT NULL
                """,
                (artifact_type,),
            )
            rows = cur.fetchall()

        if not rows:
            return []

        costs = []
        for row in rows:
            summary = row["cost_summary"]
            if isinstance(summary, str):
                summary = json.loads(summary)
            total = summary.get("total_cost_usd", 0) if summary else 0
            costs.append((row, total))

        costs.sort(key=lambda x: x[1])
        median_cost = costs[len(costs) // 2][1] if costs else 0

        if median_cost <= 0:
            return []

        outliers: list[dict[str, Any]] = []
        for row, cost in costs:
            multiplier = cost / median_cost
            if multiplier >= threshold_multiplier:
                trace = row["production_trace"] or {}
                if isinstance(trace, str):
                    trace = json.loads(trace)
                outliers.append({
                    "job_id": str(row["job_id"]),
                    "cost": round(cost, 4),
                    "median_cost": round(median_cost, 4),
                    "multiplier": round(multiplier, 2),
                    "distinguishing_features": _extract_distinguishing(trace),
                })

        return outliers

    def detect_step_value(
        self,
        artifact_type: str,
    ) -> list[dict[str, Any]]:
        """Compare quality between jobs that included vs skipped a step."""
        with get_cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    j.production_trace,
                    om.quality_summary,
                    om.first_pass_approved
                FROM jobs j
                JOIN outcome_memory om ON om.job_id = j.id
                JOIN feedback f ON f.job_id = j.id
                WHERE j.job_type = %s
                  AND {self._QUALITY_FILTER}
                  AND j.production_trace IS NOT NULL
                """,
                (artifact_type,),
            )
            rows = cur.fetchall()

        if not rows:
            return []

        # Collect all step names across traces
        step_presence: dict[str, list[tuple[bool, float]]] = {}
        for row in rows:
            trace = row["production_trace"]
            if isinstance(trace, str):
                trace = json.loads(trace)
            steps = set(trace.get("steps_executed", []))
            quality = row["quality_summary"] or {}
            if isinstance(quality, str):
                quality = json.loads(quality)
            overall = quality.get("overall_score", 0.0)

            for step in steps:
                step_presence.setdefault(step, []).append((True, overall))

            # Also record absence for steps we've seen in other jobs
            all_steps = set()
            for r2 in rows:
                t2 = r2["production_trace"]
                if isinstance(t2, str):
                    t2 = json.loads(t2)
                all_steps.update(t2.get("steps_executed", []))

            for step in all_steps - steps:
                step_presence.setdefault(step, []).append((False, overall))

        results: list[dict[str, Any]] = []
        for step, entries in step_presence.items():
            with_step = [score for present, score in entries if present]
            without_step = [score for present, score in entries if not present]
            if len(with_step) >= 3 and len(without_step) >= 3:
                avg_with = sum(with_step) / len(with_step)
                avg_without = sum(without_step) / len(without_step)
                results.append({
                    "step_name": step,
                    "quality_with": round(avg_with, 3),
                    "quality_without": round(avg_without, 3),
                    "delta": round(avg_with - avg_without, 3),
                    "sample_size": len(entries),
                })

        results.sort(key=lambda x: abs(x["delta"]), reverse=True)
        return results


# ---------------------------------------------------------------------------
# Improvement Proposals
# ---------------------------------------------------------------------------


def generate_improvement_proposal(pattern: dict[str, Any]) -> dict[str, Any]:
    """Format a detected pattern as an ImprovementProposal."""
    sample_size = pattern.get("sample_size", 0)
    return {
        "id": str(uuid.uuid4()),
        "observation": f"Pattern '{pattern.get('pattern', 'unknown')}' detected",
        "proposed_change": f"Adjust based on pattern: {pattern.get('pattern', '')}",
        "expected_impact": _format_approval_delta(
            pattern.get("approval_rate_with", 0),
            pattern.get("approval_rate_without", 0),
        ),
        "confidence": _confidence_level(sample_size),
        "sample_size": sample_size,
        "experiment_config": {
            "pattern": pattern.get("pattern"),
            "type": "prompt_refinement",
        },
    }


# ---------------------------------------------------------------------------
# Failure Analysis
# ---------------------------------------------------------------------------


class FailureAnalysis:
    """Diagnose failures and propose instruction changes (§15.7)."""

    def analyse_failures(
        self,
        artifact_type: str | None = None,
        min_rating: float = 3.0,
    ) -> list[dict[str, Any]]:
        """Query low-rated traces, cluster, and diagnose via GPT-5.4-mini."""
        with get_cursor() as cur:
            query = """
                SELECT
                    j.id AS job_id,
                    j.job_type AS artifact_type,
                    j.client_id,
                    j.production_trace,
                    f.operator_rating,
                    om.quality_summary,
                    om.human_feedback_summary
                FROM jobs j
                JOIN feedback f ON f.job_id = j.id
                JOIN outcome_memory om ON om.job_id = j.id
                WHERE f.operator_rating < %s
                  AND f.operator_rating IS NOT NULL
                  AND (f.anchor_set IS NULL OR f.anchor_set = false)
                  AND f.feedback_status NOT IN ('silence_flagged', 'unresponsive')
            """
            params: list[Any] = [min_rating]
            if artifact_type:
                query += " AND j.job_type = %s"
                params.append(artifact_type)

            cur.execute(query, params)
            rows = cur.fetchall()

        if not rows:
            return []

        clusters = self._cluster_failures(rows)
        results: list[dict[str, Any]] = []

        for idx, cluster in enumerate(clusters):
            common = _extract_common_features(cluster)
            diagnosis = self._diagnose_cluster(cluster, common)
            results.append({
                "cluster_id": idx,
                "common_features": common,
                "sample_size": len(cluster),
                "diagnosis": diagnosis.get("diagnosis", ""),
                "proposed_rule": diagnosis.get("proposed_rule", ""),
            })

            # Write proposed rule to YAML
            if diagnosis.get("proposed_rule"):
                self._save_rule(idx, common, diagnosis)

        return results

    def _cluster_failures(
        self, failures: Sequence[dict[str, Any]]
    ) -> list[list[dict[str, Any]]]:
        """Group by (artifact_type, client_id), then find common low dimensions."""
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in failures:
            key = (
                str(row.get("artifact_type", "unknown")),
                str(row.get("client_id", "unknown")),
            )
            groups.setdefault(key, []).append(row)

        return [group for group in groups.values() if len(group) >= 2]

    def _diagnose_cluster(
        self,
        cluster: list[dict[str, Any]],
        common_features: dict[str, Any],
    ) -> dict[str, str]:
        """Call GPT-5.4-mini to diagnose a failure cluster."""
        summaries = []
        for row in cluster[:5]:  # Limit context
            quality = row.get("quality_summary") or {}
            if isinstance(quality, str):
                quality = json.loads(quality)
            summaries.append({
                "rating": row.get("operator_rating"),
                "feedback": row.get("human_feedback_summary", ""),
                "quality": quality,
            })

        prompt = (
            "Analyse these failed production jobs and propose an instruction rule.\n\n"
            f"Common features: {json.dumps(common_features)}\n"
            f"Failure summaries: {json.dumps(summaries)}\n\n"
            "Respond with JSON: {\"diagnosis\": \"...\", \"proposed_rule\": \"...\"}"
        )

        sys_msg = (
            "You are a production quality analyst."
        )
        result = call_llm(
            stable_prefix=[{"role": "system", "content": sys_msg}],
            variable_suffix=[{"role": "user", "content": prompt}],
            model="gpt-5.4-mini",
            temperature=0.3,
            max_tokens=512,
        )

        try:
            return json.loads(result["content"])
        except (json.JSONDecodeError, KeyError):
            return {"diagnosis": result.get("content", ""), "proposed_rule": ""}

    def _save_rule(
        self,
        cluster_id: int,
        common: dict[str, Any],
        diagnosis: dict[str, str],
    ) -> None:
        """Write proposed rule to config/improvement_rules/ as YAML."""
        _RULES_DIR.mkdir(parents=True, exist_ok=True)
        artifact_type = common.get("artifact_type", "general")
        filename = f"rule_{artifact_type}_{cluster_id}.yaml"
        rule_data = {
            "id": f"auto_{artifact_type}_{cluster_id}",
            "artifact_type": artifact_type,
            "diagnosis": diagnosis.get("diagnosis", ""),
            "rule": diagnosis.get("proposed_rule", ""),
            "source": "failure_analysis",
            "sample_size": common.get("sample_size", 0),
        }
        path = _RULES_DIR / filename
        rule_text = yaml.dump(rule_data, default_flow_style=False)
        path.write_text(rule_text, encoding="utf-8")
        logger.info("Saved improvement rule: %s", path)


# ---------------------------------------------------------------------------
# Rule Manager
# ---------------------------------------------------------------------------


class RuleManager:
    """Load and inject improvement rules from config/improvement_rules/."""

    def load_rules(self, artifact_type: str | None = None) -> list[dict[str, Any]]:
        """Read YAML files from rules directory, optionally filter by type."""
        if not _RULES_DIR.exists():
            return []

        rules: list[dict[str, Any]] = []
        for path in _RULES_DIR.glob("*.yaml"):
            content = yaml.safe_load(path.read_text(encoding="utf-8"))
            if content is None:
                continue
            # Handle both single-rule and operators-list format
            if "operators" in content:
                for op in content["operators"]:
                    applies = op.get("applies_to", [])
                    if (
                        artifact_type is None
                        or artifact_type in applies
                    ):
                        rules.append(op)
            else:
                matches = (
                    artifact_type is None
                    or content.get("artifact_type")
                    == artifact_type
                )
                if matches:
                    rules.append(content)

        return rules

    def inject_rules_into_template(
        self, template: str, rules: list[dict[str, Any]]
    ) -> str:
        """Append relevant rules to a prompt template as instructions."""
        if not rules:
            return template

        lines = ["\n\nIMPROVEMENT RULES:"]
        for rule in rules:
            text = rule.get("rule") or rule.get("description", "")
            if text:
                lines.append(f"- {text}")

        return template + "\n".join(lines)


# ---------------------------------------------------------------------------
# Message Formatters (§15.3, §15.4, §15.10)
# ---------------------------------------------------------------------------


def format_proposal_message(proposal: dict[str, Any]) -> str:
    """Format an improvement proposal for Telegram notification."""
    obs = proposal.get("observation", "unknown")
    change = proposal.get("proposed_change", "")
    impact = proposal.get("expected_impact", "")
    conf = proposal.get("confidence", "low")
    size = proposal.get("sample_size", 0)
    return (
        f"\U0001f4a1 IMPROVEMENT PROPOSAL: {obs}\n"
        f"\n"
        f"Observation: {obs}\n"
        f"Proposed change: {change}\n"
        f"Expected: {impact}\n"
        f"Confidence: {conf} ({size} jobs)\n"
        f"\n"
        "/test \u2014 run experiment  "
        "|  /promote \u2014 apply now  "
        "|  /reject \u2014 discard"
    )


def format_experiment_result(result: dict[str, Any]) -> str:
    """Format experiment completion for Telegram notification."""
    name = result.get("name", "unknown")
    ctrl_appr = result.get("control_approved", 0)
    ctrl_total = result.get("control_total", 0)
    ctrl_cost = result.get("control_avg_cost", 0)
    exp_appr = result.get("experiment_approved", 0)
    exp_total = result.get("experiment_total", 0)
    exp_cost = result.get("experiment_avg_cost", 0)
    return (
        f"\u2705 EXPERIMENT COMPLETE: {name}\n"
        f"Control: {ctrl_appr}/{ctrl_total} approved, "
        f"{ctrl_cost} avg tokens\n"
        f"Experiment: {exp_appr}/{exp_total} approved, "
        f"{exp_cost} avg tokens\n"
        "/promote \u2014 lock it in  "
        "|  /extend \u2014 5 more jobs  "
        "|  /reject \u2014 revert"
    )


def format_drift_alert(drift_data: dict[str, Any]) -> str:
    """Format drift detection alert for Telegram notification."""
    orig = drift_data.get("original_avg", 0)
    curr = drift_data.get("current_avg", 0)
    drift = drift_data.get("drift", 0)
    return (
        "\u26a0\ufe0f DRIFT ALERT: Quality baseline "
        "may be shifting.\n"
        f"Anchor set original avg: {orig}/5\n"
        f"Anchor set current scorer avg: {curr}/5 "
        f"(+{drift:.1f} drift)\n"
        "/review-anchors \u2014 open anchor review"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_trace_keys(rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    """Count occurrences of each trace feature across rows.

    Flattens trace dicts into key=value features so that differences
    in values (not just key presence) are captured. For list values,
    records presence of each element. For scalar values, records the
    key=value pair.
    """
    counts: dict[str, int] = {}
    for row in rows:
        trace = row.get("production_trace") or {}
        if isinstance(trace, str):
            trace = json.loads(trace)
        for key, val in trace.items():
            if isinstance(val, list):
                if val:
                    feature = f"{key}:present"
                else:
                    feature = f"{key}:empty"
                counts[feature] = counts.get(feature, 0) + 1
                for item in val:
                    item_feature = f"{key}:{item}"
                    counts[item_feature] = counts.get(item_feature, 0) + 1
            elif isinstance(val, (int, float)):
                feature = f"{key}={val}"
                counts[feature] = counts.get(feature, 0) + 1
            else:
                feature = f"{key}={val}"
                counts[feature] = counts.get(feature, 0) + 1
    return counts


def _extract_distinguishing(trace: dict[str, Any]) -> list[str]:
    """Pull out notable features from a production trace."""
    features = []
    if trace.get("steps_executed"):
        features.append(f"steps: {len(trace['steps_executed'])}")
    if trace.get("knowledge_cards_used"):
        features.append(f"knowledge_cards: {len(trace['knowledge_cards_used'])}")
    if trace.get("refinement_cycles"):
        features.append(f"refinement_cycles: {trace['refinement_cycles']}")
    return features


def _extract_common_features(cluster: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract common features from a failure cluster."""
    if not cluster:
        return {}
    features: dict[str, Any] = {
        "artifact_type": cluster[0].get("artifact_type"),
        "client_id": str(cluster[0].get("client_id", "")),
        "sample_size": len(cluster),
    }
    # Find common low-scoring dimensions
    low_dims: dict[str, int] = {}
    for row in cluster:
        quality = row.get("quality_summary") or {}
        if isinstance(quality, str):
            quality = json.loads(quality)
        for dim, score in quality.items():
            if isinstance(score, (int, float)) and score < 3.0:
                low_dims[dim] = low_dims.get(dim, 0) + 1
    features["common_low_dimensions"] = {
        dim: count for dim, count in low_dims.items() if count >= 2
    }
    return features


def _format_approval_delta(
    rate_with: float,
    rate_without: float,
) -> str:
    """Format approval rate delta as a string."""
    delta = rate_with - rate_without
    return f"Approval rate delta: {delta:.1%}"


def _confidence_level(sample_size: int) -> str:
    """Map sample size to confidence level."""
    if sample_size >= 30:
        return "high"
    if sample_size >= 15:
        return "medium"
    return "low"
