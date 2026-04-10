# Successor Handover: Quality Intelligence Design Session

**Generated:** 2026-04-11  
**Handover number:** 017  
**Reason:** Session designed the brief intelligence system + dataset transformation sprint + anti-drift rules. Design complete, spec reviewed, zero implementation started. Successor implements.  
**Reviewed HEAD:** `ea9dca9`  
**Branch:** `main`

---

## Executive Summary

This session was a **design and analysis session**. One script was written (`scripts/pdf_to_exemplars.py`); everything else is documentation. No production code was changed.

**What was accomplished:**
1. Audited 6 quality gaps against the repo (operator-identified)
2. Designed a brief intelligence/coaching system (Gaps 2 & 3)
3. Discovered that 28 GB of downloaded datasets produce zero quality improvement (the "Layer 3 gap")
4. Wrote a root cause analysis with 3 new anti-drift rules (#58, #59, #60)
5. Wrote a complete S-DATA session spec (dataset transformation sprint, 4 phases)
6. Wrote a unified design doc covering coaching + datasets + calibration
7. Ran a code review agent against all specs; fixed 4 CRITICAL and 5 HIGH issues
8. Built `scripts/pdf_to_exemplars.py` for the operator's Envato template collection workflow
9. Established that datasets teach STRUCTURE, operator exemplars teach TASTE

**What was NOT accomplished:**
- Zero implementation code written (except the PDF script)
- No tests written
- No config files changed
- No production behavior changed

The successor's job is to **implement** what this session **designed**.

---

## Files Created/Modified This Session

### New Files (untracked — need to be committed)

| File | Purpose | Status |
|------|---------|--------|
| `docs/decisions/dataset_transformation_gap.md` | Root cause analysis: why datasets don't improve quality | Complete, reviewed |
| `docs/decisions/unified_quality_design.md` | Master design doc: coaching system + S-DATA + anti-drift rules | Complete, reviewed, all CRITICAL/HIGH issues fixed |
| `docs/S_DATA_SESSION_SPEC.md` | Buildable session spec: 4 phases, task-level detail, exit criteria | Complete, reviewed |
| `scripts/pdf_to_exemplars.py` | PDF → PNG page screenshots for operator exemplar collection | Complete, pyright clean, tested |

### Modified Files

| File | Change | Lines |
|------|--------|-------|
| `CLAUDE.md` | Added "Datasets & Calibration" category to §7 with anti-drift rules #58, #59, #60 | Inserted between "Publishing" and "Architecture" sections |

### Existing Untracked Files (from prior sessions, not ours)

```
docs/HANDOVER_SPRINT_GPT.md
docs/decisions/promote_sysstate_test_2026-04-10.md
docs/decisions/promote_test_template_2026-04-10.md
docs/handover/HANDOVER_014_TRACK1_TRACK2_STOP_POINT.md
docs/handover/HANDOVER_015_SUCCESSOR_REVIEW_FINDINGS.md
docs/handover/HANDOVER_016_SUCCESSOR_QUALITY_FLOOR.md
```

---

## The 6 Quality Gaps (Operator-Identified)

| # | Gap | Severity | Solution Status |
|---|-----|----------|----------------|
| 1 | Canva Pro level templates (10 vs hundreds needed) | HIGH | **S-DATA Phase 1** — cluster D4 → 20-30 templates + operator exemplars for taste |
| 2 | Handling incomplete user briefs (one-shot, no multi-turn coaching) | HIGH | **Part A of unified design** — CoachingResponse contract, content gates, wire refine_request() |
| 3 | System helping users create best prompts (intelligence exists but silent) | HIGH | **Part A** — surface InterpretedIntent, show-don't-ask pattern, language-aware questions |
| 4 | Granular cost tracking by model per stage | MEDIUM | Raw data captured in spans.db. Aggregation query needed (not designed yet). |
| 5 | Clientless industry benchmarking | MEDIUM | Industry tagging works. Exemplars still client-gated. S-DATA-4.2 adds industry_fit to template selector. |
| 6 | Screenshot replication | LOW | Visual DNA + Kontext partial. OCR/multi-ref not designed. Deferred. |

**This session focused on gaps 1, 2, and 3.** Gaps 4, 5, 6 are partially addressed by the data transformation work but need separate design sessions for full solutions.

---

## Critical Design Decisions (Read Before Implementing)

### 1. Coaching lives in the bridge, NOT the orchestrator

`plugins/vizier_tools_bridge.py:_maybe_coach_thin_brief()` is where coaching happens. Do NOT modify `tools/orchestrate.py:run_governed()` for coaching. The orchestrator has no mechanism to return questions through the subprocess boundary.

**Flow:** Bridge calls `interpret_brief()` + content gate → if coaching needed, return `CoachingResponse` JSON immediately (no subprocess) → if gate passes, call `run_governed()` normally.

### 2. Datasets teach structure, operator exemplars teach taste

Academic datasets (D4, D5, D9, D12) are globally/academically sourced — Chinese ads, Western magazines, CVPR benchmarks. They do NOT represent Malaysian SMB taste.

- D4/D5/D9 → extract layout GEOMETRY only (element positions, zones, grid structures)
- D12 → set technical quality FLOOR only (below this NIMA score, image is technically broken)
- Operator's Envato collection → defines TASTE (what "good" looks like for Malaysian market)
- Client feedback in production → defines TRUTH (what actually gets approved and paid for)

**Override hierarchy:** Client feedback > Client config > Operator exemplars > Design system defaults > Dataset-derived values > Hardcoded fallbacks

### 3. NIMA 1-10 scale ≠ Critique 1-5 scale

NIMA scores go in `config/quality_frameworks/nima_thresholds.yaml` (NEW file). Critique dimension thresholds stay in `posteriq_quality_dimensions.yaml`. Do NOT mix them in one file. The code review caught this as CRITICAL.

### 4. D12 "expert ratings" are reference scores, not ground truth

D12 PosterIQ annotations may be LLM-generated or crowd-sourced — provenance undocumented. Calibration target of 70% agreement is provisional. If NIMA-vs-D12 correlation < 0.3, skip threshold update and document.

### 5. GEPA pair count is 1,231, not 2,519

font_attributes.json (1,813 items) contains attribute identification tasks, NOT A/B preference pairs. Actual A/B pairs: layout 256 + font_matching 400 + font_effect 450 + font_effect_2 125 = 1,231.

### 6. `weighted_score()` ALREADY reads weights from YAML

`visual_scoring.py:237-255` already loads dimension weights from `posteriq_quality_dimensions.yaml` via `_load_quality_dimensions()`. Task 2.3 only needs to update the YAML values. No code wiring needed for the scorer — the original "scorer reads weights from YAML" wiring task was removed as redundant because the code already does this.

**Note:** S-DATA spec Task 4.2 is "Template Selector Scores industry_fit" (adding industry_fit scoring to template_selector.py — ~80-100 lines of new code). This is a DIFFERENT task from the removed scorer wiring. Do NOT skip Task 4.2.

---

## Implementation Plan — Build Order

### Day 0: Operator Exemplar Collection + Data Verification (GATE)

The operator is collecting 30-50 poster/flyer templates + 15-25 editorial layouts from Envato. These will be downloaded as PDFs and converted to PNGs using `scripts/pdf_to_exemplars.py`. This is the operator's task, not the successor's.

**Successor tasks:**
1. Run Phase 0 data verification (Task 0.1: unpack D12 data.zip, Task 0.2: validate D4 schema)
2. Build `scripts/ingest_operator_exemplars.py` — auto-tag operator PNGs via GPT-5.4-mini vision + NIMA + CLIP
3. Wait for operator exemplars before calibrating taste-dependent thresholds

### Day 1: Quality Calibration (S-DATA Phase 2 + 4)

```
Task 2.1: Build D12 data loader (scripts/load_posteriq.py)
Task 2.2: Calibrate NIMA thresholds → nima_thresholds.yaml
           BUT: use operator exemplars as primary taste source, D12 as technical floor only
Task 2.3: Calibrate dimension weights (update YAML values only)
Task 4.1: Wire nima_prescreen() to read from nima_thresholds.yaml
```

### Day 2: Template Intelligence (S-DATA Phase 1)

```
Task 1.1: Cluster D4 → 20-30 HTML templates (STRUCTURE only, not style)
Task 1.2: Tag templates with D5 industry → industry_fit field in _meta.yaml
Task 1.3: Validate text zones against D9 saliency (CUT if time-compressed)
Task 4.2: Wire template selector to score industry_fit (~80-100 lines)
```

### Day 3: Coaching System + Prompt Intelligence (Part A + S-DATA Phase 3)

```
Task 3.1: D8 → industry-specific coaching prompt patterns (STRUCTURAL patterns only, not English copy style)
Task 3.2: D7 → content gate definitions (per-workflow semantic gates)
Task 3.3: Wire CTA formulas via utils/copy_patterns.py (CUT if time-compressed)

Part A:
  - contracts/coaching.py (NEW: CoachingResponse + CoachingQuestion)
  - tools/coaching.py (NEW: content gates, language-aware question templates)
  - plugins/vizier_tools_bridge.py (MODIFY: _maybe_coach_thin_brief() → returns CoachingResponse JSON)
  - contracts/routing.py (MODIFY: _REFINEMENT_SYSTEM prompt with industry patterns)
```

### 70% Cut Line (2 days instead of 3)

**Ship:** NIMA calibration + config wiring, D4 template clustering, coaching system with content gates, industry tagging + template selector  
**Cut:** D9 saliency, GEPA bootstrap, OIP report, CTA formula wiring, dimension weight calibration

---

## Key Files the Successor Must Read

| File | Why | Section |
|------|-----|---------|
| `docs/decisions/unified_quality_design.md` | Master design doc — Part A (coaching), Part B (S-DATA), Part C (anti-drift) | ALL |
| `docs/S_DATA_SESSION_SPEC.md` | Task-level build spec with exact steps, exit criteria, dependencies | ALL |
| `docs/decisions/dataset_transformation_gap.md` | Root cause of why datasets don't improve quality | §1 (What Happened), §3 (Fix) |
| `plugins/vizier_tools_bridge.py:725-844` | Current thin brief coaching (to be upgraded) | `_maybe_coach_thin_brief()`, `_run_pipeline_handler()` |
| `contracts/routing.py:260-475` | Existing `refine_request()` — dead code to wire up | `_REFINEMENT_SYSTEM`, `refine_request()`, `_apply_answers()` |
| `tools/visual_scoring.py:88-104` | Current hardcoded NIMA thresholds (to be config-driven) | `nima_prescreen()` |
| `tools/visual_scoring.py:237-255` | `weighted_score()` — already reads from YAML | Confirm before writing wiring code |
| `tools/template_selector.py` | Template selector — no industry_fit dimension exists yet | `select_template()` |
| `tools/brief_interpreter.py` | `interpret_brief()` — extracts InterpretedIntent | Used by coaching for "understood" context |
| `config/quality_frameworks/posteriq_quality_dimensions.yaml` | Current 4-dim quality config (1-5 critique scale) | `scoring.thresholds` (DO NOT use for NIMA) |
| `scripts/pdf_to_exemplars.py` | PDF → PNG converter (already built, pyright clean) | Usage examples in docstring |

---

## Key Files the Successor Must NOT Touch

| File | Why |
|------|-----|
| `tools/orchestrate.py:run_governed()` | Coaching does NOT go here. Bridge handles it. |
| `tools/executor.py` | Workflow executor. Cannot pause for user input. Do not try. |
| `posteriq_quality_dimensions.yaml:scoring.thresholds` | These are 1-5 critique scale. NIMA is 1-10. Separate file. |
| `utils/retrieval.py` | Shared interface stubs. S11/S12 fill these. Don't touch. |

---

## Datasets on Disk

```
/Users/Executor/vizier/datasets/
├── D1_HQ_Poster_100K/     5.9 GB  Partial (8/94 parquets). Movie posters, English.
├── D4_CGL_Dataset_v2/     6.7 GB  Full (15 parquets). 61,583 Chinese ad layouts. COCO bbox.
├── D5_Magazine_Layout/     4.3 GB  Full (10 parquets). 3,919 layouts. 6 industries.
├── D7_Ads_Creative_Text/   ~50 MB  Full. English programmatic ad copy.
├── D8_marketing_social_media/ ~20 MB Full. 689 marketing records. English.
├── D9_PKU_PosterLayout/    6.9 GB  Full (15 parquets). 9,974 posters + saliency maps.
├── D12_PosterIQ/           3.2 GB  Full. data.zip UNEXTRACTED. 219 rated + A/B pairs.
├── D14_MalayMMLU/          132 MB  Full. 24,213 Malay MCQ. For S19, not S-DATA.
├── D16_Open_Image_Preferences_v1/  Partial (downloading).
├── D2_Poster_Preference/   EMPTY   Unavailable.
├── D3_Poster_Reflect/      EMPTY   Unavailable.
├── D10_Children_Stories/   EMPTY   Unavailable.
├── R1_awesome_design_md/   412 KB  55 brand design systems (already in config/).
├── R3_PosterCraft/         52 MB   ICLR 2026 code only, no datasets.
├── R4_Infographic/         8.3 MB  antvis infographic templates.
├── gepa_bootstrap/         EMPTY   Target for D12 preference pairs.
└── operator_exemplars/     EMPTY   Target for operator's Envato collection.
    ├── posters/
    ├── layouts/
    ├── brochures/
    └── textures/
```

**CRITICAL:** `D12_PosterIQ/data.zip` (3.2 GB) has NOT been extracted. Phase 0 Task 0.1 is to unzip it and verify poster images exist inside. If images are not in the zip, Phase 2 (calibration) is BLOCKED.

---

## Operator Context

The operator is the owner of a digital marketing production house in Malaysia. Key context:

- **Market:** Malaysian SMBs — restaurants, salons, property, automotive, education
- **Languages:** Malay primary, English secondary, code-switching common
- **Cultural calendar:** Raya, Merdeka, CNY, Deepavali drive seasonal demand
- **Client expectations:** "Paramount quality" but clients can't articulate what they want
- **Business model:** Hermes chat agent (Telegram/WhatsApp) receives requests, Vizier produces artifacts
- **Revenue deadline:** School holidays mid-May (children's books)
- **Current concern:** Quality floor isn't high enough for professional client delivery

The operator is currently collecting 40-80 Envato templates (PDFs) as taste exemplars. They've been told to:
1. Download poster/flyer PDFs → `pdf_to_exemplars.py --collection posters`
2. Download editorial/book layout PDFs → `pdf_to_exemplars.py --collection layouts --pages 1,3,5,8,12`
3. Drop PNGs into `datasets/operator_exemplars/{collection}/`

The ingestion script (`scripts/ingest_operator_exemplars.py`) has NOT been built yet — that's the successor's first task.

---

## Anti-Drift Rules Added This Session

Now in `CLAUDE.md` §7 under "Datasets & Calibration":

- **#58:** No dataset without a transformation owner AND verification test
- **#59:** No hardcoded threshold without reading from config OR documenting calibration source
- **#60:** Every session must include at least one cross-session integration test

These are binding. The successor must comply. Every task in S-DATA spec has a verification test column for this reason.

---

## Tests to Run After Implementation

### Must-pass (regression)
```bash
pytest tests/ -x -q   # All 884 existing tests still pass
pyright tools/visual_scoring.py tools/coaching.py contracts/coaching.py plugins/vizier_tools_bridge.py
```

### New tests to write (per S-DATA spec)
```bash
# Phase 0
test_d12_poster_images_accessible
test_d4_has_bbox_annotations

# Phase 1
test_template_from_d4_cluster
test_template_selector_scores_industry
test_headline_zone_saliency_overlap
test_food_brief_prefers_food_template

# Phase 2
test_posteriq_loader_returns_valid_records
test_nima_reads_thresholds_from_config
test_changing_yaml_changes_scorer_behavior
test_weight_change_changes_weighted_score
test_gepa_bootstrap_file_valid

# Phase 3
test_coaching_generates_industry_specific_questions
test_content_gate_detects_missing_promotion
test_copy_generate_uses_formula_structure

# Coaching system
test_coaching_response_contract
test_content_gate_poster
test_content_gate_passes_complete
test_thin_brief_coaching_then_produce
test_coaching_surfaces_industry_questions

# Cross-session integration (#60)
test_food_brief_full_chain
test_calibrated_threshold_changes_qa
```

---

## What Explicitly Remains Undesigned

| Gap | Status | Next Step |
|-----|--------|-----------|
| Gap 4: Granular cost aggregation query | Raw spans.db data exists | Design SQL aggregation queries + dashboard view |
| Gap 5: Clientless benchmarking (cross-industry exemplars) | Industry tagging works, exemplars client-gated | Design exemplar sharing policy across clients |
| Gap 6: Screenshot replication | Visual DNA + Kontext partial, no OCR | Design OCR + multi-reference pipeline |
| Operator exemplar ingestion script | Directory structure created | Build `scripts/ingest_operator_exemplars.py` (auto-tag via vision + NIMA + CLIP) |
| NIMA calibration against operator exemplars | Design complete, operator collecting data | Implement after exemplars arrive |
| D16 Open Image Preferences analysis | Download may be incomplete | Check, run Task 2.5 if available |

---

## Summary for the Successor

**Your mission:** Turn the design docs into working code. The specs are detailed enough to implement task-by-task. Start with:

1. **Commit this session's work** (5 new files + CLAUDE.md modification)
2. **Build `scripts/ingest_operator_exemplars.py`** (operator is collecting Envato templates NOW)
3. **Run Phase 0** (unpack D12, validate D4 — this gates everything)
4. **Follow the S-DATA spec day-by-day** (Phase 2 → Phase 1 → Phase 3/Part A → Phase 4)

Read `docs/decisions/unified_quality_design.md` first. It's the master design doc. The S-DATA spec has task-level detail. The decision record explains why we're doing this. `CLAUDE.md` has the rules you must follow.

Good luck. The system works end-to-end. Your job is to make it work **well**.
