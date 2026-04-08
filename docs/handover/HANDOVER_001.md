# VIZIER Control Tower — Handover Document

**Generated:** 2026-04-07 ~21:00
**Handover number:** 001
**Reason:** Natural break point — Block 3 launching, 4 sessions in flight, context getting long
**Prior handovers:** None (first handover)

## Current Status Board

```
SESSION | STATUS      | DEPENDS_ON     | BLOCK | ATTN | WORKER
--------|-------------|----------------|-------|------|-------
INFRA   | ✅ DONE     | —              | pre   | UN   | —
S0      | ✅ MERGED   | INFRA ✅       | 1     | UN   | —
S1      | ✅ MERGED   | S0 ✅          | 1     | UN   | —
S2      | ✅ MERGED   | S0 ✅          | 1     | UN   | —
SMOKE-1 | ✅ PASS     | S1+S2          | 1→2   | UN   | —
PATCH   | ✅ MERGED   | S0+S1          | 1→2   | UN   | —
S4      | 🔄 RUNNING  | S0 ✅          | 2     | AT   | G (on main)
S5      | 🔄 RUNNING  | S0 ✅          | 2     | UN   | D (worktree s5)
S6      | ✅ MERGED   | S0 ✅          | 2     | UN   | —
S7      | ✅ MERGED   | S0 ✅          | 2     | UN   | —
SMOKE-2 | ✅ PASS     | S6+S7          | 2→3   | UN   | —
S8      | 🔄 RUNNING  | S6 ✅          | 3     | UN   | (Claude auto-worktree)
S9      | 🔄 RUNNING  | S6 ✅          | 3     | LT   | (Claude auto-worktree)
S10a    | not_started | S6✅,S7✅,S8   | 4     | LT   | —
S11     | not_started | S10a           | 5     | LT   | —
S12     | not_started | S10a           | 5     | LT   | —
S13     | not_started | S10a           | 5     | AT   | —
S14     | not_started | S0 ✅          | 7     | UN   | —
S15     | not_started | S10a,S9,S2✅,S6✅| 4+5  | AT   | —
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

## Completed Sessions

| Session | Completed | Exit Criteria | Notes |
|---------|-----------|---------------|-------|
| INFRA | Day 1 early | All pass | Postgres, MinIO, PostgREST installed. API keys partially set. |
| S0 | Day 1 Block 1 | All 12 pass | Hermes v2026.4.3 = v0.7.0. CLIP/NIMA on MPS <100ms. 82+ files. |
| S1 | Day 1 Block 1 | All 9 pass | 25 config files. Design index filter works but textile+warm returns only 1 match (data gap, not bug). |
| S2 | Day 1 Block 1 | All 6 pass | 34 font files, 11 Typst templates, 4 visual templates. Typst 0.14.2. |
| SMOKE-1 | Day 1 Block 1→2 | PASS (1 warning) | Design index warning accepted. |
| PATCH | Day 1 Block 1→2 | All 8 pass | Tech scout gaps filled: GEPA, connectors, mutation operators, eval cases. |
| S6 | Day 1 Block 2 | All 12 pass | 52 tests, pyright clean. All contracts match CLAUDE.md §3 exactly. |
| S7 | Day 1 Block 2 | All 7 pass | 20 tests, pyright clean. Uses stdlib sqlite3 (LibSQL-compatible). |
| SMOKE-2 | Day 1 Block 2→3 | PASS | NarrativeScaffold API note: params are `target_age`, `page_count` (not `age_group`, `total_pages`). |

## In-Progress Sessions

### S4 — Endpoint Testing (ATTENDED)
- Running on main branch
- Operator is steering illustration pipeline decisions
- Testing fal.ai image generation endpoints (Kontext, IP-Adapter, Nano Banana, FLUX.2, LoRA)
- Key decision pending: illustration pipeline tier selection → `docs/decisions/illustration_pipeline.md`
- Also testing: free Nano Banana draft tier (tech scout injection)
- No completion report yet

### S5 — Dataset Processing (UNATTENDED)
- Running in worktree on branch s5 (at /Users/Executor/vizier-s5)
- Hour 1 extractions all done (visual brief expander, quality framework, composition grammar, PosterIQ)
- Working through Hours 2-4 extractions
- Datasets were NOT pre-downloaded — S5 is downloading as it goes
- Item 16 (GEPA bootstrap) pending
- No completion report yet

### S8 — Policy + Observability (UNATTENDED)
- Just launched, running in Claude auto-worktree (NOT pre-created vizier-s8)
- Building: PolicyEvaluator, Langfuse integration, dual tracing, quality posture
- No progress report yet

### S9 — Packs + Workflows + Tripwire (LIGHT-TOUCH)
- Just launched, running in Claude auto-worktree (NOT pre-created vizier-s9)
- Building: 16 workflow YAMLs, generic executor, tripwire, client overrides
- Includes tech scout injections: reminder_prompt field, Nano Banana draft tier conditional
- No progress report yet

## Deviations Register (CUMULATIVE)

DEV-001: S1 — Ran in Claude auto-worktree instead of pre-created vizier-s1
  What spec said: Worker runs in /Users/Executor/vizier-s1 worktree
  What actually happened: Worker ran in /Users/Executor/vizier/.claude/worktrees/agent-a8b4a231 on branch worktree-agent-a8b4a231
  Why: Claude Code worktree isolation mode creates its own worktrees
  Impact: Must check `git branch` for claude/* branches when merging. Pre-created worktrees may be unused.

DEV-002: S6/S7 — Also ran in Claude auto-worktrees
  What spec said: Workers run in vizier-s6 and vizier-s7
  What actually happened: S6 on branch claude/zealous-engelbart, S7 on branch claude/mystifying-borg
  Why: Same as DEV-001
  Impact: When merging, check `git log main..<branch>` on claude/* branches to find actual work. Pre-created worktrees at vizier-s6/s7 had no new commits.

DEV-003: S5 — Datasets not pre-downloaded
  What spec said: Pre-download all 15 datasets night before sprint
  What actually happened: Datasets not pre-downloaded, S5 downloading as it goes
  Why: Pre-sprint checklist item was skipped
  Impact: S5 runs longer, uses more tokens. May not complete all 15 datasets. Priority ordering ensures Hour 1 blocking items finish first.

DEV-004: S2 — Also included fonts that S0 was expected to handle
  What spec said: S2 downloads fonts to assets/fonts/
  What actually happened: S1 auto-worktree also included S2 font+template work in same commit. S2 ran separately in vizier-s2 and also produced the work.
  Why: S1's Claude auto-worktree agent was overly ambitious
  Impact: No conflict — S2 worktree had the canonical work on branch s2 which was merged properly.

## Operator Decisions (CUMULATIVE)

OD-001: Architecture docs gitignored
  Decision: VIZIER_ARCHITECTURE_v5_4_1.md, VIZIER_BUILD_v1_3_1.md, VIZIER_POST_SPRINT_ROADMAP_v1_1.md, and CONTROL_TOWER.md are gitignored. CLAUDE.md stays committed.
  When: Day 1, during S0
  Affects: All worker prompts must use absolute paths to /Users/Executor/vizier/docs/. Docs exist locally in worktrees but not on GitHub.

OD-002: Post-merge smoke tests after every block
  Decision: Run 15-min SMOKE-N validation after every block merge before launching next block.
  When: Day 1, before Block 2
  Affects: Every block transition. Tower generates SMOKE prompt tailored to merged work.

OD-003: S3 (asset collection) deferred
  Decision: Operator has not started S3 yet. No downstream session hard-depends on it.
  When: Day 1
  Affects: Book 1 creative workshop (evening Day 1) benefits from character reference images. S12 ingests whatever S3 has by Day 2.

## Pending Decisions

- **S4 illustration pipeline tier** — not yet decided. Must be decided by end of S4. Flows into S15 (publishing lane) and all Book production. Check `docs/decisions/illustration_pipeline.md` when S4 reports.
- **S4 Nano Banana draft tier** — go/no-go pending. If go, S9 adds draft_preview to image_model_preference. Check `docs/decisions/nano_banana_draft_tier.md`.
- **Book 1 creative workshop** — scheduled for evening Day 1. Operator hasn't started yet.

## Next Actions

1. **Wait for S8, S9, S4, S5 completion reports.** S8 and S9 were just launched. S4 and S5 are in progress.
2. **When S8 completes:** S10a becomes ready (all deps: S6✅, S7✅, S8). This is the critical path.
3. **When S8 + S9 complete:** Merge both to main. Run SMOKE-3. Create worktrees for Block 4.
4. **Block 4 dispatch:**
   - S10a (data foundation — 14+2 core tables). SEQUENTIAL, critical path.
   - S15a partial (assembly pipeline — tools/publish.py, tools/illustrate.py). Can start after S10a begins.
5. **When S4 completes:** Record illustration tier decision in handover. This affects S15 prompt.
6. **When S5 completes:** Merge to main. Check GEPA bootstrap pair counts.
7. **Generate S10a prompt** — include tech scout injection: 2 document_set tables (total 16 core tables, not 14).
8. **Generate S15a prompt** — depends on S4 illustration tier decision and S9 workflow schema.

## Worktree State

- `/Users/Executor/vizier` (main) — latest: all S0-S7 + patch merged. S4 running here.
- `/Users/Executor/vizier-s5` (branch: s5) — S5 dataset processing, in progress
- `/Users/Executor/vizier-s8` (branch: s8) — created but likely unused (Claude auto-worktree pattern)
- `/Users/Executor/vizier-s9` (branch: s9) — created but likely unused (Claude auto-worktree pattern)
- Multiple `claude/*` branches — check `git branch | grep claude` for active auto-worktrees

**Merge pattern for Claude auto-worktrees:** Run `git log --oneline main..claude/<name>` on each claude/* branch to find which has new commits. The branch with commits matching the session's work is the one to merge.

## Key Facts (CUMULATIVE)

- **Python:** Use `python3.11` explicitly. System python3 is 3.9.6.
- **pip:** `pip3.11 install --break-system-packages`
- **Homebrew PATH:** Every bash command needs `eval "$(/opt/homebrew/bin/brew shellenv)"` and `export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"`
- **Pro-max location:** `~/vizier-pro-max` (NOT ~/executor/vizier-pro-max)
- **MPS:** Available. CLIP and NIMA run on MPS <100ms.
- **.env location:** `/Users/Executor/vizier/.env` (gitignored). Worker preamble: `set -a && source /Users/Executor/vizier/.env && set +a`
- **API keys set:** OpenAI ✅, fal.ai ✅, Langfuse ✅, Telegram (Vizier) ✅, Telegram (Steward) ✅, ElevenLabs ✅, Gamma.app ✅
- **API keys NOT set:** Anthropic ❌ (needed S19, Month 3+), Google ❌ (needed S19, Month 3+)
- **Hermes version:** v2026.4.3 = v0.7.0, pinned as submodule
- **CLIP:** ViT-B/32, 512-dim features, MPS device
- **NIMA:** MobileNetV2 backbone, mean score 5.55, MPS device
- **Typst:** v0.14.2. Compile: `TYPST_FONT_PATHS=assets/fonts typst compile <template>.typ output.pdf`
- **Typst template params:** sys.inputs: primary_color, secondary_color, accent_color, headline_font, body_font, title, author, date, client_name
- **Children's book templates:** `target_age` input (not `age_group`), `text_side` for book_split
- **Ebook pattern:** `#import "ebook.typ": *` then append chapters
- **NarrativeScaffold API:** `.decompose(target_age=..., page_count=..., pages=...)` — NOT age_group/total_pages
- **Contract imports:** `from contracts import <Name>` or `from contracts.<module> import <Name>`
- **evaluate_readiness()** is a standalone function, not a class method
- **TraceCollector:** `.step()` context manager, `.finalise()` → ProductionTrace
- **Span decorator:** `@track_span` or `@track_span(model="gpt-5.4-mini", step_type="scoring")`
- **call_llm():** auto-records spans. Pass `operation_type=` for memory routing log.
- **Spans DB:** `data/spans.db` (LibSQL/sqlite3, gitignored)
- **Anthropic caching:** `cache_control: {"type": "ephemeral"}` on system blocks
- **Token-Efficient Tools:** `anthropic-beta: token-efficient-tools-2025-02-19`
- **Tech scout checklist:** `/Users/Executor/vizier/docs/VIZIER_TECH_SCOUT_INJECTION_CHECKLIST.md` — read BEFORE generating any worker prompt
- **GitHub repo:** https://github.com/khayroul/vizier (private)
- **MinIO:** Running as background process (not brew services). Bucket: vizier-assets.
- **Design index warning:** textile+warm filter returns 1 match (batik_air only). Data gap, not code bug. Accepted.

## Resume Instructions
To resume as the new control tower:
1. Read ~/executor/vizier/CLAUDE.md
2. Read ~/executor/vizier/docs/VIZIER_BUILD_v1_3_1.md §0-§6
3. Read ~/executor/vizier/docs/VIZIER_ARCHITECTURE_v5_4_1.md §0-§0.1 only
4. Read THIS handover document (it is cumulative — you do NOT need prior handovers)
5. Read ~/executor/vizier/docs/VIZIER_TECH_SCOUT_INJECTION_CHECKLIST.md — for injections into future worker prompts
6. You are the NEW control tower. Resume from the state above.
   Do NOT re-generate prompts for completed sessions.
   Check the Deviations Register for anything that changes downstream prompts.
   Begin with the "Next Actions" section.
