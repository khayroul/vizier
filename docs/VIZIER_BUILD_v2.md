# Vizier Build Plan V2 — Closing the Quality Gap

**Date:** 2026-04-11
**Informed by:** `docs/decisions/lessons_learned_build_plan_v1.md`
**Objective:** By the end of this plan, Vizier produces:
1. **Posters** at minimum Canva free-tier floor (clean layout, professional typography, coherent visual hierarchy, acceptable text placement, niche-appropriate aesthetics)
2. **Illustrated children's books / ebooks** that are commercially sellable (coherent pacing, consistent characters, usable page composition, print-ready assembly)

**Principle:** Optimise for output quality, not architecture completeness. The existing V1 infrastructure (contracts, routing, policy, tables, spans) is preserved and wired in at the end — after the pipeline produces sellable output.

---

## Current State (What V1 Built That Works)

### ✅ Fully Working — Keep As-Is
| Component | Files | Status |
|-----------|-------|--------|
| Brief interpretation | `tools/brief_interpreter.py` | GPT-5.4-mini → InterpretedIntent |
| Routing (fast-path + LLM) | `contracts/routing.py` | ~70% fast-path hit rate |
| Readiness evaluation | `contracts/readiness.py` | ready/shapeable/blocked |
| Policy engine (4 gates) | `middleware/policy.py` | phase → tool → budget → cost |
| Workflow executor | `tools/executor.py` | Loads YAML, runs stages, tripwire loop |
| Image generation | `tools/image.py`, `tools/registry.py` | FLUX-pro, Kontext, Nano Banana via fal.ai |
| NIMA aesthetic scoring | `tools/visual_scoring.py` | MobileNetV2 on MPS, config-driven thresholds |
| Typst rendering | `tools/publish.py` | Compiles .typ → PDF/PNG |
| Playwright HTML rendering | `tools/registry.py` | HTML templates → PNG via Chromium |
| Brand voice guardrail | `middleware/guardrails.py` | BM naturalness check |
| Coaching (structured JSON) | `contracts/coaching.py`, `tools/coaching.py` | Content gates, bilingual questions |
| Trace collection | `contracts/trace.py`, `utils/spans.py` | SQLite + Postgres persistence |
| Database (16 tables) | `migrations/` | All tables created, IF NOT EXISTS |
| MinIO storage | `utils/storage.py` | Asset upload/download |
| 16 workflow YAMLs | `manifests/workflows/` | Structural definitions |
| Industry coaching patterns | `config/coaching_patterns.yaml` | 9 industries from D8 |

### ⚠️ Works But Needs Quality Upgrade
| Component | Issue | Fix Session |
|-----------|-------|-------------|
| Template pool (38 templates) | CSS grid approximations, not professional designs | S-T1 |
| HTML rendering | No typography rules, no dynamic sizing | S-T2 |
| 4-dim critique | Runs without exemplar context (generic prompts) | S-E2 |
| Template selector | Algorithm correct but pool is weak | S-T1 (new pool) |
| NIMA calibration | Script built, never run against production | S-E1 |
| Tripwire critique-then-revise | Exists but critique prompts are generic | S-E2 |

### ❌ Stubbed / Dead — Must Build
| Component | Current State | Fix Session |
|-----------|--------------|-------------|
| story_workshop | Stub in registry.py line 2672 | S-B1 |
| scaffold_build | Stub in registry.py line 2673 | S-B1 |
| Exemplar table | 0 rows | S-E1 |
| Visual delta comparison | Function never built | S-E2 |
| Character consistency enforcement | CLIP check exists but doesn't trigger regen | S-B2 |
| knowledge_store | Stub | S-I2 |

---

## Template Ingestion Strategy (100-200 Canva/Envato References)

### Grouping Model

**Primary:** `artifact_type` → `layout_archetype` → `niche/use_case`

```
templates/
  poster/
    hero_top/             # hero image dominates top half
    split_panel/          # left-right or top-bottom split
    center_focus/         # centred subject, text radiates outward
    full_bleed/           # edge-to-edge image, text overlay
    editorial/            # text-heavy, magazine-influenced
    stacked_type/         # typography-dominant, image secondary
  brochure/
    trifold/
    bifold/
  book_layout/
    picture_book/         # illustration-dominant, minimal text
    chapter_book/         # text-dominant, spot illustrations
    magazine_spread/      # mixed layout per spread
```

**Do NOT group by source.** Canva and Envato templates solve the same design problems with different aesthetics. Grouping by source creates artificial style buckets that don't help selection. Grouping by archetype lets the selector match user intent (hero_top for event posters, center_focus for product launches) regardless of provenance.

### Metadata Schema Per Template

```yaml
# Example: templates/poster/hero_top/raya_festive_01_meta.yaml
archetype: hero_top
density: moderate
tone_fit: [festive, warm, celebratory]
occasion_fit: [hari_raya, deepavali, cny, christmas]
industry_fit: [food, retail, general]
cta_prominence: medium
hero_style: full_bleed_top
typography:
  headline_font_class: display    # display | serif | sans-serif
  hierarchy_levels: 3             # number of distinct text sizes
  min_font_size_pt: 14
  max_line_length_ch: 35
  tracking: normal                # tight | normal | wide
  cta_style: button               # button | text_link | banner
colour_palette: ["#D4A853", "#1A1A2E", "#FEFEFE"]  # extracted from template
quality_tier: professional        # professional | standard | d4_derived
source: canva                     # canva | envato | d4_derived | hand_crafted
region: my                        # my | general | global
language_fit: [ms, en]
supported_slots:
  - hero_image
  - headline
  - subheadline
  - cta
  - logo
  - body_text
  - tagline
  - price
  - badge
```

### How References Improve Each Pipeline Stage

| Stage | Without References | With 100-200 References |
|-------|--------------------|------------------------|
| **Template selection** | Scores 38 weak templates | Scores 138-238 templates; professional tier gets +3.0 bonus |
| **Image generation** | Generic visual prompt | Template's `colour_palette` injected into prompt → FLUX generates harmonising images |
| **Copy generation** | Generic tone | Template's `tone_fit` constrains GPT-5.4-mini copy style |
| **Typography** | Fixed CSS grid zones | Template's `typography` rules become rendering constraints (min size, hierarchy, tracking) |
| **Quality scoring** | Generic 4-dim critique | Exemplar-anchored: "is this as good as the top 3 similar professional templates?" |
| **Exemplar matching** | Empty table, no-ops | Top 50-80 outputs from professional templates become the taste baseline |

---

## Revised Session Plan

### Phase 1: Template Foundation

#### S-T1: Professional Template Ingestion
**Duration:** 2 days
**Depends on:** Nothing (first session)
**Input:** 100-200 Canva/Envato templates (poster, brochure, book layout) provided by operator

**Deliverables:**
1. Ingestion script: `scripts/ingest_templates.py`
   - Accepts a directory of HTML/CSS templates (exported from Canva/Envato)
   - Extracts: colour palette (dominant colours via k-means on pixel samples), typography rules (font families, sizes, weights from CSS), layout structure (grid areas, flex containers), supported slots (identified by CSS class names or placeholder patterns)
   - Generates `_meta.yaml` per template with full metadata schema
   - Validates HTML renders correctly via Playwright screenshot
   - Classifies into archetype (hero_top, split_panel, center_focus, etc.) by analysing image/text zone ratios

2. Template catalogue: 100-200 templates in `templates/poster/`, `templates/brochure/`, `templates/book_layout/` with `_meta.yaml` each

3. Quality tier tagging: Each template rated `professional` or `standard` based on:
   - Typography: ≥2 hierarchy levels, no default system fonts
   - Whitespace: ≥15% negative space ratio
   - Colour: ≤4 primary colours, not clashing (ΔE*₀₀ ≥ 20 between adjacent)

**Exit criteria:**
- ≥100 templates ingested with valid `_meta.yaml`
- Playwright renders ≥90% without visual errors
- `select_template()` returns professional-tier templates for common intents (Raya, product launch, corporate event)
- Pyright clean on all new files
- 10+ tests for ingestion script

**Acceptance test:** Render 10 templates with sample content. Operator rates ≥7 of 10 as "looks like a real Canva template."

---

#### S-T2: Template-Aware Rendering
**Duration:** 2 days
**Depends on:** S-T1

**Deliverables:**
1. Typography engine: `tools/typography.py`
   - Reads template's `typography` rules from `_meta.yaml`
   - Dynamic headline sizing: fits text to container without overflow, maintaining minimum readable size
   - Hierarchy enforcement: headline > subheadline > body by ≥1.3x ratio
   - Line length control: soft-wrap at `max_line_length_ch`
   - CTA styling: button rendering with padding, border-radius, background colour from palette
   - Tracking/leading adjustment based on font class

2. Rendering upgrade: modify `tools/registry.py` poster rendering to:
   - Inject typography rules into Playwright page context before rendering
   - Apply dynamic font sizing via JavaScript before screenshot
   - Validate text doesn't overflow containers (re-render with smaller size if needed)
   - Apply colour palette to CTA, borders, accents

3. Visual regression test suite: `tests/test_rendering_quality.py`
   - For each archetype, verify: text readable, hierarchy maintained, no overflow, CTA visible
   - Playwright screenshot comparison against reference renders

**Exit criteria:**
- Typography engine handles all 6 archetypes
- Text overflow rate <5% across 50 random content × template combinations
- Pyright clean
- 15+ tests

**Acceptance test:** Generate 20 posters using professional templates + random briefs. Operator rates ≥15 as "typography looks clean and professional."

---

### Phase 2: Exemplar Baseline + Visual QA

#### S-E1: Exemplar Seeding + NIMA Calibration
**Duration:** 1.5 days
**Depends on:** S-T2
**Can run parallel with:** S-B1

**Deliverables:**
1. Exemplar generation: Render the top 50-80 professional templates with high-quality sample content → screenshot → NIMA score → CLIP embed → insert into `exemplars` table

2. NIMA calibration: Run `scripts/calibrate_nima.py` against:
   - D12 PosterIQ rated images (correlation check)
   - Operator exemplars (taste target)
   - Update `config/quality_frameworks/nima_thresholds.yaml` with calibrated values

3. Exemplar API: Verify `retrieve_similar_exemplars()` returns ranked results from the seeded table (CLIP ViT-B/32 similarity, threshold ≥0.5)

4. Industry exemplar distribution: Ensure ≥3 exemplars per industry (food, fashion, tech, education, retail, healthcare, real_estate, automotive, general)

**Exit criteria:**
- ≥50 rows in exemplars table with CLIP embeddings
- NIMA calibration report generated with Pearson/Spearman correlations
- `retrieve_similar_exemplars(image, client_id)` returns ≥1 result for any poster-shaped input
- Pyright clean
- 10+ tests

**Acceptance test:** Generate 5 posters. For each, `retrieve_similar_exemplars()` returns ≥2 relevant professional exemplars (human verifies relevance).

---

#### S-E2: Exemplar-Anchored Quality Gates
**Duration:** 1.5 days
**Depends on:** S-E1
**Can run parallel with:** S-B2

**Deliverables:**
1. Upgrade 4-dim critique: Modify `tools/visual_scoring.py` `score_with_exemplars()` to:
   - Retrieve top-3 similar exemplars for the generated image
   - Include exemplar descriptions in the critique prompt: "Compare this output against these professional references: [exemplar 1 description], [exemplar 2 description], [exemplar 3 description]"
   - Score each dimension (composition, typography, colour, layout) relative to exemplars, not absolute
   - Return specific improvement suggestions, not just scores

2. Professional appearance gate: New function `passes_professional_gate()` in `tools/visual_scoring.py`:
   - NIMA score ≥ calibrated `pass_above` threshold
   - 4-dim average ≥ 3.5/5.0 (with exemplar context)
   - If fails: return specific reasons + suggested fixes
   - If passes: proceed to delivery

3. Wire rejection + regeneration: Modify executor's tripwire loop to:
   - On quality gate failure: regenerate image with modified prompt (incorporating critique feedback)
   - Maximum 2 regeneration attempts before delivering best-of-3
   - Log all attempts to production trace

4. Build visual delta comparison: Implement the function referenced in `middleware/quality_gate.py` — compare rendered output against template reference render, flag significant deviations

**Exit criteria:**
- 4-dim critique produces exemplar-relative scores (not generic)
- `passes_professional_gate()` rejects ≥30% of random low-quality test images
- Tripwire regeneration produces measurably better output on second attempt ≥50% of the time
- Visual delta function exists and runs
- Pyright clean
- 15+ tests

**Acceptance test:** Generate 20 posters. Quality gate rejects ≥5. Regenerated versions are rated better by operator ≥3 of 5 times.

---

### Phase 3: Children's Book Pipeline

#### S-B1: Story Architecture
**Duration:** 2 days
**Depends on:** S-T2 (needs professional book layout templates)
**Can run parallel with:** S-E1, S-E2

**Deliverables:**
1. Implement `story_workshop` (replace stub in `tools/registry.py`):
   - Input: brief (age, language, theme, page count)
   - GPT-5.4-mini generates: story premise, character list, thematic arc, tone
   - Output: StoryBible contract (already defined in `contracts/publishing.py`)

2. Implement `scaffold_build` (replace stub in `tools/registry.py`):
   - Input: StoryBible + CharacterBible
   - GPT-5.4-mini generates per page: word_target, emotional_beat, characters_present, text_image_relationship, `illustration_shows` (detailed visual description), page_turn_effect, composition_guide
   - Output: NarrativeScaffold (already defined in `contracts/publishing.py`)
   - Validate: `illustration_shows` is always populated (anti-drift #49 enforcement)

3. CharacterBible generation from brief:
   - GPT-5.4-mini generates physical descriptions, clothing, style notes
   - Output format matches `contracts/publishing.py` CharacterBible schema
   - Includes reference prompt for initial character illustration generation

4. Wire into `childrens_book_production.yaml` workflow:
   - Workshop stage calls character_workshop → story_workshop → scaffold_build
   - Page production stage reads from NarrativeScaffold (not page text) for illustration prompts
   - Verify illustration prompts come from `illustration_shows` field

**Exit criteria:**
- story_workshop returns valid StoryBible for 5 test briefs
- scaffold_build returns valid NarrativeScaffold with `illustration_shows` on every page
- Workflow YAML runs without hitting stubs
- Pyright clean
- 15+ tests (unit + integration)

**Acceptance test:** Generate scaffold for a 12-page Malay children's book about friendship. Operator reviews: story arc makes sense, page beats feel natural, illustration descriptions are specific enough to prompt from.

---

#### S-B2: Page Composition + Character Consistency
**Duration:** 2 days
**Depends on:** S-B1

**Deliverables:**
1. Dynamic text placement per spread:
   - Read `composition_guide` from NarrativeScaffold per page
   - Select text placement strategy per page based on illustration content and emotional beat
   - Alternate placement across spreads for visual variety (not same strategy on every page)
   - Implement in `tools/publish.py` as `select_page_layout(scaffold_page, illustration_metadata)`

2. Character consistency enforcement:
   - After illustration generation, run CLIP verification against CharacterBible reference
   - Threshold: 0.75 on cropped character region (existing code)
   - **New:** On failure, regenerate with Kontext iterative using character reference image
   - Maximum 3 regeneration attempts before accepting best match
   - Re-anchor every 8 pages (existing architecture)
   - Wire this into the page production loop in the workflow executor

3. Page assembly pipeline:
   - Illustration (from `illustration_shows`) + text (from section generation) + layout (from composition_guide) → Typst assembly per page
   - Table of contents, title page, back cover generated from StoryBible
   - EPUB/PDF compilation with consistent styling

4. End-to-end children's book test:
   - `tests/integration/test_childrens_book_quality.py`
   - Generate full 12-page book
   - Verify: all pages have illustrations, text doesn't overflow, characters appear consistent (CLIP > 0.65 full-page), narrative arc matches scaffold

**Exit criteria:**
- Dynamic layout varies across ≥3 different strategies in a 12-page book
- Character CLIP verification triggers regeneration when appropriate
- Full book generates end-to-end in <5 minutes (mocked image gen)
- Pyright clean
- 15+ tests

**Acceptance test:** Generate a 12-page illustrated children's book. Operator reviews: characters look consistent, page layouts vary, text is readable, story flows. Rates ≥6 of 12 pages as "commercially acceptable."

---

### Phase 4: Integration + Polish

#### S-I1: End-to-End Acceptance
**Duration:** 2 days
**Depends on:** S-E2 + S-B2

**Deliverables:**
1. Poster acceptance run:
   - Generate 50 posters across 5 industries × 5 occasions × 2 languages
   - Score each with calibrated NIMA + exemplar-anchored 4-dim critique
   - Operator rates a random sample of 20
   - Target: ≥75% rated "Canva-floor or better"
   - Document failure modes: top 5 most common quality issues

2. Children's book acceptance run:
   - Generate 10 books: 5 Malay, 5 English, ages 3-5 and 5-8
   - Operator reviews each for: character consistency, narrative coherence, page composition, text readability
   - Target: ≥6 of 10 rated "commercially viable"
   - Document failure modes

3. Fix top 5 failure modes for each pipeline:
   - Diagnose root cause of each
   - Implement fix in-session (H6: audits must ship fixes)
   - Re-run the failing cases to verify improvement

4. Regression test suite:
   - Add automated tests that codify the acceptance criteria
   - "Generate poster for Raya food promotion → NIMA ≥ calibrated threshold → 4-dim average ≥ 3.5"
   - These become the permanent quality regression suite

**Exit criteria:**
- 50 posters generated, ≥75% operator-rated acceptable
- 10 books generated, ≥60% operator-rated commercially viable
- Top 5 failure modes per pipeline fixed and regression-tested
- Pyright clean
- 20+ new acceptance tests

---

#### S-I2: Governance + Infrastructure Wiring
**Duration:** 2 days
**Depends on:** S-I1

**Deliverables:**
1. Wire existing governance onto the quality-proven pipeline:
   - Policy evaluation on every request (already built, verify it runs)
   - Quality posture selection (draft/standard/premium) affects rendering effort
   - Readiness gate feeds auto-enrichment (already built, verify end-to-end)
   - Coaching response returned for thin briefs (already built, verify JSON flow)

2. Wire knowledge retrieval:
   - Implement `knowledge_store` (currently stubbed)
   - Ingest industry-specific knowledge cards from D8 marketing data
   - Verify `contextualise_card()` runs during retrieval
   - Knowledge context injected into copy generation prompts

3. Wire self-improvement baseline:
   - Seed 10-15 anchor set exemplars from the acceptance run (best outputs)
   - Verify drift detection functions can compare new output against anchors
   - Verify pattern detection runs on production traces from acceptance run

4. Update workflow registry:
   - `_DELIVERABLE_WORKFLOWS` reflects only truly deliverable workflows
   - Phase gates enforce stub blocking
   - Extended workflows (social, calendar, serial fiction) clearly marked as future

5. Comprehensive hardening:
   - Run every deliverable workflow end-to-end
   - Verify every integration point (routing → interpretation → readiness → policy → generation → scoring → delivery)
   - Fix anything that breaks

**Exit criteria:**
- All governance layers run on every request
- Knowledge retrieval returns relevant cards for ≥3 industries
- Self-improvement baseline seeded (≥10 anchor exemplars)
- All deliverable workflows pass end-to-end test
- `_DELIVERABLE_WORKFLOWS` matches reality (tested, not declared)
- Pyright clean
- Full test suite passes (expect 1000+ tests)

---

## Critical Path

```
                  ┌─────────────────────────────────────────┐
                  │           PARALLEL TRACK                │
                  │                                         │
S-T1 ──→ S-T2 ──┤──→ S-E1 ──→ S-E2 ──┐                   │
                  │                     │                   │
                  │──→ S-B1 ──→ S-B2 ──┤                   │
                  │                     │                   │
                  └─────────────────────┤──→ S-I1 ──→ S-I2 │
                                        └───────────────────┘

Timeline (sequential):  S-T1(2d) → S-T2(2d) → S-E1(1.5d) → S-E2(1.5d) → S-I1(2d) → S-I2(2d) = 11 days
Timeline (parallel):    S-T1(2d) → S-T2(2d) → [S-E1+S-B1](2d) → [S-E2+S-B2](2d) → S-I1(2d) → S-I2(2d) = 12 days
                                                but S-B track may take longer, so realistic = 12-14 days
```

**S-B1 and S-B2 can run parallel with S-E1 and S-E2** because poster quality work and children's book architecture are independent. They converge at S-I1 for acceptance testing.

---

## What Existing V1 Code Gets Reused vs Replaced

| V1 Component | Action | Reason |
|--------------|--------|--------|
| `contracts/routing.py` | **Reuse** | Routing algorithm is correct |
| `contracts/readiness.py` | **Reuse** | Readiness classification works |
| `contracts/publishing.py` | **Reuse** | NarrativeScaffold, CharacterBible, StoryBible schemas are correct |
| `contracts/coaching.py` | **Reuse** | Built in quality intelligence session, works |
| `tools/brief_interpreter.py` | **Reuse** | InterpretedIntent extraction works |
| `tools/template_selector.py` | **Upgrade** | Add professional tier bonus, update archetype scoring |
| `tools/visual_scoring.py` | **Upgrade** | Exemplar-anchored critique, professional gate |
| `tools/visual_pipeline.py` | **Upgrade** | Wire rejection + regeneration |
| `tools/registry.py` | **Upgrade** | Replace stubs (story_workshop, scaffold_build), improve rendering |
| `tools/executor.py` | **Upgrade** | Wire tripwire to actually regenerate |
| `tools/publish.py` | **Upgrade** | Dynamic page layout for books |
| `middleware/policy.py` | **Reuse** | Policy engine works |
| `middleware/guardrails.py` | **Reuse** | Brand voice check works |
| `middleware/quality_gate.py` | **Upgrade** | Build visual delta function |
| `tools/image.py` | **Reuse** | Image generation works |
| `config/quality_frameworks/nima_thresholds.yaml` | **Upgrade** | Calibrate with real data |
| `config/coaching_patterns.yaml` | **Reuse** | 9 industries loaded |
| `templates/html/poster_d4_*.html` | **Keep as fallback** | D4 templates become standard tier |
| `templates/html/poster_*.html` (hand-crafted) | **Keep as fallback** | Existing templates become standard tier |

**New professional templates become the primary pool. Existing templates are demoted to `quality_tier: standard` or `quality_tier: d4_derived` and serve as fallbacks when no professional template matches the intent.**

---

## Anti-Drift Rules (New for V2)

Add to CLAUDE.md:

```
#61: No session exits without human-rated acceptance test on ≥5 outputs
#62: No quality gate session until exemplar table has ≥30 professional entries
#63: Professional templates are primary selection pool; D4/hand-crafted are fallback tier
#64: story_workshop and scaffold_build must produce NarrativeScaffold with illustration_shows on every page — never fall back to page-text-derived illustration prompts
#65: Tripwire critique-then-revise must regenerate (not just log) on quality gate failure
```

---

## Session Dependencies (V1 Infrastructure Required)

Each V2 session depends on this V1 infrastructure being stable:

| V2 Session | V1 Dependencies |
|------------|----------------|
| S-T1 | Playwright (S0), template selector structure (S11) |
| S-T2 | Playwright (S0), Jinja2 rendering (S2) |
| S-E1 | CLIP/NIMA (S0), exemplar table (S10a), MinIO (S10a) |
| S-E2 | visual_scoring.py (S13), executor tripwire (S9) |
| S-B1 | publishing contracts (S6/S15), workflow YAML (S9) |
| S-B2 | Kontext iterative (S4/S15b), Typst assembly (S2/S15a) |
| S-I1 | Everything above |
| S-I2 | Policy (S8), knowledge (S18), self-improvement (S19) |

V1 infrastructure is the foundation. V2 builds quality on top of it.

---

## Success Criteria

### Poster Pipeline
- [ ] ≥100 professional templates ingested with `_meta.yaml`
- [ ] Typography engine handles dynamic sizing, hierarchy, CTA
- [ ] ≥50 exemplars in table with CLIP embeddings
- [ ] NIMA calibrated against D12 + operator taste
- [ ] 4-dim critique is exemplar-anchored (not generic)
- [ ] Quality gate rejects and regenerates (not just logs)
- [ ] 50 generated posters, ≥75% operator-rated "Canva floor or better"

### Children's Book Pipeline
- [ ] story_workshop produces valid StoryBible
- [ ] scaffold_build produces NarrativeScaffold with `illustration_shows` per page
- [ ] Dynamic text placement varies across spreads
- [ ] Character CLIP verification triggers regeneration on failure
- [ ] 10 generated books, ≥60% operator-rated "commercially viable"

### System-Wide
- [ ] Full test suite passes (1000+ tests)
- [ ] All deliverable workflows verified end-to-end
- [ ] `_DELIVERABLE_WORKFLOWS` matches tested reality
- [ ] Governance, knowledge, self-improvement wired onto quality-proven pipeline
- [ ] No stub in any deliverable workflow path
