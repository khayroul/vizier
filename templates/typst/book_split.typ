// ─────────────────────────────────────────────────────────────────────────────
// book_split.typ — Children's book: split layout (text / illustration)
// Vizier — Typst 0.14.2, no external packages
//
// Layout: Left text / right illustration (configurable via text_side input).
// CRITICAL: Illustrations are ALWAYS text-free. Typst adds ALL text. (#49)
// ─────────────────────────────────────────────────────────────────────────────

// ── Brand / book inputs ──────────────────────────────────────────────────────
#let primary      = rgb(sys.inputs.at("primary_color",   default: "#1B4332"))
#let secondary    = rgb(sys.inputs.at("secondary_color", default: "#FFF9E6"))
#let accent       = rgb(sys.inputs.at("accent_color",    default: "#F77F00"))
#let heading-font = sys.inputs.at("headline_font", default: "Plus Jakarta Sans")
#let body-font    = sys.inputs.at("body_font",     default: "Plus Jakarta Sans")
#let book-title   = sys.inputs.at("title",     default: "Sang Kancil dan Buaya")
#let book-author  = sys.inputs.at("author",    default: "Penulis Contoh")
#let age-group    = sys.inputs.at("age_group", default: "5-7")
#let text-side    = sys.inputs.at("text_side", default: "left")

// ── Age-calibrated typography ────────────────────────────────────────────────
#let body-size = if age-group == "3-5" { 20pt } else if age-group == "5-7" { 16pt } else { 14pt }
#let body-leading = if age-group == "3-5" { 1.5em } else if age-group == "5-7" { 1.4em } else { 1.3em }

// ── Page setup (landscape picture book) ──────────────────────────────────────
#set page(
  width: 11in,
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

// ── Split page builder ───────────────────────────────────────────────────────
#let split-page(story-text, image-label, page-num, side: text-side) = {
  let text-block = pad(x: 1cm, y: 1.5cm)[
    #align(horizon)[
      #story-text
    ]
    #place(bottom + center, dy: -0.3cm)[
      #text(size: 9pt, fill: luma(120))[#page-num]
    ]
  ]
  let image-block = placeholder-image(image-label)

  page[
    #grid(
      columns: if side == "left" { (45%, 55%) } else { (55%, 45%) },
      rows: (100%,),
      if side == "left" {
        rect(width: 100%, height: 100%, fill: secondary)[#text-block]
      } else {
        image-block
      },
      if side == "left" {
        image-block
      } else {
        rect(width: 100%, height: 100%, fill: secondary)[#text-block]
      },
    )
  ]
}

// ═════════════════════════════════════════════════════════════════════════════
// TITLE PAGE (Page 1)
// ═════════════════════════════════════════════════════════════════════════════
#page[
  #grid(
    columns: (45%, 55%),
    rows: (100%,),
    rect(width: 100%, height: 100%, fill: primary)[
      #align(center + horizon)[
        #pad(x: 1.5cm)[
          #text(font: heading-font, size: 32pt, weight: "bold", fill: secondary)[#book-title]
          #v(1em)
          #text(size: 14pt, fill: secondary.darken(10%))[#book-author]
        ]
      ]
    ],
    placeholder-image("Title illustration — Sang Kancil in the forest"),
  )
]

// ═════════════════════════════════════════════════════════════════════════════
// STORY PAGES (Pages 2–7)
// ═════════════════════════════════════════════════════════════════════════════

#split-page(
  [Pada suatu hari, Sang Kancil ingin menyeberangi sungai yang lebar. Tetapi airnya sangat deras!],
  "Kancil standing at the wide river bank, looking across",
  2,
)

#split-page(
  ["Hmm, macam mana aku nak ke seberang?" fikir Sang Kancil. Lalu dia nampak beberapa ekor buaya!],
  "Kancil thinking with a mischievous expression, crocodiles in water",
  3,
  side: if text-side == "left" { "right" } else { "left" },
)

#split-page(
  ["Wah, ramai sungguh buaya!" kata Sang Kancil. "Aku nak kira berapa ekor kamu semua!"],
  "Kancil calling out to the crocodiles, gesturing with paws",
  4,
)

#split-page(
  [Buaya-buaya itu berbaris dari tebing ke tebing. Satu, dua, tiga... Sang Kancil melompat di atas belakang mereka!],
  "Crocodiles lined up across river, Kancil hopping on their backs",
  5,
  side: if text-side == "left" { "right" } else { "left" },
)

#split-page(
  ["Empat, lima, enam, tujuh!" kira Sang Kancil sambil melompat. Dia hampir sampai ke seberang!],
  "Kancil mid-leap between crocodiles, almost at far bank",
  6,
)

#split-page(
  [Dengan lompatan terakhir, Sang Kancil selamat sampai ke seberang! Buaya-buaya baru sedar mereka telah ditipu.],
  "Kancil safely on far bank, looking back at confused crocodiles",
  7,
  side: if text-side == "left" { "right" } else { "left" },
)

// ═════════════════════════════════════════════════════════════════════════════
// CLOSING PAGE (Page 8)
// ═════════════════════════════════════════════════════════════════════════════
#page[
  #rect(width: 100%, height: 100%, fill: secondary)[
    #align(center + horizon)[
      #pad(x: 3cm)[
        #text(font: heading-font, size: 24pt, weight: "bold", fill: primary)[Tamat]
        #v(1em)
        #text(size: body-size, fill: primary)[
          Sang Kancil tersenyum lebar.
          Dia memang kancil yang paling bijak di hutan!
        ]
        #v(2em)
        #text(size: 9pt, fill: luma(120))[8]
      ]
    ]
  ]
]
