# Handover: Poster Pipeline End-to-End Fix

**Date:** 2026-04-08  
**Commit:** `1d56b90` (vizier) + `e9ca5b49` (hermes-agent submodule)

---

## What Was Fixed

### Issue 1: Steward Bot Identity + Hang
- **Symptom:** Steward responded as "Hermes", then hung forever on "typing..."
- **Root cause:** SOUL.md wasn't deployed before first session start; OpenAI socket entered CLOSE_WAIT (dead connection, 0% CPU)
- **Fix:** Deployed `~/.hermes-steward/SOUL.md` and `~/.hermes-steward/.hermes.md` with Steward persona. Added Atomic Habits expertise section. Kill -9 and restart resolved the hang.
- **Prevention:** Always verify SOUL.md is in place before first bot launch.

### Issue 2: Vizier Poster Pipeline Not Wired
- **Symptom:** `run_pipeline` crashed (`task_id` kwarg), agent fell into 20-turn generate-vision loop with expired fal.ai URLs, burned tokens
- **Root causes (5 separate bugs):**

| # | Bug | Where | Fix |
|---|-----|-------|-----|
| 1 | `_run_pipeline_handler()` missing `**kwargs` | `~/.hermes/plugins/vizier_tools/__init__.py` | Added `**kwargs` to absorb Hermes's `task_id` |
| 2 | fal.ai CDN URLs expire in minutes | `hermes-agent/tools/image_generation_tool.py` | Download to `~/vizier/data/generated_images/{uuid}.png` immediately |
| 3 | Vision tool retried dead URLs forever | `hermes-agent/tools/vision_tools.py` | 404-specific error → "generate a new image instead" |
| 4 | No poster.typ template existed | — | Created `templates/typst/poster.typ` |
| 5 | `_deliver` was a no-op for posters | `tools/registry.py` | Full implementation: parse copy, load style, compose PDF via Typst |

### Additional Sub-Fixes
- **`stage_output.update()` key collision:** `generate_poster` and `image_generate` both returned `"output"` key in same stage. Added `"poster_copy"` key that survives the update.
- **`stage_results` not in context:** `tools/executor.py` now injects `context["stage_results"] = list(stage_results)` before each stage so delivery can walk all prior outputs.
- **Plugin response was raw JSON dump:** `vizier_tools/__init__.py` now extracts `pdf_path`, `image_path`, `qa_score` and formats clean text for the agent.

---

## Files Changed

### Vizier Repo
| File | Change |
|------|--------|
| `templates/typst/poster.typ` | **NEW** — Full-bleed poster template with sys.inputs |
| `tools/registry.py` | `_deliver` (poster PDF composition), `_generate_poster` (JSON copy), `_image_generate` (local save), `_parse_poster_copy`, `_load_client_style` |
| `tools/executor.py` | Added `context["stage_results"]` injection |
| `tests/test_poster_pipeline.py` | **NEW** — 18 tests covering all new code |
| `docs/superpowers/specs/2026-04-08-poster-pipeline-fix-design.md` | Design spec |

### Hermes Plugin (not in git, lives at `~/.hermes/plugins/vizier_tools/`)
| File | Change |
|------|--------|
| `__init__.py` | `**kwargs` on handlers, `_extract_nested()` helper, structured response formatting |

### Hermes Agent Submodule
| File | Change |
|------|--------|
| `tools/image_generation_tool.py` | Local download after fal.ai generation |
| `tools/vision_tools.py` | 404 circuit breaker before generic error handling |

### Bot Personas (not in git)
| File | Change |
|------|--------|
| `~/.hermes/SOUL.md` | Updated production workflow rules (always use `run_pipeline`, never text in image prompts) |
| `~/.hermes-steward/SOUL.md` | Added Atomic Habits Integration section |
| `~/.hermes-steward/.hermes.md` | Same Atomic Habits addition |

---

## How the Poster Pipeline Works Now

```
Operator: "Create a Raya poster for DMB"
  │
  ▼
run_pipeline (Hermes plugin) → tools/orchestrate.py:run_governed()
  │
  ▼ poster_production.yaml (4 stages)
  │
  ├─ Stage 1: classify_artifact → routes to poster workflow
  ├─ Stage 2: generate_poster (JSON copy) + image_generate (text-free bg → local .png)
  │           poster_copy key survives stage_output.update()
  ├─ Stage 3: visual_qa → score + critique
  └─ Stage 4: deliver
              │ walks stage_results for image_path + poster_copy
              │ _parse_poster_copy (JSON/labeled/unstructured)
              │ _load_client_style (config/clients/*.yaml or defaults)
              │ assemble_document_pdf() → typst compile poster.typ with --input flags
              └─ Returns: pdf_path + image_path + parsed copy
  │
  ▼
Plugin formats response: "Pipeline complete: poster_production\nPDF: /path/to/poster.pdf"
Agent displays to operator via markdown
```

---

## What Needs Doing Next

### Before First Poster Request (this session or next)
1. **Restart Vizier bot** — picks up registry.py + plugin changes:
   ```bash
   cd ~/vizier/hermes-agent
   HERMES_HOME=~/.hermes python3.11 hermes.py --telegram
   ```
2. **Restart Steward bot** — picks up Atomic Habits SOUL.md:
   ```bash
   cd ~/vizier/hermes-agent
   HERMES_HOME=~/.hermes-steward python3.11 hermes.py --telegram
   ```
3. **Smoke test:** Send "Create a simple poster for a school cleanliness campaign" to Vizier via Telegram. Expect a PDF back.

### Known Limitations
- **No client style configs exist yet.** All posters use default style (navy/blue/orange, Plus Jakarta Sans/Inter). Create `config/clients/{client_id}.yaml` files to customize.
- **Poster template is basic.** Single layout: headline top, body lower-left, CTA bottom bar. S15 can enhance with multiple layout variants.
- **Tripwire retry not tested live.** If QA score < 3.0, the executor should retry via tripwire (poster_production.yaml has `threshold: 3.0, max_retries: 2`). Needs live validation.
- **Other workflows (brochure, document) still have no-op `_deliver`.** Only `poster_production` workflow gets PDF composition. Extend the pattern per workflow as needed.

### For S15 (Publishing Lane)
- The poster pipeline is now a working reference implementation for the `_deliver` pattern
- Extend to brochure/document by adding workflow-specific branches in `_deliver`
- Creative workshop integration point: between stage 1 (classify) and stage 2 (generate)
- Template variants: add more `.typ` files in `templates/typst/`, select based on client style or brief

### For Future Debug Sessions
- **Bot launch must happen from `hermes-agent/` directory** — otherwise `utils/` import collision between vizier and hermes
- **Always use `python3.11`** — system python3 is 3.9.6
- **fal.ai images are now saved locally** at `~/vizier/data/generated_images/` — check disk usage periodically
- **If agent loops on vision errors**, check `hermes-agent/tools/vision_tools.py` line 450 — the 404 circuit breaker should interrupt the loop
