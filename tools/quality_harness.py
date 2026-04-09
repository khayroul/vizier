"""Offline quality measurement — runs benchmark briefs through scoring rubric.

Not a production tool. Used to measure and track quality floor by running
benchmark briefs through brief interpreter + template selector and scoring
the structured outputs against the adherence rubric.

Usage:
    python3 -m tools.quality_harness [--brief-id bench_festive_raya]
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from tools.brief_interpreter import interpret_brief
from tools.template_selector import select_template

logger = logging.getLogger(__name__)

_BENCHMARK_PATH = (
    Path(__file__).resolve().parent.parent
    / "evaluations"
    / "benchmark"
    / "poster_briefs.yaml"
)

_RUBRIC_PATH = (
    Path(__file__).resolve().parent.parent
    / "config"
    / "quality_frameworks"
    / "adherence_rubric.yaml"
)


def load_benchmark_briefs() -> list[dict[str, Any]]:
    """Load frozen benchmark briefs from YAML."""
    data = yaml.safe_load(_BENCHMARK_PATH.read_text())
    return list(data.get("briefs", []))


def load_adherence_rubric() -> dict[str, Any]:
    """Load adherence rubric dimensions and thresholds."""
    return yaml.safe_load(_RUBRIC_PATH.read_text())  # type: ignore[no-any-return]


def evaluate_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single benchmark brief through the intent + selector pipeline.

    Does NOT run the full governed pipeline (no image generation, no LLM cost
    beyond brief interpretation). Measures:
    - Intent extraction quality vs expected values
    - Template selection appropriateness
    - Slot coverage
    """
    raw_input = brief.get("raw_input", "")
    expected = brief.get("expected", {})

    # Step 1: Interpret brief
    interpretation = interpret_brief(raw_input)
    intent = interpretation.intent

    # Step 2: Select template
    expected_slots = set(expected.get("required_slots", []))
    match = select_template(intent, active_slots=expected_slots)

    # Step 3: Score intent extraction accuracy
    intent_scores: dict[str, float] = {}

    # Occasion match
    expected_occasion = expected.get("occasion", "")
    if expected_occasion:
        intent_scores["occasion_accuracy"] = (
            5.0 if intent.occasion == expected_occasion else
            3.0 if intent.occasion else 1.0
        )
    else:
        intent_scores["occasion_accuracy"] = 5.0 if not intent.occasion else 3.0

    # Mood match
    expected_mood = expected.get("mood", "")
    if expected_mood:
        intent_scores["mood_accuracy"] = (
            5.0 if intent.mood == expected_mood else
            3.0 if intent.mood else 1.0
        )
    else:
        intent_scores["mood_accuracy"] = 5.0 if not intent.mood else 3.0

    # Must-include extraction
    expected_must = set(expected.get("must_include", []))
    if expected_must:
        extracted_must = set(intent.must_include)
        # Fuzzy: count overlap (case-insensitive substring match)
        hits = sum(
            1 for exp in expected_must
            if any(exp.lower() in m.lower() for m in extracted_must)
        )
        intent_scores["must_include_recall"] = (
            5.0 * hits / len(expected_must) if expected_must else 5.0
        )
    else:
        intent_scores["must_include_recall"] = 5.0

    # Template appropriateness (non-default when intent has signal)
    has_signal = bool(expected_occasion or expected_mood)
    if has_signal:
        intent_scores["template_variety"] = (
            5.0 if match.template_name != "poster_default" else 2.0
        )
    else:
        intent_scores["template_variety"] = (
            5.0 if match.template_name == "poster_default" else 3.0
        )

    # Aggregate
    scores = list(intent_scores.values())
    aggregate = sum(scores) / len(scores) if scores else 3.0

    return {
        "brief_id": brief.get("id", "unknown"),
        "raw_input": raw_input[:100],
        "intent": intent.to_jsonb(),
        "template": match.template_name,
        "template_score": match.score,
        "template_reasons": list(match.reasons),
        "intent_scores": intent_scores,
        "aggregate_score": round(aggregate, 2),
        "interpretation_tokens": {
            "input": interpretation.input_tokens,
            "output": interpretation.output_tokens,
            "cost_usd": interpretation.cost_usd,
        },
    }


def run_harness(
    brief_id: str | None = None,
) -> dict[str, Any]:
    """Run quality harness across benchmark corpus.

    Args:
        brief_id: If provided, run only this brief. Otherwise run all.

    Returns:
        Summary with per-brief results and aggregate metrics.
    """
    briefs = load_benchmark_briefs()
    if brief_id:
        briefs = [b for b in briefs if b.get("id") == brief_id]
        if not briefs:
            return {"error": f"Brief '{brief_id}' not found in benchmark corpus"}

    results: list[dict[str, Any]] = []
    for brief in briefs:
        try:
            result = evaluate_brief(brief)
            results.append(result)
        except Exception as exc:
            logger.warning("Failed to evaluate %s: %s", brief.get("id"), exc)
            results.append({
                "brief_id": brief.get("id", "unknown"),
                "error": str(exc),
                "aggregate_score": 0.0,
            })

    # Aggregate metrics
    scores = [r["aggregate_score"] for r in results if "error" not in r]
    templates_used = {r.get("template", "?") for r in results if "error" not in r}

    summary: dict[str, Any] = {
        "total_briefs": len(results),
        "successful": len(scores),
        "failed": len(results) - len(scores),
        "median_score": sorted(scores)[len(scores) // 2] if scores else 0.0,
        "min_score": min(scores) if scores else 0.0,
        "max_score": max(scores) if scores else 0.0,
        "distinct_templates": len(templates_used),
        "templates_used": sorted(templates_used),
        "results": results,
    }

    rubric = load_adherence_rubric()
    pass_threshold = rubric.get("scoring", {}).get("thresholds", {}).get("pass", 3.5)
    summary["pass_threshold"] = pass_threshold
    summary["passing"] = sum(1 for s in scores if s >= pass_threshold)

    return summary


if __name__ == "__main__":
    import json as _json

    logging.basicConfig(level=logging.INFO)
    bid = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else None
    if "--brief-id" in sys.argv:
        idx = sys.argv.index("--brief-id")
        bid = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

    result = run_harness(brief_id=bid)
    print(_json.dumps(result, indent=2, default=str))
