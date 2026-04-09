# Track 1: Repo Maturity & Reliability — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fresh machine reproduces the running Vizier system with one script. No tribal knowledge.

**Architecture:** Pin all deployment state in git (submodule, plugin, configs). Thread `hermes_session_id` through bridge → orchestrate → jobs table → Langfuse. Extend media bridge to stop dropping non-image attachments. Validate everything with a smoke script.

**Tech Stack:** Python 3.11, psycopg2, Pydantic, pytest, bash

**Spec:** `docs/superpowers/specs/2026-04-09-hardening-design.md` (Track 1)

---

## Chunk 1: Deployment Boundary + Quick Fixes (1.1, 1.3, 1.4)

### Task 1: Pin hermes-agent submodule

**Files:**
- Modify: `hermes-agent/` (submodule pointer)
- Create: `plugins/hermes_loader/__init__.py`
- Create: `plugins/hermes_loader/plugin.yaml`
- Create: `scripts/install_plugin.sh`
- Create: `scripts/check_plugin_drift.sh`

- [ ] **Step 1: Commit hermes-agent submodule change**

The submodule has a local change in `gateway/run.py` (+40 lines for media env var export). Commit it inside the submodule, then update the superproject pointer.

```bash
cd hermes-agent && git add gateway/run.py && git commit -m "feat(gateway): export session media URLs as env vars"
cd .. && git add hermes-agent
```

- [ ] **Step 2: Copy live plugin into repo**

```bash
mkdir -p plugins/hermes_loader
cp ~/.hermes/plugins/vizier_tools/__init__.py plugins/hermes_loader/__init__.py
cp ~/.hermes/plugins/vizier_tools/plugin.yaml plugins/hermes_loader/plugin.yaml
```

- [ ] **Step 3: Write install_plugin.sh**

```bash
#!/usr/bin/env bash
# Idempotent installer: materializes Hermes plugin from repo source of truth.
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$HOME/.hermes/plugins/vizier_tools"

mkdir -p "$PLUGIN_DIR"
cp "$REPO_DIR/plugins/hermes_loader/__init__.py" "$PLUGIN_DIR/__init__.py"
cp "$REPO_DIR/plugins/hermes_loader/plugin.yaml" "$PLUGIN_DIR/plugin.yaml"
echo "Plugin installed to $PLUGIN_DIR"
```

- [ ] **Step 4: Write check_plugin_drift.sh**

```bash
#!/usr/bin/env bash
# Detect drift between repo and deployed plugin.
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$HOME/.hermes/plugins/vizier_tools"
DRIFT=0

for f in __init__.py plugin.yaml; do
  if [ ! -f "$PLUGIN_DIR/$f" ]; then
    echo "MISSING: $PLUGIN_DIR/$f"
    DRIFT=1
  elif ! diff -q "$REPO_DIR/plugins/hermes_loader/$f" "$PLUGIN_DIR/$f" >/dev/null 2>&1; then
    echo "DRIFT: $f differs between repo and deployed"
    diff "$REPO_DIR/plugins/hermes_loader/$f" "$PLUGIN_DIR/$f" || true
    DRIFT=1
  fi
done

if [ "$DRIFT" -eq 0 ]; then
  echo "No drift detected."
else
  echo "Run scripts/install_plugin.sh to sync."
  exit 1
fi
```

- [ ] **Step 5: Commit**

```bash
git add plugins/hermes_loader/ scripts/install_plugin.sh scripts/check_plugin_drift.sh hermes-agent
git commit -m "chore: pin deployment boundary — submodule + plugin in git"
```

### Task 2: Policy persistence fix (1.3)

**Files:**
- Modify: `middleware/policy.py:37-46`
- Test: `tests/test_policy.py` (new or extend existing)

- [ ] **Step 1: Write failing test**

```python
# tests/test_policy_persistence.py
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from contracts.policy import PolicyDecision, PolicyAction

def test_persist_policy_decision_uses_decision_timestamp():
    """PolicyDecision.timestamp should be written as evaluated_at, not DB default."""
    decision = PolicyDecision(
        action=PolicyAction.allow,
        reason="test",
        gate="test_gate",
        job_id="00000000-0000-0000-0000-000000000001",
    )
    # Freeze a known timestamp
    known_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    decision.timestamp = known_time

    with patch("middleware.policy.get_cursor") as mock_gc:
        mock_cur = MagicMock()
        mock_gc.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)

        from middleware.policy import persist_policy_decision
        persist_policy_decision(decision)

        call_args = mock_cur.execute.call_args
        params = call_args[0][1]  # second positional arg = params tuple/dict
        # The evaluated_at value should be our known_time, not omitted
        assert known_time in params or str(known_time) in str(params)
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_policy_persistence.py -v
```

- [ ] **Step 3: Fix persist_policy_decision to pass decision.timestamp**

In `middleware/policy.py`, add `evaluated_at` to the INSERT columns and pass `decision.timestamp` as the value.

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_policy_persistence.py -v
```

- [ ] **Step 5: Run pyright**

```bash
pyright middleware/policy.py
```

- [ ] **Step 6: Commit**

```bash
git add middleware/policy.py tests/test_policy_persistence.py
git commit -m "fix(policy): persist PolicyDecision.timestamp as evaluated_at"
```

### Task 3: Schema / canon reconciliation (1.4)

**Files:**
- Modify: `migrations/core.sql` (header comment, ~line 1-10)
- Modify: `CLAUDE.md` (§6 table reference)

- [ ] **Step 1: Update core.sql header**

Add or update the header comment to state: "16 core tables (original 14 + 2 document_set tables from tech scout injection §25)."

- [ ] **Step 2: Update CLAUDE.md §6**

Add a note under the table relationships section that core.sql now contains 16 tables.

- [ ] **Step 3: Commit**

```bash
git add migrations/core.sql CLAUDE.md
git commit -m "docs: reconcile schema count — 16 core tables (14 original + 2 document_set)"
```

---

## Chunk 2: Job Lifecycle + Session Correlation (1.2, 1.6)

### Task 4: Job lifecycle hardening (1.2)

**Files:**
- Modify: `tools/orchestrate.py:53-170`
- Modify: `plugins/vizier_tools_bridge.py:640-680`
- Test: `tests/test_orchestrate.py` (extend)

- [ ] **Step 1: Write failing test for job row creation**

```python
# In tests/test_orchestrate.py or new file tests/test_job_lifecycle.py
def test_run_governed_creates_job_row(mock_db, mock_route, mock_readiness, mock_policy):
    """run_governed must create a jobs row before any downstream persistence."""
    from tools.orchestrate import run_governed

    result = run_governed(
        raw_input="Test poster",
        client_id="test-client",
        job_id="test-job-001",
        hermes_session_id="hermes-session-abc",
    )

    # Verify job row was created with status and session_id
    insert_call = mock_db.execute.call_args_list[0]
    assert "INSERT INTO jobs" in insert_call[0][0] or "jobs" in str(insert_call)
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_job_lifecycle.py::test_run_governed_creates_job_row -v
```

- [ ] **Step 3: Add hermes_session_id param and job row creation to run_governed**

In `tools/orchestrate.py`:
- Add `hermes_session_id: str | None = None` to signature
- At the top of the function (before routing), INSERT or upsert a `jobs` row with `status='running'`, `hermes_session_id`, `client_id`, `raw_input`
- On completion, UPDATE `jobs` SET `status='completed'`
- On failure, UPDATE `jobs` SET `status='failed'`
- Add `hermes_session_id` to `job_context` dict

- [ ] **Step 4: Update bridge to pass hermes_session_id**

In `plugins/vizier_tools_bridge.py:663-675`, add to `run_kwargs`:
```python
session_state = _SESSION_STATE.get(current_session_id)
if session_state:
    run_kwargs["hermes_session_id"] = session_state.session_id
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_job_lifecycle.py -v
```

- [ ] **Step 6: Run full test suite to catch regressions**

```bash
pytest tests/test_orchestrate.py tests/test_e2e_layer5b_semantics.py -v
```

- [ ] **Step 7: Run pyright**

```bash
pyright tools/orchestrate.py plugins/vizier_tools_bridge.py
```

- [ ] **Step 8: Commit**

```bash
git add tools/orchestrate.py plugins/vizier_tools_bridge.py tests/test_job_lifecycle.py
git commit -m "feat(orchestrate): create job row at entry, thread hermes_session_id"
```

---

## Chunk 3: Test Hygiene (1.5)

### Task 5: Fix pre-existing test failures with proper skip guards

**Files:**
- Modify: `tests/test_e2e_layer1_connectivity.py`
- Modify: `tests/test_user_pov_poster_acceptance.py`
- Modify: `pyproject.toml` (pytest markers)

- [ ] **Step 1: Add integration marker to pyproject.toml**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
markers = [
    "integration: tests requiring external infrastructure (MinIO, API services)",
]
```

- [ ] **Step 2: Add skip guard to MinIO connectivity test**

In `tests/test_e2e_layer1_connectivity.py`, add at the top of the MinIO test class or individual test:

```python
import pytest
import socket

def _minio_reachable() -> bool:
    try:
        sock = socket.create_connection(("localhost", 9000), timeout=2)
        sock.close()
        return True
    except (OSError, ConnectionRefusedError):
        return False

@pytest.mark.integration
@pytest.mark.skipif(not _minio_reachable(), reason="MinIO not reachable on localhost:9000")
class TestMinIOConnectivity:
    ...
```

- [ ] **Step 3: Add skip guard to poster acceptance tests**

In `tests/test_user_pov_poster_acceptance.py`, add similar skip logic for the required external services (check what service they depend on — likely OpenAI API or image generation).

- [ ] **Step 4: Run default pytest — verify 0 failures**

```bash
pytest -v --ignore=tests/test_e2e_layer1_connectivity.py 2>&1 | tail -5
# Then run with skips
pytest -v 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_e2e_layer1_connectivity.py tests/test_user_pov_poster_acceptance.py pyproject.toml
git commit -m "test: add integration markers and skip guards for infra-dependent tests"
```

---

## Chunk 4: Telemetry + Media Bridge (1.7, 1.8)

### Task 6: Telemetry linkage — wire Langfuse + session metadata (1.7)

**Files:**
- Modify: `middleware/observability.py:105-163`
- Modify: `tools/orchestrate.py` or `tools/executor.py` (verify trace push call site)
- Test: `tests/test_observability.py` (new or extend)

- [ ] **Step 1: Verify trace_to_langfuse is called in governed completion**

Search for call sites of `trace_to_langfuse` in orchestrate.py and executor.py. If not called, wire it.

- [ ] **Step 2: Write failing test for session metadata in Langfuse**

```python
def test_trace_to_langfuse_includes_session_id():
    """Langfuse trace metadata must include hermes_session_id."""
    from middleware.observability import trace_to_langfuse
    from contracts.trace import ProductionTrace

    mock_client = MagicMock()
    trace = ProductionTrace(job_id="test-job")
    metadata = {
        "client_id": "test-client",
        "job_id": "test-job",
        "hermes_session_id": "session-xyz",
    }
    trace_to_langfuse(trace, metadata, langfuse_client=mock_client)

    create_call = mock_client.trace.call_args
    assert create_call is not None
    trace_metadata = create_call[1].get("metadata", {})
    assert trace_metadata.get("hermes_session_id") == "session-xyz"
```

- [ ] **Step 3: Run test — verify behavior**

```bash
pytest tests/test_observability.py -v
```

- [ ] **Step 4: Add hermes_session_id to metadata in observability.py if needed**

In the `trace_to_langfuse` function, ensure the metadata dict passed to `langfuse_client.trace()` includes `hermes_session_id` from the metadata parameter.

- [ ] **Step 5: Wire trace push in orchestrate.py if not already wired**

At the end of `run_governed()`, after `persist_trace()`, call `trace_to_langfuse()` with `hermes_session_id` from `job_context`.

- [ ] **Step 6: Run tests, pyright**

```bash
pytest tests/test_observability.py -v
pyright middleware/observability.py tools/orchestrate.py
```

- [ ] **Step 7: Commit**

```bash
git add middleware/observability.py tools/orchestrate.py tests/test_observability.py
git commit -m "feat(telemetry): wire Langfuse trace push with hermes_session_id"
```

### Task 7: Media bridge extension (1.8)

**Files:**
- Modify: `plugins/vizier_tools_bridge.py:81-91,312-340,663-675`
- Modify: `tools/orchestrate.py:53-65`
- Test: `tests/test_vizier_tools_bridge.py` (extend)

- [ ] **Step 1: Write failing test for media_manifest**

```python
def test_extract_env_media_context_includes_non_image_types():
    """Bridge must not filter out audio/document attachments."""
    import os
    env = {
        "HERMES_SESSION_MEDIA_URLS": '["photo.jpg", "voice.mp3", "doc.pdf"]',
        "HERMES_SESSION_MEDIA_TYPES": '["image/jpeg", "audio/mpeg", "application/pdf"]',
        "HERMES_SESSION_PRIMARY_IMAGE_URL": "photo.jpg",
    }
    with patch.dict(os.environ, env):
        from plugins.vizier_tools_bridge import _extract_env_media_context
        ctx = _extract_env_media_context()
        # All 3 media items should be present, not just images
        assert len(ctx.media_manifest) == 3
```

- [ ] **Step 2: Run test — verify it fails**

- [ ] **Step 3: Extend BridgeMediaContext with media_manifest**

Add to the `BridgeMediaContext` dataclass (`vizier_tools_bridge.py:81-91`):
```python
@dataclass
class MediaManifestEntry:
    path: str = ""
    url: str = ""
    mime_type: str = ""
    role: str = "attachment"  # "primary_image" | "reference" | "attachment"

@dataclass
class BridgeMediaContext:
    # ... existing fields ...
    media_manifest: tuple[MediaManifestEntry, ...] = ()
```

- [ ] **Step 4: Update _extract_env_media_context to build manifest without filtering**

Stop filtering to images only at lines 322-330. Build full manifest from env vars.

- [ ] **Step 5: Add media_manifest param to run_governed**

In `tools/orchestrate.py`, add `media_manifest: list[dict[str, str]] | None = None` to signature. Extract `primary_image` from manifest for backward compat.

- [ ] **Step 6: Update bridge to pass manifest to run_governed**

In `vizier_tools_bridge.py:663-675`, convert `BridgeMediaContext.media_manifest` to list of dicts and pass as `media_manifest` kwarg.

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_vizier_tools_bridge.py -v
pyright plugins/vizier_tools_bridge.py tools/orchestrate.py
```

- [ ] **Step 8: Commit**

```bash
git add plugins/vizier_tools_bridge.py tools/orchestrate.py tests/test_vizier_tools_bridge.py
git commit -m "feat(bridge): extend media manifest to include audio/doc attachments"
```

---

## Chunk 5: Smoke Script (1.9)

### Task 8: Smoke script — acceptance gate

**Files:**
- Create: `scripts/smoke.sh`
- Test: Run manually after all other Track 1 items

- [ ] **Step 1: Write smoke.sh**

```bash
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
    ((PASS++))
  else
    echo "  FAIL: $desc"
    ((FAIL++))
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
    n = cur.fetchone()['n']
    assert n > 0, f'exemplars empty ({n})'
    print(f'exemplars OK ({n} rows)')
"

# 6. Migrations idempotent
echo "[6/7] Migration idempotency"
check "core.sql re-runnable" python3 -c "
import sys; sys.path.insert(0, '$REPO_DIR')
from pathlib import Path
from utils.database import run_migration
run_migration(Path('$REPO_DIR/migrations/core.sql'))
print('migration OK')
"

# 7. Default test suite
echo "[7/7] Test suite"
check "pytest default green" python3 -m pytest "$REPO_DIR/tests" -x -q --timeout=60 2>&1

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/smoke.sh scripts/install_plugin.sh scripts/check_plugin_drift.sh
```

- [ ] **Step 3: Run smoke script**

```bash
scripts/smoke.sh
```

- [ ] **Step 4: Fix any failures exposed by smoke**

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke.sh
git commit -m "chore: add smoke script — validates full system operational state"
```

---

## Summary

| Task | Items | Est. |
|------|-------|------|
| 1. Pin deployment boundary | 1.1 | 30 min |
| 2. Policy persistence fix | 1.3 | 15 min |
| 3. Schema reconciliation | 1.4 | 10 min |
| 4. Job lifecycle + session correlation | 1.2 + 1.6 | 45 min |
| 5. Test hygiene | 1.5 | 20 min |
| 6. Telemetry linkage | 1.7 | 30 min |
| 7. Media bridge extension | 1.8 | 45 min |
| 8. Smoke script | 1.9 | 20 min |
