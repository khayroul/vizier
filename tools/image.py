"""Image generation wrapper — fal.ai with model routing and brief expansion.

Routes image model by job characteristics (anti-drift #17).
Visual brief expansion ALWAYS runs before generation (anti-drift #25).
Text is NEVER rendered inside AI-generated illustrations (anti-drift #49).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import fal_client  # type: ignore[import-untyped]
import httpx

from utils.call_llm import call_llm
from utils.spans import track_span

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model routing (anti-drift #17: selection by job characteristics)
# ---------------------------------------------------------------------------

_IMAGE_MODELS: dict[str, str] = {
    "bm_text": "fal-ai/nano-banana-pro",       # BM text rendering
    "photorealistic": "fal-ai/flux-pro",         # photorealistic product
    "draft": "fal-ai/nano-banana",               # free draft preview
    "character_iterative": "fal-ai/flux-pro/kontext",  # character consistency
    "generic": "fal-ai/flux/dev",                # default fallback
}


def select_image_model(
    *,
    language: str = "en",
    has_text: bool = False,
    style: str = "poster",
    artifact_family: str = "poster",
) -> str:
    """Select the best fal.ai model based on job characteristics.

    Args:
        language: ISO 639-1 language code.
        has_text: Whether the design is text-heavy.
        style: Design style hint (photorealistic, draft, poster, etc.).
        artifact_family: From ArtifactFamily enum.

    Returns:
        The fal.ai model endpoint string.
    """
    if style == "draft":
        return _IMAGE_MODELS["draft"]
    if style == "photorealistic":
        return _IMAGE_MODELS["photorealistic"]
    if language == "ms" and has_text:
        return _IMAGE_MODELS["bm_text"]
    if artifact_family == "childrens_book":
        return _IMAGE_MODELS["character_iterative"]
    return _IMAGE_MODELS["generic"]


# ---------------------------------------------------------------------------
# Brief expansion (anti-drift #25: ALWAYS before generation)
# ---------------------------------------------------------------------------

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "config" / "prompt_templates" / "visual_brief_expander.md"

_EXPAND_PREFIX: list[dict[str, str]] = []  # loaded lazily


def _load_brief_template() -> str:
    """Load the visual brief expander prompt template."""
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def _get_expand_prefix() -> list[dict[str, str]]:
    """Lazily load and cache the expansion system prompt."""
    global _EXPAND_PREFIX  # noqa: PLW0603 — intentional lazy init
    if not _EXPAND_PREFIX:
        template = _load_brief_template()
        _EXPAND_PREFIX = [{"role": "system", "content": template}]
    return _EXPAND_PREFIX


@track_span
def expand_brief(
    raw_brief: str,
    brand_config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Expand a raw visual brief into structured JSON via GPT-5.4-mini.

    Args:
        raw_brief: The operator's raw brief text.
        brand_config: Optional brand configuration with colours, logo rules, etc.

    Returns:
        Dict with keys: composition, style, brand, technical, text_content.
    """
    brand_context = ""
    if brand_config:
        brand_context = f"\n\nBrand config: {json.dumps(brand_config, ensure_ascii=False)}"

    user_msg = f"Expand this brief:{brand_context}\n\n{raw_brief}"

    result = call_llm(
        stable_prefix=_get_expand_prefix(),
        variable_suffix=[{"role": "user", "content": user_msg}],
        model="gpt-5.4-mini",
        temperature=0.4,
        max_tokens=800,
        response_format={"type": "json_object"},
        operation_type="extract",
    )

    try:
        expanded = json.loads(result["content"])
    except json.JSONDecodeError:
        logger.warning("Brief expansion returned non-JSON, using raw content")
        expanded = {
            "composition": result["content"],
            "style": "",
            "brand": "",
            "technical": "",
            "text_content": "",
        }

    return expanded


# ---------------------------------------------------------------------------
# Image generation via fal.ai
# ---------------------------------------------------------------------------


@track_span
def generate_image(
    *,
    prompt: str,
    model: str = "fal-ai/flux/dev",
    width: int = 1024,
    height: int = 1024,
    guidance_scale: float = 3.5,
    image_url: str | None = None,
) -> bytes:
    """Generate an image via fal.ai.

    Args:
        prompt: The expanded visual prompt (NOT raw brief).
        model: fal.ai model endpoint.
        width: Output width in pixels.
        height: Output height in pixels.
        guidance_scale: Model guidance scale.
        image_url: Optional reference image URL (for Kontext iterative).

    Returns:
        Raw image bytes.
    """
    arguments: dict[str, Any] = {
        "prompt": prompt,
        "image_size": {"width": width, "height": height},
        "guidance_scale": guidance_scale,
        "output_format": "jpeg",
    }

    if image_url and "kontext" in model:
        arguments["image_url"] = image_url

    result = fal_client.subscribe(model, arguments=arguments)

    image_data = result.get("images", [{}])
    if not image_data:
        raise RuntimeError(f"fal.ai returned no images for model {model}")

    image_info = image_data[0]
    image_content_url = image_info.get("url", "")

    # Download the image bytes from the returned URL
    resp = httpx.get(image_content_url, timeout=60.0)
    resp.raise_for_status()

    logger.info(
        "Generated image via %s (%dx%d, %d bytes)",
        model, width, height, len(resp.content),
    )

    return resp.content
