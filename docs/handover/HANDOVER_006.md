# VIZIER Control Tower — Handover Document

**Generated:** 2026-04-08 ~24:00
**Handover number:** 006
**Reason:** End of CT-006 session — graphify knowledge graph, blast radius debugging, full repo scan
**Prior handovers:** 001–005 (cumulative). This document is cumulative — successor needs ONLY this file.

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
CT-006  | ✅ BLAST RADIUS    | —     | +18 (recovered from errors → passing)
--------|--------------------| ------|------
TOTAL   |                    |       | 685 passing, 0 errors
```

**HEAD:** a0c31a5 (fix: 7 bugs found via full repo scan)
**Uncommitted:** CLAUDE.md only (minor addition). Everything else committed.
**Remote:** git@github.com:khayroul/vizier.git — 12 commits ahead of origin/main. Not pushed.

---

## What CT-006 Did

### 1. Installed Graphify and Built Knowledge Graph

Built a structural knowledge graph of the Vizier codebase using AST extraction (no LLM tokens spent).

- **Scope:** 107 Python files (excluded hermes-agent submodule — 1,121 files, not Vizier code)
- **Result:** 2,523 nodes, 8,533 edges, 102 communities
- **Outputs:** `graphify-out/graph.json`, `graphify-out/graph.html`, `graphify-out/GRAPH_REPORT.md`
- **God nodes:** TraceCollector (223), StyleLock (213), RollingContext (195), RoutingResult (185), WorkflowExecutor (152)
- **Bridge nodes:** TraceCollector (0.057), RollingContext (0.041), WorkflowExecutor (0.035), PolicyDecision (0.017)
- **Circular dependencies:** 0 (clean DAG)

### 2. Blast Radius Analysis on 3 Targets

Used the knowledge graph to map blast radius before fixing:

**Target A+C: 114 DB test errors + policy_logs migration** (same root cause)
- `database.py` is a leaf node (Community 46, blast radius = 9 internal nodes)
- The 114 errors were all from `_ensure_schema()` fixtures failing because `policy_logs` schema changed (added columns, dropped `outcome`/`context`) but existing tables couldn't migrate
- `persist_policy_decision` blast radius: 3 direct + 7 indirect nodes, all contained in middleware/policy.py and contracts/policy.py

**Target B: Stale session token cost**
- Gateway metering nodes (Community 27, 34) are structurally isolated — 3 direct connections
- Confirmed architectural property of Hermes gateway, not a Vizier code bug

### 3. Fix 1: Idempotent Migration + Skip Markers (commit 444faec)

**policy_logs migration:**
- Added `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for 5 new columns
- Added `ALTER TABLE ... DROP COLUMN IF EXISTS` for 2 old columns
- Added backfill + NOT NULL enforcement for `gate` and `reason`
- Migration is now truly idempotent on fresh AND existing DBs

**requires_db skip markers:**
- Created `tests/conftest.py` with `requires_db` marker + `pytest_collection_modifyitems` hook
- Checks Postgres reachability once per session, auto-skips marked tests when DB is down
- Added `pytestmark = pytest.mark.requires_db` to 11 test files:
  - `tests/test_data_foundation.py`, `test_research.py`, `test_knowledge_spine.py`
  - `tests/test_s16_bizops.py`, `test_s16_briefing.py`, `test_s16_steward.py`
  - `tests/test_improvement.py`
  - `tests/integration/test_it1_poster.py`, `test_it3_fastpath.py`, `test_it4_knowledge.py`, `test_it5_feedback.py`
- Updated `test_data_foundation.py::test_policy_log_insert` to use new schema columns

**Result:** 553 passed + 114 errors → 685 passed + 0 errors (with DB), 453 passed + 214 skipped (without DB)

### 4. Fix 2: Full Repo Scan — 7 Bugs Fixed (commit a0c31a5)

Ran 5 parallel scans: pyright, ruff, graph structural audit, import consistency, SQL migration consistency.

| # | Severity | File | Bug | Fix |
|---|----------|------|-----|-----|
| 1 | HIGH | `tools/calibration.py:186` | `'awaiting_feedback'` (invalid) inserted into feedback_status | Changed to `'awaiting'` |
| 2 | HIGH | `utils/workflow_registry.py` | Circular import when loaded first in fresh process | Moved `ArtifactFamily` import into `validate_workflow_registry()` |
| 3 | MED | `middleware/quality_gate.py:18` | Module-level import of nonexistent `scripts.visual.calculate_delta` | Moved to lazy import inside `validate_visual_qa()` |
| 4 | MED | `middleware/observability.py:79` | Langfuse `trace` assigned but never used | Renamed to `_trace` with noqa (auto-flushes on creation) |
| 5 | LOW | `tools/registry.py` | Dead `subprocess` import, 2 dead `job_ctx` vars | Removed dead code |
| 6 | LOW | `utils/call_llm.py` | Stale `Path` import | Removed (kept `DB_PATH` — tests monkeypatch it) |
| 7 | LOW | `tools/design_selector_api.py:61` | `log_message` param `fmt` mismatches base class `format` | Renamed to `format` |

---

## What Changed Since CT-005

### New Files
- `tests/conftest.py` — root conftest with `requires_db` marker and auto-skip logic
- `graphify-out/graph.json` — structural knowledge graph (2,523 nodes, 8,533 edges)
- `graphify-out/graph.html` — interactive HTML visualization
- `graphify-out/GRAPH_REPORT.md` — structural audit report (god nodes, communities, bridges)
- `graphify-out/cost.json` — graphify token cost tracker (0 tokens — AST only)
- `docs/handover/HANDOVER_006.md` — this file

### Modified Files
- `migrations/core.sql` — idempotent ALTER TABLE for policy_logs schema migration
- `tests/test_data_foundation.py` — requires_db marker + test_policy_log_insert updated to new schema
- `tests/test_research.py` — requires_db marker
- `tests/test_knowledge_spine.py` — requires_db marker
- `tests/test_s16_bizops.py` — requires_db marker
- `tests/test_s16_briefing.py` — requires_db marker
- `tests/test_s16_steward.py` — requires_db marker
- `tests/test_improvement.py` — requires_db marker
- `tests/integration/test_it1_poster.py` — requires_db marker
- `tests/integration/test_it3_fastpath.py` — requires_db marker + pytest import added
- `tests/integration/test_it4_knowledge.py` — requires_db marker
- `tests/integration/test_it5_feedback.py` — requires_db marker
- `tools/calibration.py` — fixed invalid feedback_status value
- `utils/workflow_registry.py` — fixed circular import (lazy ArtifactFamily import)
- `middleware/quality_gate.py` — fixed missing module import (lazy calculate_delta)
- `middleware/observability.py` — fixed unused trace variable
- `tools/registry.py` — removed dead imports and variables
- `utils/call_llm.py` — removed stale Path import
- `tools/design_selector_api.py` — fixed parameter name mismatch

---

## Knowledge Graph — How to Use

The graph is built and ready at `graphify-out/graph.json`. Use it for blast radius analysis before any fix.

### Quick Commands

```python
# Load the graph
import json
from pathlib import Path
from networkx.readwrite import json_graph
import networkx as nx

G = json_graph.node_link_graph(json.loads(Path('graphify-out/graph.json').read_text()), edges='links')

# Find a node
TARGET = 'YOUR_TARGET'
matches = [(nid, d) for nid, d in G.nodes(data=True) if TARGET.lower() in d.get('label', '').lower()]

# Blast radius (1-hop)
for neighbor in G.neighbors(matches[0][0]):
    nd = G.nodes[neighbor]
    print(f"  {nd.get('label', neighbor)[:60]} [{nd.get('source_file', '')}]")

# God nodes (top 10 most connected)
degree = sorted(dict(G.degree()).items(), key=lambda x: x[1], reverse=True)[:10]

# Bridge nodes (cross-cutting concerns)
betweenness = nx.betweenness_centrality(G)
```

### Rebuild After Changes

```bash
graphify . --update   # incremental rebuild (or use /graphify . --update in Claude Code)
```

### Key Structural Facts from the Graph

- **TraceCollector** (223 edges, centrality=0.057) is the #1 god node AND bridge — touch with extreme care, full regression test
- **WorkflowExecutor** (152 edges, centrality=0.035) is the highest-degree non-contract node — coupling risk
- **database.py** (Community 46) is a leaf — safe to modify without cascade
- **PolicyDecision** (centrality=0.017) is a bridge between contracts and middleware — test both sides
- **0 circular dependencies** — import graph is a clean DAG

---

## Known Issues (Updated)

1. **Stale sessions cost 16x more** — Hermes gateway accumulates context across turns. Not a code bug. Mitigation: session TTL or explicit context reset. Not implemented.

2. **Remote behind** — 12 commits ahead of origin/main. Not pushed.

3. **`scripts.visual.calculate_delta` doesn't exist** — `middleware/quality_gate.py` Layer 3 (visual QA) references a module that was never built. The import is now lazy so it won't crash at module load, but `validate_visual_qa()` will fail at runtime if called. This is a known gap — the visual delta comparison function needs to be implemented or sourced.

4. **184 line-length warnings** — ruff E501 across the codebase. Style issue, not bugs. Key offenders: `contracts/routing.py` (16), `tools/publish.py` (22), `utils/knowledge.py` (18).

5. **12 unsorted import blocks** — ruff I001, auto-fixable with `ruff check --fix`.

---

## Key Architectural Facts

- **Three-Ring Model (S0.1):** Ring 1 = Structure (contracts, gates, policy), Ring 2 = Config (YAMLs, model prefs), Ring 3 = Data (traces, exemplars).
- **Anti-drift #54:** GPT-5.4-mini for ALL text tasks Month 1-2. No exceptions.
- **Workflow registry pattern:** Adding a new workflow = 1 YAML entry in `config/workflow_registry.yaml` + 1 manifest in `manifests/workflows/`. Zero Python edits.
- **Ring enforcement tests:** `hasattr()` checks in `test_ring_enforcement.py` prevent hardcoded Ring 2 constants from returning in Ring 1 code.
- **requires_db marker:** Tests that need Postgres use `pytestmark = pytest.mark.requires_db`. Auto-skips when DB is unreachable. Root conftest at `tests/conftest.py`.
- **Graphify knowledge graph:** AST-extracted structural map at `graphify-out/graph.json`. Use for blast radius analysis before any structural change. Rebuild with `/graphify . --update`.

---

## Import Paths Quick Reference

```python
# Workflow registry (replaces hardcoded dicts)
from utils.workflow_registry import (
    get_workflow_family,
    get_density_for_family,
    get_active_workflow_descriptions,
    load_workflow_registry,
    reload_workflow_registry,
    validate_workflow_registry,
)

# Existing (unchanged)
from contracts.routing import route, fast_path_route, llm_route, select_design_systems
from contracts.policy import PolicyDecision, PolicyAction
from middleware.policy import PolicyEvaluator, PolicyRequest, persist_policy_decision
from contracts.artifact_spec import ArtifactSpec, ProvisionalArtifactSpec, ArtifactFamily

# Test marker (add to any new DB-dependent test file)
pytestmark = pytest.mark.requires_db
```

---

## Test Counts by Category

```
With DB:       685 passed,   0 errors,   0 skipped
Without DB:    453 passed,   0 errors, 214 skipped
```

The 214 skipped tests break down as:
- test_data_foundation.py: ~30 tests
- test_research.py: ~25 tests
- test_knowledge_spine.py: ~20 tests
- test_s16_bizops.py: ~15 tests
- test_s16_briefing.py: ~5 tests
- test_s16_steward.py: ~15 tests
- test_improvement.py: ~30 tests
- integration/test_it1_poster.py: ~15 tests
- integration/test_it3_fastpath.py: ~5 tests
- integration/test_it4_knowledge.py: ~40 tests
- integration/test_it5_feedback.py: ~14 tests
