// ─────────────────────────────────────────────────────────────────────────────
// book_single_page.typ — Children's book: illustration top, text bottom
// Vizier — Typst 0.14.2, no external packages
//
// Layout: Top ~60% is illustration, bottom ~40% is text zone.
// Classic picture book layout — illustration dominates, text anchored below.
// CRITICAL: Illustrations are ALWAYS text-free. Typst adds ALL text. (#49)
// ─────────────────────────────────────────────────────────────────────────────

// ── Brand / book inputs ──────────────────────────────────────────────────────
#let primary      = rgb(sys.inputs.at("primary_color",   default: "#3D405B"))
#let secondary    = rgb(sys.inputs.at("secondary_color", default: "#FFF9EC"))
#let accent       = rgb(sys.inputs.at("accent_color",    default: "#E07A5F"))
#let heading-font = sys.inputs.at("headline_font", default: "Plus Jakarta Sans")
#let body-font    = sys.inputs.at("body_font",     default: "Plus Jakarta Sans")
#let book-title   = sys.inputs.at("title",     default: "Kucing dan Bulan")
#let book-author  = sys.inputs.at("author",    default: "Penulis Contoh")
#let age-group    = sys.inputs.at("age_group", default: "3-5")

// ── Age-calibrated typography ────────────────────────────────────────────────
#let body-size = if age-group == "3-5" { 20pt } else if age-group == "5-7" { 16pt } else { 14pt }
#let body-leading = if age-group == "3-5" { 1.5em } else if age-group == "5-7" { 1.4em } else { 1.3em }

// ── Page setup (portrait picture book) ───────────────────────────────────────
#set page(
  width: 8.5in,
  height: 11in,
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

// ── Single page builder ─────────────────────────────────────────────────────
#let story-page(story-text, image-label, page-num) = {
  page[
    // Top: illustration (60%)
    #rect(width: 100%, height: 60%, fill: none)[
      #placeholder-image(image-label)
    ]

    // Bottom: text zone (40%)
    #rect(width: 100%, height: 40%, fill: secondary)[
      #pad(x: 2cm, top: 1cm, bottom: 0.8cm)[
        #align(center + horizon)[
          #story-text
        ]
      ]
      #place(bottom + center, dy: -0.4cm)[
        #text(size: 9pt, fill: luma(150))[#page-num]
      ]
    ]
  ]
}

// ═════════════════════════════════════════════════════════════════════════════
// TITLE PAGE (Page 1)
// ═════════════════════════════════════════════════════════════════════════════
#page[
  // Top illustration area
  #rect(width: 100%, height: 55%, fill: luma(230))[
    #align(center + horizon)[
      #text(size: 10pt, fill: luma(150))[TEXT-FREE ILLUSTRATION: A cat sitting on a rooftop looking at a bright full moon]
    ]
  ]

  // Title zone
  #rect(width: 100%, height: 45%, fill: primary)[
    #align(center + horizon)[
      #pad(x: 2cm)[
        #text(font: heading-font, size: 36pt, weight: "bold", fill: secondary)[#book-title]
        #v(0.8em)
        #text(size: 14pt, fill: secondary.darken(10%))[#book-author]
      ]
    ]
  ]
]

// ═════════════════════════════════════════════════════════════════════════════
// STORY PAGES (Pages 2–7)
// ═════════════════════════════════════════════════════════════════════════════

#story-page(
  [Si Kucing tinggal di atas bumbung rumah lama.
  Setiap malam, dia memandang bulan.],
  "A ginger cat sitting on an old tiled rooftop at night",
  2,
)

#story-page(
  ["Bulan, kenapa kamu jauh sangat?"
  tanya Si Kucing.],
  "Cat reaching one paw toward the bright moon",
  3,
)

#story-page(
  [Si Kucing melompat tinggi!
  Tetapi bulan masih jauh.],
  "Cat leaping high into the air, moon still far above",
  4,
)

#story-page(
  [Dia cuba panjat pokok kelapa.
  Tetapi bulan masih jauh.],
  "Cat climbing a tall coconut palm, straining upward",
  5,
)

#story-page(
  [Si Kucing duduk sedih.
  Lalu dia nampak — bulan di dalam kolam air!],
  "Cat looking down at moon reflection in a puddle, surprised expression",
  6,
)

#story-page(
  [Si Kucing menyentuh air dengan kaki.
  Bulan bergoyang dan ketawa!],
  "Cat gently touching the water with a paw, ripples distorting the moon reflection",
  7,
)

// ═════════════════════════════════════════════════════════════════════════════
// CLOSING PAGE (Page 8)
// ═════════════════════════════════════════════════════════════════════════════
#page[
  #rect(width: 100%, height: 55%, fill: luma(230))[
    #align(center + horizon)[
      #text(size: 10pt, fill: luma(150))[TEXT-FREE ILLUSTRATION: Cat curled up sleeping peacefully beside the puddle, moon reflected in the water and shining above]
    ]
  ]

  #rect(width: 100%, height: 45%, fill: secondary)[
    #align(center + horizon)[
      #pad(x: 2cm)[
        #text(font: heading-font, size: 22pt, weight: "bold", fill: primary)[Tamat]
        #v(0.6em)
        #text(fill: primary)[
          Si Kucing tersenyum.
          Bulan memang jauh,
          tapi bulan sentiasa ada untuknya.
        ]
        #v(1.5em)
        #text(size: 9pt, fill: luma(150))[8]
      ]
    ]
  ]
]
