# Lessons Learned: Vizier Build Plan V1 (Codex Regenerated Version)

**Date:** 2026-04-11  
**Status:** Decision record / reusable post-mortem  
**Scope:** Original build plan through S21, plus the post-S21 hardening and quality-recovery sessions that followed

---

## Executive Summary

Build Plan V1 did not fail because the team was careless, and it did not fail because the architecture was incoherent.

It failed because the build sequence optimized for **architecture completeness before output quality**.

By S21, the system had built:

- contracts
- governance
- routing
- observability
- workflow execution
- policy layers
- self-improvement infrastructure

But it had **not yet proven** the things the architecture implicitly promised:

- posters consistently at a believable commercial floor
- books / ebooks truthfully deliverable through the governed path
- dataset value transformed into runtime quality gains
- adaptive brief rescue on the live user path
- a trustworthy end-to-end acceptance suite showing "this is sellable"

The strongest evidence is what happened after S21. The most important quality work landed later anyway:

- `61da662` structured coaching with content gates
- `8da7755` industry-specific coaching patterns
- `2c38a66` config-driven NIMA threshold wiring
- `4bd853a` template selector `industry_fit`
- `61e1927` D4 -> 28 poster archetypes
- `5343b41` `industry_fit` tags on existing templates
- `ae35802` cross-session quality intelligence tests

That recovery tranche proves the original critical path was wrong.

---

## What The Original Plan Assumed vs What Actually Happened

### S0-S4: Foundation first would make later quality easy

**Plan assumed**

- if runtime, contracts, storage, and integration boundaries were sound, quality could be layered on safely later

**What actually happened**

- the foundation work was valuable, but it consumed the early schedule without creating one undeniably good artifact lane
- the system became structurally sophisticated before it became visually credible

**Cost**

- launch-quality proof got delayed behind groundwork that was necessary, but not sufficient

### S5: Downloading and extracting datasets would naturally improve quality

**Plan assumed**

- once the datasets were present and their quality frameworks were extracted, later sessions would benefit from them

**What actually happened**

- the build assigned acquisition and extraction, but not the transformation step that turns datasets into runtime value
- the repo later had to explicitly diagnose this in [dataset_transformation_gap.md](/Users/Executor/vizier/docs/decisions/dataset_transformation_gap.md)

**Concrete drift**

- D4 existed, but no clustering-to-template path was initially on the critical path
- D12 quality knowledge existed, but threshold promotion remained late and partial
- D8 marketing data existed, but coaching patterns were only wired much later

**Lesson**

- a dataset is not a capability
- only transformed, consumed, tested artifacts count

### S6-S9: Governance, readiness, and workflow infrastructure should come early

**Plan assumed**

- governance from day one would prevent bad behavior later

**What actually happened**

- governance became real before the governed outputs were good enough
- readiness and routing logic could classify jobs, but not rescue a weak artifact lane into a strong one

**Concrete drift**

- `contracts/routing.py` implemented `refine_request()`
- but the live path kept auto-enriching and continuing in `tools/orchestrate.py` instead of using adaptive clarification
- quality posture and policy machinery matured before the visual floor was proven

**Lesson**

- governance is highly leveraged only after one end-to-end artifact path already produces acceptable output

### S10-S13: Poster and visual quality systems were treated as additive instead of primary

**Plan assumed**

- template selection, visual scoring, and quality middleware would raise the lane sufficiently

**What actually happened**

- the system built scoring and guardrails around a weak or incomplete template/taste base
- early poster support existed, but it was not yet strong enough to support the product promise

**Concrete drift**

- visual scoring existed before thresholds were truly calibrated
- poster templates existed, but the strong D4-derived archetype tranche came later
- quality gates existed, but the governed acceptance proof did not establish "sellable"

**Lesson**

- quality gating cannot substitute for a strong underlying artifact corpus

### S14-S15: Publishing ambition ran ahead of governed truth

**Plan assumed**

- books, ebooks, and illustrated outputs could be advanced in parallel with posters without breaking the launch path

**What actually happened**

- meaningful tooling for illustration and publishing was built
- but governed deliverability truth lagged or remained conservative in the registry
- the product story was broader than the verified support matrix

**Concrete drift**

- tests for illustration / ebook / children-book lanes are now strong
- but `config/workflow_registry.yaml` still marks key publishing workflows as `deliverable: false`

**Lesson**

- support claims must trail proof, not precede it

### S16-S19: Knowledge spine, business ops, and self-improvement were scheduled too early

**Plan assumed**

- observability, stewardship, memory, calibration, and drift tooling needed to be architecturally ready before launch

**What actually happened**

- these systems were sensible in isolation
- but many depended on production fuel that did not yet exist
- meanwhile the core artifact quality path still had unresolved gaps

**Concrete drift**

- operator exemplar taste retrieval was not yet live
- calibration infrastructure existed before committed calibrated values
- self-improvement logic was built before there was a trustworthy launch-quality baseline to improve

**Lesson**

- post-launch optimization loops should not outrank pre-launch output quality

### S20-S21: Integration and completion were declared before sellable-proof was secure

**Plan assumed**

- if sessions completed and tests were broadly green, the architecture promise had effectively been met

**What actually happened**

- the repo reached a sophisticated "assembled system" state
- but still lacked a clean governed proof that the outputs met the expected floor
- post-S21 sessions then had to harden truth, recover quality, and fill missing dataset/coaching/template paths

**Concrete drift**

- poster acceptance proof is still not clean today
- `quality="high"` still maps to invalid `quality_posture="production"` on current `main`
- operator exemplar taste-layer runtime use is still incomplete

**Lesson**

- completion against session exit criteria is not the same as completion against product promise

---

## Structural Anti-Patterns Detected

### 1. Architecture-forward, artifact-late

The build kept rewarding infrastructure completion even when no lane had yet proven commercial output quality.

**Damage**

- many later sessions were forced into recovery instead of leverage

### 2. Governance before the governed

Policy, posture, readiness, and validation machinery matured before there was a trustworthy output lane worth governing.

**Damage**

- the system became good at regulating incomplete quality

### 3. Routing before worthwhile destinations

Selection logic and abstraction layers were built before the selectable pools were strong enough.

**Damage**

- smart routing over weak templates still yields weak output

### 4. Dataset acquisition without transformation ownership

The build treated "downloaded" and "extracted" as if they were close to "runtime benefit."

**Damage**

- the biggest advertised quality inputs sat nearby but dormant

### 5. Quality gates without acceptance proof

The repo accumulated scoring, guardrails, and tests that mostly verified contracts, not sellable results.

**Damage**

- confidence drifted ahead of customer-visible truth

### 6. Deliverability truth drift

Narrative, publishing, and support claims moved out of sync with the governed support matrix and verified production path.

**Damage**

- debugging sessions had to spend time re-establishing honesty before improving quality

### 7. Optimization loops before baseline value

Self-improvement, drift detection, and calibration systems were scheduled before the system had a proven baseline artifact worth optimizing.

**Damage**

- high-quality engineering effort landed in low-leverage order

---

## Specific Dead Code, Dormant Infra, and Missing Wiring

These examples matter because they show the pattern was real, not abstract.

### Adaptive clarification existed but was not live

- `contracts/routing.py` contains `refine_request()`
- the main governed flow continued with auto-enrichment instead of a live adaptive clarification loop

### Dataset-to-template value was late

- D4-derived poster archetypes are now real on current `main`
- their late arrival is itself evidence that this should have been earlier

### Threshold config existed before truthfully calibrated values

- config-driven NIMA reading is now wired
- but the calibration file still needed actual promoted values and provenance

### Taste-layer ingestion existed before runtime retrieval use

- operator exemplar ingestion scripts exist
- runtime retrieval still does not fully consume that taste layer

### Deliverability capability and deliverability truth diverged

- publishing lanes have significant test coverage
- workflow registry truth still trails that reality

### Quality posture lane still has a live bug

- the bridge maps `quality="high"` to `quality_posture="production"`
- runtime posture validation does not accept `production`

---

## Cost Of Each Anti-Pattern

These are approximate, but directionally useful.

### Architecture-forward sequencing

**Estimated cost:** 4-6 sessions of delayed quality closure

Because:

- quality-critical work had to be built after the supposed finish line

### Dataset transformation gap

**Estimated cost:** 2-3 sessions of explicit remediation

Because:

- dataset value had to be rediscovered, specified, and then transformed after the fact

### Governance before artifact proof

**Estimated cost:** 2-3 sessions of hardening and truth correction

Because:

- the system needed later work to reconcile policy/support claims with reality

### Deliverability truth drift

**Estimated cost:** 1-2 sessions of review, handover churn, and support-matrix correction

Because:

- successors had to spend time verifying what was actually launchable

### Optimization loops too early

**Estimated cost:** 1-2 sessions of lower-leverage engineering before baseline quality was secure

Because:

- the repo prepared to optimize things that were not yet good enough

### Total

**Estimated total sequencing penalty:** roughly 8-12 sessions of avoidable delay, rework, or deferred leverage

That estimate fits what the repo history now shows: a substantial post-S21 recovery tranche was necessary just to restore the missing quality path.

---

## Revised Heuristics For Future Build Plans

### 1. No quality gate session until one real artifact lane is visibly good end-to-end

Governance is not the first proof of quality. The artifact is.

### 2. No template selector sophistication before a strong template pool exists

Improve the choices before improving the chooser.

### 3. No dataset session without all three owners

Every dataset must have:

- acquisition owner
- transformation owner
- runtime-consumption test owner

If one is missing, the dataset is not yet on the critical path.

### 4. No launch claim without governed acceptance proof

Unit and integration tests are necessary, but insufficient.

There must be at least one credible, maintained suite proving the product floor from the user point of view.

### 5. Taste and structure must be planned separately

Academic/public datasets are often strong for structure.
Curated commercial references are often stronger for taste.
Do not confuse them.

### 6. Deliverability truth must be explicit and continuously reconciled

Workflow registries, support matrices, and product claims must reflect the governed reality, not intended ambition.

### 7. Post-launch optimization loops come after pre-launch artifact proof

Calibration, drift detection, experiments, and memory systems are high leverage only once the core output is already acceptable.

### 8. Every major session should leave behind one cross-session proof

Not just "my code works," but "the next session can prove this changed the real product path."

---

## Better Alternative Sequencing

If this build were redone for output quality by S21, the sequence should be:

1. Prove one artifact lane end-to-end at a believable commercial floor.
2. Build the template/taste corpus that drives that lane.
3. Add adaptive brief rescue on the live path.
4. Add calibrated QA thresholds tied to maintained acceptance tests.
5. Only then layer governance sophistication, broader routing, ops tooling, and self-improvement loops.
6. Expand into books / ebooks only once poster truth is stable or when those lanes themselves become first-class quality tracks with their own acceptance proof.

The revised plan in [VIZIER_BUILD_quality_first_v1.md](/Users/Executor/vizier/docs/VIZIER_BUILD_quality_first_v1.md) follows that logic.

---

## Bottom Line

The original build plan did build many correct pieces.

What it did not do was protect the one thing the user actually needed by S21:

- sellable output, proven end-to-end

The most reusable lesson is simple:

**A build plan should optimize for the earliest believable product floor, not the earliest architectural completeness.**

Everything else compounds from that.
