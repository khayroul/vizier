from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

import open_clip  # type: ignore[import-untyped]
import torch  # type: ignore[import-untyped]
from PIL import Image

from utils.call_llm import call_llm
from utils.database import get_cursor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CLIP model (lazy-loaded singleton)
# ---------------------------------------------------------------------------

_clip_model: Any = None
_clip_preprocess: Any = None
_clip_device: str = "cpu"


def _ensure_clip() -> tuple[Any, Any, str]:
    """Lazy-load CLIP ViT-B/32 on first call. Uses MPS if available."""
    global _clip_model, _clip_preprocess, _clip_device  # noqa: PLW0603

    if _clip_model is not None:
        return _clip_model, _clip_preprocess, _clip_device

    _clip_device = "mps" if torch.backends.mps.is_available() else "cpu"
    _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="openai",
    )
    _clip_model = _clip_model.to(_clip_device)
    _clip_model.eval()
    logger.info("CLIP ViT-B/32 loaded on %s", _clip_device)
    return _clip_model, _clip_preprocess, _clip_device


def encode_image(image_bytes: bytes) -> list[float]:
    """Encode an image to a 512-dim CLIP embedding vector.

    Args:
        image_bytes: Raw image bytes (PNG, JPEG, etc.).

    Returns:
        512-dimensional normalised embedding as list of floats.
    """
    model, preprocess, device = _ensure_clip()
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    tensor = preprocess(img).unsqueeze(0).to(device)  # type: ignore[union-attr]

    with torch.no_grad():
        features = model.encode_image(tensor)
        features = features / features.norm(dim=-1, keepdim=True)

    return features.squeeze().cpu().tolist()  # type: ignore[no-any-return]

# Stable system prompt for contextualisation — cached across calls.
_CONTEXTUALISE_PREFIX: list[dict[str, str]] = [
    {
        "role": "system",
        "content": (
            "You generate a concise context prefix (50-100 tokens, one or two "
            "sentences) for a knowledge card. The prefix explains WHAT the card "
            "is about and WHERE it comes from. It must help a retrieval system "
            "match this card to relevant queries. Return ONLY the prefix text, "
            "no quotes, no labels."
        ),
    },
]


def contextualise_card(card: dict[str, str], source: dict[str, str]) -> str:
    """Generate 50-100 token context prefix via GPT-5.4-mini.

    Prepended to card content before embedding.
    Raw card content (without prefix) is served to production models.

    Args:
        card: Must contain ``content`` (the card text) and optionally
            ``card_type``, ``title``, ``tags``, ``domain``.
        source: Describes where the card came from.  Keys vary by origin:
            ``source_type`` (e.g. "brand_config", "copy_pattern", "swipe"),
            ``client_name``, ``title``, ``domain``.

    Returns:
        The context prefix string, e.g. "This card is from DMB's
        Raya 2025 promotional campaign targeting middle-class Malay women."
    """
    user_prompt = (
        f"Source: {source.get('source_type', 'unknown')} — "
        f"{source.get('client_name', 'general')} — "
        f"{source.get('title', 'untitled')}\n"
        f"Card type: {card.get('card_type', 'general')}\n"
        f"Domain: {card.get('domain', source.get('domain', 'general'))}\n"
        f"Content: {card.get('content', '')[:500]}"
    )

    result = call_llm(
        stable_prefix=_CONTEXTUALISE_PREFIX,
        variable_suffix=[{"role": "user", "content": user_prompt}],
        model="gpt-5.4-mini",
        temperature=0.3,
        max_tokens=150,
        operation_type="extract",
    )
    prefix = result["content"].strip()
    logger.debug("contextualise_card prefix (%d chars): %s", len(prefix), prefix[:80])
    return prefix


def retrieve_similar_exemplars(
    image: bytes,
    client_id: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """CLIP ViT-B/32 similarity search against exemplars table.

    Used by S11 for exemplar injection into production prompts.
    Used by S13 for exemplar-anchored quality scoring.

    Encodes the input image with CLIP, queries pgvector for nearest
    neighbours in the assets.visual_embedding column (512-dim, IVFFlat
    index), filtered to exemplar-linked assets for the given client.

    Returns: list of dicts, each with:
        {
            "exemplar_id": str,
            "artifact_id": str,
            "asset_path": str,
            "similarity": float,
            "artifact_family": str,
            "style_tags": list[str],
        }
    Sorted by similarity descending.
    Only returns results with similarity >= 0.5.
    For character consistency verification, use threshold 0.75 on cropped regions.
    """
    query_embedding = encode_image(image)
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    sql = """
        SELECT
            e.id            AS exemplar_id,
            e.artifact_id   AS artifact_id,
            a.storage_path  AS asset_path,
            e.artifact_family,
            e.style_tags,
            1 - (a.visual_embedding <=> %s::vector) AS similarity
        FROM exemplars e
        JOIN artifacts art ON art.id = e.artifact_id
        JOIN assets a ON a.id = art.asset_id
        WHERE e.client_id = %s
          AND e.status = 'active'
          AND a.visual_embedding IS NOT NULL
          AND 1 - (a.visual_embedding <=> %s::vector) >= 0.5
        ORDER BY similarity DESC
        LIMIT %s
    """

    with get_cursor() as cur:
        cur.execute(sql, (embedding_str, client_id, embedding_str, top_k))
        rows = cur.fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        results.append({
            "exemplar_id": str(row["exemplar_id"]),
            "artifact_id": str(row["artifact_id"]),
            "asset_path": row["asset_path"],
            "similarity": float(row["similarity"]),
            "artifact_family": row["artifact_family"],
            "style_tags": list(row["style_tags"]) if row["style_tags"] else [],
        })

    return results
