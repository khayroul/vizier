"""S16 — BizOps tests.

Covers: schema existence, invoicing, payment state machine, pipeline CRUD,
client health, revenue summary.

Requires: running Postgres (vizier db) and MinIO (localhost:9000).
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = pytest.mark.requires_db

os.environ.setdefault("DATABASE_URL", "postgres://localhost:5432/vizier")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")

from utils.database import get_cursor, run_migration

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema() -> None:
    """Run core.sql + extended.sql to guarantee all tables exist."""
    base = Path(__file__).resolve().parent.parent / "migrations"
    for sql_file in ["core.sql", "extended.sql"]:
        sql_path = base / sql_file
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
def issued_invoice(client_id: str) -> str:
    """Create an issued invoice for RM 1000 and return its id."""
    inv_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO invoices (id, client_id, amount_rm, status, invoice_number)
            VALUES (%s, %s, %s, 'issued', %s)
            """,
            (inv_id, client_id, 1000.00, f"VIZ-TEST-{uuid4().hex[:6]}"),
        )
    return inv_id


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

EXPECTED_TABLES = [
    "invoices",
    "payments",
    "pipeline",
    "steward_inbox",
    "steward_projects",
    "steward_tasks",
    "steward_reviews",
    "steward_health_log",
    "steward_learning",
]


def test_all_nine_tables_exist() -> None:
    """All 9 S16 tables exist after running extended.sql."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = ANY(%s)",
            (EXPECTED_TABLES,),
        )
        found = {row["table_name"] for row in cur.fetchall()}
    missing = set(EXPECTED_TABLES) - found
    assert not missing, f"Missing tables: {missing}"


def test_invoice_number_sequence_exists() -> None:
    """Invoice number sequence exists and returns an integer."""
    with get_cursor() as cur:
        cur.execute("SELECT nextval('invoice_number_seq')")
        row = cur.fetchone()
        assert row is not None
        assert isinstance(row["nextval"], int)


# ---------------------------------------------------------------------------
# Payment state machine tests
# ---------------------------------------------------------------------------


def test_payment_partial_updates_invoice_status(
    client_id: str,
    issued_invoice: str,
) -> None:
    """Partial payment sets invoice status to 'partial'."""
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO payments (invoice_id, client_id, amount_rm, payment_method) "
            "VALUES (%s, %s, %s, 'bank_transfer')",
            (issued_invoice, client_id, 500.00),
        )
        cur.execute(
            "SELECT status FROM invoices WHERE id = %s",
            (issued_invoice,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["status"] == "partial"


def test_payment_full_updates_invoice_to_paid(
    client_id: str,
    issued_invoice: str,
) -> None:
    """Full payment (sum >= amount) sets invoice status to 'paid'."""
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO payments (invoice_id, client_id, amount_rm, payment_method) "
            "VALUES (%s, %s, %s, 'bank_transfer')",
            (issued_invoice, client_id, 1000.00),
        )
        cur.execute(
            "SELECT status, paid_at FROM invoices WHERE id = %s",
            (issued_invoice,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["status"] == "paid"
        assert row["paid_at"] is not None


def test_payment_does_not_transition_from_draft(client_id: str) -> None:
    """Payment on a draft invoice does NOT change status."""
    inv_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO invoices (id, client_id, amount_rm, status, invoice_number) "
            "VALUES (%s, %s, %s, 'draft', %s)",
            (inv_id, client_id, 500.00, f"VIZ-DRAFT-{uuid4().hex[:6]}"),
        )
        cur.execute(
            "INSERT INTO payments (invoice_id, client_id, amount_rm, payment_method) "
            "VALUES (%s, %s, %s, 'cash')",
            (inv_id, client_id, 500.00),
        )
        cur.execute("SELECT status FROM invoices WHERE id = %s", (inv_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["status"] == "draft"


# ---------------------------------------------------------------------------
# Invoice generation test
# ---------------------------------------------------------------------------


def test_generate_invoice_creates_pdf(client_id: str, tmp_path: Path) -> None:
    """generate_invoice() creates a PDF file with correct invoice number."""
    from tools.invoice import generate_invoice

    job_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO jobs (id, client_id, raw_input, status, job_type) "
            "VALUES (%s, %s, 'test job', 'completed', 'poster')",
            (job_id, client_id),
        )

    result = generate_invoice(
        client_id=client_id,
        job_ids=[job_id],
        line_items=[
            {"description": "Content Strategy", "qty": 1, "rate": 5000.00},
            {"description": "Social Media Posts", "qty": 10, "rate": 200.00},
        ],
        notes="Test invoice",
        output_dir=tmp_path,
    )

    assert result["pdf_path"].exists()
    assert result["pdf_path"].suffix == ".pdf"
    assert result["invoice_number"].startswith("VIZ-")
    assert result["invoice_id"] is not None

    # Verify DB record
    with get_cursor() as cur:
        cur.execute(
            "SELECT status, amount_rm FROM invoices WHERE id = %s",
            (result["invoice_id"],),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["status"] == "draft"
        assert float(row["amount_rm"]) == 7000.00


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------


def test_pipeline_create_and_transition(client_id: str) -> None:
    """Pipeline: create lead, transition through stages."""
    from tools.bizops import update_pipeline

    result = update_pipeline(
        prospect_name="Acme Corp",
        stage="lead",
        client_id=client_id,
        estimated_value_rm=10000.00,
    )
    assert result["stage"] == "lead"
    pipeline_id = str(result["id"])

    result = update_pipeline(
        prospect_name="Acme Corp",
        stage="contacted",
        pipeline_id=pipeline_id,
    )
    assert result["stage"] == "contacted"


def test_pipeline_rejects_invalid_transition(client_id: str) -> None:
    """Pipeline: cannot skip from lead to won."""
    from tools.bizops import update_pipeline

    result = update_pipeline(
        prospect_name="Bad Corp",
        stage="lead",
        client_id=client_id,
    )
    pipeline_id = str(result["id"])

    with pytest.raises(ValueError, match="Invalid stage transition"):
        update_pipeline(
            prospect_name="Bad Corp",
            stage="won",
            pipeline_id=pipeline_id,
        )


# ---------------------------------------------------------------------------
# Client health + revenue tests
# ---------------------------------------------------------------------------


def test_client_health_surfaces_overdue(client_id: str) -> None:
    """Client health shows overdue invoices correctly."""
    from tools.bizops import get_client_health

    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO invoices (id, client_id, amount_rm, status, "
            "invoice_number, due_at) "
            "VALUES (%s, %s, 1000.00, 'issued', %s, now() - interval '1 day')",
            (str(uuid4()), client_id, f"VIZ-OD-{uuid4().hex[:6]}"),
        )

    health = get_client_health(client_id)
    assert len(health) == 1
    assert health[0]["overdue_invoices"] >= 1
    assert float(health[0]["overdue_amount_rm"]) >= 1000.00


def test_revenue_summary_returns_structure() -> None:
    """Revenue summary returns expected keys."""
    from tools.bizops import get_revenue_summary

    result = get_revenue_summary("month")
    assert "invoiced_rm" in result
    assert "received_rm" in result
    assert "outstanding_rm" in result
    assert "overdue_rm" in result
    assert result["period"] == "month"
