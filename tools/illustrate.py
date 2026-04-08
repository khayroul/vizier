"""Stateful sequential illustration pipeline for publishing (S15b).

Unlike tools/image.py (fire-and-forget for posters/marketing), this
maintains page-to-page state: previous page image feeds into next
generation, character references are tracked, consistency is verified
via CLIP after each page, and anchor frame resets prevent cumulative drift.

Illustrations are ALWAYS text-free (anti-drift #49).
Visual brief expansion ALWAYS runs before generation (anti-drift #25).
All text tasks on GPT-5.4-mini (anti-drift #54).
"""
from __future__ import annotations

import logging
from pathlib import Path

from contracts.context import RollingContext
from contracts.publishing import (
    CharacterBible,
    NarrativeScaffold,
    PageScaffold,
    StyleLock,
)
from contracts.trace import TraceCollector
from tools.image import expand_brief, generate_image
from tools.publish import update_rolling_context_for_page
from utils.storage import upload_bytes, upload_to_fal

logger = logging.getLogger(__name__)

# Image generation cost per page (Kontext)
_KONTEXT_COST_USD = 0.04
_FLUX_DEV_COST_USD = 0.025
_ANCHOR_INTERVAL = 8


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def build_illustration_prompt(
    *,
    page: PageScaffold,
    style_lock: StyleLock,
    character_bibles: list[CharacterBible],
) -> str:
    """Build a structured illustration prompt from scaffold + style data.

    Composes: illustration_shows + composition_guide + style_lock
    (art_style + palette) + character style notes + text-free instruction.

    The result is intended to be passed through ``expand_brief()`` before
    being sent to ``generate_image()``.

    Args:
        page: PageScaffold with illustration_shows and composition_guide.
        style_lock: Locked visual parameters.
        character_bibles: Characters present on this page.

    Returns:
        Raw brief string for expansion.
    """
    guide = page.composition_guide
    parts: list[str] = [
        f"Scene: {page.illustration_shows}",
        f"Camera: {guide.camera}. Character position: {guide.character_position}.",
        (
            f"Background: {guide.background_detail} detail. "
            f"Colour temperature: {guide.colour_temperature}."
        ),
        f"Art style: {style_lock.art_style}.",
        f"Colour palette: {', '.join(style_lock.palette)}.",
    ]

    # Character descriptions for characters present on this page
    present_ids = set(page.characters_present)
    for bible in character_bibles:
        if bible.character_id in present_ids:
            phys = bible.physical
            parts.append(
                f"Character '{bible.name}': {phys.ethnicity}, age {phys.age}, "
                f"{phys.build} build, {phys.hair.style} hair ({phys.hair.colour}), "
                f"skin tone {phys.skin_tone}. "
                f"Wearing {bible.clothing.default}. "
                f"Style: {bible.style_notes.art_style}, "
                f"{bible.style_notes.line_weight} lines."
            )
            if bible.style_notes.always:
                parts.append(f"Always include: {', '.join(bible.style_notes.always)}.")
            if bible.style_notes.never:
                parts.append(f"Never include: {', '.join(bible.style_notes.never)}.")

    # Text-free enforcement (anti-drift #49)
    parts.append(
        "IMPORTANT: Do not include any text, words, letters, numbers, or writing "
        "in the illustration. The image must be completely text-free."
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# IllustrationPipeline
# ---------------------------------------------------------------------------


class IllustrationPipeline:
    """Stateful pipeline for sequential illustration with consistency tracking.

    State per project:
        character_references — CharacterBible ID -> curated reference image paths
        character_ref_embeddings — cached CLIP embeddings for references
        style_lock — locked art direction from creative workshop
        previous_page_image — fal-hosted URL fed to Kontext as image_url
        anchor_image_url — curated reference URL, reset target every 8 pages
        consistency_scores — running CLIP scores per page
        collector — TraceCollector for production observability
    """

    def __init__(
        self,
        *,
        style_lock: StyleLock,
        job_id: str,
    ) -> None:
        self.style_lock = style_lock
        self.job_id = job_id
        self.character_references: dict[str, list[Path]] = {}
        self.character_ref_embeddings: dict[str, list[list[float]]] = {}
        self.previous_page_image: str | None = None  # fal-hosted URL
        self.anchor_image_url: str | None = None
        self.pages_since_anchor: int = 0
        self.total_pages: int = 0
        self.consistency_scores: list[float] = []
        self.collector = TraceCollector(job_id=job_id)

    # ------------------------------------------------------------------
    # Anchor status
    # ------------------------------------------------------------------

    def get_anchor_status(self) -> dict[str, int | float | str]:
        """Return current anchor state for operator visibility."""
        avg = (
            sum(self.consistency_scores) / len(self.consistency_scores)
            if self.consistency_scores
            else 0.0
        )
        return {
            "pages_since_anchor": self.pages_since_anchor,
            "total_pages": self.total_pages,
            "avg_consistency": round(avg, 4),
            "anchor_url": self.anchor_image_url or "",
        }

    # ------------------------------------------------------------------
    # Reference embedding cache
    # ------------------------------------------------------------------

    def _cache_reference_embeddings(self) -> None:
        """Compute and cache CLIP embeddings for all character references.

        Called once after references are set. Avoids re-encoding 10+
        reference images on every page verification.
        """
        from utils.retrieval import encode_image

        self.character_ref_embeddings = {}
        for char_id, ref_paths in self.character_references.items():
            embeddings: list[list[float]] = []
            for ref_path in ref_paths:
                emb = encode_image(ref_path.read_bytes())
                embeddings.append(emb)
            self.character_ref_embeddings[char_id] = embeddings
            logger.info(
                "Cached %d reference embeddings for character '%s'",
                len(embeddings), char_id,
            )

    # ------------------------------------------------------------------
    # Consistency verification
    # ------------------------------------------------------------------

    def verify_consistency(
        self,
        *,
        generated_bytes: bytes,
        characters_present: list[str],
        character_position: str = "centre",
        threshold: float = 0.75,
    ) -> tuple[bool, float]:
        """Verify character consistency via position-aware CLIP similarity.

        Crops the generated image based on character_position, encodes via
        CLIP, and compares against cached reference embeddings. Returns the
        minimum score across all characters present.

        Args:
            generated_bytes: Raw bytes of the generated illustration.
            characters_present: Character IDs to verify.
            character_position: From composition_guide.character_position.
            threshold: Minimum similarity to pass (default 0.75).

        Returns:
            Tuple of (passed, min_similarity_score).
        """
        from utils.image_processing import crop_character_region
        from utils.retrieval import encode_image

        cropped = crop_character_region(generated_bytes, character_position)
        gen_embedding = encode_image(cropped)

        min_score = 1.0
        has_refs = False
        for char_id in characters_present:
            ref_embeddings = self.character_ref_embeddings.get(char_id, [])
            if not ref_embeddings:
                logger.warning("No reference embeddings for character '%s'", char_id)
                continue

            has_refs = True
            # Best match among reference images for this character
            scores = [
                sum(a * b for a, b in zip(gen_embedding, ref_emb))
                for ref_emb in ref_embeddings
            ]
            char_score = max(scores)
            min_score = min(min_score, char_score)

        if not has_refs:
            min_score = 0.0

        passed = min_score >= threshold
        logger.info(
            "Consistency check: %.4f (threshold=%.2f, %s) for characters %s",
            min_score, threshold, "PASS" if passed else "FAIL", characters_present,
        )
        return passed, min_score

    # ------------------------------------------------------------------
    # Character reference generation
    # ------------------------------------------------------------------

    def generate_character_references(
        self,
        *,
        character_bible: CharacterBible,
        output_dir: Path,
        count: int = 10,
    ) -> list[Path]:
        """Generate candidate reference images from CharacterBible.

        Operator selects best 2-3 as curated references. This method
        generates the candidates. Uses fal-ai/flux/dev (not Kontext)
        since no reference image exists yet.

        Args:
            character_bible: Character physical description + style notes.
            output_dir: Directory to save generated images.
            count: Number of candidates to generate (default 10).

        Returns:
            List of paths to generated candidate images.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        phys = character_bible.physical
        style = character_bible.style_notes

        raw_brief = (
            f"Character portrait of '{character_bible.name}': "
            f"{phys.ethnicity}, age {phys.age}, {phys.build} build, "
            f"{phys.height} height, {phys.hair.style} hair ({phys.hair.colour}), "
            f"skin tone {phys.skin_tone}, "
            f"{phys.face.shape} face, {phys.face.eyes} eyes, "
            f"{phys.face.nose} nose, {phys.face.mouth} mouth. "
            f"Wearing {character_bible.clothing.default}. "
            f"Art style: {style.art_style}. Line weight: {style.line_weight}. "
            f"Colour palette: {style.colour_palette}. "
            f"Colour palette hex: {', '.join(self.style_lock.palette)}. "
            "Full body, front view, neutral background. "
            "IMPORTANT: Do not include any text, words, letters, or writing."
        )

        paths: list[Path] = []
        for idx in range(count):
            ref_step = (
                f"generate_ref_"
                f"{character_bible.character_id}_{idx}"
            )
            with self.collector.step(ref_step) as trace:
                expanded = expand_brief(raw_brief)
                prompt = expanded.get("composition", raw_brief)

                image_bytes = generate_image(
                    prompt=prompt,
                    model="fal-ai/flux/dev",
                    guidance_scale=3.5,
                )

                # Save locally
                filename = f"ref_{character_bible.character_id}_{idx:02d}.jpg"
                local_path = output_dir / filename
                local_path.write_bytes(image_bytes)

                # Upload to MinIO
                object_name = f"references/{self.job_id}/{filename}"
                upload_bytes(object_name, image_bytes, content_type="image/jpeg")

                paths.append(local_path)
                trace.model = "fal-ai/flux/dev"
                trace.cost_usd = _FLUX_DEV_COST_USD
                trace.proof = {
                    "character": character_bible.character_id,
                    "candidate": idx,
                }

        logger.info(
            "Generated %d reference candidates for '%s'",
            len(paths), character_bible.name,
        )
        return paths

    def set_character_references(
        self,
        character_id: str,
        reference_paths: list[Path],
    ) -> None:
        """Set operator-curated references for a character and cache embeddings.

        Called after operator selects best 2-3 from generated candidates.
        Also uploads the first reference to fal.ai as the anchor image.

        Args:
            character_id: Character ID from CharacterBible.
            reference_paths: Operator-selected reference image paths.
        """
        self.character_references[character_id] = reference_paths
        self._cache_reference_embeddings()

        # Set anchor from first reference (front view preferred)
        if not self.anchor_image_url and reference_paths:
            self.anchor_image_url = upload_to_fal(
                reference_paths[0].read_bytes(), content_type="image/jpeg",
            )
            logger.info("Anchor image set from %s", reference_paths[0].name)

    # ------------------------------------------------------------------
    # Page illustration
    # ------------------------------------------------------------------

    def illustrate_page(
        self,
        *,
        page: PageScaffold,
        character_bibles: list[CharacterBible],
        output_dir: Path,
        max_retries: int = 2,
        consistency_threshold: float = 0.75,
    ) -> Path:
        """Generate a text-free illustration for a single page.

        Builds prompt from illustration_shows (NEVER page text), expands
        via GPT-5.4-mini, generates via Kontext (feeding previous page),
        verifies via CLIP, retries on low consistency.

        Re-anchors from curated reference every 8 pages to prevent
        cumulative drift.

        Args:
            page: PageScaffold with illustration_shows and composition_guide.
            character_bibles: Characters in this project.
            output_dir: Directory to save generated images.
            max_retries: Max retries on low CLIP score (default 2).
            consistency_threshold: CLIP threshold (default 0.75).

        Returns:
            Path to the generated illustration on disk.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        page_num = page.page

        # Determine image_url: anchor reset on pages divisible by 8, else previous
        if page_num > 1 and page_num % _ANCHOR_INTERVAL == 0:
            image_url = self.anchor_image_url
            self.pages_since_anchor = 0
            logger.info("Anchor reset on page %d", page_num)
        elif page_num > 1 and self.previous_page_image:
            image_url = self.previous_page_image
        else:
            image_url = self.anchor_image_url  # first page uses anchor if available

        # Build and expand prompt (anti-drift #25: expand ALWAYS before generation)
        raw_brief = build_illustration_prompt(
            page=page,
            style_lock=self.style_lock,
            character_bibles=character_bibles,
        )

        # Inject LoRA trigger words if configured
        present_ids = set(page.characters_present)
        for bible in character_bibles:
            if bible.character_id in present_ids and bible.lora:
                raw_brief = f"{bible.lora.trigger_word} {raw_brief}"

        image_bytes = b""
        best_score = 0.0

        for attempt in range(max_retries + 1):
            step_name = (
                f"illustrate_page_{page_num}"
                f"_attempt_{attempt}"
            )
            with self.collector.step(step_name) as trace:
                expanded = expand_brief(raw_brief)
                prompt = expanded.get("composition", raw_brief)

                image_bytes = generate_image(
                    prompt=prompt,
                    model="fal-ai/flux-pro/kontext",
                    guidance_scale=3.5,
                    image_url=image_url,
                )

                trace.model = "fal-ai/flux-pro/kontext"
                trace.cost_usd = _KONTEXT_COST_USD
                trace.proof = {"page": page_num, "attempt": attempt}

            # Verify consistency
            if self.character_ref_embeddings:
                passed, score = self.verify_consistency(
                    generated_bytes=image_bytes,
                    characters_present=page.characters_present,
                    character_position=page.composition_guide.character_position,
                    threshold=consistency_threshold,
                )
                best_score = max(best_score, score)

                if passed:
                    break

                if attempt < max_retries:
                    logger.warning(
                        "Page %d consistency %.4f < %.2f, retrying (%d/%d)",
                        page_num, score, consistency_threshold,
                        attempt + 1, max_retries,
                    )
                else:
                    logger.warning(
                        "Page %d consistency %.4f still below threshold after "
                        "%d retries. Flagging for operator review.",
                        page_num, score, max_retries,
                    )
            else:
                best_score = 0.0
                break

        # Save locally
        filename = f"page_{page_num:03d}.jpg"
        local_path = output_dir / filename
        local_path.write_bytes(image_bytes)

        # Upload to MinIO
        object_name = f"illustrations/{self.job_id}/{filename}"
        upload_bytes(object_name, image_bytes, content_type="image/jpeg")

        # Upload to fal.ai for next page's Kontext reference
        fal_url = upload_to_fal(image_bytes, content_type="image/jpeg")
        self.previous_page_image = fal_url

        # Update state
        self.total_pages += 1
        self.pages_since_anchor += 1
        self.consistency_scores.append(best_score)

        logger.info(
            "Page %d illustrated (consistency=%.4f, anchor_in=%d pages)",
            page_num, best_score, _ANCHOR_INTERVAL - self.pages_since_anchor,
        )
        return local_path


# ---------------------------------------------------------------------------
# Workshop flow functions
# ---------------------------------------------------------------------------


def run_creative_workshop(
    *,
    style_lock: StyleLock,
    character_bibles: list[CharacterBible],
    job_id: str,
    output_dir: Path,
    ref_count: int = 10,
) -> IllustrationPipeline:
    """Run the pre-production creative workshop.

    Generates character reference candidates and initialises the pipeline.
    Operator selects best references externally (this function generates
    candidates for selection).

    S42.6 steps covered: character reference generation, style direction lock.

    Args:
        style_lock: Locked visual parameters from workshop step 9.
        character_bibles: All characters in this project.
        job_id: Production job ID.
        output_dir: Directory for reference images.
        ref_count: Candidates per character (default 10).

    Returns:
        Initialised IllustrationPipeline ready for specimen/production.
    """
    pipeline = IllustrationPipeline(style_lock=style_lock, job_id=job_id)

    for bible in character_bibles:
        refs = pipeline.generate_character_references(
            character_bible=bible,
            output_dir=output_dir / "references" / bible.character_id,
            count=ref_count,
        )
        # Auto-select all as references (operator narrows externally)
        pipeline.set_character_references(bible.character_id, refs)

    return pipeline


def run_specimen_page(
    *,
    pipeline: IllustrationPipeline,
    page: PageScaffold,
    character_bibles: list[CharacterBible],
    output_dir: Path,
) -> Path:
    """Generate a single specimen page for operator approval.

    S42.6 step 10: specimen page approval gate.

    Returns:
        Path to the specimen illustration.
    """
    return pipeline.illustrate_page(
        page=page,
        character_bibles=character_bibles,
        output_dir=output_dir / "specimen",
    )


def run_page_production(
    *,
    pipeline: IllustrationPipeline,
    scaffold: NarrativeScaffold,
    character_bibles: list[CharacterBible],
    rolling_context: RollingContext,
    output_dir: Path,
) -> list[Path]:
    """Run sequential page production through the full scaffold.

    For each page: illustrate -> verify -> update RollingContext.
    RollingContext receives both visual and textual descriptions.

    Args:
        pipeline: Initialised IllustrationPipeline with references set.
        scaffold: NarrativeScaffold with all pages.
        character_bibles: All characters.
        rolling_context: RollingContext to update per page.
        output_dir: Directory for page images.

    Returns:
        Ordered list of paths to generated illustrations.
    """
    images: list[Path] = []
    pages_dir = output_dir / "pages"

    for page in scaffold.pages:
        img_path = pipeline.illustrate_page(
            page=page,
            character_bibles=character_bibles,
            output_dir=pages_dir,
        )
        images.append(img_path)

        # Update RollingContext with visual description
        visual_summary = (
            f"Page {page.page} ({page.emotional_beat}): "
            f"[Visual: {page.composition_guide.camera}, "
            f"character at {page.composition_guide.character_position}, "
            f"{page.composition_guide.colour_temperature} colour temperature, "
            f"{page.composition_guide.background_detail} background] "
            f"Scene: {page.illustration_shows}"
        )
        update_rolling_context_for_page(
            ctx=rolling_context,
            page=page,
            page_text=visual_summary,
        )

    return images


def run_derivative_workshop(
    *,
    source_style_lock: StyleLock,
    job_id: str,
) -> IllustrationPipeline:
    """Fast-path derivative workshop — inherits source project settings.

    S42.6.1: Inherits StyleLock, typography, illustration tier.
    New content (premise, characters, scaffold, specimen) created separately.
    Target: 45-60 min operator time (vs 2-4 hrs full workshop).

    Args:
        source_style_lock: StyleLock from the source project.
        job_id: New project's job ID.

    Returns:
        Pipeline initialised with inherited settings.
    """
    logger.info("Derivative workshop: inheriting StyleLock from source project")
    return IllustrationPipeline(style_lock=source_style_lock, job_id=job_id)
