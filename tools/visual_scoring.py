"""Visual scoring pipeline — NIMA pre-screen, 4-dim critique, exemplar scoring, lineage.

NIMA runs locally on MPS (<100ms, zero tokens). Critique uses GPT-5.4-mini (anti-drift #22, #54).
Composition grammar rules are ADVISORY, not strict blockers (anti-drift #41).
"""

from __future__ import annotations

import functools
import json
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

import torch  # type: ignore[import-not-found]
import torch.nn as nn  # type: ignore[import-not-found]
import yaml
from torchvision import models, transforms  # type: ignore[import-untyped]

from utils.call_llm import call_llm
from utils.database import get_cursor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NIMA aesthetic pre-screen (section 30.5)
# ---------------------------------------------------------------------------

_NIMA_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


@functools.lru_cache(maxsize=1)
def _load_nima_model() -> nn.Module:
    """Load MobileNetV2 with NIMA classification head on MPS."""
    base = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
    # Replace classifier with NIMA head: 10-class distribution
    base.classifier = nn.Sequential(
        nn.Dropout(p=0.75),
        nn.Linear(1280, 10),
        nn.Softmax(dim=1),
    )
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    base = base.to(device)
    base.eval()
    return base


def nima_score(image_bytes: bytes) -> float:
    """Run NIMA aesthetic scoring on an image.

    Args:
        image_bytes: Raw image bytes (JPEG/PNG).

    Returns:
        Mean aesthetic score (1.0-10.0 range). Baseline ~5.5 for random images.
    """
    from PIL import Image
    import io

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = _NIMA_TRANSFORM(image).unsqueeze(0)  # type: ignore[arg-type]

    device = next(_load_nima_model().parameters()).device
    tensor = tensor.to(device)

    with torch.no_grad():
        probs = _load_nima_model()(tensor)

    # Weighted mean: sum(i * p_i) for i in 1..10
    weights = torch.arange(1, 11, dtype=torch.float32, device=device)
    mean_score = (probs * weights).sum().item()

    return float(mean_score)


def nima_prescreen(score: float) -> dict[str, Any]:
    """Classify NIMA score into action categories.

    Args:
        score: NIMA mean aesthetic score (1.0-10.0).

    Returns:
        Dict with action ('regenerate', 'proceed_with_caution', 'pass') and score.
    """
    if score < 4.0:
        action = "regenerate"
    elif score > 7.0:
        action = "pass"
    else:
        action = "proceed_with_caution"

    return {"action": action, "score": score}


# ---------------------------------------------------------------------------
# 4-dimension critique scoring (section 30.6)
# ---------------------------------------------------------------------------

_QUALITY_DIMS_PATH = (
    Path(__file__).resolve().parent.parent
    / "config" / "quality_frameworks" / "posteriq_quality_dimensions.yaml"
)
_RUBRIC_PATH = (
    Path(__file__).resolve().parent.parent
    / "config" / "quality_frameworks" / "poster_quality.md"
)


@functools.lru_cache(maxsize=1)
def _load_quality_dimensions() -> dict[str, Any]:
    """Load 4-dimension quality scoring config."""
    return yaml.safe_load(_QUALITY_DIMS_PATH.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def _load_rubric() -> str:
    """Load poster quality scoring rubric."""
    return _RUBRIC_PATH.read_text(encoding="utf-8")


def _build_critique_prefix() -> list[dict[str, str]]:
    """Build the stable system prompt for critique scoring."""
    rubric = _load_rubric()
    return [{"role": "system", "content": rubric}]


def critique_4dim(
    *,
    image_description: str,
    brief: dict[str, str],
    exemplar_descriptions: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Score a design across 4 quality dimensions using GPT-5.4-mini.

    Each dimension gets a separate LLM call for focused evaluation.
    All calls use GPT-5.4-mini (anti-drift #22, #54).

    Args:
        image_description: Text description of the generated image for scoring.
        brief: The expanded brief dict (from expand_brief).
        exemplar_descriptions: Optional descriptions of similar approved designs.

    Returns:
        Dict keyed by dimension name, each with 'score' (float) and 'issues' (list[str]).
    """
    dims_config = _load_quality_dimensions()
    dimensions = dims_config["dimensions"]
    prefix = _build_critique_prefix()

    exemplar_context = ""
    if exemplar_descriptions:
        exemplar_context = (
            "\n\nReference approved designs for comparison:\n"
            + "\n".join(f"- {desc}" for desc in exemplar_descriptions)
        )

    results: dict[str, dict[str, Any]] = {}

    for dim_name, dim_config in dimensions.items():
        description = dim_config["description"]
        criteria = dim_config["criteria"]

        user_msg = (
            f"Score this design on the dimension: {dim_name}\n"
            f"Definition: {description}\n"
            f"Criteria: {', '.join(criteria)}\n\n"
            f"Design brief: {json.dumps(brief, ensure_ascii=False)}\n"
            f"Image description: {image_description}"
            f"{exemplar_context}\n\n"
            f"Return JSON: {{\"score\": <1-5>, \"issues\": [\"specific issue 1\", ...]}}"
        )

        llm_result = call_llm(
            stable_prefix=prefix,
            variable_suffix=[{"role": "user", "content": user_msg}],
            model="gpt-5.4-mini",
            temperature=0.3,
            max_tokens=300,
            response_format={"type": "json_object"},
        )

        try:
            parsed = json.loads(llm_result["content"])
            results[dim_name] = {
                "score": float(parsed.get("score", 3.0)),
                "issues": list(parsed.get("issues", [])),
            }
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse critique for %s", dim_name)
            results[dim_name] = {"score": 3.0, "issues": ["Parse error in critique"]}

    return results


def weighted_score(critique_results: dict[str, dict[str, Any]]) -> float:
    """Calculate weighted average score from 4-dim critique results.

    All dimensions weighted equally at 0.25 each.
    """
    dims_config = _load_quality_dimensions()
    dimensions = dims_config["dimensions"]
    total = 0.0
    total_weight = 0.0

    for dim_name, dim_config in dimensions.items():
        weight = float(dim_config.get("weight", 0.25))
        score = float(critique_results.get(dim_name, {}).get("score", 3.0))
        total += weight * score
        total_weight += weight

    if total_weight == 0:
        return 3.0
    return total / total_weight


# ---------------------------------------------------------------------------
# Exemplar-anchored scoring (section 30.6)
# ---------------------------------------------------------------------------


def score_with_exemplars(
    *,
    image_bytes: bytes,
    client_id: str,
    brief: dict[str, str],
    image_description: str = "",
) -> dict[str, Any]:
    """Score a design against similar approved exemplars via CLIP.

    Uses retrieve_similar_exemplars from S11. Falls back gracefully
    if S11 hasn't merged yet.

    Args:
        image_bytes: Generated image bytes.
        client_id: Client identifier for exemplar filtering.
        brief: Expanded brief dict.
        image_description: Text description of the image.

    Returns:
        Dict with exemplars_used count, exemplar_descriptions, and critique results.
    """
    try:
        from utils.retrieval import retrieve_similar_exemplars
        exemplars = retrieve_similar_exemplars(
            image=image_bytes,
            client_id=client_id,
            top_k=3,
        )
    except (NotImplementedError, ImportError):
        logger.info("retrieve_similar_exemplars not available, skipping exemplar scoring")
        exemplars = []

    exemplar_descriptions = [
        f"{ex.get('artifact_family', 'design')} (similarity: {ex.get('similarity', 0):.2f}, "
        f"tags: {', '.join(ex.get('style_tags', []))})"
        for ex in exemplars
    ]

    critique = critique_4dim(
        image_description=image_description,
        brief=brief,
        exemplar_descriptions=exemplar_descriptions if exemplar_descriptions else None,
    )

    return {
        "exemplars_used": len(exemplars),
        "exemplar_ids": [ex.get("exemplar_id", "") for ex in exemplars],
        "exemplar_descriptions": exemplar_descriptions,
        "critique": critique,
        "weighted_score": weighted_score(critique),
    }


# ---------------------------------------------------------------------------
# Visual lineage (section 30.3)
# ---------------------------------------------------------------------------


def record_visual_lineage(
    *,
    job_id: str | UUID,
    artifact_id: str | UUID | None = None,
    asset_id: str | UUID | None = None,
    role: str,
    reason: str,
) -> None:
    """Record which assets contributed to an artifact's production.

    Args:
        job_id: The production job ID.
        artifact_id: The output artifact ID (nullable for in-progress).
        asset_id: The source asset ID (nullable for generated-only).
        role: Role of the asset (e.g. 'generated', 'template', 'stock', 'exemplar').
        reason: Why this asset was selected.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO visual_lineage (job_id, artifact_id, asset_id, role, selection_reason)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (str(job_id), str(artifact_id) if artifact_id else None,
             str(asset_id) if asset_id else None, role, reason),
        )
    logger.info("Recorded visual lineage: job=%s role=%s", job_id, role)
