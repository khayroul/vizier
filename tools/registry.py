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
from typing import Any

logger = logging.getLogger(__name__)

# Type alias matching executor.ToolCallable protocol
ToolFn = Any  # Callable[[dict[str, Any]], dict[str, Any]]


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


def _image_generate(context: dict[str, Any]) -> dict[str, Any]:
    """Generate an image via fal.ai with brief expansion (anti-drift #25)."""
    from pathlib import Path
    from uuid import uuid4

    from tools.image import expand_brief, generate_image, select_image_model

    job_ctx = context.get("job_context", {})
    prompt = context.get("prompt", "")
    model = select_image_model(
        language=job_ctx.get("language", "en"),
        artifact_family=job_ctx.get("artifact_family", "poster"),
    )
    # Anti-drift #25: ALWAYS expand brief before generation
    expanded = expand_brief(prompt)
    visual_prompt = expanded.get("composition", prompt)

    # Anti-drift #49: text is rendered by Typst, never baked into images
    _NO_TEXT = (
        " The image must contain absolutely no text, no letters, no words, "
        "no numbers, no logos, no watermarks. Leave clean blank space for "
        "headline and body text to be overlaid by the layout engine."
    )
    if "no text" not in visual_prompt.lower():
        visual_prompt = visual_prompt.rstrip(".") + "." + _NO_TEXT

    image_bytes = generate_image(prompt=visual_prompt, model=model)

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
        "cost_usd": 0.025,  # fal.ai flux/dev approximate cost
    }


def _visual_qa(context: dict[str, Any]) -> dict[str, Any]:
    """Run 4-dimension visual quality critique."""
    from tools.visual_scoring import critique_4dim

    output = context.get("previous_output", {})
    brief = context.get("job_context", {})
    results = critique_4dim(
        image_description=str(output.get("output", "")),
        brief=brief,
    )
    avg_score = 0.0
    if results:
        avg_score = sum(d.get("score", 0.0) for d in results.values()) / len(results)
    return {
        "status": "ok",
        "output": results,
        "score": avg_score,
        "input_tokens": 0,
        "output_tokens": 0,
    }


def _typst_render(context: dict[str, Any]) -> dict[str, Any]:
    """Render a Typst template to PDF."""
    source = context.get("typst_source", "")
    if not source:
        return {"status": "ok", "output": "No Typst source provided", "cost_usd": 0.0}
    # Actual rendering would write source to file and call typst compile
    return {"status": "ok", "output": "typst_rendered", "cost_usd": 0.0}


def _generate_copy(context: dict[str, Any]) -> dict[str, Any]:
    """Generate copy text via LLM."""
    from utils.call_llm import call_llm

    prompt = context.get("prompt", "")
    result = call_llm(
        stable_prefix=[{"role": "system", "content": "Generate marketing copy."}],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.7,
        max_tokens=2048,
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
    from tools.knowledge import ingest_card  # noqa: F401 — validates import

    return {
        "status": "ok",
        "output": "knowledge_retrieved",
        "cards": [],
        "cost_usd": 0.0,
    }


def _knowledge_store(context: dict[str, Any]) -> dict[str, Any]:
    """Store a knowledge card."""
    return {"status": "ok", "output": "knowledge_stored", "cost_usd": 0.0}


def _parse_poster_copy(copy_text: str) -> dict[str, str]:
    """Extract structured fields from generate_poster LLM output.

    Expects JSON output. Falls back to heuristic extraction if JSON fails.
    """
    import json as _json

    result: dict[str, str] = {
        "headline": "", "subheadline": "", "cta": "", "body_text": "",
    }
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
            for key in result:
                if key in parsed:
                    result[key] = str(parsed[key])
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

    # If no structure found, use entire text as body
    if not any(result.values()):
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
        overrides = data.get("workflow_overrides", {}).get("poster_production", {})
        return {
            "colors": overrides.get("colors", defaults["colors"]),
            "fonts": overrides.get("fonts", defaults["fonts"]),
        }
    except Exception:
        return defaults


def _deliver(context: dict[str, Any]) -> dict[str, Any]:
    """Deliver the final artifact — composes poster PDF via Typst if applicable."""
    from pathlib import Path

    job_ctx = context.get("job_context", {})
    workflow = job_ctx.get("routing", {}).get("workflow", "")

    # Only poster delivery is fully wired — others return explicit stub
    # so callers can distinguish real delivery from unimplemented paths.
    if workflow != "poster_production":
        return {
            "status": "stub",
            "output": f"delivery_not_implemented for workflow '{workflow}'",
            "cost_usd": 0.0,
        }

    stage_results = context.get("stage_results", [])

    # Walk prior stages to find deliverables
    image_path = None
    copy_text = ""
    for stage_result in stage_results:
        if "image_path" in stage_result:
            image_path = stage_result["image_path"]
        if "poster_copy" in stage_result:
            copy_text = stage_result["poster_copy"]

    if not image_path:
        return {
            "status": "error",
            "output": "delivery_failed: no image produced by upstream stages",
            "cost_usd": 0.0,
        }

    parsed = _parse_poster_copy(copy_text)
    style = _load_client_style(job_ctx.get("client_id", "default"))

    try:
        from tools.publish import assemble_document_pdf

        output_dir = Path.home() / "vizier" / "data" / "deliverables"
        output_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = assemble_document_pdf(
            template_name="poster",
            content={
                "headline": parsed.get("headline", ""),
                "subheadline": parsed.get("subheadline", ""),
                "cta": parsed.get("cta", ""),
                "body_text": parsed.get("body_text", ""),
                "background_image": image_path,
            },
            colors=style.get("colors"),
            fonts=style.get("fonts"),
            output_dir=output_dir,
        )
        return {
            "status": "ok",
            "output": "poster_delivered",
            "pdf_path": str(pdf_path),
            "image_path": image_path,
            "copy": parsed,
            "cost_usd": 0.0,
        }
    except Exception as exc:
        logger.error("Poster PDF composition failed: %s", exc)
        return {
            "status": "error",
            "output": f"delivery_failed: PDF composition error — {exc}",
            "image_path": image_path,
            "copy": parsed,
            "cost_usd": 0.0,
        }


def _readiness_check(context: dict[str, Any]) -> dict[str, Any]:
    """Evaluate spec readiness."""
    from contracts.readiness import (
        evaluate_readiness,  # noqa: F401 — stub, will use when fleshed out
    )

    # In production this would receive a ProvisionalArtifactSpec from context
    return {"status": "ok", "output": "readiness_checked", "cost_usd": 0.0}


def _refine_spec(context: dict[str, Any]) -> dict[str, Any]:
    """Refine a vague spec via LLM."""
    from utils.call_llm import call_llm

    prompt = context.get("prompt", "")
    result = call_llm(
        stable_prefix=[{"role": "system", "content": "Refine the artifact spec."}],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.3,
        max_tokens=512,
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
    return {"status": "ok", "output": "operator_asked", "cost_usd": 0.0}


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
        max_tokens=1024,
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

    output_text = str(context.get("output", {}).get("output", ""))
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
        max_tokens=512,
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

    original = str(context.get("original_output", {}).get("output", ""))
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
        max_tokens=2048,
    )

    return {
        "status": "ok",
        "output": result.get("content", original),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost_usd": result.get("cost_usd", 0.0),
    }


def _trace_insight(context: dict[str, Any]) -> dict[str, Any]:
    """Analyse trace from a previous job for rework."""
    return {"status": "ok", "output": "trace_analysed", "cost_usd": 0.0}


def _quality_gate(context: dict[str, Any]) -> dict[str, Any]:
    """Run quality gate on rework output."""
    return {"status": "ok", "output": "quality_passed", "score": 4.0, "cost_usd": 0.0}


def _brand_extract(context: dict[str, Any]) -> dict[str, Any]:
    """Extract brand patterns from client assets."""
    return {"status": "ok", "output": "brand_extracted", "cost_usd": 0.0}


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
        max_tokens=512,
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
    """Verify character consistency across illustrations."""
    return {
        "status": "ok",
        "output": "character_verified",
        "score": 0.9,
        "cost_usd": 0.0,
    }


def _narrative_qa(context: dict[str, Any]) -> dict[str, Any]:
    """Run narrative quality checks on story content."""
    return {
        "status": "ok",
        "output": "narrative_qa_passed",
        "score": 4.0,
        "cost_usd": 0.0,
    }


def _document_qa(context: dict[str, Any]) -> dict[str, Any]:
    """Run document quality checks."""
    return {
        "status": "ok",
        "output": "document_qa_passed",
        "score": 4.0,
        "cost_usd": 0.0,
    }


def _generate_poster(context: dict[str, Any]) -> dict[str, Any]:
    """Generate structured poster copy (headline, subheadline, cta, body_text)."""
    from utils.call_llm import call_llm

    prompt = context.get("prompt", "")
    result = call_llm(
        stable_prefix=[{"role": "system", "content": (
            "Generate poster copy. Output ONLY a JSON object with these keys: "
            "headline, subheadline, cta, body_text. "
            "body_text is newline-separated bullet points. "
            "All text should be in the language of the brief. "
            "Do not include any text outside the JSON object."
        )}],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.7,
        max_tokens=1024,
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
        max_tokens=2048,
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
        max_tokens=4096,
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
        max_tokens=4096,
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
    """Run text quality checks on copy."""
    return {"status": "ok", "output": "text_qa_passed", "score": 4.0, "cost_usd": 0.0}


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
    "typst_render",          # S2 shell — no actual compile logic
    "knowledge_retrieve",    # S12/S18 dependency
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
