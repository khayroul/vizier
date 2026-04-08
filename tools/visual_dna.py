"""S12 — Visual DNA extraction for Vizier.

Extracts from images:
  - ``dominant_colours``: Top 5 hex colours via k-means on pixels.
  - ``layout_type``: Classified layout (e.g. "centered", "split", "grid").
  - ``visual_embedding``: 512-dim CLIP ViT-B/32 vector (MPS device).

Populates nullable columns on the ``assets`` table.
"""

from __future__ import annotations

import json
import logging
from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Device + model singletons (lazy-loaded)
# ---------------------------------------------------------------------------

_DEVICE: str | None = None
_CLIP_MODEL: Any = None
_CLIP_PREPROCESS: Any = None
_CLIP_TOKENIZER: Any = None


def _get_device() -> str:
    """Return the compute device, lazy-detecting MPS availability."""
    global _DEVICE  # noqa: PLW0603
    if _DEVICE is None:
        import torch  # type: ignore[import-untyped]
        _DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
    return _DEVICE


def _load_clip() -> tuple[Any, Any, Any]:
    """Lazy-load CLIP ViT-B/32 on first call."""
    global _CLIP_MODEL, _CLIP_PREPROCESS, _CLIP_TOKENIZER  # noqa: PLW0603
    if _CLIP_MODEL is None:
        import open_clip  # type: ignore[import-untyped]

        device = _get_device()
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k", device=device
        )
        model.eval()
        _CLIP_MODEL = model
        _CLIP_PREPROCESS = preprocess
        _CLIP_TOKENIZER = open_clip.get_tokenizer("ViT-B-32")
    return _CLIP_MODEL, _CLIP_PREPROCESS, _CLIP_TOKENIZER


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------


def extract_visual_dna(image_data: bytes) -> dict[str, Any]:
    """Extract visual DNA from raw image bytes.

    Returns:
        Dict with keys:
            ``dominant_colours``: list of 5 hex strings.
            ``dominant_colours_json``: JSON string for Postgres JSONB.
            ``layout_type``: str classification.
            ``visual_embedding``: numpy array (512,).
            ``visual_embedding_str``: pgvector-compatible string.
    """
    img = Image.open(BytesIO(image_data)).convert("RGB")

    colours = _extract_dominant_colours(img, n_colours=5)
    layout = _classify_layout(img)
    embedding = _extract_clip_embedding(img)

    embedding_str = f"[{','.join(str(float(v)) for v in embedding)}]"

    return {
        "dominant_colours": colours,
        "dominant_colours_json": json.dumps(colours),
        "layout_type": layout,
        "visual_embedding": embedding,
        "visual_embedding_str": embedding_str,
    }


def populate_asset_visual_dna(asset_id: str, image_data: bytes) -> dict[str, Any]:
    """Extract visual DNA and UPDATE the assets table row.

    Args:
        asset_id: UUID of the asset row to update.
        image_data: Raw image bytes.

    Returns:
        The extracted visual DNA dict.
    """
    from utils.database import get_cursor

    visual = extract_visual_dna(image_data)

    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE assets
            SET dominant_colours = %s,
                layout_type = %s,
                visual_embedding = %s
            WHERE id = %s
            """,
            (
                visual["dominant_colours_json"],
                visual["layout_type"],
                visual["visual_embedding_str"],
                asset_id,
            ),
        )

    logger.info(
        "Updated asset %s: colours=%s layout=%s",
        asset_id,
        visual["dominant_colours"][:3],
        visual["layout_type"],
    )
    return visual


# ---------------------------------------------------------------------------
# Colour extraction (k-means on downsampled pixels)
# ---------------------------------------------------------------------------


def _extract_dominant_colours(img: Image.Image, n_colours: int = 5) -> list[str]:
    """Extract dominant colours as hex strings via k-means clustering."""
    from sklearn.cluster import KMeans  # type: ignore[import-untyped]

    # Downsample for speed
    small = img.resize((100, 100))
    pixels = np.array(small).reshape(-1, 3).astype(np.float32)

    kmeans = KMeans(n_clusters=n_colours, n_init=3, random_state=42)
    kmeans.fit(pixels)

    # Sort by cluster size (most dominant first)
    counts = np.bincount(kmeans.labels_, minlength=n_colours)
    order = np.argsort(-counts)
    centres = kmeans.cluster_centers_[order]

    return [
        f"#{int(r):02x}{int(g):02x}{int(b):02x}"
        for r, g, b in centres.astype(int).clip(0, 255)
    ]


# ---------------------------------------------------------------------------
# Layout classification (simple heuristic on spatial distribution)
# ---------------------------------------------------------------------------


def _classify_layout(img: Image.Image) -> str:
    """Classify layout type based on spatial intensity distribution.

    Categories: centered, left-heavy, right-heavy, top-heavy, bottom-heavy,
    split-horizontal, split-vertical, uniform.
    """
    grey = np.array(img.convert("L").resize((64, 64)), dtype=np.float32)
    h, w = grey.shape
    mid_h, mid_w = h // 2, w // 2

    # Quadrant mean intensities
    top_left = grey[:mid_h, :mid_w].mean()
    top_right = grey[:mid_h, mid_w:].mean()
    bot_left = grey[mid_h:, :mid_w].mean()
    bot_right = grey[mid_h:, mid_w:].mean()

    top = (top_left + top_right) / 2
    bottom = (bot_left + bot_right) / 2
    left = (top_left + bot_left) / 2
    right = (top_right + bot_right) / 2
    centre = grey[mid_h - 8 : mid_h + 8, mid_w - 8 : mid_w + 8].mean()
    overall = grey.mean()

    # Thresholds for classification
    diff_threshold = 20.0

    if abs(centre - overall) > diff_threshold and centre < overall:
        return "centered"
    if abs(left - right) > diff_threshold:
        if left < right:
            return "left-heavy"
        return "right-heavy"
    if abs(top - bottom) > diff_threshold:
        if top < bottom:
            return "top-heavy"
        return "bottom-heavy"
    lr_diff = abs(top_left + bot_left - top_right - bot_right)
    tb_diff = abs(top_left + top_right - bot_left - bot_right)
    if lr_diff > diff_threshold * 2:
        return "split-vertical"
    if tb_diff > diff_threshold * 2:
        return "split-horizontal"
    return "uniform"


# ---------------------------------------------------------------------------
# CLIP embedding
# ---------------------------------------------------------------------------


def _extract_clip_embedding(img: Image.Image) -> np.ndarray:
    """Compute 512-dim CLIP ViT-B/32 embedding on MPS/CPU."""
    import torch  # type: ignore[import-untyped]

    model, preprocess, _ = _load_clip()
    device = _get_device()

    tensor = preprocess(img).unsqueeze(0).to(device)  # type: ignore[union-attr]
    with torch.no_grad():
        features = model.encode_image(tensor)
        features = features / features.norm(dim=-1, keepdim=True)

    return features.cpu().numpy().flatten()
