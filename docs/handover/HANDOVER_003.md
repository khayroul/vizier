# VIZIER Control Tower — Handover Document

**Generated:** 2026-04-08 ~14:00
**Handover number:** 003
**Reason:** End of CT-003 context window — S19 prompt generated, all code sessions except S19 complete
**Prior handovers:** 001 (audit trail), 002 (cumulative base). This document is cumulative — successor needs ONLY this file.

## Current Status Board

```
SESSION | STATUS         | DEPENDS_ON       | BLOCK | ATTN | TESTS
--------|----------------|------------------|-------|------|------
INFRA   | ✅ DONE        | —                | pre   | UN   | —
S0      | ✅ MERGED      | INFRA ✅         | 1     | UN   | —
S1      | ✅ MERGED      | S0 ✅            | 1     | UN   | —
S2      | ✅ MERGED      | S0 ✅            | 1     | UN   | —
SMOKE-1 | ✅ PASS        | S1+S2            | 1→2   | UN   | —
PATCH   | ✅ MERGED      | S0+S1            | 1→2   | UN   | —
S4      | ✅ MERGED      | S0 ✅            | 2     | AT   | —
S5      | ✅ MERGED      | S0 ✅            | 2     | UN   | —
S6      | ✅ MERGED      | S0 ✅            | 2     | UN   | 52
S7      | ✅ MERGED      | S0 ✅            | 2     | UN   | 20
SMOKE-2 | ✅ PASS        | S6+S7            | 2→3   | UN   | —
S8      | ✅ MERGED      | S6 ✅            | 3     | UN   | 23
S9      | ✅ MERGED      | S6 ✅            | 3     | LT   | 85
S10a    | ✅ MERGED      | S6✅,S7✅,S8✅   | 4     | LT   | 39
S11     | ✅ MERGED      | S10a ✅          | 5     | LT   | 40
S12     | ✅ MERGED      | S10a ✅          | 5     | LT   | 27
S13     | ✅ MERGED      | S10a ✅          | 5     | AT   | 43
S15a    | ✅ MERGED      | S10a✅,S9✅,S2✅,S6✅ | 4  | AT   | 21
S15b    | ✅ MERGED      | S15a✅,S4✅      | 5     | AT   | 60+
S16     | ✅ MERGED      | S10a ✅          | 9     | LT   | 26
S17     | ✅ MERGED      | S10a✅,S16✅     | 10    | AT   | 15
S18     | ✅ MERGED      | S10a ✅          | 9     | UN   | 28
S21     | ✅ MERGED      | S15 ✅           | 11    | LT   | 35
IT-1,3,5| ✅ DONE        | various          | 12    | —    | 47
S19     | READY ✅       | S10a✅,S18✅     | 10    | LT   | —
IT-2    | READY ✅       | S15✅,S4✅       | 12    | —    | —
IT-4    | READY ✅       | S18✅            | 12    | —    | —
S14     | NOT NEEDED?    | S0 ✅            | 7     | UN   | —
BOOK-1  | not_started    | S4✅,S15✅       | 6-8   | OP   | —
```

**Total tests on main: 538 passing, 0 failures (as of ecee3a9)**
**Remote:** git@github.com:khayroul/vizier.git — up to date, repo is PUBLIC.
**HEAD:** ecee3a9 (feat(s17): operator dashboard)

## Completed Sessions (since HANDOVER_002)

| Session | Completed | Exit Criteria | Key Output |
|---------|-----------|---------------|------------|
| S15b | Day 2 Block 6 | All 16 pass | 387+ tests. IllustrationPipeline, Kontext iterative, CLIP verification, creative workshop, derivative support |
| S16 | Day 2 Block 9 | All pass (70% cut) | 26 tests. 9 tables (invoices, payments, pipeline, steward_inbox/tasks/projects/reviews/health_log/learning). Payment trigger, invoice sequence. GTD Steward PA (/next, /done, /process, /snapshot, /project). Morning brief cron. |
| S17 | Day 2 Block 10 | All pass (Cloudflare cut) | 15 tests. PostgREST on port 3001, 7 dashboard views, Refine + Vite scaffold, design_selector_api.py, token spend + job status pages |
| S18 | Day 2 Block 9 | All pass | 28 tests. Hybrid search (FTS + pgvector + RRF + LLM reranker), retrieval profiles, Wisdom Vault Obsidian import, ingest_card, promote_exemplar, record_outcome, datasets/dataset_items tables |
| S21 | Day 2 Block 11 | All pass | 35 tests. Children's book, ebook, serial fiction production. Derivative workshop, RollingContext integration, entity tracking |
| IT-1,3,5 | Day 2 Block 12 | 45 pass, 2 skip, 3 bugs found | Routing integration, poster production chain, feedback state machine. Bugs: missing S8 merge (fixed), mock targets stale (fixed) |

## In-Progress Sessions

None actively running.

## Deviations Register (CUMULATIVE — includes all from HANDOVER_002)

DEV-001: S1 — Ran in Claude auto-worktree instead of pre-created vizier-s1
  What spec said: Worker runs in /Users/Executor/vizier-s1 worktree
  What actually happened: Claude Code worktree isolation creates its own branches
  Why: CC's agent mode creates claude/* branches automatically
  Impact: Check `git branch` for claude/* branches when merging. Pre-created worktrees may be unused.

DEV-002: S6/S7 — Also ran in Claude auto-worktrees
  What spec said: Workers run in vizier-s6 and vizier-s7
  What actually happened: S6 on claude/zealous-engelbart, S7 on claude/mystifying-borg
  Why: Same as DEV-001
  Impact: Merge pattern: `git log main..claude/<name>` to find work.

DEV-003: S5 — Datasets not pre-downloaded
  What spec said: Pre-download all 15 datasets night before sprint
  What actually happened: Downloaded during S5, 11/15 found accessible
  Why: Pre-sprint checklist skipped
  Impact: D1 found at PosterCraft/Poster100K. D2/D3 not yet public (GEPA bootstrap blocked). D6 gated. D13 institutional only.

DEV-004: S2 — S1 auto-worktree also included some S2 work
  What spec said: S2 downloads fonts
  What actually happened: S1 agent was overly ambitious, S2 ran separately with canonical work
  Why: Auto-worktree scope creep
  Impact: None — S2 canonical work merged cleanly.

DEV-005: S12 filled retrieve_similar_exemplars() (was S11's job)
  What spec said: S11 builds retrieve_similar_exemplars(), S12 builds contextualise_card()
  What actually happened: S12 implemented BOTH functions. S11 also implemented retrieve_similar_exemplars().
  Why: Both sessions running in parallel filled the same stub
  Impact: Merged without conflict — S12 merged first (3888aca), S13 used S11's version, S11 merged last (cb358e2). Final state has S11's CLIP implementation.

DEV-006: S13 recreated config files S5 already created
  What spec said: S5 creates quality frameworks and prompt templates
  What actually happened: S13 also created visual_brief_expander.md, posteriq_quality_dimensions.yaml, poster_quality.md
  Why: S13 needed specific formats; S5's versions may have differed
  Impact: Merged cleanly (S12 before S13 on main). S13's versions are canonical.

DEV-007: S8 — Silence detection via function, not trigger
  What spec said: Feedback state machine via Postgres triggers
  What actually happened: `feedback_check_silence()` is a callable function, not an auto-firing trigger
  Why: Postgres triggers can't fire on elapsed time
  Impact: S16 or cron must call `feedback_check_silence()` periodically.

DEV-008: S10a — IVFFlat indexes created on empty tables
  What spec said: Create pgvector indexes
  What actually happened: Indexes created but Postgres warns about low recall with little data
  Why: Correct long-term; recall improves as data grows
  Impact: Rebuild indexes after bulk data loading (`REINDEX`).

DEV-009: (RETRACTED — S18 spec revision reverted the changes)

DEV-010: (RETRACTED — S18 spec revision reverted the changes)

DEV-011: S8 never merged to main (caught by IT-BATCH-1)
  What spec said: HANDOVER_002 status board showed S8 as ✅ MERGED
  What actually happened: S8 commit a8de4de existed on s8 branch but was never merged to main
  Why: Previous tower's status board incorrectly recorded merge status
  Impact: middleware/observability.py and middleware/policy.py missing from main. Fixed: `git merge s8 --no-ff`. 460 tests passing after merge.

DEV-012: S16 committed directly to main (not on branch)
  What spec said: Worker runs in worktree, commits to branch
  What actually happened: S16 worker committed 8a1fb8c directly on main in its worktree
  Why: Same pattern as DEV-001/002 — CC worktree isolation
  Impact: `git merge vizier-s16` failed (already on main). No actual issue — commit was already there.

DEV-013: S17 left files unstaged
  What spec said: Worker commits and reports
  What actually happened: S17 worker created files but left them unstaged on main
  Why: Worker said "Ready to commit when you'd like"
  Impact: CT-003 staged and committed manually. All 15 tests passing.

DEV-014: S18 refactored embed_text location, broke 3 test mocks
  What spec said: S18 builds knowledge tools
  What actually happened: S18 extracted `_embed_text` from `tools/research.py` to `utils/embeddings.py`, made `tools/knowledge.ingest_card()` canonical ingestion. 3 tests in test_research.py mocked the old location.
  Why: Valid refactoring, but downstream tests had stale mock targets
  Impact: Fixed by CT-003: changed mock target to `tools.knowledge.embed_text` (must mock at import site, not definition site). 523 tests passing after fix.

## Operator Decisions (CUMULATIVE — includes all from HANDOVER_002)

OD-001: Architecture docs gitignored
  Decision: VIZIER_ARCHITECTURE_v5_4_1.md, VIZIER_BUILD_v1_3_1.md, VIZIER_POST_SPRINT_ROADMAP_v1_1.md, CONTROL_TOWER.md are gitignored. CLAUDE.md stays committed.
  When: Day 1, during S0
  Affects: All worker prompts must use absolute paths to /Users/Executor/vizier/docs/

OD-002: Post-merge smoke tests after every block
  Decision: Run SMOKE-N validation after every block merge before launching next block.
  When: Day 1, before Block 2
  Affects: Every block transition.

OD-003: S3 (asset collection) deferred
  Decision: Operator has not started S3 yet.
  When: Day 1
  Affects: Book 1 benefits from character references. S12 ingests whatever S3 has.

OD-004: Illustration pipeline — Tier 2 (Kontext iterative) selected
  Decision: PATH A (Kontext iterative) chosen. 92% consistency, $0.04/page, no training.
  When: Day 1 Block 2 (S4 endpoint testing)
  Affects: S15b, all publishing workflows, image_model_preference in YAMLs.
  Details: `fal-ai/flux-pro/kontext`, guidance_scale=3.5, output_format=jpeg, re-anchor every 8 pages.

OD-005: Nano Banana Pro BM text — GO
  Decision: Production-ready for text-heavy BM marketing. 5/5 quality.
  When: Day 1 Block 2 (S4)
  Affects: image_model_preference text_heavy field.

OD-006: Nano Banana draft tier — GO
  Decision: Free tier viable for preview/iteration. ~$0.10/image.
  When: Day 1 Block 2 (S4)
  Affects: S9 YAMLs — `draft_preview: nano-banana` added by S15b in 7 workflow YAMLs.

OD-007: FLUX.2 Pro photorealistic — GO
  Decision: Excellent product photography.
  When: Day 1 Block 2 (S4)
  Affects: image_model_preference photorealistic field.

OD-008: LoRA training — CONDITIONAL
  Decision: Viable for Tier 1 with 20+ real photos, not with 10 AI-generated images.
  When: Day 1 Block 2 (S4)
  Affects: Future Tier 1 projects only. Not sprint-blocking.

OD-009: GitHub repo made public
  Decision: Changed khayroul/vizier from private to public.
  When: Day 2 (CT-003)
  Affects: No secrets in repo. Architecture docs already gitignored (OD-001).

## Pending Decisions

- **Book 1 creative workshop** — not started. Operator hasn't begun character bibles, art style selection, or story scaffold.
- **S14 (Hermes fork patch)** — no issues reported so far. Likely not needed. Can be dropped.
- **scikit-learn in pyproject.toml** — S12 installed it but didn't add to deps. Still needs adding.

## Next Actions (PRIORITY ORDER)

### 1. Launch S19 — Self-Improvement + Calibration (LAST CODE SESSION)

Prompt already generated: `docs/handover/HANDOVER_003_S19_PROMPT.md`

All dependencies met: S10a ✅, S18 ✅. This is the final code session.

Builds: pattern detection, failure analysis, experiment framework, prompt versioning, exemplar optimisation, calibration functions, drift detection (functions only, cron cut).

### 2. When S19 completes: IT-2 + IT-4 (remaining integration tests)

Dependencies now met for both:
- **IT-2:** Children's book specimen (S15 ✅, S4 ✅)
- **IT-4:** Knowledge retrieval integration (S18 ✅)

Generate prompts for these. See BUILD spec lines 315-339 for IT format.

### 3. Block 12: Full integration test run + SHIP decision

After S19 + IT-2 + IT-4, run all integration tests (IT-1 through IT-5) together. If green, assess SHIP readiness.

### 4. Cleanup tasks (non-blocking)

- **Delete stale branches:** `claude/beautiful-khorana`, `claude/cool-brown`, `claude/eager-turing`, `claude/fervent-kare`, `claude/mystifying-borg`, `claude/zealous-engelbart`, `s5`, `s8`, `s9`, `s16`, `feat/s18-knowledge-spine`
- **Remove stale worktree:** `/Users/Executor/vizier-s18` still exists (s18 branch). Remove with `git worktree remove /Users/Executor/vizier-s18 --force` (submodule workaround)
- **Add scikit-learn to pyproject.toml** — listed as dep but not in file
- **S14 (Hermes fork patch):** No issues surfaced. Recommend SKIP unless a specific Hermes bug appears.

## Worktree State

- `/Users/Executor/vizier` (main) — at ecee3a9, clean except CLAUDE.md modification + untracked docs/handover/
- `/Users/Executor/vizier-s18` — STALE, should be removed (s18 branch, already merged)
- Stale local branches: claude/beautiful-khorana, claude/cool-brown, claude/eager-turing, claude/fervent-kare, claude/mystifying-borg, claude/zealous-engelbart, s5, s8, s9, s16, feat/s18-knowledge-spine

## Key Facts (CUMULATIVE)

**Environment:**
- Python: `python3.11` explicitly. System python3 is 3.9.6.
- pip: `pip3.11 install --break-system-packages`
- Homebrew PATH: every bash command needs `eval "$(/opt/homebrew/bin/brew shellenv)"` and `export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"`
- Pro-max location: `~/vizier-pro-max` (NOT ~/executor/vizier-pro-max)
- MPS: Available. CLIP and NIMA run on MPS.
- .env location: `/Users/Executor/vizier/.env` (gitignored). Worker preamble: `set -a && source /Users/Executor/vizier/.env && set +a`
- API keys set: OpenAI ✅, fal.ai ✅, Langfuse ✅, Telegram (Vizier) ✅, Telegram (Steward) ✅, ElevenLabs ✅, Gamma.app ✅
- API keys NOT set: Anthropic ❌ (Month 3+), Google ❌ (Month 3+)
- MinIO: background process (not brew services). Bucket: vizier-assets.
- GitHub repo: https://github.com/khayroul/vizier (PUBLIC)

**Runtime:**
- Hermes: v2026.4.3 = v0.7.0, pinned as submodule
- Typst: v0.14.2. Compile: `TYPST_FONT_PATHS=assets/fonts typst compile <template>.typ output.pdf`
- CLIP: ViT-B/32 via open_clip_torch, 512-dim, MPS device
- NIMA: MobileNetV2, ImageNet weights + custom 10-class head, mean ~5.5. No pre-trained NIMA weights.

**Contracts & imports:**
- `from contracts import <Name>` or `from contracts.<module> import <Name>`
- `from contracts.publishing import NarrativeScaffold, CharacterBible, StoryBible, StyleLock, PlanningObject`
- NarrativeScaffold: `.decompose(target_age=..., page_count=..., pages=...)` — NOT age_group/total_pages
- `evaluate_readiness()` is a standalone function, not a class method
- `TraceCollector.step()` context manager, `.finalise()` → ProductionTrace

**Routing (S11):**
- `from contracts.routing import route, fast_path_route, llm_route, refine_request, select_design_systems, RoutingResult`
- `from utils.knowledge import retrieve_knowledge, assemble_context, lost_in_middle_reorder`
- Design system selector is in `contracts/routing.py` — S17 calls `select_design_systems()`, NOT rebuild
- lru_cache on config loaders — call `.cache_clear()` if configs edited at runtime

**Research & retrieval (S12):**
- `from utils.retrieval import retrieve_similar_exemplars, encode_image, contextualise_card`
- `contextualise_card(card, source)` — both args are `dict[str, str]`
- `from tools.research import fetch_trends, ingest_swipe, check_calendar_events`
- `from tools.visual_dna import extract_visual_dna, populate_asset_visual_dna`
- `from tools.seeding import seed_client, seed_all_clients`

**Visual intelligence (S13):**
- `from tools.image import generate_image, select_image_model`
- `from tools.visual_scoring import critique_4dim, score_with_exemplars, nima_prescreen`
- `critique_4dim()` takes `image_description` (text), not raw bytes
- `from middleware.guardrails import run_parallel_guardrails, GuardrailMailbox`
- `from tools.visual_pipeline import run_visual_pipeline`
- BM naturalness is fully deterministic (regex, zero tokens)

**Data foundation (S10a):**
- `from utils.database import get_cursor, run_migration` — RealDictCursor (rows are dicts)
- `from utils.storage import upload_bytes, download_bytes` — MinIO
- `from utils.trace_persist import persist_trace, load_trace, collect_and_persist`
- Feedback state machine: transitions via trigger. Invalid → `psycopg2.errors.RaiseException`
- `feedback_check_silence()` must be called periodically (no auto-timer) — DEV-007
- pgvector indexes: IVFFlat on assets.visual_embedding (512d), knowledge_cards.embedding (1536d)

**Policy & observability (S8):**
- `from middleware.policy import PolicyEvaluator, PolicyRequest`
- `from middleware.observability import observe_with_metadata, trace_to_langfuse, dual_trace, check_context_size`
- `from middleware.quality_posture import get_quality_posture, PostureConfig`
- Gate order: phase → tool → budget → cost
- Budget gate queries spans SQLite with 24h window
- Langfuse lazy-init; if unavailable, local spans still work

**Workflow (S9):**
- `from tools.executor import WorkflowExecutor, StubWorkflowError`
- `from tools.workflow_schema import WorkflowPack, load_workflow`
- Client overrides: `config/clients/{id}.yaml` → `workflow_overrides` dict
- Tripwire critique: `{"dimension": str, "score": float, "issues": list[str], "revision_instruction": str}`
- reminder_prompt in YAML with `{variable}` placeholders

**Assembly (S15a):**
- `from tools.publish import assemble_childrens_book_pdf, assemble_ebook, assemble_document_pdf`
- `check_visual_consistency()` is a STUB — S15b wired CLIP into it
- STRATEGY_TEMPLATE_MAP maps TextPlacementStrategy → Typst template filename
- Images must exist on disk as absolute paths before calling assembly
- Typst source generated per-book (not importing templates)

**Illustration pipeline (S15b):**
- `from tools.illustration import IllustrationPipeline`
- Kontext iterative with page-to-page state, anchor resets every 8 pages
- `fal_client.upload()` needed — fal.ai requires hosted URLs, not local file paths. MinIO is localhost, so images must be uploaded to fal first.
- CLIP verification threshold: 0.75 cropped character, 0.65 full-page
- Creative workshop flow: style exploration → style lock → character consistency
- Derivative support: derivative artifacts inherit parent workshop outputs

**Knowledge spine (S18):**
- `from tools.knowledge import ingest_card, promote_exemplar, record_outcome`
- `from utils.embeddings import embed_text, format_embedding`
- Hybrid search: FTS (tsvector 'simple' dictionary) + pgvector cosine + RRF merge + GPT-5.4-mini reranker
- Retrieval profiles in `config/retrieval_profiles.yaml`
- Document set filtering via document_sets/document_set_members tables
- Wisdom Vault: `from tools.knowledge import import_obsidian_vault`
- context_prefix column on knowledge_cards — prefix for embedding, raw content for production

**BizOps + Steward (S16):**
- `from tools.steward import capture_inbox, process_inbox, get_next_task, complete_task, create_project`
- `from tools.bizops import create_invoice, generate_invoice_pdf, create_pipeline_entry, morning_brief`
- 9 tables in migrations/extended.sql (3 BizOps + 6 Steward)
- Payment trigger auto-transitions invoice status
- Steward is separate Telegram bot, same engine

**Dashboard (S17):**
- PostgREST on port 3001, config at config/postgrest.conf
- 7 dashboard views in migrations/dashboard_views.sql
- Refine + Vite scaffold in dashboard/
- design_selector_api.py — Python HTTP proxy to select_design_systems()
- Cloudflare Tunnel was CUT — local access only for Day 1

**Extended lanes (S21):**
- Children's book, ebook, serial fiction production workflows
- RollingContext per-section/per-episode coherence
- Entity tracking across episodes
- Derivative workshop inherits parent outputs

**S4 illustration decisions:**
- Tier 2 — Kontext iterative: `fal-ai/flux-pro/kontext` (NOT `fal-ai/flux-kontext/pro`)
- API params: guidance_scale=3.5, output_format=jpeg, previous page as image_url
- Re-anchor every 8 pages from original reference
- CLIP threshold: 0.75 cropped character, ~0.65 full-page
- BM posters: `fal-ai/nano-banana-pro`
- Photorealistic: `fal-ai/flux-2-pro`
- Draft: `fal-ai/nano-banana` (free OpenRouter)
- Cost: ~$0.04/page Kontext

**Integration tests (IT-BATCH-1):**
- tests/integration/test_it1_poster.py — 17 tests (poster production chain)
- tests/integration/test_it3_fastpath.py — 15 tests (routing fast-path)
- tests/integration/test_it5_feedback.py — 15 tests (feedback state machine)
- 3 bugs found and fixed during IT run (S8 merge, mock targets)

**Spans:** `@track_span` decorator, `call_llm()` auto-records. data/spans.db (sqlite3). Anthropic caching: `cache_control: {"type": "ephemeral"}`. Token-efficient tools: `anthropic-beta: token-efficient-tools-2025-02-19`.

**Tech scout checklist:** `/Users/Executor/vizier/docs/VIZIER_TECH_SCOUT_INJECTION_CHECKLIST.md` — read before generating worker prompts.

## S19 Prompt Location

Pre-generated and ready: `docs/handover/HANDOVER_003_S19_PROMPT.md`

Contents: Full self-contained worker prompt covering pattern detection, failure analysis, experiment framework, prompt versioning, exemplar optimisation, calibration, drift detection functions, benchmark plan doc. 70% cut applied (cron scheduler cut, functions kept). Tech scout GEPA injection included (preference pair columns on experiments table).

## Code Review Protocol

CT-003 reviewed code from S18, S16, and S15b workers. Pattern:
1. Worker submits code review findings (critical/high/medium)
2. CT reviews each finding, approves or rejects with rationale
3. Worker implements approved changes
4. Worker submits session report with exit criteria
5. CT merges to main

S19 should follow same pattern. Worker reports → CT reviews → merge.

## Resume Instructions

To resume as the new control tower:

1. Read ~/executor/vizier/CLAUDE.md
2. Read ~/executor/vizier/docs/VIZIER_BUILD_v1_3_1.md §0-§6
3. Read ~/executor/vizier/docs/VIZIER_ARCHITECTURE_v5_4_1.md §0-§0.1 only
4. Read ~/executor/vizier/docs/VIZIER_TECH_SCOUT_INJECTION_CHECKLIST.md
5. Read THIS handover document (it is cumulative — you do NOT need HANDOVER_001 or HANDOVER_002)
6. You are the NEW control tower. Resume from the state above.
   Do NOT re-generate prompts for completed sessions.
   Check the Deviations Register for anything that changes downstream prompts.
   Begin with the "Next Actions" section.
   The S19 prompt is ALREADY GENERATED — just launch it.
