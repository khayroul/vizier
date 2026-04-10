# Unified Quality Design: Brief Intelligence + Dataset Transformation

**Date:** 2026-04-10  
**Status:** SPEC — ready for review  
**Scope:** Gaps 2 & 3 (coaching + prompt intelligence), Gap 1 (template variety), quality calibration  
**Related:** `docs/decisions/dataset_transformation_gap.md`, `docs/S_DATA_SESSION_SPEC.md`

---

## Overview

This document specifies two workstreams that together raise Vizier's quality floor and ceiling:

1. **Brief Intelligence System** — Makes the pipeline actively help users produce better briefs (Gaps 2 & 3)
2. **Dataset Transformation Sprint (S-DATA)** — Turns 28 GB of raw datasets into committed quality artifacts (Gap 1 + calibration)

Both share a principle: **intelligence that already exists in the codebase must reach the user, and data that already exists on disk must reach the pipeline.**

---

## Part A: Brief Intelligence System

### A.1 Problem Statement

Users (Malaysian SMBs) don't know what they want, but they want paramount quality. The current system:

- **Thin brief coaching** (`_maybe_coach_thin_brief`): Returns static 5 questions when brief has <5 meaningful words. Questions are generic, not industry-specific. Output is flat text that Hermes must interpret.
- **Auto-enrich** (`_auto_enrich_spec`): Silently fills objective/format/tone/copy_register from interpreted intent. When spec stays "shapeable" after enrichment, it logs a warning and **continues to execution** — producing mediocre output instead of asking for help.
- **refine_request()**: Full LLM-powered coaching engine that generates smart, context-aware questions and applies answers to the spec. Exists in `contracts/routing.py:317-412`. **Dead code in production** — never called from `run_governed()`.
- **Brief interpretation**: `interpret_brief()` extracts 10-field `InterpretedIntent` (industry, mood, audience, cultural_context, etc.). Results are used internally but **never surfaced to the user** for confirmation.

### A.2 Design: Stateless Coaching with Smart Questions

**Architecture:** Hermes manages the conversation (stateless from Vizier's perspective). Vizier returns structured coaching responses. One-bounce gate: system asks once for critical content gaps, produces on second "go" regardless.

**Why stateless:** The workflow executor (`tools/executor.py`) cannot pause mid-workflow for user input. Hermes already manages multi-turn conversations. Vizier should be a pure function: brief in → coaching or artifact out.

#### A.2.1 Coaching Response Contract

```python
# contracts/coaching.py (NEW FILE)

class CoachingResponse(BaseModel):
    """Structured coaching response returned instead of flat text."""
    
    status: Literal["needs_detail", "ready"]
    understood: dict[str, str]     # what we already inferred
    questions: list[CoachingQuestion]  # what we still need

class CoachingQuestion(BaseModel):
    """A single coaching question with context."""
    
    field: str                     # which spec field this fills
    question: str                  # the actual question text
    why: str                       # why this matters for quality
    suggestions: list[str]         # 2-3 concrete options (not open-ended)
    priority: Literal["critical", "nice_to_have"]
```

#### A.2.2 Flow

```
User: "buat poster restoran"
  │
  ├─ Bridge: _maybe_coach_thin_brief() [UPGRADED]
  │   ├─ interpret_brief() → InterpretedIntent {industry: "food", audience: "", mood: ""}
  │   ├─ Content gate check: poster needs promotion/event + date/contact
  │   ├─ Missing: occasion, key_details (price/date/contact), audience
  │   └─ Returns CoachingResponse:
  │       status: "needs_detail"
  │       understood: {
  │         "type": "Poster",
  │         "industry": "Food/Restaurant",
  │         "language": "Malay"
  │       }
  │       questions: [
  │         {field: "occasion", question: "Apa promosi atau acara?",
  │          why: "Poster tanpa promosi spesifik kurang impak",
  │          suggestions: ["Jualan Raya", "Grand Opening", "Menu Baru"],
  │          priority: "critical"},
  │         {field: "key_details", question: "Apa maklumat penting?",
  │          why: "Pelanggan perlu tahu harga/tarikh/lokasi",
  │          suggestions: ["Diskaun 30%", "1-30 April", "Lot 23, SS15"],
  │          priority: "critical"},
  │       ]
  │
  ├─ Hermes: Formats questions naturally, asks user
  │
  ├─ User: "jualan raya, diskaun 30% semua menu, 1-30 april"
  │
  └─ Bridge: _run_pipeline_handler()
      ├─ Enriched brief: "buat poster restoran — jualan raya, diskaun 30% semua menu, 1-30 april"
      ├─ Content gate: poster + promotion + date ✓ → proceed
      └─ run_governed() → full pipeline → PDF + PNG
```

#### A.2.3 Key Design Decisions

1. **Show, don't ask.** Surface what was understood ("I see: Restaurant poster, Food industry, Malay"). Users confirm/correct rather than answering from scratch.

2. **Suggestions, not open-ended questions.** "Apa promosi?" with suggestions ["Jualan Raya", "Grand Opening", "Menu Baru"] is effortless. "Please describe your promotion in detail" is work.

3. **One-bounce gate.** System asks ONCE for critical gaps. On second call, produce regardless. Never ask twice. Never refuse to produce.

4. **Per-workflow content gates.** Replace word-count heuristic with semantic gates:
   - **Poster**: needs promotion/event OR product + at least one of: date, price, contact
   - **Document**: needs topic + purpose + audience  
   - **Brochure**: needs product/service + target audience + key benefits

5. **Language-aware.** Questions in the user's detected language. Malay brief → Malay coaching questions.

6. **Wire refine_request().** Instead of static question lists, use the existing `refine_request()` LLM-powered engine to generate smart, context-aware questions. The function already exists, already works, already handles spec cycling. Just call it.

#### A.2.4 Coaching Lives in the Bridge (Not the Orchestrator)

**Design decision:** All coaching logic stays in `_run_pipeline_handler()` (bridge level), NOT in `run_governed()` (orchestrator level).

**Why:** `run_governed()` returns a dict result and raises exceptions — it has no mechanism to return coaching questions back through the subprocess boundary. Threading coaching through subprocess invocation would require a new result type and error handling at every layer. Since `_maybe_coach_thin_brief()` already intercepts at the bridge level, the cleaner design is:

1. Bridge calls `interpret_brief()` + content gate check BEFORE `run_governed()`
2. If coaching needed → return CoachingResponse JSON immediately (no subprocess, no LLM cost beyond interpret_brief)
3. If content gate passes → call `run_governed()` normally
4. `run_governed()`'s "shapeable" warning stays as a warning (defensive logging) but should not trigger in practice because the bridge already caught incomplete briefs

This means `refine_request()` is called from the bridge when content gates fail and the brief has enough substance for LLM-powered question generation (>3 meaningful words). For very thin briefs (<3 words), static coaching questions suffice.

#### A.2.5 Changes Required

| File | Change | Lines |
|------|--------|-------|
| `contracts/coaching.py` | NEW: CoachingResponse + CoachingQuestion contracts | ~60 |
| `tools/coaching.py` | NEW: Content gate definitions per workflow, language-aware question templates | ~120 |
| `plugins/vizier_tools_bridge.py` | MODIFY: `_maybe_coach_thin_brief()` → returns CoachingResponse JSON, uses content gates instead of word count, calls `interpret_brief()` for understood context, calls `refine_request()` for LLM-powered questions when brief has substance | ~100 |
| `contracts/routing.py` | MODIFY: Update `_REFINEMENT_SYSTEM` prompt with industry-specific question patterns (D8-derived, Task 3.1) | ~20 |

**Estimated total: ~300 lines of new/modified code.**

**Note:** `tools/orchestrate.py` is NOT modified for coaching. The "shapeable" warning at L380-386 stays as defensive logging.

#### A.2.6 Token Cost

- `interpret_brief()`: Called once in the bridge for coaching. If user proceeds to production, `run_governed()` calls it again (~400 tokens). To avoid double-call, the bridge can pass the interpreted intent into `run_governed()` via `run_kwargs["interpreted_intent"]` (field already supported). Net cost: ~400 tokens once. $0.0003.
- Content gate check: Pure Python logic. Zero LLM tokens.
- `refine_request()` (when called for substantive briefs): ~500 tokens. $0.0004.
- Total per coaching interaction: ~$0.0007. Negligible vs $0.05+ for image generation.

---

## Part B: Dataset Transformation Sprint (S-DATA)

Full spec at `docs/S_DATA_SESSION_SPEC.md`. Summary below.

### B.1 The Gap

All 19 sessions shipped but the transformation step — turning raw data into committed artifacts — was never assigned. Detailed root cause in `docs/decisions/dataset_transformation_gap.md`.

### B.2 What Gets Built

| Phase | Duration | Key Outputs |
|-------|----------|-------------|
| 1: Template Intelligence | ~4h | 20-30 new HTML poster templates from D4 clusters, industry tags from D5, saliency validation from D9 |
| 2: Quality Calibration | ~4h | NIMA thresholds calibrated against D12 expert ratings, dimension weights fitted, GEPA bootstrap pairs |
| 3: Prompt Intelligence | ~2h | Industry-specific coaching prompts from D8, content gates from D7, CTA formula injection |
| 4: Wiring | ~2h | Scorer reads config (not hardcoded), template selector scores industry_fit |

### B.3 Overlap with Part A

Part A (coaching) and Part B (dataset transformation) share Phase 3:

- **Task 3.1** (D8 brief patterns) feeds directly into Part A's `_REFINEMENT_SYSTEM` prompt upgrade
- **Task 3.2** (D7 copy completeness) feeds directly into Part A's per-workflow content gates
- **Task 3.3** (CTA formula wiring) improves the copy generated AFTER coaching succeeds

Build order: Phase 2 (calibration) first → Phase 1 (templates) → Phase 3 (prompts, which feeds Part A) → Phase 4 (wiring) → Part A (coaching system).

### B.4 Quality Impact Summary

| Metric | Before S-DATA | After S-DATA |
|--------|--------------|--------------|
| HTML poster templates | 10 (hand-designed) | 30-40 (data-derived + hand-designed) |
| Industry-specific templates | 0 | 30+ (all tagged with industry_fit) |
| NIMA threshold accuracy | Unknown (hardcoded guesses) | Calibrated against D12 reference scores (≥70% agreement target, provisional) |
| Scoring dimension weights | Equal 0.25 (unvalidated, but code already reads from YAML) | Calibrated against D12 reference scores |
| Coaching questions | Static 5 generic questions | Dynamic, industry-specific, language-aware |
| Content gates | Word count (≥5 meaningful words) | Semantic per-workflow (promotion + date + contact for poster) |
| CTA formulas in prompts | 0 (config exists, not wired) | Injected per industry/language |
| GEPA preference pairs | 0 | ≥1,000 from 1,231 actual A/B pairs (bootstrap for future preference learning) |
| Config-driven NIMA thresholds | 0 (hardcoded 4.0/7.0) | Dedicated `nima_thresholds.yaml` (separate from critique 1-5 scale) |

---

## Part C: Anti-Drift Rules Added

Three new rules added to CLAUDE.md §7 to prevent this class of failure:

### Rule #58: No dataset without a transformation owner
Every dataset must have: (1) acquisition session, (2) transformation session with exit criteria, (3) verification test proving artifact is consumed at runtime.

### Rule #59: No hardcoded threshold without a calibration source
Every numeric threshold must either read from config or have documented justification. Config-driven thresholds must have a calibration plan.

### Rule #60: Exit criteria must test cross-session integration
Every session must include at least one test verifying integration with upstream data or downstream consumers. Isolation-only tests are necessary but insufficient.

---

## Part D: Execution Plan

### Recommended Build Order

```
Day 0 (30 min, GATE):
  ├─ Task 0.1: Unpack D12 data.zip, verify poster images exist
  └─ Task 0.2: Validate D4 parquet schema
  (If D12 images missing: reorder Day 1 to start with Phase 1 while investigating)

Day 1 (S-DATA Phase 2 + 4):
  ├─ Task 2.1: Build D12 data loader
  ├─ Task 2.2: Calibrate NIMA thresholds → nima_thresholds.yaml (NEW file, separate from critique scale)
  ├─ Task 2.3: Calibrate dimension weights (update values only, code already reads from YAML)
  └─ Task 4.1: Wire nima_prescreen() to read from nima_thresholds.yaml

Day 2 (S-DATA Phase 1):
  ├─ Task 1.1: Cluster D4 → 20-30 HTML templates
  ├─ Task 1.2: Tag templates with D5 industry
  ├─ Task 1.3: Validate against D9 saliency
  └─ Task 4.2: Wire template selector to score industry_fit (~80-100 lines new code)

Day 3 (S-DATA Phase 3 + Part A):
  ├─ Task 3.1: D8 → coaching prompt patterns
  ├─ Task 3.2: D7 → content gate definitions
  ├─ Task 3.3: Wire CTA formulas via utils/copy_patterns.py loader
  ├─ Part A: Build CoachingResponse contract
  ├─ Part A: Build content gates in tools/coaching.py
  └─ Part A: Upgrade _maybe_coach_thin_brief() with content gates + refine_request()
```

### 70% Cut Line (if time-compressed to 2 days)

**Ship (highest quality impact per hour):**
1. NIMA calibration + config wiring (Task 2.2 + 4.1) — affects every single poster
2. D4 template clustering (Task 1.1) — 3x template variety
3. Coaching system with content gates (Part A) — user experience
4. Industry tagging + template selector (Task 1.2 + 4.2) — industry-aware selection

**Cut:**
- D9 saliency validation (Task 1.3) — templates work without it
- GEPA bootstrap pairs (Task 2.4) — no integration code to consume them
- OIP agreement report (Task 2.5) — validation report, not production
- CTA formula wiring (Task 3.3) — incremental copy quality gain
- Dimension weight calibration (Task 2.3) — current equal weights may be close enough

---

## Part E: Verification Strategy

### Unit Tests
- `test_coaching_response_contract`: CoachingResponse serializes correctly
- `test_content_gate_poster`: Detects missing promotion
- `test_content_gate_passes_complete`: Short but complete brief passes
- `test_nima_reads_config`: Changing YAML changes prescreen behavior
- `test_scorer_reads_weights`: Changing YAML weight changes weighted score
- `test_posteriq_loader`: D12 loader returns valid records

### Integration Tests
- `test_food_brief_full_chain`: Food brief → food template → food design system → poster
- `test_coaching_surfaces_industry_questions`: Malay restaurant brief → Malay coaching questions with food-specific suggestions
- `test_thin_brief_coaching_then_produce`: First call → coaching, second call with details → production
- `test_calibrated_threshold_changes_qa`: D12-calibrated threshold → different QA outcomes than hardcoded

### Smoke Tests (require live APIs)
- `test_coached_poster_e2e`: "buat poster restoran" → coaching → "jualan raya, diskaun 30%" → PDF with food template + NIMA score

---

## Files Created/Modified Summary

| File | Status | Purpose |
|------|--------|---------|
| `docs/decisions/dataset_transformation_gap.md` | CREATED | Root cause analysis + prevention rules |
| `docs/decisions/unified_quality_design.md` | CREATED | This document |
| `docs/S_DATA_SESSION_SPEC.md` | CREATED | Buildable session spec for dataset transformation |
| `CLAUDE.md` | MODIFIED | Anti-drift rules #58-60 added to §7 |
| `contracts/coaching.py` | TO BUILD | CoachingResponse + CoachingQuestion contracts |
| `tools/coaching.py` | TO BUILD | Content gates + coaching logic |
| `plugins/vizier_tools_bridge.py` | TO MODIFY | Structured coaching responses |
| `tools/orchestrate.py` | NO CHANGE | Coaching stays in bridge (§A.2.4). Shapeable warning stays as defensive logging. |
| `tools/visual_scoring.py` | TO MODIFY | Read thresholds/weights from config |
| `contracts/routing.py` | TO MODIFY | Industry-specific coaching prompt patterns |
| `scripts/load_posteriq.py` | TO BUILD | D12 data loader |
| `scripts/cluster_d4_templates.py` | TO BUILD | D4 → HTML template generator |
| `scripts/calibrate_nima.py` | TO BUILD | NIMA threshold calibration from D12 |
