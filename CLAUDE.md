# CLAUDE.md — Vizier

You are building Vizier, a governed AI production engine. Read this file first on every session.

**Architecture:** `docs/VIZIER_ARCHITECTURE.md` (v5.4.1) — WHAT to build.  
**Build plan:** `docs/VIZIER_BUILD.md` (v1.3.1) — HOW to build, session by session.  
**Sprint dispatch:** `CONTROL_TOWER.md` — for the orchestrator session that generates worker prompts. Not for worker sessions.  
**This file:** Navigation map, shared interfaces, hard rules. Prevents you from reading 3,000 lines to find the 50 that matter for your current session.

---

## 1. What This Repo Is

Vizier is a governed, self-improving AI production engine. An operator directs it. Vizier executes, traces, learns, and gets better with every job. The current deployment is digital marketing in Malaysia — the first instantiation, not the ceiling. The architecture is domain-agnostic.

**Stack:** Hermes Agent v0.7.0 (runtime) + Pydantic (contracts) + Local Postgres 16 + pgvector (37 tables) + MinIO (asset storage) + Langfuse (observability) + GPT-5.4-mini (ALL tasks Month 1-2).

---

## 2. Architecture Navigation Map

**Tech scout injections:** `docs/VIZIER_TECH_SCOUT_INJECTION_CHECKLIST.md` — additions to worker prompts from tech scouting session. Control tower reads this BEFORE generating any worker prompt and includes relevant injections.

**Read ONLY the sections listed for your session.** Do not read the full architecture document unless specifically asked.

| Session | What You're Building | Read These Sections | Anti-Drift Rules |
|---------|---------------------|-------------------|-----------------|
| S0 | Repo scaffold + asset port | §25 (repo structure), §11 (cold start assets) | #11 (no empty engine), #16 (use existing systems) |
| S1 | Config authoring | §38.1.1 (design system index), §38.6 (code-switching), §11.4-11.8 (patterns/calendar), §38.7 (dialect) | — |
| S2 | Typst + fonts + templates | §24 (renderers), §42.3 (children's typography) | #49 (illustrations text-free, text via Typst) |
| S4 | Endpoint testing | §6.3 (image routing), §42.4 (illustration pipeline tiers) | #17 (image model by job characteristics), #47 (path per-project config) |
| S5 | Dataset processing | §38 (design intelligence — all subsections), §7.6 (golden dataset) | #24 (datasets are fuel not features), #41 (composition rules advisory) |
| S6 | Governance contracts | §7 (governance layers), §9 + §9.1 (refinement + rework), §42.1-42.3 (CharacterBible, StoryBible, NarrativeScaffold), §43 (RollingContext) | #1 (canonical doc), #4 (policy centralised), #6 (no Hermes type leaks), #13 (silence not approval) |
| S7 | Spans + memory routing | §29.1-29.3 (dual tracing, memory routing, idle detection), §13.7 (prompt caching) | #20 (local spans first layer), #54 (GPT-5.4-mini for all) |
| S8 | Policy + observability | §7.2 (policy engine), §29.7 (token tracking), §4.1 (quality postures) | #2 (phase.yaml governs), #8 (no infra without trigger) |
| S9 | Packs + workflows + tripwire | §10 (workflow packs — FULL section), §37 (tripwire + guardrails), §4.2 (quality techniques), §13.7 (observation masking) | #21 (tripwire critique-then-revise), #22 (guardrails on GPT-5.4-mini), #38 (no generic retry), #54 (all model_preference = gpt-5.4-mini) |
| S10a | Data foundation (core tables) | §16.1-16.3 (16 core tables: 14 original + 2 document_set from tech scout), §29.5 (feedback state machine), table relationships in §16 header | #7 (binaries in MinIO, structured in Postgres), #13 (silence not approval) |
| S11 | Routing + multi-model | §8 (routing model), §6.2 (prose routing), §13.2-13.3 (fast-path + lazy retrieval), §22.2 (retrieval pipeline), §38.1.1 (design system selector) | #54 (GPT-5.4-mini for ALL Month 1-2), #18 (routing map provisional until S19), #19 (no model downgrade without benchmark) |
| S12 | Research + seeding | §12 (research capabilities), §22.1 (contextual retrieval), §22.2 (retrieval pipeline — S12 builds contextualisation that feeds into pipeline S18 completes), §11.9-11.10 (client seeding + swipe) | #3 (retrieval before generation), #28 (retrieved knowledge is hint, verify) |
| S13 | Visual intel + guardrails | §30 (visual asset intelligence — all subsections), §7.4 (quality gate layers), §37.2 (parallel guardrails) | #14 (every asset has visual DNA), #17 (image model by job), #25 (visual brief expansion always) |
| S14 | Hermes fork patch | §6 header (submodule rules) | #6 (no Hermes type leaks) |
| S15 | Publishing lane | §42 (publishing intelligence — ALL subsections), §43.5 (workflow YAML), §6.3 (image routing), §18 (publishing overview), §4.2 (quality techniques — S15 wires self_refine, exemplar_injection, persona, domain_vocab, contrastive_examples) | #44-53 (ALL publishing rules), especially #49 (text-free illustrations) |
| S16 | BizOps + Steward + crons | §19 (business ops), §20 (Steward personal assistant), §16.4 (BizOps tables), §16.4a (Steward tables) | #29 (3-gate cron triggers) |
| S17 | Dashboard | §31 (operator experience — all subsections) | #15 (surface insights not data), #13 (complexity behind glass) |
| S18 | Knowledge spine | §22 (knowledge spine — all subsections), §16.2 (knowledge tables) | #3 (retrieval before generation) |
| S19 | Self-improvement + drift detection | §15 (self-improvement — all subsections incl §15.10 drift detection), §16.7 (calibration tables — create own tables as preamble) | #52 (validate before promote), #53 (versions archived never deleted), #56 (anchor set sacred) |
| S21 | Extended artifact lanes | §42.6.1 (derivative workshop), §43 (RollingContext) | #55 (derivative inherits workshop outputs), #48 (RollingContext one contract many apps) |
| Pre-sprint | Dataset download + API verification | §12.2 (research tools), §6.1 (model roster), §5 (stack) | — |

---

## 3. Shared Interfaces — DO NOT REBUILD

These functions are built ONCE by one session and imported by others. If your session is listed under "Imported by," use `from utils.retrieval import ...` — do NOT rewrite the function.

**Stub strategy:** S0 creates `utils/retrieval.py` with both function stubs (full signatures + docstrings, bodies are `raise NotImplementedError`). S11 fills in `retrieve_similar_exemplars()`. S12 fills in `contextualise_card()`. Both sessions edit the same file but touch different functions — stubs prevent merge conflicts when running in parallel.

```python
# utils/retrieval.py — CREATED BY S0 AS STUBS, POPULATED BY S11 AND S12

# Built by S12, imported by S18
def contextualise_card(card: dict, source: dict) -> str:
    """
    Generate 50-100 token context prefix via GPT-5.4-mini.
    Prepended to card content before embedding.
    Raw card content (without prefix) is served to production models.
    
    Returns: str — the context prefix, e.g. "This card is from DMB's
    Raya 2025 promotional campaign targeting middle-class Malay women."
    """

# Built by S11, imported by S13
def retrieve_similar_exemplars(
    image: bytes, 
    client_id: str, 
    top_k: int = 3
) -> list[dict]:
    """
    CLIP ViT-B/32 similarity search against exemplars table.
    Used by S11 for exemplar injection into production prompts.
    Used by S13 for exemplar-anchored quality scoring.
    
    Returns: list of dicts, each with:
        {
            "exemplar_id": str,       # UUID from exemplars table
            "artifact_id": str,       # linked artifact UUID
            "asset_path": str,        # MinIO storage path to the image
            "similarity": float,      # cosine similarity score (0-1)
            "artifact_family": str,   # e.g. "poster", "brochure"
            "style_tags": list[str],  # from exemplars table
        }
    Sorted by similarity descending.
    Only returns results with similarity >= 0.5 (lower than knowledge card
    min_score 0.65 because visual similarity is inherently noisier than text).
    For character consistency verification, use threshold 0.75 on cropped regions.
    """
```

```python
# contracts/publishing.py — SHARED CONTRACT
# S6 defines these. S15 consumes them. Do not redefine.

# NarrativeScaffold fields per page:
#   word_target: int
#   emotional_beat: str
#   characters_present: list[str]
#   checkpoint_progress: str
#   text_image_relationship: str    # symmetrical | complementary | contradictory
#   illustration_shows: str         # DETAILED description — illustration prompt source
#   page_turn_effect: str           # continuation | reveal | pause | climax
#   composition_guide: dict         # camera, character_position, background_detail, 
#                                   # colour_temperature, text_zone

# CharacterBible fields:
#   character_id, name, role, physical (age, ethnicity, skin_tone hex, height, build,
#   face details, hair), clothing (default + variants), style_notes (art_style,
#   line_weight, colour_palette, never/always), reference_images, lora (optional)

# StyleLock fields:
#   art_style, palette, typography, text_placement_strategy
#   (text-always-below | text-on-left | text-overlay-with-reserved-zone)

# StoryBible fields:
#   title, target_age, language, world (setting, sensory, cultural_context),
#   thematic_constraints (lesson, avoid), immutable_facts (grows during production)
```

### Complete Workflow YAML List (16 files — S9 creates all structural YAMLs)

All files in `manifests/workflows/`. S9 creates all 16 structural YAMLs. Workflows referencing unbuilt tools validate structurally but don't run until dependencies ship. The tools themselves are built by the sessions noted in the table.

| # | Workflow YAML | Core/Extended | Notes |
|---|--------------|---------------|-------|
| 1 | poster_production.yaml | Core | 4 stages, simplest workflow |
| 2 | document_production.yaml | Core | |
| 3 | brochure_production.yaml | Core | |
| 4 | research.yaml | Core | Standalone research workflow |
| 5 | refinement.yaml | Core | Iterative spec shaping |
| 6 | onboarding.yaml | Core | New client warm start |
| 7 | childrens_book_production.yaml | Core | Most complex — rolling_summary, creative_workshop, section_tripwire |
| 8 | ebook_production.yaml | Core | Rolling context per section |
| 9 | rework.yaml | Core | Post-delivery correction (§9.1) |
| 10 | invoice.yaml | Extended (S16) | Typst → PDF |
| 11 | proposal.yaml | Extended (S16) | Document scaffold-driven |
| 12 | company_profile.yaml | Extended (S16) | |
| 13 | social_batch.yaml | Extended (S24) | **Structural stub until S24 builds tools** |
| 14 | social_caption.yaml | Extended (S24) | **Structural stub until S24 builds tools** |
| 15 | content_calendar.yaml | Extended (S22) | **Structural stub until S22 builds tools** |
| 16 | serial_fiction_production.yaml | Extended (S21) | **Structural stub until S21 builds tools** |

---

## 4. Model Rules (Month 1-2) — NO EXCEPTIONS

```
┌─────────────────────────────────────────────────────────────────┐
│  EVERY model_preference entry = gpt-5.4-mini                   │
│  EVERY scorer_model = gpt-5.4-mini                             │
│  EVERY scorer_fallback = gpt-5.4-mini                          │
│  EVERY parallel_guardrails[].model = gpt-5.4-mini              │
│  EVERY summarisation/extraction/verification = gpt-5.4-mini    │
│                                                                 │
│  If you are about to write claude-opus, claude-sonnet,          │
│  gemini-3.1-pro, gemini-2.5-pro, or qwen-3.5-*-local          │
│  into ANY config, YAML, or code: STOP.                         │
│                                                                 │
│  Those models are INACTIVE Month 1-2. Anti-drift #54.          │
│                                                                 │
│  Image models (FLUX, Kontext, Nano Banana) ARE active.          │
│  Text-embedding-3-small for embeddings IS active.               │
└─────────────────────────────────────────────────────────────────┘
```

After S19 benchmark (Month 3+), the WorkflowPack YAMLs get updated with validated model assignments. Until then, one model, one code path, one failure mode.

---

## 5. Build Conventions

**Commits:** Conventional commits. `feat(contracts): add ArtifactSpec validation`, `fix(routing): fast-path pattern match for poster`, `chore(s0): scaffold repo structure`.

**Tests:** Every contract has at least one test. Every tool has a smoke test. Tests go in `tests/` mirroring the source structure.

**File placement:**
- Governance contracts → `contracts/`
- Custom tools → `tools/`
- Quality middleware → `middleware/`
- Shared utility functions → `utils/`
- Workflow definitions → `manifests/workflows/`
- All config → `config/`
- Database migrations → `migrations/`
- Templates ported from pro-max → `templates/`
- Decision records → `docs/decisions/`

**Dependencies:** `pip install --break-system-packages` for all Python packages. Check `pyproject.toml` before adding new deps — it may already be listed.

**Idempotent migrations:** ALL SQL uses `CREATE TABLE IF NOT EXISTS`. ALL trigger creation checks for existence. Migrations can be re-run safely.

---

## 6. Table Relationships (Quick Reference)

```
clients ──1:N──> jobs ──1:N──> artifact_specs
                  │──1:N──> artifacts ──> assets (1:1, the file)
                  │              │──> parent_artifact (self-ref, NULL for v1, set by rework)
                  │              └──> exemplars (promoted 5/5 rated artifacts)
                  │──1:1──> feedback (state machine: awaiting → approved/revision/silence)
                  │──1:N──> policy_logs
                  └──1:1──> production_trace (JSONB on jobs table)

clients ──1:N──> knowledge_cards (client-specific cards)
assets  ──1:N──> visual_lineage (which jobs used this asset and why)
jobs    ──1:N──> outcome_memory (what worked, what was rejected)
```

**Key rules:**
- Query artifacts through jobs, not directly
- Feedback links to job AND artifact AND client — all three required
- Only `explicitly_approved` feedback counts as positive quality signal
- `silence_flagged` and `unresponsive` are excluded from quality calculations
- Visual metadata lives on the assets table as nullable columns, not a separate table

---

## 7. What NOT to Do

These are extracted from the 57 anti-drift rules. Violating any of these is a build error.

**Models:**
- ❌ Do NOT use LiteLLM (#10 — supply chain compromise)
- ❌ Do NOT route any text task to Claude/Gemini/Qwen Month 1-2 (#54)
- ❌ Do NOT build fine-tuning before 200+ production ratings exist (#33)
- ❌ Do NOT downgrade a model without benchmark evidence (#19)

**Data:**
- ❌ Do NOT create tables without IF NOT EXISTS (migration safety)
- ❌ Do NOT store binaries in Postgres — use MinIO (#7)
- ❌ Do NOT count silence as approval in quality metrics (#13)
- ❌ Do NOT port client data, knowledge cards, or exemplars from pro-max (mock data — clean start)

**Quality:**
- ❌ Do NOT use score-only retry for tripwires — use critique-then-revise with specific issues (#38)
- ❌ Do NOT route guardrail checks to expensive cloud models (#22)
- ❌ Do NOT skip visual brief expansion before image generation (#25)
- ❌ Do NOT apply composition grammar rules as strict blockers — they are advisory (#41)
- ❌ Do NOT include `anchor_set: true` feedback records in exemplar libraries, training pools, or improvement loop pattern detection — they are fixed reference points for drift detection only (#56)

**Publishing:**
- ❌ Do NOT render text inside AI-generated illustrations — text is overlaid by Typst (#49)
- ❌ Do NOT generate illustration prompts from page text — use `illustration_shows` field (#42.3)
- ❌ Do NOT modify ArtifactSpec during rework — rework corrects execution, not spec (§9.1)
- ❌ Do NOT skip the creative workshop for publishing projects (#45)

**Architecture:**
- ❌ Do NOT add infrastructure without a promotion trigger documented in §28 (#8)
- ❌ Do NOT let Hermes-native types leak into domain contracts (#6)
- ❌ Do NOT write custom code when a pip install or existing system handles it (#16, P14)
- ❌ Do NOT create competing architecture sources — this doc + the architecture doc are canonical (#1)
- ❌ Do NOT expect Extended workflow YAMLs (social_batch, content_calendar, serial_fiction) to run before their tools are built — they validate structurally but fail at runtime. Phase gate prevents premature routing. (§10)
- ❌ Do NOT reimplement the design system selector — S17 (dashboard) must call `contracts/routing.py`'s selector function, not rebuild the scoring logic
- ❌ Do NOT design contracts, quality gates, or data schemas that assume a specific agent topology — these must work whether one agent or fifty process them (#57, §28.1)

---

## 8. Session-Specific Context

Before starting work on any session, read:

1. **This file** (CLAUDE.md) — you're reading it now
2. **Your session's row in the Navigation Map** (§2 above) — tells you which architecture sections to read
3. **Your session spec in VIZIER_BUILD.md** — tells you exactly what to build, exit criteria, dependencies, and what's parallel

The session spec in the build doc is your primary instruction. The architecture sections are your reference. This file is your guardrails.

**When in doubt:**
- Check the anti-drift rules in §7 above
- Check the shared interfaces in §3 above — import, don't rebuild
- Check the model rules in §4 above — GPT-5.4-mini for everything Month 1-2
- Check the table relationships in §6 above — query through the right path

**If you encounter a decision not covered by the architecture or build plan:**
- Document the decision in `docs/decisions/` with rationale
- Choose the simpler option
- Prefer deterministic over LLM-driven
- Prefer config over code
- Prefer existing systems over custom code (P14)

**Extended session 70% cut lines (when time-compressed):**
- **S16:** Ship tables + invoice + pipeline + morning brief + core Steward (/next, /done, /process, /snapshot, /project). Cut habits, deep work, health import, learning system — these are Phase 1 post-sprint additions, not sprint blockers.
- **S17:** Ship PostgREST + Refine scaffold + token spend + job status. Cut Cloudflare Tunnel setup if needed — local access is sufficient for Day 1.
- **S19:** Ship pattern detection + failure analysis + experiment framework. Cut drift detection cron — it needs 10-15 anchor set examples that won't exist until Month 1 production.
