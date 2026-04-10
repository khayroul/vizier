"""Tests for D12 PosterIQ data loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.load_posteriq import (
    ABPairRecord,
    RatingRecord,
    StyleRecord,
    load_ab_pairs,
    load_ratings,
    load_styles,
)

DATASET_DIR = Path(__file__).resolve().parent.parent / "datasets" / "D12_PosterIQ"


@pytest.fixture()
def ratings() -> list[RatingRecord]:
    return load_ratings(dataset_dir=DATASET_DIR)


@pytest.fixture()
def ab_pairs() -> list[ABPairRecord]:
    return load_ab_pairs(dataset_dir=DATASET_DIR)


@pytest.fixture()
def styles() -> list[StyleRecord]:
    return load_styles(dataset_dir=DATASET_DIR)


class TestRatings:
    def test_posteriq_loader_returns_valid_records(
        self, ratings: list[RatingRecord]
    ) -> None:
        """At least 219 ratings, all with score in 1-10."""
        assert len(ratings) >= 219
        for record in ratings:
            assert 1.0 <= record.score <= 10.0, (
                f"Score {record.score} out of range for {record.name}"
            )

    def test_rating_record_fields(self, ratings: list[RatingRecord]) -> None:
        """Each RatingRecord has name, path, score fields."""
        for record in ratings:
            assert isinstance(record.name, str)
            assert len(record.name) > 0
            assert isinstance(record.path, str)
            assert len(record.path) > 0
            assert isinstance(record.score, float)

    def test_rating_record_has_prompt(self, ratings: list[RatingRecord]) -> None:
        """Each RatingRecord carries the evaluation prompt."""
        for record in ratings:
            assert isinstance(record.prompt, str)
            assert len(record.prompt) > 0


class TestABPairs:
    def test_ab_pairs_count(self, ab_pairs: list[ABPairRecord]) -> None:
        """Total A/B pairs >= 1231 across all four source files."""
        assert len(ab_pairs) >= 1231

    def test_ab_pair_type_field(self, ab_pairs: list[ABPairRecord]) -> None:
        """Each ABPairRecord has a pair_type drawn from the four source files."""
        valid_types = {
            "layout_comparison",
            "font_matching",
            "font_effect",
            "font_effect_2",
        }
        for record in ab_pairs:
            assert record.pair_type in valid_types, (
                f"Unexpected pair_type: {record.pair_type}"
            )

    def test_ab_pair_type_distribution(self, ab_pairs: list[ABPairRecord]) -> None:
        """Verify expected counts per pair type."""
        counts: dict[str, int] = {}
        for record in ab_pairs:
            counts[record.pair_type] = counts.get(record.pair_type, 0) + 1
        assert counts.get("layout_comparison", 0) >= 256
        assert counts.get("font_matching", 0) >= 400
        assert counts.get("font_effect", 0) >= 450
        assert counts.get("font_effect_2", 0) >= 125

    def test_ab_pair_record_fields(self, ab_pairs: list[ABPairRecord]) -> None:
        """Each ABPairRecord has name, path, ground_truth, pair_type."""
        for record in ab_pairs:
            assert isinstance(record.name, str)
            assert len(record.name) > 0
            assert isinstance(record.path, str)
            assert len(record.path) > 0
            assert isinstance(record.ground_truth, str)
            assert len(record.ground_truth) > 0
            assert isinstance(record.pair_type, str)


class TestStyles:
    def test_style_categories_count(self, styles: list[StyleRecord]) -> None:
        """At least 17 unique style categories."""
        categories = {record.category for record in styles}
        assert len(categories) >= 17

    def test_style_record_count(self, styles: list[StyleRecord]) -> None:
        """At least 256 style records."""
        assert len(styles) >= 256

    def test_style_record_fields(self, styles: list[StyleRecord]) -> None:
        """Each StyleRecord has name, path, category fields."""
        for record in styles:
            assert isinstance(record.name, str)
            assert len(record.name) > 0
            assert isinstance(record.path, str)
            assert len(record.path) > 0
            assert isinstance(record.category, str)
            assert len(record.category) > 0
