"""Full visual production pipeline — brief to scored poster with guardrails.

Pipeline: brief -> expand -> generate image -> NIMA -> 4-dim critique -> trace.
Visual brief expansion ALWAYS runs before generation (anti-drift #25).
All scoring on GPT-5.4-mini (anti-drift #22, #54).
"""

from __future__ import annotations

import logging
from pathlib import Path
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


def evaluate_visual_artifact(
    *,
    image_path: str,
    client_id: str,
    brief: dict[str, Any],
    artifact_family: str = "poster",
    copy_text: str = "",
    copy_register: str = "neutral",
    brand_config: dict[str, Any] | None = None,
    language: str = "en",
    critique_max_tokens: int = 300,
    allow_parallel_guardrails: bool = True,
    qa_threshold: float = 3.2,
    adherence_threshold: float = 2.5,
    precomputed_nima_score: float | None = None,
    interpreted_intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a rendered visual artifact using the stronger scoring stack.

    Pass/fail now incorporates brief adherence when interpreted_intent is
    available: a visually polished poster that ignores the brief will fail QA.
    """
    image_bytes = Path(image_path).read_bytes()
    score = (
        float(precomputed_nima_score)
        if precomputed_nima_score is not None
        else nima_score(image_bytes)
    )
    prescreen = nima_prescreen(score)

    image_description = (
        f"Rendered {artifact_family} artifact. "
        f"Composition: {brief.get('composition', brief.get('raw_brief', 'N/A'))}. "
        f"Style: {brief.get('style', brief.get('design_system', 'N/A'))}. "
        f"Copy present: {'yes' if bool(copy_text.strip()) else 'no'}."
    )
    exemplar_result = score_with_exemplars(
        image_bytes=image_bytes,
        client_id=client_id,
        brief={str(k): str(v) for k, v in brief.items() if v is not None},
        image_description=image_description,
        max_tokens=critique_max_tokens,
    )

    guardrail_flags: list[dict[str, Any]] = []
    if allow_parallel_guardrails and copy_text.strip():
        try:
            guardrail_flags = run_parallel_guardrails(
                copy=copy_text,
                copy_register=copy_register,
                brand_config=brand_config,
                language=language,
            )
        except Exception as exc:
            logger.warning(
                "Visual guardrails failed during evaluation; continuing without flags: %s",
                exc,
            )
            guardrail_flags = []

    # Brief-adherence scoring: fail QA when output ignores the brief (P1 fix).
    # Only runs when interpreted_intent is available (i.e. brief interpreter succeeded).
    adherence_result: dict[str, Any] | None = None
    adherence_passed = True
    total_input_tokens = int(exemplar_result.get("input_tokens", 0) or 0)
    total_output_tokens = int(exemplar_result.get("output_tokens", 0) or 0)
    total_cost_usd = float(exemplar_result.get("cost_usd", 0.0) or 0.0)

    if interpreted_intent:
        try:
            from tools.visual_scoring import score_adherence

            adherence_result = score_adherence(
                image_bytes, interpreted_intent,
            )
            adherence_score = float(adherence_result.get("adherence_score", 3.0))
            adherence_passed = adherence_score >= adherence_threshold
            total_input_tokens += int(adherence_result.get("input_tokens", 0) or 0)
            total_output_tokens += int(adherence_result.get("output_tokens", 0) or 0)
            total_cost_usd += float(adherence_result.get("cost_usd", 0.0) or 0.0)

            if not adherence_passed:
                logger.warning(
                    "Adherence gate failed: %.2f < %.2f threshold",
                    adherence_score, adherence_threshold,
                )
        except Exception as exc:
            logger.warning(
                "Adherence scoring failed; proceeding without adherence gate: %s",
                exc,
            )

    passed = (
        prescreen["action"] != "regenerate"
        and float(exemplar_result["weighted_score"]) >= qa_threshold
        and adherence_passed
    )

    result: dict[str, Any] = {
        "nima_score": score,
        "nima_action": prescreen["action"],
        "weighted_score": exemplar_result["weighted_score"],
        "critique": exemplar_result["critique"],
        "exemplar_result": exemplar_result,
        "guardrail_flags": guardrail_flags,
        "passed": passed,
        "qa_threshold": qa_threshold,
        "adherence_threshold": adherence_threshold,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "cost_usd": total_cost_usd,
    }
    if adherence_result is not None:
        result["adherence_result"] = adherence_result
        result["adherence_score"] = adherence_result.get("adherence_score", 3.0)
    return result


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
            trace.proof = {
                "model": model,
                "attempt": attempt,
                "size_bytes": len(image_bytes),
            }

        with collector.step(f"nima_prescreen_attempt_{attempt}") as trace:
            score = nima_score(image_bytes)
            prescreen = nima_prescreen(score)
            trace.proof = {"nima_score": score, "action": prescreen["action"]}

        if prescreen["action"] != "regenerate":
            break

        logger.info(
            "NIMA score %.2f < 4.0, regenerating "
            "(attempt %d/%d)",
            score, attempt + 1, max_regenerations,
        )

    # Persist to a temporary local file so both runtime paths score the same artifact.
    temp_dir = Path.home() / "vizier" / "data" / "generated_images"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{job_id}_visual_pipeline.png"
    temp_path.write_bytes(image_bytes)

    # Step 5+6+8: Shared visual quality evaluation
    with collector.step("visual_quality_verdict") as trace:
        quality = evaluate_visual_artifact(
            image_path=str(temp_path),
            client_id=client_id,
            brief=expanded,
            artifact_family=artifact_family,
            copy_text=str(expanded.get("text_content", "")),
            copy_register=copy_register,
            brand_config=brand_config,
            language=language,
            allow_parallel_guardrails=True,
            qa_threshold=3.2,
            precomputed_nima_score=score,
        )
        trace.input_tokens = int(quality.get("input_tokens", 0) or 0)
        trace.output_tokens = int(quality.get("output_tokens", 0) or 0)
        trace.cost_usd = float(quality.get("cost_usd", 0.0) or 0.0)
        trace.proof = {
            "weighted_score": quality["weighted_score"],
            "nima_score": quality["nima_score"],
            "flags_count": len(quality["guardrail_flags"]),
            "passed": quality["passed"],
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

    guardrail_flags = quality["guardrail_flags"]

    # Step 9: Finalise trace
    production_trace = collector.finalise()

    return {
        "expanded_brief": expanded,
        "image_bytes": image_bytes,
        "model_used": model,
        "nima_score": score,
        "nima_action": prescreen["action"],
        "critique": quality["critique"],
        "weighted_score": quality["weighted_score"],
        "exemplar_result": quality["exemplar_result"],
        "guardrail_flags": guardrail_flags,
        "qa_threshold": quality["qa_threshold"],
        "passed": quality["passed"],
        "trace": production_trace.to_jsonb(),
    }
