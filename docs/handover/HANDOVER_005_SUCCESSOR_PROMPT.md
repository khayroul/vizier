# Vizier — Blast Radius Debugging Session

## Who You Are

You are picking up the Vizier project after a debugging + structural enforcement session (CT-005). The 3-day build sprint is long done (553 tests passing). Your predecessor evaluated audit findings from Claude and ChatGPT, then implemented 9 structural fixes to enforce the Three-Ring Architecture Model (§0.1). All fixes are committed and verified.

**Your focus: install graphify, build the knowledge graph, then use blast radius analysis to plan and execute any remaining fixes.** You are a debugging surgeon with a structural map. No new features.

---

## First Steps (do these in order)

### 1. Read context files

```bash
cd ~/vizier
```

Read these files in order:
- `CLAUDE.md` — navigation map, shared interfaces, anti-drift rules
- `docs/handover/HANDOVER_005.md` — cumulative handover from previous session

Then read memory files for infrastructure context:
- Check `~/.claude/projects/-Users-Executor-vizier/memory/` for relevant `.md` files

### 2. Install Graphify and build the knowledge graph

```bash
# Already installed (pip install graphifyy), but verify:
graphify --version

# Install the Claude Code skill + hook
graphify install

# Build the knowledge graph (AST extraction, ~30 seconds)
graphify .

# Verify outputs
ls graphify-out/
# Expected: graph.html  graph.json  GRAPH_REPORT.md  cache/
```

### 3. Read the graph report

```bash
cat graphify-out/GRAPH_REPORT.md
```

This gives you:
- **God nodes** — highest-degree entities, touch with extreme care
- **Community structure** — which modules are tightly coupled
- **Bridge nodes** — cross-cutting concerns that affect multiple communities

### 4. Identify debugging targets

Use the blast radius protocol (Steps 1-5 below) to map any remaining issues before fixing them. Known areas to investigate:

**A. The 114 DB-dependent test errors** — These all fail because `DATABASE_URL` is unset. They are not regressions, but understanding their blast radius helps decide whether to:
  - Add a `@pytest.mark.requires_db` skip marker
  - Set up a test Postgres instance
  - Leave them as-is

**B. Stale session token cost** — Hermes gateway accumulates context across turns, making stale sessions 16x more expensive. The graph will show what connects to the gateway and what a session TTL or context reset would touch.

**C. policy_logs migration** — The schema changed (added columns, dropped `outcome`). Existing tables need migration. Check what depends on the old schema before running.

**D. Any INFERRED or AMBIGUOUS edges** in the graph — These are structural uncertainties the codebase has. They represent places where coupling exists but isn't explicit. Good candidates for audit.

---

## Blast Radius Protocol

### Step 1 — Locate the target in the graph

```bash
python3 -c "
import json
from pathlib import Path
from networkx.readwrite import json_graph
import networkx as nx

G = json_graph.node_link_graph(json.loads(Path('graphify-out/graph.json').read_text()), edges='links')

TARGET = 'YOUR_TARGET_HERE'  # Replace with function/class/module name
matches = [(nid, d) for nid, d in G.nodes(data=True) if TARGET.lower() in d.get('label', '').lower()]

for nid, d in matches:
    print(f\"Node: {d.get('label', nid)}\")
    print(f\"  Source: {d.get('source_file', '')} {d.get('source_location', '')}\")
    print(f\"  Community: {d.get('community', '')}\")
    print(f\"  Degree: {G.degree(nid)} connections\")
    print()
    for neighbor in G.neighbors(nid):
        nd = G.nodes[neighbor]
        ed = G.edges[nid, neighbor]
        print(f\"  → {nd.get('label', neighbor)} [{ed.get('relation', '')}] [{ed.get('confidence', '')}]\")
"
```

### Step 2 — Map the blast radius (1-hop, 2-hop, 3-hop)

```bash
python3 -c "
import json
from pathlib import Path
from networkx.readwrite import json_graph
import networkx as nx

G = json_graph.node_link_graph(json.loads(Path('graphify-out/graph.json').read_text()), edges='links')

TARGET = 'YOUR_TARGET_HERE'
matches = [nid for nid, d in G.nodes(data=True) if TARGET.lower() in d.get('label', '').lower()]
if not matches:
    print(f'No node matching {TARGET}')
    exit()
start = matches[0]

for depth, label in [(1, 'DIRECT — must test'), (2, 'INDIRECT — likely affected'), (3, 'CASCADE — check for regression')]:
    visited = {start}
    frontier = {start}
    for _ in range(depth):
        next_f = set()
        for n in frontier:
            for neighbor in G.neighbors(n):
                if neighbor not in visited:
                    next_f.add(neighbor)
        visited.update(next_f)
        frontier = next_f
    ring = visited - {start}
    if depth == 1:
        direct = ring
    elif depth == 2:
        ring = ring - direct
    else:
        ring = ring - direct - visited

    print(f'\n{label} ({len(ring)} nodes):')
    for nid in sorted(ring, key=lambda n: G.degree(n), reverse=True):
        d = G.nodes[nid]
        print(f\"  {d.get('label', nid):40s} [{d.get('source_file', '')}]\")
"
```

### Step 3 — Check for god node involvement

```bash
python3 -c "
import json
from pathlib import Path
from networkx.readwrite import json_graph
import networkx as nx

G = json_graph.node_link_graph(json.loads(Path('graphify-out/graph.json').read_text()), edges='links')
degree = sorted(dict(G.degree()).items(), key=lambda x: x[1], reverse=True)[:10]

print('GOD NODES (touch with extreme care):')
for nid, deg in degree:
    d = G.nodes[nid]
    print(f\"  {d.get('label', nid):40s} {deg} connections  [{d.get('source_file', '')}]\")
"
```

### Step 4 — Identify the fix cluster (same community)

```bash
python3 -c "
import json
from pathlib import Path
from networkx.readwrite import json_graph
import networkx as nx

G = json_graph.node_link_graph(json.loads(Path('graphify-out/graph.json').read_text()), edges='links')

TARGET = 'YOUR_TARGET_HERE'
matches = [nid for nid, d in G.nodes(data=True) if TARGET.lower() in d.get('label', '').lower()]
if not matches:
    print(f'No node matching {TARGET}')
    exit()

target_community = G.nodes[matches[0]].get('community')
siblings = [(nid, G.nodes[nid]) for nid in G.nodes() if G.nodes[nid].get('community') == target_community]

print(f'COMMUNITY {target_community} — fix these together ({len(siblings)} nodes):')
for nid, d in sorted(siblings, key=lambda x: G.degree(x[0]), reverse=True):
    marker = ' ← TARGET' if nid == matches[0] else ''
    print(f\"  {d.get('label', nid):40s} [{d.get('source_file', '')}]{marker}\")
"
```

### Step 5 — Check cross-community bridges

```bash
python3 -c "
import json
from pathlib import Path
from networkx.readwrite import json_graph
import networkx as nx

G = json_graph.node_link_graph(json.loads(Path('graphify-out/graph.json').read_text()), edges='links')

if G.number_of_edges() == 0:
    print('No edges in graph')
    exit()

betweenness = nx.betweenness_centrality(G)
bridges = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:10]

print('BRIDGE NODES (cross-cutting concerns):')
for nid, score in bridges:
    if score > 0:
        d = G.nodes[nid]
        print(f\"  {d.get('label', nid):40s} centrality={score:.3f}  community={d.get('community', '')}  [{d.get('source_file', '')}]\")
"
```

---

## Decision Framework

After running Steps 1-5:

| Question | If YES | If NO |
|----------|--------|-------|
| Fix target is a god node? | Full regression test. Consider more targeted approach. | Continue. |
| Fix target is a bridge node? | Touches two communities. Test both. | Continue. |
| 1-hop blast radius > 8 nodes? | High risk. Consider refactoring first. | Low-medium risk. Fix directly. |
| Same-community nodes have AMBIGUOUS edges? | Audit those — likely next bug source. | Fix is contained. |

After every fix: `graphify . --update` to rebuild incrementally.

---

## Key Files

| File | What |
|------|------|
| `CLAUDE.md` | Navigation map, anti-drift rules, shared interfaces |
| `docs/handover/HANDOVER_005.md` | What CT-005 did, current status, known issues |
| `docs/superpowers/specs/2026-04-08-ring-enforcement-design.md` | Design spec for the 9 ring fixes (reference) |
| `config/workflow_registry.yaml` | Single source of truth for all 16 workflows |
| `utils/workflow_registry.py` | Registry loader — the pattern for all future config |
| `tests/test_ring_enforcement.py` | 23 tests preventing Ring 2 leakage into Ring 1 |
| `graphify-out/GRAPH_REPORT.md` | Structural report (after graphify runs) |
| `graphify-out/graph.json` | Machine-readable graph (for blast radius queries) |

---

## What NOT To Do

- Do NOT build new features — debug and harden only
- Do NOT push to origin without operator approval
- Do NOT run graphify semantic extraction (costs tokens) unless operator asks
- Do NOT modify the ring enforcement tests to make them pass — they are structural guards
- Do NOT add models other than gpt-5.4-mini for text tasks (anti-drift #54)
- Do NOT fix DB-dependent test errors by removing the tests — add skip markers or set up Postgres
