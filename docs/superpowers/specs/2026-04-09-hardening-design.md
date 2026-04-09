# Vizier Hardening Spec — Repo Maturity + Output Quality

**Date:** 2026-04-09
**Status:** Draft — awaiting user approval
**Inputs:** Codex evaluation, ChatGPT evaluation, manual codebase audit
**Goal:** Stabilize foundation before revenue expansion. No new lanes until both tracks pass.

---

## Strategic Context

In under one week the repo went from "good architecture with partial implementation" to
"working governed engine with visible production concerns." That pace created real
capability but also real debt. Revenue expansion now would monetize the parts that are
least reproducible and least measurable.

Hardening gives compounding returns: better engineer velocity, lower regression fear,
cleaner architecture, and confidence in quality claims. Revenue expansion tests
distribution; hardening tests production mechanics. Production mechanics first.

---

## Track 1: Repo Maturity & Reliability

**Goal:** A fresh machine reproduces the running system. No tribal knowledge required.
Another engineer can operate this without hidden manual steps.

**Exit criteria (all must be true):**
- Fresh setup reproduces the runtime from git alone
- No required production behavior depends on manual edits outside version control
- One smoke command proves bridge + gateway + governed runtime are alive
- Default test suite is green; infra tests skip cleanly when prerequisites absent
- Every governed job has a real `jobs` row and traceable Hermes session ID

### 1.1 Pin Deployment Boundary

**Problem:** Live state is split across main repo, nested hermes-agent (locally dirty),
and plugin files in `~/.hermes/plugins/vizier_tools/` outside git.

**Work:**
- Commit the hermes-agent `gateway/run.py` change (media env var export, +40 lines)
- Pin the updated submodule pointer in the superproject
- Copy `~/.hermes/plugins/vizier_tools/__init__.py` and `plugin.yaml` into
  `plugins/hermes_loader/` as the versioned source of truth
- Create `scripts/install_plugin.sh` — idempotent installer that materializes the
  loader into `~/.hermes/plugins/vizier_tools/` from the repo copy
- Add a parity check: `scripts/check_plugin_drift.sh` compares deployed vs repo
  loader/manifest and warns on divergence

**Exit:** `git submodule update --init && scripts/install_plugin.sh` reproduces live
state. Plugin drift detected automatically.

**Files touched:**
- `hermes-agent/` (submodule pointer update)
- `plugins/hermes_loader/__init__.py` (new, copy from live)
- `plugins/hermes_loader/plugin.yaml` (new, copy from live)
- `scripts/install_plugin.sh` (new)
- `scripts/check_plugin_drift.sh` (new)

### 1.2 Job Lifecycle Hardening

**Problem:** Bridge-driven runs generate a `job_id` in
`vizier_tools_bridge.py:640` but do not guarantee a `jobs` row exists before
`persist_trace()` (`trace_persist.py:19`) and `record_outcome()`
(`knowledge.py:189`) attempt to write against it. Both functions warn or fail
silently if the row is missing.

**Work:**
- At the start of `run_governed()` in `orchestrate.py:53`, ensure a `jobs` row is
  created or upserted with `status='running'` before any downstream persistence
- Bridge passes `hermes_session_id` (from `_SESSION_STATE`) so it can be written at
  creation time
- On governed completion, update `jobs.status` to `'completed'` or `'failed'`
- `persist_trace()` and `record_outcome()` can now rely on the row existing

**Exit:** Bridge-initiated governed runs always have a real `jobs` row. No orphaned
traces. Job status reflects lifecycle.

**Files touched:**
- `tools/orchestrate.py` (job creation/upsert at entry, status update at exit)
- `plugins/vizier_tools_bridge.py` (pass `hermes_session_id`)

### 1.3 Policy Persistence Fix

**Problem:** `PolicyDecision.timestamp` (`contracts/policy.py:25`) is never
persisted. `persist_policy_decision()` (`middleware/policy.py:37`) relies on DB
default `evaluated_at DEFAULT now()` instead of using the contract's timestamp.

**Work:**
- Pass `decision.timestamp` as the `evaluated_at` value in the INSERT statement

**Exit:** PolicyDecision round-trips cleanly. `evaluated_at` reflects decision time,
not insertion time.

**Files touched:**
- `middleware/policy.py`

### 1.4 Schema / Canon Reconciliation

**Problem:** `core.sql` declares 16 tables. Canon (CLAUDE.md §6) references 14 core
tables. The gap is `document_sets` + `document_set_members`, added by tech scout
injection and documented in core.sql as such.

**Work:**
- Update core.sql header comment to state "16 core tables (original 14 + 2
  document_set tables from tech scout injection §25)"
- Update CLAUDE.md §6 or add a note that core.sql now contains 16 tables

**Exit:** No discrepancy between code comments and project documentation.

**Files touched:**
- `migrations/core.sql` (header comment)
- `CLAUDE.md` (§6 reference)

### 1.5 Test Hygiene

**Problem:** 5 pre-existing test failures on standard dev machine. MinIO connectivity
test fails when MinIO is offline. 4 poster acceptance tests fail when external
services unavailable. This makes `pytest` noisy and masks real regressions.

**Work:**
- Define a default local suite that must be green without external services
- Add `pytest.mark.skipif` guards for MinIO connectivity tests (check MinIO reachable)
- Add `pytest.mark.skipif` guards for poster acceptance tests (check required
  services)
- Add a `pytest.ini` marker: `integration` for tests requiring infrastructure
- Default `pytest` invocation excludes `integration`; `pytest -m integration` runs them

**Exit:** `pytest` (default) shows 0 failures on standard dev machine. Integration
tests skip cleanly. `pytest -m integration` runs the full suite when infra is up.

**Files touched:**
- `tests/test_e2e_layer1_connectivity.py` (skip guards)
- `tests/test_user_pov_poster_acceptance.py` (skip guards)
- `pytest.ini` or `pyproject.toml` [tool.pytest] (marker definition)

### 1.6 Session↔Job Correlation

**Problem:** `hermes_session_id` column exists in `jobs` table (`core.sql:33`) but
nothing populates it. `run_governed()` has no `hermes_session_id` parameter. The
bridge captures session_id in `_SESSION_STATE` but never passes it downstream.

**Work:**
- Add `hermes_session_id: str | None = None` to `run_governed()` signature
- Write it into the `jobs` row (created in 1.2)
- Include it in `job_context` dict so downstream can access it

**Dependency:** 1.2 (job lifecycle) must land first.

**Exit:** Every governed job traceable to its Hermes session via `jobs.hermes_session_id`.

**Files touched:**
- `tools/orchestrate.py` (param + job_context)
- `plugins/vizier_tools_bridge.py` (pass session_id from `_SESSION_STATE`)

### 1.7 Telemetry Linkage

**Problem:** Langfuse helpers exist in `middleware/observability.py:105` but the
actual trace push may not be wired into the governed completion path. Even if
wired, traces lack `hermes_session_id` in metadata, making cross-system correlation
impossible.

**Work:**
- Verify `trace_to_langfuse()` is called on governed completion in
  `orchestrate.py` or `executor.py`. Wire it if not.
- Add `hermes_session_id` to the Langfuse trace metadata dict

**Dependency:** 1.6 (session_id in job_context).

**Exit:** Langfuse traces include `hermes_session_id` in metadata and are filterable
by session.

**Files touched:**
- `middleware/observability.py` (metadata addition)
- `tools/orchestrate.py` or `tools/executor.py` (verify/wire trace push)

### 1.8 Media Bridge Extension

**Problem:** Bridge filters to images only in `vizier_tools_bridge.py:312`. Audio
and document attachments from gateway env vars are silently dropped. `run_governed()`
only accepts `reference_image_path` / `reference_image_url`.

**Work:**
- Define `media_manifest` as a list of dicts:
  ```python
  # Each entry in media_manifest
  {
      "path": str | None,      # local filesystem path
      "url": str | None,       # remote URL (path-or-URL, not both required)
      "mime_type": str,         # e.g. "image/png", "audio/mpeg", "application/pdf"
      "role": str,              # "primary_image" | "reference" | "attachment"
  }
  ```
- Stop filtering non-image types in bridge `_extract_env_media_context()`
- Add `media_manifest: list[dict] | None = None` to `run_governed()` signature
- Keep backward compat: `reference_image_path` / `reference_image_url` still work
  and are auto-populated from the manifest's `primary_image` entry
- Downstream tools can inspect manifest for audio/doc attachments when ready

**Exit:** All gateway media reaches orchestrate. No silent data loss. Image-only
consumers still work via existing fields.

**Files touched:**
- `plugins/vizier_tools_bridge.py` (build manifest, stop filtering)
- `tools/orchestrate.py` (accept manifest, extract primary_image for compat)

### 1.9 Smoke Script (acceptance gate — runs last)

**Problem:** No single command validates the system is operational. Proving the
integration requires tribal knowledge about which pieces to check.

**Work:**
- `scripts/smoke.sh` validates (in order):
  1. Plugin installed and matches repo version
  2. Bridge module importable
  3. Hermes gateway env seam present (check for run.py media export)
  4. Database reachable and schema applied (tables exist)
  5. Exemplars table non-empty
  6. Migrations idempotent (re-run without error)
  7. One dry-run governed poster path (can be mocked LLM call)
- Exit code 0 = system alive, non-zero = specific failure identified

**Dependency:** All other Track 1 items. This is the acceptance gate.

**Exit:** `scripts/smoke.sh` passes on a freshly set up machine after
`git submodule update --init && scripts/install_plugin.sh && psql -f migrations/core.sql`.

**Files touched:**
- `scripts/smoke.sh` (new)

---

## Track 2: Output Quality & Variety

**Goal:** 10 benchmark briefs produce brief-adherent outputs across 6+ distinct
layout families at Canva-template level.

**Exit criteria (all must be true):**
- Benchmark set has stable pass/fail results
- System reliably produces "good Canva-template-level" outputs on the benchmark set
- Adherence is explicitly measured, not inferred
- At least 6 distinct layout families appear across 10 briefs
- No more than 2 briefs collapse to the same layout family unless brief semantics justify it
- Revisions improve failed outputs for known, specific reasons
- Median human quality/adherence rating clears target threshold

### 2.1 Quality Benchmark Corpus

**Problem:** No frozen reference briefs exist. Quality is evaluated ad-hoc. Can't
measure if changes improve or regress output.

**Work:**
- Create `evaluations/benchmark/` with 20-30 YAML brief files
- Cover intentionally adversarial combinations:
  - Same client, different occasion (festive vs corporate vs promo)
  - Same occasion, different density (minimal vs dense)
  - Bilingual (EN and BM variants of same brief)
  - Reference-led vs no reference
  - Promo-heavy (price, badge, offer) vs prestige/minimal
  - Event invite vs product showcase vs announcement
- Each brief includes:
  - `raw_input` (the actual request text)
  - `expected_characteristics` (layout family, tone, must-include elements)
  - `quality_floor` (minimum acceptable scores per dimension)

**Parallel with Track 1:** This is YAML authoring, no code dependency.

**Exit:** Frozen corpus. Every quality change runs against it.

**Files touched:**
- `evaluations/benchmark/*.yaml` (new, 20-30 files)

### 2.2 Adherence Rubric & Harness

**Problem:** Quality is "looks good" — no operational definition, no measurement.
Need to define what "good" means before building templates.

**Work:**
- Define scoring dimensions (each 1-5):
  1. **Brief adherence** — does the output match the requested occasion/audience/theme?
  2. **On-brand fit** — correct palette, tone, typography for client?
  3. **Layout quality** — visual hierarchy, spacing, readability?
  4. **CTA clarity** — is the action clear and prominent?
  5. **Copy usefulness** — relevant, concise, appropriate register?
  6. **Reference handling** — if reference provided, is it reflected?
  7. **Output variety** — across similar briefs, are outputs distinct?
- Build `tools/quality_harness.py`:
  - Takes a benchmark brief, runs governed pipeline (or loads cached output)
  - Scores output against rubric via GPT-5.4-mini judge
  - Produces per-dimension scores + aggregate
  - Reports floor, median, and worst-case across corpus

**Exit:** Can measure quality operationally. "Good enough" has a number.

**Files touched:**
- `config/quality_frameworks/adherence_rubric.yaml` (new)
- `tools/quality_harness.py` (new)
- `evaluations/benchmark/` (referenced)

### 2.3 Canonical Interpreted Intent

**Problem:** `raw_input` flows through as unstructured text. RoutingResult doesn't
capture occasion, audience, or mood. Template selection, copy generation, image
prompting, and QA all see the raw string differently.

**Relationship to `expand_brief()`:** The interpreted intent becomes the **canonical
parse** — structured extraction from the raw request. `expand_brief()`
(`image.py:122`) becomes a **visual elaboration step** that consumes the interpreted
intent for image-specific composition guidance. This avoids two independent parsers
and duplicated token spend.

**Work:**
- Create `tools/brief_interpreter.py`:
  - One GPT-5.4-mini call with structured output
  - Extracts: `{occasion, audience, mood, layout_hint, text_density, cta_style,
    cultural_context, must_include: list[str], must_avoid: list[str]}`
  - Returns a typed `InterpretedIntent` (Pydantic model)
- Call at start of `run_governed()`, write result to `jobs.interpreted_intent`
  (JSONB column already exists at `core.sql:29`)
- Pass into `job_context` so all downstream stages can use it
- Update `expand_brief()` to accept and consume `interpreted_intent` instead of
  re-parsing from scratch

**Exit:** Single parse, single source of truth. Structured intent visible in DB.
`expand_brief()` consumes it, doesn't duplicate it.

**Files touched:**
- `tools/brief_interpreter.py` (new)
- `tools/orchestrate.py` (call interpreter, write to DB, add to job_context)
- `tools/image.py` (`expand_brief()` consumes intent)
- `contracts/` (InterpretedIntent model, new file or in existing)

### 2.4 Poster Content Schema / Slots

**Problem:** The entire poster content model is 4 fields: `headline`, `subheadline`,
`cta`, `body_text` (`registry.py:639`). The template accepts those 4 plus
`background_image`, `logo_url`, `primary`, `accent`, `font_headline`, `font_body`.
This caps both variety and adherence — many Canva-level layouts need slots like
price blocks, event metadata, badges, or disclaimers that have no place in the
current schema.

**Work:**
- Define `PosterContentSchema` with required and optional slots:

  **Required** (every template must render these if provided):
  - `headline: str`
  - `body_text: str`
  - `cta: str`
  - `background_image: str` (path or URL)

  **Optional** (templates declare which they support via `_meta.yaml`):
  - `subheadline: str`
  - `kicker: str` (small text above headline — date, category, label)
  - `event_meta: dict` (date, time, venue, dress code)
  - `offer_block: dict` (discount %, original price, sale price, validity)
  - `badge: str` (corner badge — "NEW", "SALE", "LIMITED")
  - `price: str` (standalone price display)
  - `footer: str` (fine print, address, contact)
  - `disclaimer: str` (regulatory, terms)
  - `logo_treatment: str` (top-right circle, bottom-left inline, watermark)
  - `secondary_cta: str`

- Update copy generation to output the full schema (not just 4 fields)
- Update `_parse_poster_copy()` (`registry.py:636`) to handle new slots
- **Backward compat:** `poster_default.html` and `poster_road_safety.html` continue
  to work — they simply ignore optional slots they don't support. New templates
  declare supported slots in their `_meta.yaml`.

**Exit:** 6-8 content slots supported end-to-end: interpreter → copy generation →
template rendering → QA scoring.

**Files touched:**
- `contracts/poster.py` (new — PosterContentSchema)
- `tools/registry.py` (copy generation + parsing)
- `templates/html/poster_default.html` (no change needed — backward compat)

### 2.5 Poster Template Library

**Problem:** 2 templates in `templates/html/` (`poster_default`, `poster_road_safety`).
`_TEMPLATE_ALIASES` collapses `corporate_premium`, `premium_traditional`,
`warm_heritage` all to `poster_default`. 34 sophisticated layouts exist in
`templates/visual/` but are not used by the poster pipeline.

**Work:**
- Create 8-10 new HTML poster templates in `templates/html/`, each covering a
  distinct layout family:
  1. `poster_editorial_split.html` — 55/45 image|text grid with vertical divider
  2. `poster_diagonal_cut.html` — image clipped at diagonal, accent stripe
  3. `poster_bold_knockout.html` — knockout typography with image showing through
  4. `poster_floating_card.html` — content card floating on image background
  5. `poster_center_stage.html` — radial vignette, centered content
  6. `poster_hero_bottom.html` — large hero, text overlay at bottom (similar to current default but distinct)
  7. `poster_stacked_type.html` — typography-led, minimal image
  8. `poster_minimal_clean.html` — generous whitespace, premium feel
  9. `poster_promo_grid.html` — price block, offer badge, sale-oriented layout
  10. `poster_event_invite.html` — event meta (date, venue), RSVP CTA
- Each template gets a companion `_meta.yaml`:
  ```yaml
  density: minimal | moderate | dense
  tone_fit: [premium, bold, festive, formal, playful, ...]
  occasion_fit: [corporate, event, promo, festive, product, announcement]
  cta_prominence: high | medium | low
  hero_style: full_bleed | contained | split | minimal
  supported_slots: [headline, subheadline, cta, kicker, event_meta, ...]
  ```
- Draw layout concepts from `templates/visual/` (the proven designs), adapted for
  poster rendering dimensions (794×1123px)

**Exit:** 10+ poster templates with metadata. Visual diversity purpose-built for the
poster renderer.

**Files touched:**
- `templates/html/poster_*.html` (8-10 new files)
- `templates/html/poster_*_meta.yaml` (8-10 new files)

### 2.6 Template Selector

**Problem:** `_resolve_template_name()` (`registry.py:96`) checks for exact
template name match, then falls through to `poster_default`. The alias table
collapses most design systems to the same output.

**Work:**
- Replace `_resolve_template_name()` and `_TEMPLATE_ALIASES` with intent-aware
  scoring:
  - Load all `_meta.yaml` files from `templates/html/`
  - Score each template against:
    - `interpreted_intent.mood` ↔ `tone_fit` (set intersection)
    - `interpreted_intent.occasion` ↔ `occasion_fit`
    - `interpreted_intent.text_density` ↔ `density`
    - `interpreted_intent.cta_style` ↔ `cta_prominence`
    - Slot compatibility: template must support the slots that copy generation produced
    - Client `style_hint` and design system preferences
  - Return top-scoring template (with tiebreaker: prefer more specific over generic)

**Exit:** Different briefs select different templates. Same client gets 5+ distinct
layouts depending on occasion. `poster_default` becomes a true fallback, not the
only destination.

**Files touched:**
- `tools/registry.py` (replace `_resolve_template_name`, remove `_TEMPLATE_ALIASES`)

### 2.7 Copy / Prompt Enrichment

**Problem:** Copy generation system prompt is generic ("Generate poster copy") plus
brand defaults. Occasion, audience, tone, and must-include elements from the
interpreted intent don't shape the copy.

**Work:**
- Inject `interpreted_intent` into the copy generation system prompt:
  - Occasion → shapes framing ("This is a festive Hari Raya poster..." vs
    "This is a formal corporate anniversary...")
  - Audience → shapes register and vocabulary
  - Must-include → becomes hard constraints ("Must mention: date, venue, dress code")
  - Must-avoid → becomes negative constraints
  - Cultural context → shapes imagery references and language choices
- Generate content for all applicable `PosterContentSchema` slots, not just the
  original 4 fields. If the interpreted intent has event_meta or offer details,
  the copy stage should produce those slots.

**Exit:** Copy reflects the specific request, not just the brand. Slot-rich briefs
produce slot-rich content.

**Files touched:**
- `tools/registry.py` (copy generation prompt construction)

### 2.8 Runtime Adherence Gating

**Problem:** Tripwire and visual scoring check generic quality (text_visibility,
design_layout, colour_harmony, overall_coherence per
`posteriq_quality_dimensions.yaml`). A pretty poster that ignores the brief passes QA.

**Work:**
- Add adherence-specific scoring dimensions to the quality framework:
  - "Did the output preserve the requested theme/occasion?"
  - "Did it reflect the reference composition (if provided)?"
  - "Did it match the requested tone and density?"
  - "Did it include required commercial/event info clearly?"
- These feed into tripwire alongside existing visual quality scores
- Separate adherence score from aesthetic score in production_trace
- Critique-then-revise loop uses adherence failures as specific revision guidance

**Exit:** Brief-ignoring output fails QA even if visually attractive. Revision
targets specific adherence gaps.

**Files touched:**
- `config/quality_frameworks/adherence_dimensions.yaml` (new)
- `tools/visual_scoring.py` (adherence scoring)
- `tools/executor.py` (tripwire uses adherence score)

### 2.9 Exemplar Curation

**Problem:** Current exemplars are synthetic seeds with fake CLIP embeddings
(`scripts/seed_exemplars.py`). Similarity search returns results but they have no
real visual DNA.

**Work:**
- Run 10-15 benchmark briefs through the hardened pipeline
- Manually rate outputs (using the adherence rubric from 2.2)
- Promote best outputs (rating >= 4) to exemplars table with real CLIP embeddings
  computed from actual rendered poster images
- Replace synthetic seed data with real production exemplars
- Mark 3-5 top-rated as anchor_set feedback for drift detection

**Dependency:** 2.5 (template library) and 2.7 (copy enrichment) must land first so
the outputs are worth keeping.

**Exit:** Exemplar similarity search returns genuinely useful style anchors with real
visual DNA.

**Files touched:**
- `scripts/seed_exemplars.py` (update or replace with real data script)
- `evaluations/benchmark/` (rated outputs stored)

---

## Post-Hardening (deferred)

These items are valuable but not part of the hardening gate:

- **Self-improvement promotion loop** — auto-promote rated artifacts to exemplars.
  Changes behavior, data growth, and promotion policy. Do after hardening validates
  the quality floor.
- **Cross-session memory** — Hermes MemoryProvider adapter. Needs design decisions
  and production data. Chunk 3.
- **Full inner-stage Hermes visibility** — architectural change to make Hermes see
  governed stages as first-class events. Chunk 4.
- **Brochure / ebook quality hardening** — separate pass using same patterns
  established here for posters.

---

## Sequencing

```
Track 1 (reliability)              Track 2 (quality)
──────────────────────             ──────────────────
1.1 Pin deployment boundary         2.1 Benchmark corpus    ← parallel
1.2 Job lifecycle hardening         2.2 Adherence rubric    ← parallel
1.3 Policy persistence fix
1.4 Schema reconciliation
1.5 Test hygiene
1.6 Session↔job correlation
1.7 Telemetry linkage
1.8 Media bridge extension
1.9 Smoke script (acceptance gate)
         ↓
    Track 1 complete
         ↓
                                    2.3 Canonical interpreted intent
                                    2.4 Poster content schema
                                    2.5 Template library
                                    2.6 Template selector
                                    2.7 Copy enrichment
                                    2.8 Runtime adherence gating
                                    2.9 Exemplar curation
```

2.1 and 2.2 can start during Track 1 (YAML/config authoring, no code dependency).
Track 2 items 2.3-2.9 are sequential — each builds on the prior.
Track 1.9 (smoke script) is the acceptance gate and runs last.

---

## Verification Strategy

**Track 1 verification:**
- `scripts/smoke.sh` passes on fresh setup
- `pytest` (default) shows 0 failures
- `pytest -m integration` runs full suite when infra is up
- `scripts/check_plugin_drift.sh` reports no drift

**Track 2 verification:**
- Quality harness runs full benchmark corpus
- Median adherence score >= 3.5/5
- At least 6 distinct layout families across 10 representative briefs
- No more than 2 briefs collapse to same family unless semantically justified
- Worst-case quality score >= 2.5/5 (no catastrophic failures)
