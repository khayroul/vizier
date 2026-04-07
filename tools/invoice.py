"""Invoice generation tool for Vizier BizOps.

Generates professional PDF invoices via programmatic Typst source generation.
Stores invoice records in Postgres, PDFs in MinIO (anti-drift #7).
"""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timedelta
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
        row = cur.fetchone()
        assert row is not None
        seq = row["nextval"]
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
    billing: dict[str, Any] = (
        client_row.get("billing_config") or {} if client_row else {}
    )

    # Generate Typst source and compile
    if output_dir is None:
        import tempfile

        output_dir = Path(tempfile.mkdtemp())

    pdf_path = _render_invoice_typst(
        invoice_number=invoice_number,
        client_name=client_name,
        billing=billing,
        line_items=line_items,
        tax_rate=tax_rate,
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
            VALUES (%s, %s, %s::uuid[], %s, %s, %s, %s, %s, 'draft')
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
    tax_rate: float,
    output_dir: Path,
) -> Path:
    """Generate a Typst source file programmatically and compile to PDF.

    Writes line items directly into Typst source rather than using
    sys.inputs (which only supports string values, not arrays).
    """
    tax_label = f"SST ({tax_rate * 100:.0f}%)" if tax_rate > 0 else "Tax"

    # Build Typst line items array
    items_typst = ",\n    ".join(
        f'(desc: "{_escape_typst(item["description"])}", '
        f'qty: {item["qty"]}, rate: {item["rate"]:.2f})'
        for item in line_items
    )

    invoice_date = datetime.now().strftime("%-d %B %Y")
    due_date = (datetime.now() + timedelta(days=14)).strftime("%-d %B %Y")

    # Client details from billing_config
    client_ssm = billing.get("ssm", "")
    client_address = billing.get("address", "")
    client_attn = billing.get("contact_person", "")

    typst_source = _INVOICE_TEMPLATE.format(
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        due_date=due_date,
        client_name=_escape_typst(client_name),
        client_ssm=_escape_typst(client_ssm),
        client_address=_escape_typst(client_address),
        client_attn=_escape_typst(client_attn),
        tax_label=tax_label,
        tax_rate=tax_rate,
        items_typst=items_typst,
    )

    typ_path = output_dir / f"{invoice_number}.typ"
    typ_path.write_text(typst_source, encoding="utf-8")

    pdf_path = output_dir / f"{invoice_number}.pdf"
    env = {**os.environ, "TYPST_FONT_PATHS": str(_FONT_PATH)}
    result = subprocess.run(
        ["typst", "compile", str(typ_path), str(pdf_path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        logger.error("Typst compile failed: %s", result.stderr)
        raise RuntimeError(f"Typst compile failed: {result.stderr}")

    return pdf_path


def _escape_typst(text: str) -> str:
    """Escape special characters for Typst string literals."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


# Typst template with Python format placeholders for dynamic content.
# Double braces {{ }} escape literal braces for Typst syntax.
_INVOICE_TEMPLATE = """// Auto-generated invoice — {invoice_number}
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
"""
