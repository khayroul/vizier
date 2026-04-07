"""Image processing utilities for the illustration pipeline.

Position-aware character cropping for CLIP consistency verification.
Uses composition_guide.character_position to determine crop region
rather than always center-cropping.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image

# Crop region = 60% of image dimensions.
# Position offsets map character_position to horizontal anchor.
_CROP_FRACTION = 0.6

_POSITION_X_ANCHOR: dict[str, float] = {
    "centre": 0.5,       # crop centred horizontally
    "left_third": 0.3,   # crop centred on left third
    "right_third": 0.7,  # crop centred on right third
}


def crop_character_region(
    image_bytes: bytes,
    character_position: str = "centre",
) -> bytes:
    """Crop the character region from an illustration.

    Uses ``character_position`` from ``CompositionGuide`` to determine
    where the character is likely placed, then crops a 60% region
    around that position.

    Args:
        image_bytes: Raw image bytes (JPEG/PNG).
        character_position: From ``CompositionGuide.character_position``
            — one of ``centre``, ``left_third``, ``right_third``.

    Returns:
        Cropped image as JPEG bytes.
    """
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    width, height = img.size

    crop_w = int(width * _CROP_FRACTION)
    crop_h = int(height * _CROP_FRACTION)

    # Horizontal anchor — default to centre for unknown positions
    x_anchor = _POSITION_X_ANCHOR.get(character_position, 0.5)

    # Compute crop box, clamping to image bounds
    cx = int(width * x_anchor)
    x1 = max(0, cx - crop_w // 2)
    x2 = min(width, x1 + crop_w)
    x1 = max(0, x2 - crop_w)  # re-adjust if clamped on right

    # Vertical: always centre
    y1 = max(0, (height - crop_h) // 2)
    y2 = min(height, y1 + crop_h)

    cropped = img.crop((x1, y1, x2, y2))

    buf = BytesIO()
    cropped.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
