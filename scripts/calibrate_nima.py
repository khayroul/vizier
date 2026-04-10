"""Calibrate NIMA aesthetic thresholds from D12 PosterIQ + operator exemplars.

Run-once calibration that:
1. Scores every D12 rated poster with NIMA
2. Correlates NIMA predictions against D12 ground-truth ratings
3. Derives regenerate_below / pass_above thresholds
4. Optionally adjusts pass_above using operator exemplar taste target
5. Writes calibrated YAML + markdown report

Usage:
    python3 scripts/calibrate_nima.py
    python3 scripts/calibrate_nima.py --d12-dir datasets/D12_PosterIQ \
        --exemplars-dir datasets/operator_exemplars
"""
from __future__ import annotations

import logging
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.load_posteriq import RatingRecord, load_ratings
from tools.visual_scoring import nima_score

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_THRESHOLDS_PATH = _REPO_ROOT / "config" / "quality_frameworks" / "nima_thresholds.yaml"
_REPORT_DIR = _REPO_ROOT / "docs" / "reports"
_REPORT_PATH = _REPORT_DIR / "nima_calibration.md"
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})

# Minimum correlation to justify overriding defaults
_MIN_CORRELATION = 0.3

# D12 "poor" poster threshold — posters below this are considered low quality
_POOR_SCORE_CEILING = 4.0

# Percentile of poor-poster NIMA scores used for regenerate_below
_POOR_PERCENTILE = 0.80

# Default thresholds when correlation is too low
_DEFAULT_REGENERATE_BELOW = 4.0
_DEFAULT_PASS_ABOVE = 7.0


# ---------------------------------------------------------------------------
# Correlation helpers (stdlib-only, no scipy dependency)
# ---------------------------------------------------------------------------

def _pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation coefficient between two equal-length sequences.

    Returns 0.0 if standard deviation of either sequence is zero.
    """
    n = len(xs)
    if n < 2:
        return 0.0

    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)
    std_x = statistics.pstdev(xs)
    std_y = statistics.pstdev(ys)

    if std_x == 0.0 or std_y == 0.0:
        return 0.0

    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / n
    return covariance / (std_x * std_y)


def _rank(values: list[float]) -> list[float]:
    """Assign fractional ranks to values (average method for ties)."""
    indexed = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * len(values)

    idx = 0
    while idx < len(indexed):
        # Find all items with the same value (tie group)
        tie_start = idx
        while idx < len(indexed) and indexed[idx][1] == indexed[tie_start][1]:
            idx += 1
        # Average rank for the tie group (1-based)
        avg_rank = (tie_start + 1 + idx) / 2.0
        for tie_idx in range(tie_start, idx):
            ranks[indexed[tie_idx][0]] = avg_rank

    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    """Spearman rank correlation between two equal-length sequences."""
    if len(xs) < 2:
        return 0.0
    return _pearson(_rank(xs), _rank(ys))


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _score_d12_images(
    records: list[RatingRecord],
    d12_dir: Path,
) -> list[tuple[float, float]]:
    """Score each D12 image with NIMA and pair with ground-truth.

    Returns:
        List of (nima_score, d12_score) tuples for successfully scored images.
    """
    pairs: list[tuple[float, float]] = []
    skipped = 0

    for record in records:
        image_path = d12_dir / "data" / record.path
        if not image_path.exists():
            logger.warning("Image not found: %s", image_path)
            skipped += 1
            continue

        try:
            image_bytes = image_path.read_bytes()
            nima = nima_score(image_bytes)
            pairs.append((nima, record.score))
            logger.debug(
                "Scored %s: nima=%.2f d12=%.1f",
                record.name, nima, record.score,
            )
        except (OSError, RuntimeError) as exc:
            logger.warning("Failed to score %s: %s", record.name, exc)
            skipped += 1

    logger.info(
        "Scored %d images, skipped %d",
        len(pairs), skipped,
    )
    return pairs


def _score_exemplars(exemplars_dir: Path) -> list[float]:
    """Score operator exemplar images with NIMA.

    Scans all subdirectories for image files.

    Returns:
        List of NIMA scores for successfully scored exemplars.
    """
    scores: list[float] = []

    image_files = [
        p for p in exemplars_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
    ]

    if not image_files:
        logger.info("No operator exemplar images found in %s", exemplars_dir)
        return scores

    for image_path in sorted(image_files):
        try:
            image_bytes = image_path.read_bytes()
            score = nima_score(image_bytes)
            scores.append(score)
            logger.debug("Exemplar %s: nima=%.2f", image_path.name, score)
        except (OSError, RuntimeError) as exc:
            logger.warning("Failed to score exemplar %s: %s", image_path.name, exc)

    logger.info("Scored %d operator exemplars", len(scores))
    return scores


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Compute the pct-th percentile of a sorted list (linear interpolation)."""
    if not sorted_values:
        raise ValueError("Cannot compute percentile of empty list")

    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]

    # 0-based index for the percentile
    k = pct * (n - 1)
    lower = int(k)
    upper = min(lower + 1, n - 1)
    fraction = k - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


# ---------------------------------------------------------------------------
# Main calibration
# ---------------------------------------------------------------------------

def calibrate_nima_thresholds(
    d12_dir: Path,
    exemplars_dir: Path | None,
) -> dict[str, Any]:
    """Run full NIMA calibration and return results dict.

    Args:
        d12_dir: Root of D12_PosterIQ dataset.
        exemplars_dir: Optional directory of operator exemplar images.

    Returns:
        Dict with keys: regenerate_below, pass_above, pearson, spearman,
        d12_count, exemplar_count, calibration_date, used_defaults.
    """
    # 1. Load D12 ratings
    records = load_ratings(dataset_dir=d12_dir)
    if not records:
        logger.error("No D12 rating records loaded from %s", d12_dir)
        return {
            "regenerate_below": _DEFAULT_REGENERATE_BELOW,
            "pass_above": _DEFAULT_PASS_ABOVE,
            "pearson": 0.0,
            "spearman": 0.0,
            "d12_count": 0,
            "exemplar_count": 0,
            "calibration_date": datetime.now(tz=timezone.utc).isoformat(),
            "used_defaults": True,
            "reason": "No D12 records loaded",
        }

    # 2. Score every D12 poster with NIMA
    pairs = _score_d12_images(records, d12_dir)
    if len(pairs) < 10:
        logger.error("Too few scored images (%d) for meaningful calibration", len(pairs))
        return {
            "regenerate_below": _DEFAULT_REGENERATE_BELOW,
            "pass_above": _DEFAULT_PASS_ABOVE,
            "pearson": 0.0,
            "spearman": 0.0,
            "d12_count": len(pairs),
            "exemplar_count": 0,
            "calibration_date": datetime.now(tz=timezone.utc).isoformat(),
            "used_defaults": True,
            "reason": f"Too few scored images ({len(pairs)})",
        }

    nima_scores = [p[0] for p in pairs]
    d12_scores = [p[1] for p in pairs]

    # 3. Correlation
    pearson_r = _pearson(nima_scores, d12_scores)
    spearman_r = _spearman(nima_scores, d12_scores)

    logger.info("Pearson r=%.4f, Spearman rho=%.4f", pearson_r, spearman_r)

    # 4. Score operator exemplars if directory exists and has images
    exemplar_scores: list[float] = []
    if exemplars_dir is not None and exemplars_dir.is_dir():
        exemplar_scores = _score_exemplars(exemplars_dir)

    # 5. Check if correlation is sufficient
    if abs(pearson_r) < _MIN_CORRELATION and abs(spearman_r) < _MIN_CORRELATION:
        logger.warning(
            "Correlation too low (pearson=%.4f, spearman=%.4f) — keeping defaults. "
            "D12 ratings may be LLM-generated or crowd-sourced.",
            pearson_r, spearman_r,
        )
        return {
            "regenerate_below": _DEFAULT_REGENERATE_BELOW,
            "pass_above": _DEFAULT_PASS_ABOVE,
            "pearson": pearson_r,
            "spearman": spearman_r,
            "d12_count": len(pairs),
            "exemplar_count": len(exemplar_scores),
            "calibration_date": datetime.now(tz=timezone.utc).isoformat(),
            "used_defaults": True,
            "reason": (
                f"Correlation below {_MIN_CORRELATION} threshold "
                f"(pearson={pearson_r:.4f}, spearman={spearman_r:.4f})"
            ),
        }

    # 6. Compute regenerate_below: NIMA score below which 80% of D12 "poor" posters fall
    poor_nima = sorted(
        nima for nima, d12 in pairs if d12 < _POOR_SCORE_CEILING
    )
    if poor_nima:
        regenerate_below = round(
            _percentile(poor_nima, _POOR_PERCENTILE), 2,
        )
    else:
        # No poor posters in dataset — use D12 bottom quartile NIMA
        all_nima_sorted = sorted(nima_scores)
        regenerate_below = round(_percentile(all_nima_sorted, 0.25), 2)

    # 7. Compute pass_above
    if exemplar_scores:
        # Operator taste target: median NIMA of approved exemplars
        pass_above = round(statistics.median(exemplar_scores), 2)
    else:
        # D12 top quartile (75th percentile)
        all_nima_sorted = sorted(nima_scores)
        pass_above = round(_percentile(all_nima_sorted, 0.75), 2)

    # Guard: pass_above must be strictly above regenerate_below
    if pass_above <= regenerate_below:
        pass_above = round(regenerate_below + 1.0, 2)

    return {
        "regenerate_below": regenerate_below,
        "pass_above": pass_above,
        "pearson": pearson_r,
        "spearman": spearman_r,
        "d12_count": len(pairs),
        "exemplar_count": len(exemplar_scores),
        "calibration_date": datetime.now(tz=timezone.utc).isoformat(),
        "used_defaults": False,
        "reason": "Calibrated from D12 + exemplar data",
        "nima_mean": round(statistics.mean(nima_scores), 4),
        "nima_stdev": round(statistics.pstdev(nima_scores), 4),
        "d12_mean": round(statistics.mean(d12_scores), 4),
        "d12_stdev": round(statistics.pstdev(d12_scores), 4),
        "poor_poster_count": len(poor_nima) if poor_nima else 0,
    }


def _write_thresholds_yaml(results: dict[str, Any]) -> None:
    """Update nima_thresholds.yaml with calibrated values."""
    calibration_source = (
        "D12 PosterIQ (n={d12_count}) + operator exemplars (n={exemplar_count})"
        if int(results.get("exemplar_count", 0) or 0) > 0
        else "D12 PosterIQ (n={d12_count}) — no operator exemplars available"
    ).format(**results)

    if results.get("used_defaults"):
        calibration_source += f" [DEFAULTS KEPT: {results.get('reason', 'unknown')}]"

    yaml_content = (
        "# NIMA aesthetic score thresholds (1.0-10.0 scale)\n"
        "# SEPARATE from posteriq_quality_dimensions.yaml (1-5 critique scale)\n"
        "# Calibrated against D12 PosterIQ reference scores\n"
        "# Provenance: statistical analysis of correlation, not copyrightable\n"
        "nima:\n"
        f"  regenerate_below: {results['regenerate_below']}\n"
        f"  pass_above: {results['pass_above']}\n"
        f"  calibration_source: \"{calibration_source}\"\n"
        f"  calibration_date: \"{results['calibration_date']}\"\n"
        f"  agreement_rate: null\n"
    )
    _THRESHOLDS_PATH.write_text(yaml_content, encoding="utf-8")
    logger.info("Wrote thresholds to %s", _THRESHOLDS_PATH)


def _write_report(results: dict[str, Any]) -> None:
    """Write calibration report as markdown."""
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)

    used_defaults = results.get("used_defaults", False)
    status = "DEFAULTS KEPT" if used_defaults else "CALIBRATED"

    lines = [
        "# NIMA Calibration Report",
        "",
        f"**Status:** {status}",
        f"**Date:** {results['calibration_date']}",
        "",
        "## Sample Sizes",
        "",
        f"- D12 PosterIQ images scored: {results['d12_count']}",
        f"- Operator exemplars scored: {results['exemplar_count']}",
        "",
        "## Correlation",
        "",
        f"- Pearson r: {results['pearson']:.4f}",
        f"- Spearman rho: {results['spearman']:.4f}",
        f"- Minimum threshold: {_MIN_CORRELATION}",
        "",
    ]

    if used_defaults:
        lines.extend([
            f"**Reason for keeping defaults:** {results.get('reason', 'unknown')}",
            "",
            "Correlation between NIMA aesthetic scores and D12 ground-truth ratings",
            f"was below the {_MIN_CORRELATION} threshold. This may indicate that D12",
            "ratings are LLM-generated or crowd-sourced with low inter-annotator",
            "agreement. Default thresholds (4.0 / 7.0) are preserved.",
            "",
        ])

    lines.extend([
        "## Threshold Values",
        "",
        f"- `regenerate_below`: {results['regenerate_below']}",
        f"- `pass_above`: {results['pass_above']}",
        "",
    ])

    if not used_defaults:
        lines.extend([
            "## Distribution Statistics",
            "",
            f"- NIMA mean: {results.get('nima_mean', 'N/A')}",
            f"- NIMA stdev: {results.get('nima_stdev', 'N/A')}",
            f"- D12 mean: {results.get('d12_mean', 'N/A')}",
            f"- D12 stdev: {results.get('d12_stdev', 'N/A')}",
            f"- D12 poor posters (gt < {_POOR_SCORE_CEILING}): "
            f"{results.get('poor_poster_count', 'N/A')}",
            "",
        ])

    threshold_source = (
        "operator exemplar median" if int(results.get("exemplar_count", 0) or 0) > 0
        else "D12 top quartile (75th percentile)"
    )
    lines.extend([
        "## Methodology",
        "",
        f"- `regenerate_below`: 80th percentile of NIMA scores for D12 posters "
        f"rated below {_POOR_SCORE_CEILING}",
        f"- `pass_above`: {threshold_source}",
        "- Correlation computed using stdlib statistics (no scipy dependency)",
        "",
    ])

    _REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote calibration report to %s", _REPORT_PATH)


def main() -> None:
    """Entry point for NIMA calibration script."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Calibrate NIMA thresholds from D12 PosterIQ + operator exemplars",
    )
    parser.add_argument(
        "--d12-dir",
        type=Path,
        default=_REPO_ROOT / "datasets" / "D12_PosterIQ",
        help="Root of D12_PosterIQ dataset directory",
    )
    parser.add_argument(
        "--exemplars-dir",
        type=Path,
        default=_REPO_ROOT / "datasets" / "operator_exemplars",
        help="Directory of operator exemplar images",
    )
    args = parser.parse_args()

    d12_dir: Path = args.d12_dir
    exemplars_dir: Path | None = args.exemplars_dir

    if not d12_dir.is_dir():
        logger.error("D12 directory not found: %s", d12_dir)
        sys.exit(1)

    if exemplars_dir is not None and not exemplars_dir.is_dir():
        logger.warning("Exemplars directory not found: %s — proceeding without", exemplars_dir)
        exemplars_dir = None

    results = calibrate_nima_thresholds(d12_dir, exemplars_dir)

    _write_thresholds_yaml(results)
    _write_report(results)

    if results.get("used_defaults"):
        logger.warning("Calibration kept defaults: %s", results.get("reason"))
    else:
        logger.info(
            "Calibration complete: regenerate_below=%.2f, pass_above=%.2f",
            float(results["regenerate_below"]),
            float(results["pass_above"]),
        )


if __name__ == "__main__":
    main()
