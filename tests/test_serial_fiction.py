"""Tests for the serial fiction production pipeline (S21)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from contracts.context import RollingContext, TrackedEntity
from contracts.publishing import (
    AgeGroup,
    CharacterBible,
    ClothingDescription,
    FaceDetails,
    HairDetails,
    PhysicalDescription,
    StyleLock,
    StyleNotes,
    StoryBible,
    TextPlacementStrategy,
    ThematicConstraints,
    WorldDescription,
    SensoryDetails,
)
from tools.serial_fiction import (
    load_series_context,
    produce_episode,
    save_series_context,
    _load_entity_registry,
    _save_entity_registry,
    _inject_prior_entities,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

_CALL_COUNT = 0


def _mock_call_llm(**kwargs: Any) -> dict[str, Any]:
    """Return mock LLM response. For outline calls, return JSON."""
    global _CALL_COUNT
    _CALL_COUNT += 1

    response_format = kwargs.get("response_format")
    if response_format and isinstance(response_format, dict):
        content = json.dumps({
            "chapters": [
                {"chapter_number": 1, "title": "The Beginning", "summary": "Story starts"},
                {"chapter_number": 2, "title": "The Middle", "summary": "Action rises"},
                {"chapter_number": 3, "title": "The End", "summary": "Resolution"},
            ]
        })
    else:
        content = "Ahmad berlari di sepanjang pantai, angin meniup rambutnya."

    return {
        "content": content,
        "model": "gpt-5.4-mini",
        "input_tokens": 200,
        "output_tokens": 100,
        "cost_usd": 0.0002,
    }


def _sample_character(char_id: str = "ahmad", name: str = "Ahmad") -> CharacterBible:
    return CharacterBible(
        character_id=char_id,
        name=name,
        role="protagonist",
        physical=PhysicalDescription(
            age=12,
            ethnicity="Malay",
            skin_tone="#8D6E63",
            height="medium",
            build="athletic",
            face=FaceDetails(shape="oval", eyes="brown", nose="small", mouth="determined"),
            hair=HairDetails(style="short black", colour="#1A1A1A"),
        ),
        clothing=ClothingDescription(default="school uniform"),
        style_notes=StyleNotes(
            art_style="anime-inspired",
            line_weight="medium",
            colour_palette="vibrant",
        ),
    )


def _sample_story_bible() -> StoryBible:
    return StoryBible(
        title="Pengembaraan Ahmad",
        target_age=AgeGroup.age_8_10,
        language="ms",
        world=WorldDescription(
            setting="Coastal Malay village",
            sensory=SensoryDetails(visual="Blue ocean, white sand, coconut palms"),
        ),
        thematic_constraints=ThematicConstraints(
            lesson="Courage and perseverance",
            avoid=["violence", "horror"],
        ),
        immutable_facts=["Ahmad lives in Kampung Pantai", "Ahmad is 12 years old"],
    )


def _sample_style_lock() -> StyleLock:
    return StyleLock(
        art_style="anime-inspired watercolour",
        palette=["#1A237E", "#FFF8E1", "#FF6F00"],
        typography="Noto Sans",
        text_placement_strategy=TextPlacementStrategy.text_always_below,
    )


# ---------------------------------------------------------------------------
# Tests: Series context persistence
# ---------------------------------------------------------------------------


class TestSeriesContextPersistence:
    """Load and save series context to/from disk."""

    def test_fresh_series_returns_empty_context(self, tmp_path: Path) -> None:
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            ctx = load_series_context("new_series")
        assert ctx.context_type == "narrative"
        assert ctx.current_step == 0
        assert len(ctx.recent) == 0

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            ctx = RollingContext(
                context_type="narrative",
                recent_window=3,
                medium_scope="arc",
            )
            ctx.update("Chapter 1 content")
            ctx.update("Chapter 2 content")
            save_series_context("test_series", ctx)

            loaded = load_series_context("test_series")
        assert loaded.current_step == 2
        assert len(loaded.recent) == 2

    def test_load_preserves_entities(self, tmp_path: Path) -> None:
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            ctx = RollingContext(
                context_type="narrative",
                recent_window=3,
                medium_scope="arc",
            )
            entity = TrackedEntity(
                entity_id="ahmad",
                entity_type="character",
                name="Ahmad",
                state={"mood": "confident"},
                introduced_at=0,
                last_updated_at=0,
            )
            ctx.add_entity(entity)
            save_series_context("test_series", ctx)

            loaded = load_series_context("test_series")
        assert len(loaded.entities) == 1
        assert loaded.entities[0].entity_id == "ahmad"
        assert loaded.entities[0].state["mood"] == "confident"


class TestEntityRegistry:
    """Entity registry persistence (append-only)."""

    def test_empty_registry_on_new_series(self, tmp_path: Path) -> None:
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            registry = _load_entity_registry("new_series")
        assert registry == []

    def test_save_and_load_entities(self, tmp_path: Path) -> None:
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            entities = [
                TrackedEntity(
                    entity_id="ahmad",
                    entity_type="character",
                    name="Ahmad",
                    state={"mood": "confident"},
                    introduced_at=0,
                    last_updated_at=1,
                ),
            ]
            _save_entity_registry("test_series", entities, episode_number=1)
            registry = _load_entity_registry("test_series")
        assert len(registry) == 1
        assert registry[0]["entity_id"] == "ahmad"

    def test_append_only_across_episodes(self, tmp_path: Path) -> None:
        """Entity state from ep1 preserved when ep2 appends."""
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            ep1_entities = [
                TrackedEntity(
                    entity_id="ahmad",
                    entity_type="character",
                    name="Ahmad",
                    state={"mood": "confident"},
                    introduced_at=0,
                    last_updated_at=0,
                ),
            ]
            _save_entity_registry("test_series", ep1_entities, episode_number=1)

            ep2_entities = [
                TrackedEntity(
                    entity_id="ahmad",
                    entity_type="character",
                    name="Ahmad",
                    state={"mood": "doubting"},
                    introduced_at=0,
                    last_updated_at=3,
                ),
                TrackedEntity(
                    entity_id="siti",
                    entity_type="character",
                    name="Siti",
                    state={"mood": "supportive"},
                    introduced_at=3,
                    last_updated_at=3,
                ),
            ]
            _save_entity_registry("test_series", ep2_entities, episode_number=2)
            registry = _load_entity_registry("test_series")

        # Both ep1 and ep2 entries present (append-only)
        assert len(registry) == 3
        ahmad_entries = [e for e in registry if e["entity_id"] == "ahmad"]
        assert len(ahmad_entries) == 2  # ep1 confident + ep2 doubting

    def test_inject_prior_entities_uses_latest(self, tmp_path: Path) -> None:
        """_inject_prior_entities uses latest state per entity_id."""
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            ep1_entities = [
                TrackedEntity(
                    entity_id="ahmad",
                    entity_type="character",
                    name="Ahmad",
                    state={"mood": "confident"},
                    introduced_at=0,
                    last_updated_at=0,
                ),
            ]
            _save_entity_registry("test_series", ep1_entities, episode_number=1)

            ep2_entities = [
                TrackedEntity(
                    entity_id="ahmad",
                    entity_type="character",
                    name="Ahmad",
                    state={"mood": "doubting"},
                    introduced_at=0,
                    last_updated_at=3,
                ),
            ]
            _save_entity_registry("test_series", ep2_entities, episode_number=2)

            ctx = RollingContext(
                context_type="narrative",
                recent_window=3,
                medium_scope="arc",
            )
            _inject_prior_entities(ctx, "test_series")

        # Latest state for ahmad should be "doubting" (ep2 supersedes ep1)
        assert len(ctx.entities) == 1
        assert ctx.entities[0].state["mood"] == "doubting"


# ---------------------------------------------------------------------------
# Tests: Episode production
# ---------------------------------------------------------------------------


class TestProduceEpisode:
    """Full serial fiction episode production."""

    @patch("tools.serial_fiction.call_llm", side_effect=_mock_call_llm)
    def test_episode_produces_chapters(
        self, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            result: dict[str, Any] = produce_episode(
                episode_number=1,
                premise="Ahmad discovers a mysterious map",
                series_id="test_series",
                characters=[_sample_character()],
                story_bible=_sample_story_bible(),
                style_lock=_sample_style_lock(),
                job_id="test-ep1",
                output_dir=tmp_path / "output",
            )
        assert len(result["chapters"]) == 3

    @patch("tools.serial_fiction.call_llm", side_effect=_mock_call_llm)
    def test_entity_persists_between_episodes(
        self, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        """Entity from episode 1 persists to episode 2."""
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            produce_episode(
                episode_number=1,
                premise="Ahmad discovers a map",
                series_id="test_persist",
                characters=[_sample_character()],
                story_bible=_sample_story_bible(),
                style_lock=_sample_style_lock(),
                job_id="test-ep1",
                output_dir=tmp_path / "ep1",
            )

            result2: dict[str, Any] = produce_episode(
                episode_number=2,
                premise="Ahmad follows the map",
                series_id="test_persist",
                characters=[_sample_character()],
                story_bible=_sample_story_bible(),
                style_lock=_sample_style_lock(),
                job_id="test-ep2",
                output_dir=tmp_path / "ep2",
            )

        # Ahmad should be tracked in episode 2's entities
        entity_ids = [e["entity_id"] for e in result2["entities"]]
        assert "ahmad" in entity_ids

    @patch("tools.serial_fiction.call_llm", side_effect=_mock_call_llm)
    def test_new_character_in_ep2_persists_to_ep3(
        self, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        """New character introduced in ep2 appears in ep3 context."""
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            # Episode 1: only Ahmad
            produce_episode(
                episode_number=1,
                premise="Ahmad discovers a map",
                series_id="test_new_char",
                characters=[_sample_character()],
                story_bible=_sample_story_bible(),
                style_lock=_sample_style_lock(),
                job_id="test-ep1",
                output_dir=tmp_path / "ep1",
            )

            # Episode 2: Ahmad + Siti
            siti = _sample_character("siti", "Siti")
            produce_episode(
                episode_number=2,
                premise="Ahmad meets Siti",
                series_id="test_new_char",
                characters=[_sample_character(), siti],
                story_bible=_sample_story_bible(),
                style_lock=_sample_style_lock(),
                job_id="test-ep2",
                output_dir=tmp_path / "ep2",
            )

            # Episode 3: check Siti persists
            result3: dict[str, Any] = produce_episode(
                episode_number=3,
                premise="Ahmad and Siti explore together",
                series_id="test_new_char",
                characters=[_sample_character(), siti],
                story_bible=_sample_story_bible(),
                style_lock=_sample_style_lock(),
                job_id="test-ep3",
                output_dir=tmp_path / "ep3",
            )

        entity_ids = [e["entity_id"] for e in result3["entities"]]
        assert "siti" in entity_ids
        assert "ahmad" in entity_ids

    @patch("tools.serial_fiction.call_llm", side_effect=_mock_call_llm)
    def test_character_state_evolves(
        self, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        """Character states evolve across episodes."""
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            produce_episode(
                episode_number=1,
                premise="Ahmad is confident",
                series_id="test_evolve",
                characters=[_sample_character()],
                story_bible=_sample_story_bible(),
                style_lock=_sample_style_lock(),
                job_id="test-ep1",
                output_dir=tmp_path / "ep1",
            )

            result2: dict[str, Any] = produce_episode(
                episode_number=2,
                premise="Ahmad faces doubt",
                series_id="test_evolve",
                characters=[_sample_character()],
                story_bible=_sample_story_bible(),
                style_lock=_sample_style_lock(),
                job_id="test-ep2",
                output_dir=tmp_path / "ep2",
            )

        # Ahmad should have episode=2 in latest state
        ahmad = [e for e in result2["entities"] if e["entity_id"] == "ahmad"]
        assert len(ahmad) > 0
        # At least one entry has episode 2
        assert any(e["state"]["episode"] == 2 for e in ahmad)

    @patch("tools.serial_fiction.call_llm", side_effect=_mock_call_llm)
    def test_series_checkpoint_after_episode(
        self, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        """Series-level checkpoints checked after each episode."""
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            result: dict[str, Any] = produce_episode(
                episode_number=1,
                premise="Ahmad discovers a map",
                series_id="test_checkpoints",
                characters=[_sample_character()],
                story_bible=_sample_story_bible(),
                style_lock=_sample_style_lock(),
                job_id="test-ep1",
                output_dir=tmp_path / "output",
            )

        checkpoints = result["checkpoints"]
        ep_arc = [cp for cp in checkpoints if cp["description"] == "episode_arc_complete"]
        assert len(ep_arc) == 1
        assert ep_arc[0]["reached"] is True

    @patch("tools.serial_fiction.call_llm", side_effect=_mock_call_llm)
    def test_immutable_facts_not_duplicated(
        self, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        """Immutable facts from story bible added once, not duplicated across episodes."""
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            produce_episode(
                episode_number=1,
                premise="Episode 1",
                series_id="test_facts",
                characters=[_sample_character()],
                story_bible=_sample_story_bible(),
                style_lock=_sample_style_lock(),
                job_id="test-ep1",
                output_dir=tmp_path / "ep1",
            )

            produce_episode(
                episode_number=2,
                premise="Episode 2",
                series_id="test_facts",
                characters=[_sample_character()],
                story_bible=_sample_story_bible(),
                style_lock=_sample_style_lock(),
                job_id="test-ep2",
                output_dir=tmp_path / "ep2",
            )

            ctx = load_series_context("test_facts")

        # Story bible has 2 immutable facts — they should appear exactly once each
        fact_texts = [f.fact for f in ctx.immutable_facts]
        assert fact_texts.count("Ahmad lives in Kampung Pantai") == 1
        assert fact_texts.count("Ahmad is 12 years old") == 1

    @patch("tools.serial_fiction.call_llm", side_effect=_mock_call_llm)
    def test_3_episodes_sequential(
        self, mock_llm: MagicMock, tmp_path: Path,
    ) -> None:
        """3 test episodes generated sequentially with evolving context."""
        with patch("tools.serial_fiction._SERIES_DATA_DIR", tmp_path):
            for ep_num in range(1, 4):
                result: dict[str, Any] = produce_episode(
                    episode_number=ep_num,
                    premise=f"Episode {ep_num} premise",
                    series_id="test_sequential",
                    characters=[_sample_character()],
                    story_bible=_sample_story_bible(),
                    style_lock=_sample_style_lock(),
                    job_id=f"test-ep{ep_num}",
                    output_dir=tmp_path / f"ep{ep_num}",
                )
                assert len(result["chapters"]) == 3

            # After 3 episodes, context should have accumulated
            ctx = load_series_context("test_sequential")
        assert ctx.current_step > 0
