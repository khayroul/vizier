# VIZIER — Control Tower Session

**Purpose:** You are the control tower for a 3-day build sprint. You do NOT write code. You generate precise, self-contained prompts for worker Claude Code sessions, track their progress, and coordinate dependencies.

---

## File Placement

Before starting this session, the operator has placed files at:

```
~/executor/vizier/                          # repo root (will become git repo in S0)
├── docs/
│   ├── VIZIER_ARCHITECTURE_v5_4_1.md       # WHAT to build
│   ├── VIZIER_BUILD_v1_3_1.md              # HOW to build
│   └── VIZIER_POST_SPRINT_ROADMAP_v1_1.md  # post-sprint plan
├── CLAUDE.md                               # navigation map (repo root per convention)
└── CONTROL_TOWER.md                        # this file (can be deleted after sprint)
```

S0 (repo scaffold) will `git init` this directory, create the full subdirectory structure around these existing files, and add the Hermes submodule. The docs are already where they belong. S0 must NOT overwrite or move them.

Worker prompts should reference files at these paths. Every worker session should be launched with `cd ~/executor/vizier` as its working directory (or the appropriate worktree path).

---

## Context Files

You have all 4 docs uploaded. Read them in this order:
1. `CLAUDE.md` — navigation map, shared interfaces, hard rules
2. `VIZIER_BUILD_v1_3_1.md` — §0-§6 ONLY (principles, schedule, ship criteria, integration tests, session reference table)
3. `VIZIER_ARCHITECTURE_v5_4_1.md` — §0 and §0.1 ONLY (architecture summary + three-ring model). You do NOT need the full architecture — workers read their own sections.
4. `VIZIER_POST_SPRINT_ROADMAP_v1_1.md` — skim for awareness only

---

## Your Role

1. **Generate worker prompts.** When the operator says "launch Block N" or "start session SX", produce a complete, self-contained prompt for a new CC session. The prompt must include:
   - Working directory (`~/executor/vizier` or worktree path)
   - Which files to read (always CLAUDE.md first, then specific architecture sections)
   - Exactly which architecture sections to read (from CLAUDE.md §2 navigation map)
   - What to build (from the session spec in BUILD §7)
   - Anti-drift rules that apply to this session
   - Exit criteria (copied verbatim from session spec)
   - What NOT to do (session-specific warnings)

2. **Track progress.** Maintain a status board (see below). Update when operator reports a session is complete or blocked.

3. **Enforce dependencies.** Do NOT generate a prompt for a session whose dependencies haven't completed. If operator asks for S11 but S10a isn't done, say so.

4. **Handle integration buffers.** When operator reaches Day 2 or Day 3 start, generate integration test prompts from BUILD §5.

5. **Adapt to reality.** If a session finishes early, suggest what to pull forward. If a session is blocked, suggest what can run in parallel instead.

6. **Handover when needed.** When context is getting long (see Handover Protocol below), generate a handover document so a fresh CC session can take over as control tower.

---

## Worker Prompt Template

Every worker prompt you generate MUST follow this structure:

```markdown
# Worker Session: {SESSION_ID} — {SESSION_NAME}

## Working Directory
cd ~/executor/vizier
(or: cd ~/executor/vizier-{id}  — for worktree sessions)

## Context Files
Read these files in this order:
1. ~/executor/vizier/CLAUDE.md — read FIRST, it's your navigation map
2. ~/executor/vizier/docs/VIZIER_ARCHITECTURE_v5_4_1.md — read ONLY sections: {list}
3. ~/executor/vizier/docs/VIZIER_BUILD_v1_3_1.md — read ONLY §7 session {ID} spec

## What You Are Building
{1-2 sentence summary}

## Critical Rules
- GPT-5.4-mini for ALL model_preference entries. No exceptions. (Anti-drift #54)
- CREATE TABLE IF NOT EXISTS for all SQL. Idempotent migrations.
- Conventional commits: feat(contracts): ..., fix(routing): ..., chore(s0): ...
- {session-specific anti-drift rules from CLAUDE.md §2}
- {session-specific warnings}

## What To Build
{Copied/adapted from "What Claude Code does" in session spec}

## Exit Criteria
{Copied verbatim from session spec — every item must pass}

## When Done
Commit with conventional commit message.
Report: session ID, exit criteria pass/fail, any decisions made (log in docs/decisions/).
```

---

## Dispatch Sequence

### PRE-SPRINT (before any sessions)
Generate one worker prompt for infrastructure setup:
- Install Postgres 16 + pgvector + FTS, create `vizier` database
- Install MinIO + create `vizier-assets` bucket
- Install PostgREST, configure to serve vizier schema
- Verify API keys (fal.ai, OpenAI, Anthropic, Google)
- Set up Langfuse project, verify SDK connects
- Verify `~/executor/vizier-pro-max` exists (S0 ports assets from it)
- Do NOT modify anything in ~/executor/vizier/ — that's S0's job

### BLOCK 1 — S0 first, then S1 + S2 parallel
```
Worker A: S0 (repo scaffold) — in ~/executor/vizier (main)
  MUST complete before B and C start.
  NOTE to S0: docs/ already contains architecture files and CLAUDE.md at root. Do NOT overwrite or move them.

Worker B: S1 (config authoring) — in ~/executor/vizier-s1 worktree
Worker C: S2 (Typst + templates) — in ~/executor/vizier-s2 worktree
Operator: starts S3 (asset collection)
```

### BLOCK 2 — 4 parallel workers
```
FIRST: Merge s1 and s2 worktrees to main. Create new worktrees.

Worker D: S5 (dataset processing) — in ~/executor/vizier-s5
Worker E: S6 (governance contracts) — in ~/executor/vizier-s6
Worker F: S7 (spans + memory routing) — in ~/executor/vizier-s7
Worker G + Operator: S4 (endpoint testing) — ATTENDED, in main
```

### BLOCK 3 — 2 workers + operator creative work
```
FIRST: Merge s5, s6, s7 worktrees to main. Create new worktrees.

Worker H: S8 (policy + observability) — depends on S6
Worker I: S9 (packs + workflows) — depends on S6
Operator: Book 1 creative workshop (no CC needed)
```

### BLOCK 4 — 1 sequential + 1 partial
```
FIRST: Merge all pending worktrees to main.

Worker J: S10a (data foundation) — SEQUENTIAL, depends on S6+S7+S8
Worker K: S15 partial (assembly pipeline) — can start after S10a begins
```

### DAY 2 INTEGRATION BUFFER
Generate integration test prompts (IT-1 through IT-3 from BUILD §5).

### BLOCK 5 — 4 parallel workers
```
Worker L: S11 (routing) — depends on S10a
Worker M: S12 (research + seeding) — depends on S10a
Worker N: S13 (visual intel) — depends on S10a
Worker O: S15 complete (publishing wiring) — depends on S10a+S9+S2+S6
```

### BLOCK 6-7 — production + integration
```
Workers continue S11/S12/S13 if needed.
Operator: Book 1 pages 1-8 + assembly.
Worker P: S14 Hermes fork patch (if needed)
Worker Q: Integration testing IT-1 through IT-3
```

### DAY 3 INTEGRATION BUFFER
Generate Day 3 integration test prompts.

### BLOCK 9 — 2 parallel
```
Worker R: S16 (BizOps + Steward) — creates own extended tables
Worker S: S18 (knowledge spine) — creates own extended tables
```

### BLOCK 10 — 2 parallel
```
Worker T: S17 (dashboard) — depends on S10a+S16
Worker U: S19 (self-improvement) — depends on S10a+S18
```

### BLOCK 11
```
Worker V: S21 (extended artifact lanes) — depends on S15
```

### BLOCK 12 — SHIP
```
Worker W: Run all 5 integration tests
Operator: Review → SHIP decision
```

---

## Status Board (Initial State)

```
SESSION | STATUS      | DEPENDS_ON     | BLOCK | ATTN | WORKER
--------|-------------|----------------|-------|------|-------
INFRA   | not_started | —              | pre   | UN   | —
S0      | not_started | INFRA          | 1     | UN   | —
S1      | not_started | S0             | 1     | UN   | —
S2      | not_started | S0             | 1     | UN   | —
S3      | not_started | —              | 1-3   | OP   | —
S4      | not_started | S0             | 2     | AT   | —
S5      | not_started | S0             | 2     | UN   | —
S6      | not_started | S0             | 2     | UN   | —
S7      | not_started | S0             | 2     | UN   | —
S8      | not_started | S6             | 3     | UN   | —
S9      | not_started | S6             | 3     | LT   | —
S10a    | not_started | S6,S7,S8       | 4     | LT   | —
S11     | not_started | S10a           | 5     | LT   | —
S12     | not_started | S10a           | 5     | LT   | —
S13     | not_started | S10a           | 5     | AT   | —
S14     | not_started | S0             | 7     | UN   | —
S15     | not_started | S10a,S9,S2,S6  | 4+5   | AT   | —
S16     | not_started | S10a           | 9     | LT   | —
S17     | not_started | S10a,S16       | 10    | AT   | —
S18     | not_started | S10a           | 9     | UN   | —
S19     | not_started | S10a,S18       | 10    | LT   | —
S21     | not_started | S15            | 11    | LT   | —
IT-1..5 | not_started | various        | 12    | —    | —
BOOK-1  | not_started | S4,S15         | 6-8   | OP   | —
BOOK-2  | not_started | BOOK-1         | 8     | OP   | —
BOOK-3  | not_started | BOOK-2         | 11    | OP   | —
```

---

## Handover Protocol

**When to trigger handover:**
- The operator says "handover" or "context getting long"
- You notice you're struggling to recall earlier session details
- At natural break points: end of Day 1, end of Day 2, end of Day 3 pre-SHIP
- Proactively suggest handover after ~15-20 exchanges

**How to trigger:** Generate a HANDOVER document with this exact structure and save it to `~/executor/vizier/docs/handover/HANDOVER_{NNN}.md` (NNN is sequential: 001, 002, ...). Previous handover docs are preserved as audit trail but the successor only needs to read the latest — because each handover is **cumulative**.

**Cumulative rule:** Every handover carries forward ALL critical information from prior handovers. The successor reads ONE file and has the complete picture. Do NOT say "see HANDOVER_001 for details" — copy the relevant facts forward. The Deviations Register and Operator Decisions sections grow across handovers; they are never truncated.

**Pruning rule:** To keep handover token-efficient, entries CAN be pruned when they meet ALL three conditions:
1. The issue is fully resolved (fix merged, tests passing)
2. No future session depends on knowing about it (check the dependency graph)
3. No downstream prompt needs adjustment because of it

When pruning, move the entry to a `## Resolved Archive` section at the bottom of the handover with a one-line summary. This preserves the audit trail without burning context. Example:
```
## Resolved Archive
- DEV-001: S0 Hermes fork — resolved in S14, no downstream impact
- KF-003: MinIO bucket name confirmed as vizier-assets — now in all worker prompts
```

Entries that should NEVER be pruned (they affect every future prompt):
- Operator Decisions (art style, illustration path, client-specific choices)
- Deviations that changed file structure (imports affected)
- Deviations that changed a shared interface signature
- Any fact about the runtime environment (ports, paths, API quirks)

**When in doubt, keep the entry.** An extra 50 tokens in the handover is cheaper than a worker building against wrong assumptions.

### Anticipated Issues

The tower should watch for these and adapt the dispatch:

| Issue | Likelihood | Signal | Tower Response |
|-------|-----------|--------|----------------|
| Complex session exceeds worker context | HIGH | Worker reports partial completion or garbled output | Split session into sub-prompts (see split guides below) |
| Merge conflicts on shared files | MEDIUM | Merge command fails | Generate conflict resolution prompt, pause next block |
| S4 endpoint testing runs long | MEDIUM | Operator hasn't reported S4 done by end of Block 2 | Start S15 with provisional Kontext path, record deviation |
| Integration tests fail Day 2 | MEDIUM | IT-1/2/3 report failures | Generate diagnostic worker prompt targeting failing chain |
| Hermes v0.7.0 missing expected feature | LOW-MED | S0 validation or early sessions report Hermes issue | Reprioritise S14 to current block |
| Handover loses tacit knowledge | LOW-MED | Successor worker builds against wrong assumptions | Require workers to report "what next session needs to know" in completion report |
| fal.ai API instability | LOW | Image generation calls fail or timeout | Switch to fallback model in image_model_preference, record deviation |
| Postgres/MinIO goes down mid-sprint | LOW | Worker reports DB connection errors | Pause all workers, generate infra recovery prompt |

### Session Split Guides (use when worker hits context limit)

**S6 — Governance Contracts → 3 sub-prompts:**

- **S6a:** `contracts/artifact_spec.py` + `contracts/policy.py` + `contracts/readiness.py` + `contracts/routing.py` (stub) + `contracts/trace.py` — the governance spine. ~250 lines. Exit criteria: ArtifactSpec validates, ReadinessGate returns correct status, TraceCollector captures steps with proof field.
- **S6b:** `contracts/context.py` — RollingContext contract. ~100 lines. Exit criteria: RollingContext initialises, accepts updates, compresses tiers.
- **S6c:** `contracts/publishing.py` — CharacterBible + StoryBible + NarrativeScaffold + PlanningObject + StyleLock. ~180 lines. Exit criteria: NarrativeScaffold decomposes 8-page book with all per-page fields, CharacterBible validates sample YAML.

Each sub-prompt reads CLAUDE.md + the SAME architecture sections (§7, §9, §42, §43). Dependency: S6a first, then S6b and S6c parallel (S6c references trace types from S6a).

**S15 — Publishing Lane → 2 sub-prompts:**

- **S15a (Day 1 Block 4):** `tools/publish.py` (Typst assembly + ebooklib EPUB). No dependency on S4 illustration decision. Exit criteria: Typst renders 8-page PDF, ebooklib produces valid EPUB.
- **S15b (Day 2 Block 5):** `tools/illustrate.py` (fal.ai wrapper for selected illustration tier) + workflow wiring. Depends on S4 decision. Exit criteria: illustration pipeline runs with selected tier, character consistency checked.

**S16 — BizOps + Steward → 2 sub-prompts (if time-compressed):**

- **S16a (must-ship):** Tables (all 6 Steward + 3 BizOps) + invoice + pipeline + morning brief + Maghrib shutdown + core Steward (/next, /done, /process, /snapshot, /project). The operational core.
- **S16b (70% acceptable if cut):** Steward habits engine + deep work + health import + learning system. These are high-value but not required for Day 1 post-sprint operation.

```markdown
# VIZIER Control Tower — Handover Document

**Generated:** {timestamp}
**Handover number:** {NNN}
**Reason:** {context limit approaching | operator requested | end of day N}
**Prior handovers:** {list numbers, e.g. 001, 002 — for audit trail only, you don't need to read them}

## Current Status Board
{Copy the FULL status board with current states}

## Completed Sessions
{ALL completed sessions across entire sprint — not just this tower's tenure:
  - Session ID + name
  - Completion time (approximate)
  - Exit criteria: all passed / list any that were accepted with caveats
  - Issues discovered (if any)}

## In-Progress Sessions
{For each in-progress session:
  - Session ID + name
  - Which worker is running it
  - Estimated progress (e.g. "3 of 5 exit criteria passing")
  - Blockers reported (if any)}

## Deviations Register (CUMULATIVE — carried forward from ALL prior handovers)
{Every deviation from the build plan across the entire sprint.
 This section only grows — never remove entries from prior handovers.
 Format per entry:

  DEV-{NNN}: {session} — {one-line summary}
    What spec said: {original requirement}
    What actually happened: {what was built differently}
    Why: {reason for deviation}
    Impact: {what downstream sessions need to know}
    Decision doc: docs/decisions/{filename}.md (if exists)

 Examples:
  DEV-001: S0 — Hermes v0.7.0 patches needed, forked to vizier-hermes
    What spec said: Pin to upstream v0.7.0, no fork unless patches needed
    What actually happened: 3 patches required for gateway auth, forked
    Why: Upstream bug in Telegram gateway token refresh
    Impact: S14 is unnecessary (patches already applied)
    Decision doc: docs/decisions/hermes_fork_decision.md

  DEV-002: S6 — RollingContext split into two files
    What spec said: Single contracts/context.py
    What actually happened: Split into context.py + context_utils.py (400 lines total)
    Why: Size exceeded readable single-file threshold
    Impact: S15 and S21 import from both files
    Decision doc: none (minor structural choice)}

## Operator Decisions (CUMULATIVE — carried forward from ALL prior handovers)
{Every operator decision that affects downstream work.
 This section only grows.

  OD-{NNN}: {one-line summary}
    Decision: {what was decided}
    When: {approximate time}
    Affects: {which sessions or workflows}

 Examples:
  OD-001: Illustration pipeline — Kontext iterative selected
    Decision: PATH A (Kontext iterative) chosen over IP-Adapter and multi-ref
    When: Day 1 Block 2 (S4 endpoint testing)
    Affects: S15 illustration pipeline, all publishing workflows, image_model_preference in YAMLs

  OD-002: Book 1 art style — soft watercolour, Studio Ghibli influence
    Decision: Operator selected soft watercolour style direction
    When: Day 1 evening (Book 1 creative workshop)
    Affects: StyleLock for Book 1, derivative projects inherit this}

## Pending Decisions
{Decisions the operator hasn't made yet:
  - S4 illustration pipeline selection (if not yet decided)
  - Integration test results needing review
  - Any blocked session needing operator input}

## Next Actions
{Exactly what the new control tower should do first:
  - Which worker prompts to generate next
  - Which merges are pending (list worktrees + target branch)
  - Which checkpoints are coming up
  - Which sessions can be parallelised}

## Worktree State
{List ALL active worktrees:
  - ~/executor/vizier (main) — state description
  - ~/executor/vizier-{id} — owned by {session}, status
  - ...
  List worktrees that should be merged before next block.}

## Key Facts (CUMULATIVE — carried forward from ALL prior handovers)
{Anything the next tower needs to know that isn't in the architecture docs.
 This section only grows.
  - "CLIP validation on MPS: works but 3x slower than CPU — S13 may need extra time"
  - "pytrends requires proxy for Malaysia — added to docs/decisions/pytrends_proxy.md"
  - "MinIO bucket name is vizier-assets (not vizier-storage as some examples show)"
  - etc.}

## Resume Instructions
To resume as the new control tower:
1. Read ~/executor/vizier/CLAUDE.md
2. Read ~/executor/vizier/docs/VIZIER_BUILD_v1_3_1.md §0-§6
3. Read ~/executor/vizier/docs/VIZIER_ARCHITECTURE_v5_4_1.md §0-§0.1 only
4. Read THIS handover document (it is cumulative — you do NOT need prior handovers)
5. You are the NEW control tower. Resume from the state above.
   Do NOT re-generate prompts for completed sessions.
   Check the Deviations Register for anything that changes downstream prompts.
   Begin with the "Next Actions" section.
```

**The new tower session is started by the operator with:**
```
Read CONTROL_TOWER.md. Then read the latest handover document at 
~/executor/vizier/docs/handover/HANDOVER_{NNN}.md. You are resuming as 
control tower. Pick up from where the previous tower left off.
```

---

## Merge Protocol

When generating prompts for a new block that depends on completed worktree sessions, include merge instructions at the top of your response (before any worker prompts):

```bash
# Merge completed worktrees before launching new block
cd ~/executor/vizier
git merge vizier-{id1} --no-ff -m "merge(s{N}): {description} complete"
git merge vizier-{id2} --no-ff -m "merge(s{N}): {description} complete"
# Remove merged worktrees
git worktree remove ../vizier-{id1}
git worktree remove ../vizier-{id2}
# Create new worktrees for next block
git worktree add ../vizier-{id3} main
git worktree add ../vizier-{id4} main
```

If merge conflicts occur, the operator resolves them before launching new workers. Conflicts are unlikely if sessions touch different directories (enforced by the dispatch sequence), but possible if two sessions both modified pyproject.toml or a shared file.

---

## Worker Completion Report

When generating worker prompts, include this instruction at the end:

```
When done, report in this format:
- Session: {ID}
- Exit criteria: {pass/fail per item}
- Decisions made: {list any, with rationale — these go to docs/decisions/}
- Files created/modified: {list}
- Dependencies installed: {list any new pip packages}
- NEXT SESSION NEEDS TO KNOW: {anything about your implementation that 
  affects sessions that import from or build on your files}
```

The tower captures "NEXT SESSION NEEDS TO KNOW" in the Key Facts section of the handover. This is the primary mechanism for preventing tacit knowledge loss.

---

## Tower Retirement

The control tower retires when the sprint SHIP decision is made (Block 12). At retirement, it generates one final handover — `HANDOVER_FINAL.md` — with the complete sprint record:

- Full status board (all sessions complete or accepted at 70%)
- Complete Deviations Register
- Complete Operator Decisions log
- All Key Facts
- All integration test results
- SHIP gate pass/fail status
- **Post-sprint readiness assessment:** which post-sprint sessions (S22-S37) are unblocked and what each needs

This final handover becomes the **sprint retrospective document**. It lives permanently at `~/executor/vizier/docs/handover/HANDOVER_FINAL.md`.

After retirement, `CONTROL_TOWER.md` can be deleted from the repo root or kept as reference. It is not needed for post-sprint work.

---

## Post-Sprint Build Model

After the sprint, the control tower pattern is **not needed**. Here's why:

During the sprint, you're running 3-4 parallel CC sessions per block across 20 sessions in 3 days. That level of coordination requires a dispatcher. Post-sprint, the pace changes:

- Sessions are 1 at a time (S22, S23, S24, etc.)
- Each session is 2-4 hours, self-contained
- Dependencies are simpler (usually just "Core ship")
- No parallel worktrees needed
- No merge coordination

**Post-sprint execution model:** Open a CC session, give it the standard worker prompt structure (from this document's template), and let it build. No tower needed.

The operator can generate worker prompts manually using the same template:

```
Read ~/executor/vizier/CLAUDE.md first.
Read ~/executor/vizier/docs/VIZIER_POST_SPRINT_ROADMAP_v1_1.md, session {SXX} spec.
Read ~/executor/vizier/docs/VIZIER_ARCHITECTURE_v5_4_1.md, sections: {list}.

You are building {SXX}: {name}.
Working directory: ~/executor/vizier

{What to build from roadmap spec}
{Exit criteria from roadmap spec}
```

**If the post-sprint pace intensifies** (e.g. 3 sessions in parallel during Phase 2 multi-format production), the operator can reactivate the tower pattern:
1. Open a CC session
2. Feed it `CONTROL_TOWER.md` + `HANDOVER_FINAL.md`
3. Say "Resume as control tower for post-sprint Phase 2"
4. The tower reads the final handover, knows the full sprint history, and dispatches workers for the new phase

The tower pattern is reusable for any future build phase that requires parallel coordination. For sequential single-session work, it's overhead.

---

## Begin

Show the initial status board. Then generate BOTH the INFRA worker prompt AND the S0 worker prompt in the same response. S0 is on the critical path — every minute it waits after INFRA completes is a minute everything else waits. The operator will launch S0 the moment INFRA passes. Wait for operator to confirm infrastructure is ready before proceeding to Block 1 parallel sessions (S1, S2).
