# VIZIER Control Tower — Handover Document

**Generated:** 2026-04-08 ~23:00
**Handover number:** 005
**Reason:** End of CT-005 session — ring enforcement fixes, audit resolution, graphify planned
**Prior handovers:** 001–004 (cumulative). This document is cumulative — successor needs ONLY this file.

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
--------|--------------------| ------|------
TOTAL   |                    |       | 553 passing, 114 DB errors (pre-existing, need Postgres)
```

**HEAD:** 8bf1fd3 (feat(governance): enforce Three-Ring architecture — structural fixes)
**Uncommitted:** CLAUDE.md only (minor addition). Everything else committed.
**Remote:** git@github.com:khayroul/vizier.git — multiple commits ahead of origin/main. Not pushed.

---

## What CT-005 Did

### 1. Committed CT-004 Metering Fixes

CT-004 left uncommitted metering/e2e fixes. CT-005 verified tests and committed:
- `ecb47d6` fix(e2e): OpenAI param, fal.ai endpoints, registry wiring, trace totals

### 2. Token Efficiency Audit

Established clean baseline: ~$0.001/turn for fresh sessions. Stale sessions cost 16x more due to gateway context accumulation. Not a code bug — architectural characteristic of the Hermes gateway.

### 3. End-to-End Production Test

Full poster production chain verified: intake → production → QA → delivery. All 4 stages work. Tripwire, NIMA, traces all functional.

### 4. Evaluated Two External Audits

**Claude audit:** 6 GAPs + 3 OBS. Findings mapped to real code issues.
**ChatGPT audit:** 17 findings. Most aligned with real gaps.

Combined findings distilled into 9 structural fixes, all grounded in the Three-Ring Architecture Model (§0.1).

### 5. Designed + Implemented 9 Ring Enforcement Fixes

Design spec: `docs/superpowers/specs/2026-04-08-ring-enforcement-design.md`
Spec was self-reviewed, then reviewed by code-reviewer agent. All CRITICAL and HIGH issues resolved before and after implementation.

| Fix | What | Files |
|-----|------|-------|
| **1+2** | Workflow registry YAML + cached loader with startup validation | `config/workflow_registry.yaml`, `utils/workflow_registry.py` (new) |
| **1** | Delete hardcoded Ring 2 from routing.py | `contracts/routing.py` — removed `_ACTIVE_WORKFLOWS`, `_ARTIFACT_DENSITY`, `_workflow_to_family()` |
| **1** | Delete hardcoded Ring 2 from orchestrate.py | `tools/orchestrate.py` — removed `_WORKFLOW_FAMILY_MAP`, `_workflow_to_family()` |
| **3** | Ring enforcement tests (23 tests) | `tests/test_ring_enforcement.py` (new) |
| **4** | policy_logs schema alignment | `migrations/core.sql` — added decision_id, client_id, capability, gate, constraints |
| **5** | Policy persistence bridge | `middleware/policy.py` — `persist_policy_decision()` wired into `evaluate()` |
| **6** | PolicyDecision.capability field | `contracts/policy.py` + all 10 constructor sites in `middleware/policy.py` |
| **7** | ArtifactSpec frozen | `contracts/artifact_spec.py` — `ConfigDict(frozen=True)` |
| **8** | ProvisionalArtifactSpec.family_resolved | `contracts/artifact_spec.py` — prevents unclassified family from distorting density scoring |
| **9** | httpx module-level import | `tools/image.py` |

### 6. Graphify Planned (Not Installed)

User wants to install graphify (knowledge graph tool for blast radius analysis) as step 1 of the next debugging session. Package is `pip install graphifyy --break-system-packages`. See the DEBUG SESSION BRIEF in the successor prompt for the full workflow.

---

## What Changed Since CT-004

### New Files
- `config/workflow_registry.yaml` — single source of truth for all 16 workflows + artifact family density
- `utils/workflow_registry.py` — `@lru_cache` loader, `get_workflow_family()`, `get_density_for_family()`, `get_active_workflow_descriptions()`, `validate_workflow_registry()`
- `tests/test_ring_enforcement.py` — 23 structural tests preventing Ring 2 constants from returning in Ring 1 code
- `docs/superpowers/specs/2026-04-08-ring-enforcement-design.md` — full design spec for the 9 fixes

### Modified Files
- `contracts/routing.py` — hardcoded dicts/functions deleted, now uses `utils.workflow_registry`
- `tools/orchestrate.py` — hardcoded map/function deleted, now uses `utils.workflow_registry`
- `contracts/policy.py` — added `capability: str | None` field to `PolicyDecision`
- `middleware/policy.py` — added `persist_policy_decision()`, added `capability=` to all 10 constructor sites, wired persistence into `evaluate()`
- `contracts/artifact_spec.py` — `ArtifactSpec` now frozen, `ProvisionalArtifactSpec` has `family_resolved` flag
- `migrations/core.sql` — `policy_logs` table schema aligned to contract
- `tools/image.py` — httpx moved to module-level import
- `tests/test_routing.py` — deleted `TestWorkflowToFamily` class, removed `_workflow_to_family` import

---

## Known Issues (Unchanged)

1. **114 test errors** — all `psycopg2.errors` from tests that need a live Postgres connection. Not regressions. Tests: `test_research.py`, `test_s16_bizops.py`, `test_s16_briefing.py`, `test_s16_steward.py`.

2. **Stale sessions cost 16x more** — Hermes gateway accumulates context across turns. Not a code bug. Mitigation: session TTL or explicit context reset. Not implemented.

3. **policy_logs migration requires re-run** — The schema change (added columns, dropped `outcome`) means `policy_logs` table needs to be dropped and recreated on the live DB. Migration is idempotent for fresh DBs but existing `policy_logs` tables won't auto-migrate.

4. **Remote behind** — Multiple commits ahead of origin/main. Not pushed.

---

## Key Architectural Facts

- **Three-Ring Model (§0.1):** Ring 1 = Structure (contracts, gates, policy), Ring 2 = Config (YAMLs, model prefs), Ring 3 = Data (traces, exemplars). "Structure once, configure often, feed constantly."
- **Anti-drift #54:** GPT-5.4-mini for ALL text tasks Month 1-2. No exceptions.
- **Workflow registry pattern:** Adding a new workflow = 1 YAML entry in `config/workflow_registry.yaml` + 1 manifest in `manifests/workflows/`. Zero Python edits.
- **Ring enforcement tests:** `hasattr()` checks in `test_ring_enforcement.py` prevent hardcoded Ring 2 constants from silently returning in structural code.
- **Policy persistence:** Every `PolicyEvaluator.evaluate()` call now persists to `policy_logs`. Non-fatal on DB failure (catches `psycopg2.Error`, `OSError`, `ImportError`, `RuntimeError`).

---

## Import Paths Quick Reference

```python
# Workflow registry (new — replaces hardcoded dicts)
from utils.workflow_registry import (
    get_workflow_family,           # "poster_production" → "poster"
    get_density_for_family,        # "poster" → "moderate"
    get_active_workflow_descriptions,  # [(name, desc), ...] filtered by active phases
    load_workflow_registry,        # full registry dict
    reload_workflow_registry,      # clear lru_cache
    validate_workflow_registry,    # 6-check validation
)

# Existing (unchanged)
from contracts.routing import route, fast_path_route, llm_route, select_design_systems
from contracts.policy import PolicyDecision, PolicyAction
from middleware.policy import PolicyEvaluator, PolicyRequest, persist_policy_decision
from contracts.artifact_spec import ArtifactSpec, ProvisionalArtifactSpec, ArtifactFamily
```
