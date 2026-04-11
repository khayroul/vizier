# Successor Handover: Post-S21 Gap Analysis + Recovery State

**Generated:** 2026-04-11  
**Handover number:** 018  
**Reason:** Analysis session after the post-S21 hardening/debugging rounds. Captures what those sessions were about, which outcomes are genuinely good, what remains open, and what the successor should do next.  
**Reviewed HEAD:** `5343b41`  
**Branch:** `main`

---

## Executive Summary

This session was a **repo-reading, verification, and documentation** session. No production code was changed.

High-signal outcome:

1. the original S21 build plan did **not** reach its promised quality floor
2. the post-S21 debugging/hardening sessions were **not wasted**
3. but they were solving **different layers of the problem**
4. the later quality-intelligence commits on `main` are the strongest actual output-quality gains so far
5. the repo is materially better than the older handovers imply, but still not at a clean "sellable by proof" state

In short:

- early post-S21 sessions improved **reliability, deployment truth, and diagnosis**
- later post-S21 sessions improved **actual poster quality infrastructure**
- the remaining blockers are now narrow enough to attack directly

---

## What This Session Produced

Three new analysis documents were written:

- `docs/QUALITY_GAP_ANALYSIS_S21.md`
- `docs/VIZIER_BUILD_quality_first_v1.md`
- `docs/decisions/lessons_learned_build_plan_v1.md`

These documents answer:

- why S21 missed the architecture promise
- what should have been on the critical path earlier
- what a quality-first build plan should look like
- what anti-patterns to avoid in future build plans

This session also answered the operator's follow-up questions about:

- whether the datasets on disk are enough for the practical use case
- whether handpicked Canva/Envato references should define the taste floor
- whether the post-S21 debugging/hardening sessions were producing good outcomes

Answer summary:

- local datasets are sufficient for structure/benchmark work
- operator-curated Canva/Envato references should define **taste**, not be treated as a bulk training dump
- post-S21 sessions produced good outcomes, but mostly in two waves:
  - structural hardening first
  - quality recovery later

---

## Current Repo State

Recent commits on `main`:

- `43ea75e` - `docs(quality): design session — coaching system, S-DATA spec, anti-drift rules #58-60`
- `52f7dff` - `feat(data): Phase 0 verification tests + operator exemplar ingestion`
- `2c38a66` - `feat(quality): D12 data loader + config-driven NIMA thresholds`
- `4bd853a` - `feat(routing): template selector scores industry_fit dimension`
- `61da662` - `feat(coaching): structured coaching with content gates + bridge upgrade`
- `bc84dd5` - `fix(tests): update thin brief tests for JSON coaching format + D12 path fix`
- `8da7755` - `feat(coaching): industry-specific question patterns from D8 analysis`
- `ae35802` - `test(integration): cross-session quality intelligence tests (#60)`
- `c04e85e` - `feat(quality): NIMA calibration script — D12 reference + operator exemplars`
- `61e1927` - `feat(templates): D4 CGL clustering — 28 poster archetypes from 61K layouts`
- `5343b41` - `feat(templates): add industry_fit tags to existing templates + fix selector test`

This matters because it changes the older narrative:

- the repo is no longer just "datasets on disk but unwired"
- a meaningful post-S21 quality-intelligence tranche actually landed
- the remaining gaps are now mostly wiring, proof, and taste-layer integration gaps

---

## Working Tree State

Current untracked files in the workspace:

```text
?? .analysis/
?? .graphify_ast.json
?? .graphify_cached.json
?? .graphify_chunks.json
?? .graphify_detect.json
?? .graphify_uncached.txt
?? docs/HANDOVER_SPRINT_GPT.md
?? docs/QUALITY_GAP_ANALYSIS_S21.md
?? docs/VIZIER_BUILD_quality_first_v1.md
?? docs/decisions/lessons_learned_build_plan_v1.md
?? docs/decisions/promote_sysstate_test_2026-04-10.md
?? docs/decisions/promote_test_template_2026-04-10.md
?? docs/handover/HANDOVER_014_TRACK1_TRACK2_STOP_POINT.md
?? docs/handover/HANDOVER_015_SUCCESSOR_REVIEW_FINDINGS.md
?? docs/handover/HANDOVER_016_SUCCESSOR_QUALITY_FLOOR.md
```

Notes:

- no tracked code files were modified in this session
- `.analysis/` and `.graphify_*` came from the graphify-assisted analysis workflow
- the three new analysis docs listed above are also still untracked

---

## What Was Verified

### 1. The post-S21 sessions were checked, not assumed

I explicitly reviewed the key post-S21 hardening/debugging docs:

- `docs/handover/HANDOVER_012_HARDENING_REVIEW_AND_ROOT_CAUSE.md`
- `docs/handover/HANDOVER_013_CODEX_ROUND3_COMPLETE.md`
- `docs/handover/HANDOVER_014_TRACK1_TRACK2_STOP_POINT.md`
- `docs/HANDOVER_SPRINT_GPT_FINAL.md`

Verdict:

- these sessions produced **good outcomes**
- but not all of them improved the same thing

They split cleanly into:

- **structural hardening**
  - deployment boundary
  - plugin install determinism
  - `.vizier_root` stamping
  - session correlation
  - support-matrix truthfulness
  - better reliability tests
- **quality recovery**
  - coaching/content gates
  - D4-derived poster templates
  - `industry_fit` template scoring
  - D12/NIMA config wiring
  - cross-session quality tests

### 2. Current `main` is ahead of the earlier handovers

This is important for the successor:

- older handovers like 016 and 017 are still useful
- but they understate how much quality-focused work has already landed

The repo now has:

- structured coaching JSON via `CoachingResponse`
- semantic content gates in `tools/coaching.py`
- config-driven NIMA thresholds
- 28 D4-derived poster templates plus older templates
- `industry_fit` scoring in template selection
- operator exemplar ingestion script
- green cross-session quality-intelligence tests

### 3. Some key promises are still only partially true

The repo has improved, but several important gaps remain:

- `quality="high"` still maps to `quality_posture="production"` in the bridge, while runtime only accepts `canva_baseline`, `enhanced`, and `full`
- `refine_request()` exists but is still not on the live governed path
- operator exemplar manifests are not yet in the runtime exemplar retrieval path
- books / ebooks still lag the workflow-registry truth
- governed poster acceptance proof is still not clean

---

## Test Results Run In This Session

### Green targeted suites

```text
pytest tests/test_vizier_tools_bridge.py tests/test_routing.py tests/test_orchestrate.py tests/test_integration_quality.py tests/test_coaching.py tests/test_visual_intelligence.py -q
177 passed, 1 warning
```

```text
pytest tests/test_illustrate.py tests/test_ebook_production.py tests/test_serial_fiction.py tests/integration/test_it2_childrens_book.py -q
88 passed, 1 warning
```

```text
pytest tests/test_nima_config.py tests/test_operator_exemplars.py -q
12 passed
```

### Mixed poster acceptance proof

```text
pytest tests/test_d4_templates.py tests/test_template_industry.py tests/test_user_pov_poster_acceptance.py -q
```

Outcome:

- D4 template tests passed
- template-industry tests passed
- `tests/test_user_pov_poster_acceptance.py` had `4` failures

Interpretation:

- this does **not** prove the poster lane is poor
- it **does** prove the governed launch-proof layer is currently stale / unreliable

Immediate failure themes:

- delivery-stage post-render QA harness drift
- mocked vision QA signatures / JSON expectations not matching runtime
- missing `DATABASE_URL` in this environment
- missing or partial Langfuse configuration

---

## What The Post-S21 Sessions Were About

### Wave 1: Hardening and truth correction

Main references:

- `HANDOVER_012_HARDENING_REVIEW_AND_ROOT_CAUSE.md`
- `HANDOVER_013_CODEX_ROUND3_COMPLETE.md`
- `HANDOVER_014_TRACK1_TRACK2_STOP_POINT.md`

These sessions were mainly about:

- proving the deployment/install boundary
- making local-vs-repo assumptions explicit
- separating repo maturity from output quality
- correcting overclaims in the support matrix
- getting a more truthful view of what the system actually delivered

Outcome judgment:

- strong reliability value
- strong truthfulness value
- limited direct impact on sellable artifact quality

### Wave 2: Quality-intelligence recovery

Main references:

- `43ea75e` through `5343b41`
- `docs/decisions/dataset_transformation_gap.md`
- `docs/decisions/unified_quality_design.md`
- `docs/superpowers/plans/2026-04-11-quality-intelligence.md`

These sessions were mainly about:

- bridging the gap between raw datasets and runtime value
- improving thin-brief handling
- making template choice more intelligent
- bringing D4 / D5 / D8 / D12 outputs into actual code paths

Outcome judgment:

- this is the strongest real quality movement in the repo so far
- it confirms that the original S21 plan had front-loaded the wrong work

---

## Open Gaps That Still Need Closing

### 1. `quality="high"` posture alias bug

Current state:

- bridge maps `quality="high"` -> `quality_posture="production"`
- runtime posture validator does not accept `production`

Why it matters:

- this leaves the high-quality lane only half wired

Files:

- `plugins/vizier_tools_bridge.py`
- `middleware/quality_posture.py`

### 2. Clarification path still not fully live

Current state:

- bridge coaching exists
- content gates exist
- `refine_request()` exists
- production path still does not use `refine_request()`

Why it matters:

- current brief rescue is useful, but still more templated than adaptive

Files:

- `contracts/routing.py`
- `plugins/vizier_tools_bridge.py`
- `tools/orchestrate.py`

### 3. Taste layer is not yet runtime-wired

Current state:

- operator exemplar ingestion script exists
- operator-curated Canva/Envato references are the right taste source
- runtime retrieval still relies on DB-backed exemplars filtered by `client_id`

Why it matters:

- the system can now learn more structure than before
- but it still cannot fully claim a Malaysia-friendly, English-first commercial taste floor

Files:

- `scripts/ingest_operator_exemplars.py`
- `utils/retrieval.py`
- `middleware/quality_posture.py`

### 4. NIMA config is wired, but not yet truthfully calibrated

Current state:

- `tools/visual_scoring.py` reads from config
- calibration script exists
- YAML still declares defaults / uncalibrated source

Why it matters:

- config wiring is not the same thing as verified calibration

Files:

- `tools/visual_scoring.py`
- `config/quality_frameworks/nima_thresholds.yaml`
- `scripts/calibrate_nima_thresholds.py`

### 5. Books / ebooks still need delivery-truth alignment

Current state:

- publishing tests are strong
- workflow-registry truth still marks key publishing lanes non-deliverable

Why it matters:

- product ambition and governed truth are still misaligned

Files:

- `config/workflow_registry.yaml`

### 6. Launch-proof suite is still not trustworthy

Current state:

- poster governed acceptance suite is red

Why it matters:

- the repo still lacks one clean proof artifact saying "sellable output is re-proven"

Files:

- `tests/test_user_pov_poster_acceptance.py`

---

## Dataset Reality — Final Position

The earlier "100k+ posters on disk" question changed during investigation.

What is now safe to say:

- there is enough useful dataset material locally for near-term structure, benchmarking, and evaluation work
- the specific huge poster corpus is still only partially present
- the practical bottleneck is no longer "not enough data on disk"
- the practical bottleneck is "taste-layer and runtime integration"

Strategic conclusion already discussed with operator:

- academic/public datasets should teach **structure**
- operator-curated Canva/Envato references should define **taste**
- those references should be grouped primarily by:
  - `artifact_type`
  - `layout_archetype`
  - `use_case` / `niche`
- `source` should be preserved as provenance metadata, not the main runtime grouping key

---

## Successor Reading Order

Read these first:

1. `docs/QUALITY_GAP_ANALYSIS_S21.md`
2. `docs/VIZIER_BUILD_quality_first_v1.md`
3. `docs/decisions/lessons_learned_build_plan_v1.md`

Then re-read the most relevant prior handovers:

4. `docs/handover/HANDOVER_016_SUCCESSOR_QUALITY_FLOOR.md`
5. `docs/handover/HANDOVER_017_QUALITY_INTELLIGENCE_DESIGN.md`
6. `docs/handover/HANDOVER_012_HARDENING_REVIEW_AND_ROOT_CAUSE.md`
7. `docs/handover/HANDOVER_013_CODEX_ROUND3_COMPLETE.md`
8. `docs/handover/HANDOVER_014_TRACK1_TRACK2_STOP_POINT.md`

Then inspect runtime truth in code:

9. `plugins/vizier_tools_bridge.py`
10. `middleware/quality_posture.py`
11. `contracts/routing.py`
12. `tools/visual_scoring.py`
13. `tools/template_selector.py`
14. `utils/retrieval.py`
15. `config/workflow_registry.yaml`

---

## Safest Next-Session Sequence

1. Fix or normalize the `quality="high"` -> `quality_posture="production"` alias mismatch.
2. Repair the governed poster acceptance harness until `tests/test_user_pov_poster_acceptance.py` is trustworthy again.
3. Decide whether `refine_request()` should be wired into bridge coaching now, or whether the product promise should be narrowed temporarily.
4. Move operator exemplar manifests into the real exemplar / benchmark path used at runtime.
5. Run actual NIMA calibration and update `nima_thresholds.yaml` with verified values and provenance.
6. Reconcile publishing truth in `config/workflow_registry.yaml` with the current book / ebook runtime reality.

This order is safest because:

- it restores truth and proof first
- then finishes the taste layer
- then promotes publishing lanes from "promising" to "truthfully launchable"

---

## Bottom Line For The Successor

The repo is in a better state than the older handovers suggest.

The post-S21 sessions did produce good outcomes, but in sequence:

- first they made the system more honest and reliable
- then they started repairing the real quality path

The remaining work is no longer a vague "improve quality" problem. It is a short, concrete closure list:

- one bridge alias bug
- one stale governed acceptance harness
- one unwired adaptive clarification path
- one unwired taste-layer retrieval path
- one calibration promotion step
- one publishing truth reconciliation step

If those are closed cleanly, the repo should be much closer to a credible sellable-output claim than any earlier S21-era stop-point.
