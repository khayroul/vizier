// ─────────────────────────────────────────────────────────────────────────────
// invoice.typ — Malaysian business invoice template
// Vizier — Typst 0.14.2, no external packages
//
// Features: SSM registration, bank details, itemised lines, tax, payment terms
// ─────────────────────────────────────────────────────────────────────────────

// ── Brand inputs ─────────────────────────────────────────────────────────────
#let primary      = rgb(sys.inputs.at("primary_color",   default: "#1A1A2E"))
#let secondary    = rgb(sys.inputs.at("secondary_color", default: "#F8F9FA"))
#let accent       = rgb(sys.inputs.at("accent_color",    default: "#2563EB"))
#let heading-font = sys.inputs.at("headline_font", default: "Inter")
#let body-font    = sys.inputs.at("body_font",     default: "Inter")

// ── Company details ──────────────────────────────────────────────────────────
#let company-name    = sys.inputs.at("company_name",  default: "Vizier Digital Sdn Bhd")
#let company-ssm     = sys.inputs.at("ssm_number",    default: "202401012345 (1234567-A)")
#let company-address = sys.inputs.at("company_address", default: "Level 10, Menara Example\nJalan Ampang, 50450 Kuala Lumpur")
#let company-phone   = sys.inputs.at("phone",         default: "+60 3-1234 5678")
#let company-email   = sys.inputs.at("email",         default: "billing@vizier.com.my")

// ── Invoice details ──────────────────────────────────────────────────────────
#let invoice-number = sys.inputs.at("invoice_number", default: "INV-2026-0042")
#let invoice-date   = sys.inputs.at("invoice_date",   default: "7 April 2026")
#let due-date       = sys.inputs.at("due_date",       default: "21 April 2026")

// ── Client details ───────────────────────────────────────────────────────────
#let client-name    = sys.inputs.at("client_name",    default: "Restoran Warisan Sdn Bhd")
#let client-ssm     = sys.inputs.at("client_ssm",     default: "201901054321 (7654321-B)")
#let client-address = sys.inputs.at("client_address", default: "No. 12, Jalan Masjid India\n50100 Kuala Lumpur")
#let client-attn    = sys.inputs.at("client_attn",    default: "Encik Ahmad bin Razak")

// ── Bank details ─────────────────────────────────────────────────────────────
#let bank-name    = sys.inputs.at("bank_name",    default: "Maybank")
#let bank-account = sys.inputs.at("bank_account", default: "5123 4567 8901")
#let bank-swift   = sys.inputs.at("bank_swift",   default: "MBBEMYKL")

// ── Tax rate ─────────────────────────────────────────────────────────────────
#let tax-label = sys.inputs.at("tax_label", default: "SST (6%)")
#let tax-rate  = 0.06

// ── Page setup ───────────────────────────────────────────────────────────────
#set page(
  paper: "a4",
  margin: (top: 2cm, bottom: 2.5cm, left: 2cm, right: 2cm),
  footer: context [
    #line(length: 100%, stroke: 0.3pt + luma(200))
    #v(0.3em)
    #set text(size: 7.5pt, fill: luma(120))
    #grid(
      columns: (1fr, 1fr),
      align: (left, right),
      [#company-name · SSM #company-ssm],
      [Page #counter(page).display("1")],
    )
  ],
)

#set text(font: body-font, size: 10pt, fill: luma(30))
#set par(leading: 0.6em, spacing: 1em)

// ═════════════════════════════════════════════════════════════════════════════
// HEADER
// ═════════════════════════════════════════════════════════════════════════════

#grid(
  columns: (1fr, auto),
  align: (left, right),
  // Company info
  [
    #text(font: heading-font, size: 18pt, weight: "bold", fill: primary)[#company-name]
    #v(0.2em)
    #text(size: 8.5pt, fill: luma(80))[SSM: #company-ssm]
    #v(0.1em)
    #text(size: 8.5pt, fill: luma(80))[#company-address]
    #v(0.1em)
    #text(size: 8.5pt, fill: luma(80))[#company-phone · #company-email]
  ],
  // Invoice label
  [
    #text(font: heading-font, size: 28pt, weight: "bold", fill: accent)[INVOICE]
  ],
)

#v(0.8em)
#line(length: 100%, stroke: 1.5pt + primary)
#v(0.8em)

// ═════════════════════════════════════════════════════════════════════════════
// INVOICE META + CLIENT
// ═════════════════════════════════════════════════════════════════════════════

#grid(
  columns: (1fr, 1fr),
  column-gutter: 2cm,
  // Bill to
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
  // Invoice details
  [
    #align(right)[
      #grid(
        columns: (auto, auto),
        column-gutter: 12pt,
        row-gutter: 6pt,
        align: (right, left),
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

// ═════════════════════════════════════════════════════════════════════════════
// LINE ITEMS
// ═════════════════════════════════════════════════════════════════════════════

// Sample data — in production, injected via sys.inputs or content
#let items = (
  (desc: "Content Strategy & Planning — April 2026", qty: 1, rate: 8000.00),
  (desc: "Social Media Content Production (30 posts)", qty: 30, rate: 150.00),
  (desc: "Blog Article Writing (BM/EN bilingual)", qty: 4, rate: 500.00),
  (desc: "Visual Asset Design — Instagram + Facebook", qty: 20, rate: 120.00),
  (desc: "Monthly Performance Report", qty: 1, rate: 1500.00),
)

// ── Formatting helper ─────────────────────────────────────────────────────
#let fmt-myr(amount) = {
  let whole = calc.floor(amount)
  let cents = calc.round((amount - whole) * 100)
  let cents-str = if cents < 10 { "0" + str(cents) } else { str(cents) }
  str(whole) + "." + cents-str
}

#let subtotal = items.map(item => item.qty * item.rate).sum()
#let tax-amount = subtotal * tax-rate
#let total = subtotal + tax-amount

#table(
  columns: (auto, 1fr, auto, auto, auto),
  stroke: none,
  inset: (x: 8pt, y: 6pt),

  // Header
  table.hline(stroke: 1pt + primary),
  text(size: 8.5pt, weight: "bold", fill: primary)[No.],
  text(size: 8.5pt, weight: "bold", fill: primary)[Description],
  text(size: 8.5pt, weight: "bold", fill: primary)[Qty],
  text(size: 8.5pt, weight: "bold", fill: primary)[Rate (MYR)],
  text(size: 8.5pt, weight: "bold", fill: primary)[Amount (MYR)],
  table.hline(stroke: 0.5pt + luma(200)),

  // Items
  ..{
    let rows = ()
    for (idx, item) in items.enumerate() {
      let amount = item.qty * item.rate
      rows.push(text(size: 9pt)[#{idx + 1}])
      rows.push(text(size: 9pt)[#item.desc])
      rows.push(align(center, text(size: 9pt)[#item.qty]))
      rows.push(align(right, text(size: 9pt)[#fmt-myr(item.rate)]))
      rows.push(align(right, text(size: 9pt)[#fmt-myr(amount)]))
    }
    rows
  },
  table.hline(stroke: 0.5pt + luma(200)),
)

// ═════════════════════════════════════════════════════════════════════════════
// TOTALS
// ═════════════════════════════════════════════════════════════════════════════

#v(0.5em)
#align(right)[
  #grid(
    columns: (auto, 8em),
    column-gutter: 2em,
    row-gutter: 6pt,
    align: (right, right),
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

// ═════════════════════════════════════════════════════════════════════════════
// PAYMENT DETAILS
// ═════════════════════════════════════════════════════════════════════════════

#rect(
  width: 100%,
  inset: 14pt,
  radius: 4pt,
  fill: secondary,
  stroke: 0.5pt + luma(220),
)[
  #text(font: heading-font, size: 10pt, weight: "bold", fill: primary)[Payment Details]
  #v(0.4em)
  #grid(
    columns: (auto, 1fr),
    column-gutter: 12pt,
    row-gutter: 4pt,
    text(size: 9pt, weight: "bold", fill: luma(80))[Bank:],
    text(size: 9pt)[#bank-name],
    text(size: 9pt, weight: "bold", fill: luma(80))[Account Name:],
    text(size: 9pt)[#company-name],
    text(size: 9pt, weight: "bold", fill: luma(80))[Account No:],
    text(size: 9pt)[#bank-account],
    text(size: 9pt, weight: "bold", fill: luma(80))[SWIFT Code:],
    text(size: 9pt)[#bank-swift],
  )
]

#v(1em)

// ═════════════════════════════════════════════════════════════════════════════
// PAYMENT TERMS
// ═════════════════════════════════════════════════════════════════════════════

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
