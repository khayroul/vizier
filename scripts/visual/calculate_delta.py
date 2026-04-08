"""Visual delta — SSIM + pixel diff structural comparison.

Deterministic, zero-token, pure function. Used by Layer 3 (visual QA)
in middleware/quality_gate.py to compare rendered output against a
reference layout.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity

# Minimum per-channel L1 distance to count a pixel as "different"
_PIXEL_TOLERANCE = 10

# SSIM requires a minimum window size; images smaller than this skip SSIM
_MIN_SSIM_DIM = 7

# Composite weights
_SSIM_WEIGHT = 0.7
_PIXEL_WEIGHT = 0.3


@dataclass(frozen=True)
class VisualDelta:
    """Result of a visual delta comparison."""

    composite_score: float  # 0.0–1.0
    ssim_score: float  # 0.0–1.0
    pixel_diff_pct: float  # 0.0–100.0


def _load_as_rgb(path: Path) -> np.ndarray:
    """Load an image file and convert to RGB uint8 numpy array."""
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    return np.array(Image.open(path).convert("RGB"), dtype=np.uint8)


def _compute_pixel_diff(target: np.ndarray, rendered: np.ndarray) -> float:
    """Compute percentage of pixels differing beyond tolerance.

    Args:
        target: RGB uint8 array (H, W, 3).
        rendered: RGB uint8 array, same shape as target.

    Returns:
        Percentage of pixels that differ (0.0–100.0).
    """
    diff = np.abs(target.astype(np.int16) - rendered.astype(np.int16))
    # A pixel "differs" if any channel exceeds tolerance
    exceeds = np.any(diff > _PIXEL_TOLERANCE, axis=2)
    total_pixels = target.shape[0] * target.shape[1]
    if total_pixels == 0:
        return 0.0
    return float(exceeds.sum() / total_pixels * 100.0)


def _compute_ssim(target: np.ndarray, rendered: np.ndarray) -> float | None:
    """Compute SSIM between two RGB arrays.

    Returns None if images are too small for SSIM (< 7x7).
    """
    min_dim = min(target.shape[0], target.shape[1])
    if min_dim < _MIN_SSIM_DIM:
        return None

    # Convert to grayscale for SSIM
    gray_target = np.mean(target, axis=2)
    gray_rendered = np.mean(rendered, axis=2)

    # structural_similarity returns float when gradient=False (default),
    # but pyright can't narrow the overloaded return type.
    raw_score = float(
        structural_similarity(  # type: ignore[arg-type]
            gray_target,
            gray_rendered,
            data_range=255.0,
        )
    )
    # Clamp to [0.0, 1.0] — SSIM can technically go negative
    return max(0.0, min(1.0, raw_score))


def calculate_delta(*, target: Path, rendered: Path) -> VisualDelta:
    """Compare two images and return structural difference metrics.

    Args:
        target: Path to the reference/expected image.
        rendered: Path to the actually rendered image.

    Returns:
        VisualDelta with composite_score, ssim_score, and pixel_diff_pct.

    Raises:
        FileNotFoundError: If either image path does not exist.
    """
    target_arr = _load_as_rgb(target)
    rendered_arr = _load_as_rgb(rendered)

    # Resize rendered to match target dimensions if needed
    if rendered_arr.shape[:2] != target_arr.shape[:2]:
        height, width = target_arr.shape[:2]
        rendered_img = Image.fromarray(rendered_arr).resize(
            (width, height), Image.Resampling.LANCZOS
        )
        rendered_arr = np.array(rendered_img, dtype=np.uint8)

    pixel_diff = _compute_pixel_diff(target_arr, rendered_arr)
    ssim = _compute_ssim(target_arr, rendered_arr)

    if ssim is not None:
        composite = (
            _SSIM_WEIGHT * ssim
            + _PIXEL_WEIGHT * (1.0 - pixel_diff / 100.0)
        )
    else:
        # Images too small for SSIM — use pixel diff only
        ssim = 1.0 - pixel_diff / 100.0  # synthetic stand-in
        composite = 1.0 - pixel_diff / 100.0

    composite = max(0.0, min(1.0, composite))

    return VisualDelta(
        composite_score=composite,
        ssim_score=ssim,
        pixel_diff_pct=pixel_diff,
    )
