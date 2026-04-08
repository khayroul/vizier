"""Ebook production pipeline (S21).

Outline → section expansion → rolling context → assembly (PDF + EPUB).
WorkflowExecutor drives this via ebook_production.yaml.

GPT-5.4-mini for ALL text tasks (anti-drift #54).
"""

from __future__ import annotations

import logging
from pathlib import Path

from contracts.context import Checkpoint, RollingContext, TrackedEntity
from contracts.publishing import StyleLock
from contracts.trace import TraceCollector
from tools.publish import assemble_ebook
from utils.call_llm import call_llm

logger = logging.getLogger(__name__)


def _expand_outline(
    *,
    outline: list[dict[str, str]],
    metadata: dict[str, str],
    collector: TraceCollector,
) -> list[dict[str, str | int]]:
    """Expand each outline item into a section brief with word target and key points."""
    briefs: list[dict[str, str | int]] = []

    for idx, item in enumerate(outline):
        with collector.step(f"expand_outline_{idx}") as trace:
            result = call_llm(
                stable_prefix=[{"role": "system", "content": (
                    "You are a professional ebook editor. "
                    f"Book title: '{metadata.get('title', 'Untitled')}'. "
                    f"Language: {metadata.get('language', 'ms')}."
                )}],
                variable_suffix=[{"role": "user", "content": (
                    f"Expand this outline item into a section brief.\n"
                    f"Section {idx + 1}: "
                    f"{item.get('title', '')} \u2014 "
                    f"{item.get('summary', '')}\n\n"
                    "Provide:\n"
                    "1. Target word count (1000-3000)\n"
                    "2. Key points to cover (3-5 bullet points)\n"
                    "3. Tone guidance\n"
                    "Output as plain text."
                )}],
                model="gpt-5.4-mini",
                temperature=0.5,
                max_tokens=512,
            )
            trace.input_tokens = result["input_tokens"]
            trace.output_tokens = result["output_tokens"]
            trace.cost_usd = result["cost_usd"]

            briefs.append({
                "title": item.get("title", f"Section {idx + 1}"),
                "summary": item.get("summary", ""),
                "brief": result["content"],
                "word_target": item.get("word_target", 2000),
            })

    return briefs


def _generate_section(
    *,
    section_idx: int,
    brief: dict[str, str | int],
    metadata: dict[str, str],
    rolling_context: RollingContext,
    collector: TraceCollector,
) -> str:
    """Generate and self-refine a single section.

    Self-refine: generate → critique (claims, coherence, alignment) → revise.
    """
    ctx_window = rolling_context.get_context_window()
    title = str(brief["title"])
    section_brief = str(brief.get("brief", ""))

    system_prompt = (
        f"You are writing an ebook in {metadata.get('language', 'ms')}. "
        f"Title: '{metadata.get('title', 'Untitled')}'. "
        f"Author: {metadata.get('author', 'Vizier')}."
    )

    # Generate
    with collector.step(f"generate_section_{section_idx}") as trace:
        result = call_llm(
            stable_prefix=[{"role": "system", "content": system_prompt}],
            variable_suffix=[{"role": "user", "content": (
                f"Write section '{title}'.\n"
                f"Brief: {section_brief}\n"
                f"Word target: {brief.get('word_target', 2000)} words.\n"
                f"Prior sections context: {ctx_window}\n\n"
                "Write ONLY the section content. No meta-commentary."
            )}],
            model="gpt-5.4-mini",
            temperature=0.7,
            max_tokens=4096,
        )
        draft = result["content"]
        trace.input_tokens = result["input_tokens"]
        trace.output_tokens = result["output_tokens"]
        trace.cost_usd = result["cost_usd"]

    # Critique: claims consistency, coherence, executive summary alignment
    with collector.step(f"critique_section_{section_idx}") as trace:
        critique_result = call_llm(
            stable_prefix=[{"role": "system", "content": "You are an ebook editor."}],
            variable_suffix=[{"role": "user", "content": (
                f"Critique section '{title}'.\n"
                f"Section text:\n{draft}\n\n"
                f"Prior sections context: {ctx_window}\n\n"
                "Check for:\n"
                "1. Claims consistency with prior sections\n"
                "2. Coherence and flow\n"
                "3. Alignment with overall book structure\n"
                "List specific issues."
            )}],
            model="gpt-5.4-mini",
            temperature=0.3,
            max_tokens=512,
        )
        critique = critique_result["content"]
        trace.input_tokens = critique_result["input_tokens"]
        trace.output_tokens = critique_result["output_tokens"]
        trace.cost_usd = critique_result["cost_usd"]

    # Revise
    with collector.step(f"revise_section_{section_idx}") as trace:
        revise_result = call_llm(
            stable_prefix=[{"role": "system", "content": system_prompt}],
            variable_suffix=[{"role": "user", "content": (
                f"Revise section '{title}' based on the critique.\n"
                f"Original:\n{draft}\n\n"
                f"Critique:\n{critique}\n\n"
                "Output ONLY the revised section content."
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


def produce_ebook(
    *,
    outline: list[dict[str, str]],
    metadata: dict[str, str],
    style_lock: StyleLock | None = None,
    job_id: str,
    output_dir: Path,
) -> dict[str, Path | object]:
    """Produce an ebook: outline → sections → assembly (PDF + EPUB).

    Args:
        outline: List of dicts with title and summary keys.
        metadata: Dict with title, author, language keys.
        style_lock: Optional StyleLock for cover generation.
        job_id: Production job ID.
        output_dir: Root output directory.

    Returns:
        Dict with pdf, epub paths, sections list, and trace.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    collector = TraceCollector(job_id=job_id)

    # Initialise RollingContext for ebook
    rolling_context = RollingContext(
        context_type="document",
        recent_window=2,
        medium_scope="section",
        checkpoints=[
            Checkpoint(description="introduction_complete", target_step=1),
            Checkpoint(
                description="body_complete",
                target_step=max(1, len(outline) - 1),
            ),
            Checkpoint(description="conclusion_complete", target_step=len(outline)),
        ],
    )

    # Step 1: Expand outline
    briefs = _expand_outline(outline=outline, metadata=metadata, collector=collector)

    # Step 2: Generate each section with rolling context
    sections: list[dict[str, str]] = []
    for idx, brief in enumerate(briefs):
        text = _generate_section(
            section_idx=idx,
            brief=brief,
            metadata=metadata,
            rolling_context=rolling_context,
            collector=collector,
        )
        sections.append({"title": str(brief["title"]), "content": text})

        # Update rolling context
        rolling_context.update(f"Section '{brief['title']}': {text[:500]}")

        # Extract entities (numbers, claims mentioned)
        for entity_type in ("claim", "number"):
            entity = TrackedEntity(
                entity_id=f"section_{idx}_{entity_type}",
                entity_type=entity_type,
                name=f"{brief['title']}_{entity_type}",
                state={"section": idx, "status": "established"},
                introduced_at=rolling_context.current_step - 1,
                last_updated_at=rolling_context.current_step - 1,
            )
            rolling_context.add_entity(entity)

        # Check checkpoint alignment
        if idx == 0:
            _mark_checkpoint(rolling_context, "introduction_complete")
        elif idx == len(briefs) - 2:
            _mark_checkpoint(rolling_context, "body_complete")
        elif idx == len(briefs) - 1:
            _mark_checkpoint(rolling_context, "conclusion_complete")

        # Compress medium tier if needed
        if rolling_context.medium:
            rolling_context.compress()

    # Step 3: Assembly
    colors = None
    fonts = None
    if style_lock:
        colors = {
            "primary": style_lock.palette[0] if style_lock.palette else "#264653",
            "secondary": (
                style_lock.palette[1]
                if len(style_lock.palette) > 1
                else "#FFF8F0"
            ),
        }
        fonts = {"body": style_lock.typography}

    with collector.step("assemble_ebook") as trace:
        result = assemble_ebook(
            sections=sections,
            title=metadata.get("title", "Untitled"),
            author=metadata.get("author", "Vizier"),
            output_dir=output_dir,
            colors=colors,
            fonts=fonts,
        )
        trace.proof = {"format": "ebook", "sections": len(sections)}

    production_trace = collector.finalise()
    logger.info(
        "Ebook production complete: %d sections, cost $%.4f",
        len(sections), production_trace.total_cost_usd,
    )

    return {
        "pdf": result["pdf"],
        "epub": result["epub"],
        "sections": sections,
        "trace": production_trace,
    }


def _mark_checkpoint(ctx: RollingContext, description: str) -> None:
    """Mark a checkpoint as reached."""
    for cp in ctx.checkpoints:
        if cp.description == description and not cp.reached:
            cp.reached = True
            cp.reached_at = ctx.current_step - 1
            logger.info("Checkpoint '%s' reached", description)
            break
