// ─────────────────────────────────────────────────────────────────────────────
// content_calendar.typ — Content calendar template
// Vizier — Typst 0.14.2, no external packages
//
// Layout: Monthly grid with platform columns and event highlights
// ─────────────────────────────────────────────────────────────────────────────

// ── Brand inputs ─────────────────────────────────────────────────────────────
#let primary      = rgb(sys.inputs.at("primary_color",   default: "#1A1A2E"))
#let secondary    = rgb(sys.inputs.at("secondary_color", default: "#F0F0F5"))
#let accent       = rgb(sys.inputs.at("accent_color",    default: "#2563EB"))
#let heading-font = sys.inputs.at("headline_font", default: "Plus Jakarta Sans")
#let body-font    = sys.inputs.at("body_font",     default: "Inter")

#let cal-title  = sys.inputs.at("title",       default: "Content Calendar")
#let cal-month  = sys.inputs.at("month",       default: "April 2026")
#let cal-client = sys.inputs.at("client_name", default: "")
#let cal-author = sys.inputs.at("author",      default: "")

// ── Platform colours ─────────────────────────────────────────────────────────
#let ig-color = rgb("#E1306C")
#let fb-color = rgb("#1877F2")
#let li-color = rgb("#0A66C2")
#let tt-color = rgb("#000000")
#let blog-color = rgb("#10B981")

// ── Page setup (landscape A4) ────────────────────────────────────────────────
#set page(
  paper: "a4",
  flipped: true,
  margin: (top: 1.8cm, bottom: 1.5cm, left: 1.5cm, right: 1.5cm),
  header: context {
    if counter(page).get().first() > 1 [
      #grid(
        columns: (1fr, 1fr),
        align: (left, right),
        text(size: 8pt, fill: luma(140))[#cal-title — #cal-month],
        text(size: 8pt, fill: luma(140))[#counter(page).display("1")],
      )
      #line(length: 100%, stroke: 0.3pt + luma(220))
    ]
  },
  footer: none,
)

// ── Base typography ──────────────────────────────────────────────────────────
#set text(font: body-font, size: 9pt, fill: luma(30))
#set par(leading: 0.5em, spacing: 0.8em)

// ── Utility: platform badge ──────────────────────────────────────────────────
#let badge(label, color) = {
  box(
    inset: (x: 5pt, y: 2pt),
    radius: 3pt,
    fill: color.lighten(85%),
  )[
    #text(size: 7pt, weight: "bold", fill: color)[#label]
  ]
}

// ── Utility: calendar cell ───────────────────────────────────────────────────
#let cal-cell(day, ..items) = {
  let entries = items.pos()
  box(
    width: 100%,
    height: 100%,
    inset: 4pt,
    stroke: 0.3pt + luma(220),
  )[
    #text(font: heading-font, size: 8pt, weight: "bold", fill: primary)[#day]
    #v(2pt)
    #for entry in entries [
      #entry
      #v(1pt)
    ]
  ]
}

// ── Utility: event highlight ─────────────────────────────────────────────────
#let event-highlight(label) = {
  box(
    width: 100%,
    inset: (x: 4pt, y: 2pt),
    radius: 2pt,
    fill: accent.lighten(85%),
  )[
    #text(size: 7pt, weight: "bold", fill: accent)[#label]
  ]
}

// ═════════════════════════════════════════════════════════════════════════════
// COVER PAGE
// ═════════════════════════════════════════════════════════════════════════════
#page(
  margin: (rest: 0pt),
  header: none,
)[
  #rect(width: 100%, height: 100%, fill: primary)[
    #pad(left: 3cm, right: 3cm, top: 4cm)[
      #rect(width: 3cm, height: 4pt, fill: accent)
      #v(0.8em)

      #text(font: heading-font, size: 32pt, weight: "bold", fill: white)[#cal-title]
      #v(0.3em)
      #text(font: heading-font, size: 20pt, fill: accent)[#cal-month]

      #v(3em)
      #if cal-client != "" [
        #text(size: 12pt, fill: white.darken(15%))[Client: #cal-client]
        #v(0.3em)
      ]
      #if cal-author != "" [
        #text(size: 12pt, fill: white.darken(15%))[Prepared by: #cal-author]
      ]

      #v(4em)
      // Platform legend
      #text(font: heading-font, size: 10pt, fill: white.darken(10%), weight: "semibold")[Platforms]
      #v(0.4em)
      #grid(
        columns: (auto, auto, auto, auto, auto),
        column-gutter: 12pt,
        badge("IG", ig-color),
        badge("FB", fb-color),
        badge("LI", li-color),
        badge("TT", tt-color),
        badge("BLOG", blog-color),
      )
    ]
  ]
]

// ═════════════════════════════════════════════════════════════════════════════
// MONTHLY OVERVIEW — WEEK VIEW
// ═════════════════════════════════════════════════════════════════════════════

#v(0.3em)
#align(center)[
  #text(font: heading-font, size: 16pt, weight: "bold", fill: primary)[#cal-month — Weekly Content Plan]
]
#v(0.5em)

// ── Week headers ─────────────────────────────────────────────────────────────
#table(
  columns: (0.8fr, 1fr, 1fr, 1fr, 1fr, 1fr, 1fr, 1fr),
  stroke: 0.3pt + luma(200),
  inset: 6pt,
  fill: (x, y) => if y == 0 { primary } else if calc.even(y) { secondary } else { white },

  // Header row
  text(size: 8pt, fill: white, weight: "bold")[Week],
  text(size: 8pt, fill: white, weight: "bold")[Mon],
  text(size: 8pt, fill: white, weight: "bold")[Tue],
  text(size: 8pt, fill: white, weight: "bold")[Wed],
  text(size: 8pt, fill: white, weight: "bold")[Thu],
  text(size: 8pt, fill: white, weight: "bold")[Fri],
  text(size: 8pt, fill: white, weight: "bold")[Sat],
  text(size: 8pt, fill: white, weight: "bold")[Sun],

  // Week 1
  text(size: 8pt, weight: "bold")[Week 1 \ 1–6 Apr],
  [#badge("IG", ig-color) \ Product showcase],
  [#badge("FB", fb-color) \ Tips carousel],
  [#badge("BLOG", blog-color) \ SEO article],
  [#badge("IG", ig-color) \ Reel — BTS],
  [#badge("LI", li-color) \ Industry insight],
  [#badge("TT", tt-color) \ Trending audio],
  [],

  // Week 2
  text(size: 8pt, weight: "bold")[Week 2 \ 7–13 Apr],
  [#badge("IG", ig-color) \ Carousel — tips],
  [#badge("FB", fb-color) \ Client spotlight],
  [#event-highlight("Hari Raya") \ #badge("IG", ig-color) Greeting],
  [#badge("IG", ig-color) \ Story poll],
  [#badge("LI", li-color) \ Case study],
  [#badge("TT", tt-color) \ Tutorial],
  [],

  // Week 3
  text(size: 8pt, weight: "bold")[Week 3 \ 14–20 Apr],
  [#badge("IG", ig-color) \ Quote graphic],
  [#badge("FB", fb-color) \ Promo post],
  [#badge("BLOG", blog-color) \ How-to guide],
  [#badge("IG", ig-color) \ Reel — demo],
  [#badge("LI", li-color) \ Team feature],
  [#badge("TT", tt-color) \ Trending format],
  [],

  // Week 4
  text(size: 8pt, weight: "bold")[Week 4 \ 21–27 Apr],
  [#badge("IG", ig-color) \ Testimonial],
  [#badge("FB", fb-color) \ Event promo],
  [#badge("BLOG", blog-color) \ Listicle],
  [#badge("IG", ig-color) \ Collaboration],
  [#badge("LI", li-color) \ Thought piece],
  [#badge("TT", tt-color) \ Challenge],
  [],

  // Week 5
  text(size: 8pt, weight: "bold")[Week 5 \ 28–30 Apr],
  [#badge("IG", ig-color) \ Month recap],
  [#badge("FB", fb-color) \ Community Q&A],
  [#badge("BLOG", blog-color) \ Monthly roundup],
  [], [], [], [],
)

// ═════════════════════════════════════════════════════════════════════════════
// PLATFORM SUMMARY
// ═════════════════════════════════════════════════════════════════════════════

#v(1em)
#text(font: heading-font, size: 14pt, weight: "bold", fill: primary)[Platform Summary]
#v(0.4em)

#table(
  columns: (1fr, auto, auto, 2fr),
  stroke: 0.3pt + luma(200),
  inset: 8pt,
  fill: (x, y) => if y == 0 { primary } else { white },

  text(size: 9pt, fill: white, weight: "bold")[Platform],
  text(size: 9pt, fill: white, weight: "bold")[Posts],
  text(size: 9pt, fill: white, weight: "bold")[Frequency],
  text(size: 9pt, fill: white, weight: "bold")[Content Types],

  [#badge("IG", ig-color) Instagram], [12], [3×/week], [Carousels, Reels, Stories, Static posts],
  [#badge("FB", fb-color) Facebook], [8], [2×/week], [Links, Spotlights, Promos, Community],
  [#badge("LI", li-color) LinkedIn], [4], [1×/week], [Case studies, Thought leadership, Team features],
  [#badge("TT", tt-color) TikTok], [4], [1×/week], [Tutorials, Trending audio, Challenges],
  [#badge("BLOG", blog-color) Blog], [4], [1×/week], [SEO articles, How-to guides, Roundups],
)

// ═════════════════════════════════════════════════════════════════════════════
// KEY DATES & EVENTS
// ═════════════════════════════════════════════════════════════════════════════

#v(1em)
#text(font: heading-font, size: 14pt, weight: "bold", fill: primary)[Key Dates & Events]
#v(0.3em)

#table(
  columns: (auto, 1fr, auto),
  stroke: 0.3pt + luma(200),
  inset: 8pt,
  fill: (x, y) => if y == 0 { primary } else { white },

  text(size: 9pt, fill: white, weight: "bold")[Date],
  text(size: 9pt, fill: white, weight: "bold")[Event],
  text(size: 9pt, fill: white, weight: "bold")[Action],

  [10 Apr], [Hari Raya Aidilfitri], [Greeting post (IG + FB)],
  [22 Apr], [Earth Day], [Sustainability content (IG carousel)],
  [30 Apr], [Month-end], [Performance recap + next month preview],
)
