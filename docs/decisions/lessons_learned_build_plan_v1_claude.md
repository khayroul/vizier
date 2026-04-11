# Lessons Learned: Vizier Build Plan V1

**Date:** 2026-04-11
**Status:** Post-mortem — informs Build Plan V2
**Scope:** S0-S21 build sessions + 12 post-S21 debugging/hardening sessions (~33 total)

---

## Executive Summary

Build Plan V1 completed all 21 code sessions plus 5 integration test sessions. Every session met its stated exit criteria. 968 tests pass. The architecture is structurally sound.

**The system does not produce sellable output.**

Posters do not reach Canva free-tier floor. Children's books are not commercially viable. Ebooks lack narrative architecture. The gap is not bugs — it is sequencing. The plan built governance, observability, routing, self-improvement, and knowledge infrastructure before the rendering pipeline could produce acceptable visual output. Quality was treated as an emergent property of correct architecture. It is not. Quality is an explicit deliverable that must be front-loaded.

After S21, 12 additional sessions (~19.5 days) were spent debugging and hardening. Of those 12, only 3 improved output quality. The other 9 fixed infrastructure crashes, wiring gaps, and false capability claims — all consequences of not testing end-to-end output quality during the build.

**Total cost of the sequencing failure:** ~10 sessions of avoidable rework + 6-8 weeks of lost production runway.

---

## 1. What the Plan Assumed vs What Actually Happened

### Assumption 1: "Quality emerges from correct contracts"

**Plan assumed:** If ArtifactSpec validates correctly, PolicyEvaluator gates correctly, ReadinessResult classifies correctly, and WorkflowExecutor orchestrates correctly, output quality follows.

**What happened:** All contracts validate. All gates gate. All orchestration orchestrates. Output is mediocre. Contracts ensure structural correctness (is this a valid poster spec?), not perceptual quality (does this poster look professional?). These are orthogonal concerns.

**Evidence:** 968 tests pass. 92% are unit tests on isolated contracts. Zero tests verify "does the output look like a professional poster?" The test suite proves correctness, not quality.

### Assumption 2: "Datasets improve quality by existing"

**Plan assumed:** Downloading 28GB of datasets (D4 layouts, D5 magazines, D7 copywriting, D8 marketing, D9 trends, D12 rated posters) would fuel quality improvement through the sessions that consume them.

**What happened:** 11 of 15 datasets were downloaded. The build plan never assigned a session to transform raw data into quality-improving artifacts. S5 downloaded data; no session turned it into better templates, calibrated thresholds, or coaching patterns. The "Dataset Transformation Gap" became the #1 most-connected concept in the project's knowledge graph (11 edges across 6 documents diagnosing the same problem).

**Evidence:**
- `datasets/D4_CGL/`: 61K layouts on disk → clustered into 28 CSS grid templates (geometry only, not professional quality)
- `datasets/D12_PosterIQ/`: 3.2GB of rated posters → loader built, calibration script built, neither run against production output
- `datasets/D7_Ad_Copywriting/`: 137K records → zero transformation
- `datasets/D9_Design_Trends/`: on disk → zero transformation
- Exemplar table: 0 rows
- Knowledge cards table: 0 rows

**Root cause (from HANDOVER_017):** "Datasets teach STRUCTURE (geometry, zones), not TASTE (what good looks like for the Malaysian market)." The plan confused data acquisition with data utilisation.

### Assumption 3: "Templates are a config concern, not a quality concern"

**Plan assumed:** Templates are Ring 2 (config-driven, YAML-changeable). The template selector algorithm is the quality lever. Better selection logic → better output.

**What happened:** The selector works correctly — it scores density, tone, occasion, industry, CTA prominence, and slot compatibility. But it selects from a pool of 10 hand-crafted HTML templates and 28 D4-derived CSS grid approximations. None of these are professional-quality designs. A perfect selection algorithm choosing from a weak pool produces weak output.

**Evidence:**
- `templates/html/poster_default.html`: 103 lines, basic CSS grid, no typographic hierarchy
- `templates/html/poster_d4_hero_top_logo_00.html`: D4-derived, zone geometry only, no whitespace management
- Compare: a Canva free template has variable font sizing, optical margin alignment, colour-coordinated CTA buttons, responsive text flow. Zero Vizier templates have these properties.

### Assumption 4: "Governance before the governed"

**Plan assumed:** Building policy gates (S8), readiness evaluation (S6), quality postures (S8), and workflow validation (S9) early means the pipeline is "governed from day one."

**What happened:** Governance infrastructure was complete by S9. The thing being governed (the rendering pipeline) didn't produce acceptable output until the GPT sprint at session ~29. For 20 sessions, governance validated contracts on mediocre output — correct governance of incorrect results.

**Evidence:** PolicyEvaluator has 4 sequential gates (phase → tool → budget → cost). None evaluate "is the visual output professional?" The quality gate (`middleware/quality_gate.py`) has 6 layers, but layer 3 (visual delta comparison) references a function that was never built (`scripts.visual.calculate_delta`), and layer 5 (exemplar scoring) no-ops because the exemplar table is empty.

### Assumption 5: "Self-improvement needs to be architecturally ready"

**Plan assumed:** S19 (pattern detection, failure analysis, experiment framework, prompt versioning, drift detection) would be ready when production data arrives.

**What happened:** S19 is fully implemented. It detects patterns in production traces, runs A/B experiments on prompt versions, and measures drift against anchor sets. But there are zero production traces, zero prompt versions to compare, and zero anchor set exemplars. S19 is a factory with no raw materials.

**Evidence:** `tools/improvement.py` — fully implemented. `scripts/calibrate_nima.py` — fully implemented. Both require production data that doesn't exist. S19 should have been the last session built, not session 19 of 21.

---

## 2. Structural Anti-Patterns

### Anti-Pattern 1: Architecture-Forward, Output-Last

**Description:** The build plan sequenced sessions by architectural layer (contracts → routing → policy → data foundation → knowledge → rendering → self-improvement) instead of by output quality dependency (templates → rendering → scoring → acceptance → governance).

**Cost:** S6 (contracts), S7 (spans), S8 (policy), S10a (tables), S18 (knowledge spine), S19 (self-improvement) — 6 sessions of infrastructure that doesn't improve output quality. These are all valuable long-term but were built before the system could produce a single good poster.

**Heuristic:** Build from output backwards. Start with "what does a good poster look like?" and work backwards to "what infrastructure do I need to produce that?" Not "what architecture is elegant?" forward to "surely output follows."

### Anti-Pattern 2: Dataset Acquisition ≠ Dataset Utilisation

**Description:** S5 downloaded datasets. No session was assigned to transform them into quality-improving artifacts (better templates, calibrated thresholds, coaching patterns, exemplar libraries). The plan treated downloading as the deliverable.

**Cost:** 1 session (S5) + 28GB storage + the ongoing illusion of data-driven quality. The Dataset Transformation Gap was diagnosed 3 separate times across 3 documents before any fix was attempted. Anti-drift rules #58, #59, #60 were created specifically to prevent this recurrence.

**Heuristic:** Every dataset entry in a build plan must have three columns: (1) session that acquires, (2) session that transforms into a committed artifact, (3) test proving the artifact is consumed at runtime. If column 2 or 3 is blank, the dataset is dead weight.

### Anti-Pattern 3: Testing Correctness Instead of Quality

**Description:** 968 tests verify that contracts validate, routes resolve, policies evaluate, and workflows execute. Zero tests verify that output looks professional to a human.

**Cost:** False confidence. Every session's exit criteria said "N tests pass." All sessions passed. The system was "correct" at every checkpoint and "mediocre" at final delivery. Tests measured the wrong thing.

**Heuristic:** Every pipeline session must include at least one acceptance test that a human evaluates. "Generate 5 posters, operator rates ≥3 as Canva-floor" is a valid exit criterion. "52 contract tests pass" is not sufficient.

### Anti-Pattern 4: Stubs as Promises

**Description:** `tools/registry.py` has 14 explicit stubs. Workflow YAMLs reference tools that don't exist. `_DELIVERABLE_WORKFLOWS` claimed more workflows worked than actually did (HANDOVER_014 finding: "support matrix overstated").

**Cost:** 2 sessions (CT-014, CT-015) spent discovering that claimed capabilities were stubs. Trust erosion between build plan and reality. The operator believed the system could produce invoices, proposals, and company profiles — it cannot.

**Heuristic:** Stubs must be phase-gated in the workflow registry. A workflow with any stub dependency is excluded from `_DELIVERABLE_WORKFLOWS`. Never advertise stub capability as available. Test deliverability end-to-end, not structurally.

### Anti-Pattern 5: Reactive Debugging Spiral

**Description:** Post-S21 debugging followed a cascade pattern. CT-008 found 7 bugs. CT-009 fixed those but found 3 more. CT-011 found P0s CT-009 missed. CT-012 found deployment gaps CT-011 didn't test. Each session peeled back one layer without comprehensive coverage.

**Cost:** 9 sessions (11.5 days) of infrastructure fixes that a single comprehensive hardening session could have found. Each session lacked the test coverage to find all issues at once, so each fix revealed the next unfixed layer.

**Heuristic:** Before declaring a pipeline "complete," run one comprehensive hardening session: generate 20+ outputs end-to-end, test every integration point, verify every claimed capability. Find all layers of bugs at once, not one layer per session.

### Anti-Pattern 6: Audits That Don't Ship Code

**Description:** CT-010 (Hermes audit), CT-014 (track review), CT-015 (review findings), CT-016 (quality floor audit), CT-017 (quality intelligence design) — 5 sessions that documented problems without fixing them in-session.

**Cost:** 5 sessions (~5 days) of diagnosis without treatment. Each produced a handover document describing gaps, deferring fixes to a future session. The gaps accumulated faster than they were closed.

**Heuristic:** Every audit session must ship fixes, not just findings. If the audit surfaces 10 issues, the session exit criteria must include "top 5 fixed, remaining 5 triaged with owner and session." An audit that only documents is a half-session.

### Anti-Pattern 7: Parallel Sessions Without Integration Contracts

**Description:** Sessions S6-S13 were designed to run in parallel blocks. S11 and S12 both implemented `retrieve_similar_exemplars()`. S5 and S6 both created config files. S8 was marked merged in a handover but was actually still on a branch.

**Cost:** Schema drift became the #1 recurring bug class (27% of all bugs per HANDOVER_007). DEV-006: S13 recreated config files S5 should have created. DEV-011: S8 was discovered unmerged during integration testing. Parallel sessions without shared integration contracts produce merge conflicts and drift.

**Heuristic:** For parallel sessions: (1) define stub files with exact function signatures in S0, (2) each session edits only its assigned functions, (3) run a merge-and-smoke-test session between every parallel block — not after the full build.

---

## 3. The Post-S21 Tax — Session-by-Session

| # | Session | Days | What It Fixed | Output Quality? | Could Have Been Prevented By |
|---|---------|------|--------------|----------------|------------------------------|
| 1 | CT-008 | 1.0 | Namespace collision, stage clobbering, prompt loss, FLUX text, raw HTML errors | ❌ | End-to-end integration test in S9 |
| 2 | CT-009 | 0.5 | Playwright renderer, FLUX text fix, intelligence plumbing | ✅ | Should have been in S13 (visual pipeline session) |
| 3 | CT-010 | 1.0 | Hermes integration audit (no code shipped) | ❌ | Hermes integration should have been tested during S14 |
| 4 | CT-011 | 1.5 | Bridge hardening, parallel guardrails wiring, P0-P2 triage | ❌ | Guardrails should have been wired when built in S9 |
| 5 | CT-012 | 1.0 | Root cause analysis, deployment gap identification | ❌ | Deployment testing should have been in S0 scaffold |
| 6 | CT-013 | 1.5 | 12 deployment boundary tests, import parity | ❌ | Tests should have been written with the scripts |
| 7 | CT-014 | 1.0 | Support matrix truthfulness, deliverable whitelist correction | ❌ | Deliverability should have been tested, not declared |
| 8 | CT-015 | 1.0 | Rework pipeline blocked, family_resolved unenforced | ❌ | Integration test for rework flow in S9 |
| 9 | CT-016 | 1.0 | Quality floor audit, posture alias broken | ❌ | Quality posture should have been acceptance-tested |
| 10 | CT-017 | 1.0 | Quality intelligence design (no code shipped) | ❌ | Quality design should have preceded S6, not followed S21 |
| 11 | GPT Sprint | 7.0 | flux-pro default, coaching, auto-enrich, UUID fix, policy audit, 39 structural fixes | ✅ | Front-loading rendering quality + acceptance tests |
| 12 | GPT Final | 0.5 | Consolidation, 884→968 tests | ✅ | N/A — consolidation is inherently late-stage |
| | **TOTAL** | **19.5** | | **3 of 12** | |

**Avoidable sessions:** 8 of 12 (CT-008, CT-010 through CT-016) — ~9 days
**Unavoidable but mis-sequenced:** 1 (CT-009 should have been in S13)
**Genuinely late-stage:** 3 (GPT Sprint, GPT Final, CT-017 design)

---

## 4. Concrete Heuristics for Future Build Plans

These heuristics are derived from Vizier V1 failures. They apply to any system where the primary deliverable is generated artifacts (documents, images, media) rather than CRUD/API software.

### H1: Output-First Sequencing
**Rule:** The first 3 sessions of any generative system must produce end-to-end output that a human evaluates. No governance, no observability, no self-improvement until the pipeline generates something worth governing.

**Rationale:** Vizier spent 9 sessions (S0-S9) before producing a single poster. By that point, the governance architecture was locked in, but nobody knew if the poster looked good. Changing rendering after governance is expensive; changing governance after rendering is cheap.

### H2: Professional Assets Before Selection Logic
**Rule:** Template/asset ingestion must precede template selection logic. You cannot build a recommendation engine for an empty catalogue.

**Rationale:** S11 built template selector scoring (density, tone, occasion, industry, CTA). S1 built design system selection. Both scored against 10 basic HTML templates. The algorithm was correct; the pool was weak. Building selection before ingestion wasted the algorithm's capability.

### H3: Exemplar Baseline Before Quality Gates
**Rule:** No quality scoring session until the exemplar table has ≥30 entries from professional reference material.

**Rationale:** S13 built 4-dimensional critique (composition, typography, colour, layout). With 0 exemplars, the critique asks GPT-5.4-mini "is this good?" against general knowledge. With 50 exemplars, the critique asks "is this as good as these specific professional examples?" The second question is answerable; the first is not.

### H4: Acceptance Tests With Human Rating
**Rule:** Every pipeline session must include an acceptance test where a human rates ≥5 generated outputs. Exit criteria: ≥60% rated "acceptable or better."

**Rationale:** Every V1 session's exit criteria was "N tests pass." All passed. Output was mediocre. Automated tests caught structural failures but not perceptual quality failures. A 30-second human look at 5 outputs would have caught the quality gap at session 4, not session 33.

### H5: One Comprehensive Hardening Session, Not Twelve Incremental Ones
**Rule:** Before declaring a milestone complete, run one full hardening session: generate 20+ outputs end-to-end, test every integration point, verify every claimed capability. Budget 2 days.

**Rationale:** 12 post-S21 sessions each found one layer of bugs. A single comprehensive session with broad test coverage would have found them all at once. Cascading debug sessions cost 19.5 days; one hardening session would have cost 2.

### H6: Audits Must Ship Fixes
**Rule:** An audit session's exit criteria must include "top N issues fixed in-session." Pure-documentation sessions are capped at 0.5 days; remaining time is for fixes.

**Rationale:** 5 of 12 post-S21 sessions were audits that produced handover documents without fixing what they found. Each deferred fix accumulated interest as a future session.

### H7: Dataset Pipeline, Not Dataset Download
**Rule:** Every dataset in the build plan must have three assigned sessions: (1) acquire, (2) transform into committed artifact, (3) verify artifact is consumed at runtime. If sessions 2 and 3 are blank, remove the dataset from the plan.

**Rationale:** S5 downloaded 28GB. Zero bytes improved output by S21. Three subsequent documents diagnosed the gap. Anti-drift rules #58-#60 were created to prevent recurrence. The fix should have been in the plan, not in the anti-drift rules.

### H8: Stubs Are Phase-Gated, Never Advertised
**Rule:** Any workflow with a stub dependency is excluded from the deliverable set. Test deliverability end-to-end, not structurally. The workflow registry must enforce this programmatically.

**Rationale:** HANDOVER_014 discovered that invoice, proposal, and company_profile were listed as deliverable but depended on S16 stubs. The operator believed they worked. Trust erosion is expensive.

### H9: Integration Smoke Tests Between Parallel Blocks
**Rule:** After every block of parallel sessions merges to main, run a 15-minute smoke test before launching the next block. Test imports, test E2E on each deliverable workflow, verify no schema drift.

**Rationale:** S8 was marked merged but was actually on a branch (DEV-011). This was discovered during integration testing, not at merge time. A smoke test after Block 3 merge would have caught it in minutes.

### H10: Quality Design Precedes Architecture Design
**Rule:** Before designing the architecture of a generative system, define: (1) what "good output" looks like with 10 concrete examples, (2) what makes output unacceptable with 10 concrete anti-examples, (3) the minimum quality floor with measurable criteria. The architecture serves these definitions, not the reverse.

**Rationale:** Vizier's architecture document (§0-§43) defines 57 anti-drift rules, 16 workflow packs, 37 database tables, 7 governance layers, and 4 quality postures. It does not contain a single example of what a good poster looks like. The architecture is internally consistent and externally disconnected from quality.

---

## 5. Alternative Sequencing — What V1 Should Have Been

### V1 Actual Sequence (Architecture-Forward)
```
S0 Scaffold → S1 Config → S2 Typst → S4 Endpoints → S5 Datasets → S6 Contracts →
S7 Spans → S8 Policy → S9 Workflows → S10a Tables → S11 Routing → S12 Research →
S13 Visual Intel → S15 Publishing → S16 BizOps → S17 Dashboard → S18 Knowledge →
S19 Self-Improvement → S21 Extended Lanes
→ 12 post-S21 debugging sessions (19.5 days)
→ Quality gap still open
```

### V1 Optimal Sequence (Output-Forward)
```
Phase 1 — Output Foundation (Sessions 1-4):
  S-T1: Ingest professional templates (Canva/Envato)
  S-T2: Template-aware rendering (typography, dynamic sizing, CTA)
  S-E1: Exemplar seeding (top outputs → exemplar table, NIMA calibrate)
  S-E2: Exemplar-anchored QA (rejection + regeneration)

Phase 2 — Pipeline Hardening (Sessions 5-6):
  S-H1: End-to-end acceptance (50 posters, 10 books, human-rated)
  S-H2: Fix top 10 failure modes from acceptance testing

Phase 3 — Second Pipeline (Sessions 7-8):
  S-B1: Children's book creative foundation (story_workshop, scaffold_build)
  S-B2: Page composition + character consistency

Phase 4 — Governance + Infrastructure (Sessions 9-12):
  S-G1: Contracts + readiness + policy (S6 + S8 merged)
  S-G2: Routing + workflow executor (S9 + S11 merged)
  S-G3: Data foundation + knowledge (S10a + S18 merged)
  S-G4: Observability + self-improvement (S7 + S19 merged)

Phase 5 — Extensions (Sessions 13+):
  S-X1: BizOps + Steward (S16)
  S-X2: Dashboard (S17)
  S-X3: Extended workflows (S21)
```

**Key differences:**
- Professional templates arrive in session 1, not "eventually"
- Human-rated acceptance testing happens in session 5, not session 33
- Governance builds atop a working pipeline, not atop stubs
- Children's book pipeline gets real tools (story_workshop, scaffold_build), not stubs
- Self-improvement is last because it needs production data
- Total sessions to sellable output: 8 (vs 33 in V1)

---

## 6. Applicability to Future Systems

This post-mortem applies to any system where:
- The primary deliverable is generated artifacts (not CRUD/API endpoints)
- Quality is perceptual (looks good, reads well) not just structural (validates, responds)
- The system has a quality-scoring layer (NIMA, critique, rubrics)
- Multiple pipelines share infrastructure (routing, governance, storage)

**The core lesson:** In generative systems, the pipeline IS the product. Everything else (governance, observability, self-improvement, knowledge retrieval) is support infrastructure. Build the product first. Add support when the product deserves it.

**The cost equation:** Every session spent on support infrastructure before the pipeline produces acceptable output is a session that (a) can't be tested against real quality criteria, (b) may need rework when quality requirements clarify, and (c) delays the feedback loop that makes everything else useful.

---

## Appendix: Source Evidence

| Claim | Source File |
|-------|-------------|
| 14 explicit stubs in registry | `tools/registry.py:2669-2687` |
| Exemplar table has 0 rows | HANDOVER_016, verified via DB query |
| NIMA thresholds were hardcoded until quality intelligence session | `tools/visual_scoring.py` (pre-fix), `config/quality_frameworks/nima_thresholds.yaml` (post-fix) |
| Visual delta comparison never built | `middleware/quality_gate.py` (lazy import, function missing) |
| story_workshop is a stub | `tools/registry.py` line 2672 |
| scaffold_build is a stub | `tools/registry.py` line 2673 |
| S8 never merged (DEV-011) | `docs/handover/HANDOVER_003.md` |
| Support matrix overstated | `docs/handover/HANDOVER_014_TRACK1_TRACK2_STOP_POINT.md` |
| Dataset Transformation Gap — god node, 11 edges | `graphify-out/graph.json` |
| Schema drift is #1 bug class (27%) | `docs/handover/HANDOVER_007.md` |
| 968 tests, 92% unit, 8% integration | Test suite run 2026-04-11 |
| 12 post-S21 sessions, 19.5 days | HANDOVER_008 through HANDOVER_017 + GPT sprint docs |
| 3 of 12 post-S21 sessions improved output quality | Analysis of each session's deliverables |
