// ─────────────────────────────────────────────────────────────────────────────
// company_profile.typ — Company profile template
// Vizier — Typst 0.14.2, no external packages
//
// Sections: Hero cover, About, Services, Portfolio, Team, Contact
// ─────────────────────────────────────────────────────────────────────────────

// ── Brand inputs ─────────────────────────────────────────────────────────────
#let primary      = rgb(sys.inputs.at("primary_color",   default: "#0F172A"))
#let secondary    = rgb(sys.inputs.at("secondary_color", default: "#F8FAFC"))
#let accent       = rgb(sys.inputs.at("accent_color",    default: "#0EA5E9"))
#let heading-font = sys.inputs.at("headline_font", default: "Plus Jakarta Sans")
#let body-font    = sys.inputs.at("body_font",     default: "Inter")

#let company-name    = sys.inputs.at("company_name", default: "Syarikat Contoh Sdn Bhd")
#let company-tagline = sys.inputs.at("tagline",      default: "Digital Solutions for Modern Businesses")
#let company-ssm     = sys.inputs.at("ssm_number",   default: "202401012345 (1234567-A)")
#let company-phone   = sys.inputs.at("phone",        default: "+60 3-1234 5678")
#let company-email   = sys.inputs.at("email",        default: "hello@contoh.com.my")
#let company-web     = sys.inputs.at("website",      default: "www.contoh.com.my")
#let company-address = sys.inputs.at("address",      default: "Level 10, Menara Example, Jalan Ampang, 50450 Kuala Lumpur")

// ── Page setup ───────────────────────────────────────────────────────────────
#set page(
  paper: "a4",
  margin: (top: 2cm, bottom: 2cm, left: 2cm, right: 2cm),
  footer: context {
    if counter(page).get().first() > 1 [
      #line(length: 100%, stroke: 0.4pt + luma(200))
      #v(0.3em)
      #grid(
        columns: (1fr, 1fr),
        align: (left, right),
        text(size: 8pt, fill: luma(140))[#company-name],
        text(size: 8pt, fill: luma(140))[#counter(page).display("1")],
      )
    ]
  },
)

// ── Base typography ──────────────────────────────────────────────────────────
#set text(font: body-font, size: 10.5pt, fill: luma(30))
#set par(leading: 0.7em, spacing: 1.3em)

// ── Heading styles ───────────────────────────────────────────────────────────
#show heading.where(level: 1): it => {
  v(1em)
  text(font: heading-font, size: 22pt, weight: "bold", fill: primary)[#it.body]
  v(0.3em)
  line(length: 50%, stroke: 2pt + accent)
  v(0.6em)
}

#show heading.where(level: 2): it => {
  v(0.8em)
  text(font: heading-font, size: 14pt, weight: "semibold", fill: primary)[#it.body]
  v(0.3em)
}

// ── Utility: stat card ───────────────────────────────────────────────────────
#let stat-card(number, label) = {
  box(
    width: 100%,
    inset: 16pt,
    radius: 6pt,
    fill: secondary,
    stroke: 0.5pt + luma(220),
  )[
    #align(center)[
      #text(font: heading-font, size: 24pt, weight: "bold", fill: accent)[#number]
      #v(0.2em)
      #text(size: 9pt, fill: luma(100))[#label]
    ]
  ]
}

// ── Utility: service card ────────────────────────────────────────────────────
#let service-card(title, description) = {
  box(
    width: 100%,
    inset: 16pt,
    radius: 6pt,
    fill: secondary,
    stroke: 0.5pt + luma(220),
  )[
    #text(font: heading-font, size: 12pt, weight: "bold", fill: primary)[#title]
    #v(0.4em)
    #text(size: 10pt, fill: luma(60))[#description]
  ]
}

// ═════════════════════════════════════════════════════════════════════════════
// HERO COVER
// ═════════════════════════════════════════════════════════════════════════════
#page(
  margin: (rest: 0pt),
  footer: none,
)[
  // Full-width primary background
  #rect(width: 100%, height: 100%, fill: primary)[
    #pad(left: 3cm, right: 3cm, top: 6cm)[
      // Accent line
      #rect(width: 4cm, height: 4pt, fill: accent)
      #v(1em)

      #text(font: heading-font, size: 36pt, weight: "bold", fill: white)[#company-name]
      #v(0.6em)
      #text(font: heading-font, size: 16pt, fill: accent)[#company-tagline]

      #v(4em)
      #text(size: 11pt, fill: white.darken(20%))[SSM: #company-ssm]
      #v(0.3em)
      #text(size: 11pt, fill: white.darken(20%))[#company-web]
    ]
  ]
]

// ═════════════════════════════════════════════════════════════════════════════
// ABOUT US
// ═════════════════════════════════════════════════════════════════════════════

= About Us

#company-name is a Malaysian digital solutions company founded in 2024. We specialise in helping businesses build compelling digital presences through strategic content, visual design, and data-driven marketing.

Headquartered in Kuala Lumpur, our team of 15 professionals serves clients across Malaysia, Singapore, and Indonesia. We combine deep local market knowledge with global best practices to deliver results that matter.

== Our Mission

To empower Malaysian businesses with world-class digital tools and strategies, making professional-grade marketing accessible to companies of every size.

== By the Numbers

#grid(
  columns: (1fr, 1fr, 1fr, 1fr),
  column-gutter: 12pt,
  stat-card("50+", "Clients Served"),
  stat-card("500+", "Projects Delivered"),
  stat-card("98%", "Client Retention"),
  stat-card("15", "Team Members"),
)

// ═════════════════════════════════════════════════════════════════════════════
// SERVICES
// ═════════════════════════════════════════════════════════════════════════════

= Our Services

#grid(
  columns: (1fr, 1fr),
  column-gutter: 12pt,
  row-gutter: 12pt,
  service-card(
    "Digital Marketing",
    "Comprehensive digital marketing strategy covering social media, SEO, SEM, and email campaigns. We plan, execute, and optimise for measurable growth.",
  ),
  service-card(
    "Content Creation",
    "Bilingual content production (BM/EN) including social media posts, blog articles, email newsletters, and marketing copy tailored to Malaysian audiences.",
  ),
  service-card(
    "Visual Design",
    "Professional visual asset creation for social media, marketing collateral, presentations, and brand identity. From posters to full brand guidelines.",
  ),
  service-card(
    "Data & Analytics",
    "Performance tracking, audience insights, and strategic reporting. We turn data into actionable recommendations for continuous improvement.",
  ),
)

// ═════════════════════════════════════════════════════════════════════════════
// PORTFOLIO HIGHLIGHTS
// ═════════════════════════════════════════════════════════════════════════════

= Portfolio Highlights

#table(
  columns: (1fr, auto, 1fr),
  stroke: none,
  inset: 10pt,
  table.hline(stroke: 0.5pt + luma(200)),
  [*Client*], [*Industry*], [*Key Result*],
  table.hline(stroke: 0.5pt + luma(200)),
  [Restoran Warisan], [F&B], [+180% social engagement in 3 months],
  table.hline(stroke: 0.3pt + luma(230)),
  [KL Tech Hub], [Technology], [500+ leads from content marketing campaign],
  table.hline(stroke: 0.3pt + luma(230)),
  [Batik Nusantara], [Fashion/Retail], [2× online sales through visual branding refresh],
  table.hline(stroke: 0.3pt + luma(230)),
  [EduPath Academy], [Education], [10,000+ newsletter subscribers in 6 months],
  table.hline(stroke: 0.5pt + luma(200)),
)

// ═════════════════════════════════════════════════════════════════════════════
// TEAM
// ═════════════════════════════════════════════════════════════════════════════

= Our Team

#let team-member(name, role, bio) = {
  box(
    width: 100%,
    inset: 14pt,
    radius: 6pt,
    fill: secondary,
    stroke: 0.5pt + luma(220),
  )[
    #text(font: heading-font, size: 12pt, weight: "bold", fill: primary)[#name]
    #h(1em)
    #text(size: 10pt, fill: accent, weight: "semibold")[#role]
    #v(0.3em)
    #text(size: 10pt, fill: luma(60))[#bio]
  ]
}

#grid(
  columns: (1fr, 1fr),
  column-gutter: 12pt,
  row-gutter: 12pt,
  team-member(
    "Ahmad Razak",
    "Managing Director",
    "15 years in digital marketing. Former agency lead at a top-5 Malaysian agency.",
  ),
  team-member(
    "Siti Nurhaliza",
    "Creative Director",
    "Award-winning designer specialising in brand identity and visual storytelling.",
  ),
  team-member(
    "Raj Kumar",
    "Head of Strategy",
    "Data-driven strategist with experience across FMCG, tech, and F&B sectors.",
  ),
  team-member(
    "Lim Wei Ting",
    "Technical Lead",
    "Full-stack developer and automation specialist. Builds the tools that scale our delivery.",
  ),
)

// ═════════════════════════════════════════════════════════════════════════════
// CONTACT
// ═════════════════════════════════════════════════════════════════════════════

= Contact Us

#v(0.5em)
#grid(
  columns: (auto, 1fr),
  column-gutter: 12pt,
  row-gutter: 10pt,
  text(weight: "bold")[Address:], [#company-address],
  text(weight: "bold")[Phone:], [#company-phone],
  text(weight: "bold")[Email:], [#company-email],
  text(weight: "bold")[Website:], [#company-web],
  text(weight: "bold")[SSM:], [#company-ssm],
)

#v(2em)
#align(center)[
  #rect(
    width: 80%,
    inset: 20pt,
    radius: 8pt,
    fill: primary,
  )[
    #text(font: heading-font, size: 14pt, fill: white, weight: "bold")[
      Ready to grow your digital presence?
    ]
    #v(0.3em)
    #text(size: 11pt, fill: accent)[
      Contact us today for a free consultation.
    ]
  ]
]
