"""Tests for scripts.visual.calculate_delta — visual QA structural comparison."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


def _save_image(arr: np.ndarray, path: Path) -> None:
    """Save a numpy RGB array as PNG."""
    Image.fromarray(arr.astype(np.uint8)).save(path)


@pytest.fixture()
def tmp_images(tmp_path: Path) -> dict[str, Path]:
    """Create a pair of test image paths."""
    return {
        "target": tmp_path / "target.png",
        "rendered": tmp_path / "rendered.png",
    }


class TestIdenticalImages:
    """Identical images should produce perfect scores."""

    def test_composite_near_one(self, tmp_images: dict[str, Path]) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        arr = np.full((100, 100, 3), 128, dtype=np.uint8)
        _save_image(arr, tmp_images["target"])
        _save_image(arr, tmp_images["rendered"])

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        assert delta.composite_score == pytest.approx(1.0, abs=0.01)

    def test_ssim_near_one(self, tmp_images: dict[str, Path]) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        arr = np.full((100, 100, 3), 128, dtype=np.uint8)
        _save_image(arr, tmp_images["target"])
        _save_image(arr, tmp_images["rendered"])

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        assert delta.ssim_score == pytest.approx(1.0, abs=0.01)

    def test_pixel_diff_near_zero(self, tmp_images: dict[str, Path]) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        arr = np.full((100, 100, 3), 128, dtype=np.uint8)
        _save_image(arr, tmp_images["target"])
        _save_image(arr, tmp_images["rendered"])

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        assert delta.pixel_diff_pct == pytest.approx(0.0, abs=0.1)


class TestCompletelyDifferentImages:
    """Black vs white images should produce low scores."""

    def test_composite_well_below_threshold(
        self, tmp_images: dict[str, Path]
    ) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        black = np.zeros((100, 100, 3), dtype=np.uint8)
        white = np.full((100, 100, 3), 255, dtype=np.uint8)
        _save_image(black, tmp_images["target"])
        _save_image(white, tmp_images["rendered"])

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        assert delta.composite_score < 0.50

    def test_pixel_diff_near_hundred(
        self, tmp_images: dict[str, Path]
    ) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        black = np.zeros((100, 100, 3), dtype=np.uint8)
        white = np.full((100, 100, 3), 255, dtype=np.uint8)
        _save_image(black, tmp_images["target"])
        _save_image(white, tmp_images["rendered"])

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        assert delta.pixel_diff_pct > 95.0


class TestPartialDifference:
    """Image with a small changed region should produce intermediate scores."""

    def test_intermediate_composite(
        self, tmp_images: dict[str, Path]
    ) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        base = np.full((100, 100, 3), 128, dtype=np.uint8)
        modified = base.copy()
        # Change a 20x20 region (4% of pixels)
        modified[40:60, 40:60, :] = 255

        _save_image(base, tmp_images["target"])
        _save_image(modified, tmp_images["rendered"])

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        # Should pass default 0.80 threshold — small region changed
        assert delta.composite_score > 0.80
        assert delta.pixel_diff_pct > 0.0
        assert delta.pixel_diff_pct < 10.0


class TestDifferentSizedImages:
    """Rendered image with different dimensions should be resized, not crash."""

    def test_resize_handled(self, tmp_images: dict[str, Path]) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        target = np.full((100, 100, 3), 128, dtype=np.uint8)
        rendered = np.full((200, 150, 3), 128, dtype=np.uint8)
        _save_image(target, tmp_images["target"])
        _save_image(rendered, tmp_images["rendered"])

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        # Same color, just resized — should be near-identical
        assert delta.composite_score > 0.90


class TestSmallImages:
    """Images smaller than SSIM window (7x7) should not crash."""

    def test_1x1_identical(self, tmp_images: dict[str, Path]) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        arr = np.full((1, 1, 3), 128, dtype=np.uint8)
        _save_image(arr, tmp_images["target"])
        _save_image(arr, tmp_images["rendered"])

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        assert delta.composite_score == pytest.approx(1.0, abs=0.01)

    def test_1x1_different(self, tmp_images: dict[str, Path]) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        _save_image(
            np.zeros((1, 1, 3), dtype=np.uint8), tmp_images["target"]
        )
        _save_image(
            np.full((1, 1, 3), 255, dtype=np.uint8), tmp_images["rendered"]
        )

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        assert delta.composite_score < 0.50

    def test_3x3_images(self, tmp_images: dict[str, Path]) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        arr = np.full((3, 3, 3), 100, dtype=np.uint8)
        _save_image(arr, tmp_images["target"])
        _save_image(arr, tmp_images["rendered"])

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        assert delta.composite_score > 0.90


class TestMissingFiles:
    """Missing image files should raise FileNotFoundError."""

    def test_missing_target(self, tmp_path: Path) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        rendered = tmp_path / "rendered.png"
        _save_image(
            np.full((10, 10, 3), 128, dtype=np.uint8), rendered
        )

        with pytest.raises(FileNotFoundError):
            calculate_delta(
                target=tmp_path / "nonexistent.png",
                rendered=rendered,
            )

    def test_missing_rendered(self, tmp_path: Path) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        target = tmp_path / "target.png"
        _save_image(
            np.full((10, 10, 3), 128, dtype=np.uint8), target
        )

        with pytest.raises(FileNotFoundError):
            calculate_delta(
                target=target,
                rendered=tmp_path / "nonexistent.png",
            )


class TestReturnType:
    """Return type should be a frozen dataclass with correct fields."""

    def test_has_required_attributes(
        self, tmp_images: dict[str, Path]
    ) -> None:
        from scripts.visual.calculate_delta import VisualDelta, calculate_delta

        arr = np.full((50, 50, 3), 128, dtype=np.uint8)
        _save_image(arr, tmp_images["target"])
        _save_image(arr, tmp_images["rendered"])

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        assert isinstance(delta, VisualDelta)
        assert isinstance(delta.composite_score, float)
        assert isinstance(delta.ssim_score, float)
        assert isinstance(delta.pixel_diff_pct, float)

    def test_frozen(self, tmp_images: dict[str, Path]) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        arr = np.full((50, 50, 3), 128, dtype=np.uint8)
        _save_image(arr, tmp_images["target"])
        _save_image(arr, tmp_images["rendered"])

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        with pytest.raises(AttributeError):
            delta.composite_score = 0.5  # type: ignore[misc]


class TestRGBAHandling:
    """RGBA images (PNG with transparency) should be handled correctly."""

    def test_rgba_converted_to_rgb(self, tmp_images: dict[str, Path]) -> None:
        from scripts.visual.calculate_delta import calculate_delta

        # Save as RGBA
        rgba = np.full((50, 50, 4), 128, dtype=np.uint8)
        Image.fromarray(rgba, mode="RGBA").save(tmp_images["target"])
        Image.fromarray(rgba, mode="RGBA").save(tmp_images["rendered"])

        delta = calculate_delta(
            target=tmp_images["target"],
            rendered=tmp_images["rendered"],
        )
        assert delta.composite_score == pytest.approx(1.0, abs=0.01)
