# Successor Handover: Quality Floor + Dataset Reality Check

**Generated:** 2026-04-10
**Handover number:** 016
**Reason:** Stop-point handover after validating recent quality-floor work, model/cost tracking expectations, and the claimed poster dataset presence on the machine
**Reviewed HEAD:** `1c595b3`

---

## Executive Summary

This session did **not** make code changes. It was a verification / repo-reading session.

Two things changed during the investigation:

1. `main` moved forward beyond the previously reviewed `ee2484d`
2. several of the quality-floor checklist themes now appear to have landed on `main`

High-signal outcome:

- the repo is closer to the desired direction than it was earlier today
- but the quality-floor story is still only **partially complete**
- and the claimed `100k+` poster dataset is **not yet verified**

The next session should start by validating the new quality commits end-to-end, then checking the actual storage layers (Postgres / MinIO / external archive) instead of assuming the corpus exists locally.

---

## Current Repo State

Recent commits on `main`:

- `ee2484d` - `fix(bridge): emit full UUID job IDs + Codex review fixes`
- `97ea75c` - `feat(quality): raise poster floor - flux-pro default + high quality lane`
- `48d2605` - `feat(intelligence): industry inference + per-model cost tracking`
- `1c595b3` - `feat(quality): auto-enrich shapeable specs + thin-brief coaching`

Current working tree state:

```text
? docs/HANDOVER_SPRINT_GPT.md
? docs/decisions/promote_sysstate_test_2026-04-10.md
? docs/decisions/promote_test_template_2026-04-10.md
? docs/handover/HANDOVER_014_TRACK1_TRACK2_STOP_POINT.md
? docs/handover/HANDOVER_015_SUCCESSOR_REVIEW_FINDINGS.md
```

Important:

- no tracked code files were modified in this session
- only untracked docs are present in the worktree

---

## What Was Verified

### 1. Earlier bridge / review fixes are real

I previously re-checked commit `ee2484d` and found no findings.

Verified at that point:

- `_generate_job_id()` changed to full UUID in `plugins/vizier_tools_bridge.py`
- `family_resolved` is enforced
- `rework` skips the delivery gate via `inherits_delivery`
- generated-image directory leakage into production data was isolated for tests

Targeted suite I ran then:

```text
173 passed, 1 skipped
```

Tests included:

- `tests/test_vizier_tools_bridge.py`
- `tests/test_governed_path.py`
- `tests/test_contracts.py`
- `tests/test_e2e_layer2_primitives.py`
- `tests/test_routing.py`
- `tests/test_poster_reference_runtime.py`
- `tests/test_e2e_layer5b_semantics.py`

I did **not** rerun tests after the three newer commits landed on `main`.

### 2. Desired quality-floor themes now appear on `main`

I verified the following live code state:

- thin-brief coaching now exists in `plugins/vizier_tools_bridge.py`
  - `_run_pipeline_handler()` calls `_maybe_coach_thin_brief(...)`
  - very thin briefs are intercepted before pipeline execution
- shapeable governed specs now auto-enrich in `tools/orchestrate.py`
  - `_auto_enrich_spec(...)` runs when readiness is `shapeable`
  - if still `shapeable`, execution still continues
- industry inference was added to brief interpretation in `tools/brief_interpreter.py`
  - `industry` is now part of interpreted intent
- clientless design-system inference was added in `tools/orchestrate.py`
  - when no design system is set, inferred `industry` / `mood` are passed to `select_design_systems(...)`
- the poster no-text image-routing fix is present in `tools/registry.py`
  - poster/brochure image generation now forces `has_text=False`
  - this preserves the stronger poster image lane instead of BM text routing

### 3. One quality-lane bug is still present

The bridge guidance says to pass `quality="high"` and the schema still exposes that field.

Current mapping in `plugins/vizier_tools_bridge.py`:

- `quality="high"` -> `quality_posture="production"`
- `quality="high"` -> `budget_profile="critical"`

But `middleware/quality_posture.py` only accepts:

- `canva_baseline`
- `enhanced`
- `full`

So:

- `budget_profile="critical"` is real
- the posture alias is still wrong unless some later code normalizes it elsewhere
- this likely means the "high quality lane" is only half wired

This should be the first code-level sanity check next session.

### 4. Per-job cost tracking improved directionally, but I did not fully re-audit it

What is definitely true:

- spans still record `model`, `input_tokens`, `output_tokens`, `cost_usd`
- production traces still aggregate stage totals

What I did **not** confirm after `48d2605`:

- whether per-tool / per-stage trace payloads now include model names everywhere needed
- whether image generation spend is exact by actual fal endpoint or still approximate in some paths

Before `48d2605`, `_tool_metrics` in `tools/executor.py` did **not** include model names. I did not fully re-check whether that changed in later commits.

---

## Expectation Mapping

User expectation vs repo reality at stop-point:

### Expectation 1

`Minimum should be Canva Pro template quality`

Status:

- still not a hard guarantee
- the repo has moved in that direction
- but "canva_baseline" is still a posture/config concept, not a hard visual floor contract

### Expectation 2

`User may or may not give enough information`

Status:

- now better supported than before
- thin-brief coaching exists in the bridge
- shapeable spec auto-enrichment exists in the orchestrator
- but the system still does not hard-stop all low-information jobs

### Expectation 3

`System should help the user create the best prompt`

Status:

- partially implemented
- bridge-side coaching now exists
- brief interpretation and refinement primitives exist
- not yet fully audited as an end-to-end user-facing clarification loop

### Expectation 4

`Use best model possible and track cost per job by model used`

Status:

- image lane improved
- cost tracking direction improved
- text model lock policy still exists across the repo
- model-level per-job reporting needs re-audit on current `main`

### Expectation 5

`No-client requests should map to best benchmark / niche`

Status:

- this moved from "mostly absent" to "partially present"
- inferred industry/mood can now influence design-system selection
- not yet verified end-to-end against real no-client poster jobs

---

## Dataset Reality Check

The user stated that S0 was about downloading datasets onto the machine.

What the docs actually say:

- S0 is repo scaffold + asset port, not the session that successfully completed dataset pre-download
- multiple handovers explicitly say the planned pre-download did **not** happen
- S5 downloaded datasets as it went

Relevant docs:

- `CLAUDE.md`
- `CONTROL_TOWER.md`
- `docs/handover/HANDOVER_001.md`
- `docs/handover/HANDOVER_002.md`

### What I verified locally

Inside this repo:

- `datasets/` is effectively empty
- `datasets/gepa_bootstrap/` contains only `.gitkeep`
- `evaluations/benchmark/poster_briefs.yaml` contains 10 briefs
- `evaluations/reference_corpus/poster_ui_suite.yaml` is small

On the machine:

- Hugging Face cache entries exist for:
  - `datasets--PosterCraft--Poster100K`
  - `datasets--ArtmeScienceLab--PosterIQ`
  - `datasets--creative-graphic-design--CGL-Dataset-v2`
- but these are only tiny metadata/script cache entries, not verified full local corpora
  - `Poster100K` cache dir was only `8.0K`
  - `PosterIQ` cache dir was only `8.0K`
- MinIO has swipe assets under:
  - `/Users/Executor/minio-data/vizier-assets/swipes`
  - size around `1.0M`
  - this looks like dozens of images, not a giant corpus

I also found:

- `/Users/Executor/vizier-pro-max/output/posters` (~55M)
- `/Users/Executor/vizier-outputs/dmb/posters`
- `/Users/Executor/Downloads/vizier-artifacts/posters`

These look like generated outputs, not proof of a `100k+` source poster dataset.

### Honest conclusion

I cannot verify that we currently have a downloaded `100k+` poster dataset on this machine.

Best interpretation:

- the ecosystem references poster datasets
- some dataset IDs / HF cache entries exist
- but the actual large corpus is not yet proven locally

---

## Safest Next Sequence

### 1. Validate the new quality-floor commits, not just read them

Start by testing current `main` around:

- `quality="high"` bridge path
- thin-brief coaching
- shapeable spec auto-enrichment
- no-client industry inference
- poster image model routing

Recommended test focus:

- `tests/test_orchestrate.py`
- `tests/test_visual_intelligence.py`
- `tests/test_vizier_tools_bridge.py`
- `tests/integration/test_it1_poster.py`

### 2. Fix the broken posture alias if still real

Check whether `quality_posture="production"` is normalized anywhere.

If not:

- change bridge mapping to `quality_posture="full"`
- or add a safe alias from `production` -> `full`

### 3. Verify model-level cost tracking on current `main`

Confirm whether traces now answer:

- which model handled routing
- which model handled brief interpretation
- which model generated copy
- which model/endpoint generated the image
- which model handled QA / critique / rendered-poster checks

If not, extend production trace / `_tool_metrics` accordingly.

### 4. Verify no-client niche inference with a live or mocked run

Use a no-client poster brief like:

- Hari Kanak-Kanak
- retail sale
- school event
- community program

Confirm:

- inferred `industry` exists in interpreted intent
- inferred design system is populated in job context
- the output does not collapse back to generic corporate defaults

### 5. Check the real storage layers before assuming the corpus exists

The next factual check should be:

1. Postgres row counts for:
   - `datasets`
   - `dataset_items`
   - `exemplars`
   - `knowledge_cards`
   - `outcome_memory`
2. MinIO object counts for:
   - swipe assets
   - reference assets
   - any poster corpus buckets/prefixes
3. any external archive or legacy workspace path that actually holds the poster corpus

Only after that should anyone claim we "have 100k+ posters on the machine".

---

## Session Notes

- No files were edited in this session before this handover.
- No tests were run after `97ea75c`, `48d2605`, and `1c595b3` landed.
- This handover is meant to prevent the next session from redoing the repo-reading and filesystem scan.
