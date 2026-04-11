# Successor Prompt — Converge Claude + Codex Quality Gap Analyses

## Context

Two independent analyses were run on why Vizier doesn't produce sellable output after S21 + 12 debugging sessions. One by Claude (this repo's primary builder), one by Codex (parallel reviewer). Both produced lessons learned documents and revised build plans. They have not been compared or merged.

Your job is to read both, find what each caught that the other missed, and produce one converged gap-closing plan.

## Source Material — Read All 7 Files

### Claude's Analysis
1. `docs/decisions/lessons_learned_build_plan_v1.md` — Post-mortem: 5 false assumptions, 7 structural anti-patterns, 10 heuristics for future systems, session-by-session post-S21 tax breakdown (12 sessions, 19.5 days, 75% infra-only)
2. `docs/VIZIER_BUILD_v2.md` — Revised 8-session plan: S-T1 template ingestion → S-T2 rendering → S-E1 exemplar seeding → S-E2 anchored QA → S-B1 story architecture → S-B2 page composition → S-I1 acceptance testing → S-I2 governance wiring. Includes template ingestion metadata schema, critical path, acceptance criteria, anti-drift rules #61-#65
3. `docs/handover/HANDOVER_019_QUALITY_GAP_ANALYSIS.md` — Session handover with key numbers and merge instructions

### Codex's Analysis
4. `docs/decisions/lessons_learned_build_plan_v1_codex.md` — Codex's lessons learned (416 lines — may surface different anti-patterns or evidence)
5. `docs/QUALITY_GAP_ANALYSIS_S21.md` — Codex's gap analysis
6. `docs/VIZIER_BUILD_quality_first_v1.md` — Codex's revised build plan
7. `docs/handover/HANDOVER_018_SUCCESSOR_POST_S21_GAP_AND_RECOVERY.md` — Codex's handover

### Supporting Material
- `graphify-out/graph.html` — Interactive knowledge graph of all handover docs + decision records (198 nodes, 205 edges, 25 communities). Open in browser.
- `graphify-out/GRAPH_REPORT.md` — God nodes, surprising connections, community analysis
- `docs/VIZIER_ARCHITECTURE.md` — The original architecture document (what was promised)
- `CLAUDE.md` — Current navigation map, shared interfaces, anti-drift rules

## Task

### Step 1: Side-by-Side Comparison
Read all 7 documents. For each major finding, note:
- Did both analyses identify it? (consensus = high confidence)
- Did only one identify it? (gap = the other analysis overlooked something)
- Do they contradict on anything? (conflict = needs resolution)

Produce a comparison table:
```
| Finding | Claude | Codex | Consensus/Gap/Conflict |
```

### Step 2: Identify Blind Spots
What did each analysis miss?
- Claude focused on: post-S21 session breakdown, graphify structural patterns, heuristics for future systems, template metadata schema
- Codex focused on: (determine from reading)
- Neither covered: (identify)

### Step 3: Converge Into Final Documents

**3a. One lessons learned document:**
Write `docs/decisions/lessons_learned_build_plan_final.md`
- Merge all anti-patterns from both analyses (deduplicate, keep the better-evidenced version)
- Merge all heuristics
- Include any findings unique to one analysis that the other missed
- Keep the source evidence appendix

**3b. One build plan:**
Write `docs/VIZIER_BUILD_v2_final.md`
- Reconcile session count and sequencing between the two plans
- Pick the better template ingestion strategy (or merge the best of both)
- Agree on acceptance criteria and quality thresholds
- Agree on what gets cut/deferred
- Ensure the plan addresses ALL gaps identified by BOTH analyses
- Include critical path diagram

**3c. Update handover:**
Write `docs/handover/HANDOVER_020_CONVERGED_PLAN.md`

### Step 4: Validate Against Architecture
Read `docs/VIZIER_ARCHITECTURE.md` (the sections listed in CLAUDE.md §2 for relevant sessions). Verify the converged plan closes the gap between what the architecture promised and what the system currently delivers. Flag any architecture promises that neither analysis addressed.

## Constraints
- Do NOT start implementation. This session is analysis and planning only.
- The converged plan must be implementable in ≤12 sessions to reach sellable output.
- Optimise for output quality, not architecture completeness.
- Every session in the final plan must have human-rated acceptance tests, not just contract tests.
- Template ingestion of 100-200 Canva/Envato references is confirmed. The plan must specify the ingestion strategy.

## Key Numbers From Analysis
| Metric | Value |
|--------|-------|
| V1 build sessions | 21 |
| Post-S21 debug sessions | 12 (~19.5 days) |
| Post-S21 sessions improving output quality | 3 of 12 |
| Exemplar table rows | 0 |
| Professional-quality templates | 0 |
| Stubs in registry.py | 14 |
| Workflows truly deliverable E2E | 2 (poster, document) |
| Tests passing | 968 (92% unit, 8% integration, 0% acceptance) |
| Datasets downloaded but not utilised | 28GB |

## Expected Output
1. Comparison table (Step 1)
2. Blind spot analysis (Step 2)
3. `docs/decisions/lessons_learned_build_plan_final.md` (merged)
4. `docs/VIZIER_BUILD_v2_final.md` (merged)
5. `docs/handover/HANDOVER_020_CONVERGED_PLAN.md`
6. Architecture gap check (Step 4)
