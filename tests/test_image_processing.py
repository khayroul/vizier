"""Tests for position-aware character cropping."""
from __future__ import annotations

from io import BytesIO

from PIL import Image

from utils.image_processing import crop_character_region


def _make_test_image(width: int = 1024, height: int = 1024) -> bytes:
    """Create a solid-color test image."""
    img = Image.new("RGB", (width, height), color=(128, 128, 128))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestCropCharacterRegion:
    """crop_character_region() crops based on character_position."""

    def test_centre_crops_middle_60_percent(self) -> None:
        img_bytes = _make_test_image(1000, 1000)
        cropped = crop_character_region(img_bytes, character_position="centre")
        img = Image.open(BytesIO(cropped))
        assert img.width == 600
        assert img.height == 600

    def test_left_third_crops_left_region(self) -> None:
        img_bytes = _make_test_image(1000, 1000)
        cropped = crop_character_region(img_bytes, character_position="left_third")
        img = Image.open(BytesIO(cropped))
        assert img.width == 600
        assert img.height == 600

    def test_right_third_crops_right_region(self) -> None:
        img_bytes = _make_test_image(1000, 1000)
        cropped = crop_character_region(img_bytes, character_position="right_third")
        img = Image.open(BytesIO(cropped))
        assert img.width == 600
        assert img.height == 600

    def test_unknown_position_falls_back_to_centre(self) -> None:
        img_bytes = _make_test_image(1000, 1000)
        cropped = crop_character_region(img_bytes, character_position="unknown")
        img = Image.open(BytesIO(cropped))
        assert img.width == 600

    def test_cropped_region_differs_by_position(self) -> None:
        """Left and right crops should produce different pixel data."""
        img = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                img.putpixel((x, y), (x * 2, y * 2, 0))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        img_bytes = buf.getvalue()

        left = crop_character_region(img_bytes, "left_third")
        right = crop_character_region(img_bytes, "right_third")
        assert left != right
