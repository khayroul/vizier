# Successor Handover: Sprint Review Findings

**Generated:** 2026-04-09
**Handover number:** 015
**Reason:** Successor handover after reviewing the 7-commit hardening sprint on `main`
**Reviewed HEAD:** `68b0897`
**Context:** Sprint summary provided by user:

- `acf71f7` — import repair
- `b1f2773` — config-driven deliverability
- `f9a829a` — policy audit trail
- `980f7cd` — silent artifact-family fallback removal
- `91b2378` — canon reconciliation
- `56f6e3f` — governed-path integration test
- `68b0897` — hardening / pyright clean

---

## Executive Summary

The sprint materially improved the repo, but the review found **4 issues**:

1. `rework` is blocked by the new deliverability gate in the real orchestrator
2. `family_resolved` was introduced but not enforced by readiness
3. deliverability is **not actually YAML-only** yet because `_deliver()` still has Python-side routing constraints
4. the new "full governed path" test does not run through `run_governed()`, so it misses orchestrator-only regressions

During this session, I also found that the working tree is **not clean anymore**. There are local, uncommitted edits that appear to be in-progress fixes for Findings 1 and 2.

---

## Review Findings

### Finding 1 — `rework` blocked by deliverability gate

File:

- `tools/orchestrate.py`

Problem:

- `run_governed()` now denies any workflow with a delivery stage unless the workflow name is in the deliverable set
- `rework` still has a delivery stage
- `rework` is active in `core`
- `rework` is marked `deliverable: false`
- comment claims it should inherit deliverability from the original workflow

Observed behavior:

- patched `run_governed()` repro raised `PolicyDenied` for `rework`

Impact:

- every real `rework` request can now fail before the executor runs

Priority:

- `P1`

### Finding 2 — `family_resolved` not enforced

File:

- `contracts/readiness.py`

Problem:

- Day 4 introduced `family_resolved` to distinguish classified family vs defaulted fallback
- `evaluate_readiness()` did not initially consult it
- a provisional spec with `family_resolved=False` could still become `ready`

Impact:

- the old silent "default document" path was still structurally reachable

Priority:

- `P2`

### Finding 3 — deliverability is not YAML-only yet

File:

- `tools/registry.py`

Problem:

- orchestrator comments imply a workflow becomes deliverable by config
- `_deliver()` still only routes `document` family workflows to `_deliver_document()`
- `invoice`, `proposal`, and `company_profile` have their own artifact families
- flipping `deliverable: true` would still stub unless Python routing is extended

Impact:

- config and runtime truth still diverge

Priority:

- `P2`

### Finding 4 — "full governed path" test skips orchestrator

File:

- `tests/test_governed_path.py`

Problem:

- test manually composes `route() -> readiness -> policy -> executor`
- it does **not** invoke `run_governed()`
- so it does not cover:
  - delivery-support gate
  - runtime-readiness gate
  - job-row creation / status updates
  - real pre-flight tool gate behavior

Impact:

- orchestrator-only regressions can slip through while this test still reads as end-to-end coverage

Priority:

- `P3`

---

## Current Working Tree State

`git status --short` during this handover:

```text
 M config/workflow_registry.yaml
 M contracts/readiness.py
 M tests/test_contracts.py
 M tests/test_e2e_layer2_primitives.py
 M tools/orchestrate.py
 M utils/workflow_registry.py
?? docs/HANDOVER_SPRINT_GPT.md
?? docs/handover/HANDOVER_014_TRACK1_TRACK2_STOP_POINT.md
```

### What the local edits appear to be doing

The uncommitted changes look like an in-progress response to Findings 1 and 2:

- `config/workflow_registry.yaml`
  - adds `inherits_delivery: true` to `rework`
- `utils/workflow_registry.py`
  - adds `inherits_delivery(name)`
  - updates docstring to say deliverability is **not** YAML-only
- `tools/orchestrate.py`
  - sets `family_resolved=True` when creating the spec from routed workflow family
  - skips the deliverability gate for workflows with `inherits_delivery: true`
- `contracts/readiness.py`
  - adds `artifact_family_unresolved` to missing critical fields when `family_resolved=False`
- tests updated in:
  - `tests/test_contracts.py`
  - `tests/test_e2e_layer2_primitives.py`

### What is **not** fixed by the local edits yet

I did **not** see local changes to:

- `tools/registry.py`
  - so Finding 3 still appears open
- `tests/test_governed_path.py`
  - so Finding 4 still appears open

I also did **not** run tests against these uncommitted edits.

---

## Verified Repro Notes

### Rework regression repro

I reproduced the `rework` block by patching:

- `route`
- `evaluate_readiness`
- `PolicyEvaluator`
- `_check_runtime_readiness`
- `WorkflowExecutor`

and then calling `run_governed(...)` with workflow `rework`.

Observed result:

```text
PolicyDenied
Workflow 'rework' has a delivery stage but delivery is not yet implemented for this workflow type.
```

### `family_resolved` readiness gap repro

I constructed a `ProvisionalArtifactSpec` with:

- `artifact_family=document`
- `family_resolved=False`
- objective/format/tone/copy_register/dimensions/page_count/brand_config filled

Observed result before local edits:

```text
status='ready'
```

That confirms the fallback marker was not being enforced.

### Deliverability is not config-only repro

Direct `_deliver(...)` calls showed:

- `invoice` -> `delivery_not_implemented`
- `proposal` -> `delivery_not_implemented`
- `company_profile` -> `delivery_not_implemented`
- `document_production` routes to document delivery path

So the config layer is ahead of the delivery router.

---

## True State At Hand-Off

### Likely fixed locally but not yet verified

- `rework` deliverability inheritance
- readiness enforcement for unresolved artifact family

### Still open unless additional edits land

- delivery routing is not truly config-driven
- governed-path test still skips the orchestrator
- `pyrightconfig.json` still excludes `augments`, so Day 1 import repairs are not actually inside the pyright-checked surface

---

## Next Safe Sequence For Successor

### 1. Verify the in-progress local fixes first

Before making more changes:

- inspect current diffs in:
  - `config/workflow_registry.yaml`
  - `utils/workflow_registry.py`
  - `tools/orchestrate.py`
  - `contracts/readiness.py`
- run targeted tests for the two intended fixes

Recommended checks:

```bash
python3 -m pytest -q tests/test_contracts.py -k readiness
python3 -m pytest -q tests/test_e2e_layer2_primitives.py -k readiness
python3 -m pytest -q tests/test_orchestrate.py -k rework
```

If no `rework` orchestrator test exists yet, add one before trusting the fix.

### 2. Close Finding 3 honestly

Pick one of these paths:

Option A: make docs/comments honest

- keep current delivery router behavior
- explicitly document that new deliverable workflows still require Python routing in `_deliver()`

Option B: actually make delivery routing align with config

- extend `_deliver()` so the relevant non-`document` families (`invoice`, `proposal`, `company_profile`) can route to `_deliver_document()` when they are intentionally enabled

Given the current repo state, Option A is the safer near-term fix unless S16 is being activated now.

### 3. Close Finding 4 with a real orchestrator test

Add at least one `run_governed()`-level test that exercises:

- delivery-support gate
- runtime-readiness gate
- successful poster or document flow

At minimum:

- one positive orchestrator test
- one negative `rework` regression test

### 4. Re-run the review after fixes

After the above:

- rerun the targeted tests
- if clean, rerun full suite if time allows
- update handover or commit summary with:
  - which findings are fixed
  - which remain intentionally deferred

---

## Successor Goal

The next session should aim to turn this state into:

- Findings 1 and 2 verified fixed
- Finding 3 either fixed or explicitly narrowed in docs/comments
- Finding 4 covered by a true orchestrator test

That would convert this review from "found regressions" into "closed review loop."
