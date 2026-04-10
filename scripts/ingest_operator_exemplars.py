"""Auto-tag operator exemplar PNGs via GPT-5.4-mini vision + NIMA + CLIP.

Ingests the operator's curated Envato template screenshots into a tagged
manifest for quality calibration and taste profiling.

Usage:
    python3 scripts/ingest_operator_exemplars.py datasets/operator_exemplars/posters/
    python3 scripts/ingest_operator_exemplars.py datasets/operator_exemplars/layouts/ --family brochure

Output:
    datasets/operator_exemplars/manifest.jsonl  (one JSON record per image)
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})


@dataclass
class ExemplarRecord:
    """Tagged operator exemplar with quality scores."""

    path: Path
    tags: dict[str, str]
    nima_score: float
    critique_scores: dict[str, float]
    source: str
    artifact_family: str
    clip_embedding: list[float] | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSONL output."""
        result: dict[str, Any] = {
            "path": str(self.path),
            "tags": self.tags,
            "nima_score": self.nima_score,
            "critique_scores": self.critique_scores,
            "source": self.source,
            "artifact_family": self.artifact_family,
        }
        if self.clip_embedding is not None:
            result["clip_embedding"] = self.clip_embedding
        return result


def build_tag_prompt() -> str:
    """Build the vision tagging prompt for GPT-5.4-mini."""
    return """\
Analyze this design template and extract structured tags.

Return ONLY a JSON object with these keys:
- industry: string (food, fashion, education, tech, automotive, retail, \
healthcare, real_estate, beauty, finance, event, general)
- mood: string (festive, professional, urgent, playful, formal, premium, \
caring, warm, elegant, bold, minimal)
- occasion: string (hari_raya, chinese_new_year, merdeka, deepavali, \
christmas, product_launch, sale, grand_opening, general, "")
- density: "minimal" | "moderate" | "dense"
- cta_style: "high" | "medium" | "low" | "none"
- colour_palette: string (warm_gold, cool_blue, vibrant, pastel, \
monochrome, earth_tones, neon, corporate, festive_red)
- layout_archetype: string (hero_left, hero_center, split_vertical, \
split_horizontal, grid, full_bleed, text_overlay, minimal_white)
"""


def parse_tag_response(raw: str) -> dict[str, str]:
    """Parse GPT-5.4-mini tag response, handling markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        # Strip markdown code fence
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return {k: str(v) for k, v in parsed.items()}
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse tag response: %s", text[:200])
    return {}


def tag_image(image_path: Path) -> dict[str, str]:
    """Call GPT-5.4-mini vision to extract structured tags from an image.

    Args:
        image_path: Path to a PNG/JPG image file.

    Returns:
        Dict of tag key-value pairs (industry, mood, occasion, etc.).
    """
    from utils.call_llm import call_llm

    image_bytes = image_path.read_bytes()
    b64 = base64.b64encode(image_bytes).decode("ascii")
    suffix = image_path.suffix.lower().lstrip(".")
    mime = f"image/{'jpeg' if suffix in ('jpg', 'jpeg') else suffix}"

    response = call_llm(
        stable_prefix=[],
        variable_suffix=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                    {"type": "text", "text": build_tag_prompt()},
                ],
            }
        ],
        model="gpt-5.4-mini",
        temperature=0.2,
        max_tokens=300,
        operation_type="classify",
    )

    return parse_tag_response(response.get("content", ""))


def ingest_exemplar(
    image_path: Path,
    *,
    artifact_family: str = "poster",
    run_nima: bool = True,
    run_critique: bool = False,
) -> ExemplarRecord:
    """Full ingestion pipeline: tag + NIMA + optional critique.

    Args:
        image_path: Path to the image file.
        artifact_family: poster, brochure, layout, etc.
        run_nima: Whether to compute NIMA aesthetic score.
        run_critique: Whether to run 4-dim critique (costs LLM tokens).

    Returns:
        Fully tagged ExemplarRecord.
    """
    tags = tag_image(image_path)

    nima = 0.0
    if run_nima:
        from tools.visual_scoring import nima_score
        image_bytes = image_path.read_bytes()
        nima = nima_score(image_bytes)

    critique_scores: dict[str, float] = {}
    if run_critique:
        from tools.visual_scoring import critique_4dim
        result = critique_4dim(
            image_description=f"Operator exemplar: {image_path.name}",
            brief={"source": "operator_exemplar", "family": artifact_family},
        )
        critique_scores = {k: float(v.get("score", 3.0)) for k, v in result.items()}

    return ExemplarRecord(
        path=image_path,
        tags=tags,
        nima_score=nima,
        critique_scores=critique_scores,
        source="operator_curated",
        artifact_family=artifact_family,
    )


def ingest_directory(
    dir_path: Path,
    *,
    artifact_family: str = "poster",
    run_nima: bool = True,
    run_critique: bool = False,
) -> list[ExemplarRecord]:
    """Batch-process all images in a directory.

    Args:
        dir_path: Directory containing PNG/JPG images.
        artifact_family: Category for all images in this directory.
        run_nima: Whether to compute NIMA scores.
        run_critique: Whether to run 4-dim critique.

    Returns:
        List of ExemplarRecord for all successfully processed images.
    """
    if not dir_path.is_dir():
        logger.error("Not a directory: %s", dir_path)
        return []

    images = sorted(
        p for p in dir_path.iterdir()
        if p.suffix.lower() in _IMAGE_EXTENSIONS
    )

    if not images:
        logger.warning("No images found in %s", dir_path)
        return []

    logger.info("Processing %d images from %s", len(images), dir_path)
    records: list[ExemplarRecord] = []

    for idx, img_path in enumerate(images, 1):
        logger.info("[%d/%d] %s", idx, len(images), img_path.name)
        try:
            record = ingest_exemplar(
                img_path,
                artifact_family=artifact_family,
                run_nima=run_nima,
                run_critique=run_critique,
            )
            records.append(record)
        except Exception:
            logger.exception("Failed to process %s", img_path.name)

    return records


def write_manifest(records: list[ExemplarRecord], output_path: Path) -> None:
    """Write records to JSONL manifest file.

    Args:
        records: List of ExemplarRecord to serialize.
        output_path: Path for the JSONL output file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    logger.info("Wrote %d records to %s", len(records), output_path)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Ingest operator exemplar images into tagged manifest."
    )
    parser.add_argument("directory", type=Path, help="Directory of PNG/JPG images")
    parser.add_argument(
        "--family",
        default="poster",
        help="Artifact family (poster, brochure, layout). Default: poster",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSONL path. Default: datasets/operator_exemplars/manifest.jsonl",
    )
    parser.add_argument(
        "--no-nima",
        action="store_true",
        help="Skip NIMA scoring (faster, no torch needed)",
    )
    parser.add_argument(
        "--critique",
        action="store_true",
        help="Run 4-dim critique scoring (costs LLM tokens)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    output_path = args.output or (
        Path(__file__).resolve().parent.parent
        / "datasets" / "operator_exemplars" / "manifest.jsonl"
    )

    records = ingest_directory(
        args.directory,
        artifact_family=args.family,
        run_nima=not args.no_nima,
        run_critique=args.critique,
    )

    if records:
        write_manifest(records, output_path)
        print(f"Done: {len(records)} exemplars → {output_path}")
    else:
        print("No images processed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
