// ─────────────────────────────────────────────────────────────────────────────
// book_text_overlay.typ — Children's book: text over semi-transparent bar
// Vizier — Typst 0.14.2, no external packages
//
// Layout: Full illustration with text over a semi-transparent horizontal bar.
// CRITICAL: Illustrations are ALWAYS text-free. Typst adds ALL text. (#49)
// ─────────────────────────────────────────────────────────────────────────────

// ── Brand / book inputs ──────────────────────────────────────────────────────
#let primary      = rgb(sys.inputs.at("primary_color",   default: "#1A1A2E"))
#let secondary    = rgb(sys.inputs.at("secondary_color", default: "#FFFBEB"))
#let accent       = rgb(sys.inputs.at("accent_color",    default: "#E63946"))
#let heading-font = sys.inputs.at("headline_font", default: "Plus Jakarta Sans")
#let body-font    = sys.inputs.at("body_font",     default: "Plus Jakarta Sans")
#let book-title   = sys.inputs.at("title",     default: "Puteri Gunung Ledang")
#let book-author  = sys.inputs.at("author",    default: "Penulis Contoh")
#let age-group    = sys.inputs.at("age_group", default: "5-7")

// ── Age-calibrated typography ────────────────────────────────────────────────
#let body-size = if age-group == "3-5" { 20pt } else if age-group == "5-7" { 16pt } else { 14pt }
#let body-leading = if age-group == "3-5" { 1.5em } else if age-group == "5-7" { 1.4em } else { 1.3em }

// ── Page setup (square picture book) ─────────────────────────────────────────
#set page(
  width: 8.5in,
  height: 8.5in,
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

// ── Overlay bar builder ──────────────────────────────────────────────────────
#let overlay-page(story-text, image-label, page-num, bar-position: "bottom") = {
  let bar-y = if bar-position == "bottom" { 72% } else { 0% }
  let bar-height = 28%

  page[
    // Full-bleed illustration
    #placeholder-image(image-label)

    // Semi-transparent text bar
    #place(
      top + left,
      dy: bar-y,
      rect(
        width: 100%,
        height: bar-height,
        fill: white.transparentize(15%),
      )[
        #pad(x: 1.5cm, y: 0.6cm)[
          #align(center + horizon)[
            #text(fill: primary)[#story-text]
          ]
        ]
      ],
    )

    // Page number
    #place(bottom + if calc.even(page-num) { left } else { right },
      dx: if calc.even(page-num) { 0.5cm } else { -0.5cm },
      dy: -0.3cm,
    )[
      #text(size: 9pt, fill: luma(100))[#page-num]
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
        #text(font: heading-font, size: 36pt, weight: "bold", fill: secondary)[#book-title]
        #v(0.8em)
        #line(length: 4cm, stroke: 1.5pt + accent)
        #v(0.8em)
        #text(size: 14pt, fill: secondary.darken(10%))[#book-author]
      ]
    ]
  ]
]

// ═════════════════════════════════════════════════════════════════════════════
// STORY PAGES (Pages 2–7)
// ═════════════════════════════════════════════════════════════════════════════

#overlay-page(
  [Di puncak Gunung Ledang, tinggal seorang puteri yang sangat cantik. Tiada siapa pernah melihat wajahnya.],
  "Misty mountain peak with a palace barely visible through clouds",
  2,
)

#overlay-page(
  [Seorang sultan yang gagah menghantar utusan ke gunung itu. "Aku ingin meminang Puteri Gunung Ledang!"],
  "Royal procession climbing the mountain path with gifts",
  3,
  bar-position: "top",
)

#overlay-page(
  [Puteri menetapkan tujuh syarat yang mustahil. "Bawakan aku jambatan emas dari Melaka ke gunung ini."],
  "Princess silhouette behind a glowing veil, holding up seven fingers",
  4,
)

#overlay-page(
  [Sultan cuba memenuhi setiap syarat, tetapi semuanya terlalu sukar. Hatinya mula sedih.],
  "Sultan sitting alone in his chamber looking out at the mountain",
  5,
  bar-position: "top",
)

#overlay-page(
  ["Mungkin cinta yang sejati bukan tentang memiliki," bisik angin gunung kepada sultan.],
  "Wind swirling around the sultan, carrying flower petals from the mountain",
  6,
)

#overlay-page(
  [Sultan akhirnya faham. Dia menghormati keputusan Puteri dan pulang ke istananya.],
  "Sultan bowing respectfully toward the mountain from afar",
  7,
  bar-position: "top",
)

// ═════════════════════════════════════════════════════════════════════════════
// CLOSING PAGE (Page 8)
// ═════════════════════════════════════════════════════════════════════════════
#page[
  #placeholder-image("Gunung Ledang at sunset, peaceful and majestic")
  #place(
    top + left,
    dy: 35%,
    rect(
      width: 100%,
      height: 30%,
      fill: white.transparentize(15%),
    )[
      #pad(x: 2cm, y: 0.8cm)[
        #align(center + horizon)[
          #text(font: heading-font, size: 20pt, weight: "bold", fill: primary)[Tamat]
          #v(0.4em)
          #text(fill: primary)[
            Dan Gunung Ledang tetap berdiri megah,
            menyimpan rahsia Puteri buat selama-lamanya.
          ]
        ]
      ]
    ],
  )
  #place(bottom + right, dx: -0.5cm, dy: -0.3cm)[
    #text(size: 9pt, fill: luma(100))[8]
  ]
]
