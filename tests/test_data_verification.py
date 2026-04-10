"""Phase 0: Verify dataset foundations (D12 images + D4 schema).

These tests gate all downstream calibration and template work.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DATASETS = Path(__file__).resolve().parent.parent / "datasets"


class TestD12Verification:
    """Verify D12 PosterIQ images are accessible after unpacking."""

    def test_d12_overall_rating_exists(self) -> None:
        """overall_rating.json exists and has >=219 rated posters."""
        ratings_path = DATASETS / "D12_PosterIQ" / "und_task" / "overall_rating.json"
        assert ratings_path.exists(), "overall_rating.json not found"

        ratings = json.loads(ratings_path.read_text())
        assert len(ratings) >= 219, f"Expected >=219 ratings, got {len(ratings)}"

        # Every record has a path and a ground-truth score
        for record in ratings[:5]:
            assert "path" in record, f"Missing 'path' in record: {record}"
            assert "gt" in record, f"Missing 'gt' in record: {record}"
            assert 1.0 <= record["gt"] <= 10.0, f"Score out of range: {record['gt']}"

    def test_d12_poster_images_accessible(self) -> None:
        """At least 200 poster images exist on disk."""
        ratings_path = DATASETS / "D12_PosterIQ" / "und_task" / "overall_rating.json"
        ratings = json.loads(ratings_path.read_text())

        accessible = 0
        d12_root = DATASETS / "D12_PosterIQ"
        for record in ratings:
            # Images may be at the JSON path or under data/ prefix
            img_path = d12_root / record["path"]
            if not img_path.exists():
                img_path = d12_root / "data" / record["path"]
            if img_path.exists() and img_path.stat().st_size > 0:
                accessible += 1

        assert accessible >= 200, (
            f"Only {accessible}/{len(ratings)} images accessible. "
            "Run: cd datasets/D12_PosterIQ && unzip -o data.zip"
        )

    def test_d12_ab_pairs_exist(self) -> None:
        """layout_comprison.json has >=256 A/B preference pairs."""
        pairs_path = DATASETS / "D12_PosterIQ" / "und_task" / "layout_comprison.json"
        assert pairs_path.exists(), "layout_comprison.json not found"

        pairs = json.loads(pairs_path.read_text())
        assert len(pairs) >= 256, f"Expected >=256 pairs, got {len(pairs)}"
        assert pairs[0]["gt"] in ("A", "B"), f"Unexpected gt value: {pairs[0]['gt']}"

    def test_d12_style_categories(self) -> None:
        """style_understanding.json has >=17 unique style categories."""
        styles_path = DATASETS / "D12_PosterIQ" / "und_task" / "style_understanding.json"
        assert styles_path.exists(), "style_understanding.json not found"

        styles = json.loads(styles_path.read_text())
        unique_styles = {record["gt"] for record in styles}
        assert len(unique_styles) >= 17, (
            f"Expected >=17 styles, got {len(unique_styles)}: {unique_styles}"
        )


class TestD4Verification:
    """Verify D4 CGL parquets have bbox annotations for layout clustering."""

    def test_d4_parquet_count(self) -> None:
        """At least 14 train parquets exist."""
        parquet_dir = DATASETS / "D4_CGL_Dataset_v2" / "data"
        parquets = sorted(parquet_dir.glob("train-*.parquet"))
        assert len(parquets) >= 14, f"Expected >=14 parquets, got {len(parquets)}"

    def test_d4_has_bbox_annotations(self) -> None:
        """First D4 parquet has COCO-format bbox annotations."""
        parquet_dir = DATASETS / "D4_CGL_Dataset_v2" / "data"
        first_parquet = sorted(parquet_dir.glob("train-*.parquet"))[0]
        df = pd.read_parquet(first_parquet)

        assert len(df) > 0, "First parquet is empty"
        assert "annotations" in df.columns, f"No 'annotations' column. Columns: {list(df.columns)}"

        # Check annotation structure
        ann = df.iloc[0]["annotations"]
        assert "bbox" in ann, f"No 'bbox' in annotations. Keys: {list(ann.keys())}"
        assert "category" in ann, f"No 'category' in annotations"

        # Verify bbox is numpy array with [x, y, w, h] format
        bbox = ann["bbox"]
        assert isinstance(bbox, np.ndarray), f"bbox type: {type(bbox)}, expected ndarray"
        assert len(bbox) >= 1, "No bounding boxes found"
        assert len(bbox[0]) == 4, f"Expected [x,y,w,h], got {len(bbox[0])} values"

    def test_d4_has_image_dimensions(self) -> None:
        """D4 records have width and height for normalization."""
        parquet_dir = DATASETS / "D4_CGL_Dataset_v2" / "data"
        first_parquet = sorted(parquet_dir.glob("train-*.parquet"))[0]
        df = pd.read_parquet(first_parquet)

        assert "width" in df.columns, "No 'width' column"
        assert "height" in df.columns, "No 'height' column"
        assert df.iloc[0]["width"] > 0, "Width must be positive"
        assert df.iloc[0]["height"] > 0, "Height must be positive"

    def test_d4_total_row_count(self) -> None:
        """D4 has at least 60,000 layouts across all parquets."""
        parquet_dir = DATASETS / "D4_CGL_Dataset_v2" / "data"
        parquets = sorted(parquet_dir.glob("train-*.parquet"))

        total = sum(len(pd.read_parquet(p, columns=["image_id"])) for p in parquets)
        assert total >= 60000, f"Expected >=60,000 rows, got {total}"
