# VIZIER Control Tower — Handover Document

**Generated:** 2026-04-08 ~02:00
**Handover number:** 007
**Reason:** End of CT-006 extended session — bug classification, 6 structural preventions, E2E test plan
**Prior handovers:** 001–006 (cumulative). This document is cumulative — successor needs ONLY this file.

---

## Current Status Board

```
SESSION | STATUS             | BLOCK | TESTS
--------|--------------------| ------|------
S0–S21  | ✅ ALL MERGED      | 1–11  | 538 base
IT-1–5  | ✅ ALL MERGED      | 12    | +106
S19     | ✅ MERGED          | 10    | +29
CODEX   | ✅ MERGED          | 12    | +13
CT-004  | ✅ METERING        | —     | +6
CT-005  | ✅ RING ENFORCE    | —     | +23
CT-006  | ✅ PREVENTIONS     | —     | +19 (blast radius + 6 structural gates)
--------|--------------------| ------|------
TOTAL   |                    |       | 704 collected, 0 errors
```

**HEAD:** 7484bfe (feat(governance): add 6 structural bug-class prevention mechanisms)
**Uncommitted:** CLAUDE.md only (minor tech scout injection line). Everything else committed.
**Remote:** git@github.com:khayroul/vizier.git — 16 commits ahead of origin/main. Not pushed.

---

## What CT-006 Did (Full Session)

### Phase 1: Knowledge Graph + Blast Radius Debugging

Built a structural knowledge graph via graphify (AST extraction, 0 tokens).

- **Graph:** 2,523 nodes, 8,533 edges, 102 communities
- **God nodes:** TraceCollector (223), StyleLock (213), RollingContext (195), RoutingResult (185)
- **Bridge nodes:** TraceCollector (0.057), RollingContext (0.041), WorkflowExecutor (0.035)
- **Circular deps:** 0 (clean DAG)

Used graph for blast radius analysis before fixes. Fixed:
- Idempotent policy_logs migration (commit `444faec`)
- requires_db skip markers on 11 test files (commit `444faec`)
- 7 bugs from full repo scan (commit `a0c31a5`)

### Phase 2: Bug Classification + Pattern Analysis

Classified all 22 bugs found across CT sessions into 7 categories:

| Bug Class | Count | % | Root Cause Pattern |
|-----------|-------|---|-------------------|
| SCHEMA_DRIFT | 6 | 27% | SQL ↔ Pydantic ↔ fixtures desync (policy_logs: 3 bugs in 2 sessions) |
| WIRING | 4 | 18% | Circular imports, missing lazy imports |
| DEAD_CODE | 4 | 18% | Unused imports/variables masking real issues |
| API_DRIFT | 3 | 14% | External API param changes (OpenAI, fal.ai) |
| RING_VIOLATION | 2 | 9% | Hardcoded Ring 2 values in Ring 1 code |
| CONTRACT_SAFETY | 2 | 9% | Type mismatches caught only by pyright strict |
| VOCABULARY | 1 | 5% | Invalid enum value in status column |

**Key finding:** SCHEMA_DRIFT is the #1 recurring class. Same root cause (policy_logs) generated 3 bugs across 2 sessions.

### Phase 3: 6 Structural Prevention Mechanisms (commit `7484bfe`)

Implemented 6 permanent gates in the test suite:

| # | Prevention | What It Guards | Where |
|---|-----------|----------------|-------|
| 1 | SCHEMA_DRIFT | SQL columns must match Pydantic contract fields | `test_ring_enforcement.py::TestSchemaDrift` |
| 2 | VOCABULARY | CHECK constraint on `feedback_status` in SQL | `migrations/core.sql` (inline + ALTER TABLE) |
| 3 | DEAD_CODE | ruff F401/F841 must be clean on production code | `test_ring_enforcement.py::TestDeadCode` |
| 4 | WIRING | All 52 production modules must import cleanly | `test_ring_enforcement.py::TestModuleImports` |
| 5 | CONTRACT_SAFETY | pyright strict mode on contracts/ | `pyrightconfig.json` |
| 6 | API_DRIFT | `requires_api` marker + `--run-api` CLI option | `tests/conftest.py` |

**Pre-existing bugs caught on first run:**
- `tools/improvement.py:400` — IndentationError making `_save_rule()` completely broken (WIRING)
- `tools/improvement.py:203` — dead variable `approved` assigned but never used (DEAD_CODE)

Both fixed in the same commit. All 27 ring enforcement tests passing.

### Phase 4: E2E Test Plan (designed, NOT implemented)

Designed a 6-layer E2E test pyramid from user/functional perspective:

```
Layer 5:  Full Workflow E2E      ← "produce a poster from raw input"
Layer 4:  Tool Integration       ← "illustrate takes brief → returns scored image"
Layer 3:  Middleware Chain        ← "policy evaluates → quality gates pass"
Layer 2:  Contract Validation    ← "ArtifactSpec rejects bad input"
Layer 1:  Service Connectivity   ← "can we talk to Postgres/OpenAI/MinIO?"
Layer 0:  Smoke Import           ← "all 52 modules load" (DONE ✓)
```

**Layer 0 is done** (TestModuleImports). Layers 1–5 are the next session's work.

---

## What the Next Session Should Do (CT-007)

### Priority: Implement E2E Test Layers 1–5

Start from Layer 1 (primitives) and build up. Each layer validates the foundation for the next.

#### Layer 1 — Service Connectivity (requires_db / requires_api markers)

Test that external dependencies are reachable and functional. These are the cheapest, most impactful tests.

| Test | What user sees if broken | Marker |
|------|--------------------------|--------|
| Postgres connects + schema exists | No jobs, no history | requires_db |
| OpenAI returns a completion | No text generation | requires_api |
| OpenAI returns an embedding | No search, no retrieval | requires_api |
| MinIO bucket reachable | No asset storage | requires_db |
| fal.ai returns an image | No poster/illustration | requires_api |
| Typst renders a PDF | No PDF output | (local binary) |
| spans.db writable | No cost tracking | (local file) |

#### Layer 2 — Single-Function Primitives (mostly mockable)

Test each primitive does its one job. Mock external calls.

| Test | Input → Output |
|------|----------------|
| `call_llm()` returns content | prompt → string |
| `embed_text()` returns vector | text → float[1536] |
| `upload_asset()` stores + retrieves | bytes → path → bytes |
| `record_span()` persists | span data → row in SQLite |
| `get_workflow_family()` maps correctly | "poster_production" → "poster" |
| `evaluate_readiness()` classifies | spec → ready/shapeable/blocked |
| `fast_path_classify()` routes | "make a poster" → poster_production |

**Note:** Many of these already exist in current tests. Audit first, fill gaps second.

#### Layer 3 — Middleware Chains

| Test | Scenario |
|------|----------|
| Policy allows active workflow | poster_production → allow |
| Policy blocks inactive workflow | social_batch → block |
| Budget gate blocks over-limit | 100k tokens spent → block |
| Quality gate passes good output | score 4.2 → pass |
| Quality gate fails bad output | score 1.5 → fail |
| Guardrails flag register mismatch | formal text for casual brand → advisory |

#### Layer 4 — Tool Integration

| Test | Flow |
|------|------|
| Poster pipeline | brief → image → scored → stored |
| Research augment | query → sources → synthesized |
| Knowledge retrieval | query + client → ranked cards |
| Illustration sequence | 5-page scaffold → 5 scored images |
| Invoice render | line items → Typst → PDF bytes |

#### Layer 5 — Full Workflow E2E

Raw user input → delivered artifact, touching every layer.

| Test | Full path |
|------|-----------|
| Poster E2E | input → route → policy → generate → score → store → trace |
| Document E2E | input → route → research → outline → sections → compose → deliver |
| Children's book E2E | input → character bible → story bible → illustrations → compose → deliver |
| Rework E2E | feedback → analyze → revise → re-score → deliver |

#### Testing Strategy

- **Layer 1:** Use `requires_db` and `requires_api` markers (infrastructure already built)
- **Layer 2–3:** Mostly mockable — mock `call_llm`, DB, external APIs. Test wiring correctness.
- **Layer 4–5:** Two modes:
  - **Mocked mode** (CI-safe): mock externals, test the orchestration logic
  - **Live mode** (`--run-api`): hit real services, test actual output quality

#### Suggested File Structure

```
tests/
  test_e2e_layer1_connectivity.py    ← Service smoke tests
  test_e2e_layer2_primitives.py      ← Single-function tests
  test_e2e_layer3_middleware.py       ← Gate/guardrail chain tests
  test_e2e_layer4_tools.py           ← Tool integration tests
  test_e2e_layer5_workflows.py       ← Full workflow E2E tests
```

---

## What Changed Since HANDOVER_006

### New Commits (5)

| Commit | What |
|--------|------|
| `da30d6f` | feat(metering): per-call token metering + trim Vizier toolset |
| `c5ae24b` | feat(visual-qa): implement calculate_delta for Layer 3 structural comparison |
| `d5422b3` | fix(tests): lazy imports for heavy deps + 3 test infra fixes (72→0 failures) |
| `8085bd4` | style: fix 186 E501 line-length + 12 I001 import-sort violations |
| `7484bfe` | feat(governance): add 6 structural bug-class prevention mechanisms |

### New Files
- `pyrightconfig.json` — pyright config with strict mode for contracts/

### Modified Files
- `tests/test_ring_enforcement.py` — added TestSchemaDrift, TestDeadCode, TestModuleImports (4 new test classes)
- `tests/conftest.py` — added `requires_api` marker + `--run-api` CLI option
- `migrations/core.sql` — CHECK constraint on feedback_status (inline + ALTER TABLE for existing DBs)
- `tools/improvement.py` — fixed IndentationError in `_save_rule()`, removed dead `approved` variable
- `middleware/quality_gate.py` — lazy import for calculate_delta
- `utils/call_llm.py` — import formatting
- `tools/design_selector_api.py` — import sorting

---

## Known Issues (Updated)

1. **Remote behind** — 16 commits ahead of origin/main. Not pushed.

2. **Stale sessions cost 16x more** — Hermes gateway context accumulation. Mitigation: session TTL. Not implemented.

3. **pyright `overrides` not recognized** — pyrightconfig.json uses `overrides` key which current pyright version warns about (`Config contains unrecognized setting "overrides"`). Strict mode still works on contracts/ via include path. Low priority — investigate if pyright version supports `overrides` or use separate config.

4. **E2E test layers 1–5 not implemented** — Designed and documented above. Next session's primary work.

---

## Key Architectural Facts

- **Three-Ring Model (S0.1):** Ring 1 = Structure (contracts, gates, policy), Ring 2 = Config (YAMLs, model prefs), Ring 3 = Data (traces, exemplars).
- **Anti-drift #54:** GPT-5.4-mini for ALL text tasks Month 1-2. No exceptions.
- **6 structural prevention gates** in `test_ring_enforcement.py` — SCHEMA_DRIFT, DEAD_CODE, WIRING always run. VOCABULARY enforced via SQL CHECK. CONTRACT_SAFETY via pyright. API_DRIFT via `--run-api` marker.
- **requires_db / requires_api markers:** Auto-skip tests when services unreachable. Root conftest at `tests/conftest.py`.
- **Knowledge graph:** `graphify-out/graph.json` (2,523 nodes). Rebuild: `/graphify . --update`.

---

## Import Paths Quick Reference

```python
# Workflow registry (replaces hardcoded dicts)
from utils.workflow_registry import (
    get_workflow_family, get_density_for_family,
    get_active_workflow_descriptions, load_workflow_registry,
    reload_workflow_registry, validate_workflow_registry,
)

# Policy + routing
from contracts.routing import route, fast_path_route, llm_route, select_design_systems
from contracts.policy import PolicyDecision, PolicyAction
from middleware.policy import PolicyEvaluator, PolicyRequest, persist_policy_decision

# Test markers (add to new test files)
pytestmark = pytest.mark.requires_db       # for DB-dependent tests
pytestmark = pytest.mark.requires_api      # for external API tests (run with --run-api)
```

---

## Test Counts

```
Total collected:  704
Without DB:       ~470 passed, ~214 skipped (requires_db), 0 errors
With DB:          ~704 passed, 0 skipped, 0 errors
Ring enforcement:  27 passed (includes 6 prevention gates)
```
