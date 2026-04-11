"""Cluster D4 CGL layouts into HTML poster template archetypes.

Reads D4 CGL parquet files, extracts normalised layout features using
a 6x8 grid occupancy approach, clusters via K-means, then generates
one HTML/CSS poster template per cluster centroid.

Also cross-references D5 Magazine Layout industries to tag each
template with industry_fit.

Usage:
    python -m scripts.cluster_d4_templates
    python -m scripts.cluster_d4_templates --k 28 --output templates/html
"""
from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import yaml
from numpy.typing import NDArray
from sklearn.cluster import KMeans

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
D4_DIR = REPO_ROOT / "datasets" / "D4_CGL_Dataset_v2" / "data"
D5_DIR = REPO_ROOT / "datasets" / "D5_Magazine_Layout" / "data"
TEMPLATE_DIR = REPO_ROOT / "templates" / "html"

GRID_ROWS = 8
GRID_COLS = 6

# D4 supercategory mapping (category_id -> name)
D4_CATEGORY_MAP: dict[int, str] = {
    1: "logo",
    2: "text",
    3: "underlay",
    4: "embellishment",
}

# Channel indices in the feature vector per grid cell:
# 0=logo, 1=text, 2=underlay, 3=embellishment
CATEGORY_CHANNEL: dict[str, int] = {
    "logo": 0,
    "text": 1,
    "underlay": 2,
    "embellishment": 3,
}
NUM_CHANNELS = len(CATEGORY_CHANNEL)

# Total feature dimensionality: 6 cols * 8 rows * 4 channels = 192
FEATURE_DIM = GRID_ROWS * GRID_COLS * NUM_CHANNELS

# D5 category_id -> industry name
D5_CATEGORY_MAP: dict[int, str] = {
    0: "fashion",
    1: "food",
    2: "general",   # "news" maps to general
    3: "education",  # "science" maps to education
    4: "general",   # "travel" maps to general
    5: "general",   # "wedding" maps to general
}

# Canonical industry labels
CANONICAL_INDUSTRIES = frozenset(
    {"food", "fashion", "education", "tech", "retail", "general"}
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LayoutElement:
    """A single annotation element with normalised coordinates."""

    category: str
    x_norm: float
    y_norm: float
    w_norm: float
    h_norm: float


@dataclass(frozen=True)
class LayoutImage:
    """All elements for one image, normalised."""

    image_id: int
    width: int
    height: int
    elements: tuple[LayoutElement, ...]


@dataclass
class TemplateZone:
    """A positioned zone within a generated template."""

    zone_type: str
    grid_row_start: int
    grid_row_end: int
    grid_col_start: int
    grid_col_end: int
    area_fraction: float = 0.0


@dataclass
class ArchetypeInfo:
    """Metadata for a generated archetype template."""

    name: str
    zones: list[TemplateZone] = field(default_factory=list)
    density: str = "moderate"
    cta_prominence: str = "medium"
    supported_slots: list[str] = field(default_factory=list)
    tone_fit: list[str] = field(default_factory=list)
    occasion_fit: list[str] = field(default_factory=list)
    industry_fit: list[str] = field(default_factory=list)
    hero_style: str = "contained"
    cluster_size: int = 0


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


def _parse_d4_row(row: Any) -> LayoutImage | None:
    """Parse a single D4 parquet row into a LayoutImage."""
    width = int(cast(int, row["width"]))
    height = int(cast(int, row["height"]))
    if width <= 0 or height <= 0:
        return None

    annotations: Any = row["annotations"]
    bbox_arr: Any = annotations["bbox"]
    category_arr: Any = annotations["category"]
    n_annotations = len(bbox_arr)

    elements: list[LayoutElement] = []
    for idx in range(n_annotations):
        bbox: Any = bbox_arr[idx]
        cat_info: Any = category_arr[idx]

        # Extract supercategory name
        if isinstance(cat_info, dict):
            cat_name = cat_info.get("supercategory", "text")
        else:
            cat_name = "text"

        # bbox is [x, y, w, h] in COCO format
        bx = float(bbox[0])
        by = float(bbox[1])
        bw = float(bbox[2])
        bh = float(bbox[3])

        elements.append(
            LayoutElement(
                category=str(cat_name),
                x_norm=bx / width,
                y_norm=by / height,
                w_norm=bw / width,
                h_norm=bh / height,
            )
        )

    return LayoutImage(
        image_id=int(cast(int, row["image_id"])),
        width=width,
        height=height,
        elements=tuple(elements),
    )


def extract_layout_features(layouts: list[LayoutImage]) -> NDArray[np.float64]:
    """Convert layouts to grid-based occupancy feature vectors.

    Divides each image into a GRID_ROWS x GRID_COLS grid. For each cell,
    records which element categories are present (multi-channel binary).
    Result: (n_layouts, GRID_ROWS * GRID_COLS * NUM_CHANNELS) matrix.

    Args:
        layouts: List of LayoutImage objects.

    Returns:
        Feature matrix of shape (n_layouts, FEATURE_DIM).
    """
    features = np.zeros((len(layouts), FEATURE_DIM), dtype=np.float64)

    for idx, layout in enumerate(layouts):
        for elem in layout.elements:
            channel = CATEGORY_CHANNEL.get(elem.category)
            if channel is None:
                continue

            # Determine which grid cells this element overlaps
            col_start = int(elem.x_norm * GRID_COLS)
            col_end = int((elem.x_norm + elem.w_norm) * GRID_COLS)
            row_start = int(elem.y_norm * GRID_ROWS)
            row_end = int((elem.y_norm + elem.h_norm) * GRID_ROWS)

            # Clamp to grid bounds
            col_start = max(0, min(col_start, GRID_COLS - 1))
            col_end = max(col_start, min(col_end, GRID_COLS - 1))
            row_start = max(0, min(row_start, GRID_ROWS - 1))
            row_end = max(row_start, min(row_end, GRID_ROWS - 1))

            for row_idx in range(row_start, row_end + 1):
                for col_idx in range(col_start, col_end + 1):
                    feat_idx = (row_idx * GRID_COLS + col_idx) * NUM_CHANNELS + channel
                    features[idx, feat_idx] = 1.0

    return features


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


def cluster_layouts(
    features: NDArray[np.float64],
    n_clusters: int = 28,
    random_state: int = 42,
) -> tuple[NDArray[np.int32], NDArray[np.float64], list[int]]:
    """K-means cluster the layout feature vectors.

    Args:
        features: Feature matrix (n_samples, FEATURE_DIM).
        n_clusters: Number of clusters.
        random_state: Seed for reproducibility.

    Returns:
        Tuple of (labels, centroids, cluster_sizes).
    """
    kmeans = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        n_init=10,  # type: ignore[arg-type]  # sklearn stubs allow str but int is valid
        max_iter=300,
    )
    labels = kmeans.fit_predict(features)
    centroids = kmeans.cluster_centers_
    cluster_sizes = [int(np.sum(labels == k)) for k in range(n_clusters)]
    return labels.astype(np.int32), centroids, cluster_sizes


# ---------------------------------------------------------------------------
# Centroid → template zones
# ---------------------------------------------------------------------------

# Zone type priority — which category "wins" a grid cell
_ZONE_PRIORITY: dict[str, int] = {
    "logo": 4,
    "text": 3,
    "underlay": 1,
    "embellishment": 2,
}


def _centroid_to_zone_grid(
    centroid: NDArray[np.float64],
    threshold: float = 0.3,
) -> NDArray[np.int32]:
    """Convert a centroid vector to a GRID_ROWS x GRID_COLS zone assignment grid.

    Each cell gets the highest-priority category that exceeds the threshold.
    Returns integer grid: 0=empty, 1=logo, 2=text, 3=underlay, 4=embellishment.
    """
    grid = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.int32)

    for row_idx in range(GRID_ROWS):
        for col_idx in range(GRID_COLS):
            base = (row_idx * GRID_COLS + col_idx) * NUM_CHANNELS
            cell_values = centroid[base : base + NUM_CHANNELS]

            best_cat = 0
            best_priority = -1
            for cat_name, channel_idx in CATEGORY_CHANNEL.items():
                if cell_values[channel_idx] >= threshold:
                    priority = _ZONE_PRIORITY[cat_name]
                    if priority > best_priority:
                        best_priority = priority
                        best_cat = channel_idx + 1  # 1-indexed
            grid[row_idx, col_idx] = best_cat

    return grid


def _merge_adjacent_cells(
    zone_grid: NDArray[np.int32],
) -> list[TemplateZone]:
    """Merge adjacent grid cells of the same type into rectangular zones.

    Uses a greedy row-scanning approach to find maximal rectangles.
    """
    visited = np.zeros_like(zone_grid, dtype=bool)
    zones: list[TemplateZone] = []

    # Category channel to zone type name
    channel_to_zone: dict[int, str] = {
        1: "logo",
        2: "text",
        3: "underlay",
        4: "embellishment",
    }

    for row_idx in range(GRID_ROWS):
        for col_idx in range(GRID_COLS):
            cell_val = zone_grid[row_idx, col_idx]
            if cell_val == 0 or visited[row_idx, col_idx]:
                continue

            # Expand right
            col_end = col_idx
            while (
                col_end + 1 < GRID_COLS
                and zone_grid[row_idx, col_end + 1] == cell_val
                and not visited[row_idx, col_end + 1]
            ):
                col_end += 1

            # Expand down
            row_end = row_idx
            while row_end + 1 < GRID_ROWS:
                can_expand = True
                for ci in range(col_idx, col_end + 1):
                    if (
                        zone_grid[row_end + 1, ci] != cell_val
                        or visited[row_end + 1, ci]
                    ):
                        can_expand = False
                        break
                if can_expand:
                    row_end += 1
                else:
                    break

            # Mark visited
            for ri in range(row_idx, row_end + 1):
                for ci in range(col_idx, col_end + 1):
                    visited[ri, ci] = True

            zone_type = channel_to_zone.get(cell_val, "unknown")
            area = (row_end - row_idx + 1) * (col_end - col_idx + 1)
            total = GRID_ROWS * GRID_COLS

            zones.append(
                TemplateZone(
                    zone_type=zone_type,
                    grid_row_start=row_idx + 1,  # CSS grid is 1-indexed
                    grid_row_end=row_end + 2,
                    grid_col_start=col_idx + 1,
                    grid_col_end=col_end + 2,
                    area_fraction=area / total,
                )
            )

    return zones


# ---------------------------------------------------------------------------
# Zone → slot mapping
# ---------------------------------------------------------------------------


def _zones_to_slots(zones: list[TemplateZone]) -> list[str]:
    """Determine supported_slots from the zone types present."""
    zone_types = {zone.zone_type for zone in zones}
    has_text = "text" in zone_types
    has_logo = "logo" in zone_types
    _has_underlay = "underlay" in zone_types

    # Count text zones by size
    text_zones = sorted(
        [z for z in zones if z.zone_type == "text"],
        key=lambda z: z.area_fraction,
        reverse=True,
    )

    slots: list[str] = []

    # Always include hero_image (the background / underlay area)
    slots.append("hero_image")

    if has_text and len(text_zones) >= 1:
        slots.append("headline")
    if has_text and len(text_zones) >= 2:
        slots.append("subheadline")
    if has_text and len(text_zones) >= 3:
        slots.append("body_text")
    if has_text and len(text_zones) >= 4:
        slots.append("tagline")

    if has_logo:
        slots.append("logo")

    # CTA is common — add if there are at least 2 text zones
    if has_text and len(text_zones) >= 2:
        slots.append("cta")

    # Price slot if dense (many text zones)
    if len(text_zones) >= 5:
        slots.append("price")

    # Badge for embellishment zones
    if "embellishment" in zone_types:
        slots.append("badge")

    return slots


def _compute_density(zones: list[TemplateZone]) -> str:
    """Determine layout density from zone count and coverage."""
    total_area = sum(z.area_fraction for z in zones)
    n_zones = len(zones)

    if n_zones <= 2 or total_area < 0.25:
        return "minimal"
    elif n_zones >= 6 or total_area > 0.6:
        return "dense"
    return "moderate"


def _compute_cta_prominence(zones: list[TemplateZone]) -> str:
    """Infer CTA prominence from text zone positioning."""
    text_zones = [z for z in zones if z.zone_type == "text"]
    if not text_zones:
        return "none"

    # Check if any text zone is in the bottom third
    bottom_text = [z for z in text_zones if z.grid_row_start >= 6]
    if bottom_text:
        return "high"
    elif len(text_zones) >= 3:
        return "medium"
    return "low"


def _compute_hero_style(zones: list[TemplateZone]) -> str:
    """Infer hero image style from underlay/empty area distribution."""
    underlay_zones = [z for z in zones if z.zone_type == "underlay"]
    total_underlay = sum(z.area_fraction for z in underlay_zones)
    text_zones = [z for z in zones if z.zone_type == "text"]

    if total_underlay > 0.5:
        return "full_bleed"
    elif text_zones and any(z.grid_col_start >= 4 for z in text_zones):
        return "split"
    return "contained"


# ---------------------------------------------------------------------------
# Archetype naming
# ---------------------------------------------------------------------------

# Names based on dominant layout patterns
_POSITION_NAMES: dict[str, str] = {
    "top_left": "top_left",
    "top_center": "top_center",
    "top_right": "top_right",
    "center": "center",
    "center_left": "left_panel",
    "center_right": "right_panel",
    "bottom_left": "bottom_left",
    "bottom_center": "bottom_center",
    "bottom_right": "bottom_right",
}


def _classify_text_position(zones: list[TemplateZone]) -> str:
    """Classify the dominant text position in the layout."""
    text_zones = [z for z in zones if z.zone_type == "text"]
    if not text_zones:
        return "minimal"

    # Find the largest text zone
    main_text = max(text_zones, key=lambda z: z.area_fraction)

    # Vertical position
    mid_row = (main_text.grid_row_start + main_text.grid_row_end) / 2
    if mid_row <= 3:
        vert = "top"
    elif mid_row >= 7:
        vert = "bottom"
    else:
        vert = "center"

    # Horizontal position
    mid_col = (main_text.grid_col_start + main_text.grid_col_end) / 2
    if mid_col <= 2.5:
        horiz = "left"
    elif mid_col >= 4.5:
        horiz = "right"
    else:
        horiz = "center"

    return f"{vert}_{horiz}"


def _generate_archetype_name(
    cluster_idx: int,
    zones: list[TemplateZone],
    density: str,
) -> str:
    """Generate a descriptive archetype name for a cluster."""
    text_position = _classify_text_position(zones)
    n_text = len([z for z in zones if z.zone_type == "text"])
    has_logo = any(z.zone_type == "logo" for z in zones)

    # Build descriptive suffix
    parts: list[str] = []

    # Position descriptor
    position_map: dict[str, str] = {
        "top_left": "top_left",
        "top_center": "hero_top",
        "top_right": "top_right",
        "center_left": "left_panel",
        "center_center": "center_focus",
        "center_right": "right_panel",
        "bottom_left": "bottom_left",
        "bottom_center": "hero_bottom",
        "bottom_right": "bottom_right",
        "minimal": "minimal",
    }
    base_name = position_map.get(text_position, "layout")
    parts.append(base_name)

    # Density qualifier
    if density == "dense" and n_text >= 4:
        parts.append("dense")
    elif density == "minimal":
        parts.append("clean")

    # Logo qualifier
    if has_logo:
        parts.append("logo")

    # Text zone count qualifier
    if n_text >= 5:
        parts.append("multi")
    elif n_text == 1:
        parts.append("single")

    name = "_".join(parts)

    # Deduplicate with cluster index suffix if needed
    return f"{name}_{cluster_idx:02d}"


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

_ZONE_CSS_CLASSES: dict[str, str] = {
    "logo": "zone-logo",
    "text": "zone-text",
    "underlay": "zone-underlay",
    "embellishment": "zone-embellishment",
}

_SLOT_ORDER = [
    "hero_image",
    "headline",
    "subheadline",
    "body_text",
    "tagline",
    "cta",
    "logo",
    "price",
    "badge",
]

_SLOT_TO_PLACEHOLDER: dict[str, str] = {
    "hero_image": "{{ background_image }}",
    "headline": "{{ headline }}",
    "subheadline": "{{ subheadline }}",
    "body_text": "{{ body_text }}",
    "tagline": "{{ tagline }}",
    "cta": "{{ cta }}",
    "logo": "{{ logo_url }}",
    "price": "{{ price }}",
    "badge": "{{ badge }}",
}


def generate_template_html(archetype: ArchetypeInfo) -> str:
    """Generate an HTML/CSS poster template from archetype info.

    Creates a simple CSS grid layout with positioned zone divs.
    No JavaScript. Uses Jinja2 placeholders for content injection.

    Args:
        archetype: The ArchetypeInfo describing the template layout.

    Returns:
        HTML string for the template file.
    """
    # Build grid-area assignments for each zone
    zone_html_parts: list[str] = []
    zone_css_parts: list[str] = []

    # Track which slots have been assigned to zones
    available_slots = list(archetype.supported_slots)
    text_zone_idx = 0

    # Slot assignment for text zones (in order of area, largest first)
    text_slots = ["headline", "subheadline", "body_text", "tagline", "cta", "price"]
    _text_zones_sorted = sorted(
        [z for z in archetype.zones if z.zone_type == "text"],
        key=lambda z: z.area_fraction,
        reverse=True,
    )

    zone_slot_map: dict[int, str] = {}

    for zone_idx, zone in enumerate(archetype.zones):
        if zone.zone_type == "text":
            if text_zone_idx < len(text_slots):
                slot = text_slots[text_zone_idx]
                if slot in available_slots:
                    zone_slot_map[zone_idx] = slot
                    text_zone_idx += 1
                else:
                    text_zone_idx += 1
        elif zone.zone_type == "logo" and "logo" in available_slots:
            zone_slot_map[zone_idx] = "logo"
        elif zone.zone_type == "embellishment" and "badge" in available_slots:
            zone_slot_map[zone_idx] = "badge"

    for zone_idx, zone in enumerate(archetype.zones):
        css_class = _ZONE_CSS_CLASSES.get(zone.zone_type, "zone-generic")
        slot = zone_slot_map.get(zone_idx, "")

        # CSS for this zone
        zone_css_parts.append(
            f"    .{css_class}-{zone_idx} {{\n"
            f"      grid-row: {zone.grid_row_start} / {zone.grid_row_end};\n"
            f"      grid-column: {zone.grid_col_start} / {zone.grid_col_end};\n"
            f"    }}"
        )

        # HTML for this zone
        if slot == "hero_image":
            continue  # Hero image is background, not a zone div
        elif slot == "logo":
            zone_html_parts.append(
                f'    {{% if logo_url %}}\n'
                f'    <div class="{css_class}-{zone_idx} zone-logo">\n'
                f'      <img src="{{{{ logo_url }}}}" alt="logo" style="max-width: 100%; max-height: 100%; object-fit: contain;">\n'
                f"    </div>\n"
                f"    {{% endif %}}"
            )
        elif slot == "headline":
            zone_html_parts.append(
                f'    {{% if headline %}}\n'
                f'    <div class="{css_class}-{zone_idx} zone-text zone-headline">\n'
                f"      {{{{ headline }}}}\n"
                f"    </div>\n"
                f"    {{% endif %}}"
            )
        elif slot == "subheadline":
            zone_html_parts.append(
                f'    {{% if subheadline %}}\n'
                f'    <div class="{css_class}-{zone_idx} zone-text zone-subheadline">\n'
                f"      {{{{ subheadline }}}}\n"
                f"    </div>\n"
                f"    {{% endif %}}"
            )
        elif slot == "body_text":
            zone_html_parts.append(
                f'    {{% if body_text %}}\n'
                f'    <div class="{css_class}-{zone_idx} zone-text zone-body">\n'
                f"      {{{{ body_text }}}}\n"
                f"    </div>\n"
                f"    {{% endif %}}"
            )
        elif slot == "cta":
            zone_html_parts.append(
                f'    {{% if cta %}}\n'
                f'    <div class="{css_class}-{zone_idx} zone-text zone-cta">\n'
                f"      {{{{ cta }}}}\n"
                f"    </div>\n"
                f"    {{% endif %}}"
            )
        elif slot == "tagline":
            zone_html_parts.append(
                f'    {{% if tagline %}}\n'
                f'    <div class="{css_class}-{zone_idx} zone-text zone-tagline">\n'
                f"      {{{{ tagline }}}}\n"
                f"    </div>\n"
                f"    {{% endif %}}"
            )
        elif slot == "price":
            zone_html_parts.append(
                f'    {{% if price %}}\n'
                f'    <div class="{css_class}-{zone_idx} zone-text zone-price">\n'
                f"      {{{{ price }}}}\n"
                f"    </div>\n"
                f"    {{% endif %}}"
            )
        elif slot == "badge":
            zone_html_parts.append(
                f'    {{% if badge %}}\n'
                f'    <div class="{css_class}-{zone_idx} zone-embellishment zone-badge">\n'
                f"      {{{{ badge }}}}\n"
                f"    </div>\n"
                f"    {{% endif %}}"
            )
        else:
            # Unassigned zone — render as structural placeholder
            zone_html_parts.append(
                f'    <div class="{css_class}-{zone_idx} zone-{zone.zone_type}"></div>'
            )

    zone_css = "\n".join(zone_css_parts)
    zone_html = "\n".join(zone_html_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=794, initial-scale=1.0">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      width: 794px;
      height: 1123px;
      overflow: hidden;
      position: relative;
      font-family: var(--font-body, 'Inter', 'Helvetica Neue', Arial, sans-serif);
      background: #0a0a12;
    }}

    :root {{
      --primary: {{{{ primary | default('#1a1a2e') }}}};
      --accent: {{{{ accent | default('#e94560') }}}};
      --font-headline: {{{{ font_headline | default('Plus Jakarta Sans') }}}};
      --font-body: {{{{ font_body | default('Inter') }}}};
    }}

    .bg-image {{
      position: absolute;
      inset: 0;
      background-image: url('{{{{ background_image }}}}');
      background-size: cover;
      background-position: center;
      z-index: 0;
    }}

    .overlay {{
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.6) 100%);
      z-index: 1;
    }}

    .grid-container {{
      position: absolute;
      inset: 24px;
      display: grid;
      grid-template-rows: repeat({GRID_ROWS}, 1fr);
      grid-template-columns: repeat({GRID_COLS}, 1fr);
      gap: 8px;
      z-index: 2;
    }}

    .zone-text {{ padding: 12px; color: #fff; }}
    .zone-headline {{ font-family: var(--font-headline); font-size: 48px; font-weight: 800; line-height: 1.05; }}
    .zone-subheadline {{ font-family: var(--font-headline); font-size: 20px; font-weight: 500; line-height: 1.4; opacity: 0.85; }}
    .zone-body {{ font-size: 15px; line-height: 1.55; opacity: 0.9; }}
    .zone-cta {{ font-family: var(--font-headline); font-size: 17px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; display: flex; align-items: center; }}
    .zone-tagline {{ font-size: 14px; font-style: italic; opacity: 0.75; }}
    .zone-price {{ font-family: var(--font-headline); font-size: 36px; font-weight: 800; color: var(--accent); }}
    .zone-logo {{ padding: 8px; display: flex; align-items: center; justify-content: center; }}
    .zone-badge {{ padding: 8px; display: flex; align-items: center; justify-content: center; }}
    .zone-embellishment {{ padding: 4px; }}
    .zone-underlay {{ background: rgba(255,255,255,0.05); border-radius: 8px; }}

{zone_css}
  </style>
</head>
<body>
  <div class="bg-image"></div>
  <div class="overlay"></div>

  <div class="grid-container">
{zone_html}
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# D5 industry tagging
# ---------------------------------------------------------------------------


def _load_d5_layout_features(d5_dir: Path) -> NDArray[np.float64]:
    """Load D5 magazine layouts and extract the same grid features as D4.

    D5 elements use polygon coordinates instead of bboxes. We convert
    polygon bounding boxes to the same 6x8 grid feature format.
    """
    parquet_files = sorted(d5_dir.glob("*.parquet"))
    if not parquet_files:
        return np.zeros((0, FEATURE_DIM), dtype=np.float64)

    all_features: list[NDArray[np.float64]] = []
    all_industries: list[str] = []

    # D5 element label -> our category channel
    # 0=text, 1=image, 2=headline, 3=background, 4=logo (approximate)
    d5_label_to_channel: dict[int, int] = {
        0: CATEGORY_CHANNEL["text"],         # text -> text
        1: CATEGORY_CHANNEL["underlay"],     # image -> underlay
        2: CATEGORY_CHANNEL["text"],         # headline -> text
        3: CATEGORY_CHANNEL["underlay"],     # background -> underlay
        4: CATEGORY_CHANNEL["logo"],         # logo-ish -> logo
    }

    for pq_file in parquet_files:
        df = pd.read_parquet(pq_file)
        for _, row in df.iterrows():
            d5_row: Any = row
            size_info: Any = d5_row["size"]
            width = int(cast(int, size_info["width"]))
            height = int(cast(int, size_info["height"]))
            if width <= 0 or height <= 0:
                continue

            category_id = int(cast(int, d5_row["category"]))
            industry = D5_CATEGORY_MAP.get(category_id, "general")

            elements: Any = d5_row["elements"]
            labels: Any = elements["label"]
            polygon_x: Any = elements["polygon_x"]
            polygon_y: Any = elements["polygon_y"]

            feature_vec = np.zeros(FEATURE_DIM, dtype=np.float64)

            for elem_idx in range(len(labels)):
                label = int(labels[elem_idx])
                channel = d5_label_to_channel.get(label)
                if channel is None:
                    continue

                px: Any = polygon_x[elem_idx]
                py: Any = polygon_y[elem_idx]

                # Skip elements with NaN coordinates
                if np.any(np.isnan(px)) or np.any(np.isnan(py)):
                    continue

                # Bounding box from polygon
                x_min = float(np.nanmin(px)) / width
                x_max = float(np.nanmax(px)) / width
                y_min = float(np.nanmin(py)) / height
                y_max = float(np.nanmax(py)) / height

                col_start = max(0, min(int(x_min * GRID_COLS), GRID_COLS - 1))
                col_end = max(col_start, min(int(x_max * GRID_COLS), GRID_COLS - 1))
                row_start = max(0, min(int(y_min * GRID_ROWS), GRID_ROWS - 1))
                row_end = max(row_start, min(int(y_max * GRID_ROWS), GRID_ROWS - 1))

                for ri in range(row_start, row_end + 1):
                    for ci in range(col_start, col_end + 1):
                        feat_idx = (ri * GRID_COLS + ci) * NUM_CHANNELS + channel
                        feature_vec[feat_idx] = 1.0

            all_features.append(feature_vec)
            all_industries.append(industry)

    if not all_features:
        return np.zeros((0, FEATURE_DIM), dtype=np.float64)

    return np.array(all_features, dtype=np.float64)


def _load_d5_industries(d5_dir: Path) -> list[str]:
    """Load industry labels from D5 for each layout."""
    parquet_files = sorted(d5_dir.glob("*.parquet"))
    industries: list[str] = []

    for pq_file in parquet_files:
        df = pd.read_parquet(pq_file)
        for _, row in df.iterrows():
            d5_row: Any = row
            category_id = int(cast(int, d5_row["category"]))
            industries.append(D5_CATEGORY_MAP.get(category_id, "general"))

    return industries


def compute_industry_fit(
    d4_centroids: NDArray[np.float64],
    d5_features: NDArray[np.float64],
    d5_industries: list[str],
    top_n: int = 100,
) -> list[list[str]]:
    """For each D4 cluster centroid, find closest D5 layouts and vote on industry.

    For each centroid, finds the top_n closest D5 layouts by Euclidean
    distance, tallies industry votes, and returns industries that
    represent >= 15% of the votes.

    Args:
        d4_centroids: (n_clusters, FEATURE_DIM) cluster centroids.
        d5_features: (n_d5, FEATURE_DIM) D5 layout features.
        d5_industries: Industry label per D5 layout.
        top_n: Number of nearest D5 layouts to consider.

    Returns:
        List of industry_fit lists, one per centroid.
    """
    if len(d5_features) == 0 or len(d5_industries) == 0:
        return [["general"] for _ in range(len(d4_centroids))]

    result: list[list[str]] = []

    for centroid in d4_centroids:
        # Compute distances to all D5 layouts
        distances = np.linalg.norm(d5_features - centroid, axis=1)
        nearest_indices = np.argsort(distances)[:top_n]

        # Tally industry votes
        votes: dict[str, int] = {}
        for idx in nearest_indices:
            industry = d5_industries[int(idx)]
            votes[industry] = votes.get(industry, 0) + 1

        # Industries with >= 15% of votes
        threshold = 0.15 * len(nearest_indices)
        industries = sorted(
            ind for ind, count in votes.items() if count >= threshold
        )

        # Always include "general" as fallback
        if not industries:
            industries = ["general"]
        if "general" not in industries:
            industries.append("general")
            industries.sort()

        result.append(industries)

    return result


# ---------------------------------------------------------------------------
# Tag existing templates
# ---------------------------------------------------------------------------

# Heuristic industry_fit for the 10 hand-crafted templates
# Based on their tone_fit and occasion_fit characteristics
_EXISTING_INDUSTRY_HEURISTIC: dict[str, list[str]] = {
    "poster_default": ["food", "retail", "general"],
    "poster_bold_knockout": ["retail", "tech", "general"],
    "poster_center_stage": ["food", "fashion", "general"],
    "poster_diagonal_cut": ["retail", "fashion", "general"],
    "poster_editorial_split": ["tech", "education", "general"],
    "poster_floating_card": ["fashion", "education", "general"],
    "poster_minimal_clean": ["tech", "fashion", "general"],
    "poster_promo_grid": ["food", "retail", "general"],
    "poster_road_safety": ["education", "general"],
    "poster_stacked_type": ["education", "tech", "general"],
}


def tag_existing_templates(template_dir: Path) -> int:
    """Set canonical industry_fit on existing (hand-crafted) template metas.

    Overwrites any non-canonical industry_fit values with canonical ones.
    Uses heuristic mapping based on template characteristics.

    Args:
        template_dir: Directory containing template HTML and meta YAML files.

    Returns:
        Number of templates updated.
    """
    updated = 0
    for meta_path in sorted(template_dir.glob("*_meta.yaml")):
        name = meta_path.stem.replace("_meta", "")
        # Skip D4-derived templates
        if name.startswith("poster_d4_"):
            continue

        with meta_path.open() as fh:
            meta = yaml.safe_load(fh)

        if meta is None:
            meta = {}

        # Check if current industry_fit uses only canonical values
        current = set(meta.get("industry_fit", []))
        if current and current <= CANONICAL_INDUSTRIES:
            continue

        industry_fit = _EXISTING_INDUSTRY_HEURISTIC.get(
            name, ["general"]
        )
        meta["industry_fit"] = industry_fit

        with meta_path.open("w") as fh:
            yaml.dump(meta, fh, default_flow_style=False, sort_keys=False)

        updated += 1
        logger.info("Tagged %s with industry_fit=%s", name, industry_fit)

    return updated


# ---------------------------------------------------------------------------
# Default tone/occasion inference from layout structure
# ---------------------------------------------------------------------------


def _infer_tone_fit(density: str, hero_style: str) -> list[str]:
    """Infer tone_fit tags from structural properties."""
    tones: list[str] = []

    if density == "minimal":
        tones.extend(["premium", "elegant"])
    elif density == "dense":
        tones.extend(["bold", "urgent"])
    else:
        tones.extend(["professional", "versatile"])

    if hero_style == "full_bleed":
        tones.append("dramatic")
    elif hero_style == "split":
        tones.append("balanced")
    elif hero_style == "contained":
        tones.append("structured")

    return tones


def _infer_occasion_fit(density: str, cta_prominence: str) -> list[str]:
    """Infer occasion_fit tags from structural properties."""
    occasions: list[str] = []

    if cta_prominence == "high":
        occasions.extend(["sale", "product_launch"])
    elif cta_prominence == "medium":
        occasions.extend(["announcement", "event"])
    else:
        occasions.extend(["awareness", "corporate"])

    if density == "dense":
        occasions.append("promo")
    elif density == "minimal":
        occasions.append("announcement")

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for occ in occasions:
        if occ not in seen:
            seen.add(occ)
            result.append(occ)
    return result


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    d4_dir: Path = D4_DIR,
    d5_dir: Path = D5_DIR,
    output_dir: Path = TEMPLATE_DIR,
    n_clusters: int = 28,
    random_state: int = 42,
) -> list[ArchetypeInfo]:
    """Run the full clustering pipeline and generate templates.

    1. Load D4 parquets, parse annotations
    2. Extract grid-based layout features
    3. K-means clustering
    4. For each centroid: extract zones, generate HTML + meta YAML
    5. Cross-reference D5 for industry_fit
    6. Tag existing templates

    Args:
        d4_dir: Path to D4 CGL parquet directory.
        d5_dir: Path to D5 Magazine Layout parquet directory.
        output_dir: Directory to write generated templates.
        n_clusters: Number of K-means clusters.
        random_state: Seed for reproducibility.

    Returns:
        List of generated ArchetypeInfo objects.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load D4 data
    logger.info("Loading D4 parquets from %s", d4_dir)
    parquet_files = sorted(d4_dir.glob("*.parquet"))
    layouts: list[LayoutImage] = []

    for pq_file in parquet_files:
        df = pd.read_parquet(pq_file, columns=["image_id", "width", "height", "annotations"])
        for _, row in df.iterrows():
            layout = _parse_d4_row(row)
            if layout is not None and len(layout.elements) >= 2:
                layouts.append(layout)

    logger.info("Parsed %d layouts with >= 2 elements", len(layouts))

    # Step 2: Extract features
    logger.info("Extracting layout features (grid %dx%d, %d channels)", GRID_ROWS, GRID_COLS, NUM_CHANNELS)
    features = extract_layout_features(layouts)
    logger.info("Feature matrix: %s", features.shape)

    # Step 3: Cluster
    logger.info("Clustering into %d groups", n_clusters)
    _cluster_labels, centroids, cluster_sizes = cluster_layouts(
        features, n_clusters=n_clusters, random_state=random_state
    )
    logger.info("Cluster sizes: %s", cluster_sizes)

    # Step 4: Load D5 for industry tagging
    d5_features = np.zeros((0, FEATURE_DIM), dtype=np.float64)
    d5_industries: list[str] = []
    if d5_dir.is_dir() and any(d5_dir.glob("*.parquet")):
        logger.info("Loading D5 magazine layouts for industry tagging")
        d5_features = _load_d5_layout_features(d5_dir)
        d5_industries = _load_d5_industries(d5_dir)
        logger.info("Loaded %d D5 layouts across %d industries", len(d5_industries), len(set(d5_industries)))

    # Step 5: Compute industry fit
    industry_fits = compute_industry_fit(
        centroids, d5_features, d5_industries, top_n=min(100, max(10, len(d5_industries) // 10))
    )

    # Step 6: Generate templates
    archetypes: list[ArchetypeInfo] = []
    used_names: set[str] = set()

    for cluster_idx in range(n_clusters):
        centroid = centroids[cluster_idx]
        zone_grid = _centroid_to_zone_grid(centroid, threshold=0.3)
        zones = _merge_adjacent_cells(zone_grid)

        # Skip clusters with fewer than 2 zones
        if len(zones) < 2:
            # Lower threshold and retry
            zone_grid = _centroid_to_zone_grid(centroid, threshold=0.15)
            zones = _merge_adjacent_cells(zone_grid)

        if len(zones) < 2:
            # Create minimal fallback zones
            zones = [
                TemplateZone("underlay", 1, 5, 1, 7, 0.5),
                TemplateZone("text", 5, 9, 1, 7, 0.5),
            ]

        supported_slots = _zones_to_slots(zones)
        density = _compute_density(zones)
        cta_prominence = _compute_cta_prominence(zones)
        hero_style = _compute_hero_style(zones)

        name = _generate_archetype_name(cluster_idx, zones, density)

        # Ensure unique name
        if name in used_names:
            name = f"{name}_v2"
        used_names.add(name)

        tone_fit = _infer_tone_fit(density, hero_style)
        occasion_fit = _infer_occasion_fit(density, cta_prominence)
        industry_fit = industry_fits[cluster_idx] if cluster_idx < len(industry_fits) else ["general"]

        archetype = ArchetypeInfo(
            name=name,
            zones=zones,
            density=density,
            cta_prominence=cta_prominence,
            supported_slots=supported_slots,
            tone_fit=tone_fit,
            occasion_fit=occasion_fit,
            industry_fit=industry_fit,
            hero_style=hero_style,
            cluster_size=cluster_sizes[cluster_idx],
        )
        archetypes.append(archetype)

        # Write HTML
        html_content = generate_template_html(archetype)
        html_path = output_dir / f"poster_d4_{name}.html"
        html_path.write_text(html_content)

        # Write meta YAML
        meta = {
            "density": archetype.density,
            "tone_fit": archetype.tone_fit,
            "occasion_fit": archetype.occasion_fit,
            "cta_prominence": archetype.cta_prominence,
            "hero_style": archetype.hero_style,
            "supported_slots": archetype.supported_slots,
            "industry_fit": archetype.industry_fit,
            "cluster_size": archetype.cluster_size,
        }
        meta_path = output_dir / f"poster_d4_{name}_meta.yaml"
        with meta_path.open("w") as fh:
            yaml.dump(meta, fh, default_flow_style=False, sort_keys=False)

        logger.info(
            "Generated template: poster_d4_%s (zones=%d, slots=%s, industry=%s)",
            name, len(zones), supported_slots, industry_fit,
        )

    # Step 7: Tag existing templates
    updated_count = tag_existing_templates(output_dir)
    logger.info("Tagged %d existing templates with industry_fit", updated_count)

    return archetypes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cluster D4 CGL layouts into HTML poster template archetypes"
    )
    parser.add_argument(
        "--k", type=int, default=28, help="Number of clusters (default: 28)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(TEMPLATE_DIR),
        help="Output directory for generated templates",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed (default: 42)"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    archetypes = run_pipeline(
        d4_dir=D4_DIR,
        d5_dir=D5_DIR,
        output_dir=Path(args.output),
        n_clusters=args.k,
        random_state=args.seed,
    )

    logger.info("Done. Generated %d template archetypes.", len(archetypes))


if __name__ == "__main__":
    main()
