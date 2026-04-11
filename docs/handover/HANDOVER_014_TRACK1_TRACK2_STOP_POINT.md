# Track 1 + Track 2 Stop Point Handover

**Generated:** 2026-04-09
**Handover number:** 014
**Reason:** Clean stop point after Track 1 poster hardening, Track 2 document-lane implementation, and Codex review of the resulting support matrix
**Current inspected HEAD:** `ff4a9bd`
**Prior context:** `HANDOVER_013_CODEX_ROUND3_COMPLETE.md`, Track 1 poster hardening commits (`dcbd1b8`, `35b317d`), and Track 2 document-lane commit (`35996a3`)

---

## Executive Summary

Two important lanes are now materially better:

- `poster_production` is hardened across Playwright and Typst fallback, with post-render QA and one deterministic readability-revision path
- `document_production` now has a real Typst render path and a real document delivery path

However, the review in this session found that the **support matrix is still slightly overstated**.

### What is genuinely real now

- `poster_production`
- `document_production`

### What is **not** yet genuinely shipped in the governed runtime

- `invoice`
- `proposal`
- `company_profile`

These were added to the deliverable whitelist, but they still depend on S16 phase/state and, in some cases, placeholder generators.

---

## What Shipped Before This Review

### Track 1: Poster Lane Fully Hardened

| Step | Commit | What shipped |
|---|---|---|
| T1.1 | `dcbd1b8` | Typst fallback parity via PDF rasterization + same post-render QA gate |
| T1.2 | `dcbd1b8` | Semantic parity tests for Playwright and Typst poster delivery |
| T1.3 | `dcbd1b8` | Runtime readiness hard-blocks: `OPENAI_API_KEY` and `FAL_KEY` always block, `DATABASE_URL` blocks only in strict posture |
| T1.4 | `35b317d` | One-shot deterministic readability revision for post-render text-overlay failures |

### Track 2: Document Lane E2E

| Step | Commit | What shipped |
|---|---|---|
| T2.1 | `35996a3` | Real `_typst_render()` with template mode, source mode, and plain-text auto-wrap |
| T2.2 | `35996a3` | `_deliver_document()` with upstream PDF discovery and last-resort render |
| T2.3 | `35996a3` | Added document-family workflows to `_DELIVERABLE_WORKFLOWS` |
| T2.4 | `35996a3` | Structural QA on delivered PDFs |
| T2.5 | `35996a3` | New semantic/document delivery tests |

User-reported suite status at stop point:

```text
850 passed, 45 skipped, 0 failed
```

I did **not** rerun the full suite in this review session.

---

## What Was Re-Verified In This Session

### 1. Hermes bridge P1 fix is real

The earlier `task_id` vs `session_id` bug is fixed in the current tree:

- `_pre_tool_call()` now resolves via direct hit -> `_TASK_TO_SESSION` -> `_ACTIVE_SESSION_ID`
- `_hermes_session_id` is injected into `run_pipeline` args
- `run_pipeline()` uses exact session lookup for `media_manifest`
- session-end cleanup removes stale task-to-session mappings

Targeted verification run:

```text
tests/test_vizier_tools_bridge.py::test_pre_tool_call_resolves_session_when_task_id_differs
tests/test_vizier_tools_bridge.py::test_session_end_cleans_task_to_session_mapping
```

Both passed.

### 2. Document lane core path is real

I reviewed:

- `tools/registry.py` `_typst_render()`
- `tools/registry.py` `_deliver_document()`
- `tools/publish.py` `assemble_document_pdf()`

I also did a real local compile check with `assemble_document_pdf(template_name="report", ...)`, which produced a non-trivial PDF (`96121` bytes). So the new render path is not test-only.

Targeted verification run:

```text
tests/test_e2e_layer5b_semantics.py -k 'DocumentProductionRealDelivery or deliver_document or typst_render'
```

Result:

```text
6 passed, 29 deselected
```

---

## Findings From This Review

### Finding A — `typst_render` is still marked as a stub

`_typst_render()` is now implemented, but `_STUB_TOOL_NAMES` still includes `typst_render`.

File:

- `tools/registry.py`

Why this matters:

- any `requires_session` workflow that depends on `typst_render` can still trip the executor's stub gate when its phase is activated
- this especially affects future S16 document-family workflows

Recommended fix:

- remove `typst_render` from `_STUB_TOOL_NAMES`
- add a regression test that `_check_stub_workflow()` no longer blocks a workflow solely because it uses `typst_render`

### Finding B — deliverable whitelist currently overstates real support

`_DELIVERABLE_WORKFLOWS` now includes:

- `document_production`
- `invoice`
- `proposal`
- `company_profile`

But only `document_production` is actually aligned with the current runtime.

#### Why the others are not truly shipped yet

`invoice`

- still `requires_session: S16`
- still phase-blocked upstream

`proposal`

- still `requires_session: S16`
- still uses placeholder `generate_proposal`

`company_profile`

- still `requires_session: S16`
- still uses placeholder `generate_profile`

Net effect:

- the support matrix now says more than the governed runtime can reliably deliver

Recommended fix:

- narrow `_DELIVERABLE_WORKFLOWS` back to:
  - `poster_production`
  - `document_production`

Only re-add S16 workflows after:

- phase gate is intentionally enabled
- generator tools are real
- semantic delivery tests exist for each one

---

## Current Support Matrix At Stop Point

### Actually supported

- `poster_production`
- `document_production`

### Partially improved but not production-ready

- `invoice`
- `proposal`
- `company_profile`

### Still stub / deferred

- `ebook_production`
- `childrens_book_production`
- `serial_fiction_production`
- `social_batch`
- `content_calendar`

---

## Important Code State

### Real now

- `tools/registry.py::_typst_render`
- `tools/registry.py::_deliver_document`
- `tools/registry.py::_deliver` routing to document delivery
- `tools/orchestrate.py::_check_runtime_readiness` hard-block model/image requirements
- poster Typst fallback parity and post-render QA

### Still intentionally incomplete

- `tools/registry.py::_generate_proposal`
- `tools/registry.py::_generate_profile`
- `tools/registry.py::_generate_invoice` is not wired as a true governed generation stage result
- S15 workshop/scaffold tools
- S21 / S22 / S24 extended workflow generators

---

## Next Safe Implementation Sequence

### 1. Align the support matrix first

Do this before any new lane work.

Recommended changes:

1. Remove `typst_render` from `_STUB_TOOL_NAMES`
2. Narrow `_DELIVERABLE_WORKFLOWS` to the workflows that are genuinely real now:
   - `poster_production`
   - `document_production`
3. Add a regression test that keeps deliverable whitelist, phase gate, and stub gate aligned

This is the cleanest next session because it is:

- small
- low risk
- directly tied to the findings
- prevents future confusion about what is actually shipped

### 2. Only then decide between two follow-ups

#### Option A — deepen `document_production`

Improve quality instead of breadth:

- document-specific semantic QA beyond file existence/size
- PDF text extraction checks
- section completeness checks
- template-specific tests for `report.typ`

#### Option B — ship one S16 workflow for real

Pick **one**:

- `invoice`, or
- `proposal`, or
- `company_profile`

Then do the full lane honestly:

- real generator
- real phase activation
- semantic delivery tests
- only then re-add it to deliverable support

Do **not** re-open all S16 workflows at once.

---

## Constraints For The Next Session

1. Do not describe `invoice`, `proposal`, or `company_profile` as production-ready yet.
2. Do not begin a broad QA-contract refactor before the support matrix is truthful.
3. Keep `document_production` as the only newly claimed deliverable lane unless S16 generators are actually implemented.
4. Preserve the current poster lane behavior; do not weaken post-render QA parity between Playwright and Typst.

---

## Repo State At Handover

### Changes made in **this** review session

- new handover note added:
  - `docs/handover/HANDOVER_014_TRACK1_TRACK2_STOP_POINT.md`
- no runtime code changes
- temporary local PDF-check directory created during review was removed

### Tests run in **this** review session

- targeted bridge regression tests
- targeted document-lane semantic tests
- no full-suite rerun by me in this session

### Working tree note

There is a pre-existing untracked file outside this handover work:

- `docs/HANDOVER_SPRINT_GPT.md`

I left it untouched.

---

## Key Files For The Next Session

- `tools/registry.py`
- `tools/orchestrate.py`
- `tools/executor.py`
- `tools/publish.py`
- `tests/test_e2e_layer5b_semantics.py`
- `tests/test_orchestrate.py`
- `tests/test_e2e_layer3_middleware.py`
- `plugins/vizier_tools_bridge.py`
- `docs/handover/HANDOVER_014_TRACK1_TRACK2_STOP_POINT.md`

---

## Bottom Line

The repo is in a better place than it was at the start of Track 1:

- poster lane is materially hardened
- document lane is now real
- Hermes bridge session correlation is fixed

But the **next** session should start with support-matrix truthfulness, not new breadth:

- un-stub `typst_render`
- narrow the deliverable whitelist to what is genuinely shipped

That is the smallest safe move that prevents the next round of false confidence.
