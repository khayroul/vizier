"""Shared fixtures for integration tests.

Creates test records in the real Postgres database (vizier).
All test records use a 'TEST_INTEG_' prefix for safe cleanup.

IMPORTANT: Fixtures commit data immediately so it's visible across connections.
Cleanup runs in teardown via a separate connection.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from utils.database import get_cursor

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_PREFIX = "TEST_INTEG_"
TEST_CLIENT_NAME = f"{TEST_PREFIX}DMB"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_uuid() -> str:
    """Generate a UUID string for test records."""
    return str(uuid.uuid4())


def _cleanup_client(client_id: str) -> None:
    """Delete all test records associated with a client.

    Uses a single transaction to avoid deadlocks with concurrent cleanup.
    Silently ignores errors since this is best-effort teardown.
    """
    try:
        with get_cursor() as cur:
            cur.execute("DELETE FROM visual_lineage WHERE job_id IN (SELECT id FROM jobs WHERE client_id = %s)", (client_id,))
            cur.execute("DELETE FROM outcome_memory WHERE client_id = %s", (client_id,))
            cur.execute("DELETE FROM feedback WHERE client_id = %s", (client_id,))
            cur.execute("DELETE FROM policy_logs WHERE job_id IN (SELECT id FROM jobs WHERE client_id = %s)", (client_id,))
            cur.execute("DELETE FROM deliveries WHERE job_id IN (SELECT id FROM jobs WHERE client_id = %s)", (client_id,))
            cur.execute("DELETE FROM exemplars WHERE client_id = %s", (client_id,))
            cur.execute("DELETE FROM document_set_members WHERE knowledge_card_id IN (SELECT id FROM knowledge_cards WHERE client_id = %s)", (client_id,))
            cur.execute("DELETE FROM knowledge_cards WHERE client_id = %s", (client_id,))
            cur.execute("DELETE FROM knowledge_sources WHERE client_id = %s", (client_id,))
            cur.execute("DELETE FROM artifacts WHERE job_id IN (SELECT id FROM jobs WHERE client_id = %s)", (client_id,))
            cur.execute("DELETE FROM artifact_specs WHERE job_id IN (SELECT id FROM jobs WHERE client_id = %s)", (client_id,))
            cur.execute("DELETE FROM assets WHERE client_id = %s", (client_id,))
            cur.execute("DELETE FROM jobs WHERE client_id = %s", (client_id,))
            cur.execute("DELETE FROM clients WHERE id = %s", (client_id,))
    except Exception:
        # Best-effort cleanup — don't fail the test on teardown errors
        pass


# ---------------------------------------------------------------------------
# Fixtures — each commits its data before yielding
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_cursor():
    """Yield a RealDictCursor. Commits on clean exit."""
    with get_cursor() as cur:
        yield cur


@pytest.fixture()
def test_client():
    """Create a test client (committed immediately). Cleaned up after test."""
    client_id = _make_uuid()
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO clients (id, name, industry, brand_config, brand_mood, status)
            VALUES (%s, %s, 'textile', '{"primary_color": "#1B4332"}'::jsonb, %s, 'active')
            """,
            (client_id, TEST_CLIENT_NAME, ["warm", "traditional"]),
        )
    yield {"id": client_id, "name": TEST_CLIENT_NAME}
    _cleanup_client(client_id)


@pytest.fixture()
def test_job(test_client):
    """Create a test job linked to the test client (committed immediately)."""
    job_id = _make_uuid()
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO jobs (id, client_id, raw_input, job_type, status)
            VALUES (%s, %s, 'test poster brief', 'poster', 'received')
            """,
            (job_id, test_client["id"]),
        )
    return {"id": job_id, "client_id": test_client["id"]}


@pytest.fixture()
def test_asset(test_client):
    """Create a test asset record (committed immediately)."""
    asset_id = _make_uuid()
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO assets (id, storage_path, filename, mime_type, size_bytes, client_id)
            VALUES (%s, 'test/path/poster.png', 'poster.png', 'image/png', 1024, %s)
            """,
            (asset_id, test_client["id"]),
        )
    return {"id": asset_id}


@pytest.fixture()
def test_artifact(test_job, test_asset):
    """Create a test artifact linked to job and asset (committed immediately)."""
    artifact_id = _make_uuid()
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO artifacts (id, job_id, asset_id, artifact_type, status)
            VALUES (%s, %s, %s, 'poster', 'delivered')
            """,
            (artifact_id, test_job["id"], test_asset["id"]),
        )
    return {"id": artifact_id, "job_id": test_job["id"], "asset_id": test_asset["id"]}


@pytest.fixture()
def test_feedback_awaiting(test_client, test_job, test_artifact):
    """Create a feedback record in 'awaiting' state, delivered 25 hours ago.

    Committed immediately so feedback_check_silence() can see it.
    """
    feedback_id = _make_uuid()
    delivered_at = datetime.now(timezone.utc) - timedelta(hours=25)
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status, delivered_at)
            VALUES (%s, %s, %s, %s, 'awaiting', %s)
            """,
            (feedback_id, test_job["id"], test_artifact["id"], test_client["id"], delivered_at),
        )
    return {
        "id": feedback_id,
        "job_id": test_job["id"],
        "artifact_id": test_artifact["id"],
        "client_id": test_client["id"],
    }


@pytest.fixture()
def seed_knowledge_cards(test_client):
    """Seed 2 test knowledge cards for the test client (Raya-related)."""
    source_id = _make_uuid()
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_sources (id, client_id, source_type, title, domain, language, status)
            VALUES (%s, %s, 'manual', 'DMB Raya 2025 Campaign', 'marketing', 'bm', 'active')
            """,
            (source_id, test_client["id"]),
        )

        cards = []
        for title, content in [
            ("Raya Campaign Theme", "Tema Raya 2025: Keluarga Bahagia. Target: keluarga Melayu kelas menengah."),
            ("DMB Brand Voice", "Nada formal tetapi mesra. Warna utama hijau tua (#1B4332) dan emas (#D4A843)."),
        ]:
            card_id = _make_uuid()
            cur.execute(
                """
                INSERT INTO knowledge_cards (id, source_id, client_id, card_type, title, content, tags, domain, status)
                VALUES (%s, %s, %s, 'fact', %s, %s, %s, 'marketing', 'active')
                """,
                (card_id, source_id, test_client["id"], title, content, ["raya", "2025", "dmb"]),
            )
            cards.append({"id": card_id, "title": title})

    return cards
