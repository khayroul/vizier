// ─────────────────────────────────────────────────────────────────────────────
// book_facing_pages.typ — Children's book: text left, illustration right (spread)
// Vizier — Typst 0.14.2, no external packages
//
// Layout: Even pages = text (verso), odd pages = illustration (recto).
// Designed for print spreads where left and right pages face each other.
// CRITICAL: Illustrations are ALWAYS text-free. Typst adds ALL text. (#49)
// ─────────────────────────────────────────────────────────────────────────────

// ── Brand / book inputs ──────────────────────────────────────────────────────
#let primary      = rgb(sys.inputs.at("primary_color",   default: "#264653"))
#let secondary    = rgb(sys.inputs.at("secondary_color", default: "#FFF8F0"))
#let accent       = rgb(sys.inputs.at("accent_color",    default: "#E76F51"))
#let heading-font = sys.inputs.at("headline_font", default: "Plus Jakarta Sans")
#let body-font    = sys.inputs.at("body_font",     default: "Plus Jakarta Sans")
#let book-title   = sys.inputs.at("title",     default: "Wau Bulan Terbang Tinggi")
#let book-author  = sys.inputs.at("author",    default: "Penulis Contoh")
#let age-group    = sys.inputs.at("age_group", default: "5-7")

// ── Age-calibrated typography ────────────────────────────────────────────────
#let body-size = if age-group == "3-5" { 20pt } else if age-group == "5-7" { 16pt } else { 14pt }
#let body-leading = if age-group == "3-5" { 1.5em } else if age-group == "5-7" { 1.4em } else { 1.3em }

// ── Page setup (portrait picture book) ───────────────────────────────────────
#set page(
  width: 8in,
  height: 10in,
  margin: (rest: 0pt),
  footer: none,
  header: none,
)

#set text(font: body-font, size: body-size, fill: primary)
#set par(leading: body-leading, spacing: 1.2em)

// ── Placeholder image ────────────────────────────────────────────────────────
#let placeholder-image(label) = {
  rect(
    width: 100%,
    height: 100%,
    fill: luma(230),
    stroke: none,
  )[
    #align(center + horizon)[
      #text(size: 10pt, fill: luma(150))[TEXT-FREE ILLUSTRATION: #label]
    ]
  ]
}

// ── Text page (verso — left in spread) ───────────────────────────────────────
#let text-page(story-text, page-num) = {
  page[
    #rect(width: 100%, height: 100%, fill: secondary)[
      #pad(left: 1.5cm, right: 2cm, top: 3cm, bottom: 1.5cm)[
        #align(horizon)[
          #story-text
        ]
      ]
      #place(bottom + left, dx: 1.5cm, dy: -0.5cm)[
        #text(size: 9pt, fill: luma(150))[#page-num]
      ]
    ]
  ]
}

// ── Illustration page (recto — right in spread) ─────────────────────────────
#let illust-page(image-label, page-num) = {
  page[
    #placeholder-image(image-label)
    #place(bottom + right, dx: -0.5cm, dy: -0.5cm)[
      #text(size: 9pt, fill: luma(150))[#page-num]
    ]
  ]
}

// ═════════════════════════════════════════════════════════════════════════════
// TITLE PAGE (Page 1)
// ═════════════════════════════════════════════════════════════════════════════
#page[
  #rect(width: 100%, height: 100%, fill: primary)[
    #align(center + horizon)[
      #pad(x: 2cm)[
        // Decorative kite shape
        #text(size: 48pt)[◇]
        #v(0.5em)
        #text(font: heading-font, size: 30pt, weight: "bold", fill: secondary)[#book-title]
        #v(1em)
        #text(size: 14pt, fill: secondary.darken(10%))[#book-author]
      ]
    ]
  ]
]

// ═════════════════════════════════════════════════════════════════════════════
// SPREAD 1 (Pages 2-3)
// ═════════════════════════════════════════════════════════════════════════════
#text-page(
  [Amin suka membuat wau. Setiap petang, dia duduk di beranda rumah dan mengikat buluh dengan benang.

  "Amin, wau kamu cantik!" kata adiknya, Aisyah.],
  2,
)

#illust-page(
  "Amin on a wooden veranda, carefully tying bamboo strips into a kite frame",
  3,
)

// ═════════════════════════════════════════════════════════════════════════════
// SPREAD 2 (Pages 4-5)
// ═════════════════════════════════════════════════════════════════════════════
#text-page(
  [Hari ini hari pertandingan wau bulan di kampung. Amin membawa wau barunya — wau bulan berwarna biru dan emas.

  Hatinya berdebar-debar!],
  4,
)

#illust-page(
  "Village field filled with colourful kites, children and families gathering",
  5,
)

// ═════════════════════════════════════════════════════════════════════════════
// SPREAD 3 (Pages 6-7)
// ═════════════════════════════════════════════════════════════════════════════
#text-page(
  [Angin bertiup kuat. Amin melepaskan wau bulannya ke udara. Ia naik tinggi, lebih tinggi daripada semua wau yang lain!

  "Terbang, wau, terbang!" sorak Aisyah.],
  6,
)

#illust-page(
  "A magnificent blue and gold moon kite soaring highest in the sky, other kites below",
  7,
)

// ═════════════════════════════════════════════════════════════════════════════
// CLOSING PAGE (Page 8)
// ═════════════════════════════════════════════════════════════════════════════
#page[
  #rect(width: 100%, height: 100%, fill: secondary)[
    #align(center + horizon)[
      #pad(x: 2cm)[
        #text(font: heading-font, size: 22pt, weight: "bold", fill: primary)[Tamat]
        #v(1em)
        #text(fill: primary)[
          Amin menang pertandingan hari itu.
          Tetapi yang paling membahagiakan hatinya
          ialah melihat wau bulannya terbang tinggi,
          terbang bebas di langit biru.
        ]
        #v(2em)
        #text(size: 9pt, fill: luma(150))[8]
      ]
    ]
  ]
]
