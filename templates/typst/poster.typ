// ─────────────────────────────────────────────────────────────────────────────
// poster.typ — Single-page poster template with text overlay on background image
// Vizier — Typst 0.14.2, no external packages
//
// Layout: full-bleed background image, headline strip at top,
//         body panel lower-left, CTA bar at bottom.
// Anti-drift #49: text rendered by Typst, never baked into AI images.
// ─────────────────────────────────────────────────────────────────────────────

// ── Brand inputs ─────────────────────────────────────────────────────────────
#let primary      = rgb(sys.inputs.at("primary_color",   default: "#1A365D"))
#let secondary    = rgb(sys.inputs.at("secondary_color", default: "#2B6CB0"))
#let accent       = rgb(sys.inputs.at("accent_color",    default: "#ED8936"))
#let heading-font = sys.inputs.at("headline_font", default: "Plus Jakarta Sans")
#let body-font    = sys.inputs.at("body_font",     default: "Inter")

// ── Content inputs ───────────────────────────────────────────────────────────
#let bg-image     = sys.inputs.at("background_image", default: "")
#let headline     = sys.inputs.at("headline",         default: "HEADLINE")
#let subheadline  = sys.inputs.at("subheadline",      default: "")
#let cta-text     = sys.inputs.at("cta",              default: "")
#let body-raw     = sys.inputs.at("body_text",        default: "")
#let page-size    = sys.inputs.at("page_size",        default: "a4")

// ── Parse body text (newline-separated bullet points) ────────────────────────
#let body-lines = if body-raw.len() > 0 {
  body-raw.split("\n").filter(l => l.trim().len() > 0)
} else {
  ()
}

// ── Page setup ───────────────────────────────────────────────────────────────
#set page(
  paper: page-size,
  margin: 0pt,
)

// ── Background image (full bleed) ────────────────────────────────────────────
#if bg-image.len() > 0 {
  place(
    top + left,
    image(bg-image, width: 100%, height: 100%, fit: "cover"),
  )
}

// ── Top zone: headline + subheadline ─────────────────────────────────────────
// Semi-transparent dark strip across the top
#place(top + left, dy: 0pt, dx: 0pt,
  block(
    width: 100%,
    inset: (x: 24pt, y: 20pt),
    fill: primary.transparentize(25%),
    {
      set text(font: heading-font, fill: white)
      set par(leading: 0.5em)

      // Headline
      text(size: 28pt, weight: "bold")[#headline]

      // Subheadline
      if subheadline.len() > 0 {
        v(6pt)
        text(size: 14pt, weight: "regular")[#subheadline]
      }
    }
  )
)

// ── Lower-left zone: body text / info panel ──────────────────────────────────
#if body-lines.len() > 0 {
  place(bottom + left, dy: -60pt, dx: 16pt,
    block(
      width: 55%,
      inset: (x: 16pt, y: 14pt),
      radius: 6pt,
      fill: white.transparentize(15%),
      stroke: 0.5pt + luma(200),
      {
        set text(font: body-font, size: 11pt, fill: luma(30))
        set par(leading: 0.55em, spacing: 0.7em)
        for line in body-lines {
          [• #line.trim() \ ]
        }
      }
    )
  )
}

// ── Bottom zone: CTA bar ─────────────────────────────────────────────────────
#if cta-text.len() > 0 {
  place(bottom + left, dy: 0pt, dx: 0pt,
    block(
      width: 100%,
      inset: (x: 24pt, y: 14pt),
      fill: accent,
      {
        set text(font: heading-font, size: 16pt, weight: "bold", fill: white)
        set align(center)
        [#cta-text]
      }
    )
  )
}
