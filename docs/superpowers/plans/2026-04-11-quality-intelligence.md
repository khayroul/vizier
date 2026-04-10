# Quality Intelligence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn 28 GB of raw datasets + operator taste exemplars into quality-improving artifacts, and build a brief intelligence coaching system that helps Malaysian SMB users produce better briefs.

**Architecture:** Stateless coaching in the Hermes bridge layer (not the orchestrator). Datasets provide structural geometry; operator exemplars define taste; production feedback defines truth. All thresholds read from config YAML, not hardcoded. NIMA 1-10 scale in its own config file, separate from critique 1-5 scale.

**Tech Stack:** Python 3.11, PyMuPDF, pandas/pyarrow, scikit-learn (k-means), torch (NIMA on MPS), Pydantic (contracts), GPT-5.4-mini (all LLM calls), Playwright (template smoke tests)

**Design docs:**
- `docs/decisions/unified_quality_design.md` — master design (coaching + datasets + anti-drift)
- `docs/S_DATA_SESSION_SPEC.md` — task-level dataset transformation spec
- `docs/decisions/dataset_transformation_gap.md` — root cause analysis
- `docs/handover/HANDOVER_017_QUALITY_INTELLIGENCE_DESIGN.md` — full successor handover

**Anti-drift rules to follow:** #54 (GPT-5.4-mini only), #58 (transformation owner + test), #59 (no hardcoded thresholds), #60 (cross-session integration tests)

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `contracts/coaching.py` | CoachingResponse + CoachingQuestion Pydantic contracts |
| `tools/coaching.py` | Per-workflow content gate definitions, language-aware question templates |
| `utils/copy_patterns.py` | Loader for CTA/headline formula config → prompt fragments |
| `config/quality_frameworks/nima_thresholds.yaml` | NIMA 1-10 scale thresholds (separate from critique 1-5) |
| `scripts/ingest_operator_exemplars.py` | Auto-tag operator PNGs via GPT-5.4-mini vision + NIMA + CLIP |
| `scripts/load_posteriq.py` | D12 PosterIQ data loader |
| `scripts/cluster_d4_templates.py` | D4 CGL → HTML template archetype generator |
| `scripts/calibrate_nima.py` | NIMA threshold calibration from D12 + operator exemplars |
| `tests/test_coaching.py` | Tests for coaching contracts and content gates |
| `tests/test_nima_config.py` | Tests for config-driven NIMA thresholds |
| `tests/test_template_industry.py` | Tests for industry_fit template scoring |
| `tests/test_operator_exemplars.py` | Tests for exemplar ingestion pipeline |

### Modified Files

| File | What Changes |
|------|-------------|
| `plugins/vizier_tools_bridge.py:738-774` | `_maybe_coach_thin_brief()` → returns CoachingResponse JSON, uses content gates + interpret_brief() |
| `tools/visual_scoring.py:88-104` | `nima_prescreen()` → reads from `nima_thresholds.yaml` |
| `tools/template_selector.py` | Add `industry_fit` scoring dimension (~80-100 lines) |
| `contracts/routing.py:268-289` | `_REFINEMENT_SYSTEM` prompt → add industry-specific question patterns |
| `tools/registry.py:917-936` | `_generate_copy()` → inject CTA formulas from `utils/copy_patterns.py` |
| `templates/html/*.html` | New D4-derived templates + _meta.yaml with industry_fit |
| `config/quality_frameworks/posteriq_quality_dimensions.yaml` | Updated dimension weights from calibration |

---

## Chunk 1: Foundation — Commit, Verify, Ingest

### Task 1: Commit Design Session Work

**Files:**
- Stage: `CLAUDE.md`, `docs/decisions/dataset_transformation_gap.md`, `docs/decisions/unified_quality_design.md`, `docs/S_DATA_SESSION_SPEC.md`, `scripts/pdf_to_exemplars.py`, `docs/handover/HANDOVER_017_QUALITY_INTELLIGENCE_DESIGN.md`, `docs/superpowers/plans/2026-04-11-quality-intelligence.md`

- [ ] **Step 1: Review unstaged files**

Run: `git status`
Verify: The files listed above appear as untracked or modified.

- [ ] **Step 2: Stage and commit**

```bash
git add CLAUDE.md docs/decisions/dataset_transformation_gap.md docs/decisions/unified_quality_design.md docs/S_DATA_SESSION_SPEC.md scripts/pdf_to_exemplars.py docs/handover/HANDOVER_017_QUALITY_INTELLIGENCE_DESIGN.md docs/superpowers/plans/2026-04-11-quality-intelligence.md
git commit -m "docs(quality): design session — coaching system, S-DATA spec, anti-drift rules #58-60"
```

- [ ] **Step 3: Verify commit**

Run: `git log --oneline -3`
Expected: New commit at HEAD.

---

### Task 2: Phase 0 — Unpack D12 and Validate D4

**Files:**
- Read: `datasets/D12_PosterIQ/data.zip`, `datasets/D4_CGL_Dataset_v2/data/`
- Test: `tests/test_data_verification.py`

- [ ] **Step 1: Write verification tests**

```python
# tests/test_data_verification.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

DATASETS = Path(__file__).resolve().parent.parent / "datasets"


class TestD12Verification:
    """Verify D12 PosterIQ images are accessible after unpacking."""

    def test_d12_poster_images_accessible(self) -> None:
        """At least 200 poster images exist and are referenced by overall_rating.json."""
        ratings_path = DATASETS / "D12_PosterIQ" / "und_task" / "overall_rating.json"
        assert ratings_path.exists(), "overall_rating.json not found"

        ratings = json.loads(ratings_path.read_text())
        assert len(ratings) >= 200, f"Expected >=200 ratings, got {len(ratings)}"

        # Check that image paths resolve
        accessible = 0
        for record in ratings:
            img_path = DATASETS / "D12_PosterIQ" / record.get("path", "")
            if img_path.exists() and img_path.stat().st_size > 0:
                accessible += 1

        assert accessible >= 100, (
            f"Only {accessible}/{len(ratings)} images accessible. "
            "Run: unzip datasets/D12_PosterIQ/data.zip -d datasets/D12_PosterIQ/"
        )


class TestD4Verification:
    """Verify D4 CGL parquets have bbox annotations."""

    def test_d4_has_bbox_annotations(self) -> None:
        """First D4 parquet has required columns for layout clustering."""
        import pandas as pd

        parquet_dir = DATASETS / "D4_CGL_Dataset_v2" / "data"
        parquets = sorted(parquet_dir.glob("train-*.parquet"))
        assert len(parquets) >= 14, f"Expected >=14 parquets, got {len(parquets)}"

        df = pd.read_parquet(parquets[0])
        assert len(df) > 0, "First parquet is empty"
        # Log columns for debugging — exact column names may vary
        print(f"D4 columns: {list(df.columns)}")
        print(f"D4 rows in first parquet: {len(df)}")
        print(f"D4 sample row: {df.iloc[0].to_dict()}")
```

- [ ] **Step 2: Run tests to verify data state**

Run: `pytest tests/test_data_verification.py -v -s`
Expected: D4 test PASSES (parquets exist). D12 test may FAIL if data.zip not unpacked.

- [ ] **Step 3: Unpack D12 data.zip**

```bash
cd datasets/D12_PosterIQ && unzip -o data.zip && cd ../..
```

- [ ] **Step 4: Re-run D12 test**

Run: `pytest tests/test_data_verification.py::TestD12Verification -v -s`
Expected: PASS with >=100 accessible images. If FAIL, check README for separate image download.

- [ ] **Step 5: Examine D4 columns from test output**

Read the printed columns from Step 2. Note exact column names for bounding box data (may be `bbox`, `x/y/w/h`, or nested JSON). This determines the clustering approach in Task 5.

- [ ] **Step 6: Commit**

```bash
git add tests/test_data_verification.py
git commit -m "test(data): Phase 0 verification — D12 images + D4 schema"
```

---

### Task 3: Build Operator Exemplar Ingestion Script

**Files:**
- Create: `scripts/ingest_operator_exemplars.py`
- Test: `tests/test_operator_exemplars.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_operator_exemplars.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.ingest_operator_exemplars import tag_image, ExemplarRecord

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class TestExemplarRecord:
    """ExemplarRecord validates correctly."""

    def test_valid_record(self) -> None:
        record = ExemplarRecord(
            path=Path("test.png"),
            tags={"industry": "food", "mood": "festive", "occasion": "raya"},
            nima_score=6.2,
            critique_scores={"text_visibility": 4.0, "design_layout": 3.8},
            source="operator_curated",
            artifact_family="poster",
        )
        assert record.nima_score == 6.2
        assert record.tags["industry"] == "food"
        assert record.source == "operator_curated"
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `pytest tests/test_operator_exemplars.py -v`
Expected: FAIL — `ImportError: cannot import name 'tag_image'`

- [ ] **Step 3: Write the ingestion script**

Create `scripts/ingest_operator_exemplars.py` with:
- `ExemplarRecord` dataclass (path, tags, nima_score, critique_scores, source, artifact_family)
- `tag_image(image_path: Path) -> dict` — calls GPT-5.4-mini vision to extract industry/mood/occasion/density/cta_style/colour_palette/layout_archetype
- `ingest_exemplar(image_path: Path) -> ExemplarRecord` — full pipeline: tag + NIMA + 4-dim critique
- `ingest_directory(dir_path: Path, collection: str) -> list[ExemplarRecord]` — batch process
- CLI: `python3 scripts/ingest_operator_exemplars.py datasets/operator_exemplars/posters/`
- Output: `datasets/operator_exemplars/manifest.jsonl`

Use `tools/visual_scoring.nima_score()` for NIMA, `tools/visual_scoring.critique_4dim()` for critique, `utils/call_llm.call_llm()` for vision tagging. All GPT-5.4-mini (anti-drift #54).

- [ ] **Step 4: Run test — expect PASS**

Run: `pytest tests/test_operator_exemplars.py -v`
Expected: PASS

- [ ] **Step 5: Pyright check**

Run: `pyright scripts/ingest_operator_exemplars.py`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add scripts/ingest_operator_exemplars.py tests/test_operator_exemplars.py
git commit -m "feat(data): operator exemplar ingestion — auto-tag via vision + NIMA + CLIP"
```

---

## Chunk 2: Quality Calibration (S-DATA Phase 2 + 4)

### Task 4: Build D12 Data Loader

**Files:**
- Create: `scripts/load_posteriq.py`
- Test: `tests/test_posteriq_loader.py`

- [ ] **Step 1: Write the test**

Test that loader returns >=219 quality-scored records from `overall_rating.json`, >=256 A/B pairs from `layout_comprison.json`, and >=17 style categories from `style_understanding.json`.

- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Implement loader** — read JSON files, return typed dicts
- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Pyright check**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(data): D12 PosterIQ loader — ratings, A/B pairs, styles"
```

---

### Task 5: Create nima_thresholds.yaml + Wire nima_prescreen()

**Files:**
- Create: `config/quality_frameworks/nima_thresholds.yaml`
- Modify: `tools/visual_scoring.py:88-104`
- Test: `tests/test_nima_config.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_nima_config.py
from __future__ import annotations

from unittest.mock import patch

import pytest

from tools.visual_scoring import nima_prescreen


class TestNimaConfig:
    """NIMA prescreen reads thresholds from config."""

    def test_default_thresholds(self) -> None:
        """Without config override, uses YAML defaults."""
        result = nima_prescreen(3.5)
        assert result["action"] == "regenerate"

        result = nima_prescreen(7.5)
        assert result["action"] == "pass"

    def test_custom_config_changes_behavior(self) -> None:
        """Passing custom config overrides YAML thresholds."""
        custom = {"nima": {"regenerate_below": 2.0, "pass_above": 5.0}}

        result = nima_prescreen(3.5, config=custom)
        assert result["action"] == "proceed_with_caution"  # NOT regenerate

        result = nima_prescreen(5.5, config=custom)
        assert result["action"] == "pass"  # lower threshold

    def test_changing_yaml_changes_scorer_behavior(self) -> None:
        """Integration test: modifying YAML file changes nima_prescreen output."""
        from tools.visual_scoring import _load_nima_thresholds

        # Clear cache to pick up any changes
        _load_nima_thresholds.cache_clear()

        # Load current config
        cfg = _load_nima_thresholds()
        original_floor = cfg["nima"]["regenerate_below"]

        # Score just above original floor should NOT regenerate
        result = nima_prescreen(original_floor + 0.1)
        assert result["action"] != "regenerate"
```

- [ ] **Step 2: Run — expect FAIL** (nima_prescreen doesn't accept config param yet)

- [ ] **Step 3: Create `config/quality_frameworks/nima_thresholds.yaml`**

```yaml
# NIMA aesthetic score thresholds (1.0-10.0 scale)
# SEPARATE from posteriq_quality_dimensions.yaml (1-5 critique scale)
# Calibrated against D12 PosterIQ reference scores
# Provenance: statistical analysis of correlation, not copyrightable
nima:
  regenerate_below: 4.0
  pass_above: 7.0
  calibration_source: "uncalibrated — defaults pending D12 + operator exemplar calibration"
  calibration_date: null
  agreement_rate: null
```

- [ ] **Step 4: Modify `tools/visual_scoring.py`**

Replace `nima_prescreen()` (lines 88-104) with config-reading version. Add `_NIMA_THRESHOLDS_PATH`, `_load_nima_thresholds()`. See S-DATA spec Task 4.1 for exact code.

- [ ] **Step 5: Run test — expect PASS**
- [ ] **Step 6: Run full test suite** — `pytest tests/ -x -q` (884 existing tests must still pass)
- [ ] **Step 7: Pyright check** — `pyright tools/visual_scoring.py`
- [ ] **Step 8: Commit**

```bash
git commit -m "feat(quality): config-driven NIMA thresholds — separate nima_thresholds.yaml"
```

---

### Task 6: Calibrate NIMA Against D12 + Operator Exemplars

**Files:**
- Create: `scripts/calibrate_nima.py`
- Modify: `config/quality_frameworks/nima_thresholds.yaml` (update values)
- Create: `docs/reports/nima_calibration.md`

- [ ] **Step 1: Write calibration script**

Script runs NIMA on D12 rated posters AND operator exemplars (if available). Computes Pearson/Spearman correlation. Finds optimal thresholds. Writes updated YAML + report.

Key logic: D12 sets the technical FLOOR (regenerate_below). Operator exemplars set the TASTE TARGET (pass_above). If correlation < 0.3, document and keep defaults.

- [ ] **Step 2: Run calibration**

```bash
python3 scripts/calibrate_nima.py
```

- [ ] **Step 3: Review output report** — `docs/reports/nima_calibration.md`
- [ ] **Step 4: Verify updated YAML** — `cat config/quality_frameworks/nima_thresholds.yaml`
- [ ] **Step 5: Re-run NIMA config test**

```bash
pytest tests/test_nima_config.py -v
```

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(quality): calibrate NIMA thresholds from D12 + operator exemplars"
```

---

### Task 7: Calibrate Dimension Weights

**Files:**
- Create: `scripts/calibrate_weights.py`
- Modify: `config/quality_frameworks/posteriq_quality_dimensions.yaml` (weights only)
- Create: `docs/reports/dimension_weight_calibration.md`

NOTE: `weighted_score()` ALREADY reads weights from YAML. Only update the values.

- [ ] **Step 1: Write calibration script** — fit weights against D12 reference scores
- [ ] **Step 2: Run calibration** — `python3 scripts/calibrate_weights.py`
- [ ] **Step 3: Write integration test** — changing YAML weight changes weighted_score output (call `_load_quality_dimensions.cache_clear()` in test)
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(quality): calibrate dimension weights from D12 reference scores"
```

---

## Chunk 3: Template Intelligence (S-DATA Phase 1)

### Task 8: Cluster D4 → HTML Templates

**Files:**
- Create: `scripts/cluster_d4_templates.py`
- Create: `templates/html/poster_d4_*.html` + `*_meta.yaml` (20-30 new files)
- Test: `tests/test_d4_templates.py`

- [ ] **Step 1: Write test** — new D4-derived template renders in Playwright, meta.yaml valid
- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Write clustering script**

Load D4 parquets → normalize bbox coords → k-means (k=25-40) → for each centroid, generate HTML/CSS with zones → write _meta.yaml. Extract STRUCTURE only (element positions), NOT style.

- [ ] **Step 4: Run clustering** — `python3 scripts/cluster_d4_templates.py`
- [ ] **Step 5: Run test — expect PASS**
- [ ] **Step 6: Smoke test** — render 3 sample templates in Playwright
- [ ] **Step 7: Commit**

```bash
git commit -m "feat(templates): 20+ poster templates from D4 layout clusters"
```

---

### Task 9: Tag Templates with industry_fit from D5

**Files:**
- Modify: `templates/html/*_meta.yaml` (add industry_fit field)
- Test: `tests/test_template_industry.py`

- [ ] **Step 1: Write test** — every _meta.yaml has industry_fit field
- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Write tagging script** — cross-reference D5 industry labels against templates by structural similarity
- [ ] **Step 4: Run tagging**
- [ ] **Step 5: Run test — expect PASS**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(templates): industry_fit tags from D5 magazine layouts"
```

---

### Task 10: Wire Template Selector to Score industry_fit

**Files:**
- Modify: `tools/template_selector.py` (~80-100 lines new)
- Test: `tests/test_template_industry.py` (add scoring tests)

- [ ] **Step 1: Write test** — food brief → food-tagged template preferred
- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Add industry_fit scoring dimension** to template selector: load industry_fit from meta YAML, match against InterpretedIntent.industry, add to total score
- [ ] **Step 4: Run test — expect PASS**
- [ ] **Step 5: Pyright check**
- [ ] **Step 6: Full test suite** — `pytest tests/ -x -q`
- [ ] **Step 7: Commit**

```bash
git commit -m "feat(routing): template selector scores industry_fit dimension"
```

---

## Chunk 4: Coaching System (Part A + S-DATA Phase 3)

### Task 11: CoachingResponse Contract

**Files:**
- Create: `contracts/coaching.py`
- Test: `tests/test_coaching.py`

- [ ] **Step 1: Write test** — CoachingResponse serializes to JSON, CoachingQuestion validates
- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Implement** — Pydantic BaseModel, status Literal, questions list. See unified design doc §A.2.1.
- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Pyright check**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(contracts): CoachingResponse + CoachingQuestion contracts"
```

---

### Task 12: Content Gates

**Files:**
- Create: `tools/coaching.py`
- Test: `tests/test_coaching.py` (extend)

- [ ] **Step 1: Write test** — poster gate detects missing promotion; 4-word complete brief passes
- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Implement content gates** — per-workflow definitions. Poster: needs promotion/event + date/price/contact. Document: topic + purpose + audience. Brochure: product + audience + benefits. Language-aware question templates.
- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Pyright check**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(coaching): per-workflow content gates — semantic, not word count"
```

---

### Task 13: Upgrade _maybe_coach_thin_brief()

**Files:**
- Modify: `plugins/vizier_tools_bridge.py:738-774`
- Test: `tests/test_coaching.py` (extend with integration tests)

- [ ] **Step 1: Write test** — "buat poster restoran" returns CoachingResponse JSON with industry=food, questions about promosi/tarikh; "buat poster jualan raya diskaun 30% 1-30 april" passes content gate
- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Implement** — call interpret_brief() for understood context, check content gate, return CoachingResponse JSON. For substantive briefs (>3 meaningful words) that fail gate, call refine_request() for LLM-powered questions. Pass interpreted_intent to run_governed via run_kwargs to avoid double-call.
- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Run full test suite** — `pytest tests/ -x -q` (all 884+ tests pass)
- [ ] **Step 6: Pyright check** — `pyright plugins/vizier_tools_bridge.py`
- [ ] **Step 7: Commit**

```bash
git commit -m "feat(coaching): structured coaching with content gates + refine_request()"
```

---

### Task 14: Update _REFINEMENT_SYSTEM with Industry Patterns (from D8)

**Files:**
- Modify: `contracts/routing.py:268-289`
- Test: `tests/test_coaching.py` (extend)

- [ ] **Step 1: Extract D8 patterns** — load D8, categorize by industry, identify what complete briefs have that incomplete ones lack
- [ ] **Step 2: Write test** — refine_request() generates food-specific questions for food brief
- [ ] **Step 3: Update _REFINEMENT_SYSTEM** — add industry-specific question examples. Put patterns in `config/coaching_patterns.yaml`, not inline. Load at runtime.
- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(coaching): industry-specific question patterns from D8 analysis"
```

---

### Task 15: Cross-Session Integration Tests

**Files:**
- Create: `tests/test_integration_quality.py`

- [ ] **Step 1: Write integration tests** (anti-drift #60)

```python
def test_food_brief_full_chain():
    """Food brief → food template → food design system → poster (full chain)."""
    # This tests the entire flow from brief to template selection

def test_calibrated_threshold_changes_qa():
    """Changing nima_thresholds.yaml → changes nima_prescreen → changes QA."""

def test_coaching_surfaces_industry_questions():
    """Malay restaurant brief → Malay coaching questions with food suggestions."""
```

- [ ] **Step 2: Run — expect PASS**
- [ ] **Step 3: Full test suite** — `pytest tests/ -x -q`
- [ ] **Step 4: Commit**

```bash
git commit -m "test(integration): cross-session quality intelligence tests (#60)"
```

---

## Chunk 5: CTA Wiring + Final Commit (CUT if time-compressed)

### Task 16: Wire CTA Formulas (S-DATA Task 3.3)

**Files:**
- Create: `utils/copy_patterns.py`
- Modify: `tools/registry.py:917-936`
- Test: `tests/test_copy_patterns.py`

- [ ] **Step 1: Write test** — load_copy_patterns returns industry-specific formulas
- [ ] **Step 2: Implement** — `load_copy_patterns(language, industry)` reads from `config/copy_patterns/`
- [ ] **Step 3: Modify _generate_copy()** — prepend formulas to system prompt
- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(copy): inject CTA/headline formulas from config into copy generation"
```

---

### Task 17: Final Verification

- [ ] **Step 1: Full test suite** — `pytest tests/ -x -q` (all tests pass)
- [ ] **Step 2: Pyright clean** — `pyright tools/ contracts/ plugins/ scripts/ utils/`
- [ ] **Step 3: Run poster E2E** (if Hermes available) — "buat poster restoran" → coaching → add details → PDF
- [ ] **Step 4: Verify NIMA uses config** — `grep -n "< 4.0\|> 7.0" tools/visual_scoring.py` (should return nothing)
- [ ] **Step 5: Verify no orphaned config** — every YAML in `config/` is imported somewhere
- [ ] **Step 6: Create `docs/reports/` directory** — `mkdir -p docs/reports`
- [ ] **Step 7: Final commit if needed**

```bash
git commit -m "chore(quality): final verification — all tests pass, pyright clean"
```

---

## Deferred Items (Intentionally Cut)

These tasks exist in the S-DATA spec and design doc but are explicitly deferred from this plan because they are below the 70% cut line. The successor should build them when time allows, in priority order.

| Task | Source | Why Cut | When to Build |
|------|--------|---------|---------------|
| **S-DATA Task 1.3** — D9 saliency validation | S-DATA spec Phase 1 | Templates work without saliency validation. CSS fixes are nice-to-have. | After core templates ship and are in production use |
| **S-DATA Task 2.4** — GEPA bootstrap pairs | S-DATA spec Phase 2 | GEPA dependency is installed but has ZERO integration code. Pairs would sit idle. | After GEPA integration is built (no session assigned yet) |
| **S-DATA Task 2.5** — OIP agreement report | S-DATA spec Phase 2 | Validation report only, no runtime impact. D16 download may be incomplete. | Before S19 benchmark session, as validation evidence for NIMA |
| **S-DATA Task 2.3** — Dimension weight calibration | S-DATA spec Phase 2 | Current equal 0.25 weights may be close enough. Code already reads from YAML. | After production data validates whether unequal weights improve scoring |
| **S-DATA Task 3.3** — CTA formula wiring | S-DATA spec Phase 3 | Incremental copy quality improvement. Config exists but impact unclear. | Listed as Task 16 in Chunk 5 (CUT if time-compressed) |

---

## Notes for Successor

### Build Order Rationale

This plan reorders the design spec's recommended phases (Phase 2 → 1 → 3 → 4) into a more natural implementation flow:

- **Chunk 1** (Foundation) is prerequisite for everything
- **Chunk 2** (Calibration + Wiring) groups NIMA work together — calibrate and wire in one pass
- **Chunk 3** (Templates) depends on D4 schema validation from Chunk 1
- **Chunk 4** (Coaching) depends on template industry_fit from Chunk 3 for full-chain tests

The design spec groups by data phase; this plan groups by implementation dependency.

### Template Metadata Naming Convention

**Use the existing pattern:** `{template_name}_meta.yaml` (e.g., `poster_d4_hero_left_meta.yaml`). This matches the 10 existing templates on disk:
```
poster_default_meta.yaml
poster_road_safety_meta.yaml
poster_bold_knockout_meta.yaml
...
```

### Operator Exemplar Fallback

If operator exemplars are NOT yet available when you reach Task 6 (NIMA calibration):
- Calibrate using D12 reference scores ONLY
- Set `calibration_source: "D12 PosterIQ only — operator exemplars pending"`
- Mark `pass_above` threshold as provisional
- Re-run calibration when operator exemplars arrive

### Dependency Verification

Before starting implementation, verify these packages are installed:
```bash
pip3 list | grep -iE "pandas|pyarrow|scikit-learn|pillow|torch|PyMuPDF"
```
If any are missing: `pip3 install --break-system-packages <package>`. Check `pyproject.toml` first — the package may already be listed as a dependency.

### Template Registration

The plan references `config/poster_templates.yaml` for registering new templates. **This file may not exist.** Check how the existing template selector discovers templates — it may scan the `templates/html/` directory directly or use a different registry mechanism. Adapt Task 8 accordingly.
