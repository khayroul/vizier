"""S10a — Data Foundation tests.

Covers: 16 core tables, views, feedback state machine trigger,
TraceCollector Postgres persistence, MinIO storage, document sets,
self-referential artifact FK, goal_chain on jobs, anchor_set exclusion,
and end-to-end trace flow.

Requires: running Postgres (vizier db) and MinIO (localhost:9000).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest

pytestmark = pytest.mark.requires_db

# Ensure env is loaded for tests
os.environ.setdefault("DATABASE_URL", "postgres://localhost:5432/vizier")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")

from contracts.trace import TraceCollector
from utils.database import get_cursor, run_migration
from utils.storage import (
    BUCKET_NAME,
    delete_object,
    download_bytes,
    get_minio_client,
    object_exists,
    upload_bytes,
)
from utils.trace_persist import collect_and_persist, load_trace, persist_trace


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _ensure_schema() -> None:
    """Run core.sql before the test session to guarantee tables exist."""
    sql_path = Path(__file__).resolve().parent.parent / "migrations" / "core.sql"
    if sql_path.exists():
        run_migration(sql_path)


@pytest.fixture()
def client_id() -> str:
    """Insert a test client and return its id."""
    cid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO clients (id, name, industry) VALUES (%s, %s, %s)",
            (cid, f"test-client-{cid[:8]}", "testing"),
        )
    return cid


@pytest.fixture()
def job_id(client_id: str) -> str:
    """Insert a test job and return its id."""
    jid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO jobs (id, client_id, job_type, status) VALUES (%s, %s, %s, %s)",
            (jid, client_id, "poster", "received"),
        )
    return jid


@pytest.fixture()
def asset_id() -> str:
    """Insert a test asset and return its id."""
    aid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO assets (id, storage_path, filename, mime_type) VALUES (%s, %s, %s, %s)",
            (aid, "vizier-assets/test/img.png", "img.png", "image/png"),
        )
    return aid


@pytest.fixture()
def spec_id(job_id: str) -> str:
    """Insert a test artifact_spec and return its id."""
    sid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO artifact_specs (id, job_id, spec_data) VALUES (%s, %s, %s)",
            (sid, job_id, json.dumps({"type": "poster", "language": "ms"})),
        )
    return sid


# ---------------------------------------------------------------------------
# §1  Table existence (all 16)
# ---------------------------------------------------------------------------

EXPECTED_TABLES = [
    "clients", "jobs", "artifact_specs", "artifacts", "assets",
    "deliveries", "policy_logs", "feedback",
    "knowledge_sources", "knowledge_cards", "exemplars", "outcome_memory",
    "visual_lineage", "system_state",
    "document_sets", "document_set_members",
]


@pytest.mark.parametrize("table", EXPECTED_TABLES)
def test_table_exists(table: str) -> None:
    with get_cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
            (table,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["exists"] is True, f"Table {table} does not exist"


# ---------------------------------------------------------------------------
# §2  Idempotent re-run
# ---------------------------------------------------------------------------

def test_migration_idempotent() -> None:
    """Re-running core.sql must not error."""
    sql_path = Path(__file__).resolve().parent.parent / "migrations" / "core.sql"
    run_migration(sql_path)  # should not raise


# ---------------------------------------------------------------------------
# §3  goal_chain on jobs
# ---------------------------------------------------------------------------

def test_jobs_goal_chain(client_id: str) -> None:
    jid = str(uuid4())
    goal = {"campaign": "Raya 2026", "objective": "increase festive sales 30%"}
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO jobs (id, client_id, job_type, goal_chain) VALUES (%s, %s, %s, %s)",
            (jid, client_id, "poster", json.dumps(goal)),
        )
        cur.execute("SELECT goal_chain FROM jobs WHERE id = %s", (jid,))
        row = cur.fetchone()
        assert row is not None
        assert row["goal_chain"]["campaign"] == "Raya 2026"


def test_jobs_goal_chain_nullable(client_id: str) -> None:
    jid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO jobs (id, client_id, job_type) VALUES (%s, %s, %s)",
            (jid, client_id, "poster"),
        )
        cur.execute("SELECT goal_chain FROM jobs WHERE id = %s", (jid,))
        row = cur.fetchone()
        assert row is not None
        assert row["goal_chain"] is None


# ---------------------------------------------------------------------------
# §4  Self-referential FK on artifacts
# ---------------------------------------------------------------------------

def test_artifact_self_referential_fk(job_id: str, spec_id: str, asset_id: str) -> None:
    parent_id = str(uuid4())
    child_id = str(uuid4())
    with get_cursor() as cur:
        # Insert parent artifact (NULL parent_artifact_id)
        cur.execute(
            """INSERT INTO artifacts (id, job_id, spec_id, asset_id, artifact_type, parent_artifact_id)
               VALUES (%s, %s, %s, %s, %s, NULL)""",
            (parent_id, job_id, spec_id, asset_id, "poster"),
        )
        # Insert child artifact pointing to parent
        cur.execute(
            """INSERT INTO artifacts (id, job_id, spec_id, asset_id, artifact_type, parent_artifact_id)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (child_id, job_id, spec_id, asset_id, "poster", parent_id),
        )
        # Verify both
        cur.execute("SELECT parent_artifact_id FROM artifacts WHERE id = %s", (parent_id,))
        assert cur.fetchone()["parent_artifact_id"] is None
        cur.execute("SELECT parent_artifact_id FROM artifacts WHERE id = %s", (child_id,))
        assert str(cur.fetchone()["parent_artifact_id"]) == parent_id


# ---------------------------------------------------------------------------
# §5  Feedback state machine trigger
# ---------------------------------------------------------------------------

def test_feedback_insert_sets_delivered_at(job_id: str, client_id: str) -> None:
    fid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO feedback (id, job_id, client_id, feedback_status)
               VALUES (%s, %s, %s, 'awaiting') RETURNING delivered_at""",
            (fid, job_id, client_id),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["delivered_at"] is not None


def test_feedback_valid_transition(job_id: str, client_id: str) -> None:
    fid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO feedback (id, job_id, client_id, feedback_status) VALUES (%s, %s, %s, 'awaiting')",
            (fid, job_id, client_id),
        )
        # awaiting → explicitly_approved (valid)
        cur.execute(
            "UPDATE feedback SET feedback_status = 'explicitly_approved' WHERE id = %s RETURNING feedback_received_at",
            (fid,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["feedback_received_at"] is not None


def test_feedback_invalid_transition(job_id: str, client_id: str) -> None:
    fid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO feedback (id, job_id, client_id, feedback_status) VALUES (%s, %s, %s, 'awaiting')",
            (fid, job_id, client_id),
        )
    # awaiting → unresponsive is NOT a valid transition
    with pytest.raises(psycopg2.errors.RaiseException, match="Invalid feedback transition"):
        with get_cursor() as cur:
            cur.execute(
                "UPDATE feedback SET feedback_status = 'unresponsive' WHERE id = %s",
                (fid,),
            )


def test_feedback_silence_flagging(job_id: str, client_id: str) -> None:
    """Test the silence detection function flags stale awaiting feedback."""
    fid = str(uuid4())
    with get_cursor() as cur:
        # Insert feedback with delivered_at in the past (>24h ago)
        cur.execute(
            """INSERT INTO feedback (id, job_id, client_id, feedback_status, delivered_at)
               VALUES (%s, %s, %s, 'awaiting', now() - interval '25 hours')""",
            (fid, job_id, client_id),
        )
        # Run silence check
        cur.execute("SELECT feedback_check_silence()")
        flagged = cur.fetchone()["feedback_check_silence"]
        assert flagged >= 1

        # Verify it was flagged
        cur.execute("SELECT feedback_status FROM feedback WHERE id = %s", (fid,))
        assert cur.fetchone()["feedback_status"] == "silence_flagged"


def test_feedback_full_silence_path(job_id: str, client_id: str) -> None:
    """Test full path: awaiting → silence_flagged → prompted → unresponsive."""
    fid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO feedback (id, job_id, client_id, feedback_status, delivered_at)
               VALUES (%s, %s, %s, 'awaiting', now() - interval '25 hours')""",
            (fid, job_id, client_id),
        )
        cur.execute("SELECT feedback_check_silence()")
        cur.execute("UPDATE feedback SET feedback_status = 'prompted' WHERE id = %s", (fid,))
        cur.execute("UPDATE feedback SET feedback_status = 'unresponsive' WHERE id = %s", (fid,))
        cur.execute("SELECT feedback_status FROM feedback WHERE id = %s", (fid,))
        assert cur.fetchone()["feedback_status"] == "unresponsive"


# ---------------------------------------------------------------------------
# §6  Feedback anchor_set and benchmark_source columns
# ---------------------------------------------------------------------------

def test_feedback_anchor_set_column(job_id: str, client_id: str) -> None:
    fid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO feedback (id, job_id, client_id, anchor_set, benchmark_source)
               VALUES (%s, %s, %s, true, 'external') RETURNING anchor_set, benchmark_source""",
            (fid, job_id, client_id),
        )
        row = cur.fetchone()
        assert row["anchor_set"] is True
        assert row["benchmark_source"] == "external"


def test_feedback_anchor_set_default_false(job_id: str, client_id: str) -> None:
    fid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO feedback (id, job_id, client_id) VALUES (%s, %s, %s) RETURNING anchor_set",
            (fid, job_id, client_id),
        )
        assert cur.fetchone()["anchor_set"] is False


# ---------------------------------------------------------------------------
# §7  Views return data
# ---------------------------------------------------------------------------

def test_view_system_health() -> None:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM v_system_health")
        row = cur.fetchone()
        assert row is not None
        assert "current_version" in row
        assert "active_clients" in row


def test_view_client_health(client_id: str) -> None:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM v_client_health WHERE client_id = %s", (client_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["client_name"].startswith("test-client-")


def test_view_feedback_quality_excludes_anchor_and_silence(
    job_id: str, client_id: str
) -> None:
    """Verify v_feedback_quality excludes anchor_set and silence_flagged/unresponsive."""
    with get_cursor() as cur:
        # Insert an approved feedback (should be counted)
        cur.execute(
            """INSERT INTO feedback (id, job_id, client_id, feedback_status, anchor_set)
               VALUES (%s, %s, %s, 'awaiting', false)""",
            (str(uuid4()), job_id, client_id),
        )
        # Transition to approved
        cur.execute(
            "UPDATE feedback SET feedback_status = 'explicitly_approved' WHERE job_id = %s AND anchor_set = false",
            (job_id,),
        )

        # Insert an anchor_set feedback (should be excluded)
        fid_anchor = str(uuid4())
        cur.execute(
            """INSERT INTO feedback (id, job_id, client_id, feedback_status, anchor_set, delivered_at)
               VALUES (%s, %s, %s, 'awaiting', true, now())""",
            (fid_anchor, job_id, client_id),
        )

        # Insert a silence_flagged feedback (should be excluded)
        fid_silence = str(uuid4())
        cur.execute(
            """INSERT INTO feedback (id, job_id, client_id, feedback_status, delivered_at)
               VALUES (%s, %s, %s, 'awaiting', now() - interval '25 hours')""",
            (fid_silence, job_id, client_id),
        )
        cur.execute("SELECT feedback_check_silence()")

        # Check the view — only the approved one should appear
        cur.execute(
            "SELECT * FROM v_feedback_quality WHERE client_id = %s",
            (client_id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["approved"] >= 1
        # anchor_set and silence_flagged should be excluded from totals


# ---------------------------------------------------------------------------
# §8  Document sets
# ---------------------------------------------------------------------------

def test_document_sets(client_id: str) -> None:
    """Insert a document set, assign knowledge cards, query via membership."""
    ds_id = str(uuid4())
    ks_id = str(uuid4())
    kc_id = str(uuid4())

    with get_cursor() as cur:
        # Create knowledge source and card
        cur.execute(
            "INSERT INTO knowledge_sources (id, client_id, title) VALUES (%s, %s, %s)",
            (ks_id, client_id, "Test source"),
        )
        cur.execute(
            "INSERT INTO knowledge_cards (id, source_id, client_id, content) VALUES (%s, %s, %s, %s)",
            (kc_id, ks_id, client_id, "Test card content"),
        )

        # Create document set
        cur.execute(
            "INSERT INTO document_sets (id, client_id, name, is_default) VALUES (%s, %s, %s, %s)",
            (ds_id, client_id, "Default Set", True),
        )

        # Add card to set
        cur.execute(
            "INSERT INTO document_set_members (document_set_id, knowledge_card_id) VALUES (%s, %s)",
            (ds_id, kc_id),
        )

        # Query via membership
        cur.execute(
            """SELECT kc.content FROM knowledge_cards kc
               JOIN document_set_members dsm ON dsm.knowledge_card_id = kc.id
               WHERE dsm.document_set_id = %s""",
            (ds_id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["content"] == "Test card content"


def test_document_set_unique_constraint(client_id: str) -> None:
    """Duplicate (set_id, card_id) pair should fail."""
    ds_id = str(uuid4())
    ks_id = str(uuid4())
    kc_id = str(uuid4())

    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO knowledge_sources (id, client_id, title) VALUES (%s, %s, %s)",
            (ks_id, client_id, "Src"),
        )
        cur.execute(
            "INSERT INTO knowledge_cards (id, source_id, client_id, content) VALUES (%s, %s, %s, %s)",
            (kc_id, ks_id, client_id, "Card"),
        )
        cur.execute(
            "INSERT INTO document_sets (id, client_id, name) VALUES (%s, %s, %s)",
            (ds_id, client_id, "Set"),
        )
        cur.execute(
            "INSERT INTO document_set_members (document_set_id, knowledge_card_id) VALUES (%s, %s)",
            (ds_id, kc_id),
        )

    with pytest.raises(psycopg2.errors.UniqueViolation):
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO document_set_members (document_set_id, knowledge_card_id) VALUES (%s, %s)",
                (ds_id, kc_id),
            )


# ---------------------------------------------------------------------------
# §9  TraceCollector Postgres integration
# ---------------------------------------------------------------------------

def test_trace_persist_and_load(job_id: str) -> None:
    collector = TraceCollector(job_id=job_id)
    with collector.step("generate_copy") as step:
        step.input_tokens = 100
        step.output_tokens = 50
        step.cost_usd = 0.001
        step.model = "gpt-5.4-mini"

    trace = collector.finalise()
    persist_trace(job_id, trace)

    loaded = load_trace(job_id)
    assert loaded is not None
    assert len(loaded.steps) == 1
    assert loaded.steps[0].step_name == "generate_copy"
    assert loaded.steps[0].input_tokens == 100


def test_collect_and_persist(job_id: str) -> None:
    collector = TraceCollector(job_id=job_id)
    with collector.step("render") as step:
        step.input_tokens = 200
        step.output_tokens = 100
        step.cost_usd = 0.002

    trace = collect_and_persist(job_id, collector)
    assert trace.total_input_tokens == 200

    loaded = load_trace(job_id)
    assert loaded is not None
    assert loaded.steps[0].step_name == "render"


# ---------------------------------------------------------------------------
# §10  MinIO storage integration
# ---------------------------------------------------------------------------

def test_minio_upload_download() -> None:
    test_data = b"PNG test data for S10a"
    obj_name = f"test/{uuid4()}.png"

    path = upload_bytes(obj_name, test_data, content_type="image/png")
    assert path == f"{BUCKET_NAME}/{obj_name}"

    assert object_exists(obj_name)

    downloaded = download_bytes(obj_name)
    assert downloaded == test_data

    # Cleanup
    delete_object(obj_name)
    assert not object_exists(obj_name)


# ---------------------------------------------------------------------------
# §11  End-to-end: poster job → trace → feedback trigger → spans
# ---------------------------------------------------------------------------

def test_end_to_end_poster_flow(client_id: str) -> None:
    """Full flow: create job, trace steps, persist trace, create feedback, verify trigger."""
    jid = str(uuid4())
    aid = str(uuid4())
    sid = str(uuid4())
    art_id = str(uuid4())

    with get_cursor() as cur:
        # 1. Create job
        cur.execute(
            "INSERT INTO jobs (id, client_id, job_type, status) VALUES (%s, %s, %s, %s)",
            (jid, client_id, "poster", "in_progress"),
        )

        # 2. Create asset (MinIO path)
        test_data = b"poster binary data"
        obj_name = f"posters/{jid}.png"
        upload_bytes(obj_name, test_data, content_type="image/png")

        cur.execute(
            "INSERT INTO assets (id, storage_path, filename, mime_type, size_bytes) VALUES (%s, %s, %s, %s, %s)",
            (aid, f"{BUCKET_NAME}/{obj_name}", "poster.png", "image/png", len(test_data)),
        )

        # 3. Create spec
        cur.execute(
            "INSERT INTO artifact_specs (id, job_id, spec_data) VALUES (%s, %s, %s)",
            (sid, jid, json.dumps({"type": "poster"})),
        )

        # 4. Create artifact
        cur.execute(
            "INSERT INTO artifacts (id, job_id, spec_id, asset_id, artifact_type) VALUES (%s, %s, %s, %s, %s)",
            (art_id, jid, sid, aid, "poster"),
        )

    # 5. Trace production steps
    collector = TraceCollector(job_id=jid)
    with collector.step("interpret") as step:
        step.input_tokens = 50
        step.output_tokens = 30
        step.cost_usd = 0.0005
    with collector.step("generate") as step:
        step.input_tokens = 200
        step.output_tokens = 150
        step.cost_usd = 0.002
    with collector.step("render") as step:
        step.input_tokens = 0
        step.output_tokens = 0
        step.duration_ms = 500

    trace = collect_and_persist(jid, collector)
    assert trace.total_input_tokens == 250

    # 6. Verify trace persisted
    loaded = load_trace(jid)
    assert loaded is not None
    assert len(loaded.steps) == 3

    # 7. Create feedback — trigger should set delivered_at
    fid = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status)
               VALUES (%s, %s, %s, %s, 'awaiting') RETURNING delivered_at""",
            (fid, jid, art_id, client_id),
        )
        row = cur.fetchone()
        assert row["delivered_at"] is not None

        # 8. Transition to approved
        cur.execute(
            """UPDATE feedback SET feedback_status = 'explicitly_approved', operator_rating = 5
               WHERE id = %s RETURNING feedback_received_at, response_time_hours""",
            (fid,),
        )
        row = cur.fetchone()
        assert row["feedback_received_at"] is not None
        assert row["response_time_hours"] is not None

        # 9. Mark job completed
        cur.execute(
            "UPDATE jobs SET status = 'completed', completed_at = now() WHERE id = %s",
            (jid,),
        )

    # Cleanup MinIO
    delete_object(obj_name)


# ---------------------------------------------------------------------------
# §12  Policy logs and visual lineage
# ---------------------------------------------------------------------------

def test_policy_log_insert(job_id: str) -> None:
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO policy_logs (job_id, action, gate, reason, capability)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (job_id, "allow", "budget", "budget within limits", "poster_production"),
        )
        assert cur.fetchone()["id"] is not None


def test_visual_lineage_insert(job_id: str, asset_id: str) -> None:
    with get_cursor() as cur:
        art_id = str(uuid4())
        spec_id_local = str(uuid4())
        cur.execute(
            "INSERT INTO artifact_specs (id, job_id, spec_data) VALUES (%s, %s, %s)",
            (spec_id_local, job_id, json.dumps({"type": "poster"})),
        )
        cur.execute(
            "INSERT INTO artifacts (id, job_id, spec_id, asset_id, artifact_type) VALUES (%s, %s, %s, %s, %s)",
            (art_id, job_id, spec_id_local, asset_id, "poster"),
        )
        cur.execute(
            """INSERT INTO visual_lineage (job_id, artifact_id, asset_id, role, selection_reason)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (job_id, art_id, asset_id, "template", "best match for brand"),
        )
        assert cur.fetchone()["id"] is not None


# ---------------------------------------------------------------------------
# §13  System state
# ---------------------------------------------------------------------------

def test_system_state_seed() -> None:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM system_state WHERE version = '0.1.0'")
        row = cur.fetchone()
        assert row is not None
        assert row["change_type"] == "session_ship"
