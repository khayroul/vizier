# Runtime + MemPalace Pattern Adoption — Implementation Plan

> **For agentic workers:** This plan is meant to be applied inside the current runtime-strengthening work, not as an unrelated side branch. Do not revert or replace the active runtime-control changes. Extend them.

**Goal:** Adopt the high-value MemPalace patterns that strengthen Vizier's runtime retrieval, fact lookup, and context discipline without adding new dependencies or a parallel memory stack.

**Primary outcome:** The governed runtime path gains:

- explicit layered context loading
- cheap memory-type labeling
- a temporal fact layer for structured queries
- a documented decision on pre-compaction save behavior

**Report to update before and after implementation:** `docs/VIZIER_MEMPALACE_RUNTIME_ADOPTION_REPORT_2026-04-08.md`

**Related runtime context:** `docs/VIZIER_QUALITY_SPINE_REMEDIATION_REPORT_2026-04-08.md`

**Source material:** MemPalace v3.0.0 (`knowledge_graph.py`, `general_extractor.py`, `layers.py`, `hooks/mempal_precompact_hook.sh`)

---

## Read This First

This plan is intentionally opinionated about what to adopt and what to reject.
The previous MemPalace evaluation concluded:

1. Vizier already has a strong hybrid retrieval spine.
2. The current runtime session is already making retrieval and runtime controls
   real.
3. The correct move is to enrich the current runtime seam, not build a second
   "memory system".

So the key rule is:

**MemPalace patterns must be translated into Vizier's existing runtime-control,
Postgres, and Hermes boundary model.**

Notable constraints:

- No new Python/package dependencies
- No ChromaDB
- No MemPalace install
- No second context-loading config stack beside runtime controls
- No async-postgres redesign
- No partial takeover of Hermes compaction/session semantics unless the current
  session is already modifying Hermes runtime code

---

## Current Vizier State To Build On

Use these as your anchors:

- `middleware/runtime_controls.py`
  - already resolves `quality_posture`, `budget_profile`, token caps, retry
    caps, and `knowledge_card_cap`
- `tools/orchestrate.py`
  - already injects runtime controls into `job_context`
- `tools/executor.py`
  - already resolves stage knowledge and injects knowledge context into prompts
- `utils/knowledge.py`
  - already performs hybrid retrieval and context assembly
- `config/retrieval_profiles.yaml`
  - already describes retrieval budgets and pipeline behavior
- `tools/knowledge.py`
  - already owns ingestion, outcome memory, and exemplar promotion

Known gaps relevant to this plan:

- `tools/registry.py` still exposes `knowledge_retrieve` and `knowledge_store`
  as stubs in the workflow registry
- `knowledge_cards` has no general metadata JSONB field
- there is no temporal fact layer
- Hermes pre-compaction behavior is not owned by Vizier

---

## Pattern Decisions

### Pattern A: Layered context loading

Adopt now, but implement through runtime controls and retrieval profiles.

Do not:

- create a separate `context_strategy.yaml`
- duplicate budget logic outside `phase.yaml` / runtime controls

Do:

- map L0/L1/L2 passive loading into runtime ceilings and stage behavior
- keep L3 as explicit deep retrieval/tool use

### Pattern B: Heuristic memory classification

Adopt now, but tie it directly to storage and retrieval.

Do:

- preserve the upstream extractor's useful behavior such as code filtering,
  segment-level scoring, and disambiguation
- persist labels into the knowledge layer
- expose those labels to retrieval and trace/reporting

### Pattern C: Temporal knowledge graph

Adopt if the current session still has capacity for schema and utility work.

Do:

- build it in Postgres
- align to Vizier's UUID-backed tables
- scope everything by client
- keep provenance links to jobs/cards

Do not:

- mirror the SQLite design mechanically
- introduce an async pool abstraction just for this

### Pattern D: Pre-compaction save

Only implement if the current session is already inside Hermes/session code.

Otherwise:

- document the plan
- define what data should be saved
- leave the actual hook implementation to a dedicated Hermes runtime session

---

## Execution Order

The recommended order is designed to reinforce the runtime work already in
flight and minimize merge risk with the dirty worktree.

1. Document the baseline and preserve the rationale
2. Convert layered context loading into explicit runtime behavior
3. Add heuristic classification and retrieval labels
4. Add the temporal knowledge graph
5. Wire fact/label extraction into runtime persistence points
6. Decide and optionally implement Hermes pre-compaction save
7. Verify and update the after-state report

---

## Chunk 0: Documentation Baseline

### Task 0.1: Read and preserve context

Read these files first:

- `docs/VIZIER_MEMPALACE_RUNTIME_ADOPTION_REPORT_2026-04-08.md`
- `docs/VIZIER_QUALITY_SPINE_REMEDIATION_REPORT_2026-04-08.md`
- `middleware/runtime_controls.py`
- `tools/orchestrate.py`
- `tools/executor.py`
- `utils/knowledge.py`
- `tools/knowledge.py`

Goal:

- understand the current runtime seam
- avoid fighting the existing runtime-strengthening work
- preserve the baseline report before changing behavior

### Task 0.2: Confirm active file ownership

Because the worktree is already dirty, do not assume a clean isolated change.

Before editing, inspect current local modifications in:

- `config/phase.yaml`
- `contracts/trace.py`
- `tools/executor.py`
- `tools/orchestrate.py`
- `tools/registry.py`
- `middleware/runtime_controls.py`

Rule:

- work with those changes
- do not overwrite them with a stale local mental model

---

## Chunk 1: Layered Context Loading Through Runtime Controls

### Objective

Turn the MemPalace 4-layer discipline into governed runtime behavior without
creating a second configuration regime.

### Files

- Modify: `middleware/runtime_controls.py`
- Modify: `config/phase.yaml`
- Modify: `config/retrieval_profiles.yaml`
- Modify: `tools/executor.py`
- Modify: `utils/knowledge.py`
- Potentially modify: `contracts/trace.py`

### Design decisions

Use the following mapping:

- **L0 identity**
  - client identity, brand, defaults, copy register
  - always available through resolved runtime context
- **L1 essentials**
  - small passive card set loaded automatically
  - controlled by budget profile and retrieval ceilings
- **L2 workflow context**
  - stage-specific declarative knowledge loading
  - loaded only when stage config asks for it
- **L3 deep search**
  - explicit retrieval/tool-triggered expansion beyond passive budget

### Steps

- [x] Add explicit passive-context fields to runtime controls.
  Suggested fields:
  - `identity_context_cap`
  - `essential_context_cap`
  - `workflow_context_cap`
  - `allow_deep_search`

- [x] Keep those fields under the existing `budget_profiles` structure in
  `config/phase.yaml`, not in a new standalone context config file.

- [x] Update runtime-control resolution so these caps are carried into
  `job_context`.

- [x] Update `tools/executor.py` stage knowledge resolution so passive loading
  honors those caps.

- [x] Update `utils/knowledge.py` context assembly helpers so they can:
  - distinguish passive vs explicit retrieval
  - cap snippets by budget tier
  - return enough metadata to show which layer produced what

- [x] Update trace/reporting so runtime evidence can answer:
  - how many cards were passively loaded
  - how many were stage/workflow specific
  - whether deep search was invoked

### Verification

- unit tests for runtime-control resolution
- tests for executor stage knowledge injection under each budget profile
- assertions that lean/standard/critical produce different knowledge behavior

### Done when

- context layering is real runtime behavior
- budget profiles now govern context richness, not just token caps

### Progress note — 2026-04-09

The first implementation slice is complete:

- runtime controls now expose explicit L0/L1/L2 context caps
- stage knowledge assembly distinguishes essential vs workflow cards
- executor trace now records context-layer usage

What remains in this chunk is deeper retrieval-profile integration and any
follow-on tuning of passive-vs-deep retrieval behavior.

---

## Chunk 2: Heuristic Memory Classification

### Objective

Introduce cheap structure for memory/retrieval types so decisions, problems,
milestones, and preferences can be surfaced deliberately.

### Files

- Create: `utils/memory_classifier.py`
- Modify: `migrations/extended.sql` or a new migration file
- Modify: `tools/knowledge.py`
- Modify: `tools/seeding.py`
- Modify: `tools/research.py`
- Modify: `utils/knowledge.py`
- Modify: tests for knowledge spine and runtime behavior

### Schema decision

Do one of the following:

1. Preferred: add `memory_labels text[] DEFAULT '{}'`
2. Acceptable: add `metadata jsonb DEFAULT '{}'::jsonb`

Prefer the smaller change unless broader card metadata is already emerging in
the current runtime work.

### Steps

- [x] Build a lightweight deterministic classifier helper.
  Current implementation uses `utils/memory_labels.py`.
  Remaining possible upgrade: preserve more of the upstream extractor's
  segmentation/disambiguation behavior.

- [x] Add a minimal persistence field to `knowledge_cards`.

- [x] Classify cards during ingestion in `tools/knowledge.py`.

- [x] Expose label-aware retrieval in `utils/knowledge.py`.
  Current implementation:
  - persists `memory_labels`
  - exposes `query_labels`
  - lightly boosts retrieval by query/card label overlap

- [x] Surface labels in traces or retrieval debug data so quality/runtime
  reports can show whether the classifier is actually being used.

- [ ] Expand the classifier toward the upstream MemPalace extractor,
  preserving:
  - segmentation
  - code/prose filtering
  - marker-based scoring
  - disambiguation for resolved problems vs milestones

- [x] Classify seeded cards in `tools/seeding.py`.
  Covered indirectly because seeding delegates to canonical `ingest_card()`.

- [x] Classify research-ingested cards in `tools/research.py`.
  Covered indirectly because research delegates to canonical `ingest_card()`.

### Verification

- tests for segment classification
- tests for code-heavy text not being misclassified
- tests for resolved-problem paragraphs becoming milestones
- tests that labeled cards can be filtered or boosted in retrieval

### Done when

- newly ingested cards carry classifier output
- retrieval can use that output
- runtime/debug traces can show the labels involved

### Progress note — 2026-04-09

The first implementation slice is complete:

- `knowledge_cards` now have a `memory_labels` column
- deterministic classification lives in `utils/memory_labels.py`
- canonical ingestion persists labels
- retrieval exposes query labels and lightly boosts query/card overlap
- layered runtime traces can now surface those query labels

What remains in this chunk is broader ingestion coverage and a richer
classifier if we want more of the original MemPalace segmentation behavior.

---

## Chunk 3: Temporal Knowledge Graph In Postgres

### Objective

Add a structured fact layer for temporal relationships that complements, not
replaces, RAG.

### Files

- Create: migration file for KG tables
- Create: `utils/knowledge_graph.py`
- Modify: `tools/registry.py`
- Modify: `tools/executor.py` or runtime persistence helper(s)
- Potentially modify: `contracts/trace.py`

### Design constraints

- use PostgreSQL, not SQLite
- use current synchronous DB helpers
- align client/job/card references to Vizier's actual schema
- preserve provenance

### Recommended schema shape

Keep entity ids human-stable, but align provenance to real Vizier keys.

Suggested tables:

- `kg_entities`
  - `id text primary key`
  - `name text not null`
  - `entity_type text`
  - `properties jsonb`
  - `client_id uuid references clients(id)`
  - timestamps

- `kg_triples`
  - `id uuid primary key default gen_random_uuid()`
  - `subject text references kg_entities(id)`
  - `predicate text not null`
  - `object text references kg_entities(id)`
  - `valid_from date`
  - `valid_to date`
  - `confidence float`
  - `source_job_id uuid references jobs(id)`
  - `source_card_id uuid references knowledge_cards(id)`
  - `client_id uuid references clients(id)`
  - timestamps

### Steps

- [ ] Add the KG migration with indexes for subject/object/predicate/time/client.

- [ ] Implement a synchronous `KnowledgeGraph` helper around `get_cursor()`.

- [ ] Support:
  - `add_entity`
  - `add_triple`
  - `invalidate`
  - `query_entity`
  - `query_relationship`
  - `timeline`
  - `stats`

- [ ] Add registry-level runtime wrappers or direct tool callables for:
  - `queryKnowledgeGraph`
  - `addKnowledgeFact`
  - `invalidateKnowledgeFact`

- [ ] Decide retrieval policy:
  - either a direct workflow tool
  - or a pre-RAG structured lookup path for certain query types

Recommendation:

- keep KG lookup explicit or query-routed
- do not force all retrieval through KG-first logic

### Verification

- migration tests
- utility tests for dedupe and invalidation
- query-as-of-time tests
- client-scope isolation tests

### Done when

- structured facts can be queried independently of document retrieval
- provenance is preserved
- KG complements the existing retrieval spine instead of bypassing it

---

## Chunk 4: Runtime Write Path For Labels And Facts

### Objective

Make the classifier and KG part of runtime truth rather than a disconnected
storage experiment.

### Files

- Modify: `tools/executor.py`
- Modify: `tools/knowledge.py`
- Modify: `utils/trace_persist.py`
- Potentially modify: `contracts/trace.py`
- Potentially modify: `tools/improvement.py`

### Strategy

Do not invent a fake "reflection step" if one does not exist.

Instead, choose real write points already in Vizier:

- card ingestion
- stage knowledge resolution
- trace finalization/persistence
- outcome recording
- exemplar promotion input preparation

### Steps

- [ ] Add runtime extraction points for classifier output.

- [ ] Decide where fact extraction belongs.
  Recommended order:
  1. deterministic/runtime-known facts first
  2. heuristic extraction second
  3. LLM extraction later only if justified

- [ ] Start with narrow, high-confidence fact classes only:
  - approved_by
  - assigned_to
  - decided
  - uses_template
  - uses_design_system
  - workflow_for_client

- [ ] Persist those facts from runtime truth already present in
  `job_context`, artifact payload, trace, or outcome data.

- [ ] Avoid broad free-text fact mining in the first iteration.

### Verification

- tests that runtime-known facts land in KG
- tests that trace/outcome persistence records enough provenance
- tests that failure paths do not create garbage facts

### Done when

- KG and classifier outputs are fed by the real governed path
- the improvement loop can inspect richer runtime truth later

---

## Chunk 5: Hermes Pre-Compaction Save Decision

### Objective

Make an explicit decision on the MemPalace pre-compact pattern instead of
leaving it vague.

### Files

- If implementing in this session:
  - Hermes hook/plugin files outside the core Vizier runtime path
- If not implementing:
  - update the report with deferral rationale

### Decision rule

Only implement now if the active session is already touching Hermes gateway or
session lifecycle code.

If yes:

- [ ] adapt the MemPalace `PreCompact` idea into Hermes hook/plugin form
- [ ] save a concise runtime summary, not an unbounded transcript dump
- [ ] define exactly what is saved:
  - unresolved questions
  - latest artifact/runtime state
  - key decisions
  - important labels/facts

If no:

- [ ] document the design and defer implementation

### Verification

- if implemented: hook-level verification and one real compaction simulation
- if deferred: report updated with exact ownership boundary and next step

### Done when

- the plan is explicit about whether this pattern shipped or was deferred

---

## Chunk 6: Runtime Registry Cleanup

### Objective

Ensure the newly strengthened retrieval path is not undermined by stubbed or
duplicate runtime paths.

### Files

- Modify: `tools/registry.py`
- Modify: `tools/executor.py`
- Potentially modify: any now-obsolete helper wrappers

### Steps

- [ ] Replace `knowledge_retrieve` stub behavior with real runtime retrieval or
  explicitly demote it if stage knowledge loading has fully superseded it.

- [ ] Replace `knowledge_store` stub behavior with real ingestion or keep it
  intentionally unavailable with clear failure semantics.

- [ ] Confirm no duplicate retrieval/control path now competes with the new
  layered runtime behavior.

- [ ] If the runtime-strengthening session is also collapsing duplicate visual
  quality paths, ensure the MemPalace-related changes plug into the same
  canonical governed path.

### Verification

- registry tool tests
- end-to-end workflow tests for stages that declare `knowledge:`

### Done when

- the runtime path is clearer after this work, not more duplicated

---

## Chunk 7: Verification And After-State Documentation

### Objective

Close the loop with both tests and narrative documentation.

### Files

- Update: `docs/VIZIER_MEMPALACE_RUNTIME_ADOPTION_REPORT_2026-04-08.md`
- Potentially update: `docs/VIZIER_QUALITY_SPINE_REMEDIATION_REPORT_2026-04-08.md`
- Potentially update: `docs/VIZIER_ARCHITECTURE_v5_4_1.md`

### Steps

- [ ] Run targeted tests for:
  - runtime controls
  - executor knowledge injection
  - knowledge retrieval
  - classifier behavior
  - KG utilities

- [ ] Run relevant integration tests for runtime workflows that consume
  declarative knowledge.

- [ ] Update the report with:
  - exact files changed
  - schema changes
  - runtime behavior changes
  - what shipped vs what was deferred
  - verification results
  - residual risks

- [ ] If the architecture changed durably enough, fold the stable design
  outcomes into the architecture doc rather than leaving them only in an
  implementation report.

### Done when

- the code and the documentation tell the same story
- the report clearly captures before-state rationale and after-state outcome

---

## Non-Goals

This session should not:

- install MemPalace
- add ChromaDB
- add a parallel memory service
- rewrite DB access to async
- invent a second runtime-control language
- broadly mine arbitrary free text into KG facts in the first pass
- partially own Hermes session compaction unless already working in Hermes

---

## Final Success Criteria

This plan is successful when:

- layered context loading is runtime-governed
- labeled memory/retrieval types are persisted and usable
- structured temporal facts are queryable with provenance
- retrieval remains one coherent Vizier system
- runtime reports can explain what changed and why
- the before/after documentation is detailed enough to survive into
  architecture or post-build documentation later
