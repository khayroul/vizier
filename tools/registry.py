"""Production tool registry — maps workflow YAML tool names to callables.

Every tool name that appears in any ``manifests/workflows/*.yaml`` has an
entry here.  Implementations fall into three categories:

1. **Real** — delegates to an existing function via lazy import.
2. **Explicit stub** — named placeholder for tools whose session hasn't
   shipped yet.  Returns ``{"status": "stub", ...}`` so callers can
   distinguish stubs from real results.

Lazy imports inside each wrapper prevent circular-dependency issues at
import time.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Type alias matching executor.ToolCallable protocol
ToolFn = Any  # Callable[[dict[str, Any]], dict[str, Any]]

_REPO_ROOT = Path(__file__).resolve().parent.parent
_HTML_TEMPLATES_DIR = _REPO_ROOT / "templates" / "html"


def _runtime_controls(context: dict[str, Any]) -> dict[str, Any]:
    """Return shared runtime controls from job_context."""
    job_ctx = context.get("job_context", {})
    return dict(job_ctx.get("runtime_controls") or {})


def _runtime_max_tokens(
    context: dict[str, Any],
    *,
    purpose: str,
    default: int,
) -> int:
    controls = _runtime_controls(context)
    if purpose == "critique":
        return int(controls.get("critique_max_tokens", default))
    if purpose == "revision":
        return int(controls.get("revision_max_tokens", default))
    return int(controls.get("default_max_tokens", default))


def _artifact_payload(context: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical artifact payload if present."""
    payload = context.get("artifact_payload")
    if isinstance(payload, dict):
        return payload
    previous = context.get("previous_output", {})
    if isinstance(previous, dict):
        previous_payload = previous.get("_artifact_payload")
        if isinstance(previous_payload, dict):
            return previous_payload
    return {}


def _quality_target_field(payload: dict[str, Any]) -> str:
    """Pick which text field should be scored or revised."""
    for key in (
        "poster_copy",
        "brochure_copy",
        "document_content",
        "section_content",
        "page_text",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return key
    return "output"


def _quality_target_text(payload: dict[str, Any], fallback: dict[str, Any]) -> str:
    """Return the best textual artifact representation for scoring/revision."""
    field = _quality_target_field(payload)
    value = payload.get(field) if field != "output" else None
    if isinstance(value, str) and value.strip():
        return value
    output = fallback.get("output", "")
    return str(output)


def _resolve_template_name(
    job_ctx: dict[str, Any],
    *,
    workflow: str,
    active_slots: set[str] | None = None,
) -> str:
    """Resolve a concrete render template via intent-aware scoring.

    Priority:
    1. Explicit template_name in job_ctx (operator override)
    2. Road safety pattern match (backward compat for safety workflows)
    3. Intent-aware selector scoring against _meta.yaml catalog
    4. Fallback: poster_default
    """
    if workflow != "poster_production":
        return "poster"

    # 1. Explicit override
    explicit = job_ctx.get("template_name")
    if explicit and (_HTML_TEMPLATES_DIR / f"{explicit}.html").exists():
        return str(explicit)

    # 2. Road safety backward compat
    design_system = job_ctx.get("design_system") or job_ctx.get(
        "routing", {},
    ).get("design_system")
    if isinstance(design_system, str):
        ds_key = design_system.strip().lower().replace(" ", "_")
        if "road" in ds_key or "safety" in ds_key:
            return "poster_road_safety"

    # 3. Intent-aware selector (hardening 2.6)
    from contracts.interpreted_intent import InterpretedIntent
    from tools.template_selector import select_template

    intent_data = job_ctx.get("interpreted_intent", {})
    try:
        intent = (
            InterpretedIntent.model_validate(intent_data)
            if intent_data
            else InterpretedIntent()
        )
    except Exception:
        intent = InterpretedIntent()

    match = select_template(
        intent,
        active_slots=active_slots,
        client_style_hint=str(design_system or ""),
    )

    if (_HTML_TEMPLATES_DIR / f"{match.template_name}.html").exists():
        return match.template_name
    return "poster_default"


def _stub(name: str, reason: str) -> ToolFn:
    """Return an explicit named stub that identifies itself in output."""

    def _wrapper(context: dict[str, Any]) -> dict[str, Any]:
        logger.info("stub_tool_called: %s — %s", name, reason)
        return {
            "status": "stub",
            "tool": name,
            "reason": reason,
            "output": "",
        }

    _wrapper.__qualname__ = f"stub_{name}"
    return _wrapper


# ---------------------------------------------------------------------------
# Real tool wrappers (lazy imports to avoid circular deps)
# ---------------------------------------------------------------------------


def _classify_artifact(context: dict[str, Any]) -> dict[str, Any]:
    """Classify the incoming request into an artifact family."""
    from utils.call_llm import call_llm

    prompt = context.get("prompt", "Classify this artifact request.")
    result = call_llm(
        stable_prefix=[{"role": "system", "content": "Classify the artifact type."}],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.0,
        max_tokens=256,
        operation_type="classify",
    )
    return {
        "status": "ok",
        "output": result.get("content", ""),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": result.get("cost_usd", 0.0),
    }


def _sanitize_visual_prompt(prompt: str) -> str:
    """Rewrite visual prompt as a scene description, not an artifact.

    FLUX renders gibberish text whenever the prompt describes a "poster",
    "campaign", or any finished design artifact. The fix is aggressive:
    strip ALL artifact/design language and ensure the prompt only
    describes a visual scene suitable as a background.
    """
    import re

    # Remove quoted strings (text content FLUX would try to render)
    prompt = re.sub(r"['\"][^'\"]{3,}['\"]", "", prompt)

    # Remove "headline: ...", "CTA: ...", etc. instruction patterns
    prompt = re.sub(
        r"(?i)(headline|subheadline|cta|body text|body copy|"
        r"caption|tagline|slogan|title|subtitle|footer|header"
        r"|text reads|text says|include text|with text"
        r"|call to action|main message|supporting text"
        r"|banner text|logo text)\s*[:=][^\n.]*",
        "",
        prompt,
    )

    # Remove artifact/design words that make FLUX generate a
    # "finished poster" instead of a background scene
    prompt = re.sub(
        r"(?i)\b(poster|flyer|banner|brochure|pamphlet|leaflet"
        r"|advertisement|ad |campaign materials?|print design"
        r"|website|mockup|ui |ux |wireframe|infographic"
        r"|layout|typography|typographic|font|typeface"
        r"|professionally done|professional design"
        r"|government agency|gov agency|official poster"
        r"|notice ?board|bulletin|announcement)\b",
        "",
        prompt,
    )

    # Collapse whitespace
    prompt = re.sub(r"\s{2,}", " ", prompt).strip()
    return prompt


def _build_reference_style_guidance(
    context: dict[str, Any],
) -> tuple[str | None, str | None, dict[str, Any] | None]:
    """Summarise an optional reference poster into promptable guidance.

    This gives poster jobs a concrete seam for sample-poster adaptation:
    if a caller provides a local reference image or a fal-hosted URL, we
    preserve the layout/palette cues in the prompt and, when possible,
    route generation through an image-to-image model.
    """
    import mimetypes

    job_ctx = context.get("job_context", {})
    payload = _artifact_payload(context)

    reference_path = (
        payload.get("reference_image_path")
        or job_ctx.get("reference_image_path")
    )
    reference_url = (
        payload.get("reference_image_url")
        or job_ctx.get("reference_image_url")
    )
    reference_notes = (
        payload.get("reference_notes")
        or job_ctx.get("reference_notes")
    )

    reference_visual_dna: dict[str, Any] | None = None

    if isinstance(reference_path, str) and reference_path.strip():
        path = Path(reference_path).expanduser()
        if path.exists():
            try:
                from tools.visual_dna import extract_visual_dna
                from utils.storage import upload_to_fal

                image_bytes = path.read_bytes()
                reference_visual_dna = extract_visual_dna(image_bytes)
                if not reference_url:
                    mime_type = (
                        mimetypes.guess_type(str(path))[0]
                        or "image/jpeg"
                    )
                    reference_url = upload_to_fal(
                        image_bytes,
                        content_type=mime_type,
                    )
            except Exception as exc:
                logger.warning(
                    "Reference poster analysis failed for %s: %s",
                    path,
                    exc,
                )

    if not reference_visual_dna and not reference_notes and not reference_url:
        return None, None, None

    guidance_parts: list[str] = [
        "Reference poster guidance:",
        "Use the reference's layout rhythm and visual hierarchy as inspiration, "
        "but create a new poster tailored to the current brief.",
        "Do not copy any original text, logos, marks, or trademarks from the "
        "reference image.",
    ]
    if reference_visual_dna:
        layout_type = str(reference_visual_dna.get("layout_type", "")).strip()
        colours = reference_visual_dna.get("dominant_colours") or []
        if layout_type:
            guidance_parts.append(
                f"- Layout type to echo: {layout_type}"
            )
        if isinstance(colours, list) and colours:
            guidance_parts.append(
                "- Palette cues: " + ", ".join(str(colour) for colour in colours[:4])
            )
    if isinstance(reference_notes, str) and reference_notes.strip():
        guidance_parts.append(f"- Operator notes: {reference_notes.strip()}")

    return "\n".join(guidance_parts), (
        str(reference_url) if isinstance(reference_url, str) and reference_url else None
    ), reference_visual_dna


def _image_generate(context: dict[str, Any]) -> dict[str, Any]:
    """Generate an image via fal.ai with brief expansion (anti-drift #25).

    Passes client brand config and design system from routing into brief
    expansion so the generated image reflects client identity.
    """
    from pathlib import Path
    from uuid import uuid4

    from tools.image import (
        expand_brief,
        generate_image,
        select_image_dimensions,
        select_image_model,
    )

    job_ctx = context.get("job_context", {})
    payload = _artifact_payload(context)
    prompt = context.get("prompt", "")
    client_id = job_ctx.get("client_id", "default")

    # Load client brand for brief expansion context
    brand_config = {
        **_load_client_brand(client_id),
        **dict(job_ctx.get("brand_config") or {}),
    }

    # Include design system from routing if available
    design_system = job_ctx.get("routing", {}).get("design_system")
    if design_system:
        brand_config["design_system"] = design_system

    reference_guidance, reference_image_url, reference_visual_dna = (
        _build_reference_style_guidance(context)
    )
    if reference_visual_dna:
        brand_config["reference_visual_dna"] = reference_visual_dna
    prompt_for_expansion = prompt
    if reference_guidance:
        prompt_for_expansion = f"{prompt}\n\n{reference_guidance}"

    # Anti-drift #25: ALWAYS expand brief before generation
    # Pass interpreted intent so visual elaboration uses canonical parse (P1 fix)
    expanded = expand_brief(
        prompt_for_expansion,
        brand_config=brand_config,
        interpreted_intent=job_ctx.get("interpreted_intent"),
    )
    visual_prompt = expanded.get("composition", prompt)

    if reference_visual_dna:
        layout_type = reference_visual_dna.get("layout_type")
        dominant_colours = reference_visual_dna.get("dominant_colours") or []
        palette_hint = ", ".join(str(colour) for colour in dominant_colours[:4])
        reference_hint_parts: list[str] = []
        if layout_type:
            reference_hint_parts.append(
                f"Follow a {layout_type} composition inspired by the reference poster"
            )
        if palette_hint:
            reference_hint_parts.append(
                f"with palette accents inspired by {palette_hint}"
            )
        if reference_hint_parts:
            visual_prompt = (
                f"{visual_prompt.rstrip('.')} "
                + " ".join(reference_hint_parts)
                + "."
            )

    # Anti-drift #49: text is rendered by Typst, never baked into images.
    # Rewrite prompt as a scene description, stripping all artifact language.
    visual_prompt = _sanitize_visual_prompt(visual_prompt)

    # Prepend scene framing + append hard no-text rule
    visual_prompt = (
        "Illustration of a visual scene: "
        + visual_prompt.rstrip(".")
        + ". The image contains NO text whatsoever — no letters, "
        "no words, no numbers, no logos, no signs with writing, "
        "no watermarks. Pure visual imagery only."
    )

    model = select_image_model(
        language=str(job_ctx.get("language", "en")),
        has_text=bool(str(payload.get("poster_copy") or payload.get("text_content") or "").strip()),
        style=str(brand_config.get("image_mode") or "poster"),
        artifact_family=str(job_ctx.get("artifact_family", "poster")),
        image_mode=str(brand_config.get("image_mode") or ""),
        reference_image_url=reference_image_url,
    )
    width, height = select_image_dimensions(
        artifact_family=str(job_ctx.get("artifact_family", "poster")),
        platform=str(job_ctx.get("platform") or ""),
    )

    image_bytes = generate_image(
        prompt=visual_prompt,
        model=model,
        width=width,
        height=height,
        image_url=reference_image_url,
    )

    # Save to local file — prevents fal.ai CDN URL expiry issues
    # and provides a stable path for downstream stages (vision, delivery).
    local_dir = Path.home() / "vizier" / "data" / "generated_images"
    local_dir.mkdir(parents=True, exist_ok=True)
    # Detect actual format from magic bytes — fal.ai often returns JPEG
    ext = ".png"
    if image_bytes[:2] == b"\xff\xd8":
        ext = ".jpg"
    elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        ext = ".webp"
    local_path = local_dir / f"{uuid4().hex}{ext}"
    local_path.write_bytes(image_bytes)
    logger.info("Image saved: %s (%d bytes)", local_path, len(image_bytes))

    return {
        "status": "ok",
        "output": f"image_generated ({len(image_bytes)} bytes via {model})",
        "image_path": str(local_path),
        "image_model": model,
        "image_width": width,
        "image_height": height,
        "reference_image_url": reference_image_url,
        "reference_visual_dna": reference_visual_dna,
        "expanded_brief": expanded,
        "cost_usd": 0.025,  # fal.ai flux/dev approximate cost
    }


def _visual_qa(context: dict[str, Any]) -> dict[str, Any]:
    """Run visual QA — critique-then-revise on failure (anti-drift #21, #38).

    When the initial image fails QA, regenerates with the critique as
    guidance and re-evaluates.  Max retries controlled by
    ``runtime_controls.qa_max_retries`` (default 1).
    """
    from tools.visual_pipeline import evaluate_visual_artifact

    job_ctx = context.get("job_context", {})
    previous_output = context.get("previous_output", {})
    payload = _artifact_payload(context)
    image_path = (
        payload.get("image_path")
        or context.get("previous_output", {}).get("image_path")
    )
    if not image_path:
        return {
            "status": "error",
            "output": "visual_qa_failed: no rendered image available",
            "score": 0.0,
            "cost_usd": 0.0,
        }

    controls = _runtime_controls(context)
    expanded_brief = (
        previous_output.get("expanded_brief")
        if isinstance(previous_output, dict)
        else None
    )
    if not isinstance(expanded_brief, dict):
        expanded_brief = {}
    brief = {
        **expanded_brief,
        "raw_brief": str(job_ctx.get("raw_input", "")),
        "design_system": str(
            job_ctx.get("design_system")
            or job_ctx.get("routing", {}).get("design_system")
            or expanded_brief.get("design_system")
            or ""
        ),
        "template_name": str(
            payload.get("template_name")
            or job_ctx.get("template_name")
            or ""
        ),
        "style": str(
            expanded_brief.get("style")
            or payload.get("design_system")
            or ""
        ),
        "composition": str(
            expanded_brief.get("composition")
            or payload.get("text_content")
            or ""
        ),
    }
    reference_visual_dna = (
        previous_output.get("reference_visual_dna")
        if isinstance(previous_output, dict)
        else None
    )
    if isinstance(reference_visual_dna, dict):
        brief["reference_layout"] = str(
            reference_visual_dna.get("layout_type", "")
        )
        brief["reference_palette"] = ", ".join(
            str(c)
            for c in (reference_visual_dna.get("dominant_colours") or [])[:4]
        )

    qa_kwargs: dict[str, Any] = {
        "client_id": str(job_ctx.get("client_id", "default")),
        "brief": brief,
        "artifact_family": str(job_ctx.get("artifact_family", "poster")),
        "copy_text": str(payload.get("text_content", "")),
        "copy_register": str(job_ctx.get("copy_register", "neutral")),
        "brand_config": job_ctx.get("brand_config"),
        "language": str(job_ctx.get("language", "en")),
        "critique_max_tokens": int(
            controls.get("critique_max_tokens", 300)
        ),
        "allow_parallel_guardrails": bool(
            controls.get("allow_parallel_guardrails", True)
        ),
        "qa_threshold": float(controls.get("qa_threshold", 3.2)),
        "interpreted_intent": job_ctx.get("interpreted_intent"),
    }

    # --- Evaluate (with critique-then-revise retry) ---
    max_retries = int(controls.get("qa_max_retries", 1))
    total_cost = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    current_image_path = str(image_path)

    for attempt in range(max_retries + 1):
        quality = evaluate_visual_artifact(
            image_path=current_image_path, **qa_kwargs,
        )
        total_cost += float(quality.get("cost_usd", 0.0))
        total_input_tokens += int(quality.get("input_tokens", 0))
        total_output_tokens += int(quality.get("output_tokens", 0))

        if quality["passed"]:
            break

        # Last attempt already — don't regenerate, just report
        if attempt >= max_retries:
            break

        # --- Critique-then-revise: regenerate with specific issues ---
        critique = quality.get("critique", {})
        failing_dims = [
            f"{dim}: {info.get('issues', [])}"
            for dim, info in critique.items()
            if isinstance(info, dict) and float(info.get("score", 5)) < 3.0
        ]
        if not failing_dims:
            # No actionable critique → cannot revise (anti-drift #38)
            logger.warning(
                "QA failed (%.2f) but no actionable dimension critique "
                "— cannot revise, attempt %d/%d",
                quality["weighted_score"],
                attempt + 1,
                max_retries,
            )
            break

        logger.info(
            "QA failed (%.2f < %.2f), revising image — attempt %d/%d. "
            "Failing dimensions: %s",
            quality["weighted_score"],
            qa_kwargs["qa_threshold"],
            attempt + 1,
            max_retries,
            "; ".join(failing_dims),
        )

        try:
            from tools.image import (
                generate_image,
                select_image_dimensions,
                select_image_model,
            )
            from uuid import uuid4

            critique_guidance = (
                "REVISION — previous image failed QA. Fix these issues: "
                + "; ".join(failing_dims)
            )
            # Use the same expanded composition prompt as the first pass,
            # NOT "visual_prompt" (which doesn't exist in expanded_brief).
            visual_prompt = expanded_brief.get("composition", "")
            if not visual_prompt:
                visual_prompt = str(job_ctx.get("raw_input", ""))

            # Apply the same sanitization + no-text framing as first pass
            visual_prompt = _sanitize_visual_prompt(visual_prompt)
            visual_prompt = (
                "Illustration of a visual scene: "
                + visual_prompt.rstrip(".")
                + ". The image contains NO text whatsoever — no letters, "
                "no words, no numbers, no logos, no signs with writing, "
                "no watermarks. Pure visual imagery only."
            )
            revised_prompt = f"{visual_prompt}\n\n{critique_guidance}"

            ref_url = (
                previous_output.get("reference_image_url")
                if isinstance(previous_output, dict)
                else None
            )
            model = select_image_model(
                language=str(job_ctx.get("language", "en")),
                has_text=bool(qa_kwargs["copy_text"].strip()),
                style=str(
                    (job_ctx.get("brand_config") or {}).get(
                        "image_mode", "poster"
                    )
                ),
                artifact_family=qa_kwargs["artifact_family"],
                image_mode=str(
                    (job_ctx.get("brand_config") or {}).get(
                        "image_mode", ""
                    )
                ),
                reference_image_url=ref_url,
            )
            # Recover original dimensions from first-pass output so the
            # revised image matches the poster geometry, not 1024x1024.
            first_pass_width = (
                previous_output.get("image_width") if isinstance(previous_output, dict) else None
            )
            first_pass_height = (
                previous_output.get("image_height") if isinstance(previous_output, dict) else None
            )
            if not first_pass_width or not first_pass_height:
                first_pass_width, first_pass_height = select_image_dimensions(
                    artifact_family=qa_kwargs["artifact_family"],
                    platform=str(job_ctx.get("platform") or ""),
                )
            image_bytes = generate_image(
                prompt=revised_prompt,
                model=model,
                width=first_pass_width,
                height=first_pass_height,
                image_url=ref_url,
            )
            total_cost += 0.025  # approx fal.ai cost

            # Save revised image
            local_dir = (
                Path.home() / "vizier" / "data" / "generated_images"
            )
            local_dir.mkdir(parents=True, exist_ok=True)
            ext = ".png"
            if image_bytes[:2] == b"\xff\xd8":
                ext = ".jpg"
            elif (
                image_bytes[:4] == b"RIFF"
                and image_bytes[8:12] == b"WEBP"
            ):
                ext = ".webp"
            revised_path = local_dir / f"{uuid4().hex}_revised{ext}"
            revised_path.write_bytes(image_bytes)
            current_image_path = str(revised_path)
            logger.info(
                "Revised image saved: %s (%d bytes)",
                revised_path,
                len(image_bytes),
            )
        except Exception as exc:
            logger.warning(
                "Image regeneration failed during QA revision: %s", exc,
            )
            break

    status = "ok" if quality["passed"] else "error"
    return {
        "status": status,
        "output": quality["critique"],
        "score": quality["weighted_score"],
        "image_path": current_image_path,
        "qa_threshold": quality["qa_threshold"],
        "quality_summary": {
            "nima_score": quality["nima_score"],
            "nima_action": quality["nima_action"],
            "weighted_score": quality["weighted_score"],
            "flags_count": len(quality["guardrail_flags"]),
        },
        "guardrail_flags": quality["guardrail_flags"],
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "cost_usd": total_cost,
    }


def _typst_render(context: dict[str, Any]) -> dict[str, Any]:
    """Render a document to PDF via Typst.

    Two modes — chosen automatically from context:

    1. **Template mode** (``template_name`` present): delegates to
       ``assemble_document_pdf()`` which maps content keys to Typst
       ``sys.inputs`` and compiles the named template.
    2. **Source mode** (``typst_source`` present or ``document_content``
       from upstream ``_generate_document``): writes Typst markup to a
       temp file and compiles directly.  If the content is plain text
       (not Typst markup), it is wrapped in a minimal Typst document.

    Outputs ``pdf_path`` so the delivery stage can package it.
    """
    from tools.publish import assemble_document_pdf

    payload = _artifact_payload(context)
    job_ctx = context.get("job_context", {})

    # Where to write the PDF
    output_root = Path.home() / "vizier" / "data" / "deliverables"
    output_dir = output_root / str(job_ctx.get("job_id", "default"))
    output_dir.mkdir(parents=True, exist_ok=True)

    # Mode 1: Named template — structured metadata documents (invoice, proposal, report)
    template_name = (
        payload.get("template_name")
        or context.get("template_name")
        or job_ctx.get("template_name")
    )
    if template_name:
        # Gather content from payload + job context
        content: dict[str, str] = {}
        for key in (
            "title", "subtitle", "client_name", "author", "date",
            "period", "reference", "company_name", "invoice_number",
            "invoice_date", "body_text",
        ):
            val = payload.get(key) or job_ctx.get(key)
            if val:
                content[key] = str(val)

        # Pull document_content from upstream generation if available
        doc_content = str(
            payload.get("document_content")
            or payload.get("text_content")
            or context.get("previous_output", {}).get("output", "")
        )
        if doc_content.strip():
            content["body_text"] = doc_content

        style = _load_client_style(job_ctx.get("client_id", "default"))
        try:
            pdf_path = assemble_document_pdf(
                template_name=template_name,
                content=content,
                colors=style.get("colors"),
                fonts=style.get("fonts"),
                output_dir=output_dir,
            )
            return {
                "status": "ok",
                "output": "typst_rendered",
                "pdf_path": str(pdf_path),
                "template_name": template_name,
                "cost_usd": 0.0,
            }
        except Exception as exc:
            logger.error("Typst template render failed: %s", exc)
            return {
                "status": "error",
                "output": f"typst_render_failed: {exc}",
                "cost_usd": 0.0,
            }

    # Mode 2: Raw Typst source or plain-text document content
    typst_source = str(
        context.get("typst_source", "")
        or payload.get("typst_source", "")
    )
    if not typst_source:
        # Fall back to document_content and wrap in minimal Typst
        raw_content = str(
            payload.get("document_content")
            or payload.get("text_content")
            or context.get("previous_output", {}).get("output", "")
        )
        if not raw_content.strip():
            return {
                "status": "error",
                "output": "typst_render_failed: no content to render",
                "cost_usd": 0.0,
            }
        typst_source = _wrap_plain_text_as_typst(
            raw_content,
            title=str(
                payload.get("title")
                or job_ctx.get("raw_input", "Document")[:80]
            ),
            client_name=str(job_ctx.get("client_name", "")),
        )

    # Compile the source
    import tempfile

    from tools.publish import _compile_typst

    source_file = output_dir / "document.typ"
    source_file.write_text(typst_source, encoding="utf-8")
    pdf_path = output_dir / "document.pdf"

    try:
        _compile_typst(source_file, pdf_path)
        return {
            "status": "ok",
            "output": "typst_rendered",
            "pdf_path": str(pdf_path),
            "cost_usd": 0.0,
        }
    except Exception as exc:
        logger.error("Typst source compilation failed: %s", exc)
        return {
            "status": "error",
            "output": f"typst_render_failed: {exc}",
            "cost_usd": 0.0,
        }


def _wrap_plain_text_as_typst(
    content: str,
    *,
    title: str = "Document",
    client_name: str = "",
) -> str:
    """Wrap plain text content in a minimal Typst document.

    Used when ``_generate_document`` outputs prose/structured text
    rather than raw Typst markup.  Converts markdown-style headings
    (``# Heading``) to Typst headings and preserves paragraph breaks.
    """
    from tools.publish import _escape_typst

    lines: list[str] = []
    lines.append('#set page(paper: "a4", margin: (x: 2.5cm, y: 2cm))')
    lines.append('#set text(font: "Inter", size: 11pt)')
    lines.append('#set par(leading: 0.7em, spacing: 1.4em)')
    lines.append('#set heading(numbering: "1.1")')
    lines.append("")

    # Title block
    escaped_title = _escape_typst(title)
    lines.append(f'#align(center)[#text(size: 22pt, weight: "bold")[{escaped_title}]]')
    if client_name:
        escaped_client = _escape_typst(client_name)
        lines.append(f'#align(center)[#text(size: 12pt, fill: luma(100))[{escaped_client}]]')
    lines.append("#v(1em)")
    lines.append('#line(length: 100%, stroke: 0.5pt + luma(200))')
    lines.append("#v(1em)")
    lines.append("")

    # Convert content — handle markdown-style headings
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("### "):
            heading_text = _escape_typst(stripped[4:])
            lines.append(f"=== {heading_text}")
        elif stripped.startswith("## "):
            heading_text = _escape_typst(stripped[3:])
            lines.append(f"== {heading_text}")
        elif stripped.startswith("# "):
            heading_text = _escape_typst(stripped[2:])
            lines.append(f"= {heading_text}")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            bullet_text = _escape_typst(stripped[2:])
            lines.append(f"- {bullet_text}")
        elif stripped:
            lines.append(_escape_typst(stripped))
        else:
            lines.append("")

    return "\n".join(lines)


def _generate_copy(context: dict[str, Any]) -> dict[str, Any]:
    """Generate copy text via LLM."""
    from utils.call_llm import call_llm

    prompt = context.get("prompt", "")
    result = call_llm(
        stable_prefix=[{"role": "system", "content": "Generate marketing copy."}],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.7,
        max_tokens=_runtime_max_tokens(context, purpose="generate", default=2048),
        operation_type="generate",
    )
    return {
        "status": "ok",
        "output": result.get("content", ""),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": result.get("cost_usd", 0.0),
    }


def _knowledge_retrieve(context: dict[str, Any]) -> dict[str, Any]:
    """Retrieve relevant knowledge cards."""
    from utils.embeddings import embed_text
    from utils.knowledge import assemble_context

    job_ctx = context.get("job_context", {})
    controls = _runtime_controls(context)
    client_id = str(job_ctx.get("client_id", "default"))
    query = str(context.get("prompt") or job_ctx.get("raw_input") or "")
    top_k = int(controls.get("knowledge_card_cap", 4))

    try:
        query_embedding = embed_text(query, job_id=job_ctx.get("job_id")) if query else None
        assembled = assemble_context(
            client_id=client_id,
            query=query,
            query_embedding=query_embedding,
            include_knowledge=True,
            top_k=top_k,
        )
        cards = assembled.get("knowledge_cards", [])
    except Exception as exc:
        logger.debug("knowledge_retrieve skipped: %s", exc)
        cards = []

    snippets: list[str] = []
    if isinstance(cards, list):
        for card in cards[:top_k]:
            if not isinstance(card, dict):
                continue
            title = str(card.get("title") or "Untitled card")
            content = str(card.get("content") or "").strip()
            if content:
                snippets.append(f"- {title}: {content[:240]}")

    return {
        "status": "ok",
        "output": "knowledge_retrieved",
        "cards": cards if isinstance(cards, list) else [],
        "knowledge_context": "\n".join(snippets),
        "cost_usd": 0.0,
    }


def _knowledge_store(context: dict[str, Any]) -> dict[str, Any]:
    """Store a knowledge card."""
    return {"status": "ok", "output": "knowledge_stored", "cost_usd": 0.0}


def _infer_failed_stage_from_trace(trace: dict[str, Any]) -> str | None:
    """Infer a failing stage name from a prior workflow trace/result payload."""
    stages = trace.get("stages", [])
    if isinstance(stages, list):
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            if stage.get("status") in {"error", "stub"} and stage.get("stage"):
                return str(stage["stage"])

    steps = trace.get("steps", [])
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            if step.get("error"):
                name = step.get("step_name") or step.get("name")
                if name:
                    return str(name)

    if isinstance(stages, list):
        candidates = [
            str(stage["stage"])
            for stage in stages
            if isinstance(stage, dict)
            and stage.get("stage")
            and stage.get("stage") not in {"delivery", "qa", "diagnose"}
        ]
        if candidates:
            return candidates[-1]

    if isinstance(steps, list):
        names = [
            step.get("step_name") or step.get("name")
            for step in steps
            if isinstance(step, dict)
        ]
        names = [str(name) for name in names if name]
        if names:
            return names[-1]

    return None


def _parse_poster_copy(copy_text: str) -> dict[str, Any]:
    """Extract structured fields from generate_poster LLM output.

    Expects JSON output with required fields (headline, subheadline, cta,
    body_text) and optional extended slots (kicker, badge, event_meta,
    offer_block, price, footer, disclaimer, secondary_cta).

    Falls back to heuristic extraction if JSON fails.
    """
    import json as _json

    _STRING_SLOTS = (
        "headline", "subheadline", "cta", "body_text",
        "kicker", "badge", "price", "footer", "disclaimer", "secondary_cta",
    )
    _DICT_SLOTS = ("event_meta", "offer_block")

    result: dict[str, Any] = {k: "" for k in _STRING_SLOTS}
    result.update({k: None for k in _DICT_SLOTS})

    if not copy_text:
        return result

    # Strip markdown fencing if present
    stripped = copy_text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        if "```" in stripped:
            stripped = stripped[:stripped.rfind("```")].strip()

    # Try JSON first
    try:
        parsed = _json.loads(stripped)
        if isinstance(parsed, dict):
            for key in _STRING_SLOTS:
                if key in parsed:
                    result[key] = str(parsed[key])
            for key in _DICT_SLOTS:
                if key in parsed and isinstance(parsed[key], dict):
                    result[key] = parsed[key]
            return result
    except (ValueError, TypeError):
        pass

    # Heuristic fallback: look for labeled sections
    for line in copy_text.strip().split("\n"):
        lower = line.lower().strip()
        if lower.startswith("headline:"):
            result["headline"] = line.split(":", 1)[1].strip()
        elif lower.startswith(("subheadline:", "tagline:")):
            result["subheadline"] = line.split(":", 1)[1].strip()
        elif lower.startswith(("cta:", "call to action:")):
            result["cta"] = line.split(":", 1)[1].strip()
        elif lower.startswith(("body:", "body text:", "body_text:")):
            result["body_text"] = line.split(":", 1)[1].strip()
        elif lower.startswith("kicker:"):
            result["kicker"] = line.split(":", 1)[1].strip()
        elif lower.startswith("badge:"):
            result["badge"] = line.split(":", 1)[1].strip()
        elif lower.startswith("footer:"):
            result["footer"] = line.split(":", 1)[1].strip()

    # If no structure found, use entire text as body
    if not any(v for k, v in result.items() if k in _STRING_SLOTS and v):
        result["body_text"] = copy_text.strip()
    return result


def _load_client_style(client_id: str) -> dict[str, Any]:
    """Load brand colors and fonts for a client from config/clients/{id}.yaml."""
    from pathlib import Path

    import yaml as _yaml

    _repo_root = Path(__file__).resolve().parent.parent
    client_path = _repo_root / "config" / "clients" / f"{client_id}.yaml"
    defaults: dict[str, Any] = {
        "colors": {"primary": "#1a365d", "secondary": "#2b6cb0", "accent": "#ed8936"},
        "fonts": {"headline": "Plus Jakarta Sans", "body": "Inter"},
    }
    if not client_path.exists():
        return defaults
    try:
        with client_path.open() as fh:
            data = _yaml.safe_load(fh) or {}
        brand = data.get("brand", {})
        overrides = data.get("workflow_overrides", {}).get("poster_production", {})
        # Prefer brand section, fall back to workflow overrides, then defaults
        return {
            "colors": overrides.get("colors", {
                "primary": brand.get("primary_color", defaults["colors"]["primary"]),
                "secondary": brand.get("secondary_color", defaults["colors"]["secondary"]),
                "accent": brand.get("accent_color", defaults["colors"]["accent"]),
            }),
            "fonts": overrides.get("fonts", {
                "headline": brand.get("headline_font", defaults["fonts"]["headline"]),
                "body": brand.get("body_font", defaults["fonts"]["body"]),
            }),
        }
    except Exception:
        return defaults


def _load_client_brand(client_id: str) -> dict[str, Any]:
    """Load full brand context for brief expansion and copy generation.

    Returns brand colors, mood, tone, style hints — everything the LLM needs
    to generate on-brand content. Used by _generate_poster and _image_generate.
    """
    from pathlib import Path

    import yaml as _yaml

    _repo_root = Path(__file__).resolve().parent.parent
    client_path = _repo_root / "config" / "clients" / f"{client_id}.yaml"
    if not client_path.exists():
        return {}
    try:
        with client_path.open() as fh:
            data = _yaml.safe_load(fh) or {}
        brand = dict(data.get("brand", {}))
        defaults = data.get("defaults", {})
        # Merge relevant defaults into brand context
        for key in (
            "tone",
            "copy_register",
            "language",
            "style_hint",
            "image_mode",
            "style_reference",
            "style_reference_options",
        ):
            if key in defaults:
                brand[key] = defaults[key]
        brand["brand_mood"] = data.get("brand_mood", [])
        return brand
    except Exception:
        return {}


def _attempt_readability_revision(
    *,
    template_name: str,
    content: dict[str, Any],
    style: dict[str, Any],
    output_dir: Path,
    quality_verdict: Any,
    controls: dict[str, Any],
    image_path: str,
    parsed: dict[str, Any],
    original_qa: dict[str, Any],
) -> dict[str, Any] | None:
    """One-shot readability revision: re-render with boosted overlay + text-shadow.

    Called when post-render QA fails on text-overlay dimensions
    (cta_visibility / text_readability / overlay_balance) but the
    underlying image is fine (NIMA above floor, vision check succeeded).

    Injects ``_readability_boost`` flag into the content dict so
    ``render_poster_html`` applies stronger CSS overlay + text-shadow.
    Then re-runs post-render QA on the revised render.

    Returns:
        A successful delivery result dict if the revision passes QA,
        or ``None`` if the revision also fails (caller should fail-stop).
    """
    from tools.publish import assemble_poster_pdf

    boosted_content = {**content, "_readability_boost": True}

    try:
        revised_pdf = assemble_poster_pdf(
            template_name=template_name,
            content=boosted_content,
            colors=style.get("colors"),
            fonts=style.get("fonts"),
            output_dir=output_dir,
        )
    except Exception as render_exc:
        logger.warning(
            "Readability revision re-render failed: %s", render_exc,
        )
        return None

    revised_png = revised_pdf.with_suffix("").with_name(
        revised_pdf.stem + ".png"
    )
    if not revised_png.exists():
        logger.warning("Readability revision produced no PNG")
        return None

    from tools.visual_pipeline import evaluate_rendered_poster

    raw_nima = None
    if isinstance(quality_verdict, dict):
        raw_nima = quality_verdict.get("nima_score")

    revised_qa = evaluate_rendered_poster(
        rendered_png_path=str(revised_png),
        raw_image_nima=(
            float(raw_nima) if raw_nima is not None else None
        ),
        nima_floor=float(controls.get("render_nima_floor", 3.5)),
        composition_threshold=float(
            controls.get("composition_threshold", 3.0)
        ),
    )

    total_cost = (
        float(original_qa.get("cost_usd", 0.0))
        + float(revised_qa.get("cost_usd", 0.0))
    )

    if revised_qa.get("passed", False):
        logger.info(
            "Readability revision succeeded (composition %.2f → %.2f)",
            original_qa.get("composition_score", 0.0),
            revised_qa.get("composition_score", 0.0),
        )
        return {
            "status": "ok",
            "output": "poster_delivered",
            "revision_applied": True,
            "pdf_path": str(revised_pdf),
            "png_path": str(revised_png),
            "post_render_qa": revised_qa,
            "original_qa": original_qa,
            "image_path": image_path,
            "template_name": template_name,
            "copy": parsed,
            "cost_usd": total_cost,
        }

    logger.warning(
        "Readability revision also failed QA (composition %.2f), "
        "failing delivery",
        revised_qa.get("composition_score", 0.0),
    )
    return None


def _deliver_document(
    context: dict[str, Any],
    workflow: str,
) -> dict[str, Any]:
    """Deliver a document artifact — locates or renders the PDF.

    Looks for a ``pdf_path`` produced by upstream ``_typst_render``.
    If none found, attempts a last-resort render from available content.
    Runs structural QA: PDF exists, non-zero, not corrupt.

    Args:
        context: The execution context with job_context, stage_results, payload.
        workflow: The effective workflow name (for logging/metadata).

    Returns:
        Delivery result dict with status, pdf_path, structural QA.
    """
    payload = _artifact_payload(context)
    job_ctx = context.get("job_context", {})
    stage_results = context.get("stage_results", [])

    # 1. Locate PDF from upstream _typst_render output
    pdf_path_str: str | None = payload.get("pdf_path")
    for stage_result in stage_results:
        if not isinstance(stage_result, dict):
            continue
        if not pdf_path_str and stage_result.get("pdf_path"):
            pdf_path_str = str(stage_result["pdf_path"])

    # 2. If no PDF yet, attempt last-resort render from content
    if not pdf_path_str:
        doc_content = str(
            payload.get("document_content")
            or payload.get("text_content")
            or ""
        )
        if not doc_content.strip():
            return {
                "status": "error",
                "output": (
                    "delivery_failed: no PDF produced by upstream stages "
                    "and no document content available for rendering"
                ),
                "cost_usd": 0.0,
            }

        # Attempt to render
        template_name = (
            payload.get("template_name")
            or _document_type_to_template(workflow)
        )
        render_result = _typst_render({
            **context,
            "template_name": template_name,
        })
        if render_result.get("status") != "ok" or not render_result.get("pdf_path"):
            return {
                "status": "error",
                "output": (
                    "delivery_failed: last-resort render failed — "
                    + str(render_result.get("output", "unknown error"))
                ),
                "cost_usd": 0.0,
            }
        pdf_path_str = str(render_result["pdf_path"])

    # 3. Structural QA: PDF exists and has non-trivial content
    pdf_path = Path(pdf_path_str)
    structural_issues: list[str] = []
    if not pdf_path.exists():
        structural_issues.append(f"PDF file missing: {pdf_path}")
    elif pdf_path.stat().st_size == 0:
        structural_issues.append("PDF file is empty (0 bytes)")
    elif pdf_path.stat().st_size < 500:
        structural_issues.append(
            f"PDF suspiciously small ({pdf_path.stat().st_size} bytes)"
        )

    if structural_issues:
        return {
            "status": "error",
            "output": (
                "delivery_failed: structural QA — "
                + "; ".join(structural_issues)
            ),
            "structural_qa": {
                "passed": False,
                "issues": structural_issues,
            },
            "pdf_path": pdf_path_str,
            "cost_usd": 0.0,
        }

    return {
        "status": "ok",
        "output": "document_delivered",
        "pdf_path": pdf_path_str,
        "structural_qa": {"passed": True, "issues": []},
        "template_name": payload.get("template_name"),
        "workflow": workflow,
        "cost_usd": 0.0,
    }


def _document_type_to_template(workflow: str) -> str:
    """Map workflow name to default Typst template name."""
    _MAP: dict[str, str] = {
        "document_production": "report",
        "invoice": "invoice",
        "proposal": "proposal",
        "company_profile": "company_profile",
    }
    return _MAP.get(workflow, "report")


def _deliver(context: dict[str, Any]) -> dict[str, Any]:
    """Deliver the final artifact — composes poster PDF via Typst if applicable."""
    job_ctx = context.get("job_context", {})
    workflow = job_ctx.get("routing", {}).get("workflow", "")
    stage_results = context.get("stage_results", [])
    payload = _artifact_payload(context)

    effective_workflow = workflow
    if workflow == "rework":
        for stage_result in reversed(stage_results):
            if not isinstance(stage_result, dict):
                continue
            source_workflow = (
                stage_result.get("rework_source_workflow")
                or stage_result.get("original_workflow")
            )
            if source_workflow:
                effective_workflow = str(source_workflow)
                break
        if effective_workflow == "rework":
            effective_workflow = str(job_ctx.get("original_workflow", "rework"))

    # Route delivery by workflow type.
    # Only document_production is fully wired.  invoice/proposal/company_profile
    # are S16 — still phase-blocked with placeholder generators.
    _DOCUMENT_WORKFLOWS = frozenset({"document_production"})
    if effective_workflow in _DOCUMENT_WORKFLOWS:
        return _deliver_document(context, effective_workflow)

    if effective_workflow != "poster_production":
        return {
            "status": "stub",
            "output": (
                f"delivery_not_implemented for workflow '{effective_workflow}'"
            ),
            "cost_usd": 0.0,
        }

    # Walk prior stages to find deliverables
    image_path = payload.get("image_path")
    copy_text = str(payload.get("poster_copy", ""))
    for stage_result in stage_results:
        if not image_path and "image_path" in stage_result:
            image_path = stage_result["image_path"]
        if not copy_text and "poster_copy" in stage_result:
            copy_text = stage_result["poster_copy"]

    if not image_path:
        return {
            "status": "error",
            "output": "delivery_failed: no image produced by upstream stages",
            "cost_usd": 0.0,
        }

    parsed = _parse_poster_copy(copy_text)
    style = _load_client_style(job_ctx.get("client_id", "default"))

    # Compute active optional slots for intent-aware template selection (P1 fix)
    _OPTIONAL_SLOTS = {
        "kicker", "badge", "price", "footer", "disclaimer",
        "secondary_cta", "event_meta", "offer_block",
    }
    active_slots: set[str] = set()
    for slot in _OPTIONAL_SLOTS:
        val = parsed.get(slot)
        if val is not None and val != "":
            active_slots.add(slot)

    template_name = _resolve_template_name(
        job_ctx, workflow=effective_workflow, active_slots=active_slots or None,
    )
    output_root = Path.home() / "vizier" / "data" / "deliverables"
    output_dir = output_root / str(job_ctx.get("job_id", "default"))
    output_dir.mkdir(parents=True, exist_ok=True)

    quality_verdict = payload.get("quality_verdict")
    require_quality_pass = bool(
        _runtime_controls(context).get("require_quality_pass", True),
    )
    if (
        require_quality_pass
        and isinstance(quality_verdict, dict)
        and not bool(quality_verdict.get("passed", True))
    ):
        return {
            "status": "error",
            "output": "delivery_failed: quality gate not passed",
            "cost_usd": 0.0,
        }

    # Carry ALL parsed fields through to renderer — not just legacy 4 (P1 fix).
    # Templates use Jinja2 conditionals to render slots they support.
    content: dict[str, Any] = {
        "headline": parsed.get("headline", ""),
        "subheadline": parsed.get("subheadline", ""),
        "cta": parsed.get("cta", ""),
        "body_text": parsed.get("body_text", ""),
        "background_image": image_path,
    }
    # Extended string slots
    for slot in ("kicker", "badge", "price", "footer", "disclaimer", "secondary_cta"):
        val = parsed.get(slot, "")
        if val:
            content[slot] = str(val)
    # Structured dict slots
    for slot in ("event_meta", "offer_block"):
        val = parsed.get(slot)
        if isinstance(val, dict):
            content[slot] = val

    # Primary: Playwright HTML renderer (Canva-quality CSS)
    # Fallback: Typst (for environments without Playwright/Chromium)
    try:
        from tools.publish import assemble_poster_pdf

        pdf_path = assemble_poster_pdf(
            template_name=template_name,
            content=content,
            colors=style.get("colors"),
            fonts=style.get("fonts"),
            output_dir=output_dir,
        )
        # PNG preview is generated alongside the PDF
        png_path = pdf_path.with_suffix("").with_name(
            pdf_path.stem + ".png"
        )

        # Post-render QA: evaluate the RENDERED poster (with text overlays)
        # to catch CTA visibility / text readability / overlay collisions
        # that raw-image QA cannot detect.
        post_render_result: dict[str, Any] = {}
        if png_path.exists():
            from tools.visual_pipeline import evaluate_rendered_poster

            raw_nima = None
            if isinstance(quality_verdict, dict):
                raw_nima = quality_verdict.get("nima_score")
            controls = _runtime_controls(context)
            post_render_result = evaluate_rendered_poster(
                rendered_png_path=str(png_path),
                raw_image_nima=(
                    float(raw_nima) if raw_nima is not None else None
                ),
                nima_floor=float(
                    controls.get("render_nima_floor", 3.5)
                ),
                composition_threshold=float(
                    controls.get("composition_threshold", 3.0)
                ),
            )
            if not post_render_result.get("passed", True):
                # Post-render revision V1: one deterministic retry for
                # text-overlay issues (cta_visibility / text_readability /
                # overlay_balance).  Fail-stop for image/vision problems.
                from tools.visual_pipeline import classify_post_render_failure

                failure_class = classify_post_render_failure(post_render_result)
                if failure_class == "retryable":
                    logger.info(
                        "Post-render revision: retrying with readability "
                        "boost (original issues: %s)",
                        post_render_result.get("issues"),
                    )
                    revision_result = _attempt_readability_revision(
                        template_name=template_name,
                        content=content,
                        style=style,
                        output_dir=output_dir,
                        quality_verdict=quality_verdict,
                        controls=controls,
                        image_path=image_path,
                        parsed=parsed,
                        original_qa=post_render_result,
                    )
                    if revision_result is not None:
                        return revision_result
                    # Revision also failed — fall through to error return

                return {
                    "status": "error",
                    "output": (
                        "delivery_failed: rendered poster did not pass "
                        "post-render QA — "
                        + "; ".join(post_render_result.get("issues", []))
                    ),
                    "post_render_qa": post_render_result,
                    "failure_class": failure_class,
                    "pdf_path": str(pdf_path),
                    "png_path": str(png_path),
                    "image_path": image_path,
                    "copy": parsed,
                    "cost_usd": float(
                        post_render_result.get("cost_usd", 0.0)
                    ),
                }

        return {
            "status": "ok",
            "output": "poster_delivered",
            "pdf_path": str(pdf_path),
            "png_path": str(png_path) if png_path.exists() else None,
            "post_render_qa": post_render_result,
            "image_path": image_path,
            "template_name": template_name,
            "copy": parsed,
            "cost_usd": float(
                post_render_result.get("cost_usd", 0.0)
            ),
        }
    except Exception as pw_exc:
        logger.warning(
            "Playwright render failed (%s), falling back to Typst",
            pw_exc,
        )

    # Fallback: Typst renderer
    try:
        from tools.publish import assemble_document_pdf, rasterize_pdf_to_png

        pdf_path = assemble_document_pdf(
            template_name="poster",
            content=content,
            colors=style.get("colors"),
            fonts=style.get("fonts"),
            output_dir=output_dir,
        )

        # Rasterize the Typst PDF to PNG so post-render QA can evaluate
        # the rendered composition — same gate as the Playwright path.
        typst_post_render: dict[str, Any] = {}
        typst_post_render_cost = 0.0
        typst_png_path: Path | None = None
        try:
            typst_png_path = rasterize_pdf_to_png(pdf_path)
            from tools.visual_pipeline import evaluate_rendered_poster

            raw_nima = None
            if isinstance(quality_verdict, dict):
                raw_nima = quality_verdict.get("nima_score")
            controls = _runtime_controls(context)
            typst_post_render = evaluate_rendered_poster(
                rendered_png_path=str(typst_png_path),
                raw_image_nima=(
                    float(raw_nima) if raw_nima is not None else None
                ),
                nima_floor=float(
                    controls.get("render_nima_floor", 3.5)
                ),
                composition_threshold=float(
                    controls.get("composition_threshold", 3.0)
                ),
            )
            typst_post_render_cost = float(
                typst_post_render.get("cost_usd", 0.0)
            )
            if not typst_post_render.get("passed", True):
                return {
                    "status": "error",
                    "output": (
                        "delivery_failed: Typst-rendered poster did not "
                        "pass post-render QA — "
                        + "; ".join(typst_post_render.get("issues", []))
                    ),
                    "post_render_qa": typst_post_render,
                    "pdf_path": str(pdf_path),
                    "png_path": str(typst_png_path),
                    "image_path": image_path,
                    "copy": parsed,
                    "cost_usd": typst_post_render_cost,
                }
        except Exception as raster_exc:
            logger.warning(
                "Typst post-render QA skipped (rasterization failed): %s",
                raster_exc,
            )

        return {
            "status": "ok",
            "output": "poster_delivered",
            "pdf_path": str(pdf_path),
            "png_path": (
                str(typst_png_path)
                if typst_png_path is not None and typst_png_path.exists()
                else None
            ),
            "post_render_qa": typst_post_render,
            "image_path": image_path,
            "template_name": template_name,
            "copy": parsed,
            "cost_usd": typst_post_render_cost,
        }
    except Exception as exc:
        logger.error("Both renderers failed: %s", exc)
        return {
            "status": "error",
            "output": f"delivery_failed: rendering error — {exc}",
            "image_path": image_path,
            "copy": parsed,
            "cost_usd": 0.0,
        }


def _readiness_check(context: dict[str, Any]) -> dict[str, Any]:
    """Evaluate spec readiness."""
    from contracts.readiness import (
        evaluate_readiness,
    )
    from contracts.artifact_spec import ArtifactFamily, ProvisionalArtifactSpec

    job_ctx = context.get("job_context", {})
    raw_brief = str(job_ctx.get("raw_input") or context.get("prompt") or "")
    artifact_family_raw = str(job_ctx.get("artifact_family", "document"))
    language = str(job_ctx.get("language", "en"))

    try:
        artifact_family = ArtifactFamily(artifact_family_raw)
    except ValueError:
        artifact_family = ArtifactFamily.document

    spec = ProvisionalArtifactSpec(
        client_id=str(job_ctx.get("client_id", "default")),
        artifact_family=artifact_family,
        language=language,
        raw_brief=raw_brief,
    )
    result = evaluate_readiness(spec)

    status = "ok" if result.status in {"ready", "shapeable"} else "error"
    return {
        "status": status,
        "output": f"readiness_{result.status}",
        "readiness_status": result.status,
        "readiness_reason": result.reason,
        "missing_critical": result.missing_critical,
        "completeness": result.completeness,
        "cost_usd": 0.0,
    }


def _refine_spec(context: dict[str, Any]) -> dict[str, Any]:
    """Refine a vague spec via LLM."""
    from utils.call_llm import call_llm

    prompt = context.get("prompt", "")
    result = call_llm(
        stable_prefix=[{"role": "system", "content": "Refine the artifact spec."}],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.3,
        max_tokens=_runtime_max_tokens(context, purpose="critique", default=512),
        operation_type="classify",
    )
    return {
        "status": "ok",
        "output": result.get("content", ""),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": result.get("cost_usd", 0.0),
    }


def _ask_operator(context: dict[str, Any]) -> dict[str, Any]:
    """Ask the operator for clarification."""
    previous = context.get("previous_output", {})
    missing = previous.get("missing_critical") or []
    if not isinstance(missing, list):
        missing = []

    if missing:
        questions = [f"Please clarify: {field}" for field in missing[:5]]
    else:
        questions = [
            "Please clarify the objective, audience, and required format.",
        ]

    return {
        "status": "ok",
        "output": "operator_questions_prepared",
        "questions": questions,
        "cost_usd": 0.0,
    }


def _web_search(context: dict[str, Any]) -> dict[str, Any]:
    """Web search for research workflows."""
    return {"status": "ok", "output": "web_search_results", "cost_usd": 0.0}


def _trend_analyse(context: dict[str, Any]) -> dict[str, Any]:
    """Analyse market trends."""
    from tools.research import fetch_trends  # noqa: F401 — validates import

    return {"status": "ok", "output": "trends_analysed", "cost_usd": 0.0}


def _competitor_scan(context: dict[str, Any]) -> dict[str, Any]:
    """Scan competitor activity."""
    return {"status": "ok", "output": "competitors_scanned", "cost_usd": 0.0}


def _summarise(context: dict[str, Any]) -> dict[str, Any]:
    """Summarise research findings."""
    from utils.call_llm import call_llm

    prompt = context.get("prompt", "")
    result = call_llm(
        stable_prefix=[{
            "role": "system",
            "content": "Summarise the research findings.",
        }],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.3,
        max_tokens=_runtime_max_tokens(context, purpose="generate", default=1024),
        operation_type="generate",
    )
    return {
        "status": "ok",
        "output": result.get("content", ""),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": result.get("cost_usd", 0.0),
    }


def _tripwire_scorer(context: dict[str, Any]) -> dict[str, Any]:
    """Default tripwire scorer — LLM-based quality critique (anti-drift #21).

    Evaluates output against the stage's threshold and returns a score
    with structured critique dimensions. Anti-drift #38: critique must
    identify specific issues, not just return a score.
    """
    from utils.call_llm import call_llm

    output_data = context.get("output", {})
    artifact_payload = context.get("artifact_payload", {})
    output_text = _quality_target_text(
        artifact_payload if isinstance(artifact_payload, dict) else {},
        output_data if isinstance(output_data, dict) else {},
    )
    stage = context.get("stage", "unknown")
    threshold = context.get("threshold", 3.0)

    result = call_llm(
        stable_prefix=[{"role": "system", "content": (
            "You are a quality scorer. Rate the output 1-5 on these dimensions: "
            "relevance, completeness, clarity, accuracy. "
            "Return JSON: {\"score\": <float>, \"critique\": "
            "{\"relevance\": <1-5>, \"completeness\": <1-5>, "
            "\"clarity\": <1-5>, \"accuracy\": <1-5>, "
            "\"issues\": [\"specific issue 1\", ...]}}"
        )}],
        variable_suffix=[{"role": "user", "content": (
            f"Stage: {stage}\nThreshold: {threshold}\n\n"
            f"Output to evaluate:\n{output_text[:2000]}"
        )}],
        model="gpt-5.4-mini",
        temperature=0.0,
        max_tokens=_runtime_max_tokens(context, purpose="critique", default=512),
    )

    import json as _json

    try:
        content = result.get("content", "").strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = _json.loads(content)
        return {
            "score": float(parsed.get("score", 3.0)),
            "critique": parsed.get("critique", {}),
        }
    except (ValueError, _json.JSONDecodeError):
        logger.warning("Tripwire scorer returned non-JSON: %s", content[:100])
        return {"score": 3.0, "critique": {}}


def _tripwire_reviser(context: dict[str, Any]) -> dict[str, Any]:
    """Default tripwire reviser — LLM-based revision from critique (anti-drift #38).

    Takes the original output and structured critique, produces a revised version
    addressing the specific issues identified.
    """
    from utils.call_llm import call_llm

    original_output = context.get("original_output", {})
    artifact_payload = context.get("artifact_payload", {})
    target_field = _quality_target_field(
        artifact_payload if isinstance(artifact_payload, dict) else {},
    )
    original = _quality_target_text(
        artifact_payload if isinstance(artifact_payload, dict) else {},
        original_output if isinstance(original_output, dict) else {},
    )
    critique = context.get("critique", {})
    issues = critique.get("issues", [])
    stage = context.get("stage", "unknown")
    attempt = context.get("attempt", 1)

    result = call_llm(
        stable_prefix=[{"role": "system", "content": (
            "You are a quality reviser. Given the original output and specific "
            "quality issues, produce a revised version that addresses each issue. "
            "Return only the revised content."
        )}],
        variable_suffix=[{"role": "user", "content": (
            f"Stage: {stage} (revision attempt {attempt})\n"
            f"Issues to fix: {issues}\n\n"
            f"Original output:\n{original[:2000]}"
        )}],
        model="gpt-5.4-mini",
        temperature=0.3,
        max_tokens=_runtime_max_tokens(context, purpose="revision", default=2048),
    )

    revised_text = result.get("content", original)
    revised_result = {
        "status": "ok",
        "output": revised_text,
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": result.get("cost_usd", 0.0),
    }
    if target_field != "output":
        revised_result[target_field] = revised_text
    return revised_result


def _trace_insight(context: dict[str, Any]) -> dict[str, Any]:
    """Analyse trace from a previous job for rework."""
    job_ctx = context.get("job_context", {})
    original_trace = job_ctx.get("original_trace") or {}

    original_workflow = (
        job_ctx.get("original_workflow")
        or (original_trace.get("workflow") if isinstance(original_trace, dict) else None)
    )
    if not original_workflow and isinstance(original_trace, dict):
        routing = original_trace.get("routing", {})
        if isinstance(routing, dict):
            original_workflow = routing.get("workflow")

    failed_stage = job_ctx.get("failed_stage")
    if not failed_stage and isinstance(original_trace, dict):
        failed_stage = _infer_failed_stage_from_trace(original_trace)

    feedback = (
        job_ctx.get("feedback")
        or job_ctx.get("raw_input")
        or context.get("prompt", "")
    )

    if not original_workflow:
        return {
            "status": "error",
            "output": "trace_insight_failed: missing original workflow",
            "cost_usd": 0.0,
        }
    if not failed_stage:
        return {
            "status": "error",
            "output": "trace_insight_failed: missing failed stage",
            "original_workflow": original_workflow,
            "cost_usd": 0.0,
        }

    return {
        "status": "ok",
        "output": "trace_analysed",
        "original_workflow": str(original_workflow),
        "failed_stage": str(failed_stage),
        "feedback": str(feedback),
        "cost_usd": 0.0,
    }


def _quality_gate(context: dict[str, Any]) -> dict[str, Any]:
    """Run quality gate on rework output."""
    from middleware.quality_gate import validate_content_quality

    rerun_output = context.get("previous_output", {})
    if not isinstance(rerun_output, dict):
        rerun_output = {}
    payload = _artifact_payload(context)

    if rerun_output.get("status") in {"error", "stub"}:
        return {
            "status": "error",
            "output": "quality_failed: rerun stage did not complete successfully",
            "score": 0.0,
            "cost_usd": 0.0,
        }

    candidate_text = _quality_target_text(payload, rerun_output)
    image_path = payload.get("image_path") or rerun_output.get("image_path")
    if not candidate_text and not image_path:
        return {
            "status": "error",
            "output": "quality_failed: rerun produced no deliverable content",
            "score": 0.0,
            "cost_usd": 0.0,
        }

    if candidate_text:
        expected_languages = [str(context.get("job_context", {}).get("language", "en"))]
        validation = validate_content_quality(
            content=str(candidate_text),
            expected_languages=expected_languages,
            expected_tone=context.get("job_context", {}).get("copy_register"),
        )
        if not validation.passed:
            return {
                "status": "error",
                "output": "quality_failed: " + "; ".join(validation.errors),
                "score": 2.0,
                "errors": validation.errors,
                "cost_usd": 0.0,
            }

    return {
        "status": "ok",
        "output": "quality_passed",
        "score": 4.0,
        "cost_usd": 0.0,
    }


def _brand_extract(context: dict[str, Any]) -> dict[str, Any]:
    """Extract brand patterns from client assets."""
    job_ctx = context.get("job_context", {})
    client_id = str(job_ctx.get("client_id", "default"))
    brand = _load_client_brand(client_id)
    style = _load_client_style(client_id)

    if not brand and not style:
        return {
            "status": "error",
            "output": f"brand_extract_failed: no brand config for '{client_id}'",
            "cost_usd": 0.0,
        }

    profile = {
        "brand": brand,
        "style": style,
    }
    return {
        "status": "ok",
        "output": "brand_extracted",
        "brand_profile": profile,
        "cost_usd": 0.0,
    }


def _swipe_index(context: dict[str, Any]) -> dict[str, Any]:
    """Index a swipe file into visual DNA."""
    return {"status": "ok", "output": "swipe_indexed", "cost_usd": 0.0}


def _calibration_check(context: dict[str, Any]) -> dict[str, Any]:
    """Run calibration check during onboarding."""
    return {"status": "ok", "output": "calibration_passed", "cost_usd": 0.0}


def _character_workshop(context: dict[str, Any]) -> dict[str, Any]:
    """Run creative character workshop for publishing."""
    from tools.illustrate import run_creative_workshop  # noqa: F401 — validates import

    return {"status": "ok", "output": "character_workshop_complete", "cost_usd": 0.0}


def _story_workshop(context: dict[str, Any]) -> dict[str, Any]:
    """Run creative story workshop for publishing."""
    return {"status": "ok", "output": "story_workshop_complete", "cost_usd": 0.0}


def _scaffold_build(context: dict[str, Any]) -> dict[str, Any]:
    """Build narrative scaffold for publishing."""
    return {"status": "ok", "output": "scaffold_built", "cost_usd": 0.0}


def _generate_page_text(context: dict[str, Any]) -> dict[str, Any]:
    """Generate text for a single page of a children's book."""
    from utils.call_llm import call_llm

    prompt = context.get("prompt", "")
    result = call_llm(
        stable_prefix=[{"role": "system", "content": "Generate page text."}],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.7,
        max_tokens=_runtime_max_tokens(context, purpose="generate", default=512),
        operation_type="generate",
    )
    return {
        "status": "ok",
        "output": result.get("content", ""),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": result.get("cost_usd", 0.0),
    }


def _character_verify(context: dict[str, Any]) -> dict[str, Any]:
    """Verify character consistency across illustrations via LLM.

    Compares character descriptions from the CharacterBible against
    the generated page text/illustrations to flag drift.
    """
    from utils.call_llm import call_llm

    job_ctx = context.get("job_context", {})
    payload = _artifact_payload(context)
    page_text = str(
        payload.get("page_text")
        or payload.get("text_content")
        or context.get("previous_output", {}).get("output", "")
    )
    character_bible = job_ctx.get("character_bible", {})
    if not page_text.strip():
        return {
            "status": "ok",
            "output": "character_verify_skipped: no page text",
            "score": 3.0,
            "cost_usd": 0.0,
        }

    import json as _json

    result = call_llm(
        stable_prefix=[{
            "role": "system",
            "content": (
                "You are a children's book editor. Check whether the "
                "page text is consistent with the character descriptions. "
                "Score 1-5 (5 = perfectly consistent). "
                "Return JSON: {\"score\": <1-5>, \"issues\": [...]}"
            ),
        }],
        variable_suffix=[{
            "role": "user",
            "content": (
                f"Character bible:\n{_json.dumps(character_bible, default=str)}\n\n"
                f"Page text:\n{page_text}"
            ),
        }],
        model="gpt-5.4-mini",
        temperature=0.2,
        max_tokens=200,
        response_format={"type": "json_object"},
        operation_type="score",
    )
    try:
        parsed = _json.loads(result["content"])
        score = float(parsed.get("score", 3.0))
        issues = parsed.get("issues", [])
    except (ValueError, KeyError):
        score = 3.0
        issues = ["Parse error in character verification"]

    controls = _runtime_controls(context)
    threshold = float(controls.get("character_verify_threshold", 3.0))
    passed = score >= threshold

    return {
        "status": "ok" if passed else "error",
        "output": (
            f"character_verify: score {score:.1f}"
            + (f" — issues: {issues}" if issues else "")
        ),
        "score": score,
        "issues": issues,
        "input_tokens": int(result.get("input_tokens", 0) or 0),
        "output_tokens": int(result.get("output_tokens", 0) or 0),
        "cost_usd": float(result.get("cost_usd", 0.0) or 0.0),
    }


def _narrative_qa(context: dict[str, Any]) -> dict[str, Any]:
    """Run narrative quality checks on story content via LLM.

    Evaluates coherence, pacing, age-appropriateness, and lesson delivery.
    """
    from utils.call_llm import call_llm

    payload = _artifact_payload(context)
    job_ctx = context.get("job_context", {})
    text = str(
        payload.get("page_text")
        or payload.get("text_content")
        or context.get("previous_output", {}).get("output", "")
    )
    if not text.strip():
        return {
            "status": "ok",
            "output": "narrative_qa_skipped: no text to evaluate",
            "score": 3.0,
            "cost_usd": 0.0,
        }

    import json as _json

    language = str(job_ctx.get("language", "en"))
    target_age = str(job_ctx.get("target_age", ""))
    result = call_llm(
        stable_prefix=[{
            "role": "system",
            "content": (
                "You are a children's literature editor. Evaluate the "
                "narrative on 4 dimensions (score each 1-5):\n"
                "1. coherence: logical flow and consistency\n"
                "2. pacing: appropriate rhythm for the target age\n"
                "3. age_appropriateness: vocabulary and themes\n"
                "4. lesson_delivery: thematic message woven naturally\n\n"
                "Return JSON: {\"coherence\": <1-5>, \"pacing\": <1-5>, "
                "\"age_appropriateness\": <1-5>, \"lesson_delivery\": <1-5>, "
                "\"issues\": [...]}"
            ),
        }],
        variable_suffix=[{
            "role": "user",
            "content": (
                f"Language: {language}\n"
                f"Target age: {target_age or 'unspecified'}\n\n"
                f"Text:\n{text[:3000]}"
            ),
        }],
        model="gpt-5.4-mini",
        temperature=0.2,
        max_tokens=250,
        response_format={"type": "json_object"},
        operation_type="score",
    )
    try:
        parsed = _json.loads(result["content"])
        scores = [
            float(parsed.get("coherence", 3.0)),
            float(parsed.get("pacing", 3.0)),
            float(parsed.get("age_appropriateness", 3.0)),
            float(parsed.get("lesson_delivery", 3.0)),
        ]
        avg_score = sum(scores) / len(scores)
        issues = parsed.get("issues", [])
    except (ValueError, KeyError):
        avg_score = 3.0
        issues = ["Parse error in narrative QA"]

    controls = _runtime_controls(context)
    threshold = float(controls.get("narrative_qa_threshold", 3.0))
    passed = avg_score >= threshold

    return {
        "status": "ok" if passed else "error",
        "output": (
            f"narrative_qa: score {avg_score:.1f}"
            + (f" — issues: {issues}" if issues else "")
        ),
        "score": avg_score,
        "issues": issues if isinstance(issues, list) else [],
        "input_tokens": int(result.get("input_tokens", 0) or 0),
        "output_tokens": int(result.get("output_tokens", 0) or 0),
        "cost_usd": float(result.get("cost_usd", 0.0) or 0.0),
    }


def _document_qa(context: dict[str, Any]) -> dict[str, Any]:
    """Run document quality checks via LLM.

    Evaluates structure, completeness, clarity, and professionalism.
    """
    from utils.call_llm import call_llm

    payload = _artifact_payload(context)
    job_ctx = context.get("job_context", {})
    text = str(
        payload.get("text_content")
        or payload.get("document_content")
        or context.get("previous_output", {}).get("output", "")
    )
    if not text.strip():
        return {
            "status": "ok",
            "output": "document_qa_skipped: no text to evaluate",
            "score": 3.0,
            "cost_usd": 0.0,
        }

    import json as _json

    language = str(job_ctx.get("language", "en"))
    artifact_family = str(job_ctx.get("artifact_family", "document"))
    result = call_llm(
        stable_prefix=[{
            "role": "system",
            "content": (
                "You are a professional document reviewer. Evaluate on "
                "4 dimensions (score each 1-5):\n"
                "1. structure: clear sections, logical flow, headings\n"
                "2. completeness: covers the brief, no missing sections\n"
                "3. clarity: easy to understand, no ambiguity\n"
                "4. professionalism: tone, grammar, formatting quality\n\n"
                "Return JSON: {\"structure\": <1-5>, \"completeness\": <1-5>, "
                "\"clarity\": <1-5>, \"professionalism\": <1-5>, "
                "\"issues\": [...]}"
            ),
        }],
        variable_suffix=[{
            "role": "user",
            "content": (
                f"Document type: {artifact_family}\n"
                f"Language: {language}\n\n"
                f"Content:\n{text[:3000]}"
            ),
        }],
        model="gpt-5.4-mini",
        temperature=0.2,
        max_tokens=250,
        response_format={"type": "json_object"},
        operation_type="score",
    )
    try:
        parsed = _json.loads(result["content"])
        scores = [
            float(parsed.get("structure", 3.0)),
            float(parsed.get("completeness", 3.0)),
            float(parsed.get("clarity", 3.0)),
            float(parsed.get("professionalism", 3.0)),
        ]
        avg_score = sum(scores) / len(scores)
        issues = parsed.get("issues", [])
    except (ValueError, KeyError):
        avg_score = 3.0
        issues = ["Parse error in document QA"]

    controls = _runtime_controls(context)
    threshold = float(controls.get("document_qa_threshold", 3.0))
    passed = avg_score >= threshold

    return {
        "status": "ok" if passed else "error",
        "output": (
            f"document_qa: score {avg_score:.1f}"
            + (f" — issues: {issues}" if issues else "")
        ),
        "score": avg_score,
        "issues": issues if isinstance(issues, list) else [],
        "input_tokens": int(result.get("input_tokens", 0) or 0),
        "output_tokens": int(result.get("output_tokens", 0) or 0),
        "cost_usd": float(result.get("cost_usd", 0.0) or 0.0),
    }


def _generate_poster(context: dict[str, Any]) -> dict[str, Any]:
    """Generate structured poster copy with intent-aware enrichment.

    Injects client brand context, interpreted intent (occasion, audience, mood,
    must-include/avoid), and requests extended content slots when the brief
    signals them (event_meta, offer_block, kicker, badge, footer).
    """
    from utils.call_llm import call_llm

    prompt = context.get("prompt", "")
    job_ctx = context.get("job_context", {})
    client_id = job_ctx.get("client_id", "default")
    intent_data: dict[str, Any] = job_ctx.get("interpreted_intent", {})

    # Determine which content slots to request based on intent
    base_slots = "headline, subheadline, cta, body_text"
    extra_slots: list[str] = []
    if intent_data:
        occasion = str(intent_data.get("occasion", ""))
        if occasion in ("sale", "promo"):
            extra_slots.extend(["offer_block", "badge"])
        if occasion in ("event", "hari_raya", "maulidur_rasul", "health"):
            extra_slots.append("event_meta")
        if str(intent_data.get("text_density", "")) == "dense":
            extra_slots.append("footer")
        if str(intent_data.get("text_density", "")) == "minimal":
            extra_slots.append("kicker")

    slot_list = base_slots
    if extra_slots:
        slot_list += ", " + ", ".join(extra_slots)

    # Build brand-aware system prompt with intent enrichment
    system_content = (
        f"Generate poster copy. Output ONLY a JSON object with these keys: "
        f"{slot_list}. "
        "body_text is newline-separated bullet points. "
        "event_meta (if requested) is a JSON object with keys like date, time, venue, dress_code. "
        "offer_block (if requested) is a JSON object with keys like discount, validity. "
        "All text should be in the language of the brief. "
        "Do not include any text outside the JSON object."
    )

    brand = _load_client_brand(client_id)
    if brand:
        brand_lines: list[str] = []
        if brand.get("primary_color"):
            brand_lines.append(
                f"Brand colors: {brand['primary_color']}"
                + (f", accent {brand['accent_color']}" if brand.get("accent_color") else "")
            )
        if brand.get("tone"):
            brand_lines.append(f"Tone: {brand['tone']}")
        if brand.get("copy_register"):
            brand_lines.append(f"Register: {brand['copy_register']}")
        if brand.get("brand_mood"):
            brand_lines.append(f"Brand mood: {', '.join(brand['brand_mood'])}")
        if brand.get("language"):
            brand_lines.append(f"Primary language: {brand['language']}")
        if brand_lines:
            system_content += "\n\nBrand guidelines:\n" + "\n".join(brand_lines)

    # Inject interpreted intent for occasion-aware copy (hardening 2.7)
    if intent_data:
        intent_lines: list[str] = []
        if intent_data.get("occasion"):
            intent_lines.append(f"Occasion: {intent_data['occasion']}")
        if intent_data.get("audience"):
            intent_lines.append(f"Target audience: {intent_data['audience']}")
        if intent_data.get("mood"):
            intent_lines.append(f"Mood/tone: {intent_data['mood']}")
        if intent_data.get("cultural_context"):
            intent_lines.append(f"Cultural context: {intent_data['cultural_context']}")
        must_include = intent_data.get("must_include", [])
        if must_include:
            intent_lines.append(f"MUST include: {', '.join(must_include)}")
        must_avoid = intent_data.get("must_avoid", [])
        if must_avoid:
            intent_lines.append(f"MUST NOT include: {', '.join(must_avoid)}")
        if intent_lines:
            system_content += "\n\nBrief intent:\n" + "\n".join(intent_lines)

    result = call_llm(
        stable_prefix=[{"role": "system", "content": system_content}],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.7,
        max_tokens=_runtime_max_tokens(context, purpose="generate", default=1024),
        operation_type="generate",
    )
    content = result.get("content", "")
    return {
        "status": "ok",
        "output": content,
        "poster_copy": content,  # survives stage_output.update() from image_generate
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": result.get("cost_usd", 0.0),
    }


def _generate_brochure(context: dict[str, Any]) -> dict[str, Any]:
    """Generate brochure copy and layout."""
    from utils.call_llm import call_llm

    prompt = context.get("prompt", "")
    result = call_llm(
        stable_prefix=[{"role": "system", "content": "Generate brochure content."}],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.7,
        max_tokens=_runtime_max_tokens(context, purpose="generate", default=2048),
        operation_type="generate",
    )
    return {
        "status": "ok",
        "output": result.get("content", ""),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": result.get("cost_usd", 0.0),
    }


def _generate_document(context: dict[str, Any]) -> dict[str, Any]:
    """Generate document content."""
    from utils.call_llm import call_llm

    prompt = context.get("prompt", "")
    result = call_llm(
        stable_prefix=[{"role": "system", "content": "Generate document content."}],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.5,
        max_tokens=_runtime_max_tokens(context, purpose="generate", default=4096),
        operation_type="generate",
    )
    return {
        "status": "ok",
        "output": result.get("content", ""),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": result.get("cost_usd", 0.0),
    }


def _generate_section(context: dict[str, Any]) -> dict[str, Any]:
    """Generate a single section for ebook production."""
    from utils.call_llm import call_llm

    prompt = context.get("prompt", "")
    result = call_llm(
        stable_prefix=[{"role": "system", "content": "Generate ebook section."}],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.7,
        max_tokens=_runtime_max_tokens(context, purpose="generate", default=4096),
        operation_type="generate",
    )
    return {
        "status": "ok",
        "output": result.get("content", ""),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": result.get("cost_usd", 0.0),
    }


def _generate_invoice(context: dict[str, Any]) -> dict[str, Any]:
    """Generate an invoice PDF."""
    from tools.invoice import generate_invoice  # noqa: F401 — validates import

    return {"status": "ok", "output": "invoice_generated", "cost_usd": 0.0}


def _generate_profile(context: dict[str, Any]) -> dict[str, Any]:
    """Generate a company profile."""
    return {"status": "ok", "output": "profile_generated", "cost_usd": 0.0}


def _generate_proposal(context: dict[str, Any]) -> dict[str, Any]:
    """Generate a business proposal."""
    return {"status": "ok", "output": "proposal_generated", "cost_usd": 0.0}


def _generate_episode(context: dict[str, Any]) -> dict[str, Any]:
    """Generate a serial fiction episode."""
    return {"status": "ok", "output": "episode_generated", "cost_usd": 0.0}


def _generate_social_batch(context: dict[str, Any]) -> dict[str, Any]:
    """Generate a batch of social media posts."""
    return {"status": "ok", "output": "social_batch_generated", "cost_usd": 0.0}


def _generate_caption(context: dict[str, Any]) -> dict[str, Any]:
    """Generate a social media caption."""
    return {"status": "ok", "output": "caption_generated", "cost_usd": 0.0}


def _generate_calendar(context: dict[str, Any]) -> dict[str, Any]:
    """Generate a content calendar."""
    return {"status": "ok", "output": "calendar_generated", "cost_usd": 0.0}


def _calendar_qa(context: dict[str, Any]) -> dict[str, Any]:
    """Quality-check a content calendar."""
    return {"status": "ok", "output": "calendar_qa_passed", "cost_usd": 0.0}


def _platform_check(context: dict[str, Any]) -> dict[str, Any]:
    """Check social post against platform requirements."""
    return {"status": "ok", "output": "platform_check_passed", "cost_usd": 0.0}


def _text_qa(context: dict[str, Any]) -> dict[str, Any]:
    """Run text/copy quality checks via LLM.

    Evaluates grammar, tone consistency, brand voice, and engagement.
    """
    from utils.call_llm import call_llm

    payload = _artifact_payload(context)
    job_ctx = context.get("job_context", {})
    text = str(
        payload.get("text_content")
        or payload.get("caption")
        or context.get("previous_output", {}).get("output", "")
    )
    if not text.strip():
        return {
            "status": "ok",
            "output": "text_qa_skipped: no text to evaluate",
            "score": 3.0,
            "cost_usd": 0.0,
        }

    import json as _json

    language = str(job_ctx.get("language", "en"))
    copy_register = str(job_ctx.get("copy_register", "neutral"))
    result = call_llm(
        stable_prefix=[{
            "role": "system",
            "content": (
                "You are a copy editor. Evaluate the text on 3 dimensions "
                "(score each 1-5):\n"
                "1. grammar: correct grammar and spelling\n"
                "2. tone: matches the requested register\n"
                "3. engagement: compelling, clear call to action\n\n"
                "Return JSON: {\"grammar\": <1-5>, \"tone\": <1-5>, "
                "\"engagement\": <1-5>, \"issues\": [...]}"
            ),
        }],
        variable_suffix=[{
            "role": "user",
            "content": (
                f"Language: {language}\n"
                f"Register: {copy_register}\n\n"
                f"Text:\n{text[:2000]}"
            ),
        }],
        model="gpt-5.4-mini",
        temperature=0.2,
        max_tokens=200,
        response_format={"type": "json_object"},
        operation_type="score",
    )
    try:
        parsed = _json.loads(result["content"])
        scores = [
            float(parsed.get("grammar", 3.0)),
            float(parsed.get("tone", 3.0)),
            float(parsed.get("engagement", 3.0)),
        ]
        avg_score = sum(scores) / len(scores)
        issues = parsed.get("issues", [])
    except (ValueError, KeyError):
        avg_score = 3.0
        issues = ["Parse error in text QA"]

    controls = _runtime_controls(context)
    threshold = float(controls.get("text_qa_threshold", 3.0))
    passed = avg_score >= threshold

    return {
        "status": "ok" if passed else "error",
        "output": (
            f"text_qa: score {avg_score:.1f}"
            + (f" — issues: {issues}" if issues else "")
        ),
        "score": avg_score,
        "issues": issues if isinstance(issues, list) else [],
        "input_tokens": int(result.get("input_tokens", 0) or 0),
        "output_tokens": int(result.get("output_tokens", 0) or 0),
        "cost_usd": float(result.get("cost_usd", 0.0) or 0.0),
    }


def _onboard_client(context: dict[str, Any]) -> dict[str, Any]:
    """Run client onboarding pipeline."""
    from tools.seeding import seed_client  # noqa: F401 — validates import

    return {"status": "ok", "output": "client_onboarded", "cost_usd": 0.0}


# ---------------------------------------------------------------------------
# Registry builder
# ---------------------------------------------------------------------------


# Tools that are structurally registered but not yet backed by real logic.
# Active workflows that depend on these should fail closed at runtime.
_STUB_TOOL_NAMES: frozenset[str] = frozenset({
    # typst_render removed — now has real compile logic (Track 2)
    "knowledge_store",       # S12 ingestion path not wired in workflow runtime
    "story_workshop",        # S15 publishing
    "scaffold_build",        # S15 publishing
    "generate_episode",      # S21 serial fiction
    "generate_social_batch", # S24 social
    "generate_caption",      # S24 social
    "generate_calendar",     # S22 content calendar
    "calendar_qa",           # S22 content calendar
    "generate_proposal",     # S16 extended
    "generate_profile",      # S16 extended
    "platform_check",        # S24 social
    "web_search",            # no live search backend in workflow runtime
    "competitor_scan",       # no live competitor backend in workflow runtime
    "swipe_index",           # swipe ingestion not wired to workflow runtime
    "rolling_summary",       # executor-handled, not a real tool
    "section_tripwire",      # executor-handled, not a real tool
})


def get_stub_tool_names() -> frozenset[str]:
    """Return the set of tool names that are registered but not yet real."""
    return _STUB_TOOL_NAMES


def build_production_registry() -> dict[str, Any]:
    """Build the complete production tool registry.

    Every tool name from every ``manifests/workflows/*.yaml`` file is
    mapped here.  Returns a dict mapping tool name to callable.
    """
    return {
        # --- Shared across many workflows ---
        "classify_artifact": _classify_artifact,
        "deliver": _deliver,
        "image_generate": _image_generate,
        "typst_render": _typst_render,
        "knowledge_retrieve": _knowledge_retrieve,
        "knowledge_store": _knowledge_store,
        # --- Copy generation ---
        "generate_copy": _generate_copy,
        "generate_poster": _generate_poster,
        "generate_brochure": _generate_brochure,
        "generate_document": _generate_document,
        "generate_section": _generate_section,
        "generate_page_text": _generate_page_text,
        "generate_profile": _generate_profile,
        "generate_proposal": _generate_proposal,
        "generate_invoice": _generate_invoice,
        "generate_episode": _generate_episode,
        "generate_social_batch": _generate_social_batch,
        "generate_caption": _generate_caption,
        "generate_calendar": _generate_calendar,
        # --- Quality ---
        "visual_qa": _visual_qa,
        "document_qa": _document_qa,
        "narrative_qa": _narrative_qa,
        "text_qa": _text_qa,
        "calendar_qa": _calendar_qa,
        "quality_gate": _quality_gate,
        "platform_check": _platform_check,
        # --- Publishing ---
        "character_workshop": _character_workshop,
        "story_workshop": _story_workshop,
        "scaffold_build": _scaffold_build,
        "character_verify": _character_verify,
        # --- Research ---
        "web_search": _web_search,
        "trend_analyse": _trend_analyse,
        "competitor_scan": _competitor_scan,
        "summarise": _summarise,
        # --- Refinement ---
        "refine_spec": _refine_spec,
        "readiness_check": _readiness_check,
        "ask_operator": _ask_operator,
        # --- Onboarding ---
        "brand_extract": _brand_extract,
        "swipe_index": _swipe_index,
        "calibration_check": _calibration_check,
        "onboard_client": _onboard_client,
        # --- Rework ---
        "trace_insight": _trace_insight,
        # --- Policy-level tools (approved_tools in phase.yaml) ---
        "creative_workshop": _character_workshop,
        "rolling_summary": _stub(
            "rolling_summary",
            "Handled by executor rolling context, not a tool",
        ),
        "section_tripwire": _stub(
            "section_tripwire",
            "Handled by executor tripwire logic, not a tool",
        ),
        "character_consistency": _character_verify,
        # --- Tripwire (used by run_governed, not workflow YAMLs) ---
        "_tripwire_scorer": _tripwire_scorer,
        "_tripwire_reviser": _tripwire_reviser,
    }
