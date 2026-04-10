# Decision Record: The Dataset Transformation Gap

**Date:** 2026-04-10  
**Status:** Active  
**Scope:** Architecture process, dataset utilisation, quality floor

---

## 1. What Happened

All 19 build sessions shipped. Every session met its exit criteria. 884 tests pass. The system runs end-to-end.

But 28 GB of downloaded datasets sit on disk producing zero quality improvement. The architecture described transformation outcomes ("element position heatmaps from CGL", "preference calibration from PosterCraft"). The build plan assigned extraction tasks ("download D4, extract quality framework"). The transformation step — turning raw data into actionable templates, calibrated thresholds, and better prompts — was never assigned to any session.

### The Pattern (repeated 6 times)

```
Architecture doc says:   "[outcome] from [dataset]"
Build plan assigns:      "Download [dataset], extract [metadata]"
Nobody assigns:          "Process [dataset] → produce [outcome]"
Result:                  Data on disk. Outcome not delivered.
```

### Specific instances

| Architecture promise | S5 delivered | Nobody delivered |
|---|---|---|
| §38.3 "Element position heatmaps from CGL 60K" | Downloaded D4. Created poster/LAYOUT.md description. | Load 60K bounding boxes, cluster into layout archetypes, generate HTML templates |
| §38.3 "Quality evaluation framework from PosterCraft Reflect-120K" | Created posteriq_quality_dimensions.yaml | Calibrate NIMA + critique thresholds against actual rated poster data |
| §38.3 "Preference calibration from PosterCraft Preference-100K" | D2/D3 unavailable. D12 downloaded. | Convert D12 pairs → GEPA bootstrap jsonl |
| §30.5 "NIMA pre-screen with calibrated thresholds" | NIMA scorer built with hardcoded thresholds | Run NIMA on rated posters, find thresholds that match expert judgment |
| §38.4 "CTA formula library from ad copy datasets" | Created cta_formulas.yaml from D7/D8 | Wire formulas into copy generation prompts (formulas exist as config, never injected) |
| §15.10 "Anchor set drift detection" | score_anchor_set() function built | No anchor examples exist (need production data), no cron scheduled |

### Why it happened

The architecture doc is written as an **outcome specification** — it describes what the system looks like when complete. The build plan translates outcomes into **session-sized deliverables**. The translation step decomposed each outcome into:

1. ✅ Infrastructure (tables, functions, contracts)
2. ✅ Data acquisition (download datasets, extract metadata)
3. ❌ Data processing (transform raw data into quality artifacts)

Step 3 was assumed to be part of step 2, but it's fundamentally different work. Downloading D4 and extracting a layout description is 30 minutes. Loading 60K annotations, clustering, and generating 20+ production HTML templates is a full session.

### Why nobody caught it

Each session's exit criteria tested its own deliverables:
- S5 exit: "55 DESIGN.md files created" ✅
- S13 exit: "NIMA pre-screen catches low-quality images" ✅
- S19 exit: "Pattern detector finds approval correlations" ✅

No exit criteria tested **cross-session integration**:
- ❌ "NIMA thresholds calibrated against D12 expert ratings"
- ❌ "Template selector has 30+ templates derived from D4 clusters"
- ❌ "Quality scorer reads thresholds from config, not hardcoded"

The integration tests (IT-1 through IT-5) tested the pipeline flow, not whether the pipeline used the dataset-derived artifacts.

---

## 2. Impact

### Quality floor today

- **Templates:** 10 hand-designed layouts. No industry-specific variants. Template selector picks from a narrow pool regardless of niche.
- **Quality thresholds:** Hardcoded guesses (NIMA: regenerate < 4.0, pass > 7.0). Unknown alignment with human judgment. May be passing mediocre work or rejecting acceptable work.
- **Coaching:** Static 5-question list for thin briefs. No dynamic questions. System proceeds silently with gaps.
- **Exemplar benchmarking:** 8 seed exemplars for one client. No cross-industry exemplar access. Clientless requests get zero exemplar context.
- **GEPA:** Dependency installed. Zero imports. Zero preference data converted.

### Quality ceiling blocked by

- No mechanism to improve templates from data (the 10 we have are the ceiling)
- No mechanism to calibrate scoring from expert ratings (thresholds may be wrong in both directions)
- No mechanism to feed production feedback into threshold adjustment (improvement loop is dormant until production starts, and even then the wiring is incomplete)

---

## 3. Fix — The Data Transformation Sprint

### Principle

Every dataset must have a **transformation owner** and a **verification test**. The transformation produces a committed artifact (template, config value, prompt string). The test proves the artifact is used at runtime.

### Session: S-DATA (Dataset Processing)

**Duration:** 2-3 sessions  
**Depends on:** All sessions complete (they are)  
**Blocks:** Production launch quality bar

#### Phase 1: Template Intelligence (1 session)

| Task | Dataset | Output | Verification |
|---|---|---|---|
| Cluster D4 layouts → HTML template archetypes | D4 (60K) | 20-30 new `templates/html/*.html` + `*_meta.yaml` | Template selector returns D4-derived template for food/fashion/event brief |
| Tag templates with industry from D5 | D5 (3.9K) | `industry_fit` field in each `_meta.yaml` | Template selector scores industry dimension |
| Validate text zones against D9 saliency | D9 (10K) | CSS fixes + saliency report per template | Every template headline zone > 60% saliency overlap |

#### Phase 2: Quality Calibration (1 session)

| Task | Dataset | Output | Verification |
|---|---|---|---|
| Calibrate NIMA against D12 expert ratings | D12 (219 rated) | Updated thresholds in `phase.yaml` or config | NIMA agree rate > 70% with expert ratings |
| Calibrate dimension weights from D12 | D12 (219 rated) | Updated weights in `posteriq_quality_dimensions.yaml` | Scorer reads weights from config, not hardcoded |
| Check NIMA against Open Image Preferences | OIP (10K pairs) | NIMA agreement report | Agreement rate documented |
| Convert D12 → GEPA bootstrap pairs | D12 (5K derivable) | `datasets/gepa_bootstrap/d12_prefs.jsonl` | File exists, ≥ 3K valid pairs |
| Synthesize failure feedback for low-rated D12 | D12 (124 posters ≤ 4) | Failure diagnoses in bootstrap jsonl | Each low-rated poster has a diagnosis string |

#### Phase 3: Prompt Intelligence (half session)

| Task | Dataset | Output | Verification |
|---|---|---|---|
| Extract marketing brief patterns from D8 | D8 (689) | Improved `_REFINEMENT_SYSTEM` prompt | Coaching generates industry-specific questions, not generic |
| Extract copy completeness patterns from D7 | D7 (1K) | Content gate definitions in `tools/coaching.py` | Content gate detects missing promotion details |
| Wire CTA/headline formulas to copy generation | D7, D8 | Prompt injection in copy_generate tool | Generated copy uses formula structure |

#### Phase 4: Wiring (half session)

| Task | Input | Output | Verification |
|---|---|---|---|
| Scorer reads thresholds from YAML, not hardcoded | `posteriq_quality_dimensions.yaml` | Updated `visual_scoring.py` | Changing YAML value changes scorer behavior |
| Scorer reads dimension weights from YAML | `posteriq_quality_dimensions.yaml` | Updated `visual_scoring.py` | Changing weight in YAML changes weighted score |
| Template selector scores `industry_fit` | Template meta.yaml `industry_fit` field | Updated `template_selector.py` | Food brief → food-tagged template preferred |

---

## 4. Prevention — New Anti-Drift Rules

### Rule #58: No dataset without a transformation owner

> Every dataset referenced in the architecture MUST have:
> 1. A session that **acquires** it (download, access, validate format)
> 2. A session that **transforms** it (process into committed artifact)
> 3. A **verification test** proving the artifact is consumed at runtime
>
> The transformation session and verification test MUST be explicit in the build plan. If the architecture says "X from dataset Y", the build plan must have a session row with exit criteria: "X exists and is verified consumed by Z."

### Rule #59: No hardcoded threshold without a calibration source

> Every numeric threshold in the codebase (quality scores, token limits, similarity cutoffs) MUST either:
> 1. Be read from a config file (not hardcoded in Python), OR
> 2. Have a documented justification for the specific value
>
> Config-driven thresholds MUST have a calibration section in the build plan specifying which data source will validate or adjust the value.

### Rule #60: Exit criteria must test cross-session integration

> Session exit criteria MUST include at least one test that verifies integration with upstream data or downstream consumers. Examples:
> - "Scorer reads thresholds from S5-produced config file"
> - "Template selector returns S5-derived template for industry query"
> - "Coaching prompt includes D8-derived question patterns"
>
> Exit criteria that only test the session's own code in isolation are necessary but insufficient.

---

## 5. Process Change — Build Plan Template

Every future build plan session spec must include this section:

```markdown
### Data Dependencies

| Dataset/Config | Acquired by | Transformed by | Consumed by | Verification |
|---|---|---|---|---|
| D4 CGL layouts | S5 | THIS SESSION | template_selector.py | test_template_from_d4_cluster |
| phase.yaml thresholds | S5 | THIS SESSION | visual_scoring.py | test_scorer_reads_config |
```

If the "Transformed by" column says a different session, that session's exit criteria must include the transformation. If it says "N/A" (raw data not processed), the architecture must justify why the data exists.

---

## 6. Broader Lesson

The architecture described a **system that learns from data**. The build plan built a **system with data nearby**. The difference is the transformation pipeline — the code that reads raw annotations and writes production-quality artifacts. This code is unsexy, often simple (clustering, threshold fitting, template generation), but it's the bridge between "we have data" and "the data improves quality."

Future architecture docs should distinguish three layers:

```
Layer 1: Infrastructure  — "the system CAN learn"  (tables, functions, APIs)
Layer 2: Acquisition     — "the system HAS data"    (downloads, imports, seeds)
Layer 3: Transformation  — "the system IS better"   (processing, calibration, generation)
```

All three layers must have session owners and exit criteria. Layer 3 is the one that got missed.
