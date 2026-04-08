# Poster Pipeline End-to-End Fix — Design Spec v2

**Date:** 2026-04-08
**Scope:** Issues #6-12 from debugging session — wire poster production pipeline to deliver composed PDF posters via Telegram. Plus Steward Atomic Habits persona update (#12).

---

## Problem Statement

The Vizier poster production pipeline has all infrastructure components (routing, readiness gates, policy checks, quality tripwires, Typst compiler, fal.ai image generation) but cannot deliver a finished poster. The agent bypasses `run_pipeline` and uses `image_generate` directly, producing images with text baked in (spelling errors, garbled Malay). The pipeline's `_deliver` stage is a no-op, there's no poster Typst template, and the registry's `_image_generate` returns raw bytes that never get saved to disk.

## Design

### A. New file: `templates/typst/poster.typ`

Single-page poster template using `sys.inputs.at("key", default: "fallback")` pattern (matches invoice.typ, report.typ, proposal.typ).

**Parameters (all via sys.inputs):**
- `background_image` — absolute path to text-free AI-generated image
- `headline` — main headline text
- `subheadline` — supporting tagline
- `cta` — call-to-action text
- `body_text` — bullet points or info text (newline-separated, split on `\n`)
- `primary_color`, `secondary_color`, `accent_color` — hex brand colors
- `headline_font`, `body_font` — font family names from assets/fonts/
- `page_size` — "a3" or "a4" (default "a4")

**Naming convention:** sys.inputs keys use underscores (`sys.inputs.at("headline_font")`), matching all existing templates. Typst internal variable names use hyphens (`#let heading-font = ...`).

**Layout zones:**
- Full-bleed background image
- Top zone: headline + subheadline (white text on semi-transparent dark overlay strip)
- Lower-left zone: body text / pricing info (semi-transparent panel)
- Bottom zone: CTA bar (accent color background, white text)

### B. Reuse existing `assemble_document_pdf()` — NO new function

`tools/publish.py` already has `assemble_document_pdf()` (lines 532-584) which:
- Takes `template_name`, `content` dict (→ sys.inputs), `colors`, `fonts`, `output_dir`
- Builds `--input key=value` args and calls `subprocess.run()` directly
- Handles `TYPST_FONT_PATHS` env var
- Returns PDF `Path`

The poster uses this directly:
```python
from tools.publish import assemble_document_pdf

pdf_path = assemble_document_pdf(
    template_name="poster",
    content={
        "headline": "JAGALAH KEBERSIHAN",
        "subheadline": "Cerminan Disiplin...",
        "cta": "MARI BERSAMA MEMBUDAYAKAN KEBERSIHAN",
        "body-text": "Buang sampah di tempat yang disediakan\nPastikan kelas...",
        "background-image": "/Users/Executor/vizier/data/generated_images/abc123.png",
    },
    colors={"primary": "#1a365d", "secondary": "#2b6cb0", "accent": "#ed8936"},
    fonts={"headline": "Plus Jakarta Sans", "body": "Inter"},
    output_dir=output_dir,
)
```

**No `assemble_poster_pdf()` needed.** This avoids function proliferation and reuses proven code.

**Note:** `_compile_typst()` does NOT accept `inputs` — it only takes `(source_path, output_path)`. The `assemble_document_pdf()` function bypasses `_compile_typst()` and calls `subprocess.run()` directly with `--input` flags. This is the correct pattern (same as `assemble_ebook()` and `assemble_document_pdf()`).

### C. Edit: `tools/registry.py` → `_image_generate` saves to file

After `generate_image()` returns bytes, save to disk:

```python
from pathlib import Path
from uuid import uuid4

local_dir = Path.home() / "vizier" / "data" / "generated_images"
local_dir.mkdir(parents=True, exist_ok=True)
local_path = local_dir / f"{uuid4().hex}.png"
local_path.write_bytes(image_bytes)

return {
    "status": "ok",
    "output": f"image_generated ({len(image_bytes)} bytes via {model})",
    "image_path": str(local_path),
    "image_model": model,
    "cost_usd": 0.025,
}
```

**`image_bytes` removed from return dict.** Verified safe: `_visual_qa` (the only downstream consumer in the executor pipeline) reads `context["previous_output"]["output"]` as a string, not `image_bytes`. The separate `visual_pipeline.py` code path calls `generate_image()` directly and is unaffected.

**Divergence note:** The registry's `_image_generate` now returns a file path, while `tools/visual_pipeline.py` still works with in-memory bytes via `tools.image.generate_image()`. These are separate code paths. Future convergence is out of scope for this fix.

### D. Edit: `tools/executor.py` → pass cumulative stage results in context

**Critical fix.** The delivery stage needs access to ALL prior stage outputs (not just the immediately preceding one). Currently the executor only passes `context["previous_output"]` (last stage) and `context["previous_stage"]` (compressed string). The delivery stage can't reach the production stage's `image_path`.

Add ONE line at the start of the stage loop (before `_run_stage`):

```python
for stage in self.pack.stages:
    context["stage_results"] = list(stage_results)  # cumulative for downstream stages
    stage_output = self._run_stage(stage, context, collector)
    # ... rest unchanged ...
```

This is non-breaking: no existing tools read `stage_results`. The delivery stage now has access to all prior stage outputs.

### E. Edit: `tools/registry.py` → `_deliver` composes poster PDF

```python
def _deliver(context: dict[str, Any]) -> dict[str, Any]:
    job_ctx = context.get("job_context", {})
    workflow = job_ctx.get("routing", {}).get("workflow", "")

    # Only poster delivery is wired — others fall through to no-op
    if workflow != "poster_production":
        return {"status": "ok", "output": "delivered", "cost_usd": 0.0}

    stage_results = context.get("stage_results", [])

    # Walk prior stages to find deliverables
    # poster_copy key survives stage_output.update() (see Section F)
    image_path = None
    copy_text = ""
    for stage_result in stage_results:
        if "image_path" in stage_result:
            image_path = stage_result["image_path"]
        if "poster_copy" in stage_result:
            copy_text = stage_result["poster_copy"]

    if not image_path:
        return {"status": "ok", "output": "delivered (no image produced)", "cost_usd": 0.0}

    # Parse structured copy from generate_poster output
    parsed = _parse_poster_copy(copy_text)

    # Get client style or defaults
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
        # Graceful degradation: return image + copy without PDF
        return {
            "status": "ok",
            "output": f"poster_delivered (PDF failed: {exc})",
            "image_path": image_path,
            "copy": parsed,
            "cost_usd": 0.0,
        }
```

**Helper functions (defined in registry.py):**

```python
def _parse_poster_copy(copy_text: str) -> dict[str, str]:
    """Extract structured fields from generate_poster LLM output.

    Expects JSON output from the updated _generate_poster system prompt.
    Falls back to heuristic extraction if JSON parsing fails.
    """
    import json as _json
    # Strip markdown fencing if present (LLM may wrap JSON in ```json ... ```)
    stripped = copy_text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]  # remove first line (```json)
        if "```" in stripped:
            stripped = stripped[:stripped.rfind("```")].strip()

    # Try JSON first (preferred — _generate_poster outputs structured JSON)
    try:
        parsed = _json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, TypeError):
        pass

    # Heuristic fallback: look for labeled sections
    result = {"headline": "", "subheadline": "", "cta": "", "body_text": ""}
    lines = copy_text.strip().split("\n")
    for line in lines:
        lower = line.lower().strip()
        if lower.startswith("headline:"):
            result["headline"] = line.split(":", 1)[1].strip()
        elif lower.startswith("subheadline:") or lower.startswith("tagline:"):
            result["subheadline"] = line.split(":", 1)[1].strip()
        elif lower.startswith("cta:") or lower.startswith("call to action:"):
            result["cta"] = line.split(":", 1)[1].strip()
        elif lower.startswith("body:") or lower.startswith("body text:"):
            result["body_text"] = line.split(":", 1)[1].strip()
    # If no structure found, use entire text as body
    if not any(result.values()):
        result["body_text"] = copy_text.strip()
    return result


def _load_client_style(client_id: str) -> dict[str, Any]:
    """Load brand colors and fonts for a client.

    Reads from config/clients/{client_id}.yaml if it exists.
    Returns defaults otherwise.
    """
    import yaml as _yaml
    _repo_root = Path(__file__).resolve().parent.parent
    client_path = _repo_root / "config" / "clients" / f"{client_id}.yaml"
    defaults = {
        "colors": {"primary": "#1a365d", "secondary": "#2b6cb0", "accent": "#ed8936"},
        "fonts": {"headline": "Plus Jakarta Sans", "body": "Inter"},
    }
    if not client_path.exists():
        return defaults
    try:
        with client_path.open() as fh:
            data = _yaml.safe_load(fh) or {}
        overrides = data.get("workflow_overrides", {}).get("poster_production", {})
        colors = overrides.get("colors", defaults["colors"])
        fonts = overrides.get("fonts", defaults["fonts"])
        return {"colors": colors, "fonts": fonts}
    except Exception:
        return defaults
```

### F. Edit: `tools/registry.py` → `_generate_poster` outputs structured JSON under `poster_copy` key

**Critical fix:** In the poster workflow, `generate_poster` and `image_generate` both run in the same stage. The executor calls `stage_output.update(tool_result)` for each tool. Both return an `"output"` key — `image_generate` runs second and overwrites the copy text. The poster copy is permanently lost.

**Fix:** `_generate_poster` returns its copy under `"poster_copy"` (a unique key) instead of relying solely on `"output"`. The `_deliver` function searches `stage_results` for `"poster_copy"` instead of `"output"`.

```python
def _generate_poster(context: dict[str, Any]) -> dict[str, Any]:
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
```

### G. Edit: `~/.hermes/plugins/vizier_tools/__init__.py` → structured response

Modify only the success path. **Preserve existing error handling** (`ReadinessError`, `PolicyDenied`, generic `Exception` try/except blocks remain unchanged).

```python
def _run_pipeline_handler(args: dict[str, Any], **kwargs: Any) -> str:
    if args.get("action") == "list":
        return _list_workflows()

    request = args.get("request", "")
    if not request:
        return "Error: 'request' is required. Describe what you want to produce."

    client_id = args.get("client_id", "default")
    job_id = args.get("job_id") or _generate_job_id()

    try:
        from tools.orchestrate import run_governed, ReadinessError, PolicyDenied

        result = run_governed(
            raw_input=request,
            client_id=client_id,
            job_id=job_id,
        )

        # Extract deliverables for clean agent response
        pdf_path = _extract_nested(result, "pdf_path")
        image_path = _extract_nested(result, "image_path")
        qa_score = _extract_nested(result, "score")
        workflow = result.get("routing", {}).get("workflow", "unknown")

        lines = [f"Pipeline complete: {workflow}"]
        if pdf_path:
            lines.append(f"PDF: {pdf_path}")
        if image_path:
            lines.append(f"Image: {image_path}")
        if qa_score is not None:
            try:
                lines.append(f"QA score: {float(qa_score):.1f}/5")
            except (ValueError, TypeError):
                pass
        lines.append("")
        lines.append("Display the PDF (or image if no PDF) to the operator using markdown.")

        return "\n".join(lines)

    except ReadinessError as exc:
        return f"Readiness gate blocked: {exc}"
    except PolicyDenied as exc:
        return f"Policy denied: {exc}"
    except Exception as exc:
        logger.error("run_governed failed: %s", exc, exc_info=True)
        return f"Pipeline error: {exc}"


def _extract_nested(data: dict, key: str) -> Any:
    """Walk a nested dict (including 'stages' list) to find a key."""
    if key in data:
        return data[key]
    for value in data.values():
        if isinstance(value, dict):
            found = _extract_nested(value, key)
            if found is not None:
                return found
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found = _extract_nested(item, key)
                    if found is not None:
                        return found
    return None
```

### H. Edit: `~/.hermes/SOUL.md` → tighten production guidance

Replace section 3 (Production workflow):

```markdown
3. **Production workflow.** For asset production requests:
   - **Always** use `run_pipeline` for client deliverables (posters, brochures, documents, books)
   - `run_pipeline` handles governance, quality gates, and delivers composed PDFs
   - Display returned PDF/image paths using markdown: ![poster](path)
   - Use `image_generate` only for quick previews or ad-hoc images NOT tied to a deliverable
   - **Never** include text in image generation prompts — text is rendered by Typst templates
```

### I. Edit: `~/.hermes-steward/SOUL.md` → add Atomic Habits

Add after the GTD Pipeline section:

```markdown
## Atomic Habits Integration

You are also an expert on Atomic Habits (James Clear). You weave habit-building into GTD naturally:

- **The 4 Laws**: Make it obvious (cue design), make it attractive (temptation bundling), make it easy (2-minute rule, reduce friction), make it satisfying (habit tracking, reward)
- **Identity-based habits**: "What would a healthy person do?" — frame habits as identity, not outcomes
- **Habit stacking**: Link new habits to existing routines. "After I finish Fajr prayer, I will review my 3 priorities for the day."
- **Environment design**: Suggest physical/digital environment changes that make good habits obvious and bad habits invisible
- **Tracking**: When the operator uses /done for a recurring habit, show streak count and consistency percentage
- **Recovery**: "Never miss twice" — when a streak breaks, acknowledge without guilt and restart

Integrate habits into the existing GTD system:
- Habits are recurring next-actions with a context and trigger time
- Weekly review includes habit consistency check
- /habits command shows active habits with streaks
```

---

## What This Does NOT Change

- Hermes submodule internals (no changes to gateway, event loop, timeout handling)
- Other workflow types (book, ebook, brochure) — their delivery stays as-is (`_deliver` checks workflow type and falls through)
- Model selection (GPT-5.4-mini for everything, anti-drift #54)
- The Hermes `image_generate` tool fix from earlier (local download) — that stays, this is the registry version
- `_compile_typst()` function signature — unchanged, `assemble_document_pdf()` bypasses it

## Dependencies

- Typst 0.14.2 (installed, verified in S2)
- Fonts in `assets/fonts/` (Inter, Plus Jakarta Sans, IBM Plex Serif, Amiri — verified)
- `assemble_document_pdf()` in `tools/publish.py` (exists, handles sys.inputs via --input flags)

## Testing

- Unit test for poster template — compile with fixture data, verify PDF exists and is non-empty
- Unit test for `_deliver` with poster context including `stage_results` — verifies PDF path in result
- Unit test for `_parse_poster_copy` — JSON input and heuristic fallback
- Unit test for `_load_client_style` — with and without client config file
- Integration test for `_run_pipeline_handler` — verifies structured response with deliverable paths
- Smoke test: send "make a simple poster" to Vizier Telegram, verify PDF arrives

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `templates/typst/poster.typ` | NEW | Poster Typst template |
| `tools/executor.py` | EDIT (1 line) | Add `context["stage_results"]` to stage loop |
| `tools/registry.py` | EDIT | `_image_generate` saves to file, `_deliver` composes PDF, `_generate_poster` outputs JSON, add helpers |
| `~/.hermes/plugins/vizier_tools/__init__.py` | EDIT | Structured response + `_extract_nested` helper |
| `~/.hermes/SOUL.md` | EDIT | Tighten production workflow guidance |
| `~/.hermes-steward/SOUL.md` | EDIT | Add Atomic Habits section |
| `tests/test_poster_pipeline.py` | NEW | Unit + integration tests |
