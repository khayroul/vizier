"""Full children's book production pipeline (S21).

Orchestrates: text generation → illustration → rolling context → assembly.
WorkflowExecutor drives this via childrens_book_production.yaml.

GPT-5.4-mini for ALL text tasks (anti-drift #54).
Illustrations text-free — Typst overlays text (anti-drift #49).
Illustration prompts from illustration_shows, NOT page text (§42.3).
"""

from __future__ import annotations

import logging
from pathlib import Path

from contracts.context import Checkpoint, RollingContext
from contracts.publishing import (
    CharacterBible,
    NarrativeScaffold,
    PageScaffold,
    StoryBible,
    StyleLock,
)
from contracts.trace import TraceCollector
from tools.illustrate import IllustrationPipeline
from tools.publish import (
    assemble_childrens_book_pdf,
    assemble_ebook,
    update_rolling_context_for_page,
)
from utils.call_llm import call_llm

logger = logging.getLogger(__name__)

# Page turn effect → text ending guidance
_TURN_GUIDANCE: dict[str, str] = {
    "continuation": (
        "End mid-tension \u2014 the reader should feel "
        "compelled to turn the page."
    ),
    "reveal": (
        "Start with a payoff or surprise that resolves "
        "the previous page's tension."
    ),
    "pause": "Provide a gentle landing — a moment of calm or reflection.",
    "climax": "This is the peak emotional moment. Maximum intensity.",
}


def _generate_page_text(
    *,
    page: PageScaffold,
    story_bible: StoryBible,
    rolling_context: RollingContext,
    persona_path: str = "",
    collector: TraceCollector,
) -> str:
    """Generate and self-refine text for a single page.

    Self-refine: generate → critique → revise (1 cycle).
    Verifies word count within ±20% of page.word_target.
    """
    turn_guidance = _TURN_GUIDANCE.get(page.page_turn_effect.value, "")
    ctx_window = rolling_context.get_context_window()

    # Build prompt
    system_prompt = (
        f"You are writing a children's book in {story_bible.language} "
        f"for age group {story_bible.target_age.value}. "
        f"Title: '{story_bible.title}'. "
        f"Theme: {story_bible.thematic_constraints.lesson}. "
        "Avoid: "
        f"{', '.join(story_bible.thematic_constraints.avoid) or 'nothing specific'}."
    )
    if persona_path:
        system_prompt += f"\nPersona: {persona_path}"

    user_prompt = (
        f"Write page {page.page} text.\n"
        f"Emotional beat: {page.emotional_beat}\n"
        f"Word target: {page.word_target} words (±20%)\n"
        f"Characters present: {', '.join(page.characters_present)}\n"
        f"Checkpoint progress: {page.checkpoint_progress}\n"
        f"Page turn effect: {page.page_turn_effect.value}. {turn_guidance}\n"
        f"\nPrior context: {ctx_window}\n"
        f"\nWrite ONLY the story text for this page. No meta-commentary."
    )

    # Step 1: Generate
    with collector.step(f"generate_text_page_{page.page}") as trace:
        result = call_llm(
            stable_prefix=[{"role": "system", "content": system_prompt}],
            variable_suffix=[{"role": "user", "content": user_prompt}],
            model="gpt-5.4-mini",
            temperature=0.8,
            max_tokens=512,
        )
        draft = result["content"]
        trace.input_tokens = result["input_tokens"]
        trace.output_tokens = result["output_tokens"]
        trace.cost_usd = result["cost_usd"]

    # Step 2: Self-refine — critique
    with collector.step(f"critique_page_{page.page}") as trace:
        critique_result = call_llm(
            stable_prefix=[{
                "role": "system",
                "content": (
                    "You are an editor for "
                    "children's literature."
                ),
            }],
            variable_suffix=[{"role": "user", "content": (
                "Critique this children's book page text "
                f"for age {story_bible.target_age.value}.\n"
                f"Word target: {page.word_target} (±20%). "
                f"Emotional beat: {page.emotional_beat}.\n"
                f"Text:\n{draft}\n\n"
                "List specific issues: word count, "
                "age-appropriateness, emotional tone, flow."
            )}],
            model="gpt-5.4-mini",
            temperature=0.3,
            max_tokens=256,
        )
        critique = critique_result["content"]
        trace.input_tokens = critique_result["input_tokens"]
        trace.output_tokens = critique_result["output_tokens"]
        trace.cost_usd = critique_result["cost_usd"]

    # Step 3: Self-refine — revise
    with collector.step(f"revise_page_{page.page}") as trace:
        revise_result = call_llm(
            stable_prefix=[{"role": "system", "content": system_prompt}],
            variable_suffix=[{"role": "user", "content": (
                f"Revise this page {page.page} text based on the critique.\n"
                f"Original:\n{draft}\n\n"
                f"Critique:\n{critique}\n\n"
                f"Word target: {page.word_target} (±20%). "
                "Output ONLY the revised story text."
            )}],
            model="gpt-5.4-mini",
            temperature=0.7,
            max_tokens=512,
        )
        revised = revise_result["content"]
        trace.input_tokens = revise_result["input_tokens"]
        trace.output_tokens = revise_result["output_tokens"]
        trace.cost_usd = revise_result["cost_usd"]

    # Verify word count (log warning if outside ±20%)
    word_count = len(revised.split())
    low = int(page.word_target * 0.8)
    high = int(page.word_target * 1.2)
    if word_count < low or word_count > high:
        logger.warning(
            "Page %d word count %d outside target range [%d, %d]",
            page.page, word_count, low, high,
        )

    return revised


def produce_book(
    *,
    scaffold: NarrativeScaffold,
    characters: list[CharacterBible],
    story_bible: StoryBible,
    style_lock: StyleLock,
    job_id: str,
    pipeline: IllustrationPipeline,
    output_dir: Path,
    persona_path: str = "",
) -> dict[str, object]:
    """Produce a complete children's book: text + illustrations + PDF + EPUB.

    Full automated pipeline after creative workshop completes.

    Args:
        scaffold: NarrativeScaffold with per-page structure.
        characters: CharacterBibles for all characters.
        story_bible: Story world and thematic constraints.
        style_lock: Locked visual parameters.
        job_id: Production job ID.
        pipeline: Initialised IllustrationPipeline with references set.
        output_dir: Root output directory.
        persona_path: Optional path to persona config.

    Returns:
        Dict with pdf, epub paths, page_texts list, and trace.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    collector = TraceCollector(job_id=job_id)

    # Initialise RollingContext for children's book
    rolling_context = RollingContext(
        context_type="narrative",
        recent_window=scaffold.page_count,  # all pages for children's book
        medium_scope="not_needed",
        checkpoints=[
            Checkpoint(description="character_introduced", target_step=2),
            Checkpoint(description="conflict_established", target_step=4),
            Checkpoint(
                description="resolution_reached",
                target_step=scaffold.page_count - 1,
            ),
        ],
    )

    # Add immutable facts from story bible
    for fact in story_bible.immutable_facts:
        rolling_context.add_immutable_fact(fact, source="story_bible")

    page_texts: list[str] = []
    images: list[Path] = []

    for page in scaffold.pages:
        # 1. Generate text
        text = _generate_page_text(
            page=page,
            story_bible=story_bible,
            rolling_context=rolling_context,
            persona_path=persona_path,
            collector=collector,
        )
        page_texts.append(text)

        # 2. Illustrate (uses illustration_shows, NOT page text — anti-drift #49)
        img_path = pipeline.illustrate_page(
            page=page,
            character_bibles=characters,
            output_dir=output_dir / "pages",
        )
        images.append(img_path)

        # 3. Post-page update — rolling context
        visual_summary = (
            f"[Visual: {page.composition_guide.camera}, "
            f"{page.composition_guide.character_position}, "
            f"{page.composition_guide.colour_temperature}] "
            f"{page.illustration_shows}"
        )
        update_rolling_context_for_page(
            ctx=rolling_context,
            page=page,
            page_text=f"{text} | {visual_summary}",
        )

        # 4. Check checkpoint progress
        if page.checkpoint_progress:
            for cp in rolling_context.checkpoints:
                if cp.description == page.checkpoint_progress and not cp.reached:
                    cp.reached = True
                    cp.reached_at = rolling_context.current_step - 1
                    logger.info(
                        "Checkpoint '%s' reached at page %d",
                        cp.description, page.page,
                    )

    # Assembly
    with collector.step("assemble_pdf") as trace:
        pdf_path = assemble_childrens_book_pdf(
            images=images,
            scaffold=scaffold,
            style_lock=style_lock,
            title=story_bible.title,
            author="Vizier",
            output_dir=output_dir,
            page_texts=page_texts,
        )
        trace.proof = {"format": "pdf", "pages": len(images)}

    with collector.step("assemble_epub") as trace:
        chapters = [
            {"title": f"Page {idx + 1}", "content": text}
            for idx, text in enumerate(page_texts)
        ]
        epub_result = assemble_ebook(
            sections=chapters,
            title=story_bible.title,
            author="Vizier",
            output_dir=output_dir,
        )
        epub_path = epub_result["epub"]
        trace.proof = {"format": "epub", "sections": len(chapters)}

    production_trace = collector.finalise()
    logger.info(
        "Book production complete: %d pages, cost $%.4f",
        len(page_texts), production_trace.total_cost_usd,
    )

    return {
        "pdf": pdf_path,
        "epub": epub_path,
        "page_texts": page_texts,
        "trace": production_trace,
    }
