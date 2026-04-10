"""Tests for operator exemplar ingestion pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.ingest_operator_exemplars import (
    ExemplarRecord,
    build_tag_prompt,
    parse_tag_response,
)


class TestExemplarRecord:
    """ExemplarRecord validates correctly."""

    def test_valid_record(self) -> None:
        record = ExemplarRecord(
            path=Path("test.png"),
            tags={"industry": "food", "mood": "festive", "occasion": "raya"},
            nima_score=6.2,
            critique_scores={"text_visibility": 4.0, "design_layout": 3.8},
            source="operator_curated",
            artifact_family="poster",
        )
        assert record.nima_score == 6.2
        assert record.tags["industry"] == "food"
        assert record.source == "operator_curated"

    def test_record_to_dict(self) -> None:
        record = ExemplarRecord(
            path=Path("posters/raya_sale.png"),
            tags={"industry": "food", "mood": "festive"},
            nima_score=7.1,
            critique_scores={"text_visibility": 4.5},
            source="operator_curated",
            artifact_family="poster",
        )
        as_dict = record.to_dict()
        assert as_dict["path"] == "posters/raya_sale.png"
        assert as_dict["nima_score"] == 7.1
        assert isinstance(as_dict["tags"], dict)

    def test_record_defaults(self) -> None:
        record = ExemplarRecord(
            path=Path("test.png"),
            tags={},
            nima_score=5.0,
            critique_scores={},
            source="operator_curated",
            artifact_family="poster",
        )
        assert record.clip_embedding is None


class TestTagging:
    """Tag prompt construction and response parsing."""

    def test_build_tag_prompt_is_string(self) -> None:
        prompt = build_tag_prompt()
        assert isinstance(prompt, str)
        assert "industry" in prompt
        assert "mood" in prompt

    def test_parse_valid_response(self) -> None:
        raw = json.dumps({
            "industry": "food",
            "mood": "festive",
            "occasion": "hari_raya",
            "density": "moderate",
            "cta_style": "high",
            "colour_palette": "warm_gold",
            "layout_archetype": "hero_left",
        })
        tags = parse_tag_response(raw)
        assert tags["industry"] == "food"
        assert tags["mood"] == "festive"
        assert tags["occasion"] == "hari_raya"

    def test_parse_malformed_response_returns_empty(self) -> None:
        tags = parse_tag_response("not json at all")
        assert tags == {}

    def test_parse_response_with_markdown_fence(self) -> None:
        raw = '```json\n{"industry": "food", "mood": "warm"}\n```'
        tags = parse_tag_response(raw)
        assert tags["industry"] == "food"
