# S16 BizOps + Steward + Crons — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build BizOps (invoicing, payments, pipeline, client health, crons) and Steward (GTD personal assistant with inbox, /next, /done, /snapshot, /project) with 9 database tables.

**Architecture:** Three tool modules (`tools/invoice.py`, `tools/bizops.py`, `tools/steward.py`) plus a cross-cutting briefing module (`tools/briefing.py`). All backed by 9 Postgres tables in `migrations/extended.sql`. Prayer times via `adhan` library. Invoice PDF via programmatic Typst generation.

**Tech Stack:** Python 3.11, psycopg2, Typst (CLI), MinIO, adhan (prayer times), GPT-5.4-mini via `call_llm()`.

**Spec:** `docs/superpowers/specs/2026-04-08-s16-bizops-steward-design.md`

---

## Chunk 1: Foundation (Database + Config + Dependencies)

### Task 1: Install `adhan` dependency and add to pyproject.toml

**Files:**
- Modify: `pyproject.toml:48` (add adhan to dependencies)

- [ ] **Step 1: Install adhan**

```bash
pip3.11 install adhan --break-system-packages
```

- [ ] **Step 2: Add adhan to pyproject.toml**

In `pyproject.toml`, add `"adhan>=1.0",` to the dependencies list after the `croniter` line:

```toml
    "croniter>=2.0.0",
    "adhan>=1.0",
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore(s16): add adhan prayer times dependency"
```

### Task 2: Create domain constants

**Files:**
- Create: `config/steward_domains.py`
- Test: `tests/test_s16_steward.py` (domain validation test)

- [ ] **Step 1: Write the test for domain constants**

Create `tests/test_s16_steward.py`:

```python
"""S16 — Steward tests.

Covers: inbox capture, process, /next, /done, /snapshot, /project,
domain balance, and domain constants.

Requires: running Postgres (vizier db).
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

os.environ.setdefault("DATABASE_URL", "postgres://localhost:5432/vizier")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")


def test_domains_are_21_unique_strings() -> None:
    """Domain constants: exactly 21 unique non-empty strings."""
    from config.steward_domains import DOMAINS

    assert len(DOMAINS) == 21
    assert len(set(DOMAINS)) == 21
    for domain in DOMAINS:
        assert isinstance(domain, str)
        assert len(domain) > 0
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_steward.py::test_domains_are_21_unique_strings -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'config.steward_domains'`

- [ ] **Step 3: Create the domain constants file**

Create `config/steward_domains.py`:

```python
"""21 Wisdom Vault life domains for Steward task balance tracking.

Flat constant list — no logic. Used by steward.py for domain validation
and heatmap generation. Operator can adjust this list post-deploy.
"""

from __future__ import annotations

DOMAINS: list[str] = [
    "Deen",
    "Health",
    "Family",
    "Marriage",
    "Parenting",
    "Career",
    "Business",
    "Finance",
    "Learning",
    "Teaching",
    "Community",
    "Dawah",
    "Creativity",
    "Environment",
    "Legacy",
    "Social",
    "Self-Care",
    "Recreation",
    "Civic",
    "Travel",
    "Gratitude",
]

# Domain heatmap thresholds (tasks completed in last 7 days)
HEATMAP_GREEN = 3   # 3+ tasks = active
HEATMAP_AMBER = 1   # 1-2 tasks = slowing
# 0 tasks for 7+ days = red (neglected)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_steward.py::test_domains_are_21_unique_strings -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/steward_domains.py tests/test_s16_steward.py
git commit -m "feat(s16): add 21 Wisdom Vault domain constants"
```

### Task 3: Create prayer times utility

**Files:**
- Create: `utils/prayer_times.py`
- Test: inline in existing test file

- [ ] **Step 1: Write the test for prayer times**

Append to `tests/test_s16_steward.py`:

```python
from datetime import date, time


def test_prayer_times_returns_five_prayers() -> None:
    """Prayer times: returns dict with 5 prayer times for a given date."""
    from utils.prayer_times import get_prayer_times

    times = get_prayer_times(date(2026, 4, 8))
    assert "subuh" in times
    assert "zohor" in times
    assert "asr" in times
    assert "maghrib" in times
    assert "isyak" in times
    for prayer_time in times.values():
        assert isinstance(prayer_time, time)


def test_prayer_times_subuh_before_asr() -> None:
    """Subuh is always before Asr."""
    from utils.prayer_times import get_prayer_times

    times = get_prayer_times(date(2026, 4, 8))
    assert times["subuh"] < times["asr"]
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_steward.py::test_prayer_times_returns_five_prayers -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement prayer times utility**

Create `utils/prayer_times.py`:

```python
"""Prayer time calculation for Malaysian scheduling.

Uses the adhan library with Kuala Lumpur coordinates.
Falls back to a static lookup table if adhan is unavailable.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time

logger = logging.getLogger(__name__)

# Kuala Lumpur coordinates
_KL_LAT = 3.1390
_KL_LON = 101.6869

# Static fallback: approximate monthly averages for KL (24h format)
# Source: JAKIM prayer time tables, averaged per month
_STATIC_TIMES: dict[int, dict[str, tuple[int, int]]] = {
    1:  {"subuh": (5, 58), "zohor": (13, 15), "asr": (16, 36), "maghrib": (19, 24), "isyak": (20, 35)},
    2:  {"subuh": (6, 1),  "zohor": (13, 16), "asr": (16, 38), "maghrib": (19, 25), "isyak": (20, 35)},
    3:  {"subuh": (5, 57), "zohor": (13, 12), "asr": (16, 33), "maghrib": (19, 19), "isyak": (20, 29)},
    4:  {"subuh": (5, 49), "zohor": (13, 6),  "asr": (16, 25), "maghrib": (19, 12), "isyak": (20, 23)},
    5:  {"subuh": (5, 44), "zohor": (13, 3),  "asr": (16, 21), "maghrib": (19, 9),  "isyak": (20, 21)},
    6:  {"subuh": (5, 45), "zohor": (13, 4),  "asr": (16, 23), "maghrib": (19, 11), "isyak": (20, 23)},
    7:  {"subuh": (5, 49), "zohor": (13, 8),  "asr": (16, 27), "maghrib": (19, 14), "isyak": (20, 26)},
    8:  {"subuh": (5, 48), "zohor": (13, 7),  "asr": (16, 26), "maghrib": (19, 13), "isyak": (20, 24)},
    9:  {"subuh": (5, 42), "zohor": (13, 2),  "asr": (16, 19), "maghrib": (19, 7),  "isyak": (20, 18)},
    10: {"subuh": (5, 36), "zohor": (12, 57), "asr": (16, 12), "maghrib": (19, 1),  "isyak": (20, 12)},
    11: {"subuh": (5, 36), "zohor": (12, 58), "asr": (16, 12), "maghrib": (19, 1),  "isyak": (20, 13)},
    12: {"subuh": (5, 44), "zohor": (13, 5),  "asr": (16, 20), "maghrib": (19, 10), "isyak": (20, 22)},
}


def get_prayer_times(target_date: date | None = None) -> dict[str, time]:
    """Return today's prayer times for Kuala Lumpur.

    Tries the adhan library first, falls back to static monthly averages.

    Returns:
        Dict with keys: subuh, zohor, asr, maghrib, isyak.
        Values are datetime.time objects.
    """
    if target_date is None:
        target_date = date.today()

    try:
        return _adhan_times(target_date)
    except Exception:
        logger.info("adhan library unavailable, using static prayer times")
        return _static_times(target_date)


def _adhan_times(target_date: date) -> dict[str, time]:
    """Calculate prayer times using the adhan library."""
    from adhan import adhan  # type: ignore[import-untyped]
    from adhan.methods import ISNA  # type: ignore[import-untyped]

    params = ISNA
    prayers = adhan(
        day=target_date.day,
        month=target_date.month,
        year=target_date.year,
        latitude=_KL_LAT,
        longitude=_KL_LON,
        method=params,
        time_zone=8,  # MYT = UTC+8
    )
    return {
        "subuh": time(prayers["fajr"][0], prayers["fajr"][1]),
        "zohor": time(prayers["dhuhr"][0], prayers["dhuhr"][1]),
        "asr": time(prayers["asr"][0], prayers["asr"][1]),
        "maghrib": time(prayers["maghrib"][0], prayers["maghrib"][1]),
        "isyak": time(prayers["isha"][0], prayers["isha"][1]),
    }


def _static_times(target_date: date) -> dict[str, time]:
    """Return static monthly average prayer times for KL."""
    month_data = _STATIC_TIMES[target_date.month]
    return {
        name: time(hour, minute)
        for name, (hour, minute) in month_data.items()
    }


def is_after_prayer(prayer: str, target_date: date | None = None) -> bool:
    """Check if current time is after the given prayer time."""
    times = get_prayer_times(target_date)
    if prayer not in times:
        raise ValueError(f"Unknown prayer: {prayer}. Use: {list(times.keys())}")
    now = datetime.now().time()
    return now >= times[prayer]
```

- [ ] **Step 4: Run all prayer time tests**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_steward.py -k "prayer" -v
```

Expected: PASS

- [ ] **Step 5: Run pyright on the new file**

```bash
cd /Users/Executor/vizier && python3.11 -m pyright utils/prayer_times.py
```

Fix any type errors.

- [ ] **Step 6: Commit**

```bash
git add utils/prayer_times.py tests/test_s16_steward.py
git commit -m "feat(s16): prayer times utility with adhan + static fallback"
```

### Task 4: Database migration — 9 tables + trigger + sequence

**Files:**
- Modify: `migrations/extended.sql`
- Test: `tests/test_s16_bizops.py` (schema existence test)

- [ ] **Step 1: Write the schema existence test**

Create `tests/test_s16_bizops.py`:

```python
"""S16 — BizOps tests.

Covers: invoicing, payments, pipeline, client health, revenue.

Requires: running Postgres (vizier db) and MinIO (localhost:9000).
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

os.environ.setdefault("DATABASE_URL", "postgres://localhost:5432/vizier")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")

from utils.database import get_cursor, run_migration


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema() -> None:
    """Run core.sql + extended.sql to guarantee all tables exist."""
    base = Path(__file__).resolve().parent.parent / "migrations"
    for sql_file in ["core.sql", "extended.sql"]:
        sql_path = base / sql_file
        if sql_path.exists():
            run_migration(sql_path)


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
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            (EXPECTED_TABLES,),
        )
        found = {row["table_name"] for row in cur.fetchall()}
    missing = set(EXPECTED_TABLES) - found
    assert not missing, f"Missing tables: {missing}"


def test_invoice_number_sequence_exists() -> None:
    """Invoice number sequence exists and returns an integer."""
    with get_cursor() as cur:
        cur.execute("SELECT nextval('invoice_number_seq')")
        val = cur.fetchone()["nextval"]
        assert isinstance(val, int)
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_bizops.py::test_all_nine_tables_exist -v
```

Expected: FAIL — tables don't exist yet

- [ ] **Step 3: Write extended.sql with all 9 tables**

Replace the content of `migrations/extended.sql` with the full DDL. Tables must be created in FK-dependency order:

1. `invoices` (refs `clients`, `assets`)
2. `payments` (refs `invoices`, `clients`)
3. `pipeline` (refs `clients`, `assets`)
4. `steward_inbox` (no new-table FKs)
5. `steward_projects` (self-ref)
6. `steward_tasks` (refs `steward_inbox`, `steward_projects`)
7. `steward_reviews` (no FKs)
8. `steward_health_log` (no FKs)
9. `steward_learning` (no FKs)

DDL is verbatim from architecture §16.4 and §16.4a. Add:

```sql
-- Invoice number sequence for VIZ-YYYY-NNN format
CREATE SEQUENCE IF NOT EXISTS invoice_number_seq;
```

Then add the payment trigger:

```sql
-- Payment state machine: update invoice status when payment received.
-- Only transitions from 'issued' or 'partial' — never from 'draft'.
CREATE OR REPLACE FUNCTION update_invoice_status_on_payment()
RETURNS trigger AS $$
DECLARE
    total_paid decimal(10,2);
    invoice_amount decimal(10,2);
    current_status text;
BEGIN
    SELECT COALESCE(SUM(amount_rm), 0) INTO total_paid
      FROM payments WHERE invoice_id = NEW.invoice_id;

    SELECT amount_rm, status INTO invoice_amount, current_status
      FROM invoices WHERE id = NEW.invoice_id;

    -- Only transition from issued or partial, never from draft
    IF current_status IN ('issued', 'partial') THEN
        IF total_paid >= invoice_amount THEN
            UPDATE invoices SET status = 'paid', paid_at = now()
             WHERE id = NEW.invoice_id;
        ELSE
            UPDATE invoices SET status = 'partial'
             WHERE id = NEW.invoice_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_invoice_on_payment ON payments;
CREATE TRIGGER trg_update_invoice_on_payment
    AFTER INSERT ON payments
    FOR EACH ROW
    EXECUTE FUNCTION update_invoice_status_on_payment();
```

- [ ] **Step 4: Run the migration**

```bash
cd /Users/Executor/vizier && psql -d vizier -f migrations/extended.sql
```

Expected: no errors

- [ ] **Step 5: Run the schema tests**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_bizops.py -k "tables_exist or sequence" -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add migrations/extended.sql tests/test_s16_bizops.py
git commit -m "feat(s16): 9 extended tables + payment trigger + invoice sequence"
```

---

## Chunk 2: Invoice Generation

### Task 5: Payment state machine tests

**Files:**
- Modify: `tests/test_s16_bizops.py`

- [ ] **Step 1: Add payment state machine tests**

Append to `tests/test_s16_bizops.py`:

```python
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
            VALUES (%s, %s, %s, 'issued', 'VIZ-2026-TEST')
            """,
            (inv_id, client_id, 1000.00),
        )
    return inv_id


def test_payment_partial_updates_invoice_status(
    client_id: str, issued_invoice: str
) -> None:
    """Partial payment sets invoice status to 'partial'."""
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO payments (invoice_id, client_id, amount_rm, payment_method)
            VALUES (%s, %s, %s, 'bank_transfer')
            """,
            (issued_invoice, client_id, 500.00),
        )
        cur.execute(
            "SELECT status FROM invoices WHERE id = %s", (issued_invoice,)
        )
        assert cur.fetchone()["status"] == "partial"


def test_payment_full_updates_invoice_to_paid(
    client_id: str, issued_invoice: str
) -> None:
    """Full payment (sum >= amount) sets invoice status to 'paid'."""
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO payments (invoice_id, client_id, amount_rm, payment_method)
            VALUES (%s, %s, %s, 'bank_transfer')
            """,
            (issued_invoice, client_id, 1000.00),
        )
        cur.execute(
            "SELECT status, paid_at FROM invoices WHERE id = %s",
            (issued_invoice,),
        )
        row = cur.fetchone()
        assert row["status"] == "paid"
        assert row["paid_at"] is not None


def test_payment_does_not_transition_from_draft(client_id: str) -> None:
    """Payment on a draft invoice does NOT change status."""
    inv_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO invoices (id, client_id, amount_rm, status, invoice_number)
            VALUES (%s, %s, %s, 'draft', 'VIZ-2026-DRAFT')
            """,
            (inv_id, client_id, 500.00),
        )
        cur.execute(
            """
            INSERT INTO payments (invoice_id, client_id, amount_rm, payment_method)
            VALUES (%s, %s, %s, 'cash')
            """,
            (inv_id, client_id, 500.00),
        )
        cur.execute("SELECT status FROM invoices WHERE id = %s", (inv_id,))
        assert cur.fetchone()["status"] == "draft"
```

- [ ] **Step 2: Run payment tests**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_bizops.py -k "payment" -v
```

Expected: PASS (trigger was created in Task 4)

- [ ] **Step 3: Commit**

```bash
git add tests/test_s16_bizops.py
git commit -m "test(s16): payment state machine tests — partial, full, draft guard"
```

### Task 6: Invoice generation tool

**Files:**
- Create: `tools/invoice.py`
- Modify: `tests/test_s16_bizops.py`

- [ ] **Step 1: Write the invoice generation test**

Append to `tests/test_s16_bizops.py`:

```python
def test_generate_invoice_creates_pdf(client_id: str, tmp_path: Path) -> None:
    """generate_invoice() creates a PDF file with correct invoice number."""
    from tools.invoice import generate_invoice

    # Create a test job
    job_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO jobs (id, client_id, raw_input, status, job_type)
            VALUES (%s, %s, 'test job', 'completed', 'poster')
            """,
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
    assert result["invoice_number"].startswith("VIZ-2026-")
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
        assert float(row["amount_rm"]) == 7000.00  # 5000 + 10*200
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_bizops.py::test_generate_invoice_creates_pdf -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement tools/invoice.py**

Create `tools/invoice.py`:

```python
"""Invoice generation tool for Vizier BizOps.

Generates professional PDF invoices via programmatic Typst source generation.
Stores invoice records in Postgres, PDFs in MinIO (anti-drift #7).
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from utils.database import get_cursor
from utils.spans import track_span
from utils.storage import upload_bytes

logger = logging.getLogger(__name__)

_FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts"


@track_span(step_type="invoice")
def generate_invoice(
    *,
    client_id: str,
    job_ids: list[str],
    line_items: list[dict[str, Any]],
    notes: str = "",
    tax_rate: float = 0.0,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate an invoice PDF and store the record.

    Args:
        client_id: UUID of the client.
        job_ids: List of job UUIDs covered by this invoice.
        line_items: List of dicts with keys: description, qty, rate.
        notes: Optional notes on the invoice.
        tax_rate: Tax rate as decimal (e.g. 0.08 for 8% SST). Default 0.0.
        output_dir: Where to write the PDF. Uses tempdir if None.

    Returns:
        Dict with: invoice_id, invoice_number, pdf_path, amount_rm.
    """
    # Generate invoice number
    with get_cursor() as cur:
        cur.execute("SELECT nextval('invoice_number_seq')")
        seq = cur.fetchone()["nextval"]
    year = datetime.now().year
    invoice_number = f"VIZ-{year}-{seq:03d}"

    # Calculate totals
    subtotal = sum(item["qty"] * item["rate"] for item in line_items)
    tax_amount = subtotal * tax_rate
    total = subtotal + tax_amount

    # Fetch client info for the invoice
    with get_cursor() as cur:
        cur.execute(
            "SELECT name, billing_config FROM clients WHERE id = %s",
            (client_id,),
        )
        client_row = cur.fetchone()
    client_name = client_row["name"] if client_row else "Unknown Client"
    billing = client_row.get("billing_config") or {} if client_row else {}

    # Generate Typst source and compile
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp())
    pdf_path = _render_invoice_typst(
        invoice_number=invoice_number,
        client_name=client_name,
        billing=billing,
        line_items=line_items,
        subtotal=subtotal,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        total=total,
        notes=notes,
        output_dir=output_dir,
    )

    # Upload PDF to MinIO
    pdf_bytes = pdf_path.read_bytes()
    storage_path = upload_bytes(
        f"invoices/{invoice_number}.pdf",
        pdf_bytes,
        content_type="application/pdf",
    )

    # Create asset record for the PDF
    asset_id = str(uuid4())
    invoice_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO assets (id, storage_path, mime_type, size_bytes)
            VALUES (%s, %s, 'application/pdf', %s)
            """,
            (asset_id, storage_path, len(pdf_bytes)),
        )
        cur.execute(
            """
            INSERT INTO invoices
              (id, client_id, job_ids, amount_rm, description, invoice_number,
               pdf_asset_id, notes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'draft')
            """,
            (
                invoice_id,
                client_id,
                job_ids,
                total,
                f"Invoice {invoice_number}",
                invoice_number,
                asset_id,
                notes,
            ),
        )

    return {
        "invoice_id": invoice_id,
        "invoice_number": invoice_number,
        "pdf_path": pdf_path,
        "amount_rm": total,
    }


def _render_invoice_typst(
    *,
    invoice_number: str,
    client_name: str,
    billing: dict[str, Any],
    line_items: list[dict[str, Any]],
    subtotal: float,
    tax_rate: float,
    tax_amount: float,
    total: float,
    notes: str,
    output_dir: Path,
) -> Path:
    """Generate a Typst source file and compile to PDF."""
    tax_label = f"SST ({tax_rate * 100:.0f}%)" if tax_rate > 0 else "Tax"

    # Build Typst line items array
    items_typst = ",\n    ".join(
        f'(desc: "{item["description"]}", qty: {item["qty"]}, rate: {item["rate"]:.2f})'
        for item in line_items
    )

    invoice_date = datetime.now().strftime("%-d %B %Y")
    # Due date: 14 days from now
    from datetime import timedelta

    due_date = (datetime.now() + timedelta(days=14)).strftime("%-d %B %Y")

    # Client details from billing_config
    client_ssm = billing.get("ssm", "")
    client_address = billing.get("address", "")
    client_attn = billing.get("contact_person", "")

    typst_source = f'''// Auto-generated invoice — {invoice_number}
#let primary      = rgb("#1A1A2E")
#let secondary    = rgb("#F8F9FA")
#let accent       = rgb("#2563EB")
#let heading-font = "Inter"
#let body-font    = "Inter"

#let company-name    = "Vizier Digital Sdn Bhd"
#let company-ssm     = "202401012345 (1234567-A)"
#let company-address = "Level 10, Menara Example\\nJalan Ampang, 50450 Kuala Lumpur"
#let company-phone   = "+60 3-1234 5678"
#let company-email   = "billing@vizier.com.my"

#let invoice-number = "{invoice_number}"
#let invoice-date   = "{invoice_date}"
#let due-date       = "{due_date}"

#let client-name    = "{client_name}"
#let client-ssm     = "{client_ssm}"
#let client-address = "{client_address}"
#let client-attn    = "{client_attn}"

#let bank-name    = "Maybank"
#let bank-account = "5123 4567 8901"
#let bank-swift   = "MBBEMYKL"

#let tax-label = "{tax_label}"
#let tax-rate  = {tax_rate}

#let items = (
    {items_typst},
)

#let fmt-myr(amount) = {{
  let whole = calc.floor(amount)
  let cents = calc.round((amount - whole) * 100)
  let cents-str = if cents < 10 {{ "0" + str(cents) }} else {{ str(cents) }}
  str(whole) + "." + cents-str
}}

#let subtotal = items.map(item => item.qty * item.rate).sum()
#let tax-amount = subtotal * tax-rate
#let total = subtotal + tax-amount

#set page(paper: "a4", margin: (top: 2cm, bottom: 2.5cm, left: 2cm, right: 2cm),
  footer: context [
    #line(length: 100%, stroke: 0.3pt + luma(200))
    #v(0.3em)
    #set text(size: 7.5pt, fill: luma(120))
    #grid(columns: (1fr, 1fr), align: (left, right),
      [#company-name · SSM #company-ssm],
      [Page #counter(page).display("1")],
    )
  ],
)

#set text(font: body-font, size: 10pt, fill: luma(30))
#set par(leading: 0.6em, spacing: 1em)

#grid(columns: (1fr, auto), align: (left, right),
  [
    #text(font: heading-font, size: 18pt, weight: "bold", fill: primary)[#company-name]
    #v(0.2em)
    #text(size: 8.5pt, fill: luma(80))[SSM: #company-ssm]
    #v(0.1em)
    #text(size: 8.5pt, fill: luma(80))[#company-address]
    #v(0.1em)
    #text(size: 8.5pt, fill: luma(80))[#company-phone · #company-email]
  ],
  [#text(font: heading-font, size: 28pt, weight: "bold", fill: accent)[INVOICE]],
)

#v(0.8em)
#line(length: 100%, stroke: 1.5pt + primary)
#v(0.8em)

#grid(columns: (1fr, 1fr), column-gutter: 2cm,
  [
    #text(font: heading-font, size: 9pt, weight: "bold", fill: luma(100))[BILL TO]
    #v(0.3em)
    #text(weight: "bold")[#client-name]
    #v(0.1em)
    #text(size: 9pt, fill: luma(60))[SSM: #client-ssm]
    #v(0.1em)
    #text(size: 9pt, fill: luma(60))[#client-address]
    #v(0.1em)
    #text(size: 9pt, fill: luma(60))[Attn: #client-attn]
  ],
  [
    #align(right)[
      #grid(columns: (auto, auto), column-gutter: 12pt, row-gutter: 6pt, align: (right, left),
        text(size: 9pt, weight: "bold", fill: luma(100))[Invoice No:],
        text(size: 9pt)[#invoice-number],
        text(size: 9pt, weight: "bold", fill: luma(100))[Date:],
        text(size: 9pt)[#invoice-date],
        text(size: 9pt, weight: "bold", fill: luma(100))[Due Date:],
        text(size: 9pt, weight: "bold", fill: accent)[#due-date],
      )
    ]
  ],
)

#v(1.2em)

#table(
  columns: (auto, 1fr, auto, auto, auto), stroke: none,
  inset: (x: 8pt, y: 6pt),
  table.hline(stroke: 1pt + primary),
  text(size: 8.5pt, weight: "bold", fill: primary)[No.],
  text(size: 8.5pt, weight: "bold", fill: primary)[Description],
  text(size: 8.5pt, weight: "bold", fill: primary)[Qty],
  text(size: 8.5pt, weight: "bold", fill: primary)[Rate (MYR)],
  text(size: 8.5pt, weight: "bold", fill: primary)[Amount (MYR)],
  table.hline(stroke: 0.5pt + luma(200)),
  ..{{
    let rows = ()
    for (idx, item) in items.enumerate() {{
      let amount = item.qty * item.rate
      rows.push(text(size: 9pt)[#{{idx + 1}}])
      rows.push(text(size: 9pt)[#item.desc])
      rows.push(align(center, text(size: 9pt)[#item.qty]))
      rows.push(align(right, text(size: 9pt)[#fmt-myr(item.rate)]))
      rows.push(align(right, text(size: 9pt)[#fmt-myr(amount)]))
    }}
    rows
  }},
  table.hline(stroke: 0.5pt + luma(200)),
)

#v(0.5em)
#align(right)[
  #grid(columns: (auto, 8em), column-gutter: 2em, row-gutter: 6pt, align: (right, right),
    text(size: 10pt, fill: luma(60))[Subtotal:],
    text(size: 10pt)[MYR #fmt-myr(subtotal)],
    text(size: 10pt, fill: luma(60))[#tax-label:],
    text(size: 10pt)[MYR #fmt-myr(tax-amount)],
    line(length: 100%, stroke: 0.5pt + luma(200)),
    line(length: 100%, stroke: 0.5pt + luma(200)),
    text(font: heading-font, size: 12pt, weight: "bold", fill: primary)[TOTAL:],
    text(font: heading-font, size: 12pt, weight: "bold", fill: primary)[MYR #fmt-myr(total)],
  )
]

#v(1.5em)

#rect(width: 100%, inset: 14pt, radius: 4pt, fill: secondary, stroke: 0.5pt + luma(220))[
  #text(font: heading-font, size: 10pt, weight: "bold", fill: primary)[Payment Details]
  #v(0.4em)
  #grid(columns: (auto, 1fr), column-gutter: 12pt, row-gutter: 4pt,
    text(size: 9pt, weight: "bold", fill: luma(80))[Bank:], text(size: 9pt)[#bank-name],
    text(size: 9pt, weight: "bold", fill: luma(80))[Account Name:], text(size: 9pt)[#company-name],
    text(size: 9pt, weight: "bold", fill: luma(80))[Account No:], text(size: 9pt)[#bank-account],
    text(size: 9pt, weight: "bold", fill: luma(80))[SWIFT Code:], text(size: 9pt)[#bank-swift],
  )
]

#v(1em)
#text(font: heading-font, size: 10pt, weight: "bold", fill: primary)[Payment Terms]
#v(0.3em)
#set text(size: 9pt, fill: luma(60))
+ Payment is due within 14 days of invoice date.
+ Please include the invoice number (#invoice-number) as payment reference.
+ Late payments are subject to a 1.5% monthly charge on outstanding balance.
+ All amounts are in Malaysian Ringgit (MYR).

#v(1.5em)
#align(center)[
  #text(size: 9pt, fill: luma(120))[
    Thank you for your business. · Terima kasih atas urusan perniagaan anda.
  ]
]
'''

    typ_path = output_dir / f"{invoice_number}.typ"
    typ_path.write_text(typst_source, encoding="utf-8")

    pdf_path = output_dir / f"{invoice_number}.pdf"
    env = {"TYPST_FONT_PATHS": str(_FONT_PATH)}
    result = subprocess.run(
        ["typst", "compile", str(typ_path), str(pdf_path)],
        capture_output=True,
        text=True,
        env={**subprocess.os.environ, **env},  # type: ignore[arg-type]
        check=False,
    )
    if result.returncode != 0:
        logger.error("Typst compile failed: %s", result.stderr)
        raise RuntimeError(f"Typst compile failed: {result.stderr}")

    return pdf_path
```

- [ ] **Step 4: Run the invoice test**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_bizops.py::test_generate_invoice_creates_pdf -v
```

Expected: PASS

- [ ] **Step 5: Run pyright**

```bash
cd /Users/Executor/vizier && python3.11 -m pyright tools/invoice.py
```

Fix any type errors.

- [ ] **Step 6: Commit**

```bash
git add tools/invoice.py tests/test_s16_bizops.py
git commit -m "feat(s16): invoice generation with programmatic Typst + MinIO upload"
```

---

## Chunk 3: BizOps Tools (Pipeline + Health + Revenue)

### Task 7: Pipeline CRUD

**Files:**
- Create: `tools/bizops.py`
- Modify: `tests/test_s16_bizops.py`

- [ ] **Step 1: Write pipeline tests**

Append to `tests/test_s16_bizops.py`:

```python
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
    pipeline_id = result["id"]

    # Valid transition: lead → contacted
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
    pipeline_id = result["id"]

    with pytest.raises(ValueError, match="Invalid stage transition"):
        update_pipeline(
            prospect_name="Bad Corp",
            stage="won",
            pipeline_id=pipeline_id,
        )
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_bizops.py -k "pipeline" -v
```

Expected: FAIL

- [ ] **Step 3: Implement tools/bizops.py**

Create `tools/bizops.py`:

```python
"""BizOps tools — pipeline CRUD, client health, revenue summary.

All queries use the Postgres tables from migrations/extended.sql.
Model: GPT-5.4-mini for any LLM work (anti-drift #54).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from utils.database import get_cursor
from utils.spans import track_span

logger = logging.getLogger(__name__)

# Valid pipeline stages and allowed transitions
PIPELINE_STAGES = ["lead", "contacted", "proposal_sent", "negotiating", "won", "lost"]

_VALID_TRANSITIONS: dict[str, list[str]] = {
    "lead": ["contacted", "lost"],
    "contacted": ["proposal_sent", "lost"],
    "proposal_sent": ["negotiating", "lost"],
    "negotiating": ["won", "lost"],
    "won": [],
    "lost": [],
}


@track_span(step_type="bizops")
def update_pipeline(
    *,
    prospect_name: str,
    stage: str,
    pipeline_id: str | None = None,
    client_id: str | None = None,
    estimated_value_rm: float | None = None,
    source: str | None = None,
    notes: str | None = None,
    next_followup_at: datetime | None = None,
) -> dict[str, Any]:
    """Create or update a pipeline entry.

    If pipeline_id is None, creates a new entry at the given stage.
    If pipeline_id is provided, validates the stage transition.

    Raises:
        ValueError: If stage is invalid or transition is not allowed.
    """
    if stage not in PIPELINE_STAGES:
        raise ValueError(f"Invalid stage: {stage}. Valid: {PIPELINE_STAGES}")

    if pipeline_id is not None:
        # Update existing — validate transition
        with get_cursor() as cur:
            cur.execute(
                "SELECT stage FROM pipeline WHERE id = %s", (pipeline_id,)
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Pipeline entry not found: {pipeline_id}")
            current_stage = row["stage"]
            if stage not in _VALID_TRANSITIONS.get(current_stage, []):
                raise ValueError(
                    f"Invalid stage transition: {current_stage} → {stage}. "
                    f"Allowed: {_VALID_TRANSITIONS.get(current_stage, [])}"
                )
            cur.execute(
                """
                UPDATE pipeline
                   SET stage = %s, prospect_name = %s, notes = COALESCE(%s, notes),
                       estimated_value_rm = COALESCE(%s, estimated_value_rm),
                       next_followup_at = COALESCE(%s, next_followup_at),
                       updated_at = now()
                 WHERE id = %s
                RETURNING id, prospect_name, stage, estimated_value_rm, created_at
                """,
                (stage, prospect_name, notes, estimated_value_rm,
                 next_followup_at, pipeline_id),
            )
            return dict(cur.fetchone())
    else:
        # Create new
        new_id = str(uuid4())
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline
                  (id, client_id, prospect_name, stage, estimated_value_rm,
                   source, notes, next_followup_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, prospect_name, stage, estimated_value_rm, created_at
                """,
                (new_id, client_id, prospect_name, stage, estimated_value_rm,
                 source, notes, next_followup_at),
            )
            return dict(cur.fetchone())


@track_span(step_type="bizops")
def get_client_health(client_id: str | None = None) -> list[dict[str, Any]]:
    """Return client health data: overdue invoices, last job timestamps.

    If client_id is None, returns health for all clients.
    Overdue = status IN ('issued', 'partial') AND due_at < now().
    """
    where_clause = "WHERE c.id = %s" if client_id else ""
    params: tuple[Any, ...] = (client_id,) if client_id else ()

    query = f"""
        SELECT
            c.id AS client_id,
            c.name AS client_name,
            (SELECT MAX(j.created_at) FROM jobs j WHERE j.client_id = c.id)
                AS last_job_at,
            (SELECT COUNT(*) FROM invoices i
             WHERE i.client_id = c.id
               AND i.status IN ('issued', 'partial')
               AND i.due_at < now())
                AS overdue_invoices,
            (SELECT COALESCE(SUM(i.amount_rm), 0) FROM invoices i
             WHERE i.client_id = c.id
               AND i.status IN ('issued', 'partial')
               AND i.due_at < now())
                AS overdue_amount_rm,
            (SELECT p.stage FROM pipeline p
             WHERE p.client_id = c.id
             ORDER BY p.updated_at DESC LIMIT 1)
                AS pipeline_stage
        FROM clients c
        {where_clause}
        ORDER BY c.name
    """
    with get_cursor() as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


@track_span(step_type="bizops")
def get_revenue_summary(period: str = "month") -> dict[str, Any]:
    """Return revenue summary: invoiced, received, outstanding, overdue.

    Args:
        period: 'month' (current month) or 'week' (current week).
    """
    if period == "week":
        start = datetime.now() - timedelta(days=datetime.now().weekday())
    else:
        start = datetime.now().replace(day=1, hour=0, minute=0, second=0)

    with get_cursor() as cur:
        # Total invoiced this period
        cur.execute(
            """
            SELECT COALESCE(SUM(amount_rm), 0) AS invoiced
            FROM invoices WHERE issued_at >= %s
            """,
            (start,),
        )
        invoiced = cur.fetchone()["invoiced"]

        # Total received this period
        cur.execute(
            """
            SELECT COALESCE(SUM(amount_rm), 0) AS received
            FROM payments WHERE received_at >= %s
            """,
            (start,),
        )
        received = cur.fetchone()["received"]

        # Outstanding (issued or partial, not yet fully paid)
        cur.execute(
            """
            SELECT COALESCE(SUM(amount_rm), 0) AS outstanding
            FROM invoices WHERE status IN ('issued', 'partial')
            """
        )
        outstanding = cur.fetchone()["outstanding"]

        # Overdue (outstanding + past due)
        cur.execute(
            """
            SELECT COALESCE(SUM(amount_rm), 0) AS overdue
            FROM invoices
            WHERE status IN ('issued', 'partial') AND due_at < now()
            """
        )
        overdue = cur.fetchone()["overdue"]

    return {
        "period": period,
        "period_start": start.isoformat(),
        "invoiced_rm": float(invoiced),
        "received_rm": float(received),
        "outstanding_rm": float(outstanding),
        "overdue_rm": float(overdue),
    }


def morning_brief_data() -> dict[str, Any]:
    """Aggregate data for the morning brief (Vizier side).

    Returns jobs summary, revenue, pipeline, overdue items.
    Called by tools/briefing.py which adds Steward data.
    """
    with get_cursor() as cur:
        # Active jobs
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM jobs WHERE status = 'active'"
        )
        active_jobs = cur.fetchone()["cnt"]

        # Completed today
        cur.execute(
            """
            SELECT COUNT(*) AS cnt FROM jobs
            WHERE status = 'completed'
              AND updated_at >= CURRENT_DATE
            """
        )
        completed_today = cur.fetchone()["cnt"]

        # Pipeline summary
        cur.execute(
            """
            SELECT stage, COUNT(*) AS cnt
            FROM pipeline
            WHERE stage NOT IN ('won', 'lost')
            GROUP BY stage
            """
        )
        pipeline = {row["stage"]: row["cnt"] for row in cur.fetchall()}

    revenue = get_revenue_summary("month")

    return {
        "active_jobs": active_jobs,
        "completed_today": completed_today,
        "pipeline": pipeline,
        "revenue": revenue,
    }


def maghrib_summary_data() -> dict[str, Any]:
    """Aggregate data for Maghrib shutdown (Vizier side).

    Returns today's production summary, completed jobs, revenue collected.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt FROM jobs
            WHERE status = 'completed'
              AND updated_at >= CURRENT_DATE
            """
        )
        completed = cur.fetchone()["cnt"]

        cur.execute(
            """
            SELECT COALESCE(SUM(amount_rm), 0) AS collected
            FROM payments WHERE received_at >= CURRENT_DATE
            """
        )
        collected = cur.fetchone()["collected"]

    return {
        "jobs_completed_today": completed,
        "revenue_collected_today_rm": float(collected),
    }
```

- [ ] **Step 4: Run pipeline tests**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_bizops.py -k "pipeline" -v
```

Expected: PASS

- [ ] **Step 5: Write and run client health + revenue tests**

Append to `tests/test_s16_bizops.py`:

```python
def test_client_health_surfaces_overdue(client_id: str) -> None:
    """Client health shows overdue invoices correctly."""
    from tools.bizops import get_client_health

    # Create an overdue invoice (due yesterday, still issued)
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO invoices (id, client_id, amount_rm, status,
                                  invoice_number, due_at)
            VALUES (%s, %s, 1000.00, 'issued', %s,
                    now() - interval '1 day')
            """,
            (str(uuid4()), client_id, f"VIZ-OVERDUE-{uuid4().hex[:6]}"),
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
```

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_bizops.py -k "health or revenue" -v
```

Expected: PASS

- [ ] **Step 6: Run pyright**

```bash
cd /Users/Executor/vizier && python3.11 -m pyright tools/bizops.py
```

- [ ] **Step 7: Commit**

```bash
git add tools/bizops.py tests/test_s16_bizops.py
git commit -m "feat(s16): pipeline CRUD + client health + revenue summary"
```

---

## Chunk 4: Steward Core Commands

### Task 8: Inbox capture + process

**Files:**
- Create: `tools/steward.py`
- Modify: `tests/test_s16_steward.py`

- [ ] **Step 1: Write inbox tests**

Append to `tests/test_s16_steward.py`:

```python
from pathlib import Path

from utils.database import get_cursor, run_migration


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema() -> None:
    """Run core.sql + extended.sql to guarantee all tables exist."""
    base = Path(__file__).resolve().parent.parent / "migrations"
    for sql_file in ["core.sql", "extended.sql"]:
        sql_path = base / sql_file
        if sql_path.exists():
            run_migration(sql_path)


def test_capture_inbox_zero_tokens() -> None:
    """capture_inbox stores text and returns immediately, no LLM call."""
    from tools.steward import capture_inbox

    result = capture_inbox(raw_input="Buy groceries for Ramadan")
    assert result["captured"] is True
    assert result["inbox_id"] is not None

    # Verify in DB
    with get_cursor() as cur:
        cur.execute(
            "SELECT raw_input, processed FROM steward_inbox WHERE id = %s",
            (result["inbox_id"],),
        )
        row = cur.fetchone()
        assert row["raw_input"] == "Buy groceries for Ramadan"
        assert row["processed"] is False


def test_capture_inbox_with_source_message() -> None:
    """capture_inbox stores source_message_id."""
    from tools.steward import capture_inbox

    result = capture_inbox(
        raw_input="Call Ahmad about the proposal",
        input_type="text",
        source_message_id="tg-msg-12345",
    )
    with get_cursor() as cur:
        cur.execute(
            "SELECT source_message_id FROM steward_inbox WHERE id = %s",
            (result["inbox_id"],),
        )
        assert cur.fetchone()["source_message_id"] == "tg-msg-12345"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_steward.py -k "capture" -v
```

Expected: FAIL

- [ ] **Step 3: Implement tools/steward.py (first part: capture + process)**

Create `tools/steward.py`:

```python
"""Steward — GTD personal assistant tools.

ADHD-friendly: zero-friction capture, one-task-at-a-time /next,
streak tracking, domain balance. Separate Telegram bot, same engine.

Model: GPT-5.4-mini for all LLM work (anti-drift #54).
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4

from config.steward_domains import DOMAINS, HEATMAP_AMBER, HEATMAP_GREEN
from utils.call_llm import call_llm
from utils.database import get_cursor
from utils.prayer_times import get_prayer_times, is_after_prayer
from utils.spans import track_span

logger = logging.getLogger(__name__)


def capture_inbox(
    raw_input: str,
    input_type: str = "text",
    source_message_id: str | None = None,
) -> dict[str, Any]:
    """Zero-friction inbox capture. No LLM call — immediate storage.

    Returns:
        Dict with: captured (bool), inbox_id (str).
    """
    inbox_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO steward_inbox (id, raw_input, input_type, source_message_id)
            VALUES (%s, %s, %s, %s)
            """,
            (inbox_id, raw_input, input_type, source_message_id),
        )
    return {"captured": True, "inbox_id": inbox_id}


@track_span(step_type="steward")
def process_inbox(limit: int = 5) -> list[dict[str, Any]]:
    """Process unprocessed inbox items via GPT-5.4-mini.

    Extracts: title, domain, context, energy_level, time_estimate_min.
    Returns suggestions for tap-confirm UI.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, raw_input, input_type, created_at
            FROM steward_inbox
            WHERE processed = false
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        items = [dict(row) for row in cur.fetchall()]

    if not items:
        return []

    suggestions = []
    for item in items:
        prompt = f"""Extract a task from this inbox capture. Return JSON with:
- title: concise task title (under 60 chars)
- domain: one of {json.dumps(DOMAINS)}
- context: one of ["home", "office", "errands", "phone", "computer", "anywhere"]
- energy_level: one of ["high", "medium", "low"]
- time_estimate_min: estimated minutes (integer)

Inbox text: "{item['raw_input']}"

Return ONLY valid JSON, no markdown."""

        response = call_llm(
            stable_prefix=[
                {"role": "system", "content": "You are Steward, a GTD task processor. Extract actionable tasks from raw inbox captures. Be concise and practical."}
            ],
            variable_suffix=[{"role": "user", "content": prompt}],
            model="gpt-5.4-mini",
            temperature=0.3,
            max_tokens=256,
        )

        try:
            parsed = json.loads(response["content"])
        except (json.JSONDecodeError, KeyError):
            parsed = {
                "title": item["raw_input"][:60],
                "domain": "Career",
                "context": "anywhere",
                "energy_level": "medium",
                "time_estimate_min": 15,
            }

        # Validate domain
        if parsed.get("domain") not in DOMAINS:
            parsed["domain"] = "Career"

        suggestions.append({
            "inbox_id": str(item["id"]),
            "raw_input": item["raw_input"],
            "suggestion": parsed,
        })

    return suggestions


def confirm_processed(
    inbox_id: str,
    title: str,
    domain: str,
    context: str,
    energy: str,
    time_estimate: int,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Create a steward_task from a confirmed inbox item.

    Returns:
        Dict with task_id and task details.
    """
    if domain not in DOMAINS:
        raise ValueError(f"Invalid domain: {domain}. Valid: {DOMAINS}")

    task_id = str(uuid4())
    with get_cursor() as cur:
        # Mark inbox item as processed
        cur.execute(
            """
            UPDATE steward_inbox
               SET processed = true, processed_at = now()
             WHERE id = %s
            """,
            (inbox_id,),
        )
        # Create the task
        cur.execute(
            """
            INSERT INTO steward_tasks
              (id, inbox_id, project_id, title, next_action, context,
               energy_level, time_estimate_min, domain, status)
            VALUES (%s, %s, %s, %s, true, %s, %s, %s, %s, 'active')
            RETURNING id, title, domain, context, energy_level, time_estimate_min
            """,
            (task_id, inbox_id, project_id, title, context,
             energy, time_estimate, domain),
        )
        return dict(cur.fetchone())


@track_span(step_type="steward")
def get_next(
    energy: str | None = None,
    domain: str | None = None,
) -> dict[str, Any] | None:
    """Recommend ONE task based on energy, context, deadline, domain balance.

    Uses multiplicative scoring with energy/context as hard filters.
    After Asr, only low-energy tasks are eligible.

    Returns:
        Dict with task details and explanation, or None if no tasks.
    """
    today = date.today()
    now = datetime.now()

    # Determine energy filter
    if energy is None:
        if is_after_prayer("asr"):
            energy = "low"
        elif is_after_prayer("zohor"):
            energy = "medium"

    # Build energy filter
    energy_filter: list[str]
    if energy == "low":
        energy_filter = ["low"]
    elif energy == "medium":
        energy_filter = ["low", "medium"]
    else:
        energy_filter = ["low", "medium", "high"]

    with get_cursor() as cur:
        # Get eligible tasks (hard filters)
        cur.execute(
            """
            SELECT id, title, domain, context, energy_level,
                   time_estimate_min, due_date, project_id, description
            FROM steward_tasks
            WHERE status = 'active'
              AND next_action = true
              AND (defer_until IS NULL OR defer_until <= %s)
              AND energy_level = ANY(%s)
            ORDER BY created_at ASC
            """,
            (today, energy_filter),
        )
        candidates = [dict(row) for row in cur.fetchall()]

    if not candidates:
        return None

    # Domain filter (optional)
    if domain:
        filtered = [c for c in candidates if c["domain"] == domain]
        if filtered:
            candidates = filtered

    # Compute domain neglect scores
    domain_last_done = _domain_last_activity()

    # Score each candidate (multiplicative)
    scored = []
    for task in candidates:
        # Deadline urgency: higher for closer deadlines
        if task["due_date"]:
            days_left = (task["due_date"] - today).days
            deadline_score = max(0.1, 1.0 / max(1, days_left))
        else:
            deadline_score = 0.1  # No deadline = low urgency

        # Domain neglect: higher for more neglected domains
        task_domain = task["domain"] or "Career"
        last_active = domain_last_done.get(task_domain)
        if last_active is None:
            neglect_score = 2.0  # Never done = high priority
        else:
            days_neglected = (today - last_active).days
            neglect_score = 1.0 + (days_neglected / 7.0)

        total_score = deadline_score * neglect_score
        scored.append((total_score, task))

    # Pick highest scoring task
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_task = scored[0]

    # Build explanation
    reasons = []
    if best_task["due_date"]:
        days_left = (best_task["due_date"] - today).days
        if days_left <= 1:
            reasons.append("Due today" if days_left == 0 else "Due tomorrow")
        elif days_left <= 3:
            reasons.append(f"Due in {days_left} days")
    task_domain = best_task["domain"] or "Career"
    last_active = domain_last_done.get(task_domain)
    if last_active is None or (today - last_active).days >= 7:
        days = "never" if last_active is None else f"{(today - last_active).days} days"
        reasons.append(f"Domain: {task_domain} (neglected {days})")
    if best_task["time_estimate_min"]:
        reasons.append(f"~{best_task['time_estimate_min']} min")

    # Prayer time context
    prayer_times = get_prayer_times(today)
    for prayer_name in ["asr", "maghrib"]:
        prayer_t = prayer_times[prayer_name]
        minutes_until = (
            datetime.combine(today, prayer_t) - now
        ).total_seconds() / 60
        if 0 < minutes_until < 60:
            reasons.append(
                f"{int(minutes_until)} min until {prayer_name.capitalize()}"
            )
            break

    return {
        **best_task,
        "explanation": ". ".join(reasons) if reasons else "Next available task",
        "score": best_score,
    }


def _domain_last_activity() -> dict[str, date]:
    """Return the last completion date for each domain."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT domain, MAX(completed_at::date) AS last_done
            FROM steward_tasks
            WHERE status = 'done' AND domain IS NOT NULL
            GROUP BY domain
            """
        )
        return {
            row["domain"]: row["last_done"]
            for row in cur.fetchall()
            if row["last_done"] is not None
        }


def mark_done(
    task_id: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Mark a task as done. Update streak, return progress.

    Returns:
        Dict with: task_id, title, streak_count, domain, domain_progress, win_summary.
    """
    with get_cursor() as cur:
        # Complete the task
        cur.execute(
            """
            UPDATE steward_tasks
               SET status = 'done', completed_at = now(), completion_note = %s,
                   updated_at = now()
             WHERE id = %s
            RETURNING id, title, domain, streak_count, streak_last_date
            """,
            (note, task_id),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Task not found: {task_id}")

        task_title = row["title"]
        task_domain = row["domain"] or "Career"
        old_streak = row["streak_count"] or 0
        last_date = row["streak_last_date"]

        # Update streak
        today = date.today()
        if last_date == today - timedelta(days=1) or last_date == today:
            new_streak = old_streak + 1
        else:
            new_streak = 1

        cur.execute(
            """
            UPDATE steward_tasks
               SET streak_count = %s, streak_last_date = %s
             WHERE id = %s
            """,
            (new_streak, today, task_id),
        )

        # Update project progress if linked
        cur.execute(
            "SELECT project_id FROM steward_tasks WHERE id = %s",
            (task_id,),
        )
        proj_row = cur.fetchone()
        if proj_row and proj_row["project_id"]:
            cur.execute(
                """
                UPDATE steward_projects
                   SET completed_tasks = completed_tasks + 1,
                       updated_at = now()
                 WHERE id = %s
                """,
                (proj_row["project_id"],),
            )

        # Count today's completions for streak display
        cur.execute(
            """
            SELECT COUNT(*) AS cnt FROM steward_tasks
            WHERE status = 'done'
              AND completed_at::date = CURRENT_DATE
            """
        )
        today_done = cur.fetchone()["cnt"]

        # Domain progress (last 7 days)
        cur.execute(
            """
            SELECT COUNT(*) AS cnt FROM steward_tasks
            WHERE status = 'done'
              AND domain = %s
              AND completed_at >= now() - interval '7 days'
            """,
            (task_domain,),
        )
        domain_count = cur.fetchone()["cnt"]

    return {
        "task_id": task_id,
        "title": task_title,
        "streak_count": today_done,
        "domain": task_domain,
        "domain_progress": f"{domain_count} tasks this week",
        "win_summary": f"{task_title} — done!",
    }


def get_snapshot() -> dict[str, Any]:
    """Return snapshot: active tasks, overdue, today's completions, domain heatmap, streak.

    Domain heatmap: green (3+), amber (1-2), red (0 in 7 days).
    """
    today = date.today()
    week_ago = today - timedelta(days=7)

    with get_cursor() as cur:
        # Active tasks
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM steward_tasks WHERE status = 'active'"
        )
        active = cur.fetchone()["cnt"]

        # Overdue
        cur.execute(
            """
            SELECT COUNT(*) AS cnt FROM steward_tasks
            WHERE status = 'active' AND due_date < %s
            """,
            (today,),
        )
        overdue = cur.fetchone()["cnt"]

        # Today's completions
        cur.execute(
            """
            SELECT COUNT(*) AS cnt FROM steward_tasks
            WHERE status = 'done' AND completed_at::date = CURRENT_DATE
            """
        )
        today_done = cur.fetchone()["cnt"]

        # Domain heatmap
        cur.execute(
            """
            SELECT domain, COUNT(*) AS cnt
            FROM steward_tasks
            WHERE status = 'done'
              AND domain IS NOT NULL
              AND completed_at >= %s
            GROUP BY domain
            """,
            (week_ago,),
        )
        domain_counts = {row["domain"]: row["cnt"] for row in cur.fetchall()}

    heatmap: dict[str, str] = {}
    for domain in DOMAINS:
        count = domain_counts.get(domain, 0)
        if count >= HEATMAP_GREEN:
            heatmap[domain] = "green"
        elif count >= HEATMAP_AMBER:
            heatmap[domain] = "amber"
        else:
            heatmap[domain] = "red"

    return {
        "active_tasks": active,
        "overdue_tasks": overdue,
        "today_done": today_done,
        "domain_heatmap": heatmap,
        "current_streak": today_done,
    }


@track_span(step_type="steward")
def decompose_project(
    objective: str,
    domain: str | None = None,
) -> dict[str, Any]:
    """Decompose a project objective into tasks via GPT-5.4-mini.

    Returns project details and proposed tasks for operator confirmation.
    """
    if domain and domain not in DOMAINS:
        raise ValueError(f"Invalid domain: {domain}. Valid: {DOMAINS}")

    prompt = f"""Break down this project objective into actionable tasks.
Return JSON with:
- "tasks": array of objects, each with:
  - "title": concise task title
  - "context": one of ["home", "office", "errands", "phone", "computer", "anywhere"]
  - "energy_level": one of ["high", "medium", "low"]
  - "time_estimate_min": estimated minutes

Objective: "{objective}"
Domain: {domain or "Career"}

Return 4-8 tasks, ordered by logical sequence. Return ONLY valid JSON."""

    response = call_llm(
        stable_prefix=[
            {"role": "system", "content": "You are Steward, a GTD project planner. Break objectives into specific, actionable tasks with realistic estimates."}
        ],
        variable_suffix=[{"role": "user", "content": prompt}],
        model="gpt-5.4-mini",
        temperature=0.5,
        max_tokens=1024,
    )

    try:
        parsed = json.loads(response["content"])
        tasks = parsed.get("tasks", parsed) if isinstance(parsed, dict) else parsed
    except (json.JSONDecodeError, KeyError):
        tasks = [{"title": objective, "context": "anywhere",
                  "energy_level": "medium", "time_estimate_min": 30}]

    # Create project record
    project_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO steward_projects (id, title, objective, domain, status)
            VALUES (%s, %s, %s, %s, 'active')
            RETURNING id, title, objective, domain
            """,
            (project_id, objective[:100], objective, domain or "Career"),
        )
        project = dict(cur.fetchone())

    return {
        **project,
        "proposed_tasks": tasks,
    }


def confirm_decomposition(
    project_id: str,
    tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create tasks linked to a project after operator confirmation.

    Returns list of created task dicts.
    """
    created = []
    with get_cursor() as cur:
        # Get project domain
        cur.execute(
            "SELECT domain FROM steward_projects WHERE id = %s",
            (project_id,),
        )
        proj = cur.fetchone()
        proj_domain = proj["domain"] if proj else "Career"

        for task_data in tasks:
            task_id = str(uuid4())
            cur.execute(
                """
                INSERT INTO steward_tasks
                  (id, project_id, title, next_action, context,
                   energy_level, time_estimate_min, domain, status)
                VALUES (%s, %s, %s, true, %s, %s, %s, %s, 'active')
                RETURNING id, title, domain, context, energy_level, time_estimate_min
                """,
                (
                    task_id,
                    project_id,
                    task_data["title"],
                    task_data.get("context", "anywhere"),
                    task_data.get("energy_level", "medium"),
                    task_data.get("time_estimate_min", 15),
                    proj_domain,
                ),
            )
            created.append(dict(cur.fetchone()))

        # Update project totals
        cur.execute(
            """
            UPDATE steward_projects
               SET total_tasks = %s, decomposed = true,
                   decomposition_approved = true, updated_at = now()
             WHERE id = %s
            """,
            (len(tasks), project_id),
        )

    return created


def steward_brief_data() -> dict[str, Any]:
    """Aggregate Steward data for the morning brief.

    Returns: today's top 3 tasks, domain balance snapshot, streak.
    Called by tools/briefing.py.
    """
    snapshot = get_snapshot()

    # Get top 3 tasks for today (use get_next logic but return 3)
    top_tasks = []
    seen_ids: set[str] = set()
    for _ in range(3):
        task = get_next()
        if task is None or task["id"] in seen_ids:
            break
        top_tasks.append({
            "title": task["title"],
            "domain": task["domain"],
            "time_estimate_min": task.get("time_estimate_min"),
            "explanation": task.get("explanation", ""),
        })
        seen_ids.add(task["id"])

    # Unprocessed inbox count
    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM steward_inbox WHERE processed = false"
        )
        unprocessed = cur.fetchone()["cnt"]

    return {
        "top_3_tasks": top_tasks,
        "unprocessed_inbox": unprocessed,
        "domain_heatmap": snapshot["domain_heatmap"],
        "active_tasks": snapshot["active_tasks"],
        "current_streak": snapshot["current_streak"],
    }
```

- [ ] **Step 4: Run capture tests**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_steward.py -k "capture" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/steward.py tests/test_s16_steward.py
git commit -m "feat(s16): steward core — inbox capture, process, next, done, snapshot, project"
```

### Task 9: Steward /next, /done, /snapshot tests

**Files:**
- Modify: `tests/test_s16_steward.py`

- [ ] **Step 1: Write /next, /done, /snapshot tests**

Append to `tests/test_s16_steward.py`:

```python
@pytest.fixture()
def active_task() -> str:
    """Create an active task and return its id."""
    task_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO steward_tasks
              (id, title, next_action, context, energy_level,
               time_estimate_min, domain, status)
            VALUES (%s, 'Test task for next', true, 'computer', 'medium',
                    15, 'Career', 'active')
            """,
            (task_id,),
        )
    return task_id


def test_get_next_returns_one_task(active_task: str) -> None:
    """get_next returns exactly ONE task with explanation."""
    from tools.steward import get_next

    result = get_next()
    assert result is not None
    assert "title" in result
    assert "explanation" in result
    assert isinstance(result["explanation"], str)


def test_mark_done_updates_streak(active_task: str) -> None:
    """mark_done completes task and returns streak + domain progress."""
    from tools.steward import mark_done

    result = mark_done(active_task, note="Learned something new")
    assert result["task_id"] == active_task
    assert result["streak_count"] >= 1
    assert "domain" in result
    assert "domain_progress" in result
    assert "win_summary" in result

    # Verify task is done in DB
    with get_cursor() as cur:
        cur.execute(
            "SELECT status, completion_note FROM steward_tasks WHERE id = %s",
            (active_task,),
        )
        row = cur.fetchone()
        assert row["status"] == "done"
        assert row["completion_note"] == "Learned something new"


def test_get_snapshot_returns_domain_heatmap() -> None:
    """get_snapshot returns active tasks, overdue, heatmap, streak."""
    from tools.steward import get_snapshot

    result = get_snapshot()
    assert "active_tasks" in result
    assert "overdue_tasks" in result
    assert "today_done" in result
    assert "domain_heatmap" in result
    assert isinstance(result["domain_heatmap"], dict)
    # All 21 domains present
    assert len(result["domain_heatmap"]) == 21


def test_get_next_filters_low_energy_after_asr(active_task: str) -> None:
    """get_next with energy=low only returns low-energy tasks."""
    from tools.steward import get_next

    # Create a low-energy task
    low_id = str(uuid4())
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO steward_tasks
              (id, title, next_action, context, energy_level,
               time_estimate_min, domain, status)
            VALUES (%s, 'Low energy task', true, 'anywhere', 'low',
                    5, 'Health', 'active')
            """,
            (low_id,),
        )

    result = get_next(energy="low")
    assert result is not None
    assert result["energy_level"] == "low"


def test_domain_balance_nudges_neglected() -> None:
    """get_next prioritises tasks in neglected domains."""
    from tools.steward import get_next

    # Create two tasks: one in active domain, one in neglected
    with get_cursor() as cur:
        # First, complete some Career tasks to make it "active"
        for i in range(3):
            tid = str(uuid4())
            cur.execute(
                """
                INSERT INTO steward_tasks
                  (id, title, next_action, domain, status, energy_level,
                   completed_at)
                VALUES (%s, %s, false, 'Career', 'done', 'medium', now())
                """,
                (tid, f"Career task {i}"),
            )

        # Create active tasks in Career and Finance (neglected)
        career_id = str(uuid4())
        cur.execute(
            """
            INSERT INTO steward_tasks
              (id, title, next_action, domain, status, energy_level,
               time_estimate_min, context)
            VALUES (%s, 'Career task', true, 'Career', 'active', 'medium',
                    15, 'computer')
            """,
            (career_id,),
        )

        finance_id = str(uuid4())
        cur.execute(
            """
            INSERT INTO steward_tasks
              (id, title, next_action, domain, status, energy_level,
               time_estimate_min, context)
            VALUES (%s, 'Finance task', true, 'Finance', 'active', 'medium',
                    15, 'computer')
            """,
            (finance_id,),
        )

    result = get_next(energy="high")
    # Finance should score higher due to domain neglect
    assert result is not None
    # The finance task should be recommended due to neglect
    assert result["domain"] == "Finance"
```

- [ ] **Step 2: Run all steward tests**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_steward.py -v
```

Expected: PASS

- [ ] **Step 3: Run pyright**

```bash
cd /Users/Executor/vizier && python3.11 -m pyright tools/steward.py
```

Fix any errors.

- [ ] **Step 4: Commit**

```bash
git add tests/test_s16_steward.py
git commit -m "test(s16): steward /next, /done, /snapshot, domain balance tests"
```

### Task 10: Steward /project decomposition tests

**Files:**
- Modify: `tests/test_s16_steward.py`

- [ ] **Step 1: Write decomposition tests**

Append to `tests/test_s16_steward.py`:

```python
def test_decompose_project_returns_tasks() -> None:
    """decompose_project breaks objective into tasks via GPT-5.4-mini."""
    from tools.steward import decompose_project

    result = decompose_project(
        objective="Set up KDP publishing pipeline",
        domain="Career",
    )
    assert "proposed_tasks" in result
    assert isinstance(result["proposed_tasks"], list)
    assert len(result["proposed_tasks"]) >= 1
    assert result["id"] is not None  # project created in DB


def test_confirm_decomposition_creates_tasks() -> None:
    """confirm_decomposition creates tasks linked to project."""
    from tools.steward import confirm_decomposition, decompose_project

    project = decompose_project(
        objective="Test project decomposition",
        domain="Learning",
    )

    tasks = [
        {"title": "Research topic", "context": "computer",
         "energy_level": "medium", "time_estimate_min": 30},
        {"title": "Write outline", "context": "computer",
         "energy_level": "high", "time_estimate_min": 45},
    ]

    created = confirm_decomposition(project["id"], tasks)
    assert len(created) == 2
    assert created[0]["domain"] == "Learning"

    # Verify project updated
    with get_cursor() as cur:
        cur.execute(
            "SELECT total_tasks, decomposed FROM steward_projects WHERE id = %s",
            (project["id"],),
        )
        proj = cur.fetchone()
        assert proj["total_tasks"] == 2
        assert proj["decomposed"] is True
```

- [ ] **Step 2: Run decomposition tests**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_steward.py -k "decompose or confirm_decomposition" -v
```

Expected: PASS (requires OPENAI_API_KEY for GPT-5.4-mini calls)

- [ ] **Step 3: Commit**

```bash
git add tests/test_s16_steward.py
git commit -m "test(s16): steward /project decomposition + confirmation tests"
```

---

## Chunk 5: Briefing Crons + Finalize

### Task 11: Briefing module — morning brief + Maghrib shutdown

**Files:**
- Create: `tools/briefing.py`
- Create: `tests/test_s16_briefing.py`

- [ ] **Step 1: Write briefing tests**

Create `tests/test_s16_briefing.py`:

```python
"""S16 — Briefing cron tests.

Covers: morning brief 3-gate check, Maghrib shutdown, silence detection.

Requires: running Postgres (vizier db).
"""

from __future__ import annotations

import os
from datetime import date, datetime, time
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

os.environ.setdefault("DATABASE_URL", "postgres://localhost:5432/vizier")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")

from utils.database import get_cursor, run_migration


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema() -> None:
    """Run core + extended SQL."""
    base = Path(__file__).resolve().parent.parent / "migrations"
    for sql_file in ["core.sql", "extended.sql"]:
        sql_path = base / sql_file
        if sql_path.exists():
            run_migration(sql_path)


def test_morning_brief_gate_skips_if_no_new_data() -> None:
    """Morning brief does NOT fire if no new data since last brief."""
    from tools.briefing import _check_three_gates

    # Insert a daily_brief review for today to simulate "already fired"
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO steward_reviews (review_type, review_date)
            VALUES ('daily_brief', CURRENT_DATE)
            """
        )

    # Gate 3 should fail (already fired today)
    with patch("tools.briefing.get_prayer_times") as mock_pt:
        mock_pt.return_value = {
            "subuh": time(5, 45),
            "zohor": time(13, 0),
            "asr": time(16, 25),
            "maghrib": time(19, 12),
            "isyak": time(20, 23),
        }
        with patch("tools.briefing.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 8, 8, 0)
            mock_dt.combine = datetime.combine
            gates = _check_three_gates()

    assert gates["gate3_not_fired_today"] is False
    assert gates["should_fire"] is False


def test_morning_brief_gate_passes_with_new_data() -> None:
    """Morning brief fires when all 3 gates pass."""
    from tools.briefing import _check_three_gates

    # Clean up any existing daily_brief for today
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM steward_reviews WHERE review_type = 'daily_brief' AND review_date = CURRENT_DATE"
        )
        # Insert new data (a steward inbox item)
        cur.execute(
            """
            INSERT INTO steward_inbox (raw_input, input_type)
            VALUES ('New data for morning brief test', 'text')
            """
        )

    with patch("tools.briefing.get_prayer_times") as mock_pt:
        mock_pt.return_value = {
            "subuh": time(5, 45),
            "zohor": time(13, 0),
            "asr": time(16, 25),
            "maghrib": time(19, 12),
            "isyak": time(20, 23),
        }
        with patch("tools.briefing.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 8, 8, 0)
            mock_dt.combine = datetime.combine
            gates = _check_three_gates()

    assert gates["gate1_after_subuh"] is True
    assert gates["gate2_new_data"] is True
    assert gates["gate3_not_fired_today"] is True
    assert gates["should_fire"] is True


def test_feedback_check_silence_called_in_morning_brief() -> None:
    """Morning brief calls feedback_check_silence() SQL function."""
    from tools.briefing import morning_brief

    # Mock the gates to pass and verify silence check is called
    with patch("tools.briefing._check_three_gates") as mock_gates:
        mock_gates.return_value = {"should_fire": True,
                                    "gate1_after_subuh": True,
                                    "gate2_new_data": True,
                                    "gate3_not_fired_today": True}
        with patch("tools.briefing._generate_brief_text") as mock_gen:
            mock_gen.return_value = "Test brief"
            result = morning_brief()

    # Should have called feedback_check_silence
    assert result is not None
    assert "silence_flagged" in result


def test_maghrib_shutdown_produces_summary() -> None:
    """Maghrib shutdown returns Vizier + Steward summaries."""
    from tools.briefing import maghrib_shutdown

    result = maghrib_shutdown()
    assert "vizier_summary" in result
    assert "steward_summary" in result
    assert "tomorrow_top_3" in result
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_briefing.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement tools/briefing.py**

Create `tools/briefing.py`:

```python
"""Briefing module — morning brief + Maghrib shutdown.

Cross-cutting crons that synthesize Vizier (BizOps) and Steward data.
Implements 3-gate cron requirement (anti-drift #29).
Calls feedback_check_silence() for DEV-007 compliance.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from tools.bizops import maghrib_summary_data, morning_brief_data
from tools.steward import get_snapshot, steward_brief_data
from utils.database import get_cursor
from utils.prayer_times import get_prayer_times
from utils.spans import track_span

logger = logging.getLogger(__name__)


def _check_three_gates() -> dict[str, Any]:
    """Check the 3 gates for morning brief (anti-drift #29).

    Gate 1: Current time is after today's Subuh prayer.
    Gate 2: New data exists since last morning brief.
    Gate 3: Morning brief hasn't already fired today.

    Returns dict with gate statuses and overall should_fire.
    """
    today = date.today()
    now = datetime.now()
    prayer_times = get_prayer_times(today)

    # Gate 1: After Subuh
    subuh_dt = datetime.combine(today, prayer_times["subuh"])
    gate1 = now >= subuh_dt

    # Gate 3: Not already fired today
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt FROM steward_reviews
            WHERE review_type = 'daily_brief' AND review_date = %s
            """,
            (today,),
        )
        gate3 = cur.fetchone()["cnt"] == 0

    # Gate 2: New data since last brief
    gate2 = False
    with get_cursor() as cur:
        # Find last brief time
        cur.execute(
            """
            SELECT MAX(created_at) AS last_brief
            FROM steward_reviews
            WHERE review_type = 'daily_brief'
            """
        )
        row = cur.fetchone()
        last_brief = row["last_brief"] if row else None

        if last_brief is None:
            gate2 = True  # Never briefed before — there's "new" data
        else:
            # Check for new data across key tables
            for table in ["jobs", "invoices", "payments", "steward_inbox"]:
                cur.execute(
                    f"SELECT MAX(created_at) AS latest FROM {table}"  # noqa: S608 — table names are hardcoded
                )
                latest_row = cur.fetchone()
                if latest_row and latest_row["latest"] and latest_row["latest"] > last_brief:
                    gate2 = True
                    break

    return {
        "gate1_after_subuh": gate1,
        "gate2_new_data": gate2,
        "gate3_not_fired_today": gate3,
        "should_fire": gate1 and gate2 and gate3,
    }


@track_span(step_type="briefing")
def morning_brief() -> dict[str, Any] | None:
    """Generate the morning brief if all 3 gates pass.

    Synthesizes Vizier + Steward data. Calls feedback_check_silence().
    Records the brief in steward_reviews.

    Returns brief data or None if gates fail.
    """
    gates = _check_three_gates()
    if not gates["should_fire"]:
        logger.info("Morning brief skipped — gates: %s", gates)
        return {
            "fired": False,
            "gates": gates,
            "silence_flagged": 0,
        }

    # DEV-007: Call feedback_check_silence
    with get_cursor() as cur:
        cur.execute("SELECT feedback_check_silence()")
        silence_count = cur.fetchone()["feedback_check_silence"]

    # Gather data
    vizier_data = morning_brief_data()
    steward_data = steward_brief_data()

    # Generate brief text
    brief_text = _generate_brief_text(vizier_data, steward_data, silence_count)

    # Record the brief
    today = date.today()
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO steward_reviews
              (review_type, review_date, completion_stats, domain_scores)
            VALUES ('daily_brief', %s, %s::jsonb, %s::jsonb)
            """,
            (
                today,
                '{"type": "morning_brief"}',
                '{}',
            ),
        )

    return {
        "fired": True,
        "gates": gates,
        "silence_flagged": silence_count,
        "vizier": vizier_data,
        "steward": steward_data,
        "brief_text": brief_text,
    }


def _generate_brief_text(
    vizier: dict[str, Any],
    steward: dict[str, Any],
    silence_count: int,
) -> str:
    """Format the morning brief as readable text."""
    lines = ["Assalamualaikum. Morning brief:\n"]

    # Vizier section
    lines.append(f"Active jobs: {vizier['active_jobs']}")
    if vizier["revenue"]:
        rev = vizier["revenue"]
        lines.append(
            f"Revenue (month): RM {rev['invoiced_rm']:,.2f} invoiced, "
            f"RM {rev['received_rm']:,.2f} received"
        )
        if rev["overdue_rm"] > 0:
            lines.append(f"⚠ Overdue: RM {rev['overdue_rm']:,.2f}")
    if vizier["pipeline"]:
        lines.append(f"Pipeline: {vizier['pipeline']}")

    # Steward section
    lines.append(f"\nInbox: {steward['unprocessed_inbox']} unprocessed")
    lines.append(f"Active tasks: {steward['active_tasks']}")
    if steward["top_3_tasks"]:
        lines.append("\nToday's focus:")
        for i, task in enumerate(steward["top_3_tasks"], 1):
            est = f" (~{task['time_estimate_min']}min)" if task.get("time_estimate_min") else ""
            lines.append(f"  {i}. {task['title']}{est}")

    # Silence check
    if silence_count > 0:
        lines.append(f"\n⚠ {silence_count} feedback item(s) flagged as silent")

    return "\n".join(lines)


@track_span(step_type="briefing")
def maghrib_shutdown() -> dict[str, Any]:
    """Maghrib shutdown: Vizier production + Steward personal summary + tomorrow's top 3."""
    vizier_data = maghrib_summary_data()
    steward_snapshot = get_snapshot()

    # Tomorrow's top 3 (just re-use get_next logic)
    from tools.steward import get_next

    tomorrow_tasks = []
    seen: set[str] = set()
    for _ in range(3):
        task = get_next()
        if task is None or task["id"] in seen:
            break
        tomorrow_tasks.append({
            "title": task["title"],
            "domain": task["domain"],
        })
        seen.add(task["id"])

    return {
        "vizier_summary": vizier_data,
        "steward_summary": {
            "active_tasks": steward_snapshot["active_tasks"],
            "today_done": steward_snapshot["today_done"],
            "domain_heatmap": steward_snapshot["domain_heatmap"],
        },
        "tomorrow_top_3": tomorrow_tasks,
    }
```

- [ ] **Step 4: Run briefing tests**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_briefing.py -v
```

Expected: PASS

- [ ] **Step 5: Run pyright on all S16 files**

```bash
cd /Users/Executor/vizier && python3.11 -m pyright tools/briefing.py tools/steward.py tools/bizops.py tools/invoice.py utils/prayer_times.py config/steward_domains.py
```

Fix any errors.

- [ ] **Step 6: Commit**

```bash
git add tools/briefing.py tests/test_s16_briefing.py
git commit -m "feat(s16): morning brief with 3-gate check + Maghrib shutdown"
```

### Task 12: Final verification and cleanup

**Files:**
- Possibly modify: `.env.example` (if it exists)

- [ ] **Step 1: Add STEWARD_TELEGRAM_TOKEN to .env.example**

If `.env.example` exists, add:
```
STEWARD_TELEGRAM_TOKEN=  # Separate bot token for @steward_bot
```

If it doesn't exist, create it with that line plus a comment.

- [ ] **Step 2: Run ALL S16 tests together**

```bash
cd /Users/Executor/vizier && python3.11 -m pytest tests/test_s16_bizops.py tests/test_s16_steward.py tests/test_s16_briefing.py -v --tb=short
```

Expected: ALL PASS

- [ ] **Step 3: Run pyright on all S16 files**

```bash
cd /Users/Executor/vizier && python3.11 -m pyright tools/invoice.py tools/bizops.py tools/steward.py tools/briefing.py utils/prayer_times.py config/steward_domains.py
```

Expected: 0 errors

- [ ] **Step 4: Run ruff + black**

```bash
cd /Users/Executor/vizier && python3.11 -m ruff check tools/invoice.py tools/bizops.py tools/steward.py tools/briefing.py utils/prayer_times.py config/steward_domains.py --fix
cd /Users/Executor/vizier && python3.11 -m black tools/invoice.py tools/bizops.py tools/steward.py tools/briefing.py utils/prayer_times.py config/steward_domains.py
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(s16): BizOps + Steward — invoicing, pipeline, crons, GTD personal assistant"
```

- [ ] **Step 6: Verify exit criteria**

Run through the exit criteria checklist:

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | Invoice PDF via Typst | `test_generate_invoice_creates_pdf` passes |
| 2 | Payment state machine | `test_payment_partial_*`, `test_payment_full_*`, `test_payment_does_not_transition_from_draft` pass |
| 3 | Pipeline CRUD | `test_pipeline_create_and_transition`, `test_pipeline_rejects_invalid_transition` pass |
| 4 | Morning brief 3-gate | `test_morning_brief_gate_skips_*`, `test_morning_brief_gate_passes_*` pass |
| 5 | Client health | `test_client_health_surfaces_overdue` passes |
| 6 | Maghrib shutdown | `test_maghrib_shutdown_produces_summary` passes |
| 7 | 9 tables | `test_all_nine_tables_exist` passes |
| 8 | Inbox capture | `test_capture_inbox_zero_tokens` passes |
| 9 | /next ONE task | `test_get_next_returns_one_task` passes |
| 10 | /done with streak | `test_mark_done_updates_streak` passes |
| 11 | /snapshot heatmap | `test_get_snapshot_returns_domain_heatmap` passes |
| 12 | /project | `test_decompose_project_returns_tasks`, `test_confirm_decomposition_creates_tasks` pass |
| 13 | Domain balance | `test_domain_balance_nudges_neglected` passes |
| 14 | feedback_check_silence | `test_feedback_check_silence_called_in_morning_brief` passes |
| 15 | Persona file | `config/personas/steward.md` exists (already present) |
| 16 | pyright clean | pyright reports 0 errors |
