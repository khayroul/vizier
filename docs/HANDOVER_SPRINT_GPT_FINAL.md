# Handover: GPT 7-Day Sprint — Final State (8.4 → 9.0)

**Date:** 2026-04-10  
**Branch:** `main` at `1c595b3`  
**Tests:** 884 passed, 46 skipped, 0 failed  
**Pyright:** 0 errors across all production + test files  
**All pushed to origin.**

---

## What This Sprint Accomplished

The sprint raised Vizier from 8.4/10 to 9.0/10 across two tracks: **structural integrity** (Days 1-7) and **output quality** (Codex review cycles). 39 commits, ~3,400 lines changed.

### Track 1 — Structural Integrity (Days 1-7)

| Day | Goal | Commit(s) | Result |
|-----|------|-----------|--------|
| 1 | Fix broken imports (listening subsystem) | `acf71f7` | All modules import cleanly. Created `augments/listening/exceptions.py`, rewired `adapter.llm_client` → `utils.call_llm` |
| 2 | Workflow truthfulness — reconcile phase/stub/delivery gates | `b1f2773` | Config-driven deliverability. `workflow_registry.yaml` has `deliverable: true/false` per workflow. Hardcoded frozenset removed. |
| 3 | Policy symmetry — full audit trail | `f9a829a` | Every `PolicyEvaluator.evaluate()` call produces a `policy_logs` row. No silent passes. |
| 4 | Remove soft truth — no silent artifact-family fallbacks | `980f7cd` | Removed `artifact_family=document` default for unclassified specs. Routing now requires explicit classification. |
| 5 | Canon reconciliation | `91b2378` | Decision record documenting architecture doc vs repo drift. |
| 6 | Full governed path integration test | `56f6e3f` | One test exercising route → intent → readiness → policy → execute → QA → deliver → trace end-to-end. |
| 7 | Hardening sweep | `68b0897` | Dead stubs removed, unused code cleaned, pyright clean pass. |

### Track 2 — Output Quality (Codex Reviews)

Five Codex code review rounds drove these fixes:

| Fix | Commit(s) | Impact |
|-----|-----------|--------|
| **UUID job IDs** (P0) | `ee2484d` | `_generate_job_id()` was emitting `job-{hex8}` which failed UUID validation → ALL Postgres persistence silently skipped. Now emits full UUIDs. |
| **flux-pro as universal default** | `97ea75c` | Replaced flux/dev ($0.025) with flux-pro ($0.05) as default image model. Cheap enough for everything, dramatically better quality. flux/dev reserved for explicit draft mode only. |
| **has_text routing fix** | `97ea75c` | Poster/brochure workflows were setting `has_text=True` when copy existed, routing Malay posters to weak nano-banana-pro. But text is overlaid by Typst (anti-drift #49), never baked into images. Now `has_text=False`. |
| **Quality tier in bridge** | `97ea75c` | `quality="high"` parameter exposed in `run_pipeline` tool schema. Maps to `quality_posture=production` + `budget_profile=critical` (QA threshold 3.5, 2 retries, deep search). |
| **Per-model image cost tracking** | `48d2605` | `_FAL_IMAGE_PRICING` dict replaces hardcoded $0.025. flux-pro $0.05, flux/dev $0.025, nano-banana-pro $0.01, nano-banana free. |
| **Industry inference from brief** | `48d2605` | `InterpretedIntent.industry` field extracted by GPT-5.4-mini. Clientless requests auto-tag to industry niche. |
| **Design system selection for clientless requests** | `48d2605` | `select_design_systems()` accepts `override_industry`/`override_mood`. Orchestrator infers design system from industry when no client_id. |
| **Auto-enrich shapeable specs** | `1c595b3` | `_auto_enrich_spec()` fills objective/format/tone/copy_register from brief + interpreted intent. Most specs now upgrade from "shapeable" to "ready" instead of proceeding with gaps. |
| **Thin-brief prompt coaching** | `1c595b3` | `_maybe_coach_thin_brief()` intercepts briefs with <5 meaningful words. Returns 5 coaching questions so the agent gathers detail before burning pipeline tokens. |

---

## Current System State

### What Works End-to-End

| Lane | Route | Readiness | Policy | Execute | QA | Deliver | Trace |
|------|-------|-----------|--------|---------|-----|---------|-------|
| poster_production | Fast-path regex + LLM fallback | Auto-enrich → ready | Full audit trail | Real image gen (flux-pro) + copy + template selection | NIMA + vision + post-render revision | Playwright + Typst | SQLite spans + Postgres jobs |
| document_production | Fast-path regex + LLM fallback | Auto-enrich → ready | Full audit trail | Real content gen | Structural (size/exists) | Typst compile | SQLite spans + Postgres jobs |
| All others | Routes correctly | Auto-enrich runs | Policy checks run | Stub tools | None | Blocked by deliverable: false | Partial |

### Key Numbers

- **884 tests** (876 before this sprint → +8 from quality fixes)
- **10 HTML poster templates** (poster_default, editorial_split, floating_card, bold_knockout, center_stage, diagonal_cut, stacked_type, minimal_clean, promo_grid, road_safety)
- **55 design systems** scored by industry/mood/density/colour overlap
- **2 deliverable workflows** (poster_production, document_production)
- **14 stub tools** awaiting their session builds (S12, S15, S16, S21, S22, S24)
- **3 active phases** (core, publishing, research)

### Pipeline Flow (Poster)

```
User brief ("buat poster jualan raya untuk restoran saya")
  │
  ├─ Bridge: _maybe_coach_thin_brief() → coaching if <5 meaningful words
  │
  ├─ run_governed():
  │   ├─ route() → fast-path regex → "poster_production"
  │   ├─ interpret_brief() → InterpretedIntent {occasion: "hari_raya", mood: "festive",
  │   │   industry: "food", audience: "malay_families", cultural_context: "islamic_festive"}
  │   ├─ ProvisionalArtifactSpec → evaluate_readiness() → "shapeable"
  │   ├─ _auto_enrich_spec() → fills objective/format/tone → re-evaluate → "ready"
  │   ├─ PolicyEvaluator → allow (persisted to policy_logs)
  │   ├─ select_design_systems(override_industry=["food"]) → best match
  │   ├─ WorkflowExecutor:
  │   │   ├─ copy_generate → GPT-5.4-mini + intent context
  │   │   ├─ select_template → intent-aware scorer
  │   │   ├─ expand_brief → visual brief from intent
  │   │   ├─ image_generate → flux-pro (has_text=False, $0.05)
  │   │   ├─ visual_qa → NIMA + vision check → revision if needed
  │   │   └─ deliver → Playwright HTML render + Typst text overlay → PDF + PNG
  │   └─ Trace: spans.db (LLM tokens) + jobs.production_trace (stage JSONB)
  │
  └─ Bridge: returns PDF path + preview PNG + QA score to Hermes agent
```

---

## Known Gaps / What To Build Next

### High Priority

1. **Template variety** — Only 10 HTML poster templates. Niche coverage gaps: food/restaurant, automotive, property/real estate, kids/education, healthcare. Adding a template is config-only (HTML + metadata YAML), no code changes needed. See `templates/html/poster_default.html` and `config/poster_templates.yaml` for the pattern.

2. **Refinement workflow for shapeable specs** — Auto-enrich handles most cases now, but when readiness stays "shapeable" after enrichment, the orchestrator just warns and continues. The proper path is to redirect to `refinement.yaml` workflow (exists but is stub-tool-only). Requires building the refinement tools in S6's scope.

3. **Brochure production lane** — Routes correctly, stubs in place, but no real tools. Next natural lane to ship after poster + document. Needs: multi-page layout engine, section-level content generation, Typst multi-page compile.

### Medium Priority

4. **Interactive prompt coaching** — Current coaching is one-shot (returns suggestions, hopes the agent asks). A more sophisticated approach: the bridge stores the coaching state and does a multi-turn coaching conversation before allowing `run_pipeline`. Low complexity, high UX impact.

5. **Children's book lane** — Most complex workflow (rolling_summary, creative_workshop, section_tripwire). CharacterBible + StoryBible contracts exist (S6). Needs S15 publishing tools. Blocked until S15 ships.

6. **Exemplar injection** — `retrieve_similar_exemplars()` stub exists in `utils/retrieval.py` (S11 scope). CLIP ViT-B/32 is available on MPS (<100ms inference). Needs exemplars table populated with rated production artifacts (currently empty — clean start, no pro-max data ported).

7. **Knowledge spine** — `contextualise_card()` stub exists in `utils/retrieval.py` (S12 scope). Knowledge cards table exists but empty. S12 builds contextualisation, S18 completes the retrieval pipeline.

### Low Priority / Deferred

8. **Drift detection (S19)** — Needs 10-15 anchor set examples from production. Won't have data until Month 1 is running.

9. **Social batch / content calendar** — S22/S24 scope. Structural YAMLs exist and validate, but all tools are stubs.

10. **Self-improvement loop** — S19 scope. Pattern detection + failure analysis + experiment framework. Needs 200+ production ratings before meaningful.

---

## Files Your Successor Needs to Know

### Core Pipeline

| File | What | Key Functions |
|------|------|---------------|
| `plugins/vizier_tools_bridge.py` | Hermes ↔ Vizier adapter | `_run_pipeline_handler()` (L725), `_maybe_coach_thin_brief()` (L725), `_build_guidance()` (L444) |
| `tools/orchestrate.py` | Governed execution chain | `run_governed()` (L227), `_auto_enrich_spec()` (L50), `_ensure_job_row()` (L66) |
| `tools/registry.py` | All tool implementations | `build_production_registry()`, `_image_generate()`, `_visual_qa()`, `_FAL_IMAGE_PRICING` (L31) |
| `contracts/routing.py` | Router + design system selector | `route()`, `select_design_systems()` (accepts `client_id: str | None` + overrides) |
| `tools/brief_interpreter.py` | Brief → InterpretedIntent | `interpret_brief()`, `_SYSTEM_PROMPT` (extracts industry) |
| `contracts/interpreted_intent.py` | Structured intent contract | `InterpretedIntent` (10 fields incl. `industry`) |

### Quality & Governance

| File | What |
|------|------|
| `contracts/readiness.py` | ReadinessGate: ready/shapeable/blocked |
| `middleware/policy.py` | PolicyEvaluator with full audit trail |
| `middleware/quality_posture.py` | Quality posture configs (canva_baseline, enhanced, production) |
| `middleware/runtime_controls.py` | Per-client runtime control resolution |
| `tools/visual_pipeline.py` | NIMA + composition QA + post-render failure classification |
| `tools/image.py` | Image model selection (`select_image_model()` — flux-pro default) |

### Config

| File | What |
|------|------|
| `config/workflow_registry.yaml` | 16 workflows with deliverable flags |
| `config/phase.yaml` | Phase activation (core/publishing/research active) |
| `config/poster_templates.yaml` | Template metadata for intent-aware selection |
| `config/clients/` | Per-client config (industry, mood, language, template, design_system) |
| `config/design_systems/` | Empty directory — 55 systems are inline in `contracts/routing.py` |

---

## Anti-Patterns to Avoid

These are the bugs we found and fixed. Don't reintroduce them:

1. **Don't use truncated job IDs** — Must be full UUID4 for Postgres FK compatibility. `_generate_job_id()` returns `str(uuid.uuid4())`.

2. **Don't set `has_text=True` for poster/brochure** — Text is ALWAYS overlaid by Typst, never baked into AI images (anti-drift #49). Setting `has_text=True` routes to weaker models.

3. **Don't hardcode image costs** — Use `_fal_image_cost(model)` from `_FAL_IMAGE_PRICING` dict.

4. **Don't write test artifacts to production paths** — Mock `_GENERATED_IMAGES_DIR` in tests, not `Path.home()`.

5. **Don't log policy allows without persisting** — Every evaluate() call must produce a policy_logs row.

6. **Don't assume readiness fields are filled** — The orchestrator creates ProvisionalArtifactSpec without objective/format. `_auto_enrich_spec()` fills them. If you add new critical fields to readiness, update auto-enrich too.

7. **Don't add models besides GPT-5.4-mini for text tasks** — Anti-drift #54 is absolute for Month 1-2. Image models (flux-pro, Kontext, nano-banana) are fine.

---

## How to Test

```bash
# Full suite (should take ~22s)
/opt/homebrew/bin/python3 -m pytest tests/ -q

# Type check
pyright tools/orchestrate.py contracts/routing.py plugins/vizier_tools_bridge.py

# Smoke test pipeline (requires OPENAI_API_KEY + FAL_KEY)
/opt/homebrew/bin/python3 scripts/smoke_test.py

# Live poster test via Hermes
# 1. Restart Hermes to pick up bridge changes
# 2. Send: "buat poster jualan Raya untuk restoran Warung Selera, diskaun 30%"
# 3. Expect: PDF + PNG + QA score ≥ 3.0
```

---

## Environment

- **Python:** 3.14 at `/opt/homebrew/bin/python3` (3.11 also available)
- **Typst:** installed system-wide (`typst compile` works)
- **Postgres 16:** local, 37 tables via `DATABASE_URL`
- **MinIO:** local, for binary asset storage
- **API keys:** `OPENAI_API_KEY`, `FAL_KEY` in environment
- **Architecture docs:** gitignored (proprietary), read from `/Users/Executor/vizier/docs/VIZIER_ARCHITECTURE.md`
- **Pro-max (legacy):** at `~/pro-max/`, templates ported, no client data ported (clean start)
- **Hermes Agent v0.7.0:** submodule at `hermes-agent/`, plugin at `plugins/vizier_tools_bridge.py`
