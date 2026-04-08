# Vizier Quality Spine Remediation Report

Date: 2026-04-08
Updated: 2026-04-09
Repo: `/Users/Executor/vizier`
Status: Implemented and verified

## Purpose

This report captures the quality/runtime audit, the graph-derived root cause,
the remediation plan, and the before/after state of the implementation.

The goal is not to patch isolated defects. The goal is to collapse Vizier onto
one enforced execution-quality-learning spine so that:

- generation, QA, tripwire, guardrails, and delivery operate on the same
  artifact state
- success means "artifact passed quality bar", not just "stages ran"
- token usage is controllable by job criticality and measurable against quality
- feedback and improvement consume the same runtime truth that delivery used

## Baseline Summary

### What was already working

- Routing selects a workflow and design system in
  [`contracts/routing.py`](/Users/Executor/vizier/contracts/routing.py).
- Brand context is injected into poster copy generation in
  [`tools/registry.py`](/Users/Executor/vizier/tools/registry.py).
- Design-system context reaches image brief expansion in
  [`tools/registry.py`](/Users/Executor/vizier/tools/registry.py).
- The generic executor is test-backed and already enforces terminal
  `error`/`stub` states in the current working tree.
- Per-step token and cost fields already exist in
  [`contracts/trace.py`](/Users/Executor/vizier/contracts/trace.py).
- Quality posture config already exists in
  [`config/phase.yaml`](/Users/Executor/vizier/config/phase.yaml).

### What was not working well enough

- The quality stack was fragmented across:
  - [`tools/executor.py`](/Users/Executor/vizier/tools/executor.py)
  - [`tools/registry.py`](/Users/Executor/vizier/tools/registry.py)
  - [`middleware/quality_gate.py`](/Users/Executor/vizier/middleware/quality_gate.py)
  - [`tools/visual_scoring.py`](/Users/Executor/vizier/tools/visual_scoring.py)
  - [`tools/visual_pipeline.py`](/Users/Executor/vizier/tools/visual_pipeline.py)
  - [`middleware/quality_posture.py`](/Users/Executor/vizier/middleware/quality_posture.py)
- The strongest visual-quality path existed as a side path instead of the
  default governed path.
- Success semantics were too shallow: the runtime primarily bound on `status`,
  not on "artifact met quality bar".
- Client/template/brand context was only partially propagated into execution.
- `knowledge:` in workflow YAML was still mostly dormant at runtime.
- The improvement loop expected richer trace/outcome fields than the runtime
  persisted.
- Token usage was recorded, but not yet governed by an explicit runtime budget
  profile and not yet granular enough for quality-vs-cost experiments.

## Graph-Derived Root Cause

The existing Graphify output in
[`graphify-out/GRAPH_REPORT.md`](/Users/Executor/vizier/graphify-out/GRAPH_REPORT.md)
showed a deeper architectural problem than a few isolated bugs:

1. Split quality architecture
2. Shallow success semantics
3. Parallel quality implementations
4. Config that informs but does not govern

The structural graph was useful for identifying missing edges and duplicate
paths, but runtime probes were still required to prove semantic bugs such as
"QA is scoring a status string instead of the rendered artifact."

## Baseline Findings

### Root-Cause Class A: Fragmented Quality Spine

- Visual QA in the active governed path did not evaluate the actual rendered
  artifact end to end.
- Tripwire, QA, and delivery did not all operate on one canonical artifact
  payload.
- Parallel guardrails and stronger visual scoring existed, but the stronger
  path was not the default governed path.

### Root-Cause Class B: Success Semantics Too Weak

- Delivery success could still be determined by stage flow rather than by a
  binding quality verdict.
- Low-quality outputs were too often represented as metadata instead of a
  terminal routing decision.

### Root-Cause Class C: Context Propagation Gaps

- Client-specific fields existed in config but did not consistently reach
  reminders, guardrails, template selection, and delivery.
- Design-system selection and template selection were not consistently joined.

### Root-Cause Class D: Dormant Learning Loop

- Knowledge retrieval logic existed but was not fully bound into stage
  execution.
- Outcome and exemplar logic existed but runtime persistence did not yet feed
  it richly enough.

### Root-Cause Class E: Token Governance Not Operationalized

- Token counts and costs were recorded.
- Quality posture existed.
- But there was no explicit budget profile such as `lean`, `standard`, or
  `critical`.
- There was no granular trace model for "which budget or retry path caused
  which quality outcome".

## Data Readiness Snapshot

The checkout itself shows real scarcity in checked-in client context:

- `config/clients`: 1 live client config
- `config/brand_patterns`: 1 file
- `config/copy_patterns`: 1 file
- `config/design_systems`: no checked-in implementation files in this checkout

This means part of the "on-brand quality" problem is code wiring, and part of
it is simply lack of seeded data.

## Remediation Strategy

The remediation is organized around one target architecture:

1. One canonical artifact payload
2. One shared quality verdict
3. One governed runtime path
4. One feedback/improvement feed
5. One token-governance model with measurable quality outcomes

## Execution Plan

### 1. Baseline report and evidence capture

- Capture the before-state findings and rationale.
- Preserve graph-derived root-cause analysis.
- Define success criteria before making runtime changes.

### 2. Canonical artifact payload and quality verdict

- Introduce a shared runtime artifact payload carried across stages.
- Make generation, QA, tripwire, guardrails, and delivery read/write the same
  payload.
- Introduce a shared quality verdict instead of scattered stage-local signals.

### 3. Collapse duplicate visual-quality paths

- Promote stronger visual scoring/guardrail logic into shared helpers.
- Make the governed visual path use those helpers.
- Reduce drift between the "strong side path" and the active runtime path.

### 4. Operationalize quality posture and budget profile

- Keep `quality_posture` as the strictness control.
- Add `budget_profile` as the spend/latency control.
- Track both per job and per stage/tool so quality-vs-cost experiments become
  possible.

### 5. Wire knowledge, feedback, and improvement

- Make stage `knowledge:` declarations operational.
- Persist `knowledge_cards_used`, revision counts, quality signals, and
  delivery metadata.
- Feed runtime outcomes into exemplar promotion and improvement analysis.

### 6. Verification and after-state reporting

- Run targeted and full-suite verification.
- Document the after-state architecture, gains, and remaining risks.

## Planned Runtime Controls

The intended runtime controls are:

- `quality_posture`
  - `canva_baseline`
  - `enhanced`
  - `full`
- `budget_profile`
  - `lean`
  - `standard`
  - `critical`

The distinction is intentional:

- `quality_posture` controls strictness and active techniques
- `budget_profile` controls token/context/retry spending

This avoids assuming that "more tokens" automatically means "better quality".

## Success Criteria

The remediation is considered successful when:

- QA evaluates the actual artifact being delivered
- tripwire revisions affect the artifact that delivery ships
- delivery depends on a binding quality verdict
- client/template/design-system context is consistent for branded jobs
- stage `knowledge:` becomes live runtime behavior
- token usage is measurable at a granularity that supports experiments
- outcome and trace data are rich enough for improvement analysis

## After-State Notes

## Implemented Changes

### 1. Runtime controls became operational

New runtime-control resolution was added in
[`middleware/runtime_controls.py`](/Users/Executor/vizier/middleware/runtime_controls.py)
and wired through [`tools/orchestrate.py`](/Users/Executor/vizier/tools/orchestrate.py).

Implemented behavior:

- `budget_profile` is now explicit (`lean`, `standard`, `critical`)
- `quality_posture` is now carried into execution context
- branded jobs now hydrate client-aware runtime context:
  - `client_name`
  - `brand_config`
  - `copy_register`
  - `template_name`
  - `platform`
- runtime controls are available in `job_context` for downstream generation,
  QA, tripwire, and delivery decisions

This turns runtime config from "informational" into an actual execution input.

### 2. Canonical artifact payload was introduced

[`tools/executor.py`](/Users/Executor/vizier/tools/executor.py) now carries a
canonical `artifact_payload` through the workflow.

Implemented behavior:

- stages initialize and merge into a shared artifact state
- generation, QA, tripwire, and delivery now read/write the same payload
- stage traces now persist richer proof and tool metrics
- stage-level token and cost metrics are aggregated instead of effectively
  "last tool wins"

This is the core structural change that collapses multiple weak local payloads
into one shared runtime truth.

### 3. Visual-quality paths were collapsed onto shared evaluation

The stronger visual path in
[`tools/visual_pipeline.py`](/Users/Executor/vizier/tools/visual_pipeline.py)
was promoted into a shared evaluator instead of remaining a side path.

Implemented behavior:

- `evaluate_visual_artifact(...)` now provides the common visual-quality
  primitive
- [`tools/registry.py`](/Users/Executor/vizier/tools/registry.py) visual QA now
  scores the actual rendered asset, not a status string
- [`tools/visual_scoring.py`](/Users/Executor/vizier/tools/visual_scoring.py)
  now returns token/cost metrics for exemplar-backed critique
- visual guardrails fail soft during QA evaluation instead of crashing the run
- exemplar lookup now degrades gracefully when the client identifier is not
  retrieval-compatible

This directly addresses the earlier split between the "strong side path" and
the weaker active governed path.

### 4. Delivery is now quality-bound and template-aware

[`tools/registry.py`](/Users/Executor/vizier/tools/registry.py) delivery logic
was updated to consume the canonical artifact payload and resolved runtime
context.

Implemented behavior:

- poster delivery now reads `image_path`, `poster_copy`, and quality state from
  the shared payload
- delivery blocks when `require_quality_pass` is enabled and the quality
  verdict is not satisfied
- template resolution now uses client/default context instead of hardcoding the
  previous render target
- delivery writes into job-specific output directories to avoid cross-run
  overwrites

This changes delivery from "best effort stage completion" to a governed
artifact handoff.

### 5. Tripwire now acts on the shipped artifact fields

Tripwire in [`tools/executor.py`](/Users/Executor/vizier/tools/executor.py)
and [`tools/registry.py`](/Users/Executor/vizier/tools/registry.py) was
reworked so critique and revision operate on the fields that delivery actually
uses.

Implemented behavior:

- scorer and reviser use artifact text from the canonical payload
- retries are governed by runtime controls
- exhaustion can fail closed when quality is required
- revised output is merged back into the payload instead of destroying artifact
  metadata

This closes the earlier gap where critique-then-revise could run without
meaningfully affecting the delivered poster.

### 6. Declarative stage knowledge is now live runtime behavior

[`tools/executor.py`](/Users/Executor/vizier/tools/executor.py) now resolves
stage `knowledge:` declarations into prompt context and trace output.

Implemented behavior:

- stage knowledge resolution is invoked during stage execution
- retrieved knowledge snippets are injected into prompts
- `knowledge_cards_used` is persisted into trace data
- runtime evidence now exposes that knowledge was actually used, not just
  declared in YAML

This converts an earlier dormant config seam into real runtime grounding.

### 7. Trace and improvement persistence were widened

[`contracts/trace.py`](/Users/Executor/vizier/contracts/trace.py) and
[`tools/executor.py`](/Users/Executor/vizier/tools/executor.py) now persist
more of the runtime truth that quality and improvement systems need.

Implemented behavior:

- `steps_executed`
- `knowledge_cards_used`
- `revision_count`
- `template_used`
- `design_system`
- `runtime_controls`
- `quality_summary`
- `artifact_summary`

On successful runs, the executor now also attempts to feed outcome recording
through [`tools/knowledge.py`](/Users/Executor/vizier/tools/knowledge.py).

## Before vs After

### Before

- QA, tripwire, guardrails, and delivery operated on partially disconnected
  payloads
- visual QA in the governed path did not reliably evaluate the actual artifact
- the strongest visual-quality machinery lived off to the side
- runtime controls and quality posture existed, but did not govern enough
- stage `knowledge:` was mostly declarative rather than operational
- success mainly meant "stages ran"

### After

- one shared artifact payload is carried through the governed workflow
- QA evaluates the real rendered visual artifact
- tripwire revisions affect the artifact fields that are actually delivered
- delivery depends on a binding quality verdict when the runtime profile
  requires it
- budget profile and quality posture are explicit runtime controls
- stage knowledge is injected, traced, and measurable
- successful runs now persist richer quality/improvement data

The most important change is semantic:

**success now means the artifact for this job passed the active quality bar,
not merely that the workflow advanced through its stages.**

## Verification Results

### Type checking

- `pyright` on the modified runtime and test files:
  - `0 errors`
  - `0 warnings`

### Focused regression slices

- [`tests/test_orchestrate.py`](/Users/Executor/vizier/tests/test_orchestrate.py)
- [`tests/test_e2e_layer5b_semantics.py`](/Users/Executor/vizier/tests/test_e2e_layer5b_semantics.py)
- [`tests/test_workflows.py`](/Users/Executor/vizier/tests/test_workflows.py)

Result:

- `115 passed`

Additional focused validation:

- poster acceptance + visual intelligence + briefing modules:
  - `47 passed`
  - `4 skipped`

### Full local verification

Command:

```bash
DATABASE_URL=postgres://localhost:5432/vizier pytest -q
```

Result:

- `787 passed`
- `3 skipped`
- `10 warnings`

Warnings were non-blocking library warnings from `open_clip` and
`sklearn`-cluster convergence, not runtime-quality-spine regressions.

## Rationale

The implementation intentionally did not treat this as a collection of local
bug fixes.

The graph-derived root cause was that Vizier had:

- multiple quality communities
- shallow success semantics
- duplicate visual-quality paths
- config that informed more than it governed

The implemented changes therefore favored shared runtime structures over local
patches:

- one artifact payload instead of multiple local result shapes
- one shared visual evaluator instead of a sidecar "strong path"
- one runtime-control seam instead of ad hoc token choices
- one trace truth rich enough for quality and improvement analysis

This is why the remediation improves both deliverable quality and confidence in
success states at the same time.

## Relationship To MemPalace Runtime Adoption

This work also created a stronger insertion point for the MemPalace-inspired
runtime enhancements documented in
[`docs/VIZIER_MEMPALACE_RUNTIME_ADOPTION_REPORT_2026-04-08.md`](/Users/Executor/vizier/docs/VIZIER_MEMPALACE_RUNTIME_ADOPTION_REPORT_2026-04-08.md)
and
[`docs/superpowers/plans/2026-04-08-runtime-mempalace-adoption.md`](/Users/Executor/vizier/docs/superpowers/plans/2026-04-08-runtime-mempalace-adoption.md).

Specifically, the quality-spine work now provides:

- a real `runtime_controls` seam for layered context budgets
- a real `job_context` seam for passive vs stage-specific retrieval
- richer trace/output persistence for retrieval-layer evidence
- a governed runtime path into which classifier labels and a temporal fact
  layer can be integrated without creating a second memory architecture

In other words, the MemPalace adoption work is now a clean extension of this
runtime, not a competing subsystem.

## Residual Risks And Remaining Work

The quality spine is materially stronger, but this pass does not mean all
quality-adjacent work is complete.

Remaining work includes:

- exemplar promotion metadata is still thinner than ideal for long-term
  retrieval and style anchoring
- not every LLM-using helper in the repo is yet governed by the new budget
  profile model
- some registry tools remain intentional stubs outside the primary delivered
  poster path
- checked-in client/brand/design-system data is still sparse, which limits
  on-brand performance even when the wiring is correct
- Hermes-side pre-compaction save behavior remains a separate runtime concern,
  as documented in the MemPalace adoption report

These are now follow-on improvements on top of a verified governed runtime
spine rather than blockers to the core architecture.
