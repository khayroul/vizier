# Vizier — Successor Prompt (CT-006 → CT-007)

## Who You Are

You are picking up the Vizier project after a blast radius debugging session (CT-006). The codebase has a structural knowledge graph (2,523 nodes, 8,533 edges) and all tests pass (685, 0 errors). Your predecessor fixed the policy_logs migration, added DB test skip markers, and resolved 7 bugs found via a full repo scan.

**Your focus depends on operator direction.** The codebase is structurally sound. Potential next steps below.

---

## First Steps (do these in order)

### 1. Read context files

```bash
cd ~/vizier
```

Read these files in order:
- `CLAUDE.md` — navigation map, shared interfaces, anti-drift rules
- `docs/handover/HANDOVER_006.md` — cumulative handover from previous session

Then read memory files for infrastructure context:
- Check `~/.claude/projects/-Users-Executor-vizier/memory/` for relevant `.md` files

### 2. Verify the knowledge graph is intact

```bash
ls graphify-out/
# Expected: graph.html  graph.json  GRAPH_REPORT.md  cost.json  cache/
```

The graph is ready to query. No rebuild needed unless code changed since CT-006.

### 3. Verify tests pass

```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
DATABASE_URL="postgres://localhost:5432/vizier" python3.11 -m pytest --tb=short -q
# Expected: 685 passed, 0 errors
```

---

## Current State Summary

| Metric | Value |
|--------|-------|
| Tests passing | 685 (with DB), 453 + 214 skipped (without DB) |
| Pyright errors | 0 (production code) |
| Ruff functional issues | 0 (all fixed) |
| Circular dependencies | 0 |
| Commits ahead of origin | 12 |
| Knowledge graph | 2,523 nodes, 8,533 edges, 102 communities |

---

## Potential Next Steps (operator chooses)

### A. Push to remote
12 commits ahead of origin/main. All tests pass. Safe to push if operator approves.

### B. Address remaining lint (low priority)
- 184 line-length warnings (E501) — style, not bugs
- 12 unsorted imports (I001) — auto-fixable: `ruff check --fix contracts/ middleware/ tools/ utils/`

### C. Build `scripts.visual.calculate_delta`
`middleware/quality_gate.py` Layer 3 (visual QA) references a function that doesn't exist. Currently lazy-imported so it won't crash at module load, but `validate_visual_qa()` will fail at runtime. Options:
- Implement using SSIM + pixel diff (PIL/scikit-image)
- Stub it with a pass-through until visual QA is needed

### D. Semantic graph extraction
The current graph is AST-only (free, fast). Running semantic extraction (`/graphify . --mode deep`) would add cross-module edges that AST can't detect (shared data patterns, architectural relationships). Costs Claude tokens but makes blast radius analysis more accurate.

### E. Run a production workflow test
The poster_production workflow passed E2E in CT-005. Other workflows (children's book, ebook, document) haven't been tested end-to-end. The graph shows `WorkflowExecutor` (degree=152) is the highest coupling point — testing more workflows validates its wiring.

### F. Session TTL for Hermes gateway
Stale sessions cost 16x more ($0.017 vs $0.001 per turn). Not a code bug but an architectural optimization. The gateway metering nodes are isolated in the graph (Community 27, 34) — safe to modify without cascade.

---

## Blast Radius Protocol (for any future fix)

Before touching any code, run the blast radius analysis:

### Step 1 — Locate the target
```python
python3.11 -c "
import json
from pathlib import Path
from networkx.readwrite import json_graph
import networkx as nx

G = json_graph.node_link_graph(json.loads(Path('graphify-out/graph.json').read_text()), edges='links')
TARGET = 'YOUR_TARGET_HERE'
matches = [(nid, d) for nid, d in G.nodes(data=True) if TARGET.lower() in d.get('label', '').lower()]
for nid, d in matches:
    print(f\"Node: {d.get('label', nid)}\")
    print(f\"  Source: {d.get('source_file', '')} {d.get('source_location', '')}\")
    print(f\"  Community: {d.get('community', '')}\")
    print(f\"  Degree: {G.degree(nid)} connections\")
"
```

### Step 2 — Map blast radius
```python
# 1-hop = must test, 2-hop = likely affected, 3-hop = check for regression
# See HANDOVER_005_SUCCESSOR_PROMPT.md for full blast radius scripts
```

### Step 3 — Decision framework

| Question | If YES | If NO |
|----------|--------|-------|
| Target is a god node (>150 edges)? | Full regression test. | Continue. |
| Target is a bridge node (centrality >0.01)? | Test both communities. | Continue. |
| 1-hop blast radius > 8 nodes? | High risk. Consider refactoring first. | Fix directly. |

### Step 4 — After every fix
```bash
graphify . --update   # rebuild graph incrementally
```

---

## God Nodes (touch with extreme care)

| Node | Edges | File | Role |
|------|-------|------|------|
| TraceCollector | 223 | contracts/trace.py | Tracing contract — used everywhere |
| StyleLock | 213 | contracts/publishing.py | Publishing style lock |
| RollingContext | 195 | contracts/context.py | Cross-step context tracking |
| RoutingResult | 185 | contracts/routing.py | Routing output contract |
| WorkflowExecutor | 152 | tools/executor.py | Runs all workflow packs |

## Bridge Nodes (cross-cutting concerns)

| Node | Centrality | Communities bridged |
|------|-----------|-------------------|
| TraceCollector | 0.057 | Publishing ↔ Testing ↔ Execution |
| RollingContext | 0.041 | Publishing ↔ Context tracking |
| WorkflowExecutor | 0.035 | Config loading ↔ Execution |
| PolicyDecision | 0.017 | Contracts ↔ Middleware |

---

## Key Files

| File | What |
|------|------|
| `CLAUDE.md` | Navigation map, anti-drift rules, shared interfaces |
| `docs/handover/HANDOVER_006.md` | What CT-006 did, current status, known issues |
| `graphify-out/graph.json` | Structural knowledge graph (for blast radius queries) |
| `graphify-out/GRAPH_REPORT.md` | Structural report (god nodes, communities, bridges) |
| `graphify-out/graph.html` | Interactive visualization (open in browser) |
| `tests/conftest.py` | Root conftest — requires_db marker + auto-skip |
| `config/workflow_registry.yaml` | Single source of truth for all 16 workflows |
| `tests/test_ring_enforcement.py` | 23 tests preventing Ring 2 leakage into Ring 1 |

---

## What NOT To Do

- Do NOT push to origin without operator approval
- Do NOT modify ring enforcement tests to make them pass — they are structural guards
- Do NOT add models other than gpt-5.4-mini for text tasks (anti-drift #54)
- Do NOT fix DB-dependent test errors by removing tests — add skip markers
- Do NOT run graphify semantic extraction without operator approval (costs tokens)
- Do NOT touch god nodes without running full blast radius analysis first
- Do NOT delete the knowledge graph files in graphify-out/
