"""D12 PosterIQ dataset loader.

Loads and parses JSON annotation files from the PosterIQ benchmark dataset
into typed dataclass records for quality intelligence calibration.

Dataset structure expected at ``datasets/D12_PosterIQ/und_task/``.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default dataset directory: ``<repo>/datasets/D12_PosterIQ``
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DATASET_DIR = _REPO_ROOT / "datasets" / "D12_PosterIQ"

# Mapping from source JSON filename (without .json) to canonical pair_type
_AB_PAIR_SOURCES: tuple[tuple[str, str], ...] = (
    ("layout_comprison", "layout_comparison"),  # note: typo in dataset filename
    ("font_matching", "font_matching"),
    ("font_effect", "font_effect"),
    ("font_effect_2", "font_effect_2"),
)


# ---------------------------------------------------------------------------
# Record types
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RatingRecord:
    """A single poster overall-quality rating from PosterIQ."""

    name: str
    path: str
    score: float
    prompt: str


@dataclass(frozen=True, slots=True)
class ABPairRecord:
    """An A/B comparison or classification pair from PosterIQ."""

    name: str
    path: str
    ground_truth: str
    pair_type: str
    prompt: str


@dataclass(frozen=True, slots=True)
class StyleRecord:
    """A poster style classification record from PosterIQ."""

    name: str
    path: str
    category: str
    prompt: str


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _read_json(file_path: Path) -> list[dict[str, object]]:
    """Read a JSON file and return its contents as a list of dicts.

    Raises:
        FileNotFoundError: If *file_path* does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        TypeError: If the top-level JSON value is not a list.
    """
    with file_path.open("r", encoding="utf-8") as fh:
        data: object = json.load(fh)
    if not isinstance(data, list):
        raise TypeError(
            f"Expected JSON array at top level of {file_path}, "
            f"got {type(data).__name__}"
        )
    return data  # type: ignore[return-value]


def _normalise_ground_truth(gt_value: object) -> str:
    """Convert a heterogeneous ``gt`` field to a stable string.

    * ``str`` values are returned unchanged.
    * ``list`` values (e.g. font_effect_2 multi-label) are joined with ``|``.
    * Everything else is coerced via ``str()``.
    """
    if isinstance(gt_value, str):
        return gt_value
    if isinstance(gt_value, list):
        return "|".join(str(item) for item in gt_value)
    return str(gt_value)


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------

def load_ratings(
    dataset_dir: Path = _DEFAULT_DATASET_DIR,
) -> list[RatingRecord]:
    """Load overall_rating.json into typed :class:`RatingRecord` instances.

    Args:
        dataset_dir: Root of the D12_PosterIQ dataset directory.

    Returns:
        List of :class:`RatingRecord`, one per poster.
    """
    file_path = dataset_dir / "und_task" / "overall_rating.json"
    raw_records = _read_json(file_path)

    results: list[RatingRecord] = []
    for idx, raw in enumerate(raw_records):
        try:
            results.append(
                RatingRecord(
                    name=str(raw["name"]),
                    path=str(raw["path"]),
                    score=float(raw["gt"]),  # type: ignore[arg-type]
                    prompt=str(raw["prompt"]),
                )
            )
        except (KeyError, ValueError) as exc:
            logger.warning("Skipping rating record %d: %s", idx, exc)

    logger.info("Loaded %d rating records from %s", len(results), file_path)
    return results


def load_ab_pairs(
    dataset_dir: Path = _DEFAULT_DATASET_DIR,
) -> list[ABPairRecord]:
    """Load all A/B pair JSON files into typed :class:`ABPairRecord` instances.

    Merges records from layout_comprison, font_matching, font_effect, and
    font_effect_2 JSON files.  Each record is tagged with a canonical
    ``pair_type`` for downstream filtering.

    Args:
        dataset_dir: Root of the D12_PosterIQ dataset directory.

    Returns:
        List of :class:`ABPairRecord` across all four source files.
    """
    results: list[ABPairRecord] = []

    for filename_stem, pair_type in _AB_PAIR_SOURCES:
        file_path = dataset_dir / "und_task" / f"{filename_stem}.json"
        raw_records = _read_json(file_path)

        for idx, raw in enumerate(raw_records):
            try:
                results.append(
                    ABPairRecord(
                        name=str(raw.get("name", "")),
                        path=str(raw["path"]),
                        ground_truth=_normalise_ground_truth(raw["gt"]),
                        pair_type=pair_type,
                        prompt=str(raw["prompt"]),
                    )
                )
            except (KeyError, ValueError) as exc:
                logger.warning(
                    "Skipping AB record %d in %s: %s", idx, filename_stem, exc
                )

        logger.info(
            "Loaded %d AB pair records from %s",
            len(raw_records),
            file_path,
        )

    logger.info("Total AB pair records: %d", len(results))
    return results


def load_styles(
    dataset_dir: Path = _DEFAULT_DATASET_DIR,
) -> list[StyleRecord]:
    """Load style_understanding.json into typed :class:`StyleRecord` instances.

    Args:
        dataset_dir: Root of the D12_PosterIQ dataset directory.

    Returns:
        List of :class:`StyleRecord`, one per poster.
    """
    file_path = dataset_dir / "und_task" / "style_understanding.json"
    raw_records = _read_json(file_path)

    results: list[StyleRecord] = []
    for idx, raw in enumerate(raw_records):
        try:
            results.append(
                StyleRecord(
                    name=str(raw["name"]),
                    path=str(raw["path"]),
                    category=str(raw["gt"]),
                    prompt=str(raw["prompt"]),
                )
            )
        except (KeyError, ValueError) as exc:
            logger.warning("Skipping style record %d: %s", idx, exc)

    logger.info("Loaded %d style records from %s", len(results), file_path)
    return results
