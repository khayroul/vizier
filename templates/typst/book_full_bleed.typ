// ─────────────────────────────────────────────────────────────────────────────
// book_full_bleed.typ — Children's book: full-bleed illustration layout
// Vizier — Typst 0.14.2, no external packages
//
// Layout: Illustration fills entire page. Text in semi-transparent overlay box.
// CRITICAL: Illustrations are ALWAYS text-free. Typst adds ALL text. (#49)
//
// Typography targets (§42.3):
//   Age 3-5: 20pt body, 150% line spacing, max 3-4 lines
//   Age 5-7: 16pt body, 130-150%, max 3-4 lines
//   Age 8-10: 14pt body, 130%, max 6-8 lines
// ─────────────────────────────────────────────────────────────────────────────

// ── Brand / book inputs ──────────────────────────────────────────────────────
#let primary      = rgb(sys.inputs.at("primary_color",   default: "#2D1B69"))
#let secondary    = rgb(sys.inputs.at("secondary_color", default: "#FFF8E7"))
#let accent       = rgb(sys.inputs.at("accent_color",    default: "#FF6B35"))
#let heading-font = sys.inputs.at("headline_font", default: "Plus Jakarta Sans")
#let body-font    = sys.inputs.at("body_font",     default: "Plus Jakarta Sans")
#let book-title   = sys.inputs.at("title",  default: "Ahmad dan Batik Ajaib")
#let book-author  = sys.inputs.at("author", default: "Penulis Contoh")
#let age-group    = sys.inputs.at("age_group", default: "5-7")

// ── Age-calibrated typography ────────────────────────────────────────────────
#let body-size = if age-group == "3-5" { 20pt } else if age-group == "5-7" { 16pt } else { 14pt }
#let body-leading = if age-group == "3-5" { 1.5em } else if age-group == "5-7" { 1.4em } else { 1.3em }

// ── Page setup (square picture book format) ──────────────────────────────────
#set page(
  width: 8.5in,
  height: 8.5in,
  margin: (rest: 0pt),
  footer: none,
  header: none,
)

#set text(font: body-font, size: body-size, fill: primary)
#set par(leading: body-leading, spacing: 1.2em)

// ── Placeholder image (grey rectangle with label) ────────────────────────────
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

// ── Text overlay box ─────────────────────────────────────────────────────────
#let text-overlay(body, position: bottom) = {
  let y-offset = if position == bottom { 60% } else { 0% }
  let box-height = 40%
  place(
    top + left,
    dy: y-offset,
    rect(
      width: 100%,
      height: box-height,
      fill: white.transparentize(20%),
    )[
      #pad(x: 1.2cm, y: 0.8cm)[
        #align(center)[#body]
      ]
    ],
  )
}

// ═════════════════════════════════════════════════════════════════════════════
// TITLE PAGE (Page 1)
// ═════════════════════════════════════════════════════════════════════════════
#page[
  #rect(width: 100%, height: 100%, fill: primary)[
    #align(center + horizon)[
      #pad(x: 2cm)[
        #text(font: heading-font, size: 36pt, weight: "bold", fill: secondary)[#book-title]
        #v(1em)
        #text(font: body-font, size: 14pt, fill: secondary.darken(10%))[#book-author]
      ]
    ]
  ]
  // Page number (none for title)
]

// ═════════════════════════════════════════════════════════════════════════════
// STORY PAGES (Pages 2–7)
// ═════════════════════════════════════════════════════════════════════════════

// Page 2
#page[
  #placeholder-image("Ahmad finds the old batik cloth in nenek's chest")
  #text-overlay(position: bottom)[
    Ahmad membuka peti kayu nenek dengan perlahan.
    Di dalam, sehelai kain batik berwarna-warni berkilauan.
  ]
  #place(bottom + right, dx: -0.5cm, dy: -0.3cm)[
    #text(size: 9pt, fill: white)[2]
  ]
]

// Page 3
#page[
  #placeholder-image("The batik cloth begins to glow with magical light")
  #text-overlay(position: bottom)[
    "Wahhh!" bisik Ahmad.
    Kain batik itu mula bersinar terang!
  ]
  #place(bottom + left, dx: 0.5cm, dy: -0.3cm)[
    #text(size: 9pt, fill: white)[3]
  ]
]

// Page 4
#page[
  #placeholder-image("Ahmad is transported to a magical batik forest")
  #text-overlay(position: bottom)[
    Tiba-tiba, Ahmad berada di dalam hutan ajaib.
    Pokok-pokok dihiasi corak batik yang indah.
  ]
  #place(bottom + right, dx: -0.5cm, dy: -0.3cm)[
    #text(size: 9pt, fill: white)[4]
  ]
]

// Page 5
#page[
  #placeholder-image("Ahmad meets a wise bird with batik-patterned wings")
  #text-overlay(position: bottom)[
    Seekor burung cantik hinggap di bahunya.
    "Selamat datang, Ahmad," kata burung itu.
  ]
  #place(bottom + left, dx: 0.5cm, dy: -0.3cm)[
    #text(size: 9pt, fill: white)[5]
  ]
]

// Page 6
#page[
  #placeholder-image("Ahmad tries to draw batik patterns with the canting")
  #text-overlay(position: bottom)[
    Ahmad mencuba melukis corak batik.
    Tangannya gementar, tetapi dia tidak berputus asa.
  ]
  #place(bottom + right, dx: -0.5cm, dy: -0.3cm)[
    #text(size: 9pt, fill: white)[6]
  ]
]

// Page 7
#page[
  #placeholder-image("Ahmad's batik pattern comes alive with colour")
  #text-overlay(position: bottom)[
    Perlahan-lahan, corak batik Ahmad mula hidup!
    Warna-warna cantik memenuhi kain putih itu.
  ]
  #place(bottom + left, dx: 0.5cm, dy: -0.3cm)[
    #text(size: 9pt, fill: white)[7]
  ]
]

// ═════════════════════════════════════════════════════════════════════════════
// CLOSING PAGE (Page 8)
// ═════════════════════════════════════════════════════════════════════════════
#page[
  #placeholder-image("Ahmad shows nenek his first batik — both smiling")
  #text-overlay(position: bottom)[
    "Nenek, lihat!" Ahmad tersenyum bangga.
    Nenek memeluknya erat. "Batik pertamamu, sayang."
  ]
  #place(bottom + right, dx: -0.5cm, dy: -0.3cm)[
    #text(size: 9pt, fill: white)[8]
  ]
]
