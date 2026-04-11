# Successor Prompt — Adversarial Merge Session: Claude vs Codex Quality-Gap Analysis

## Context

Two parallel analyses now exist on why Vizier failed to reach the architecture promise by S21. They overlap, but they also emphasize different failure modes and may each miss things the other caught.

Your job is not to pick one. Your job is to compare them adversarially, validate disputed claims against the repo, surface overlooked items, and merge them into one stronger canonical analysis plus one stronger gap-closing plan.

**Important:**
- Preserve both originals. Do not overwrite source files.
- Treat this as an analysis + reconciliation session first, not an implementation session.
- Check relevant repo code and tests, not just docs.
- Optimize for truth, not diplomacy.

---

## Primary Inputs — Read All 7 Files

### Claude's Analysis
1. `docs/decisions/lessons_learned_build_plan_v1.md` — Post-mortem: 5 false assumptions, 7 structural anti-patterns, 10 heuristics for future systems, session-by-session post-S21 tax breakdown (12 sessions, 19.5 days, 75% infra-only)
2. `docs/VIZIER_BUILD_v2.md` — Revised 8-session plan: S-T1 template ingestion → S-T2 rendering → S-E1 exemplar seeding → S-E2 anchored QA → S-B1 story architecture → S-B2 page composition → S-I1 acceptance testing → S-I2 governance wiring. Includes template ingestion metadata schema, critical path, acceptance criteria, anti-drift rules #61-#65
3. `docs/handover/HANDOVER_019_QUALITY_GAP_ANALYSIS.md` — Session handover with key numbers and merge instructions

### Codex's Analysis
4. `docs/decisions/lessons_learned_build_plan_v1_codex.md` — Codex's lessons learned (416 lines — may surface different anti-patterns or evidence)
5. `docs/QUALITY_GAP_ANALYSIS_S21.md` — Codex's gap analysis
6. `docs/VIZIER_BUILD_quality_first_v1.md` — Codex's revised build plan
7. `docs/handover/HANDOVER_018_SUCCESSOR_POST_S21_GAP_AND_RECOVERY.md` — Codex's handover

### Supporting Context To Re-check
- All relevant `docs/handover/HANDOVER_*.md`
- `docs/HANDOVER_SPRINT_GPT.md`
- `docs/HANDOVER_SPRINT_GPT_FINAL.md`
- `docs/decisions/*.md`
- `docs/VIZIER_BUILD_v1_3_1.md`
- `docs/VIZIER_ARCHITECTURE.md` — The original architecture document (what was promised)
- `CLAUDE.md` — Current navigation map, shared interfaces, anti-drift rules

### Pre-Built Knowledge Graph
A graphify knowledge graph was already built on the handover + decision corpus during the Claude analysis session. **Do not re-run `/graphify` from scratch — use the existing graph:**
- `graphify-out/graph.html` — Interactive visualization (198 nodes, 205 edges, 25 communities). Open in browser.
- `graphify-out/graph.json` — Raw graph data. Use `/graphify query "<question>"` to traverse.
- `graphify-out/GRAPH_REPORT.md` — God nodes, surprising connections, community labels.

If you need to add the Codex documents to the graph, use `/graphify --update` on the new files only.

---

## Required Method

1. Read both Claude and Codex lessons-learned docs line by line.
2. Build a comparison table (see Step 1 below).
3. Verify disputed or high-impact claims in current repo code, config, workflow registry, and tests. Do not trust docs alone.
4. Use the graphify graph to surface repeated failure clusters, disconnected capability clusters, and "built but not consumed" patterns.
5. Identify what each analysis overlooked.
6. Merge the strongest parts of both into one canonical post-mortem and one canonical gap-closing plan.

### What To Look For Specifically
- Where the original build plan optimized for architecture completeness instead of output quality
- Where sessions built dead code, dormant infra, or premature abstractions
- Where datasets were acquired/extracted but not transformed into runtime value
- Where governance/routing/testing were built before worthwhile artifact lanes existed
- Where support/deliverability truth drifted from actual runtime capability
- What the post-S21 hardening sessions fixed structurally vs what they fixed in output quality
- What still blocks "sellable output by proof"
- What either Claude or Codex analysis underweighted or overstated

---

## Task

### Step 1: Adversarial Comparison Table
Read all 7 documents. For each major finding, classify:

```
| Finding | Claude | Codex | Classification | Repo Verified? |
|---------|--------|-------|----------------|----------------|
| ...     | ✅/❌  | ✅/❌ | Consensus / Claude-only / Codex-only / Conflict | Yes/No/Pending |
```

- **Consensus** = both identified it (high confidence)
- **Claude-only** = Codex missed this (gap in Codex analysis)
- **Codex-only** = Claude missed this (gap in Claude analysis)
- **Conflict** = they disagree (needs repo verification to resolve)

### Step 2: Repo Verification
For every disputed or high-impact claim, check the actual code:
- Is the stub really a stub? Check `tools/registry.py` line numbers.
- Is the quality gate really ceremonial? Check `middleware/quality_gate.py`, `tools/visual_scoring.py`.
- Is the exemplar table really empty? Check the DB or the seeding scripts.
- Are the post-S21 session counts accurate? Cross-reference handover docs.
- Does the template selector really have no professional templates? Check `templates/html/*_meta.yaml`.

### Step 3: Identify Blind Spots
What did each analysis miss?
- Claude focused on: post-S21 session breakdown, graphify structural patterns, heuristics for future systems, template metadata schema
- Codex focused on: (determine from reading)
- Neither covered: (identify — these are the most dangerous gaps)

### Step 4: Produce Merged Deliverables

**Do NOT use filenames from either original analysis. Use new merged filenames.**

---

## Deliverable 1: Canonical Merged Lessons Learned

Create: `docs/decisions/lessons_learned_build_plan_v1_merged.md`

Must include:
- The strongest root-cause diagnosis from both versions
- Explicit "what Claude caught that Codex underplayed"
- Explicit "what Codex caught that Claude underplayed"
- A merged anti-pattern list (deduplicated, keep the better-evidenced version)
- A merged heuristic list for future build plans
- Concrete cost-of-sequencing estimates
- A clear statement of why S21 missed the architecture promise
- Source evidence appendix with repo file paths

## Deliverable 2: Canonical Merged Gap-Closing Plan

Create: `docs/VIZIER_BUILD_gap_closure_merged.md`

Must:
- Merge the best parts of `VIZIER_BUILD_quality_first_v1.md` and `VIZIER_BUILD_v2.md`
- Distinguish:
  - **Immediate closures** on current `main` (quick wins, config fixes)
  - **Short build-plan corrections** (the core sessions to sellable output)
  - **Longer post-launch improvements** (governance, self-improvement, extensions)
- Prioritize output quality and proof over architecture expansion
- Explicitly sequence:
  - Poster quality floor
  - Template/taste ingestion (100-200 Canva/Envato references confirmed)
  - Adaptive brief rescue (coaching system)
  - Calibrated QA (exemplar-anchored gates)
  - Governed acceptance proof (human-rated acceptance tests)
  - Book/ebook truth reconciliation (stub replacement, character consistency)
- Include critical path diagram
- Every session has human-rated acceptance tests, not just contract tests
- Implementable in ≤12 sessions to reach sellable output

### Template Ingestion Decision
Both plans address 100-200 Canva/Envato templates. Reconcile and decide:
- Grouping model (by archetype? by source? by artifact type?)
- Metadata schema
- How references influence template selection, prompting, QA, and exemplar matching
- Whether templates from the same source should be grouped separately

Claude's recommendation: `artifact_type → layout_archetype → niche/use_case`, not by source.
Codex's recommendation: (determine from reading)
Pick the better one or merge.

## Deliverable 3: Adversarial Findings Memo

Create: `docs/decisions/analysis_diff_claude_vs_codex.md`

Compact memo covering:
- Overlap summary
- Disagreements and how each was resolved
- Overlooked items surfaced during merge
- Final judgment on which claims survived repo verification
- Recommended canonical files going forward (so future sessions know which docs are authoritative)

---

## Validate Against Architecture

Read `docs/VIZIER_ARCHITECTURE.md` (sections listed in CLAUDE.md §2 for relevant sessions). Verify the converged plan closes the gap between what the architecture promised and what the system currently delivers. Flag any architecture promises that neither analysis addressed.

---

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
| D4 templates generated (CSS grid, not professional) | 28 |
| Hand-crafted HTML templates | 10 |
| Knowledge cards ingested | 0 |
| Children's book stubs (story_workshop, scaffold_build) | 2 critical |
| Quality gates that materially improve output | 2 of 8 |

---

## Constraints
- Do NOT start implementation. This session is analysis and planning only.
- Do NOT overwrite the original Claude or Codex files.
- Do NOT hand-wave with "needs more wiring" — name exact missing links with file paths.
- Cite exact repo files where possible.
- Do not implement product code unless a tiny fix is required to validate a claim.
- Optimize for truth, not diplomacy.

## Success Criteria
1. There is one stronger canonical post-mortem (`lessons_learned_build_plan_v1_merged.md`).
2. There is one stronger canonical gap-closing plan (`VIZIER_BUILD_gap_closure_merged.md`).
3. The differences between Claude and Codex are made explicit (`analysis_diff_claude_vs_codex.md`).
4. Overlooked items are surfaced, not silently merged away.
5. Disputed claims are verified against repo code, not just accepted from docs.
6. The result is usable as the new source of truth for closing the quality gap.

## Expected Output
1. Adversarial comparison table
2. Repo verification of disputed claims
3. Blind spot analysis
4. `docs/decisions/lessons_learned_build_plan_v1_merged.md`
5. `docs/VIZIER_BUILD_gap_closure_merged.md`
6. `docs/decisions/analysis_diff_claude_vs_codex.md`
7. Architecture gap check
8. `docs/handover/HANDOVER_020_CONVERGED_PLAN.md`
