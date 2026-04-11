# Handover: GPT 7-Day Sprint (8.4 → 9.0/10)

**Date:** 2026-04-09  
**Branch:** `main` at `ff4a9bd`  
**Tests:** 854 passed, 46 skipped, 0 failed  
**All pushed to origin.**

---

## Context

GPT evaluated Vizier at **8.4/10** and identified 3 structural weaknesses blocking 9/10:

1. **Config vs structure leakage** — routing logic baked into Python instead of config
2. **Governance not fully auditable** — policy decisions not all persisted, no immutable specs
3. **"Soft truth"** — implicit defaults, silent assumptions, no explicit uncertainty

**Codex cross-check (2026-04-09)** revised priorities after scanning the actual repo:

- **Routing leakage is mostly fixed** — registry YAML + utils loader are live. Only 3 residual frozensets remain.
- **ArtifactSpec is already frozen** — `model_config = ConfigDict(frozen=True)` at `contracts/artifact_spec.py:114`. Day 3 (immutability) dropped as a standalone day.
- **Two new HIGH/MEDIUM issues found:**
  - Listening subsystem has broken imports (`adapter`, `exceptions` modules don't exist)
  - phase.yaml marks 9 workflows as `core: active` but only 2 are truly deliverable end-to-end

Sprint reordered to fix concrete breakage before abstract architecture debt.

---

## What Was Completed Before This Sprint

### Track 1: Poster Lane Hardened
- Typst fallback now runs `evaluate_rendered_poster()` (was skipped)
- Runtime readiness hard-blocks on missing DB/OPENAI_API_KEY
- Post-render revision V1: one deterministic CSS retry for text-overlay failures
- `classify_post_render_failure()` routes to `retryable` or `fail_stop`
- Commits: `dcbd1b8`, `35b317d`

### Track 2: Document Lane E2E
- Real `_typst_render` (template mode + source mode + auto-wrap plain text)
- `_deliver_document` with structural QA (exists, non-zero, min 500 bytes)
- Real pipeline tests (Typst compiles, no mocks on local tools)
- Commits: `35996a3`, `1a8d1e5`

### Codex P2 Fixes
- `_DELIVERABLE_WORKFLOWS` narrowed to `{poster_production, document_production}` only
- `typst_render` removed from `_STUB_TOOL_NAMES`
- Commit: `ff4a9bd`

---

## The 7-Day Sprint Plan (Revised)

### Day 1: Import Integrity — Fix Broken Listening Subsystem
**Status: NOT STARTED**

**Goal:** Every Python module in the repo can be imported without error.

**The problem:**
The entire `augments/listening/` subsystem is broken — three files import from modules that don't exist:
- `collector.py:11` — `from adapter.llm_client import chat as llm_chat` (no `adapter` module)
- `watchlist.py:8` — `from exceptions import InputCheckError` (no `exceptions` module)
- `store.py:19` — `from exceptions import WatchlistNotFoundError` (no `exceptions` module)

Any code that touches `augments.listening` will crash at import time. The `__init__.py` eagerly imports `Collector`, so even `from augments.listening import X` fails.

**What to do:**
1. **Determine intent:** Is listening a future feature (S12/S16 dependency) or was it ported from pro-max with missing dependencies?
2. **If future/not-yet-built:** Convert `__init__.py` to lazy imports or remove the eager re-export. Add a `# TODO: depends on adapter module (S12)` marker. Ensure `from augments.listening.watchlist import ListeningItem` works in isolation (move `InputCheckError` / `WatchlistNotFoundError` to a local exceptions file within the listening package).
3. **If ported with missing deps:** Create `adapter/llm_client.py` with the `chat` function signature (stub or real), and a top-level `exceptions.py` with the two exception classes.
4. **Verify:** `python3 -c "import augments.listening"` must succeed.
5. **Run pyright** on all changed files.
6. **Run full test suite** — confirm 854+ pass, 0 fail.

**Key judgment call:** Don't build out the listening engine — just fix the import graph so the subsystem doesn't poison anything that touches it. Minimum viable fix.

---

### Day 2: Workflow Truthfulness — Reconcile Phase/Stub/Delivery Gates
**Status: NOT STARTED**

**Goal:** `phase.yaml` active flags, `_DELIVERABLE_WORKFLOWS`, `_STUB_TOOL_NAMES`, and actual tool implementations all tell the same story.

**The problem:**
- `config/phase.yaml` marks `core` phase as active with 9 workflows
- `tools/orchestrate.py:426` — `_DELIVERABLE_WORKFLOWS = frozenset({"poster_production", "document_production"})`
- `tools/registry.py:2622` — 16 stub tools exist for structurally-registered-but-not-implemented workflows
- So: routing will accept a `childrens_book_production` job (phase says active), execution will use stub tools (fake output), but delivery will block (not in `_DELIVERABLE_WORKFLOWS`)
- The system works correctly (stubs don't escape to users), but the config is misleading

**What to do:**
1. **Audit phase.yaml:** Should `core` list only truly E2E workflows? Or is "active for routing but not delivery" an intentional intermediate state? Document the decision.
2. **Option A — Narrow phase.yaml:** Only list workflows where all tools are real. Stubbed workflows move to inactive phases.
3. **Option B — Add a `deliverable` field to workflow_registry.yaml:** Keep routing broad but make deliverability explicit in config. `_DELIVERABLE_WORKFLOWS` reads from YAML instead of being hardcoded.
4. **Option C — Keep current layered defense:** Phase gates routing, `_DELIVERABLE_WORKFLOWS` gates delivery, stubs gate execution. Document this as intentional three-layer safety. Annotate phase.yaml with comments explaining the distinction.
5. **Whichever option:** Document in `docs/decisions/`, update any misleading comments, ensure `validate_workflow_registry()` checks the new invariant.
6. **Also audit `_DOCUMENT_WORKFLOWS`** (registry.py:1384) — same question as Day 1 of old plan.
7. **Run full test suite** after changes.

**Key judgment call:** Option B is probably right — it keeps the three-layer defense but makes it config-driven and honest. Option A would break routing tests. Option C is the least work but doesn't fix the truthfulness issue. The deciding factor: can you add a new deliverable workflow by changing YAML only?

---

### Day 3: Policy Symmetry — Full Audit Trail
**Status: NOT STARTED**

**Goal:** Every policy decision is persisted. No silent passes.

**What to check:**
- `middleware/policy.py` — `PolicyEvaluator.evaluate()` — does it log every decision (allow + deny), or only denials?
- `contracts/policy.py` — `PolicyAction` enum — does it cover all outcomes?
- `policy_logs` DB table schema — does it have enough columns for full audit?
- `tools/orchestrate.py` — after `policy_evaluator.evaluate()`, is the result always persisted?

**What to build:**
- Ensure every `PolicyEvaluator.evaluate()` call produces a `policy_logs` row
- Add `constraints_snapshot` to policy_logs (what rules were evaluated)
- Test: given a governed execution, verify `policy_logs` has a row for every policy check

---

### Day 4: Remove Soft Truth
**Status: NOT STARTED**

**Goal:** No implicit defaults. Every assumption is explicit and traceable.

**Known soft truths:**
- `contracts/routing.py:342` — `artifact_family=ArtifactFamily.document` as default for unclassified specs with `family_resolved=False`
- This is a "document until proven otherwise" assumption
- Should be `ArtifactFamily.unknown` (add to enum if needed) with explicit degrade paths

**What to do:**
1. Audit all `ArtifactFamily.document` usages — which are real classification vs default placeholder?
2. Add `ArtifactFamily.unknown` if it doesn't exist
3. Add explicit handling for `unknown` family — routing must either classify or reject
4. Audit all `default=` values in Pydantic models — are any hiding assumptions?
5. Document degrade paths: what happens when classification confidence < threshold?

---

### Day 5: Canon Reconciliation
**Status: NOT STARTED**

**Goal:** Architecture doc matches repo reality. No drift.

**What to do:**
- Read `docs/VIZIER_ARCHITECTURE.md` sections that cover routing (§8), quality (§7.4), publishing (§18, §42)
- Compare with actual implementations in `contracts/routing.py`, `tools/registry.py`, `middleware/policy.py`
- Where repo truth diverged from architecture (it has — Track 1/2 made changes), update the architecture
- Document any intentional deviations in `docs/decisions/`

**Note:** Architecture doc is gitignored (proprietary). Read from disk at the absolute path. Check memory file `od_001_gitignore_docs.md` for path info.

---

### Day 6: Prove One Airtight Governed Path
**Status: NOT STARTED**

**Goal:** Full chain integration test: route → intent → readiness → policy → execute → QA → deliver → trace → policy persist → lineage → feedback

**What to build:**
- One integration test that exercises the FULL governed pipeline for poster_production
- Not mocked — real routing, real readiness, real policy, real execution (but image generation can be mocked since it's external API)
- Verify every link in the chain produces expected artifacts:
  - RoutingResult stored on job
  - Readiness check passed (or blocked correctly)
  - PolicyLog row created
  - Execution trace captured
  - QA ran and scored
  - Delivery produced a file
  - Trace totals correct
  - Feedback record created

**This is where the Shared QA Contract (Track 3a) naturally emerges** — the test needs a unified assertion interface for quality gates.

---

### Day 7: Hardening Sweep
**Status: NOT STARTED**

**Goal:** Clean up technical debt exposed by Days 1-6.

**Checklist:**
- [ ] Dead stubs: any `_STUB_TOOL_NAMES` entries that are now implemented?
- [ ] False comments: any comments that describe old behavior?
- [ ] Shadow registries: any hardcoded workflow/tool lists that duplicate the YAML registry?
- [ ] Decision docs: any undocumented decisions from this sprint?
- [ ] Test coverage: any new code paths without tests?
- [ ] Pyright: any new type errors?
- [ ] Storage-level spec lineage: `supersedes_spec_id` or revision chain if needed (folded from old Day 3)

---

## Dropped / Folded Items

| Original Plan | Disposition | Reason |
|---------------|-------------|--------|
| Day 1: Kill Routing Leakage | Folded into Day 2 | Routing is already config-driven. Residual frozensets are part of the truthfulness audit. |
| Day 3: ArtifactSpec Immutability | Dropped as standalone day | Already frozen via `ConfigDict(frozen=True)`. Storage lineage folded into Day 7. |

---

## Key Files Reference

| File | What | Lines of Interest |
|------|------|-------------------|
| `augments/listening/collector.py` | Broken imports | L11: `from adapter.llm_client` |
| `augments/listening/watchlist.py` | Broken imports | L8: `from exceptions import InputCheckError` |
| `augments/listening/store.py` | Broken imports | L19: `from exceptions import WatchlistNotFoundError` |
| `config/workflow_registry.yaml` | Single source of truth for workflow metadata | All 16 workflows + density map |
| `config/phase.yaml` | Phase activation flags | L8: `core: active: true` with 9 workflows |
| `utils/workflow_registry.py` | Loader/validator for registry YAML | `validate_workflow_registry()` L111, `get_active_workflow_descriptions()` L89 |
| `contracts/routing.py` | Fast-path + LLM router + refinement + design system selector | Already imports from registry util (L35-39) |
| `contracts/artifact_spec.py` | ProvisionalArtifactSpec (frozen) + ArtifactFamily enum | L114: `ConfigDict(frozen=True)` |
| `tools/orchestrate.py` | Governed execution chain | `_DELIVERABLE_WORKFLOWS` L426 |
| `tools/registry.py` | Tool implementations | `_DOCUMENT_WORKFLOWS` L1384, `_STUB_TOOL_NAMES` L2622 |
| `middleware/policy.py` | PolicyEvaluator | Check audit completeness |
| `tools/visual_pipeline.py` | NIMA + composition QA + classify_post_render_failure | Post-render revision support |
| `tools/publish.py` | Poster HTML render + readability boost CSS + assemble_document_pdf | Typst compilation |

## Current Stub Tools (tools/registry.py L2622-2640)

These are structurally registered but return placeholder responses:
```
knowledge_store, story_workshop, scaffold_build, generate_episode,
generate_social_batch, generate_caption, generate_calendar, calendar_qa,
generate_proposal, generate_profile, platform_check, web_search,
competitor_scan, swipe_index, rolling_summary, section_tripwire
```

## What's Working End-to-End

| Lane | Route | Readiness | Policy | Execute | QA | Deliver | Trace |
|------|-------|-----------|--------|---------|-----|---------|-------|
| poster_production | Fast-path + LLM | Hard-block | Yes | Real generation | NIMA + vision + revision | Playwright + Typst | Yes |
| document_production | Fast-path + LLM | Hard-block | Yes | Real generation | Structural (size/exists) | Real Typst compile | Yes |
| All others | Routes correctly | Checks run | Yes | Stubs | None | Blocked by _DELIVERABLE_WORKFLOWS | Partial |

## Environment Notes

- Python 3.11 via `/opt/homebrew/bin/python3`
- Typst installed at system level (`typst compile` works)
- Architecture docs are gitignored — read from `/Users/Executor/vizier/docs/VIZIER_ARCHITECTURE.md` directly
- All API keys (OpenAI, fal.ai) configured in environment
- Tests: `python3 -m pytest` (854 pass, 46 skip)
- Real API tests: `python3 -m pytest --run-api` (requires live API keys + spend)
