"""Serial fiction production pipeline (S21).

Episode-level production with cross-episode rolling context and entity
registry persistence. WorkflowExecutor drives this via
serial_fiction_production.yaml.

GPT-5.4-mini for ALL text tasks (anti-drift #54).
Entity state transitions are append-only — prior states never deleted.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from contracts.context import Checkpoint, RollingContext, TrackedEntity
from contracts.publishing import CharacterBible, StoryBible, StyleLock
from contracts.trace import TraceCollector
from utils.call_llm import call_llm

logger = logging.getLogger(__name__)

_SERIES_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "series"


# ---------------------------------------------------------------------------
# Series context persistence
# ---------------------------------------------------------------------------


def load_series_context(series_id: str) -> RollingContext:
    """Load persisted RollingContext from prior episodes.

    If no prior context (episode 1), returns a fresh RollingContext
    configured for serial fiction.

    Args:
        series_id: Unique series identifier.

    Returns:
        RollingContext loaded from disk or freshly initialised.
    """
    ctx_path = _SERIES_DATA_DIR / series_id / "rolling_context.json"
    if ctx_path.exists():
        data = json.loads(ctx_path.read_text(encoding="utf-8"))
        ctx = RollingContext.model_validate(data)
        logger.info(
            "Loaded series context for '%s' (step %d)",
            series_id, ctx.current_step,
        )
        return ctx

    logger.info("No prior context for series '%s' — starting fresh", series_id)
    return RollingContext(
        context_type="narrative",
        recent_window=3,
        medium_scope="arc",
        checkpoints=[
            Checkpoint(description="episode_arc_complete"),
            Checkpoint(description="series_arc_milestone"),
            Checkpoint(description="character_development_beat"),
        ],
    )


def save_series_context(series_id: str, context: RollingContext) -> None:
    """Persist RollingContext after episode completes.

    Args:
        series_id: Unique series identifier.
        context: RollingContext to persist.
    """
    series_dir = _SERIES_DATA_DIR / series_id
    series_dir.mkdir(parents=True, exist_ok=True)
    ctx_path = series_dir / "rolling_context.json"
    ctx_path.write_text(
        context.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.info(
        "Saved series context for '%s' (step %d)",
        series_id, context.current_step,
    )


def _load_entity_registry(series_id: str) -> list[dict[str, object]]:
    """Load entity registry from prior episodes (append-only)."""
    registry_path = _SERIES_DATA_DIR / series_id / "entity_registry.json"
    if registry_path.exists():
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    return []


def _save_entity_registry(
    series_id: str,
    entities: list[TrackedEntity],
    episode_number: int,
) -> None:
    """Append current episode entities to the registry.

    Entity state transitions are append-only: prior states are never
    deleted, just superseded by newer entries.
    """
    registry = _load_entity_registry(series_id)

    for entity in entities:
        registry.append({
            "entity_id": entity.entity_id,
            "entity_type": entity.entity_type,
            "name": entity.name,
            "state": entity.state,
            "episode": episode_number,
            "step": entity.last_updated_at,
        })

    series_dir = _SERIES_DATA_DIR / series_id
    series_dir.mkdir(parents=True, exist_ok=True)
    registry_path = series_dir / "entity_registry.json"
    registry_path.write_text(
        json.dumps(registry, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info(
        "Saved %d entities for series '%s' episode %d",
        len(entities), series_id, episode_number,
    )


def _inject_prior_entities(
    context: RollingContext,
    series_id: str,
) -> None:
    """Load prior episode entities and inject into fresh RollingContext."""
    registry = _load_entity_registry(series_id)
    if not registry:
        return

    # Get latest state per entity_id (last entry wins — append-only)
    latest: dict[str, dict[str, object]] = {}
    for entry in registry:
        eid = str(entry.get("entity_id", ""))
        if eid:
            latest[eid] = entry

    for eid, entry in latest.items():
        raw_state = entry.get("state", {})
        state = raw_state if isinstance(raw_state, dict) else {}
        entity = TrackedEntity(
            entity_id=eid,
            entity_type=str(entry.get("entity_type", "character")),
            name=str(entry.get("name", eid)),
            state={k: v for k, v in state.items()},
            introduced_at=0,
            last_updated_at=0,
        )
        context.add_entity(entity)

    logger.info("Injected %d prior entities into context", len(latest))


# ---------------------------------------------------------------------------
# Episode production
# ---------------------------------------------------------------------------


def _generate_episode_outline(
    *,
    episode_number: int,
    premise: str,
    story_bible: StoryBible,
    series_context: RollingContext,
    collector: TraceCollector,
) -> list[dict[str, str]]:
    """Generate chapter outline for this episode aligned with series arc."""
    ctx_window = series_context.get_context_window()

    with collector.step(f"episode_{episode_number}_outline") as trace:
        result = call_llm(
            stable_prefix=[{"role": "system", "content": (
                "You are planning episode "
                f"{episode_number} of a serial fiction "
                f"series. Title: '{story_bible.title}'. "
                f"Language: {story_bible.language}. "
                f"Age group: {story_bible.target_age.value}. "
                f"Theme: {story_bible.thematic_constraints.lesson}."
            )}],
            variable_suffix=[{"role": "user", "content": (
                f"Episode premise: {premise}\n"
                f"Series context so far: {ctx_window}\n\n"
                "Generate a 3-5 chapter outline for this episode. "
                "For each chapter provide: chapter_number, "
                "title, summary (2-3 sentences). "
                "Output as JSON array."
            )}],
            model="gpt-5.4-mini",
            temperature=0.7,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        trace.input_tokens = result["input_tokens"]
        trace.output_tokens = result["output_tokens"]
        trace.cost_usd = result["cost_usd"]

    # Parse outline
    try:
        parsed = json.loads(result["content"])
        chapters = parsed if isinstance(parsed, list) else parsed.get("chapters", [])
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Failed to parse episode outline as JSON, using fallback")
        chapters = [
            {"chapter_number": 1, "title": "Chapter 1", "summary": premise},
            {"chapter_number": 2, "title": "Chapter 2", "summary": "Development"},
            {"chapter_number": 3, "title": "Chapter 3", "summary": "Resolution"},
        ]

    return chapters


def _generate_chapter(
    *,
    episode_number: int,
    chapter: dict[str, str],
    chapter_idx: int,
    story_bible: StoryBible,
    characters: list[CharacterBible],
    series_context: RollingContext,
    collector: TraceCollector,
) -> str:
    """Generate and self-refine a single chapter.

    3-pass critique: narrative coherence, character consistency, arc progression.
    """
    ctx_window = series_context.get_context_window()
    char_names = ", ".join(c.name for c in characters)

    system_prompt = (
        f"You are a fiction author writing episode {episode_number}, "
        f"chapter {chapter_idx + 1} of '{story_bible.title}'. "
        f"Language: {story_bible.language}. Age: {story_bible.target_age.value}. "
        f"Characters: {char_names}."
    )

    # Generate
    with collector.step(f"ep{episode_number}_ch{chapter_idx}_generate") as trace:
        result = call_llm(
            stable_prefix=[{"role": "system", "content": system_prompt}],
            variable_suffix=[{"role": "user", "content": (
                f"Chapter: {chapter.get('title', '')}\n"
                f"Summary: {chapter.get('summary', '')}\n"
                f"Series context: {ctx_window}\n\n"
                "Write the full chapter text (800-1500 words). "
                "Output ONLY the story text."
            )}],
            model="gpt-5.4-mini",
            temperature=0.8,
            max_tokens=4096,
        )
        draft = result["content"]
        trace.input_tokens = result["input_tokens"]
        trace.output_tokens = result["output_tokens"]
        trace.cost_usd = result["cost_usd"]

    # 3-pass critique: narrative coherence, character consistency, arc progression
    critique_dims = [
        ("narrative_coherence", "Does the chapter flow logically? Any plot holes?"),
        (
            "character_consistency",
            f"Are characters ({char_names}) consistent "
            "with prior episodes?",
        ),
        ("arc_progression", "Does this chapter advance the episode and series arcs?"),
    ]

    critique_combined = ""
    for dim_name, dim_question in critique_dims:
        step_name = (
            f"ep{episode_number}_ch{chapter_idx}"
            f"_critique_{dim_name}"
        )
        with collector.step(step_name) as trace:
            crit_result = call_llm(
                stable_prefix=[{
                    "role": "system",
                    "content": "You are a fiction editor.",
                }],
                variable_suffix=[{"role": "user", "content": (
                    f"Critique this chapter for {dim_name}:\n{dim_question}\n\n"
                    f"Chapter text:\n{draft}\n\n"
                    f"Series context: {ctx_window}\n\n"
                    "List specific issues."
                )}],
                model="gpt-5.4-mini",
                temperature=0.3,
                max_tokens=256,
            )
            critique_combined += f"\n{dim_name}: {crit_result['content']}"
            trace.input_tokens = crit_result["input_tokens"]
            trace.output_tokens = crit_result["output_tokens"]
            trace.cost_usd = crit_result["cost_usd"]

    # Revise
    with collector.step(f"ep{episode_number}_ch{chapter_idx}_revise") as trace:
        revise_result = call_llm(
            stable_prefix=[{"role": "system", "content": system_prompt}],
            variable_suffix=[{"role": "user", "content": (
                f"Revise this chapter based on the critique.\n"
                f"Original:\n{draft}\n\n"
                f"Critique:\n{critique_combined}\n\n"
                "Output ONLY the revised chapter text."
            )}],
            model="gpt-5.4-mini",
            temperature=0.7,
            max_tokens=4096,
        )
        revised = revise_result["content"]
        trace.input_tokens = revise_result["input_tokens"]
        trace.output_tokens = revise_result["output_tokens"]
        trace.cost_usd = revise_result["cost_usd"]

    return revised


def produce_episode(
    *,
    episode_number: int,
    premise: str,
    series_id: str,
    characters: list[CharacterBible],
    story_bible: StoryBible,
    style_lock: StyleLock,
    job_id: str,
    output_dir: Path,
) -> dict[str, object]:
    """Produce a single episode of serial fiction.

    Loads series context, generates chapter outline, produces chapters
    with rolling context, persists entity registry and series context.

    Args:
        episode_number: Episode number (1-based).
        premise: Episode premise (1-2 sentences).
        series_id: Unique series identifier for persistence.
        characters: CharacterBibles for series characters.
        story_bible: Series-level story bible.
        style_lock: Locked visual parameters.
        job_id: Production job ID.
        output_dir: Root output directory.

    Returns:
        Dict with chapters, episode_text, trace, and context state.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    collector = TraceCollector(job_id=job_id)

    # Load series context (or fresh for episode 1)
    series_context = load_series_context(series_id)

    # Inject prior episode entities
    _inject_prior_entities(series_context, series_id)

    # Add immutable facts from story bible
    for fact in story_bible.immutable_facts:
        existing = [f.fact for f in series_context.immutable_facts]
        if fact not in existing:
            series_context.add_immutable_fact(fact, source="story_bible")

    # Reset episode-level checkpoints
    for cp in series_context.checkpoints:
        if cp.description in ("episode_arc_complete", "character_development_beat"):
            cp.reached = False
            cp.reached_at = None

    # Step 1: Episode outline
    chapter_outline = _generate_episode_outline(
        episode_number=episode_number,
        premise=premise,
        story_bible=story_bible,
        series_context=series_context,
        collector=collector,
    )

    # Step 2: Generate chapters with rolling context
    chapter_texts: list[str] = []
    for idx, chapter in enumerate(chapter_outline):
        text = _generate_chapter(
            episode_number=episode_number,
            chapter=chapter,
            chapter_idx=idx,
            story_bible=story_bible,
            characters=characters,
            series_context=series_context,
            collector=collector,
        )
        chapter_texts.append(text)

        # Update rolling context after each chapter
        series_context.update(
            f"Episode {episode_number}, Chapter {idx + 1} "
            f"({chapter.get('title', '')}): {text[:500]}"
        )

        # Track character entities with state changes
        for character in characters:
            entity = TrackedEntity(
                entity_id=character.character_id,
                entity_type="character",
                name=character.name,
                state={
                    "episode": episode_number,
                    "chapter": idx + 1,
                    "status": "active",
                },
                introduced_at=series_context.current_step - 1,
                last_updated_at=series_context.current_step - 1,
            )
            series_context.add_entity(entity)

    # Mark episode-level checkpoints
    for cp in series_context.checkpoints:
        if cp.description == "episode_arc_complete" and not cp.reached:
            cp.reached = True
            cp.reached_at = series_context.current_step - 1
        if cp.description == "character_development_beat" and not cp.reached:
            cp.reached = True
            cp.reached_at = series_context.current_step - 1

    # Persist
    save_series_context(series_id, series_context)
    _save_entity_registry(series_id, series_context.entities, episode_number)

    production_trace = collector.finalise()
    episode_text = "\n\n---\n\n".join(chapter_texts)

    logger.info(
        "Episode %d complete: %d chapters, cost $%.4f",
        episode_number, len(chapter_texts), production_trace.total_cost_usd,
    )

    return {
        "episode_number": episode_number,
        "chapters": [
            {"title": ch.get("title", f"Chapter {i + 1}"), "content": text}
            for i, (ch, text) in enumerate(zip(chapter_outline, chapter_texts))
        ],
        "episode_text": episode_text,
        "trace": production_trace,
        "entities": [e.model_dump() for e in series_context.entities],
        "checkpoints": [cp.model_dump() for cp in series_context.checkpoints],
    }
