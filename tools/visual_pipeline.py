"""Full visual production pipeline — brief to scored poster with guardrails.

Pipeline: brief -> expand -> generate image -> NIMA -> 4-dim critique -> trace.
Visual brief expansion ALWAYS runs before generation (anti-drift #25).
All scoring on GPT-5.4-mini (anti-drift #22, #54).
"""

from __future__ import annotations

import logging
from typing import Any

from contracts.trace import TraceCollector
from middleware.guardrails import run_parallel_guardrails
from tools.image import expand_brief, generate_image, select_image_model
from tools.visual_scoring import (
    nima_prescreen,
    nima_score,
    record_visual_lineage,
    score_with_exemplars,
)

logger = logging.getLogger(__name__)


def run_visual_pipeline(
    *,
    raw_brief: str,
    job_id: str,
    client_id: str,
    artifact_family: str = "poster",
    language: str = "en",
    brand_config: dict[str, Any] | None = None,
    copy_register: str = "neutral",
    has_text: bool = True,
    width: int = 1024,
    height: int = 1024,
    max_regenerations: int = 2,
) -> dict[str, Any]:
    """Run the full visual production pipeline.

    Steps:
        1. Expand brief (GPT-5.4-mini)
        2. Select image model by job characteristics
        3. Generate image via fal.ai
        4. NIMA aesthetic pre-screen (local, zero cost)
        5. 4-dimension critique scoring (GPT-5.4-mini)
        6. Exemplar-anchored scoring (CLIP + GPT-5.4-mini)
        7. Record visual lineage
        8. Run parallel guardrails
        9. Collect trace

    Args:
        raw_brief: Operator's raw visual brief.
        job_id: Production job ID.
        client_id: Client identifier.
        artifact_family: From ArtifactFamily enum.
        language: ISO 639-1 language code.
        brand_config: Optional brand configuration.
        copy_register: Target register for guardrails.
        has_text: Whether the design is text-heavy.
        width: Output image width.
        height: Output image height.
        max_regenerations: Max NIMA-triggered regeneration attempts.

    Returns:
        Dict with expanded_brief, image_bytes, model_used, nima_score,
        nima_action, critique, exemplar_result, guardrail_flags, trace.
    """
    collector = TraceCollector(job_id=job_id)

    # Step 1: Expand brief
    with collector.step("expand_brief") as trace:
        expanded = expand_brief(raw_brief, brand_config=brand_config)
        trace.proof = {"fields_count": len(expanded)}

    # Step 2: Select model
    model = select_image_model(
        language=language,
        has_text=has_text,
        style=artifact_family,
        artifact_family=artifact_family,
    )

    # Step 3 + 4: Generate + NIMA loop
    image_bytes = b""
    score = 0.0
    prescreen = {"action": "regenerate", "score": 0.0}
    generation_prompt = expanded.get("composition", raw_brief)

    for attempt in range(max_regenerations + 1):
        with collector.step(f"generate_image_attempt_{attempt}") as trace:
            image_bytes = generate_image(
                prompt=generation_prompt,
                model=model,
                width=width,
                height=height,
            )
            trace.proof = {"model": model, "attempt": attempt, "size_bytes": len(image_bytes)}

        with collector.step(f"nima_prescreen_attempt_{attempt}") as trace:
            score = nima_score(image_bytes)
            prescreen = nima_prescreen(score)
            trace.proof = {"nima_score": score, "action": prescreen["action"]}

        if prescreen["action"] != "regenerate":
            break

        logger.info("NIMA score %.2f < 4.0, regenerating (attempt %d/%d)", score, attempt + 1, max_regenerations)

    # Step 5+6: Critique + exemplar scoring
    with collector.step("critique_and_exemplar_scoring") as trace:
        image_description = (
            f"Generated {artifact_family} using model {model}. "
            f"Brief composition: {expanded.get('composition', 'N/A')}. "
            f"Style: {expanded.get('style', 'N/A')}."
        )

        exemplar_result = score_with_exemplars(
            image_bytes=image_bytes,
            client_id=client_id,
            brief=expanded,
            image_description=image_description,
        )
        trace.proof = {
            "weighted_score": exemplar_result["weighted_score"],
            "exemplars_used": exemplar_result["exemplars_used"],
        }

    # Step 7: Visual lineage
    try:
        record_visual_lineage(
            job_id=job_id,
            role="generated",
            reason=f"Primary {artifact_family} via {model}",
        )
    except Exception as exc:
        logger.warning("Failed to record visual lineage: %s", exc)

    # Step 8: Run guardrails on any copy content
    guardrail_flags: list[dict[str, Any]] = []
    text_content = expanded.get("text_content", "")
    if text_content:
        with collector.step("parallel_guardrails") as trace:
            guardrail_flags = run_parallel_guardrails(
                copy=text_content,
                copy_register=copy_register,
                brand_config=brand_config,
                language=language,
            )
            trace.proof = {"flags_count": len(guardrail_flags)}

    # Step 9: Finalise trace
    production_trace = collector.finalise()

    return {
        "expanded_brief": expanded,
        "image_bytes": image_bytes,
        "model_used": model,
        "nima_score": score,
        "nima_action": prescreen["action"],
        "critique": exemplar_result["critique"],
        "weighted_score": exemplar_result["weighted_score"],
        "exemplar_result": exemplar_result,
        "guardrail_flags": guardrail_flags,
        "trace": production_trace.to_jsonb(),
    }
