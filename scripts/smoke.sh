#!/usr/bin/env bash
# Smoke test: validates Vizier system is operational.
# Run after: git submodule update --init && scripts/install_plugin.sh && migrations
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0
FAIL=0

check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "  PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Vizier Smoke Test ==="

# 1. Plugin parity
echo "[1/7] Plugin parity"
check "Plugin matches repo" bash "$REPO_DIR/scripts/check_plugin_drift.sh"

# 2. Bridge importable
echo "[2/7] Bridge import"
check "Bridge module loads" python3 -c "
import sys; sys.path.insert(0, '$REPO_DIR')
from plugins.vizier_tools_bridge import register
print('bridge OK')
"

# 3. Database reachable + schema applied
echo "[3/7] Database"
check "DB reachable" python3 -c "
import sys; sys.path.insert(0, '$REPO_DIR')
from utils.database import get_cursor
with get_cursor() as cur:
    cur.execute('SELECT count(*) FROM clients')
    print('db OK')
"

# 4. Schema tables exist
echo "[4/7] Schema tables"
check "Core tables exist" python3 -c "
import sys; sys.path.insert(0, '$REPO_DIR')
from utils.database import get_cursor
EXPECTED = ['clients','jobs','assets','artifact_specs','artifacts','feedback',
            'exemplars','outcome_memory','knowledge_cards','policy_logs']
with get_cursor() as cur:
    for t in EXPECTED:
        cur.execute(f'SELECT 1 FROM {t} LIMIT 0')
print('tables OK')
"

# 5. Exemplars non-empty
echo "[5/7] Exemplars"
check "Exemplars populated" python3 -c "
import sys; sys.path.insert(0, '$REPO_DIR')
from utils.database import get_cursor
with get_cursor() as cur:
    cur.execute('SELECT count(*) AS n FROM exemplars')
    n = cur.fetchone()[0]
    assert n > 0, f'exemplars empty ({n})'
print(f'exemplars OK ({n})')
"

# 6. Migrations idempotent (re-run core.sql safely)
echo "[6/7] Migrations idempotent"
check "core.sql re-run safe" python3 -c "
import sys; sys.path.insert(0, '$REPO_DIR')
from utils.database import get_cursor
from pathlib import Path
sql = (Path('$REPO_DIR') / 'migrations' / 'core.sql').read_text()
with get_cursor() as cur:
    cur.execute(sql)
print('migrations idempotent OK')
"

# 7. Dry-run governed path (route + readiness + policy, no actual execution)
echo "[7/7] Governed path dry-run"
check "Route+readiness+policy pass" python3 -c "
import sys; sys.path.insert(0, '$REPO_DIR')
from contracts.routing import route
from contracts.readiness import evaluate_readiness
from contracts.artifact_spec import ArtifactFamily, ProvisionalArtifactSpec
from middleware.policy import PolicyEvaluator, PolicyRequest

# Route
r = route('Create a Raya poster for DMB halal catering', client_id='dmb', job_id='smoke-test-dry')
assert r.workflow, f'routing returned empty workflow: {r}'

# Readiness
spec = ProvisionalArtifactSpec(
    client_id='dmb',
    artifact_family=ArtifactFamily.poster,
    language='en',
    raw_brief='Create a Raya poster for DMB halal catering',
)
rd = evaluate_readiness(spec)
assert rd.status in ('ready', 'shapeable'), f'readiness blocked: {rd.reason}'

# Policy
ev = PolicyEvaluator()
dec = ev.evaluate(PolicyRequest(capability=r.workflow, job_id='smoke-test-dry', client_id='dmb'))
assert dec.action.value != 'block', f'policy blocked: {dec.reason}'
print('governed dry-run OK')
"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
echo "All smoke checks passed."
