# VIZIER Control Tower — Handover Document

**Generated:** 2026-04-08 ~09:00
**Handover number:** 002
**Reason:** Natural break point — Block 5 complete, Block 9 ready to launch, context long
**Prior handovers:** 001 (audit trail only — this document is cumulative)

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
S15b    | not_started    | S15a✅,S4✅      | 5     | AT   | —
S14     | not_started    | S0 ✅            | 7     | UN   | —
S16     | not_started    | S10a ✅          | 9     | LT   | —
S17     | not_started    | S10a✅,S16       | 10    | AT   | —
S18     | not_started    | S10a ✅          | 9     | UN   | —
S19     | not_started    | S10a✅,S18       | 10    | LT   | —
S21     | not_started    | S15              | 11    | LT   | —
IT-1..5 | not_started    | various          | 12    | —    | —
BOOK-1  | not_started    | S4✅,S15         | 6-8   | OP   | —
```

**Total tests on main: 327 passing, 0 failures (as of cb358e2)**

## Completed Sessions

| Session | Completed | Exit Criteria | Key Output |
|---------|-----------|---------------|------------|
| INFRA | Day 1 early | All pass | Postgres 16, MinIO, PostgREST, API keys |
| S0 | Day 1 Block 1 | All 12 pass | Hermes v2026.4.3, CLIP/NIMA MPS, 82+ files |
| S1 | Day 1 Block 1 | All 9 pass | 25 config files, design index |
| S2 | Day 1 Block 1 | All 6 pass | 34 fonts, 11 Typst templates, 4 visual templates |
| SMOKE-1 | Day 1 B1→B2 | PASS | Design index textile+warm=1 match (data gap, accepted) |
| PATCH | Day 1 B1→B2 | All 8 pass | GEPA, connectors, mutation operators, eval cases |
| S4 | Day 1 Block 2 | All 10 pass | Tier 2 Kontext, Nano Banana GO, FLUX.2 GO. $4.46 total |
| S5 | Day 1 Block 2 | Partial (11/15 datasets) | 255 files, 58 design systems, quality frameworks |
| S6 | Day 1 Block 2 | All 12 pass | 52 tests, all contracts match CLAUDE.md §3 |
| S7 | Day 1 Block 2 | All 7 pass | 20 tests, sqlite3 spans |
| SMOKE-2 | Day 1 B2→B3 | PASS | NarrativeScaffold params: target_age, page_count |
| S8 | Day 1 Block 3 | All 5 pass | 23 tests, PolicyEvaluator 4 gates |
| S9 | Day 1 Block 3 | All 18 pass | 85 tests, 16 YAMLs, executor |
| S10a | Day 1 Block 4 | All 12 pass | 39 tests, 16 tables, MinIO, trace persist |
| S11 | Day 2 Block 5 | All 7 pass | 40 tests, routing, exemplar retrieval, design selector |
| S12 | Day 2 Block 5 | All 8 pass | 27 tests, research tools, seeding, contextualise_card |
| S13 | Day 2 Block 5 | All 11 pass | 43 tests, image gen, NIMA, 4-dim critique, guardrails |
| S15a | Day 1 Block 4 | All 13 pass | 21 tests, Typst assembly, EPUB, document templates |

## In-Progress Sessions

None actively running. S15b has a generated prompt (see Next Actions) but has not been launched.

## Deviations Register (CUMULATIVE)

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

## Operator Decisions (CUMULATIVE)

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
  Affects: S9 YAMLs need `draft_preview: nano-banana` added. Not yet done — bundle into S15b.

OD-007: FLUX.2 Pro photorealistic — GO
  Decision: Excellent product photography.
  When: Day 1 Block 2 (S4)
  Affects: image_model_preference photorealistic field.

OD-008: LoRA training — CONDITIONAL
  Decision: Viable for Tier 1 with 20+ real photos, not with 10 AI-generated images.
  When: Day 1 Block 2 (S4)
  Affects: Future Tier 1 projects only. Not sprint-blocking.

## Pending Decisions

- **Book 1 creative workshop** — not started. Operator hasn't begun character bibles, art style selection, or story scaffold.
- **S14 (Hermes fork patch)** — no issues reported so far. May not be needed. Decide after S15b.

## Next Actions

1. **Launch S15b** — illustration pipeline. Prompt already generated by Tower 002 (see below). All deps met: S15a ✅, S4 ✅. This is on the critical path to Book 1 and S21.

2. **Launch S16 + S18 in parallel** — both deps met (S10a ✅). Generate prompts for these.
   - S16: BizOps + Steward (tables, invoice, pipeline, morning brief, core Steward commands)
   - S18: Knowledge spine (retrieval pipeline, document set filtering)

3. **When S15b completes:** S15 is fully done. Unblocks S21 (extended artifact lanes) and Book 1.

4. **When S16 completes:** Unblocks S17 (dashboard).

5. **When S18 completes:** Unblocks S19 (self-improvement).

6. **S15b prompt (pre-generated, ready to launch):**
   See full prompt in HANDOVER_002_S15B_PROMPT.md (saved alongside this file).

7. **S16 + S18 prompts:** Successor tower should generate these. Read S16/S18 specs from VIZIER_BUILD_v1_3_1.md §7. Include tech scout injections:
   - S18: "If document_sets table exists from S10a, filter retrieval by document set membership instead of client_id tag"
   - S16: Wire `feedback_check_silence()` into a cron/timer (DEV-007)

8. **Minor patch needed:** Add `draft_preview: nano-banana` to image_model_preference in workflow YAMLs (OD-006). Bundle into S15b prompt.

9. **Add scikit-learn to pyproject.toml** — S12 installed it but didn't add to deps.

## Worktree State

- `/Users/Executor/vizier` (main) — at `cb358e2`, clean. All work merged.
- No active worktrees.
- Stale local branches exist: claude/beautiful-khorana, claude/cool-brown, claude/eager-turing, claude/fervent-kare, claude/mystifying-borg, claude/zealous-engelbart, s5, s8, s9. Can be pruned with `git branch -d <name>`.

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
- GitHub repo: https://github.com/khayroul/vizier (private)

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
- Design system selector is in `contracts/routing.py` — S17 must call `select_design_systems()`, NOT rebuild
- lru_cache on config loaders — call `.cache_clear()` if configs edited at runtime

**Research & retrieval (S12):**
- `from utils.retrieval import retrieve_similar_exemplars, encode_image, contextualise_card`
- `contextualise_card(card, source)` — both args are `dict[str, str]`
- `from tools.research import fetch_trends, ingest_swipe, check_calendar_events`
- `from tools.visual_dna import extract_visual_dna, populate_asset_visual_dna`
- `from tools.seeding import seed_client, seed_all_clients`
- Brand patterns in config/brand_patterns/, copy patterns in config/copy_patterns/

**Visual intelligence (S13):**
- `from tools.image import generate_image, select_image_model` — fire-and-forget generation
- `from tools.visual_scoring import critique_4dim, score_with_exemplars, nima_prescreen`
- `critique_4dim()` takes `image_description` (text), not raw bytes
- `from middleware.guardrails import run_parallel_guardrails, GuardrailMailbox`
- `from tools.visual_pipeline import run_visual_pipeline` — full brief→image→score→trace
- BM naturalness is fully deterministic (regex, zero tokens)

**Data foundation (S10a):**
- `from utils.database import get_cursor, run_migration` — RealDictCursor (rows are dicts)
- `from utils.storage import upload_bytes, download_bytes` — MinIO
- `from utils.trace_persist import persist_trace, load_trace, collect_and_persist`
- Feedback state machine: transitions via trigger. Invalid → `psycopg2.errors.RaiseException`
- `feedback_check_silence()` must be called periodically (no auto-timer)
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
- `check_visual_consistency()` is a STUB — S15b must wire CLIP into it
- STRATEGY_TEMPLATE_MAP maps TextPlacementStrategy → Typst template filename
- Images must exist on disk as absolute paths before calling assembly
- Typst source generated per-book (not importing templates) — templates have hardcoded content

**S4 illustration decisions:**
- Tier 2 — Kontext iterative: `fal-ai/flux-pro/kontext` (NOT `fal-ai/flux-kontext/pro`)
- API params: guidance_scale=3.5, output_format=jpeg, previous page as image_url
- Re-anchor every 8 pages from original reference
- CLIP threshold: 0.75 cropped character, ~0.65 full-page
- BM posters: `fal-ai/nano-banana-pro`
- Photorealistic: `fal-ai/flux-2-pro`
- Draft: `fal-ai/nano-banana` (free OpenRouter)
- Cost: ~$0.04/page Kontext

**Design index note:** textile+warm filter returns only 1 match (batik_air). Data gap, not bug. Accepted.

**Spans:** `@track_span` decorator, `call_llm()` auto-records. data/spans.db (sqlite3). Anthropic caching: `cache_control: {"type": "ephemeral"}`. Token-efficient tools: `anthropic-beta: token-efficient-tools-2025-02-19`.

**Tech scout checklist:** `/Users/Executor/vizier/docs/VIZIER_TECH_SCOUT_INJECTION_CHECKLIST.md` — read before generating worker prompts.

## Resume Instructions
To resume as the new control tower:
1. Read ~/executor/vizier/CLAUDE.md
2. Read ~/executor/vizier/docs/VIZIER_BUILD_v1_3_1.md §0-§6
3. Read ~/executor/vizier/docs/VIZIER_ARCHITECTURE_v5_4_1.md §0-§0.1 only
4. Read ~/executor/vizier/docs/VIZIER_TECH_SCOUT_INJECTION_CHECKLIST.md
5. Read THIS handover document (it is cumulative — you do NOT need HANDOVER_001)
6. You are the NEW control tower. Resume from the state above.
   Do NOT re-generate prompts for completed sessions.
   Check the Deviations Register for anything that changes downstream prompts.
   Begin with the "Next Actions" section.
