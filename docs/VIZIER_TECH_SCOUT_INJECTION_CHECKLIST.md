# VIZIER SPRINT — Tech Scout Injection Checklist

**Date:** 7 April 2026  
**Purpose:** Maps every extraction from the tech scout session into the exact sprint session, with what to add to worker prompts, exit criteria, and CLAUDE.md.

**Reference:** VIZIER_SPRINT_IMMEDIATE_EXTRACTIONS v1.3.0 (10 items + 2 implementation notes)

---

## S0 — Repo Scaffold (COMPLETED — verify these were included)

| Item | What to verify | If missing |
|---|---|---|
| #7 GEPA in pyproject.toml | `gepa>=0.1.0` in pyproject.toml dependencies | Add to pyproject.toml now — `pip install gepa --break-system-packages` |
| #4 Connector interface stub | `connectors/__init__.py` with `BaseConnector` ABC + `connectors/manual.py` with MinIO adapter stub | Create now — ~30 lines, see sprint extractions doc for exact code |
| #9 GEPA model strategy doc | `docs/decisions/gepa_model_strategy.md` exists | Create now — copy from sprint extractions doc Item #9 |

**S0 directory structure additions to verify:**

```
vizier/
├── connectors/
│   ├── __init__.py       # BaseConnector ABC + ConnectorDocument dataclass
│   └── manual.py         # MinIO manual upload adapter (stub)
├── datasets/
│   └── gepa_bootstrap/   # empty dir, populated by S5
```

---

## S1 — Config Authoring (COMPLETED — verify these were included)

| Item | What to verify | If missing |
|---|---|---|
| #5 Marketing mutation operators | `config/critique_templates/poster_quality.md` has 10 variation axes (CTA_POSITION, CTA_COLOUR, HEADLINE_URGENCY, etc.) | Append the variation axes section — see sprint extractions doc Item #5 |
| #1 (evolution) Mutation operators YAML | `config/improvement_rules/mutation_operators.yaml` with 10+ operators | Create the file — copy from evolution roadmap v1.2 Extraction #1 |
| #10 Eval YAML test cases | `config/evaluations/` directory with per-client YAML files | Create directory + 3-5 test cases per client — see sprint extractions doc Item #10 |
| Structured visual brief schema | `config/prompt_templates/visual_brief_expander.md` outputs structured JSON (composition, style, brand, technical, text_content) | S5 creates visual_brief_expander.md — add schema note to S5 worker prompt instead |
| Reminder prompt YAML field | WorkflowPack YAML schema recognises `reminder_prompt` field | This is a schema awareness item — S9 implements it. No S1 action needed. |

**S1 files to verify exist:**

```
config/
├── improvement_rules/
│   └── mutation_operators.yaml     # 10+ operators with id, description, when
├── evaluations/
│   ├── poster_production_dmb.yaml        # 3-5 test cases
│   ├── poster_production_ar_rawdhah.yaml # 3-5 test cases
│   └── poster_production_rtm.yaml        # 3-5 test cases
├── critique_templates/
│   └── poster_quality.md           # verify: has "Variation Axes" section at bottom
```

---

## S2 — Typst + Fonts + Templates (COMPLETED)

No tech scout injections. S2 is Typst templates — none of the extractions touch this session.

---

## S4 — Endpoint Testing (UPCOMING — Block 2)

**Add to S4 worker prompt — 2 additions:**

### Addition 1: Free Nano Banana draft tier test

Add to "Other endpoint tests" section:

```
- Test OpenRouter free Nano Banana endpoint for BM text rendering quality.
  Same 5 BM poster test cases as Nano Banana Pro.
  Compare: is draft quality acceptable for iteration/preview (not production)?
  Record go/no-go in docs/decisions/nano_banana_draft_tier.md.
  If go: note for S9 to add `draft_preview: nano-banana-openrouter` to image_model_preference in WorkflowPack YAMLs.
```

### Addition 2: Per-generation cost logging pattern

Add to S4 implementation notes:

```
- Log per-generation cost for every image generation test.
  Pattern: model name, size, cost_usd, timestamp → append to test results.
  This pattern becomes the Media agent's cost tracking in production.
  Source: nano-banana-2-skill cost tracking pattern.
```

**S4 exit criteria additions:**

```
- OpenRouter free Nano Banana tested for BM text quality — go/no-go in docs/decisions/
- Per-generation cost logged for all image tests (model, size, cost)
```

---

## S5 — Dataset Processing (UPCOMING — Block 2)

**Add to S5 worker prompt — 1 addition:**

### Addition: GEPA bootstrap preference conversion

Add as Item 16 in the S5 task list (Hour 3-4, non-blocking):

```
16. Convert poster quality datasets to GEPA preference pair format:
    - D2 (Poster-Preference-100K, 5K subset) → direct preference pairs
    - D3 (Poster-Reflect-120K, 5K subset) → preference + diagnosed failure feedback
    - D12 (PosterIQ-7,765) → dimension-derived preference pairs
    
    Output: datasets/gepa_bootstrap/d2_prefs.jsonl, d3_prefs.jsonl, d12_prefs.jsonl
    
    Format per line:
    {"input": "<context>", "preferred": "<winner_id>", "rejected": "<loser_id>",
     "score": 1.0, "feedback": "<why winner is better — from dataset annotations>"}
    
    For D3: feedback field includes the diagnosed failure explanation (this is
    GEPA's Actionable Side Information — the richest training signal).
    
    ~20 lines conversion code. These bootstrap GEPA with ~13,000 preference
    examples before the first production poster is rated.
```

### Addition: Structured visual brief schema

Add to Item 1 (visual brief expander extraction from PosterCraft):

```
When extracting visual_brief_expander.md from PosterCraft recap agent (R3),
structure the output as JSON with named sections rather than freeform text:
  composition: {layout, focal_point, text_zones, safe_zones}
  style: {aesthetic, colour_palette, colour_temperature, typography_feel}
  brand: {logo_placement, brand_colours_required, product_visibility}
  technical: {platform, ratio, min_resolution, text_overlay, illustration_text_free}
  text_content: {headline, cta, register, max_word_count}

This structured format enables: (1) Coder agent reads composition+technical for HTML scaffold,
(2) Media agent reads style for illustration generation, (3) GEPA can diff two briefs
structurally to identify which dimensions drive preference scores.
```

**S5 exit criteria addition:**

```
- GEPA bootstrap preferences produced: D2 (~5,000 pairs), D3 (~5,000 pairs with diagnosed feedback), D12 (~3,000 pairs). Stored in datasets/gepa_bootstrap/. Total: ~13,000 preference examples.
- Visual brief expander outputs structured JSON with named sections (composition, style, brand, technical, text_content), not freeform text.
```

---

## S6 — Governance Contracts (UPCOMING — Block 2)

No tech scout injections. S6 is contracts — the extractions don't touch governance.

---

## S7 — Local Spans + Memory Routing (UPCOMING — Block 2)

No tech scout injections. S7 is observability infrastructure.

---

## S8 — Policy + Observability (Block 3)

No tech scout injections.

---

## S9 — Packs + Workflows + Tripwire (Block 3)

**Add to S9 worker prompt — 2 additions:**

### Addition 1: Reminder prompt field in WorkflowPack YAML schema

```
Add `reminder_prompt` as an optional field in the WorkflowPack YAML schema.
When present and stage.role == "production", the executor appends this text
to the END of the user message (not system prompt) before the final LLM call.

Format: reminder_prompt is a string with {variable} placeholders resolved
from job context (client_name, copy_register, etc.).

Implementation in executor (~5 lines):
  if workflow.reminder_prompt and stage.role == "production":
      user_message += "\n\n" + workflow.reminder_prompt.format(**job_context)

Add reminder_prompt to at least childrens_book_production.yaml and poster_production.yaml:

  # In childrens_book_production.yaml:
  reminder_prompt: |
    REMINDER: This output is for {client_name}. Register: {copy_register}.
    Illustrations MUST be text-free. Use illustration_shows field, not page text.
    Quality dimensions: {critique_dimensions}.

  # In poster_production.yaml:
  reminder_prompt: |
    REMINDER: Client: {client_name}. Register: {copy_register}.
    CTA must be visible. Brand colours required. Platform: {platform}.
```

### Addition 2: Free Nano Banana draft tier in image_model_preference

```
IF docs/decisions/nano_banana_draft_tier.md from S4 says "go":
Add draft_preview tier to image_model_preference in WorkflowPack YAMLs:

  image_model_preference:
    text_heavy: nano-banana-pro
    draft_preview: nano-banana-openrouter  # free, draft quality
    photorealistic: flux-2-pro
    character_iterative: flux-kontext-pro
    draft: flux-2-dev
    element: flux-2-dev
```

**S9 exit criteria additions:**

```
- `reminder_prompt` field supported in WorkflowPack YAML schema
- Executor appends reminder_prompt to user turn on production stages when field is present
- childrens_book_production.yaml and poster_production.yaml both have reminder_prompt fields
- Verified: reminder_prompt {variables} resolve correctly from job context
```

---

## S10a — Data Foundation (Block 4)

**Add to S10a worker prompt — 1 addition:**

### Addition: Document set tables

```
Add 2 tables to migrations/core.sql (after knowledge_cards table):

CREATE TABLE IF NOT EXISTS document_sets (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  description text,
  client_id uuid references clients(id),
  is_default boolean default false,
  status text default 'active',
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS document_set_members (
  id uuid primary key default gen_random_uuid(),
  document_set_id uuid references document_sets(id) on delete cascade,
  knowledge_card_id uuid references knowledge_cards(id) on delete cascade,
  added_at timestamptz default now(),
  unique(document_set_id, knowledge_card_id)
);

Test: insert 'dmb_docs' set, assign 3 test cards, query cards via set membership.
Verify: clientless mode uses 'generic_docs' default set.
```

**S10a exit criteria addition:**

```
- `document_sets` and `document_set_members` tables created with IF NOT EXISTS
- Test: insert document set, assign knowledge cards, query via membership
- Core table count: 16 (was 14 + 2 new document set tables)
```

---

## S11 onwards — no sprint-day injections

S11 (routing), S12 (research), S13 (visual intel), S15 (publishing) — no tech scout items. These sessions build on the foundations where injections already landed.

S18 (knowledge spine) — retrieval profiles should filter by document_set when available (add note to S18 worker prompt: "If document_sets table exists from S10a, filter retrieval by document set membership instead of client_id tag").

S19 (self-improvement) — this is where GEPA activates post-sprint. The build plan already includes pattern detection, failure analysis, experiment framework. Add note to S19 worker prompt: "GEPA is installed (pyproject.toml). VizierAdapter and eval_runner.py are Week 1 post-sprint builds — S19 provides the infrastructure they plug into. Ensure experiments table schema supports preference pair storage (winner_id, loser_id, preference_source) alongside absolute ratings."

---

## CLAUDE.md Additions

### Addition to §2 Navigation Map:

Add one row:

```
| S5 | Dataset processing | §38 (design intelligence), §7.6 (golden dataset) | #24, #41 |
```

Add note under S5 row: "Also produces GEPA bootstrap preferences in datasets/gepa_bootstrap/ (~13,000 pairs from D2/D3/D12)."

### Addition to §3 Shared Interfaces:

Add after the `contracts/publishing.py` block:

```python
# connectors/__init__.py — CREATED BY S0, IMPLEMENTED POST-SPRINT
# BaseConnector with Load/Poll/Slim modes for external data ingestion.
# Manual upload via MinIO is the only implementation during sprint.
# Future: Google Drive, Instagram, WhatsApp connectors implement same interface.
```

### Addition to §5 Build Conventions — File placement:

```
- GEPA bootstrap data → `datasets/gepa_bootstrap/`
- Evaluation test cases → `config/evaluations/`
- Improvement rules → `config/improvement_rules/`
- Connector implementations → `connectors/`
```

### Addition to §7 What NOT to Do:

```
**GEPA / Improvement Loop:**
- ❌ Do NOT build VizierAdapter, eval_runner, or Preference Arena during the sprint — these are Week 1 post-sprint
- ❌ Do NOT run GEPA optimization during the sprint — it needs production data
- ❌ Do NOT route GPT-5.4 to production tasks — GEPA validation judging is quality assurance, not production (#54 compliance)
```

---

## Summary — What Goes Where

| Item | Session | Status | Action |
|---|---|---|---|
| GEPA in pyproject.toml | S0 | Verify | Check pyproject.toml |
| Connector interface stub | S0 | Verify | Check connectors/ directory |
| GEPA model strategy doc | S0 | Verify | Check docs/decisions/ |
| Mutation operators YAML | S1 | Verify | Check config/improvement_rules/ |
| Variation axes in critique template | S1 | Verify | Check poster_quality.md |
| Eval YAML test cases | S1 | Verify | Check config/evaluations/ |
| Free Nano Banana draft test | S4 | **Inject** | Add to S4 worker prompt |
| Cost tracking pattern | S4 | **Inject** | Add to S4 worker prompt |
| GEPA bootstrap preferences | S5 | **Inject** | Add as Item 16 to S5 worker prompt |
| Structured visual brief schema | S5 | **Inject** | Add note to Item 1 in S5 worker prompt |
| Reminder prompt in executor | S9 | **Inject** | Add to S9 worker prompt |
| Nano Banana draft tier in YAMLs | S9 | **Inject** | Conditional on S4 decision |
| Document set tables | S10a | **Inject** | Add 2 tables to core.sql |
| Document set filtering | S18 | **Note** | Add to S18 worker prompt |
| GEPA infrastructure | S19 | **Note** | Add preference pair columns to experiments table |

**S0/S1 items:** Verify now. If missing, create before launching Block 2.  
**S4/S5 items:** Inject into Block 2 worker prompts before launch.  
**S9/S10a items:** Inject into Block 3-4 worker prompts when generated.  
**S18/S19 items:** Notes for Day 3 worker prompts.

**Total injection effort:** Zero schedule impact. Each injection adds 5-20 lines to an existing worker prompt. No new sessions, no new blocks, no dependency changes.
