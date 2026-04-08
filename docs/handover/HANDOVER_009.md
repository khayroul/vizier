# VIZIER Control Tower — Handover Document

**Generated:** 2026-04-08 ~late night
**Handover number:** 009
**Reason:** End of CT-008 session — Telegram debug, Codex audit fixes, FLUX text hallucination fix, Playwright renderer, intelligence plumbing wiring
**Prior handovers:** 001–008 (cumulative). This document is cumulative — successor needs ONLY this file.

---

## Current Status Board

```
SESSION | STATUS             | BLOCK | TESTS
--------|--------------------| ------|------
S0–S21  | ✅ ALL MERGED      | 1–11  | 538 base
IT-1–5  | ✅ ALL MERGED      | 12    | +106
S19     | ✅ MERGED          | 10    | +29
CODEX   | ✅ MERGED          | 12    | +13
CT-004  | ✅ METERING        | —     | +6
CT-005  | ✅ RING ENFORCE    | —     | +23
CT-006  | ✅ BUG PREVENTION  | —     | +6
CT-007  | ✅ E2E PYRAMID     | —     | +65
CT-008  | ✅ INTEL PLUMBING  | —     | +4 (acceptance)
--------|--------------------| ------|------
TOTAL   |                    |       | 778 passing, 3 skipped, 0 failures
```

**HEAD:** `05cb615` (feat(pipeline): wire intelligence plumbing + Playwright poster renderer)
**Working tree:** Clean. Everything committed.
**Remote:** 14 commits ahead of origin/main. Not pushed.

---

## What CT-008 Did (This Session)

### 1. Fixed Telegram Bot Failures (500/503 Errors)

**Root cause:** Hermes plugin at `~/.hermes/plugins/vizier_tools/__init__.py` used `sys.executable` to spawn subprocesses. This resolved to Python 3.9.6 (system Python) instead of 3.11, causing `StrEnum` ImportError and raw HTML 503 responses to Telegram.

**Fix:** Hardcoded `/opt/homebrew/bin/python3.11` in subprocess calls (lines 178 and 314 of the plugin). Also updated deliverable extraction to prefer `png_path` (composed poster with text overlay) over `image_path` (raw background).

### 2. Applied 12 Codex Audit Fixes (Two Rounds)

| Fix | Category | What |
|-----|----------|------|
| 1 | Image format | Magic byte detection: JPEG (ff d8), WebP (RIFF...WEBP), PNG default |
| 2 | Delivery | `_deliver` returns `status="error"` when no image or PDF fails (was false-success) |
| 3 | Tripwire | Revision merges fields into original output instead of replacing (preserves metadata) |
| 4 | Language | `_detect_brief_language()` heuristic replaces hardcoded `language="en"` |
| 5 | Steward | Energy filter widens when auto-selected bucket returns no candidates |
| 6 | Stub gate | Gate 3: `_STUB_TOOL_NAMES` frozenset blocks active workflows depending on unimplemented tools |
| 7–8 | FLUX sanitize | Two-pass prompt sanitization: strip text instructions, then strip ALL artifact language |
| 9 | Brief expander | Rules updated: "NEVER mention text, headlines, CTAs in composition" |
| 10–12 | Tests | Semantic test updates for fail-closed delivery + stub tool enforcement |

### 3. Solved FLUX Text Hallucination

**Problem:** FLUX renders gibberish when prompts contain artifact language ("poster", "campaign", "banner", "typography").

**Solution:** `_sanitize_visual_prompt()` in `tools/registry.py`:
- Strips all quoted strings (text FLUX would try to render)
- Strips `headline: ...`, `CTA: ...` instruction patterns
- Strips 30+ artifact/design words (poster, flyer, banner, brochure, mockup, typography, etc.)
- Rewrites as: `"Illustration of a visual scene: " + sanitized + no-text suffix`

### 4. Built Playwright/Jinja2 Poster Renderer

**Why:** User rejected Typst poster quality. Playwright + HTML/CSS gives Canva-quality output.

**Architecture:**
```
Jinja2 template → render(data) → page.set_content(html) → page.pdf() + page.screenshot()
```

**Key files:**
- `tools/publish.py` — `assemble_poster_pdf()` (sync entry), `render_poster_html()` (async Playwright)
- `templates/html/poster_default.html` — Professional CSS: gradient overlays, film grain, accent rule, pill CTA
- `templates/html/poster_road_safety.html` — Themed variant
- `tools/registry.py:_deliver()` — Playwright primary, Typst fallback

**Technical notes:**
- Local images → base64 data URIs (Playwright `page.set_content()` has no file:// context)
- No `text-shadow` (duplicates text in PDF extraction) or `backdrop-filter: blur()` (rasterizes text)
- Poster size: 794×1123px (A4 at 96 DPI)

### 5. Wired Intelligence Plumbing (THE CRITICAL FIX)

Sessions S5–S13 built design systems, exemplars, CLIP scoring, datasets — but NONE of it was connected to the poster pipeline. Everything was dead infrastructure. This session wired 3 critical connections:

| Connection | From → To | How |
|-----------|-----------|-----|
| **Client brand → copy** | `config/clients/{id}.yaml` → `_generate_poster()` | Tone, mood, register, colors injected into LLM system prompt |
| **Client brand + design system → image** | `route()` → `_image_generate()` → `expand_brief()` | Brand config + `routing_result.design_system` passed as `brand_config` parameter |
| **Exemplar injection → quality techniques** | `exemplars` table → `apply_quality_techniques()` | Queries DB for active style tags, injects into prompt. Graceful no-op when DB unavailable |

**Data flow after wiring:**
```
route() → design_system selected
                ↓
_generate_poster() ← client brand (tone, mood, register, colors)
                ↓
_image_generate() ← client brand + design_system → expand_brief(brand_config=...)
                ↓
apply_quality_techniques() ← exemplar style tags (when available)
                ↓
_deliver() ← client colors/fonts → Playwright HTML render
```

### 6. Added Acceptance Tests

4 user-POV poster acceptance tests in `tests/test_user_pov_poster_acceptance.py`. Full governed path with deterministic fixtures. Verifies: routing, stage statuses, PDF/PNG generation, text extraction, weighted score, prompt content.

Uses `pdftotext` (poppler) for reliable PDF text extraction — pypdf had issues with Chromium-rendered PDFs.

---

## Commits This Session (Chronological)

```
c5ae24b feat(visual-qa): implement calculate_delta for Layer 3 structural comparison
d5422b3 fix(tests): lazy imports for heavy deps + 3 test infra fixes (72→0 failures)
8085bd4 style: fix 186 E501 line-length + 12 I001 import-sort violations
7484bfe feat(governance): add 6 structural bug-class prevention mechanisms
90c6b7f docs(handover): CT-007 briefing — E2E test pyramid plan
ddfa764 fix(pipeline): 6 E2E poster pipeline fixes from Telegram debug session
552f123 docs: add handover reports, decision records, and E2E test stubs
65a6fec chore: add runtime dirs to gitignore + E2E layer 3 test stub
1fdfcd8 feat(tests): implement E2E test pyramid layers 1-5 (65 tests)
6c92fbf fix(pipeline): 5 structural fixes from Codex audit + semantics tests
b9d7941 fix(pipeline): 7 structural fixes from Codex audit round 2
88f5fc6 fix(image): sanitize visual prompts to prevent FLUX text hallucination
d92b14f fix(image): aggressively strip artifact language from FLUX prompts
05cb615 feat(pipeline): wire intelligence plumbing + Playwright poster renderer
```

---

## Known Issues / Remaining Work

### Must Do (P0)
1. **Rework rerun is a no-op.** `_trace_insight` and `_quality_gate` tools return static "ok" without replaying. The rework workflow YAML exists but does nothing useful.
2. **Parallel guardrails not wired.** Workflow YAMLs define `parallel_guardrails` entries but `_run_stage()` in executor.py doesn't invoke them. Would need concurrent LLM calls.

### Should Do (P1)
3. **Exemplar table is empty.** The `exemplar_injection` plumbing works but returns nothing — no exemplars populated yet. Auto-activates once jobs get 5/5 ratings and are promoted.
4. **Knowledge retrieval is a stub.** `_knowledge_retrieve` in registry.py returns `{"status": "ok", "cards": []}`. S18 (knowledge spine) needs to fill this in.
5. **Client configs sparse.** Only `dmb.yaml` has full brand config. Other clients will get default colors/fonts.
6. **Template selection is hardcoded.** Always uses `poster_default`. No logic to select road safety or other themed templates based on brief content.

### Nice to Have (P2)
7. **Visual QA scores are placeholder.** `_visual_qa` calls `critique_4dim` but results aren't used to block delivery.
8. **Hermes plugin not version-controlled.** `~/.hermes/plugins/vizier_tools/__init__.py` is outside the repo.
9. **14 commits ahead of remote.** Not pushed.

---

## Key Architectural Facts

- **Poster rendering:** Playwright/Jinja2 primary, Typst fallback. Templates in `templates/html/`.
- **Image pipeline:** `brief → expand_brief(brand_config) → sanitize_visual_prompt() → generate_image()`. FLUX never sees text or artifact language.
- **Brand config:** `config/clients/{id}.yaml` `brand:` section → `_load_client_brand()` for generation, `_load_client_style()` for delivery.
- **Design system:** `route() → select_design_systems() → routing_result.design_system → job_context → expand_brief()`.
- **Exemplar flow:** `apply_quality_techniques() → _get_exemplar_context() → DB query → style tag injection`. No-op when empty.
- **Anti-drift #54:** GPT-5.4-mini for ALL text tasks Month 1-2.
- **778 tests, 0 failures, 3 skipped.**

---

## Import Paths Quick Reference

```python
# Poster rendering
from tools.publish import assemble_poster_pdf      # sync, returns Path to PDF + PNG
from tools.publish import render_poster_html        # async Playwright

# Pipeline entry
from tools.orchestrate import run_governed          # full governed chain
from tools.registry import build_production_registry  # tool name → callable

# Routing + design system
from contracts.routing import route, select_design_systems

# Executor + quality
from tools.executor import WorkflowExecutor, apply_quality_techniques

# Image generation
from tools.image import expand_brief, generate_image, select_image_model

# Workflow registry
from utils.workflow_registry import get_workflow_family, get_density_for_family

# Database
from utils.database import get_cursor              # context manager, dict cursor
```

---

## Hermes Gateway Reference

```bash
# Vizier bot (main)
HERMES_HOME=~/.hermes /opt/homebrew/bin/python3.11 -m hermes_cli.main gateway run --replace

# Steward bot (personal assistant)
HERMES_HOME=~/.hermes-steward /opt/homebrew/bin/python3.11 -m hermes_cli.main gateway run --replace

# Plugin location (OUTSIDE repo)
~/.hermes/plugins/vizier_tools/__init__.py

# Plugin runs pipeline as subprocess:
# /opt/homebrew/bin/python3.11 -c "script" with cwd=~/vizier
# Code changes in ~/vizier/ take effect immediately (no restart needed)
# Plugin changes in ~/.hermes/plugins/ require gateway restart
```
