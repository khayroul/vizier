# S-DATA — Dataset Transformation Sprint

**Date:** 2026-04-10  
**Status:** SPEC (not yet started)  
**Depends on:** All 19 sessions complete (they are)  
**Blocks:** Production launch quality bar  
**Duration:** 2-3 sessions (~8-12 hours)  
**Decision record:** `docs/decisions/dataset_transformation_gap.md`  
**Anti-drift rules:** #58 (transformation owner), #59 (calibration source), #60 (cross-session integration)

---

## 0. Why This Exists

All 19 build sessions shipped. 884 tests pass. The system runs end-to-end. But 28 GB of downloaded datasets sit on disk producing zero quality improvement. The architecture described transformation outcomes ("element position heatmaps from CGL", "preference calibration from PosterCraft"). The build plan assigned extraction tasks ("download D4, extract quality framework"). The **transformation step** — turning raw data into actionable templates, calibrated thresholds, and better prompts — was never assigned to any session.

This sprint bridges the gap. Every task produces a **committed artifact** (HTML template, YAML config value, prompt string) and a **verification test** proving the artifact is consumed at runtime.

---

## 1. Inventory — What's On Disk vs What's Consumed

| Dataset | Size | Status | Artifact Produced by S5 | Transformation Needed |
|---------|------|--------|------------------------|-----------------------|
| D1 HQ-Poster-100K | 5.9 GB | Partial (8/94 parquets) | None | Visual DNA seed (2K images → exemplar embeddings) |
| D4 CGL-Dataset V2 | 6.7 GB | Full (15 parquets) | `poster/LAYOUT.md` description | Cluster 60K layouts → HTML template archetypes |
| D5 Magazine Layout | 4.3 GB | Full (10 parquets) | None | Tag templates with industry from 6 categories |
| D7 Ads Creative Text | ~50 MB | Full | `cta_formulas.yaml` (config, never injected) | Wire CTA/headline formulas into copy prompts |
| D8 Marketing Social | ~20 MB | Full | None | Extract brief patterns → coaching prompts |
| D9 PKU-PosterLayout | 6.9 GB | Full (15 parquets) | None | Validate text zones against saliency maps |
| D12 PosterIQ | 3.2 GB | Full (data.zip) | `posteriq_quality_dimensions.yaml` (4 dims, equal weights) | Calibrate NIMA thresholds, dimension weights, generate GEPA pairs |
| D14 MalayMMLU | 132 MB | Full | None | BM model benchmark for S19 (out of scope for S-DATA) |
| D16 Open Image Prefs | ~11.7 GB | Partial (downloading) | None | NIMA agreement validation, additional preference pairs |
| D2/D3 | Empty | Unavailable | — | D12 compensates |
| D10 Children's Stories | Empty | Unavailable | — | Deferred to S15 |

---

## 2. Phase 0 — Data Verification (30 minutes, MUST run first)

### Task 0.1: Unpack D12 and Verify Images Exist

```
id: S-DATA-0.1
dataset: D12 PosterIQ (data.zip, 3.2 GB)
output: Unpacked directory + verification report
verification: test_d12_poster_images_accessible
```

**Steps:**
1. Unzip `datasets/D12_PosterIQ/data.zip` into `datasets/D12_PosterIQ/images/`.
2. Cross-reference `und_task/overall_rating.json` paths against unpacked files.
3. Verify ≥200 poster images are accessible (JPG or PNG).
4. If images are NOT in data.zip: check D12 README for separate download instructions. If images require separate download, document in status report and reorder Day 1 to start with Phase 1 (templates) while images download.

**Gate:** If fewer than 100 poster images are accessible after unpacking, Phase 2 (calibration) is BLOCKED. Proceed with Phase 1 (templates) and Phase 3 (prompts) while investigating.

### Task 0.2: Validate D4 Parquet Schema

```
id: S-DATA-0.2
dataset: D4 CGL-Dataset V2 (15 parquets)
output: Schema report confirming columns needed for clustering
verification: test_d4_has_bbox_annotations
```

**Steps:**
1. Load first parquet. Print schema.
2. Verify columns include bounding box annotations (x, y, width, height) and element type labels.
3. Count total rows (expected ~61K).
4. Sample 10 rows. Verify annotations are parseable.

---

## 3. Phase 1 — Template Intelligence (1 session, ~4 hours)

### Task 1.1: Cluster D4 Layouts → HTML Template Archetypes

```
id: S-DATA-1.1
dataset: D4 CGL-Dataset V2 (~61,583 layouts, 15 parquets)
depends_on: S-DATA-0.2 (schema validated)
input_format: Parquet with COCO annotations, 5 element types (text, underlay, embellishment, image, logo)
output: 20-30 new templates/html/poster_*.html + *_meta.yaml
consumed_by: tools/publish.py → render_poster_html()
verification: test_template_selector_returns_d4_template
```

**Steps:**
1. Load all 15 parquets with `pd.read_parquet()`. Extract bounding box annotations per layout.
2. Normalize coordinates to 0-1 range (layouts vary in absolute size).
3. Cluster layouts by element positions using k-means (k=25-40, elbow method).
4. For each cluster centroid: generate an HTML/CSS template with zones for the dominant element positions.
5. Name templates by visual archetype (e.g., `poster_hero_left`, `poster_grid_3col`, `poster_text_heavy_top`).
6. Write `_meta.yaml` for each with density, tone_fit, occasion_fit, cta_prominence, hero_style, supported_slots — matching existing template metadata schema.
7. Register new templates in `config/poster_templates.yaml`.

**Current state:** 10 hand-designed templates. No `industry_fit` field in any meta.yaml.

**Exit criteria:**
- ≥20 new HTML templates in `templates/html/` with valid `_meta.yaml`
- Each template renders without error in Playwright (smoke test)
- `config/poster_templates.yaml` lists all new templates
- Template selector returns a D4-derived template when given a food/fashion/event brief

### Task 1.2: Tag Templates with Industry from D5

```
id: S-DATA-1.2
dataset: D5 Magazine Layout (3,919 layouts, 10 parquets, 6 industry categories)
input_format: Parquet with industry labels (fashion, food, news, science, travel, wedding)
output: industry_fit field in each _meta.yaml
consumed_by: contracts/routing.py → select_design_systems() / template selector
verification: test_template_selector_scores_industry
```

**Steps:**
1. Load D5 parquets. Extract industry labels and layout structures.
2. Cross-reference D5 industry clusters against D4-derived template archetypes (by structural similarity).
3. Assign `industry_fit: [list]` to each template's `_meta.yaml` (both existing 10 and new D4-derived).
4. Update template selector scoring to include `industry_fit` dimension.

**Exit criteria:**
- Every template `_meta.yaml` has `industry_fit` field (list of 1-3 industries)
- Template selector uses `industry_fit` when `InterpretedIntent.industry` is set
- Food brief → food-tagged template preferred over generic

### Task 1.3: Validate Text Zones Against D9 Saliency

```
id: S-DATA-1.3
dataset: D9 PKU-PosterLayout (9,974 posters, 15 parquets with BASNet+PFPN saliency maps)
input_format: Parquet with saliency maps as images
output: CSS fixes to templates + saliency validation report
consumed_by: templates/html/*.html (offline correction)
verification: test_headline_zone_saliency_overlap
```

**Steps:**
1. Load D9 parquets. Extract saliency maps.
2. For each D4-derived template: overlay text zones against D9 saliency probability maps.
3. Compute overlap score: what % of the template's headline zone falls in high-saliency regions.
4. Templates where headline zone < 60% saliency overlap → adjust CSS to move text into higher-saliency area.
5. Generate a saliency report per template.

**Exit criteria:**
- Every template's headline zone has ≥60% saliency overlap (or documented exception)
- Saliency report committed to `docs/reports/template_saliency.md`
- At least 3 templates have CSS fixes from saliency analysis

---

## 3. Phase 2 — Quality Calibration (1 session, ~4 hours)

### Task 2.1: Build D12 Data Loader

```
id: S-DATA-2.1
dataset: D12 PosterIQ (und_task/*.json + images from data.zip)
depends_on: S-DATA-0.1 (images verified accessible)
output: scripts/load_posteriq.py — loads D12 into structured Python dicts
verification: test_posteriq_loader_returns_valid_records
```

**Steps:**
1. Build a loader for `und_task/overall_rating.json` (219 records) → returns poster image path + reference score (1-10).
2. Build a loader for A/B comparison tasks → returns preference pairs.
3. Build a loader for style/composition tasks → returns classification labels.
4. Verify: ≥219 quality-scored records, ≥17 style categories.

**D12 actual file inventory (verified):**

| File | Items | Type |
|------|-------|------|
| overall_rating.json | 219 | Quality scores (1-10 scale) |
| layout_comprison.json | 256 | Layout A/B comparisons |
| font_matching.json | 400 | Font matching tasks |
| font_effect.json | 450 | Font effect comparisons |
| font_effect_2.json | 125 | Font effect comparisons |
| font_attributes.json | 1,813 | Font attribute identification (NOT A/B pairs) |
| style_understanding.json | 256 | Style classification |
| composition_understanding.json | 117 | Composition understanding |
| intention_understanding.json | 202 | Design intent classification |
| alignment.json | 200 | Alignment assessment |
| Total usable for A/B pairs | **~1,231** | layout + font_matching + font_effect + font_effect_2 |

### Task 2.2: Calibrate NIMA Thresholds Against D12 Reference Scores

```
id: S-DATA-2.2
dataset: D12 PosterIQ (219 scored posters)
depends_on: S-DATA-0.1 (images accessible), S-DATA-2.1 (loader built)
input: Poster images + D12 reference scores (1-10 scale)
output: New config section in config/quality_frameworks/nima_thresholds.yaml (SEPARATE from critique thresholds)
consumed_by: tools/visual_scoring.py → nima_prescreen()
verification: test_nima_reads_thresholds_from_config
```

**Provenance note:** D12 "ground truth" scores are from the PosterIQ benchmark (CVPR 2026). The annotation methodology is not documented in the README — scores may be aggregated LLM evaluations or crowd-sourced, not design expert ratings. We use them as reference scores (best available), not ground truth. The 70% agreement target is provisional. If NIMA-vs-D12 correlation is <0.3, the calibration has limited value and we should retain current thresholds with a documented "uncalibrated" marker.

**Scale clarification:** NIMA produces scores on a 1.0-10.0 scale. The existing `posteriq_quality_dimensions.yaml` thresholds are on a 1-5 critique scale (used by `weighted_score()`). These are DIFFERENT scales. NIMA thresholds go in a NEW config file `config/quality_frameworks/nima_thresholds.yaml` to avoid confusion.

**Steps:**
1. Run NIMA on all 219 D12 poster images (MPS, <100ms each, ~22 seconds total).
2. Collect (nima_score, d12_reference_score) pairs.
3. Compute Pearson/Spearman correlation. If correlation < 0.3, document and skip threshold update.
4. If correlation ≥ 0.3: find optimal thresholds that maximize agreement:
   - `regenerate_below`: NIMA score below which D12 also scored ≤4
   - `pass_above`: NIMA score above which D12 also scored ≥7
5. Write calibrated thresholds to `config/quality_frameworks/nima_thresholds.yaml`.
6. Update `nima_prescreen()` to load from this new YAML.

**Current state:** Hardcoded at `visual_scoring.py:97` (`< 4.0` → regenerate) and `visual_scoring.py:99` (`> 7.0` → pass). These are unvalidated guesses.

**Exit criteria:**
- NIMA correlation and agreement rate documented in `docs/reports/nima_calibration.md`
- `nima_prescreen()` reads from `nima_thresholds.yaml`, not hardcoded values
- Changing YAML threshold value changes `nima_prescreen()` behavior (integration test)
- Calibration report committed

**License note:** D12 is released under a non-commercial research license. The calibrated threshold values (numbers derived from statistical analysis of correlation) are not copyrightable expressions. However, this provenance should be documented.

### Task 2.3: Calibrate Dimension Weights from D12

```
id: S-DATA-2.3
dataset: D12 PosterIQ (219 scored + composition/style annotations)
depends_on: S-DATA-0.1, S-DATA-2.1
output: Updated weights in posteriq_quality_dimensions.yaml
consumed_by: tools/visual_scoring.py → weighted_score() (already reads from YAML)
verification: test_weight_change_changes_weighted_score
```

**Note:** `weighted_score()` at `visual_scoring.py:237-255` ALREADY reads dimension weights from YAML via `_load_quality_dimensions()`. No code wiring needed — only the calibration itself and updating the YAML values.

**Steps:**
1. For each D12 scored poster: run 4-dimension critique (text_visibility, design_layout, colour_harmony, overall_coherence).
2. Fit weights that minimize distance between weighted-dimension score and D12 reference score.
3. If weights differ significantly from current equal 0.25/0.25/0.25/0.25, update YAML.
4. Call `_load_quality_dimensions.cache_clear()` in tests to pick up new values.

**Current state:** All 4 dimensions weighted equally at 0.25. `weighted_score()` reads from YAML correctly. Only the VALUES need calibration.

**Exit criteria:**
- Dimension weights in YAML reflect D12 calibration (may stay 0.25 if data confirms equal weighting)
- Calibration results documented in `docs/reports/dimension_weight_calibration.md`
- Test confirms changing weight in YAML changes weighted score output

### Task 2.4: Convert D12 → GEPA Bootstrap Pairs

```
id: S-DATA-2.4
dataset: D12 PosterIQ A/B comparison tasks (verified counts below)
output: datasets/gepa_bootstrap/d12_prefs.jsonl
consumed_by: Future GEPA integration (dependency installed, zero imports today)
verification: test_gepa_bootstrap_file_valid
```

**Actual A/B pair sources (verified):**
- layout_comprison.json: 256 pairs
- font_matching.json: 400 pairs
- font_effect.json: 450 pairs
- font_effect_2.json: 125 pairs
- **Total: 1,231 pairs** (NOT 2,519 — font_attributes.json has 1,813 items but they are attribute identification tasks, not A/B preference pairs)

**Steps:**
1. Load D12 A/B comparison tasks (4 files, 1,231 total pairs).
2. Convert each pair to GEPA format: `{chosen: image_a_features, rejected: image_b_features, category: "layout"|"font"|"font_effect"}`.
3. For quality-scored posters with score ≤4 in overall_rating.json: generate failure diagnosis string via GPT-5.4-mini (one-shot, estimate ~50-80 posters below 4).
4. Write to `datasets/gepa_bootstrap/d12_prefs.jsonl`.

**Exit criteria:**
- `d12_prefs.jsonl` exists with ≥1,000 valid preference pairs
- Each low-scored poster (≤4) has a `diagnosis` field
- File format validated (JSON Lines, required fields present)

### Task 2.5: NIMA Agreement with Open Image Preferences

```
id: S-DATA-2.5
dataset: D16 Open Image Preferences (10K pairs, ~11.7 GB when complete)
output: Agreement report
consumed_by: docs/reports/nima_oip_agreement.md (reference, not runtime)
verification: Report exists with agreement rate documented
```

**Steps:**
1. Load OIP binarized pairs (if download complete; skip task if not).
2. Run NIMA on both images in each pair.
3. Check: does NIMA prefer the same image as the human annotator?
4. Report agreement rate. If >65%, OIP validates NIMA as a reasonable proxy.

**Exit criteria:**
- Agreement report exists (or skip documented if D16 not fully downloaded)
- If agreement >65%: document as NIMA validation evidence
- If agreement <50%: flag as concern for S19 benchmark design

---

## 4. Phase 3 — Prompt Intelligence (half session, ~2 hours)

### Task 3.1: Extract Brief Patterns from D8 → Coaching Prompts

```
id: S-DATA-3.1
dataset: D8 Marketing Social Media (689 records)
output: Updated _REFINEMENT_SYSTEM prompt in contracts/routing.py
consumed_by: contracts/routing.py → refine_request()
verification: test_coaching_generates_industry_specific_questions
```

**Steps:**
1. Load D8 records. Categorize by industry/niche.
2. Extract patterns: what information do complete marketing briefs contain that incomplete ones don't?
3. Build industry-specific question patterns (food → "what dish/product?", fashion → "what season/collection?", education → "what age group?").
4. Update `_REFINEMENT_SYSTEM` prompt to include industry-specific coaching patterns.

**Current state:** Coaching is a static 5-question list. Does not adapt to industry. `refine_request()` exists but uses a generic prompt.

**Exit criteria:**
- `_REFINEMENT_SYSTEM` prompt includes industry-specific question examples
- `refine_request()` generates industry-specific questions (test with food, fashion, education briefs)

### Task 3.2: Extract Copy Completeness Patterns from D7

```
id: S-DATA-3.2
dataset: D7 Ads Creative Text (1K records)
output: Content gate definitions in tools/coaching.py (new file)
consumed_by: plugins/vizier_tools_bridge.py → _maybe_coach_thin_brief()
verification: test_content_gate_detects_missing_promotion
```

**Steps:**
1. Load D7 records. Analyze which fields are present in high-performing ad copy.
2. Define per-workflow content gates:
   - Poster: needs promotion OR event + date/time + contact/location
   - Document: needs topic + purpose + audience
   - Brochure: needs product/service + target audience + key selling points
3. Update coaching to check content gates, not just word count.

**Current state:** `_maybe_coach_thin_brief()` checks `len(meaningful) >= 5`. A 5-word brief with no promotion details passes; a 4-word brief with everything needed gets coached.

**Exit criteria:**
- Content gate definitions exist per deliverable workflow
- Coaching detects "missing promotion details" for a poster brief that has 10 words but no promotion
- Coaching passes a 4-word brief that has all critical fields for its workflow

### Task 3.3: Wire CTA/Headline Formulas to Copy Generation

```
id: S-DATA-3.3
dataset: D7, D8 (already extracted to config/copy_patterns/formal_bm.yaml)
output: Updated tools/registry.py → _generate_copy() with config-driven prompt injection
consumed_by: copy generation at runtime
verification: test_copy_generate_uses_formula_structure
```

**Injection mechanism:** The actual function is `_generate_copy()` at `tools/registry.py:917-936`. It uses a barebones system prompt `"Generate marketing copy."` with no mechanism for config-driven patterns. The wiring approach:

1. Create `utils/copy_patterns.py` with `load_copy_patterns(language: str, industry: str) -> str` that reads from `config/copy_patterns/` and returns a formatted prompt fragment with relevant CTA + headline formulas.
2. Modify `_generate_copy()` to call `load_copy_patterns()` and prepend the result to its system prompt.
3. The function receives `interpreted_intent` in its tool context (threaded via workflow executor), so language + industry are available.

**Steps:**
1. Read existing `config/copy_patterns/formal_bm.yaml`.
2. Expand with CTA formulas from D7 and headline formulas from D8 (if not already present).
3. Create `utils/copy_patterns.py` loader.
4. Modify `_generate_copy()` to inject loaded patterns into system prompt.

**Current state:** Config files exist but are never loaded by any production code.

**Exit criteria:**
- `_generate_copy()` system prompt includes formula examples from config
- Different industries get different formula suggestions (test with food vs fashion)
- Config change → prompt change (no hardcoded formulas)

---

## 5. Phase 4 — Wiring (half session, ~2 hours)

### Task 4.1: Scorer Reads NIMA Thresholds from Dedicated YAML

```
id: S-DATA-4.1
input: config/quality_frameworks/nima_thresholds.yaml (NEW file, created by Task 2.2)
output: Updated tools/visual_scoring.py
consumed_by: nima_prescreen() at runtime
verification: test_changing_yaml_changes_scorer_behavior
```

**Why a new YAML:** NIMA scores are on a 1-10 scale. The existing `posteriq_quality_dimensions.yaml` thresholds (regenerate: 2.0, acceptable: 3.0) are on the 1-5 critique scale used by `weighted_score()`. Mixing scales in one file is a bug waiting to happen. NIMA gets its own config.

**New file: `config/quality_frameworks/nima_thresholds.yaml`:**
```yaml
# NIMA aesthetic score thresholds (1.0-10.0 scale)
# Calibrated against D12 PosterIQ reference scores (Task 2.2)
# Provenance: statistical analysis, not copyrightable expression
nima:
  regenerate_below: 4.0   # ← will be updated by calibration
  pass_above: 7.0         # ← will be updated by calibration
  calibration_source: "D12 PosterIQ (219 posters)"
  calibration_date: null   # ← set by calibration script
  agreement_rate: null     # ← set by calibration script
```

**What changes in visual_scoring.py:**
```python
# BEFORE (visual_scoring.py:97-104)
def nima_prescreen(score: float) -> dict[str, Any]:
    if score < 4.0:           # ← hardcoded
        action = "regenerate"
    elif score > 7.0:         # ← hardcoded
        action = "pass"
    else:
        action = "proceed_with_caution"
    return {"action": action, "score": score}

# AFTER
_NIMA_THRESHOLDS_PATH = (
    Path(__file__).resolve().parent.parent
    / "config" / "quality_frameworks" / "nima_thresholds.yaml"
)

@functools.lru_cache(maxsize=1)
def _load_nima_thresholds() -> dict[str, Any]:
    return yaml.safe_load(_NIMA_THRESHOLDS_PATH.read_text(encoding="utf-8"))

def nima_prescreen(score: float, config: dict | None = None) -> dict[str, Any]:
    cfg = config or _load_nima_thresholds()
    nima_cfg = cfg["nima"]
    if score < nima_cfg["regenerate_below"]:
        action = "regenerate"
    elif score > nima_cfg["pass_above"]:
        action = "pass"
    else:
        action = "proceed_with_caution"
    return {"action": action, "score": score}
```

**Note:** Task 4.2 (scorer reads dimension weights from YAML) is NOT needed — `weighted_score()` at `visual_scoring.py:237-255` already reads weights from `posteriq_quality_dimensions.yaml` via `_load_quality_dimensions()`. Task 2.3 only needs to update the YAML values.

### Task 4.2: Template Selector Scores industry_fit

```
id: S-DATA-4.2
input: Template _meta.yaml files with industry_fit field (from 1.2)
output: Updated tools/template_selector.py with new industry_fit scoring dimension
consumed_by: template selection at runtime
verification: test_food_brief_prefers_food_template
```

**Scope note:** The template selector currently scores on mood, occasion, density, CTA, and slot compatibility. It has ZERO code for industry_fit. This task requires:
1. Adding industry_fit to the _meta.yaml schema (all templates)
2. Loading industry_fit in the template selector
3. Adding a new scoring dimension that matches InterpretedIntent.industry against template industry_fit
4. Adjusting total score weights to incorporate the new dimension
This is ~80-100 lines of new code in template_selector.py, not a trivial config change.

---

## 6. Data Dependencies Matrix (Anti-Drift #58 compliance)

| Dataset | Acquired by | Transformed by | Consumed by | Verification Test |
|---------|-------------|----------------|-------------|-------------------|
| D4 CGL ~61K | S5 (download) | S-DATA-1.1 | templates/html/*.html → publish.py | test_template_from_d4_cluster |
| D5 Magazine 3.9K | S5 (download) | S-DATA-1.2 | _meta.yaml → template_selector | test_template_industry_scoring |
| D7 Ads Creative 1K | S5 (download) | S-DATA-3.2, 3.3 | coaching.py, utils/copy_patterns.py → _generate_copy() | test_content_gate, test_copy_formula |
| D8 Marketing 689 | S5 (download) | S-DATA-3.1 | routing.py → _REFINEMENT_SYSTEM | test_industry_coaching |
| D9 PKU Poster 10K | S5 (download) | S-DATA-1.3 | templates/html/*.html CSS fixes | test_saliency_overlap |
| D12 PosterIQ | S5 (download) | S-DATA-2.1-2.4 | nima_thresholds.yaml + GEPA bootstrap | test_nima_config, test_gepa_pairs |
| D16 OIP 10K | Pre-sprint | S-DATA-2.5 | docs/reports/ (reference) | report_exists |
| nima_thresholds.yaml | S-DATA-2.2 (create) | S-DATA-4.1 (wire) | visual_scoring.py → nima_prescreen() | test_changing_yaml_changes_scorer |
| posteriq_quality_dimensions.yaml | S5 (create) | S-DATA-2.3 (calibrate values) | visual_scoring.py → weighted_score() (already reads) | test_weight_change_changes_score |
| config/copy_patterns/*.yaml | S5 (create) | S-DATA-3.3 | utils/copy_patterns.py → _generate_copy() | test_copy_reads_config |

---

## 7. Exit Criteria (Full Sprint)

### Phase 0
- [ ] D12 data.zip unpacked, poster images verified accessible (≥200 images)
- [ ] D4 parquet schema validated (bbox annotations + element types confirmed)

### Phase 1
- [ ] ≥20 new HTML poster templates with valid _meta.yaml
- [ ] All templates render in Playwright without error
- [ ] Every template has `industry_fit` field
- [ ] Template selector uses `industry_fit` when InterpretedIntent.industry is set (~80-100 lines new code)
- [ ] ≥3 templates have CSS fixes from D9 saliency analysis
- [ ] Saliency report committed

### Phase 2
- [ ] D12 loader built and tested
- [ ] NIMA calibration: correlation + agreement rate documented (≥70% agreement or documented why not)
- [ ] NIMA thresholds in NEW `nima_thresholds.yaml` (separate from critique 1-5 thresholds)
- [ ] Dimension weights calibrated in existing `posteriq_quality_dimensions.yaml` (code already reads them)
- [ ] GEPA bootstrap file: ≥1,000 pairs in valid JSONL (actual source: 1,231 A/B pairs)
- [ ] Low-scored posters have diagnosis strings
- [ ] OIP agreement report (or skip documented)
- [ ] Calibration reports committed
- [ ] D12 non-commercial license provenance documented

### Phase 3
- [ ] Coaching generates industry-specific questions
- [ ] Content gates defined per workflow (not just word count)
- [ ] CTA/headline formulas injected into `_generate_copy()` system prompt via `utils/copy_patterns.py`
- [ ] All config files consumed by production code (not orphaned)

### Phase 4
- [ ] `nima_prescreen()` reads from `nima_thresholds.yaml` (changing config changes behavior)
- [ ] Template selector scores `industry_fit` (new scoring dimension, not just config)
- [ ] No hardcoded threshold in visual_scoring.py without calibration source

### Cross-Session Integration (Anti-Drift #60)
- [ ] Food brief → food-tagged template → food-industry design system (full chain)
- [ ] Changing `nima_thresholds.yaml` → changes nima_prescreen → changes QA pass/fail
- [ ] Coaching surfaces D8-derived industry questions for a Malay restaurant brief

---

## 8. Dependencies and Tooling

**Python packages needed:**
- `pandas` (parquet reading) — check pyproject.toml
- `pyarrow` (parquet backend) — check pyproject.toml
- `scikit-learn` (k-means clustering for D4) — check pyproject.toml
- `Pillow` (image processing for D9 saliency) — likely already installed
- `torch` + NIMA model (already installed, running on MPS)

**Hardware:**
- MPS (Apple Silicon GPU) for NIMA inference on 219+ images (<100ms per image)
- ~10 GB RAM for parquet loading (D4 60K rows, loaded in chunks if needed)

**LLM calls (budget):**
- ~124 GPT-5.4-mini calls for D12 failure diagnosis (Task 2.4)
- ~10 GPT-5.4-mini calls for D8 pattern extraction (Task 3.1)
- ~20 GPT-5.4-mini calls for D7 copy pattern extraction (Task 3.2)
- Total: ~154 calls × ~400 tokens avg = ~62K tokens ≈ $0.05

---

## 9. Priority If Time-Compressed (70% Cut Line)

If only 2 days available, ship these (ordered by quality impact per hour):

1. **Task 0.1 + 0.2** (Phase 0 verification) — gate for everything else
2. **Task 2.2 + 4.1** (NIMA calibration + config wiring) — affects every single poster QA decision
3. **Task 1.1** (D4 template clustering) — 3x template variety, highest visual impact
4. **Task 1.2 + 4.2** (industry tagging + template selector) — industry-aware selection chain
5. **Part A coaching** (content gates + CoachingResponse) — user experience uplift

Cut these (still valuable, just lower priority):
- Task 1.3 (saliency validation) — templates work without it
- Task 2.3 (dimension weight calibration) — current equal weights may be close enough
- Task 2.4 (GEPA bootstrap) — GEPA has zero integration code, pairs would sit idle
- Task 2.5 (OIP agreement) — validation report, not runtime improvement
- Task 3.3 (CTA formula wiring) — incremental improvement over current copy quality
