# Vizier MemPalace Runtime Adoption Report

Date: 2026-04-08
Repo: `/Users/Executor/vizier`
Status: Baseline assessment complete, implementation pending

## Purpose

This report documents the rationale, findings, source review, and intended
before/after record for adopting selected MemPalace patterns into Vizier.

The goal is not to install MemPalace or add another memory stack beside
Vizier's existing one. The goal is to extract a small set of high-value
patterns and implement them natively inside Vizier's current runtime,
retrieval, storage, and governance architecture.

This report is meant to serve two jobs:

1. The "before" document for the current runtime-strengthening session
2. The document to update after implementation so the architectural delta is
   recorded in one place

## Executive Summary

Vizier already has much of the retrieval backbone that MemPalace would
normally justify:

- hybrid retrieval over `knowledge_cards`
- query variants, FTS, RRF, reranking, and lost-in-the-middle ordering
- client config and seasonal context assembly
- outcome memory and exemplar promotion
- rolling context contracts for long-running creative workflows
- explicit runtime controls for quality posture and budget profile

What Vizier does not yet have is the specific combination of:

1. A structured fact layer for temporal relationships
2. A fully operational layered context-loading discipline in runtime
3. A cheap first-pass classifier for memory/retrieval types
4. A pre-compaction save strategy tied to Hermes session pressure

The conclusion of this assessment is:

- Adopt the MemPalace layered-context discipline now, but fold it into
  Vizier's existing runtime controls instead of creating a second parallel
  config model.
- Adopt the temporal knowledge graph, but implement it with Vizier-native
  PostgreSQL, UUID references, client scoping, and current synchronous DB
  helpers.
- Adopt heuristic memory classification, but wire it into card metadata,
  retrieval filters, and runtime trace/output persistence rather than treating
  it as a standalone extractor.
- Treat the pre-compact save as a Hermes-side hook/plugin concern. It is a
  good idea, but it is not a pure Vizier-runtime feature.

## Why This Belongs In The Current Runtime Session

The current runtime-strengthening work is already moving the codebase toward
one governed runtime path with explicit controls and better knowledge/runtime
binding.

Relevant current-state signals in this checkout:

- `middleware/runtime_controls.py` introduces explicit runtime controls from
  config to execution.
- `tools/orchestrate.py` now resolves those runtime controls into `job_context`
  before workflow execution.
- `tools/executor.py` already contains a new `_resolve_stage_knowledge()`
  helper and injects retrieved knowledge into stage prompts.
- `tools/executor.py` also persists richer runtime truth into trace fields such
  as `knowledge_cards_used`, `runtime_controls`, `quality_summary`, and
  artifact summary fields.
- `docs/VIZIER_QUALITY_SPINE_REMEDIATION_REPORT_2026-04-08.md` explicitly
  identifies "knowledge in workflow YAML is still mostly dormant at runtime"
  and "config that informs but does not govern" as root causes.

That makes this the right insertion point. MemPalace's useful ideas should be
layered into the runtime work that is already making knowledge retrieval,
budget controls, and artifact-state governance real.

This should not become a separate "memory feature branch" with its own
concepts, context budgets, and persistence model. It should reinforce the
runtime path that is already being unified.

## Source Material Reviewed

The patterns in scope come from MemPalace v3.0.0 by `milla-jovovich`
(MIT-licensed). Vizier is not adopting the package itself. The source was
reviewed only to extract portable design patterns.

Reviewed source files:

- `https://raw.githubusercontent.com/milla-jovovich/mempalace/v3.0.0/mempalace/knowledge_graph.py`
- `https://raw.githubusercontent.com/milla-jovovich/mempalace/v3.0.0/mempalace/general_extractor.py`
- `https://raw.githubusercontent.com/milla-jovovich/mempalace/v3.0.0/mempalace/layers.py`
- `https://raw.githubusercontent.com/milla-jovovich/mempalace/v3.0.0/hooks/mempal_precompact_hook.sh`

Patterns extracted:

1. Temporal knowledge graph
2. Four-layer context loading protocol
3. Pre-compaction emergency save
4. Heuristic memory classification

## Vizier Baseline Relevant To This Work

### Retrieval and storage already present

Vizier already has a strong document/card retrieval spine:

- `utils/knowledge.py` implements query variants, semantic search, FTS, RRF,
  reranking, and lost-in-the-middle reordering.
- `config/retrieval_profiles.yaml` already defines retrieval profiles and
  pipeline parameters.
- `tools/knowledge.py` already supports ingestion, exemplar promotion, and
  outcome-memory persistence.
- `tools/seeding.py` already creates knowledge cards from client config,
  brand patterns, and copy patterns.

### Runtime controls already emerging

The active runtime work already introduced:

- explicit budget profiles in `config/phase.yaml`
- runtime control resolution in `middleware/runtime_controls.py`
- propagation into `job_context` in `tools/orchestrate.py`
- stage knowledge injection in `tools/executor.py`

This is important because MemPalace's layered-loading discipline should be
implemented through these controls, not beside them.

### Rolling context already exists

Vizier already has a generic `RollingContext` contract and file-backed entity
registry patterns for serial fiction. Those solve a different problem from the
proposed temporal KG:

- `RollingContext` preserves coherence across generated sequences
- a temporal KG would preserve queryable relational facts across jobs and time

These are complementary, not redundant.

### Current limitations

The current state still has several relevant gaps:

- `knowledge_retrieve` and `knowledge_store` in `tools/registry.py` are still
  stubs in the workflow tool registry.
- `context_budget_tokens` exists in config but is not the runtime governor.
- the executor can inject stage knowledge, but there is not yet a typed fact
  layer for approvals, ownership, changes, or temporal relationships.
- `knowledge_cards` does not currently have a metadata JSONB field for
  classifier output.
- Vizier's DB helper uses synchronous `psycopg2`, not async pools.
- there is no Vizier-native thread-memory table for emergency overflow save.
- Hermes session pruning and pre-compaction behavior live on the Hermes side,
  not in the Vizier repo.

## Pattern-by-Pattern Findings

### Pattern 1: Temporal Knowledge Graph

Assessment: Strong fit, but must be adapted carefully.

Why it helps:

- structured relationship questions are poorly served by document-only RAG
- temporal facts like approvals, assignments, ownership, status changes, and
  "what changed since X" benefit from direct lookup
- KG facts can point back to jobs, cards, or policy logs for provenance

Why the proposed implementation must change:

- Vizier uses synchronous `psycopg2` helpers in `utils/database.py`
- Vizier stores clients, jobs, artifacts, and cards with UUID-backed tables
- the current plan's `TEXT` ids for `client_id`, `source_job_id`, and
  `source_card_id` should instead align to Vizier's real schema and key types

Recommended adaptation:

- add Postgres KG tables with UUID foreign keys where possible
- keep entity ids stable and human-oriented, but use proper client/job/card
  references for provenance
- scope queries by client
- keep KG writes append-oriented and reversible via `valid_to`

### Pattern 2: Four-Layer Context Loading Protocol

Assessment: Best immediate fit.

Why it helps:

- makes context loading predictable and debuggable
- gives runtime controls a concrete meaning beyond token caps alone
- reduces the risk that retrieval expands until the actual task is crowded out

Why the proposed implementation must change:

- Vizier already has `budget_profiles` and runtime controls in `phase.yaml`
- Vizier already assembles client config and seasonal context in
  `utils/knowledge.py`
- creating a separate `config/context_strategy.yaml` would duplicate what
  budget profiles are already starting to express

Recommended adaptation:

- represent L0/L1/L2 ceilings inside runtime controls or retrieval profiles
- treat L3 as explicit search/tool-triggered deep retrieval
- make the executor and stage-knowledge path honor those budgets

### Pattern 3: Pre-Overflow Thread Memory Save

Assessment: Good idea, wrong layer for most of the work.

Why it helps:

- long Hermes sessions already show cost and quality degradation from stale
  accumulated context
- saving important context before compaction reduces silent state loss

Why the proposed implementation must change:

- Vizier does not currently own Hermes session lifecycle
- there is no native Vizier thread-memory store ready for overflow snapshots
- MemPalace's upstream hook is fundamentally a pre-compaction block-and-save
  strategy, not a complete persistence backend

Recommended adaptation:

- implement this as a Hermes hook/plugin concern if the current session is
  already modifying gateway/session behavior
- if not, document it and defer it to a dedicated Hermes runtime session
- keep Vizier's role limited to defining what should be saved and how that
  should be summarized or classified

### Pattern 4: Heuristic Memory Classification

Assessment: Worth adopting if tied directly to retrieval and persistence.

Why it helps:

- adds cheap structure to knowledge cards, reflections, and summaries
- improves retrieval filtering for things like decisions, problems, and
  milestones
- provides a first-pass signal without extra LLM cost

Why the proposed implementation must change:

- the simplified proposal under-specifies the upstream extractor's paragraph
  splitting, code filtering, and disambiguation
- `knowledge_cards` currently lacks a metadata JSONB column

Recommended adaptation:

- add either a `memory_labels text[]` column or a `metadata jsonb` column to
  `knowledge_cards`
- classify at ingestion time, reflection time, and any runtime save step
- use labels to bias retrieval and improve operator/debug queries

## Adoption Decisions

### Adopt now

- Layered context-loading discipline, merged into runtime controls
- Heuristic classification for card and runtime memory labeling
- Temporal knowledge graph schema and utilities, if the current runtime session
  still has room for storage-layer work

### Adopt now only if already in Hermes/session code

- Pre-compaction save hook and session-pressure save behavior

### Do not adopt

- ChromaDB
- MemPalace package install
- separate memory storage stack beside Postgres + existing Hermes session state
- any design that duplicates Vizier runtime controls with a parallel config
  regime

## Architectural Recommendations

### Recommendation 1: Keep one runtime control model

`quality_posture`, `budget_profile`, retrieval caps, passive context ceilings,
and optional classifier/KG toggles should all live in one runtime-control
language.

MemPalace should strengthen that language, not compete with it.

### Recommendation 2: Keep one retrieval system

Vizier should continue to use:

- Postgres + pgvector
- FTS
- RRF
- reranking
- declarative stage knowledge

The KG should become an additional retrieval substrate, not a replacement.

### Recommendation 3: Keep one provenance model

Every structured fact introduced by KG or classification should retain a link
back to:

- the originating job
- the originating card when available
- the originating trace or outcome record where applicable

This keeps structured facts auditable.

### Recommendation 4: Keep Hermes responsibilities separate

Hermes owns:

- session lifecycle
- compaction
- gateway behavior
- thread persistence outside Vizier data tables

Vizier owns:

- artifact/runtime contracts
- retrieval and knowledge storage
- outcome/exemplar persistence
- structured fact models and runtime context policy

## Risks and Constraints

### Dirty worktree constraint

The current runtime-strengthening session already has local modifications in:

- `config/phase.yaml`
- `contracts/trace.py`
- `tools/executor.py`
- `tools/orchestrate.py`
- `tools/registry.py`
- `middleware/runtime_controls.py`
- multiple tests

Any follow-on Codex session must work with those changes, not revert them.

### Scope creep risk

This adoption can easily turn into "build an entire memory platform".
That is not the goal. The goal is to strengthen runtime retrieval, fact lookup,
and context discipline with a few specific patterns.

### Schema risk

The KG and classifier work will likely require schema changes. Those should be
minimal and directly justified by runtime behavior.

### Ownership boundary risk

The pre-overflow save idea becomes dangerous if Vizier starts partially owning
Hermes session semantics while Hermes still owns compaction behavior. That
boundary should stay explicit.

## Success Criteria

The MemPalace adoption is successful when:

- runtime context loading is explicitly layered and budgeted
- stage `knowledge:` behavior is more predictable and traceable
- knowledge cards can be filtered or labeled by memory type
- structured factual queries can resolve through a temporal fact layer instead
  of document search alone
- provenance for structured facts is auditable
- no duplicate memory/retrieval control model is introduced
- Hermes/session save behavior, if implemented, is clearly separated from
  Vizier app-layer logic

## What To Update After Implementation

When the plan is implemented, this report should be updated with:

### Exact changes shipped

- files modified
- tables/columns added
- tools or helpers introduced
- runtime-control fields added or changed

### Behavioral changes

- what now happens at session/job startup
- what now happens on stage knowledge resolution
- how classifier labels affect retrieval
- how KG lookup is used relative to RAG
- whether pre-compaction save behavior was implemented or deferred

### Verification

- targeted tests added
- integration tests added
- live or fixture-backed runtime checks
- any benchmark or retrieval-quality spot checks

### Residual risks

- anything intentionally deferred
- accuracy limits of heuristic classification
- open questions around automatic fact extraction

## Candidate Architecture-Doc Updates After Build

If implementation lands successfully, the architecture doc is the right place
to fold in the durable design decisions:

- the runtime-control interpretation of layered context loading
- the presence and scope of the temporal knowledge graph
- the role of heuristic classification in retrieval and persistence
- the explicit Hermes/Vizier split for pre-compaction memory handling

Until then, this report should remain the authoritative "before" and "during"
document for the adoption work.
