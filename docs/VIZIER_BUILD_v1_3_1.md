# VIZIER — BUILD PLAN

**Version:** 1.3.1  
**Date:** 7 April 2026  
**Status:** Single source of truth for execution. Hand this to Claude Code.  
**Architecture reference:** VIZIER_ARCHITECTURE.md (v5.4.1)  
**Supersedes:** VIZIER_BUILD.md v1.3.0, all prior execution plans.  
**Build model:** 3-day marathon. 4×3-hour blocks/day. 3-4 parallel CC sessions/block. Publishing is Core. Children's books and ebooks ship with the engine, targeting school holidays mid-May.

---

## Changes from v1.3.0

| # | Change | Rationale |
|---|--------|-----------|
| 1 | Architecture reference updated to v5.4.1 | Three-ring model + 9 enhancements added. |
| 2 | S6: StepTrace gains `proof: dict` field | Structured evidence per step feeds improvement loop for step-level correlation. |
| 3 | S9: Workflow executor merges `workflow_overrides` from client config | Per-client quality tuning without duplicating workflow YAMLs. ~10 lines. |
| 4 | S10a: `jobs` table gains `goal_chain jsonb` column | Links jobs to campaign/business goal ancestry for goal-level pattern detection. |
| 5 | S19: Benchmark additions — Sonnet 4.6 vs Opus, Flash-Lite for routing, Anthropic web search vs Tavily | April 2026 market context updates S19 benchmark plan. |

---

## Changes from v1.2.3

| # | Change | Rationale |
|---|--------|-----------|
| 1 | Renamed from vizier-supreme to vizier | Canonical build. All future upgrades base on this codebase. |
| 2 | Architecture reference updated to v5.4.0 | Aligned with architecture version bump. |
| 3 | Removed S10a from S9 `blocks` list | S10a depends on S6/S7/S8, not S9. Schedule already resolves ordering. |
| 4 | Standardised extended.sql as single DDL source | Each session runs `psql -f migrations/extended.sql` as preamble. No inline DDL. |

---

## Changes from v1.1.0

| # | Change | Rationale |
|---|--------|-----------|
| 1 | Split S10 into S10a (core tables) and S10b (extended tables on-demand) | Unblock Day 2 earlier. Remove sequential bottleneck. |
| 2 | Move Book 1 creative workshop to evening of Day 1 | Deconflict Block 4. Workshop is OPERATOR-ONLY — no CC needed. |
| 3 | Add 1-hour integration buffers at start of Day 2 and Day 3 | Catch integration failures early instead of discovering them in Block 12. |
| 4 | Pre-download all datasets and clone repos night before sprint | Remove network latency from critical path. |
| 5 | Prioritize S5 extractions by downstream dependency | Visual brief expander + quality framework + composition grammar first (blocks S13). |
| 6 | Define 5 integration tests for SHIP gate | No ambiguity about what "SHIP" means. |
| 7 | Define ship criteria (3 gates) | Poster end-to-end + children's book specimen + gateway routing. |
| 8 | Extract shared functions: contextualise_card and retrieve_similar_exemplars | Built once, imported by multiple sessions. No rebuild. |
| 9 | Test workflow executor against simple AND complex workflows in S9 | Catch executor bugs on Day 1, not Day 2. |
| 10 | Make all migrations idempotent (IF NOT EXISTS) | Safe re-run if S10a fails partway. No data loss. |
| 11 | Pro-max migration: assets only, no data | All prior client data is mock. Clean start. |
| 12 | GPT-5.4-mini for ALL tasks Month 1-2 including creative prose | One model, one code path, one failure mode. Anti-drift #54. |
| 13 | Add design system selector to S1 config authoring | 55 → 3 candidates via deterministic matching. |
| 14 | Add rework workflow YAML to S9 | Post-delivery correction path. |
| 15 | Add derivative workshop fast-path to S15 | Books 2-10: 45-60 min workshop vs 2-4 hours. |
| 16 | Add git init, .gitignore, worktrees to S0 | Parallel CC sessions need isolated working directories. Missing from v1.2.0. |
| 17 | S0 creates `utils/retrieval.py` with function stubs (NotImplementedError) | S11 and S12 both edit same file — stubs prevent merge conflicts. |
| 18 | Split `tools/image.py` and `tools/illustrate.py` | image.py = fire-and-forget generation; illustrate.py = stateful sequential illustration pipeline. Re-merge if >70% code overlap. |
| 19 | Fix S16 dependency description | S16 DOES depend on S10a (FK references). Corrected misleading "does not depend" language. |
| 20 | Local-first data stack: Postgres + MinIO + PostgREST | Replaces Supabase. Zero cost, zero tier limits, zero network latency. LifeOS bridge removed (data stripped). |
| 21 | Steward personal assistant in S16 | GTD + ADHD-friendly PA on separate Telegram bot. 4 tables, `tools/steward.py`, `config/personas/steward.md`. Replaces LifeOS bridge. |

---

## 0. Execution Principles

E1 — Core + Publishing ships first. Get paid.  
E2 — One capability per session.  
E3 — Priority: publishing + production quality → research → social → websites.  
E4 — Use existing systems (P14). pip install before custom code.  
E5 — Datasets are fuel, not features. No hard runtime dependency.  
E6 — Train later, produce now. GPT-5.4-mini for everything Month 1-2.  
E7 — The moat is compounding data.  
E8 — Publishing is Core. School holidays mid-May = revenue deadline.  
**E9 — One model Month 1-2. GPT-5.4-mini for ALL tasks including creative prose. Multi-model activates after S19 benchmark only. (Anti-drift #54.)**

### Model Strategy (Month 1-2)

GPT-5.4-mini handles ALL tasks: scoring, routing, guardrails, memory, AND creative prose (EN and BM). Qwen local is OFF for production. Claude Opus, Claude Sonnet, Gemini 3.1 Pro, Gemini 2.5 Pro are available in credential pools but NOT routed to by any WorkflowPack YAML. Daily usage ~310K tokens = 3.1% of 10M/day free budget.

Month 3+: S19 benchmark validates prose routing map (10 briefs × Claude/Gemini/GPT × EN+BM). Update WorkflowPack YAMLs with validated model assignments. Fine-tune Qwen 4B (quality scorer) and 2B (routing + register classifier) on production data. Migrate narrow tasks to local only after >80% correlation validated.

### Quality Strategy

Launch at Canva-baseline quality posture. 8 quality techniques configured per-workflow via YAML:

1. Self-Refine (critique-then-revise), 2. Iterative rubric refinement, 3. Exemplar injection, 4. Structured critique chain, 5. Expert persona, 6. Silver→Gold ratchet, 7. Contrastive examples, 8. Domain vocabulary. First 5-10 jobs per client are deliberate calibration rounds.

### Claw-Code Patterns (absorbed, not installed)

Skeptical Memory → S0 (.hermes.md)  
3-Gate Cron Triggers → S16 (cron jobs)  
Parity Audit → S0 (docs/parity_audit.yaml)  
Graduated Context Compaction → S9 (WorkflowPack YAML context_strategy)  
Guardrail Mailbox → S13 (quality gate dedup)

---

## 1. Attention Classification

**UNATTENDED** — Fully specified. Claude Code builds autonomously.  
**LIGHT-TOUCH** — Mostly autonomous. 1-2 decision points.  
**ATTENDED** — You're actively steering.  
**OPERATOR-ONLY** — Your work. Creative decisions, asset curation.

---

## 2. Pre-Sprint Checklist (Night Before)

Complete ALL of the following before Day 1 Block 1:

- [ ] Pre-download all 15 datasets (D1-D15) to local storage. Verify checksums. ~6GB total.
  - [ ] For each HuggingFace dataset: verify download completes without approval gate. If gated, request access NOW.
  - [ ] D12 (PosterIQ): verify source URL resolves — if behind academic paywall, search for arXiv supplementary materials or GitHub mirror.
  - [ ] D13 (UiTM Manglish): verify CC BY licence file present in download.
  - [ ] If ANY dataset fails to download, note it and proceed — S5 priority ordering means Hour 1 extractions (D3, D4, D12, R3) are blocking; Hours 3-4 are non-blocking.
- [ ] Clone all 6 repos (R1-R6) to local storage.
- [ ] Verify vizier-pro-max exists at `~/executor/vizier-pro-max` — S0 ports assets from it.
- [ ] Verify fal.ai API key works (test one image generation call)
- [ ] Set up Langfuse project (free tier)
- [ ] Install Postgres 16 locally (`brew install postgresql@16`), create `vizier` database, enable pgvector (`CREATE EXTENSION IF NOT EXISTS vector`), enable FTS
- [ ] Install and start MinIO (`brew install minio` or Docker, create `vizier-assets` bucket)
- [ ] Install PostgREST (`brew install postgrest`), verify it serves the `vizier` database schema
- [ ] Create HuggingFace account if needed
- [ ] Check Anthropic + Google AI + OpenAI API keys
- [ ] Prepare Book 1 premise (even 1 sentence + target age group + art style preference)
- [ ] Start Book 1 character concepts (rough notes — full bibles authored during evening of Day 1)

**Post-sprint admin (DO NOT block sprint — start process now, results arrive later):**

- [ ] Apply for Meta Business verification (takes weeks — needed for S24)
- [ ] Apply for TikTok API access (takes weeks — needed for S24)

**Why pre-download matters:** S5 processes 15 datasets and 6 repos. If any dataset requires authentication, has changed URLs, or downloads slowly, you discover it now — not mid-sprint when S5 is blocking S13.

---

## 3. 3-Day Marathon Schedule

### DAY 1: Foundation + Contracts + Endpoints

**BLOCK 1 (3 hrs):**

```
├── CC-A: S0 Repo scaffold
├── CC-B: S1 Config authoring (incl design_system_index.yaml)
├── CC-C: S2 Typst + fonts + templates
└── YOU: Start S3 asset collection
```

**BLOCK 2 (3 hrs):**

```
├── CC-A: S5 Dataset processing (priority extractions first)
├── CC-B: S6 ALL governance contracts
├── CC-C: S7 Spans + memory routing
└── CC-D + YOU: S4 Endpoint testing
```

⚡ ILLUSTRATION PIPELINE DECIDED END OF BLOCK

**BLOCK 3 (3 hrs):**

```
├── CC-A: S8 Policy + observability
├── CC-B: S9 Packs + workflows + tripwire + rework YAML
├── CC-C: Continue S5
└── YOU: Start Book 1 creative workshop (conceptual work — high energy)
    ├── Write premise → expanded synopsis
    ├── Author story bible YAML (world, settings, sensory, cultural context)
    ├── Define 8-page structural scaffold with word targets and arc beats
    └── Define checkpoints (failure point, breakthrough, lesson learned)
```

**BLOCK 4 (3 hrs):**

```
├── CC-A: S10a Data foundation (14 CORE tables only) — SEQUENTIAL
├── CC-B: S15 partial — assembly pipeline (tools/publish.py, tools/illustrate.py)
└── YOU: Continue S3
```

**EVENING (post-blocks, 1.5-2 hrs — OPERATOR-ONLY, no CC needed):**

```
└── YOU: Complete Book 1 creative workshop (structured YAML work — lower energy)
    ├── Author 2 character bible YAMLs (§42.1 schema — hex colours, clothing, style notes)
    ├── Select art style direction from S4 results
    └── Review scaffold + checkpoints from Block 3 with fresh eyes
```

### DAY 2: Routing + Research + Visual + Book 1

**INTEGRATION BUFFER (1 hr — start of day):**

```
├── Test 1: Create mock poster request → fast-path routes to poster_production
│   at zero tokens → verify RoutingResult stored on job record
├── Test 2: Run poster_production workflow with stub tools → verify
│   TraceCollector captures steps → verify Langfuse trace appears with metadata
├── Test 3: Deliver stub artifact → verify feedback trigger fires →
│   wait 24hrs (simulated) → verify silence_flagged state transition
└── Fix anything broken before launching parallel blocks
```

**BLOCK 5 (3 hrs):**

```
├── CC-A: S11 Routing + multi-model (all model_preference = gpt-5.4-mini)
├── CC-B: S12 Research + seeding
├── CC-C: S13 Visual intel + guardrails
└── CC-D: S15 complete — workflow wiring
```

**BLOCK 6 (3 hrs):**

```
├── CC-A/B/C: Continue S11/S12/S13
└── YOU + Vizier: BOOK 1 pages 1-4
```

**BLOCK 7 (3 hrs):**

```
├── CC-A: S14 Hermes patch (if needed)
├── CC-B: Integration testing (IT-1 through IT-3)
└── YOU + Vizier: BOOK 1 pages 5-8 + assembly + cover
```

**BLOCK 8 (3 hrs):**

```
├── CC-A: Fix issues from integration tests
├── YOU: Book 1 polish + KDP prep
└── YOU + Vizier: BOOK 2 creative workshop (DERIVATIVE fast-path: 60-90 min — first derivative run, allow extra validation)
```

### DAY 3: Extended + Books 2-3 + Ship

**INTEGRATION BUFFER (1 hr — start of day):**

```
├── Test 1: Vague BM brief "buatkan poster Raya untuk DMB" → LLM routing
│   classifies correctly → refinement loop runs 1 cycle → production stub
│   generates → NIMA pre-screen runs → 4-dim critique fires → delivery
├── Test 2 (IT-4): Query "Raya batik promotion DMB" → 4 query variants
│   generated → hybrid search returns pgvector + FTS results → reranking
│   selects top 5 → contextual prefixes present on returned cards
├── Test 3: Knowledge retrieval returns client brand config + seasonal
│   context for a poster job (verify lazy retrieval doesn't over-inject)
└── Fix anything broken
```

**BLOCK 9 (3 hrs):**

```
├── CC-A: S16 BizOps + Steward + 3-gate crons (creates own extended tables)
├── CC-B: S18 Knowledge spine (creates own extended tables)
├── YOU + Vizier: BOOK 2 production
└── Book 1 → KDP + Shopee
```

**BLOCK 10 (3 hrs):**

```
├── CC-A: S17 Dashboard
├── CC-B: S19 Self-improvement (creates own extended tables)
└── YOU + Vizier: Book 2 assembly + BOOK 3 workshop (DERIVATIVE, 45-60 min)
```

**BLOCK 11 (3 hrs):**

```
├── CC-A: S21 Extended artifact lanes
├── CC-B: Ebook production
└── YOU: Book 3 production + Book 2 upload
```

**BLOCK 12 (3 hrs):**

```
├── Run all 5 integration tests (IT-1 through IT-5)
├── Fix anything broken
├── Book 3 upload + Ebook published
└── SHIP
```

### Critical Path

```
S0 → S6 → S8/S9 → S10a → S11/S12/S13/S15 (parallel) → SHIP
```

### Collision Rules

Sessions touching SAME directories must be sequential. Sessions touching DIFFERENT directories run in parallel via git worktrees.

---

## 4. Ship Criteria

Core is shippable when all three gates pass:

**Gate 1 — Poster Production End-to-End:**  
Vague BM brief → LLM routing or fast-path → refinement (if shapeable) → production with visual brief expansion → NIMA pre-screen → 4-dimension critique → trace captured (StepTrace + Langfuse) → feedback state machine triggers → delivery message via Telegram.

**Gate 2 — Children's Book Specimen:**  
Creative workshop loads CharacterBible + StoryBible + NarrativeScaffold → specimen page produced (text with self-refine + illustration from `illustration_shows` field) → Typst assembly with text overlay on text-free illustration → operator review checkpoint functional.

**Gate 3 — Gateway Routing:**  
Telegram gateway receives a request → Hermes processes → fast-path resolves "poster DMB" at zero tokens OR LLM classification resolves ambiguous request → correct workflow selected → RoutingResult stored on job record.

**Extended sessions (S16-S19) shipping at 70% completion is acceptable.** They build from revenue.

---

## 5. Integration Test Suite

Five integration tests (defined in architecture §26.2). IT-1 through IT-3 run on Day 2 Block 7. IT-4 and IT-5 run on Day 3 integration buffer and Block 12.

**IT-1: Poster from vague brief.**  
Input: "buatkan poster Raya untuk DMB" via Telegram.  
Expected: LLM routing → poster_production workflow → refinement (1-2 cycles) → production → NIMA pre-screen → 4-dim critique → visual lineage recorded → trace in Langfuse → feedback trigger fires → delivery message.

**IT-2: Children's book specimen page.**  
Input: Load Book 1 creative workshop outputs.  
Expected: text_gen produces page 1 text with persona + self-refine → illustrate produces text-free image from `illustration_shows` → CLIP similarity against character references > 0.75 → Typst assembly renders PDF with text overlay → operator_review stage presents for approval.

**IT-3: Fast-path routing.**  
Input: "poster DMB" via Telegram.  
Expected: fast-path pattern match → poster_production workflow at zero tokens → no LLM classification call → RoutingResult stored with `routing_method: fast_path`.

**IT-4: Knowledge retrieval pipeline.**  
Input: query "Raya batik promotion DMB".  
Expected: query transformation generates 4 variants (BM + EN) → hybrid search returns results from both pgvector AND Postgres FTS → RRF merge → cross-encoder reranking selects top 5 → lost-in-the-middle reordering applied → contextual prefixes present on all returned cards.

**IT-5: Feedback state machine.**  
Input: deliver artifact → wait 24hrs (simulated via direct DB timestamp manipulation).  
Expected: `awaiting_feedback` → `silence_flagged` trigger fires → one follow-up message sent → if response received: `responded` state → if no response: `unresponsive` state.  
Verify: `silence_flagged` excluded from quality calculations.

---

## 6. Session Reference

| ID | Name | Attn | Hrs | Lines | Hard Deps | Day.Block |
|----|------|------|-----|-------|-----------|-----------|
| S0 | Repo scaffold + assets | UN | 2-3 | 0 | — | 1.1 |
| S1 | Config authoring | UN | 2-3 | 0 | S0 | 1.1 |
| S2 | Typst + fonts + templates | UN | 2-3 | 0 | S0 | 1.1 |
| S3 | Asset collection | OP | ongoing | 0 | — | 1-3 |
| S4 | Endpoint testing | AT | 2-3 | 0 | S0 | 1.2 |
| S5 | Dataset processing | UN | 3-4 | 0 | S0, pre-download | 1.2-1.3 |
| S6 | Governance contracts | UN | 3-4 | 500-650 | S0 | 1.2 |
| S7 | Spans + memory routing | UN | 2-3 | 200-250 | S0 | 1.2 |
| S8 | Policy + observability | UN | 2-3 | 250-350 | S6 | 1.3 |
| S9 | Packs + workflows + tripwire | LT | 3-4 | 300-400 | S6 | 1.3 |
| **S10a** | **Data foundation (CORE)** | **LT** | **2-2.5** | **250-300** | **S6,S7,S8** | **1.4** |
| S11 | Routing + multi-model | LT | 3-4 | 450-550 | S10a | 2.5-2.6 |
| S12 | Research + seeding | LT | 3-4 | 350-450 | S10a | 2.5-2.6 |
| S13 | Visual intel + guardrails | AT | 3-4 | 450-550 | S10a | 2.5-2.6 |
| S14 | Hermes fork patch | UN | 0-3 | 0-100 | S0 | 2.7 |
| S15 | Publishing lane | AT | 4-6 | 500-650 | S10a,S9,S2,S6 | 1.4+2.5 |
| S16 | BizOps + Steward + crons | LT | 4-5 | 550-750 | S10a | 3.9 |
| S17 | Dashboard | AT | 3-4 | 200-300 | S10a,S16 | 3.10 |
| S18 | Knowledge spine | UN | 3-4 | 250-350 | S10a | 3.9 |
| S19 | Self-improvement | LT | 3-4 | 350-450 | S10a,S18 | 3.10 |
| S21 | Extended artifacts | LT | 3-4 | 300-400 | S15 | 3.11 |

**Core + Publishing:** ~3,200-4,200 lines (reduced from v1.1 due to S10 split and shared functions).  
**With Extended Ops (Day 3):** ~5,000-6,500 lines.

---

## 7. Session Specifications

### S0 — Repo Scaffold + Asset Port

```
id: S0
attention: UNATTENDED
duration: 2-3 hours
code: 0 (structure only)
depends_on: []
parallel_with: [S1, S2, S3]
blocks: [everything]
day: 1, block: 1
```

**Directories touched:**

```
vizier/
├── hermes-agent/                 # submodule v0.7.0
├── .hermes.md                    # includes skeptical memory rule
├── AGENTS.md
├── CLAUDE.md
├── contracts/                    # empty structure
├── middleware/
├── tools/
├── plugins/
├── manifests/workflows/
├── config/                       # full subdir structure including:
│   ├── personas/
│   ├── vocab/
│   ├── critique_templates/
│   ├── character_templates/
│   └── story_bible_templates/
├── templates/                    # ported from pro-max (ASSETS ONLY)
│   ├── visual/
│   ├── documents/
│   ├── typst/
│   └── web/
├── augments/listening/           # ported from pro-max
├── evaluations/reference_corpus/
├── migrations/                   # NEW — core.sql and extended.sql
├── utils/                        # NEW — shared functions
├── docs/
│   ├── decisions/
│   └── parity_audit.yaml
├── tests/
└── pyproject.toml
```

**What Claude Code does:**

- **Git repository setup (FIRST action):**
  - `git init vizier/`
  - Create `.gitignore`:
    ```
    __pycache__/
    *.pyc
    .env
    .env.*
    datasets/
    *.sqlite
    *.db
    .DS_Store
    node_modules/
    *.safetensors
    .ollama/
    *.egg-info/
    dist/
    build/
    .venv/
    ```
  - Add Hermes Agent as submodule: `git submodule add --branch v0.7.0 https://github.com/NousResearch/hermes-agent.git hermes-agent`
  - Initial commit: `chore(s0): scaffold repo structure`
  - Create GitHub remote `vizier` and push
  - **Set up git worktrees for parallel CC sessions:**
    ```bash
    # Block 1 parallel sessions
    git worktree add ../vizier-s1 main    # S1 config authoring (config/)
    git worktree add ../vizier-s2 main    # S2 Typst + fonts (assets/, templates/)
    # Block 2 parallel sessions
    git worktree add ../vizier-s5 main    # S5 dataset processing (config/)
    git worktree add ../vizier-s6 main    # S6 governance contracts (contracts/)
    git worktree add ../vizier-s7 main    # S7 spans (utils/, plugins/)
    ```
    Worktrees enable parallel CC sessions on different directories without merge conflicts. Each CC session works in its own worktree, merges to main between blocks. Operator creates new worktrees as needed for subsequent blocks.
- Create vizier directory structure (architecture §25)
- Diff vizier-gate2-patch against v0.7.0 → `docs/decisions/hermes_fork_decision.md`
- **Port from pro-max (ASSETS ONLY — see exact paths below)**
- `pyproject.toml` with all deps
- `.hermes.md` with skeptical memory instruction
- Create `docs/parity_audit.yaml` mapping all §35 capabilities to status: planned
- Create `utils/__init__.py` and `utils/retrieval.py` with **function stubs** — full signatures and docstrings from CLAUDE.md §3, bodies are `raise NotImplementedError("Populated by S11/S12")`. S11 fills in `retrieve_similar_exemplars()`, S12 fills in `contextualise_card()`. Stubs prevent merge conflicts when both sessions edit the same file.
- Create `migrations/` directory with placeholder `core.sql` and `extended.sql`
- Validate CLIP ViT-B/32 on Mac Mini M4 via MPS
- Validate NIMA MobileNet aesthetic model on Mac Mini M4
- Fork decision doc produced

**Pro-max port — exact paths:**

Clone `https://github.com/khayroul/vizier-pro-max.git` as read-only reference (already available locally at `~/executor/vizier-pro-max`). Copy ONLY these paths into vizier:

```
FROM vizier-pro-max                    → TO vizier
─────────────────────────────────────────────────────────
templates/visual/*.html (30 files)     → templates/visual/
templates/visual/stock-heroes.json     → templates/visual/
templates/documents/*.html (6 files)   → templates/documents/
templates/typst/*.typ (2 files)        → templates/typst/
augments/listening/ (entire dir)       → augments/listening/
scripts/visual/screenshot_html.py      → scripts/visual/screenshot_html.py
scripts/visual/generate_image.py       → scripts/visual/generate_image.py
middleware/quality_gate.py             → middleware/quality_gate.py (visual QA utilities only)
evaluations/reference_corpus/rubric.yaml        → evaluations/reference_corpus/
evaluations/reference_corpus/suite.yaml         → evaluations/reference_corpus/
evaluations/reference_corpus/poster_ui_suite.yaml → evaluations/reference_corpus/
evaluations/reference_corpus/milestones.yaml    → evaluations/reference_corpus/
pyproject.toml                         → pyproject.toml (merge deps, don't overwrite)
config/clients/_schema.yaml            → config/clients/_schema.yaml
```

**DO NOT port any of the following:**
- `adapter/` — replaced by Hermes runtime
- `bridge/` — replaced by Hermes gateway
- `pipelines/` — replaced by WorkflowPack YAMLs + generic executor
- `plugins/` — replaced by contracts + middleware
- `references/` — replaced by config/design_systems/ (55 DESIGN.md files from S5)
- `augments/` (except listening/) — replaced by Langfuse, S19 improvement loop
- `config/clients/*.yaml` (except _schema.yaml) — clean start, operator authors fresh configs in S3
- `evaluations/reference_corpus/results/` — old eval results, not portable
- Any `.db`, `.sqlite`, `.json` data files — mock data, discard

**Exit criteria:**

- Git repo initialised, `.gitignore` committed, pushed to GitHub
- Hermes v0.7.0 submodule wired and checked out
- Git worktrees created for Block 1 parallel sessions (S1, S2) and Block 2 (S5, S6, S7)
- Pro-max ASSETS ported (templates, listening engine, stock images). NO client data, NO knowledge cards, NO exemplars.
- pyproject.toml installs clean
- .hermes.md includes skeptical memory instruction
- parity_audit.yaml exists with all capabilities listed
- `utils/retrieval.py` contains stubs for `contextualise_card()` and `retrieve_similar_exemplars()` with full signatures, docstrings, and `NotImplementedError` bodies
- CLIP runs on MPS
- NIMA aesthetic scoring runs locally
- Fork decision doc produced
- Repo on GitHub with full directory structure including `migrations/` and `utils/`

---

### S1 — Config Authoring

```
id: S1
attention: UNATTENDED
duration: 2-3 hours
code: 0 (config only)
depends_on: [S0]
parallel_with: [S2, S5]
blocks: [S9]
day: 1, block: 1
```

**Directories touched:** `config/` only

**What Claude Code does:**

- `config/phase.yaml` — phase activation flags (publishing as Core phase, not Extended)
- `config/artifact_taxonomy.yaml` — complete taxonomy from §17
- `config/fast_paths.yaml` — deterministic routing patterns covering: poster, document, invoice, research, brochure, content_calendar, social_batch, childrens_book, ebook
- `config/retrieval_profiles.yaml` — knowledge retrieval config by artifact type
- `config/calendar/malaysia_2026.yaml` — ~50 events with prep windows
- `config/document_scaffolds/` — 6 scaffolds (proposal, plan, report, profile, invoice, calendar)
- `config/content_strategies.yaml` — industry × channel × objective mappings
- `config/social_platforms.yaml` — platform sizing and content density rules
- `config/autonomy_rules.yaml` — social media autonomy levels per action type
- `config/personas/childrens_author_bm.md` — BM children's book expert persona
- `config/personas/marketing_director_my.md` — Malaysian marketing expert persona
- `config/personas/business_consultant.md` — business document expert persona
- **`config/personas/steward.md`** — Steward personal assistant persona. GTD-based, ADHD-friendly. Voice: warm, concise, never overwhelming. Always presents options via tap buttons, never open-ended questions. Shows ONE task at a time. Celebrates completions with streak/domain progress. Uses Islamic greetings naturally. BM/EN code-switching matching operator's register. Knows prayer times. Never nags — one gentle nudge, then silence until asked.
- `config/vocab/bm_children_5_7.yaml` — age-appropriate BM word list (20+ terms)
- `config/vocab/bm_marketing.yaml` — Malaysian marketing BM terms: diskaun, percuma, tawaran, jom, etc. (20+ terms)
- `config/critique_templates/childrens_narrative.md` — dimension-specific critique prompts for children's text: age vocabulary, narrative momentum, cultural authenticity, emotional arc. **Output format: structured JSON** with dimension, score, issues array, revision_instruction.
- `config/critique_templates/poster_quality.md` — dimensions: CTA visibility, text readability, colour contrast, layout balance, brand alignment. **Output format: structured JSON.**
- `config/critique_templates/document_coherence.md` — dimensions: section-to-section logic, claims consistency, executive summary alignment. **Output format: structured JSON.**
- **`config/code_switching/rules.yaml`** — extracted from 500 sampled Manglish Twitter posts via Claude. Contains: trigger taxonomy (noun insertion, discourse markers, phrase-boundary switching with syntactic patterns), particle grammar (lah/mah/lor/kan/wei/eh with position rules), register-to-ratio mapping (formal 90:10, casual 60:40, youth 40:60), platform patterns (instagram→casual, facebook→formal, poster→none, children_book→none). See §38.6.
- **`config/design_system_index.yaml`** — tags all 55 design systems with: `industry` (list of 1-5 tags), `density` (minimal/moderate/dense), `mood` (list of 1-3 tags), `colour_temperature` (warm/cool/neutral). See architecture §38.1.1.

**Exit criteria:**

- All config files parse as valid YAML/markdown
- Calendar has ≥40 events with prep_window_days
- Fast paths cover 9+ artifact types
- 4 persona files with expert role descriptions (100+ words each, including steward.md)
- 2 vocabulary files with 20+ terms each
- 3 critique template files with dimension-specific prompts in structured JSON format
- code_switching/rules.yaml contains trigger taxonomy, particle grammar, register-to-ratio mapping, platform patterns
- `design_system_index.yaml` tags all 55 design systems with 4 attributes each
- Verify: given client config `industry: textile, brand_mood: [warm, traditional]`, a simple grep/filter returns 3-5 matching systems (not 55)

---

### S2 — Typst + Fonts + Templates

```
id: S2
attention: UNATTENDED
duration: 2-3 hours
code: 0 (templates only)
depends_on: [S0]
parallel_with: [S1, S5]
blocks: [S15]
day: 1, block: 1
```

**Directories touched:** `assets/fonts/`, `templates/typst/`, `templates/visual/`

**What Claude Code does:**

- Download fonts: IBM Plex Serif, Inter, Plus Jakarta Sans, Amiri → `assets/fonts/`
- Create 4 Typst document templates: proposal, company profile, report, content calendar
- Create 5 Typst children's book layout variants:
  - full-bleed (illustration fills page, text in overlay box)
  - split (left text, right illustration or vice versa)
  - text-overlay (text over semi-transparent bar on illustration)
  - facing-pages (text on left page, illustration on right)
  - single-page (illustration top, text bottom)
- Create 1 Typst ebook template (chapter layout, ToC, cover page)
- Create 1 Typst invoice template (SSM, bank details, itemised)
- Generate 8-10 core visual template patterns for social media (Canva-baseline quality)
- Test rendering with curated fonts (Latin + Jawi)

**Exit criteria:**

- 4 document templates render sample pages
- 5 children's book layouts render with placeholder text + image
- 1 ebook template renders with 3-chapter sample
- 1 invoice template renders with test data
- 8-10 visual templates render at correct platform sizes
- Fonts installed and render in Typst

---

### S3 — Asset Collection (Operator Only)

```
id: S3
attention: OPERATOR-ONLY
duration: spread across all 3 days
depends_on: []
parallel_with: [ALL]
blocks: [S12]
```

**What YOU do:**

- Collect 200+ Malaysian marketing screenshots (swipe file)
- Curate 30-50 real BM marketing copy samples from real brands
- Write client configs: `config/clients/dmb.yaml`, `ar_rawdhah.yaml`, `rempah_tok_ma.yaml`
- Author 20+ brand pattern files in `config/brand_patterns/`
- Expand Terengganu dialect YAML with 50+ substitutions
- **Book 1 creative workshop** split across Day 1 Block 3 + evening:
  - **Block 3 (high energy, conceptual):** Write premise → expanded synopsis. Author story bible YAML (world, settings, sensory, cultural context). Define 8-page structural scaffold with word targets and arc beats. Define checkpoints (failure point, breakthrough, lesson learned).
  - **Evening (lower energy, specification):** Author 2 character bible YAMLs following §42.1 schema (hex colours, clothing variants, style notes). Select art style direction from S4 results. Review scaffold + checkpoints with fresh eyes.
- **NOT ported:** No prior client deliverables promoted to exemplar status. All three clients start with zero exemplars. Exemplar library grows entirely from production output rated 5/5 by operator.

**Exit criteria:**

- 200+ screenshots saved
- 30+ BM copy samples curated
- 3 client config YAMLs authored (zero exemplar references — clean start)
- 20+ brand pattern files
- Book 1: premise, story bible, 8-page scaffold, checkpoints defined (Block 3) + 2 character bibles, art style selected (evening Day 1)

**Collection priority (S12 ingests whatever S3 has by Day 2 Block 5):** Collect the 30 BM copy samples first — they seed knowledge cards immediately and directly improve production output. Screenshots second — they seed visual DNA which enriches production but doesn't block it. More assets = richer seed corpus, but S12 won't wait for S3 to finish.

---

### S4 — Endpoint Testing

```
id: S4
attention: ATTENDED
duration: 2-3 hours
code: 0 (docs only)
depends_on: [S0]
parallel_with: [S5, S6, S7]
blocks: [S13, S15]
day: 1, block: 2
```

**What you and Claude Code do:**

**Illustration consistency testing (CRITICAL — determines publishing pipeline):**

- Test FLUX.1 Kontext pro: generate 1 character from description, produce 8 sequential pages using iterative editing. Measure consistency page-to-page — does the character remain recognisable? Score 1-5 per page.
- Test FLUX General + IP-Adapter: generate 3 reference images, produce 5 pages with IP-Adapter conditioning. Compare consistency vs Kontext.
- Test Nano Banana Pro multi-reference: same character, 3 pages with 3 references. Evaluate BM text rendering quality simultaneously.
- Test FLUX.2 multi-reference: same character, 3 pages with 2 references. Cheapest option.
- **Test LoRA training (Tier 1):** Train a test character LoRA on fal.ai (10 images → train → generate 5 diverse scenes). Measure consistency vs Kontext and IP-Adapter on same character. Document cost and training time.
- **Test multi-LoRA composition:** Compose character LoRA + style LoRA (+ optional test product LoRA). Verify all adapters activate simultaneously without interference. Document any weight tuning needed.
- **Test character-cropped CLIP verification:** Crop character bounding box from generated pages, compute CLIP similarity against references. Compare cropped vs full-page similarity scores — cropped should be more stable.
- **DECISION:** Which tier achieves ≥80% character consistency across 8 pages? Is LoRA training viable within time/cost constraints? Document in `docs/decisions/illustration_pipeline.md`

**Other endpoint tests:**

- Nano Banana Pro BM text quality: 5 posters with BM copy (pricing, phone numbers) — go/no-go
- FLUX.2 Pro photorealistic: 3 product photography scenes
- MaLLaM feasibility on Mac Mini M4 alongside Ollama

**Illustration pipeline fallback (v1.2 addition):** If no path achieves ≥80% consistency across 8 pages, use the best-performing path + operator review checkpoint every 4 pages. Document actual consistency scores and selected path in `docs/decisions/illustration_pipeline.md`. Do NOT block the publishing pipeline — degrade gracefully with human checkpoints.

**Forced decision rule:** A tier MUST be selected and committed to `docs/decisions/illustration_pipeline.md` by the end of Block 2. No "still evaluating" state allowed past this point. S15 Day 2 reads this file. Rank tiers by measured consistency score and select the highest, even if below 80%. The operator review checkpoint compensates for lower-consistency tiers. An imperfect decision beats an open decision.

**Exit criteria:**

- Illustration pipeline tier selected and documented
- Kontext consistency score across 8 pages recorded
- IP-Adapter consistency score across 5 pages recorded
- LoRA training tested — consistency score, cost, time recorded
- Multi-LoRA composition verified — no adapter interference
- Character-cropped CLIP scores compared to full-page CLIP scores
- Nano Banana Pro BM text rendering assessed — go/no-go
- All decisions in `docs/decisions/`

---

### S5 — Dataset Processing + Design Intelligence

```
id: S5
attention: UNATTENDED
duration: 3-4 hours
code: 0 (config + knowledge output)
depends_on: [S0, PRE-DOWNLOADED datasets]
parallel_with: [S1, S2, S4, S6, S7]
blocks: [S13]
day: 1, blocks: 2-3
```

**PRIORITY ORDER for extractions (by downstream dependency):**

**Datasets (pre-downloaded night before):**

```
D1  — HQ-Poster-100K (captions + 2K images)     ~2.5GB   HuggingFace
D2  — Poster-Preference-100K (5K subset)         ~200MB   HuggingFace
D3  — Poster-Reflect-120K (5K subset)            ~200MB   HuggingFace
D4  — CGL-Dataset V2 (annotations)               ~500MB   HuggingFace
D5  — Magazine Layout (annotations)               ~200MB   HuggingFace
D6  — AdImageNet (9K images + text)               ~2GB    HuggingFace
D7  — Ads_Creative_Text_Programmatic              ~50MB   HuggingFace
D8  — marketing_social_media                      ~20MB   HuggingFace
D9  — PKU-PosterLayout                            ~300MB  HuggingFace
D10 — Children-Stories-Collection (10K subset)    ~100MB  HuggingFace
D11 — AdParaphrase                                ~10MB   GitHub
D12 — PosterIQ (7,765 annotated posters)          ~TBD    arXiv/GitHub
D13 — UiTM Manglish X corpus (650K posts)         ~200MB  ScienceDirect (CC BY)
D14 — MalayMMLU (24,213 BM questions)             ~50MB   GitHub UMxYTL-AI-Labs
D15 — Tatabahasa BM grammar (349 questions)        ~1MB   GitHub mesolitica
```

**Repos (pre-cloned night before):**

```
R1  — awesome-design-md (55 systems)    3.8MB   VoltAgent/GitHub
R2  — electric-book                     310MB   electricbookworks/GitHub
R3  — PosterCraft                       53MB    MeiGen-AI/GitHub
R4  — Infographic (antvis)              8.3MB   antvis/GitHub
R5  — AdParaphrase                      ~5MB    CyberAgentAILab/GitHub
R6  — Code-Switch-Language-Modeling-EN-Malay  ~5MB   kjgpta/GitHub
```

**Hour 1 — Blocks S13 (MUST complete before Day 2):**

1. Extract visual brief expander from PosterCraft recap agent (R3) → `config/prompt_templates/visual_brief_expander.md`
2. Extract quality framework from D3 → `config/quality_frameworks/poster_quality.md`
3. Process CGL annotations (D4) → composition grammar → `config/quality_frameworks/composition_grammar.yaml`
4. Process PosterIQ (D12) → 4-dimension quality annotations + style classifications

**Hour 2 — Enriches production quality:**

5. Process AdImageNet (D6) → content density model → enrich `config/social_platforms.yaml`
6. Process ad copy (D7) → CTA + headline formulas → `config/copy_patterns/`
7. Copy 55 DESIGN.md → `config/design_systems/`
8. Extract linguistic quality rules from D11

**Hour 3-4 — Useful but non-blocking:**

9. Process marketing dataset (D8) → `config/content_strategies.yaml`
10. Process children's stories (D10) → narrative scaffolding templates
11. Install antvis Infographic templates (R4)
12. Extract LAYOUT.md from Electric Book (R2) → `config/layout_systems/`
13. Run swipe ingest on 2K poster images (D1) → visual DNA seed
14. Verify UiTM Manglish corpus (D13) accessible for code-switching extraction
15. Verify MalayMMLU (D14) + Tatabahasa (D15) accessible for S19 benchmarks

**Exit criteria:**

- All 15 datasets downloaded, all 6 repos cloned
- 55 DESIGN.md + 6 LAYOUT.md files in config
- Visual brief expander template created
- Quality framework with scoring dimensions
- CTA (50+) + headline (30+) formula YAMLs populated
- Composition grammar YAML with structural rules
- PosterIQ quality dimensions extracted into YAML
- PosterIQ 17 style classifications extracted
- Content density model extracted (word budgets per platform/format)
- Children's story scaffolds extracted from D10
- 2K poster images processed for visual DNA
- UiTM Manglish corpus (D13) available for code-switching rule extraction
- MalayMMLU (D14) + Tatabahasa (D15) available as BM model benchmarks for S19

Note: extraction ORDER is prioritized by downstream dependency (Hour 1 blocks S13, Hour 2 enriches quality, Hour 3-4 useful but non-blocking).

---

### S6 — Governance Contracts

```
id: S6
attention: UNATTENDED
duration: 3-4 hours
code: ~500-650 lines
depends_on: [S0]
parallel_with: [S7, S4, S5]
blocks: [S8, S9, S10a, S15]
day: 1, block: 2
```

**Directories touched:**

```
contracts/
├── artifact_spec.py       # ArtifactSpec, ProvisionalArtifactSpec
├── policy.py              # PolicyDecision
├── readiness.py           # ReadinessGate, RefinementLimits
├── routing.py             # RoutingResult (stub)
├── trace.py               # StepTrace, ProductionTrace, TraceCollector
├── context.py             # RollingContext (§43) — generic sequential coherence
└── publishing.py          # PlanningObject, CharacterBible, StoryBible,
                           # NarrativeScaffold, CharacterRegistry, StyleLock
```

**What Claude Code does:**

- ArtifactSpec + ProvisionalArtifactSpec with Pydantic validation (structural, style, QA, delivery reqs)
- PolicyDecision enum: allow/block/degrade/escalate with reason
- ReadinessGate: ready/shapeable/blocked
- RefinementLimits: max cycles, clarifications, prototypes, cost ceiling
- StepTrace + ProductionTrace + TraceCollector with `step()` context manager
  - StepTrace includes `proof: dict | None` — optional structured evidence of step success (e.g. `{"nima_score": 6.8, "brand_voice_match": 0.92}`). Populated by QA stages, tripwire scorers, guardrails. Feeds improvement loop for step-level correlation with operator approval.
- **RollingContext contract** (~100 lines, §43):
  - `context_type` (narrative/campaign/document/client/social)
  - Three-tier summary: `recent` (full fidelity), `medium` (beat level), `long_term` (compressed)
  - `entities` list with state tracking
  - `immutable_facts` list (never contradicted)
  - `checkpoints` list (target states)
  - Config: `recent_window`, `medium_scope`, `compression_model`
- **CharacterBible** (~80 lines) — Pydantic model matching §42.1 YAML schema:
  - `physical` (age, ethnicity, skin_tone hex, height, build, face details, hair)
  - `clothing` (default + variants: school, festive, etc.)
  - `style_notes` (art_style, line_weight, colour_palette, never/always rules)
  - `reference_images` (front, three_quarter, profile — operator-curated)
- **StoryBible** (~60 lines) — §42.2 schema:
  - `world` (setting, sensory details, cultural_context, values)
  - `thematic_constraints` (lesson, avoid list)
  - `immutable_facts` (populated during production)
  - Domain-specific vocabulary section
- **NarrativeScaffold** (~80 lines) — age-calibrated decomposition:
  - Word count targets per page/chapter by age group (3-5: 10-20, 5-7: 20-40, 8-10: 80-120)
  - Emotional beat per page, checkpoint progress, characters present
  - Arc templates (discover→try→succeed for age 3-5, problem→attempt→fail→learn→succeed for 5-7)
  - **Research-validated per-page fields (§42.3):**
    - `text_image_relationship`: symmetrical | complementary | contradictory
    - `illustration_shows`: detailed description of what illustration communicates BEYOND the text
    - `page_turn_effect`: continuation | reveal | pause | climax
    - `composition_guide`: camera distance, character_position, background_detail, colour_temperature, text_zone
  - Typography constraints per age group: min font size, line spacing, max lines per page
- **PlanningObject** — compound artifact decomposition connected to NarrativeScaffold
- **StyleLock** — locked illustration parameters (art style, palette, typography) PLUS `text_placement_strategy` (text-always-below | text-on-left | text-overlay-with-reserved-zone)
- Wire poster pipeline to consume ArtifactSpec
- Test ready/shapeable/blocked paths

**Exit criteria:**

- ArtifactSpec validates — rejects incomplete specs
- ReadinessGate returns correct status for 3 test inputs
- TraceCollector captures step name, tokens, cost, duration
- StepTrace `proof` field accepts dict and serialises to JSONB in production_trace
- RollingContext initialises with config, accepts updates, compresses tiers
- CharacterBible validates against sample character YAML
- StoryBible validates against sample story bible YAML
- NarrativeScaffold decomposes "8-page children's book age 5-7" into 8 page specs with: word targets, text_image_relationship, illustration_shows, page_turn_effect, composition_guide
- StyleLock includes text_placement_strategy field
- PlanningObject connected to NarrativeScaffold

---

### S7 — Local Spans + Memory Routing

```
id: S7
attention: UNATTENDED
duration: 2-3 hours
code: ~200-250 lines
depends_on: [S0]
parallel_with: [S6, S4, S5]
blocks: [S10a]
day: 1, block: 2
```

**Note:** `spans` and `memory_routing_log` tables are created in LibSQL by S7 directly — they are NOT part of S10a's Postgres migration.

**What Claude Code does:**

- Create spans table in LibSQL (step_id, model, input_tokens, output_tokens, cost_usd, duration_ms, job_id, timestamp)
- Python decorator wrapping call_llm() and tool dispatch
- **Prompt caching structure in call_llm (~20 lines, §13.7):** every LLM call structured as stable prefix (persona + templates + client config) + variable suffix (job-specific content). Anthropic calls use `cache_control` headers on stable blocks. OpenAI calls use cached input pricing. Token-Efficient Tool Use header enabled for Claude 4 models.
- Memory routing config — all memory ops to GPT-5.4-mini (Month 1-2)
- 5 SQL diagnostic queries: total cost by model, avg latency by step, token burn by job, idle burn detection, cost per client
- Idle token alarm (hourly: flag spans without job_id)

**Exit criteria:**

- Spans table created, decorator captures model/tokens/cost/duration/job_id
- call_llm structures stable prefix + variable suffix (verified via log inspection)
- Anthropic cache_control header present on cached calls
- 5 diagnostic queries return results on test data
- Idle token alarm fires on spans without job_id

---

### S8 — Policy + Observability

```
id: S8
attention: UNATTENDED
duration: 2-3 hours
code: ~250-350 lines
depends_on: [S6]
parallel_with: [S9]
blocks: [S10a]
day: 1, block: 3
```

**What Claude Code does:**

- PolicyEvaluator: budget gate (daily token limit), tool gate (approved tools per phase), phase gate (config/phase.yaml), cost gate (per-job ceiling)
- Langfuse @observe decorator with custom metadata (client_id, tier, job_id, artifact_type)
- Dual tracing: local spans + Langfuse coexist. Both fire on every call.
- Context size cap in PolicyEvaluator (reject prompts > configured token limit)
- Quality posture handler: reads quality posture from phase.yaml (Canva-baseline / Enhanced / Full), adjusts contract strictness and quality technique activation accordingly

**Exit criteria:**

- PolicyEvaluator blocks over-budget and wrong-phase requests
- Langfuse trace appears with client_id metadata
- Local span AND Langfuse trace exist for same call
- Context size cap rejects oversized prompt
- Quality posture handler returns correct posture for test config

---

### S9 — Packs + Workflows + Tripwire

```
id: S9
attention: LIGHT-TOUCH
duration: 3-4 hours
code: ~300-400 lines + ~16 YAML files
depends_on: [S6]
parallel_with: [S8]
blocks: [S15]
day: 1, block: 3
```

**Changes from v1.1.0:**

- **16 workflow YAMLs** (was 15): add `rework.yaml` (see architecture v5.3 Change 6)
- All 16 WorkflowPack YAMLs set `model_preference` to `gpt-5.4-mini` for ALL entries. No Claude/Gemini/Qwen routing until S19. **(Anti-drift #54)**
- Add `derivative_source` field to `childrens_book_production.yaml` schema

**Additional workflow YAML:**

```yaml
# manifests/workflows/rework.yaml
name: rework
posture: production
model_preference:
  # all gpt-5.4-mini Month 1-2
plan_enabled: false
stages:
  - name: diagnose
    role: qa
    tools: [trace_insight]
    action: analyse original trace + feedback to identify failing step
  - name: rerun
    role: production
    tools: []  # inherits from original workflow
    action: re-run from failing step with feedback as additional context
  - name: qa
    role: qa
    tools: [quality_gate]
    action: validate revised output against original spec
  - name: delivery
    role: delivery
    tools: [deliver]
    action: deliver revised version, link to original artifact
```

**Test executor against BOTH simple and complex workflows:**

- Simple: `poster_production` (4 stages, no rolling context, no creative workshop)
- Complex: `childrens_book_production` (7 stages, `rolling_summary` context strategy, `creative_workshop: true`, `section_tripwire: true`)
- Client override: load `workflow_overrides` from `config/clients/{id}.yaml`, merge onto WorkflowPack YAML defaults at runtime (~10 lines in executor). Override fields: `tripwire`, `quality_techniques`, `parallel_guardrails`. Missing overrides = use workflow defaults.

If executor handles both, it handles everything. If it fails on complex, you discover it Day 1 Block 3 — not Day 2 Block 6.

**Exit criteria:**

- WorkflowPack schema validates all 16 YAML files
- Generic executor runs poster_production end-to-end (with stubs)
- Tripwire generates specific critique and produces revised output
- post_step_update fires rolling summary update when context_strategy=rolling_summary
- quality_techniques activates persona and self_refine from YAML config
- childrens_book_production.yaml includes creative_workshop, rolling_context, quality_techniques, section_tripwire
- scorer_fallback and latency_threshold_ms fields validated
- context_strategy field accepts simple/rolling_summary/aggressive
- `rework.yaml` validates and executor can iterate its stages
- Rework executor test: diagnose stage accepts trace + feedback input, rerun stage inherits tools from original workflow
- All 16 YAMLs have `model_preference` set to `gpt-5.4-mini` for every entry
- Executor passes smoke test on BOTH `poster_production` AND `childrens_book_production` (with stubs)
- Executor merges `workflow_overrides` from client config onto YAML defaults (test: DMB override raises tripwire threshold from 3.0 to 3.5)
- `childrens_book_production.yaml` accepts `creative_workshop: derivative` with `derivative_source` field
- Workflows for Extended capabilities (social_batch, content_calendar, serial_fiction) reference unbuilt tools — these YAMLs validate structurally but don't run until dependencies ship. Phase gate prevents premature routing. This is intentional.
- When executor hits a stub workflow (tools not yet built), the error message MUST be human-readable: `"Workflow '{name}' requires tools from {session} which hasn't shipped yet. Enable in config/phase.yaml after {session} completes."` — not a raw validation exception.

---

### S10a — Data Foundation (CORE)

```
id: S10a
attention: LIGHT-TOUCH
duration: 2-2.5 hours
code: ~250-300 lines
depends_on: [S6, S7, S8]
parallel_with: [] # SEQUENTIAL — Day 2 depends on core tables
blocks: [S11, S12, S13, S15, S16, S17, S18, S19]
day: 1, block: 4
```

**What Claude Code does:**

Create 14 CORE Postgres tables from `migrations/core.sql`:

**Core 8:** `clients`, `jobs`, `artifact_specs`, `artifacts`, `assets`, `deliveries`, `policy_logs`, `feedback`

- `jobs` table includes `goal_chain jsonb` — optional field linking job to campaign/business goal ancestry. NULL for standalone jobs. Populated by S16 BizOps when job originates from campaign plan. Feeds improvement loop for goal-level pattern detection.

**Knowledge 4:** `knowledge_sources`, `knowledge_cards`, `exemplars`, `outcome_memory`

**Infrastructure 2:** `visual_lineage`, `system_state`

**All statements use `CREATE TABLE IF NOT EXISTS`** — idempotent, safe to re-run.

Additional:

- Add `diversity_score` float column to a future `datasets` table stub (or defer to S19)
- Create Postgres views: system health, client health, feedback quality
- Create database triggers for feedback state machine (`delivered → awaiting → silence_flagged` after 24hrs) with existence checks
- Build TraceCollector Postgres integration
- Wire Langfuse SDK with custom metadata
- MinIO Storage integration for binary assets (boto3 or minio-py S3 client)
- End-to-end test: poster job → trace → Langfuse → feedback trigger → spans

**Extended tables are NOT created here.** Each Extended session (S16, S18, S19, etc.) creates its own tables as a preamble step using `migrations/extended.sql` or inline DDL.

**Exit criteria:**

- 14 core tables exist with correct schemas
- `jobs` table includes `goal_chain jsonb` column (nullable, verified with INSERT test)
- All CREATE statements are idempotent (IF NOT EXISTS)
- Postgres views return data on test rows
- Feedback trigger transitions correctly
- Feedback table includes `anchor_set boolean default false` and `benchmark_source text` columns (§15.10 drift detection)
- Self-referential FK on artifacts table: insert artifact with NULL parent_artifact_id, insert child artifact pointing to parent, verify both queries work
- End-to-end trace works
- MinIO uploads work (upload test image, retrieve via S3 URL)
- Re-running `core.sql` does not error or lose data

---

### S11 — Routing + Multi-Model

```
id: S11
attention: LIGHT-TOUCH
duration: 3-4 hours
code: ~450-550 lines
depends_on: [S10a]
parallel_with: [S12, S13, S15]
blocks: []
day: 2, blocks: 5-6
```

**Changes from v1.1.0:**

- Multi-model prose routing: **all `model_preference` entries point to `gpt-5.4-mini`** Month 1-2. The routing code reads from YAML — it doesn't care which model. When S19 validates the prose map, updating YAMLs activates multi-model routing with zero code change.
- **Build `utils/retrieval.py:retrieve_similar_exemplars(image, client_id, top_k)`** — shared function used by BOTH S11 (exemplar injection into production prompt) AND S13 (exemplar-anchored quality scoring). One CLIP similarity query against `exemplars` table, one function, two consumers.
- **Build design system selector** (~20 lines in `contracts/routing.py`): read `config/design_system_index.yaml` + client config `brand_mood` + artifact type → score all 55 systems → return top 3. Inject 3 DESIGN.md references into production prompt.

**Exit criteria:**

- Fast-path: "poster DMB" → poster_production at zero tokens
- LLM routing: "buatkan sesuatu untuk Raya" → correct workflow via GPT-5.4-mini
- Refinement: vague request → 2 shaping cycles → spec promoted → production
- Knowledge retrieval returns client config + seasonal context with lost-in-the-middle reordering applied
- Exemplar retrieval returns 2-3 visually similar approved designs via CLIP
- `utils/retrieval.py:retrieve_similar_exemplars()` returns 2-3 visually similar designs via CLIP
- Design system selector returns 3 candidates for DMB (industry: textile, mood: warm, traditional)
- All routing uses GPT-5.4-mini (verify no Claude/Gemini/Qwen calls in logs)

---

### S12 — Research + Seeding

```
id: S12
attention: LIGHT-TOUCH
duration: 3-4 hours
code: ~350-450 lines
depends_on: [S10a]
soft_depends: [S3]
parallel_with: [S11, S13, S15]
blocks: []
day: 2, blocks: 5-6
```

**Changes from v1.1.0:**

- **Build `utils/retrieval.py:contextualise_card(card, source)`** — shared function used by BOTH S12 (seeding contextualisation) AND S18 (knowledge spine ingestion). One function that generates 50-100 token context prefix via GPT-5.4-mini. Built once here, imported by S18.
- **Clean start: no pro-max data migrated.** All knowledge cards seeded fresh from S1 configs (brand patterns, copy patterns) and S3 operator-curated materials (client configs, BM copy samples). Zero exemplars — exemplar library grows from production.

**Exit criteria:**

- pytrends returns data for "batik Malaysia"
- Swipe ingest produces contextualised knowledge cards from screenshot
- Contextualised card has source prefix ("This card is from DMB brand config about...")
- Visual DNA populates dominant_colours, layout_type, visual_embedding on assets table
- Calendar cron fires for events within prep_window_days
- Brand pattern → contextualised knowledge card ingestion works
- `utils/retrieval.py:contextualise_card()` generates prefix and is importable
- Verify: zero knowledge cards, zero exemplars carried from pro-max. All cards seeded fresh.

---

### S13 — Visual Intelligence + Guardrails

```
id: S13
attention: ATTENDED
duration: 3-4 hours
code: ~450-550 lines
depends_on: [S10a]
soft_depends: [S4, S5]
parallel_with: [S11, S12, S15]
blocks: []
day: 2, blocks: 5-6
```

**Changes from v1.1.0:**

- Exemplar-anchored scoring uses `utils/retrieval.py:retrieve_similar_exemplars()` from S11 — does NOT rebuild the function.

**Exit criteria:**

- Poster generates via Nano Banana Pro with expanded brief
- NIMA pre-screen catches low-quality test image (score < 4.0) and triggers regeneration
- NIMA passes high-quality test image (score > 7.0) without regeneration
- 4-dim critique generates specific issues across all 4 dimensions for a test poster
- Exemplar-anchored scoring retrieves 2-3 similar approved designs via CLIP similarity
- Visual lineage records template + stock assets + exemplar used
- Brand voice guardrail flags register mismatch
- GuardrailMailbox deduplicates 3 flags about same issue into 1
- BM naturalness heuristic flags overly formal copy
- Full pipeline: brief → poster → NIMA → 4-dim critique → trace → feedback trigger
- Import verification: `from utils.retrieval import retrieve_similar_exemplars` works

---

### S14 — Hermes Fork Patch (CONDITIONAL)

```
id: S14
attention: UNATTENDED
duration: 0-3 hours (skip if upstream suffices)
code: 0-100 lines
depends_on: [S0]
parallel_with: [S11, S12, S13]
day: 2, block: 7
```

Read `docs/decisions/hermes_fork_decision.md` from S0. If upstream v0.7.0 covers everything → skip entirely.

---

### S15 — Publishing Lane

```
id: S15
attention: ATTENDED
duration: 4-6 hours (Day 1 block 4: assembly, Day 2 block 5: wiring)
code: ~500-650 lines
depends_on: [S10a, S9, S2, S6]
parallel_with: [S11, S12, S13]
blocks: [S21]
day: 1 block 4 + day 2 block 5
```

**Changes from v1.1.0:**

**File split: `tools/image.py` vs `tools/illustrate.py`**

`tools/image.py` (existing, S11/S13) wraps generic fal.ai image generation — fire-and-forget calls for posters, marketing graphics, and graphic elements. No state between calls.

`tools/illustrate.py` (new, S15) wraps the publishing illustration pipeline — stateful sequential production where each page depends on prior pages. Handles: character consistency verification (CLIP similarity against references), LoRA composition (character + style adapters), Kontext iterative mode (page N → page N+1), anchor frame resets, and reference image management.

**Re-merge trigger:** If after S15, both files share >70% of their code (same fal.ai API calls, same error handling, same retry logic), merge into `image.py` with an `illustration_mode: bool` parameter that activates the stateful consistency pipeline. Keep separate until that convergence is proven.

**Day 1 Block 4 — Assembly pipeline:** No dependency on S4 illustration decision. Assembly is Typst rendering + ebooklib EPUB — pure document layout. Can start immediately alongside S10a (different directories: `tools/` vs `migrations/`).

**Day 2 Block 5 — Workflow wiring:** This is where S4's illustration pipeline decision matters. The `tools/illustrate.py` fal.ai wrapper supports the tier selected in S4.

**Derivative workshop support:**

```yaml
# When creative_workshop: derivative
# Workflow executor loads source project's StyleLock, story bible template,
# typography settings, illustration tier from derivative_source project ID.
# Operator confirms inherited settings (1 screen, not 8 steps).
# Then proceeds to: new premise → new characters → new scaffold → specimen.
```

**Exit criteria:**

- `tools/illustrate.py` exists with fal.ai wrapper supporting the tier selected in S4 (Kontext iterative, IP-Adapter anchored, LoRA, or multi-reference)
- `tools/illustrate.py` maintains page-to-page state (previous page image, character references, consistency scores)
- Typst renders 8-page children's book PDF with text overlaid on text-free illustrations
- Text placement matches StyleLock text_placement_strategy consistently across all pages
- Typography meets minimum standards (16pt body, 130%+ leading for age 5-7)
- ebooklib produces valid EPUB from same content
- Illustration tool generates TEXT-FREE images (no words/letters in output)
- Illustration prompt uses `illustration_shows` field, not raw page text
- Text gen respects `page_turn_effect` (continuation page ends mid-sentence/tension)
- Character reference generation produces 10+ candidates from CharacterBible YAML
- Full workflow: creative_workshop → storyboard review → specimen → 2 test pages → post_page_update → assembly → operator_review
- RollingContext updates after each page
- Consistency check catches a planted contradiction in test data
- Ebook workflow produces valid PDF + EPUB from 3-section test content
- Visual consistency checker flags character mismatch between two test images
- LoRA composition: if Tier 1 selected in S4, character LoRA + style LoRA produce consistent output
- Anchor frame: Kontext iterative resets to original reference on anchor pages
- Character-cropped CLIP: cropped similarity scores more stable than full-page scores
- Derivative workshop: load source project StyleLock → confirm → proceed to new content only
- Verify: derivative workshop completes in < 60 min of operator time (vs 2-4 hrs full workshop)

---

### S16 — BizOps + Steward + Crons

```
id: S16
attention: LIGHT-TOUCH
duration: 4-5 hours
code: ~550-750 lines
depends_on: [S10a]
parallel_with: [S18]
blocks: [S17]
day: 3, block: 9
```

**Changes from v1.1.0:**

- **Creates its own extended tables as preamble:** `invoices`, `payments`, `pipeline`, `steward_inbox`, `steward_tasks`, `steward_projects`, `steward_reviews` — using `CREATE TABLE IF NOT EXISTS` from `migrations/extended.sql` or inline DDL. These tables reference core tables (e.g. `clients`), so S10a must complete first (as listed in `depends_on`). S16 does NOT wait for a separate extended migration session — it runs its own DDL as a preamble step.
- **Steward personal assistant (§20):** `tools/steward.py` (~150-200 lines). GTD inbox capture, task processing via GPT-5.4-mini, `/next` recommendation engine (energy × context × deadline × domain balance scoring), `/done` with streak tracking, `/snapshot` domain heatmap, `/project` decomposition, `/review` weekly prep. Separate Telegram bot token in Hermes gateway config.

**Exit criteria:**

- Invoice generates PDF via Typst with SSM, bank details, itemised line items
- Payment state machine transitions correctly (pending → partial → paid → overdue)
- Pipeline CRUD works conversationally via Telegram (lead → contacted → proposal_sent → negotiating → won/lost)
- Morning brief fires after Subuh with Vizier + Steward synthesis (jobs, revenue, pipeline, calendar + today's top 3 personal tasks, domain balance snapshot, streak)
- 3-gate cron: morning brief does NOT fire if no new data since last brief
- Client health surfaces overdue invoices and last-job timestamps
- Prayer scheduling blocks new intake after Asr
- Maghrib shutdown ritual synthesises both Vizier production summary + Steward personal summary + tomorrow's top 3 from both
- `invoices`, `payments`, `pipeline` tables created with IF NOT EXISTS
- **Steward:** `steward_inbox`, `steward_tasks`, `steward_projects`, `steward_reviews` tables created with IF NOT EXISTS
- **Steward:** Separate Telegram bot token configured in Hermes gateway. Messages to @steward_bot route to Steward persona, not Vizier.
- **Steward:** Text message → inbox capture (zero tokens, immediate "✓ Captured")
- **Steward:** `/process` presents unprocessed inbox items with suggested title/domain/context/energy for tap-confirm
- **Steward:** `/next` recommends ONE task based on energy + context + deadline + domain balance
- **Steward:** `/done` marks complete, shows streak + domain progress
- **Steward:** `/snapshot` returns active tasks, overdue count, domain heatmap (green/amber/red), streak
- **Steward:** `/project "objective"` decomposes via GPT-5.4-mini and presents for confirmation
- **Steward:** `config/personas/steward.md` exists with ADHD-friendly persona (warm, concise, never overwhelming, tap-to-confirm UX)
- **Steward Habits:** Habit entries with four-law fields (cue/trigger, minimum_version, celebration). Habit stacking chains work (completing one cues the next). Never-miss-twice grace period logic. Daily habit scorecard in morning brief.
- **Steward Deep Work:** `/deep [duration]` starts timer, silences all non-prayer notifications. `/deep end` logs hours. `/ratio` shows deep/shallow split. Time block proposal in morning brief anchored to prayer times.
- **Steward Health:** `steward_health_log` table created. Apple Health JSON import works (manual `/health-sync` or file drop). Sleep data adjusts `/next` energy recommendations. Health patterns mentioned in weekly `/review`.
- **Steward Learning:** `steward_learning` table created. `/learn` creates learning goal linked to domain. `/reading "title" N` logs progress. Spaced repetition nudges fire when `review_interval_days` elapsed. Learning progress appears in domain balance and weekly review.
- **All 6 Steward tables** created with IF NOT EXISTS: `steward_inbox`, `steward_tasks`, `steward_projects`, `steward_reviews`, `steward_health_log`, `steward_learning`

---

### S17 — Dashboard

```
id: S17
attention: ATTENDED
duration: 3-4 hours
code: ~200-300 lines + Refine scaffold
depends_on: [S10a, S16]
parallel_with: []
day: 3, block: 10
```

**What Claude Code does:**

- Scaffold Vizier Dashboard with Refine + `@refinedev/simple-rest` provider pointing at PostgREST
- Apply DESIGN.md aesthetic (Linear or Supabase-inspired style)
- **PostgREST JSONB handling:** `production_trace` and `goal_chain` columns are JSONB. PostgREST serves them as nested JSON by default. Verify Refine renders these correctly in the pull-to-inspect view. If PostgREST nesting causes issues, create Postgres views that flatten the top-level JSONB keys into columns for the dashboard (e.g. `v_job_traces` with step_count, total_tokens, last_step_name extracted). The views serve the dashboard; raw JSONB serves the insight tool.
- Functional table views with Cloudflare Access auth and Postgres LISTEN/NOTIFY for live updates (polling fallback at 30s)
- Token spend display: single number + daily trend chart
- Job status view with pull-to-inspect: click job → trace → step detail (3 depth levels)
- Cloudflare Tunnel + Cloudflare Access wiring for remote access
- All writes flow through Hermes as write gateway (dashboard is read-only + action triggers)
- Design system selector: call `contracts/routing.py`'s selector function — do NOT rebuild the scoring logic

**Exit criteria:**

- Dashboard renders with PostgREST data layer working
- Token spend visible as single number with trend
- Job status updates live (LISTEN/NOTIFY or polling)
- Pull-to-inspect shows 3 depth levels
- Accessible via Cloudflare Tunnel

---

### S18 — Knowledge Spine

```
id: S18
attention: UNATTENDED
duration: 3-4 hours
code: ~250-350 lines
depends_on: [S10a]
parallel_with: [S16]
blocks: [S19]
day: 3, block: 9
```

**Changes from v1.1.0:**

- **Creates its own extended tables as preamble** if needed: `datasets`, `dataset_items` — using `CREATE TABLE IF NOT EXISTS`.
- **Imports `utils/retrieval.py:contextualise_card()`** from S12 — does NOT rebuild the contextualisation logic.

**Exit criteria:**

- Card ingested with contextualised embedding (prefix present: "This card is from...")
- Hybrid search returns results from BOTH pgvector AND Postgres FTS merged via RRF
- Query transformation generates 4 variants including BM and EN for a test query
- Reranker reorders 20 candidates and selects top 5 with relevance scores
- Lost-in-the-middle: top-ranked card appears at position 1 AND 5 in final context
- Exemplar promoted from artifact with operator rating
- Outcome memory record created after job completion
- pgvector semantic search returns relevant cards for "Raya batik promotion"
- FTS keyword search catches exact term "DMB" that semantic search might miss
- Wisdom Vault imports test book → contextualised knowledge cards
- Verify: `from utils.retrieval import contextualise_card` works
- Contextualisation function is the SAME function S12 built (not a copy)

---

### S19 — Self-Improvement + Calibration

```
id: S19
attention: LIGHT-TOUCH
duration: 3-4 hours
code: ~350-450 lines
depends_on: [S10a, S18]
blocks: [S20]
day: 3, block: 10
```

**Changes from v1.1.0:**

- **Creates its own extended tables as preamble:** `experiments`, `experiment_results` — using `CREATE TABLE IF NOT EXISTS`.

**Post-S19: Prose Model Benchmark** now explicitly gates multi-model activation:

> After benchmark completes, update all 16 WorkflowPack YAMLs with validated `model_preference` assignments. Until then, GPT-5.4-mini for everything. This is a config change pushed via git, not a code deployment.

**S19 benchmark additions (April 2026 market context):**

- Benchmark Claude Sonnet 4.6 alongside Opus 4.6 for `en_creative`. Sonnet 4.6 delivers near-Opus quality at ~40% lower cost ($3/$15 vs $5/$25). If Sonnet matches Opus on EN creative prose for marketing copy, use Sonnet and reserve Opus for fiction/narratives only.
- Benchmark Gemini 3.1 Flash-Lite ($0.25/M input) for `routing` and `classification` tasks alongside Qwen 3.5 2B fine-tuned. Flash-Lite may match fine-tuned Qwen at comparable latency without the training investment.
- Evaluate Anthropic native web search (now GA, free with code execution) as alternative to Tavily for the S12 research pipeline. Test coverage and quality for Malaysian market research queries.

**Exit criteria:**

- Pattern detector finds approval correlations from test data
- Failure analysis clusters low-rated jobs and proposes instruction changes
- Improvement proposal delivered via Telegram with /test /promote /reject action buttons
- Experiment tags jobs, compares results, reports winner
- Prompt template versioning: /promote increments version, /revert restores previous
- Exemplar set optimisation selects best 3-exemplar combination from test pool
- Prompt variation testing generates 3 variants and scores against held-out examples
- Rubric refinement proposes updated criteria from 20 test comparisons
- /promote updates YAML and logs decision in docs/decisions/
- `config/improvement_rules/` directory exists and rules inject into templates
- `experiments`, `experiment_results` tables created with IF NOT EXISTS
- **Drift detection (§15.10):** Monthly anchor set re-scoring cron built. Drift alert fires when anchor scores shift >0.5 from originals. Improvement velocity decay alert fires after 100 jobs with zero proposals. External benchmark ingestion tool tags feedback records with `benchmark_source: external`.

---

### S20 — Local Model Training (DEFERRED)

```
id: S20
condition: Month 3+ ONLY. Do NOT build before 200+ production ratings exist.
depends_on: [S19, 200+ ratings]
```

NOT IN 3-DAY SPRINT. Fine-tune Qwen 4B quality scorer, Qwen 2B routing+register classifiers. Validate >80% correlation. Then migrate from GPT-5.4-mini.

---

### S21 — Extended Artifact Lanes

```
id: S21
attention: LIGHT-TOUCH
duration: 3-4 hours
code: ~300-400 lines
depends_on: [S15]
parallel_with: []
day: 3, block: 11
```

**What Claude Code does:**

- Upgrade children's book from S15 specimen to full production pipeline
- Full ebook production: outline → section generation → rolling context → assembly
- Serial fiction workflow: chapter-level rolling context across episodes, entity registry, checkpoint alignment
- Code generation workflow (if time permits)

**Exit criteria:**

- 8-page children's book produces complete PDF + EPUB through automated pipeline
- Ebook produces from outline → sections → assembly with section-level self-refine
- Serial fiction maintains character consistency across 3 test episodes via RollingContext
- Entity registry catches new character introduced in episode 2, persists to episode 3

---

### S22-S37 — Post-Sprint Capabilities

See **VIZIER_POST_SPRINT_ROADMAP.md** (v1.1.0) for complete post-sprint execution plan covering 5 phases:

- **Phase 1 (Week 1-2):** YouTube research (S22), education content config (S23), social publishers (S24), narration tool (S30)
- **Phase 2 (Week 3-4):** Video assembly (S31), song generation (S32), multi-format workflow (S33)
- **Phase 3 (Month 2):** Webapp building / Jarvis mode (S27), question bank app (S34), storybook app (S35)
- **Phase 4 (Month 3-4):** FSRS adaptive learning (S36), tuition centre white-label (S37)
- **Phase 5 (Month 4-6):** Campaign planning (S26), social analytics (S25), decision support (S28), Wazir core (S29)

All phases use the same engine, same governance, same quality gate. New capabilities are config + workflow YAMLs + lightweight tools (~20-50 lines each). No architectural changes required.

---

## 8. Shared Functions Registry

Functions built ONCE by one session, imported by others. Prevents rebuild and ensures consistency.

| Function | Built by | Imported by | Location |
|----------|----------|-------------|----------|
| `contextualise_card(card, source)` | S12 | S18 | `utils/retrieval.py` |
| `retrieve_similar_exemplars(image, client_id, top_k)` | S11 | S13 | `utils/retrieval.py` |

S0 creates the `utils/` directory with stubs. S11 and S12 populate the functions. S13 and S18 import them.

---

## 9. Post-Sprint Production Schedule

```
Week 1:
  Day 4-5:  Book 1 production through Vizier → KDP + Shopee
  Day 5-6:  Book 2 production (DERIVATIVE workshop, 45-60 min) → publish
  Day 6-7:  Book 3 production (DERIVATIVE) → publish + Ebook live
  Day 5:    S23 Education config authoring (no code — config only)
  Day 6-7:  First worksheet sets produced → Shopee

Week 2:
  Books 4-5, start serial fiction (weekly episodes)
  S30 Narration tool (2-3 hrs) → audiobooks from existing stories
  S22 YouTube research pipeline (3-4 hrs)
  Education worksheets: cover Tahun 4-6 Maths + Science (40+ sets)

Week 3:
  Books 6-8, serial episodes 2-4
  S31 Video assembly (3-4 hrs) → story videos for YouTube
  S32 Song generation (2-3 hrs) → children's songs for Spotify
  YouTube channel launch with first story videos

Week 4 (mid-May school holidays):
  S33 Multi-format workflow live → one prompt, four formats
  10+ children's book titles listed
  40+ worksheet sets listed
  Songs on Spotify

Month 2:
  S27 Webapp building (Jarvis mode)
  S34 Question bank app → subscriptions live
  S35 Storybook app → subscriptions live

Month 3:
  S36 FSRS adaptive learning
  200+ ratings → S19 prose benchmark → multi-model activation
  Self-improvement loop active

Month 4-6:
  S37 Tuition centre white-label
  S26 Campaign planning, S25 Social analytics
  Revenue diversified across 8+ streams
```

Books 2-10 use derivative workshop fast-path (45-60 min each). Education worksheets use education_content_production workflow (config-driven, no code). Multi-format stories use story_multiformat workflow (one prompt → book + video + song).

---

## 10. Anti-Drift Rules (Build-Specific)

See architecture §34 for complete list (now 57 rules, 8 categories). Key rules for the build:

- **#31:** GPT-5.4-mini for ALL scoring/routing/guardrails Month 1-2.
- **#34:** No fine-tuning before 200+ production ratings.
- **#36:** Quality posture progression based on data, not build completion.
- **#38:** Tripwire uses critique-then-revise, not score-only.
- **#40:** Golden dataset splits quality (convergent) from creative (diverse).
- **#41:** Composition rules are advisory, not strict.
- **#44:** Publishing is Core.
- **#45:** Every publishing project starts with creative workshop.
- **#54 (NEW):** GPT-5.4-mini for ALL tasks including creative prose Month 1-2. Multi-model after S19 only.
- **#55 (NEW):** Derivative projects inherit creative workshop outputs.
- **#56 (NEW):** Anchor set examples are sacred — never enter exemplar library or training pools. Fixed reference for drift detection (§15.10).
- **#57 (NEW):** Agent topology changes are additive. Contracts, quality gate, data model are topology-independent (§28.1).

---

## 11. Success Metrics

### After Day 3 (Sprint)

- Core engine: routing, governance, workflows, traces all working
- All 3 ship gates pass (§4)
- All 5 integration tests pass (§5)
- Publishing pipeline: specimen page through full pipeline
- Illustration consistency validated on 8+ pages
- Extended ops building/built (70%+ acceptable)

### After Week 1

- 2-3 children's books published (KDP + Shopee)
- 1 ebook published as lead magnet
- 10+ jobs through pipeline
- First-pass approval rate tracked
- Derivative workshop validated on Book 2

### After Week 4 (School holidays)

- 10+ children's book titles listed
- Serial fiction running weekly
- 50+ approved pages in exemplar library
- Enhanced quality posture for established clients

### Month 3

- 200+ production ratings → S19 prose benchmark → multi-model activation
- Qwen fine-tuning ready
- Self-improvement loop proposing
- Revenue from books + retainers

---

## 12. Monthly API Costs (Full Vizier, 3 clients + publishing)

| Provider | Usage | Est. Monthly (USD) |
|----------|-------|--------------------|
| FLUX.1 Kontext (illustrations) | ~80-120 images | $4-12 |
| Nano Banana Pro (posters) | ~40-60 images | $5-8 |
| FLUX.2 Pro (scenes) | ~10-20 images | $0.30-0.60 |
| FLUX.2 Dev (drafts) | ~30-50 images | $0.36-0.60 |
| GPT-5.4-mini (ALL tasks Month 1-2) | Routine ops | Free (10M/day) |
| Claude/Gemini (INACTIVE Month 1-2) | 0 | $0 |
| **TOTAL** | | **~$10-22/month (RM 44-97)** |

Note: Month 1-2 cost is LOWER than v1.1.0 estimate because all prose routes to GPT-5.4-mini (free) instead of Claude/Gemini (paid). Month 3+ costs increase when S19 benchmark activates multi-model prose routing.
