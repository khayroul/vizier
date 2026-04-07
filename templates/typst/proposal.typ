// ─────────────────────────────────────────────────────────────────────────────
// proposal.typ — Business proposal template
// Vizier — Typst 0.14.2, no external packages
//
// Sections: Cover, ToC, Executive Summary, Problem, Solution, Timeline,
//           Investment, Team, Appendix
// ─────────────────────────────────────────────────────────────────────────────

// ── Brand inputs ─────────────────────────────────────────────────────────────
#let primary      = rgb(sys.inputs.at("primary_color",   default: "#1A1A2E"))
#let secondary    = rgb(sys.inputs.at("secondary_color", default: "#F0F0F5"))
#let accent       = rgb(sys.inputs.at("accent_color",    default: "#2563EB"))
#let heading-font = sys.inputs.at("headline_font", default: "Plus Jakarta Sans")
#let body-font    = sys.inputs.at("body_font",     default: "IBM Plex Serif")

#let proposal-title    = sys.inputs.at("title",       default: "Business Proposal")
#let proposal-subtitle = sys.inputs.at("subtitle",    default: "")
#let proposal-client   = sys.inputs.at("client_name", default: "")
#let proposal-author   = sys.inputs.at("author",      default: "")
#let proposal-date     = sys.inputs.at("date",        default: "")
#let proposal-ref      = sys.inputs.at("reference",   default: "")

// ── Page setup ───────────────────────────────────────────────────────────────
#set page(
  paper: "a4",
  margin: (top: 2.5cm, bottom: 2cm, inside: 2.5cm, outside: 2cm),
  header: context {
    if counter(page).get().first() > 2 [
      #set text(size: 8pt, fill: luma(140))
      #grid(
        columns: (1fr, 1fr),
        align: (left, right),
        [#proposal-title], [#proposal-ref],
      )
      #line(length: 100%, stroke: 0.4pt + luma(200))
    ]
  },
  footer: context {
    if counter(page).get().first() > 1 [
      #align(center)[
        #set text(size: 8pt, fill: luma(140))
        #counter(page).display("1")
      ]
    ]
  },
)

// ── Base typography ──────────────────────────────────────────────────────────
#set text(font: body-font, size: 11pt, fill: luma(30))
#set par(leading: 0.7em, spacing: 1.4em)

// ── Heading styles ───────────────────────────────────────────────────────────
#set heading(numbering: "1.")

#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  v(1.5em)
  text(font: heading-font, size: 20pt, weight: "bold", fill: primary)[#it]
  v(0.5em)
  line(length: 60%, stroke: 1.5pt + accent)
  v(0.8em)
}

#show heading.where(level: 2): it => {
  v(1em)
  text(font: heading-font, size: 15pt, weight: "semibold", fill: primary)[#it]
  v(0.4em)
}

#show heading.where(level: 3): it => {
  v(0.6em)
  text(font: heading-font, size: 12pt, weight: "semibold", fill: primary.lighten(15%))[#it]
  v(0.3em)
}

// ── Table styling ────────────────────────────────────────────────────────────
#set table(stroke: 0.5pt + luma(200), inset: 8pt)
#show table.cell.where(y: 0): set text(fill: white, weight: "bold")
#show table.cell.where(y: 0): set block(fill: primary)

// ── Links ────────────────────────────────────────────────────────────────────
#show link: set text(fill: accent)

// ═════════════════════════════════════════════════════════════════════════════
// COVER PAGE
// ═════════════════════════════════════════════════════════════════════════════
#page(
  margin: (rest: 0pt),
  header: none,
  footer: none,
)[
  // Top accent bar
  #rect(width: 100%, height: 1cm, fill: accent)

  // Left colour strip + content
  #grid(
    columns: (6mm, 1fr),
    rect(width: 100%, height: 100% - 1cm, fill: primary),
    pad(left: 2.5cm, right: 2.5cm, top: 4cm)[
      #text(font: heading-font, size: 32pt, weight: "bold", fill: primary)[#proposal-title]

      #if proposal-subtitle != "" [
        #v(0.4em)
        #text(font: heading-font, size: 16pt, fill: luma(80))[#proposal-subtitle]
      ]

      #v(2em)
      #line(length: 6cm, stroke: 1.5pt + accent)
      #v(2em)

      #if proposal-client != "" [
        #text(size: 12pt, fill: luma(50))[*Prepared for:* #proposal-client]
        #v(0.4em)
      ]
      #if proposal-author != "" [
        #text(size: 12pt, fill: luma(50))[*Prepared by:* #proposal-author]
        #v(0.4em)
      ]
      #if proposal-date != "" [
        #text(size: 12pt, fill: luma(50))[*Date:* #proposal-date]
        #v(0.4em)
      ]
      #if proposal-ref != "" [
        #text(size: 12pt, fill: luma(50))[*Reference:* #proposal-ref]
      ]
    ],
  )
]

// ═════════════════════════════════════════════════════════════════════════════
// TABLE OF CONTENTS
// ═════════════════════════════════════════════════════════════════════════════
#page[
  #text(font: heading-font, size: 20pt, weight: "bold", fill: primary)[Contents]
  #v(0.6em)
  #line(length: 100%, stroke: 0.4pt + luma(200))
  #v(0.6em)
  #outline(indent: 1.5em, depth: 2)
]

// ═════════════════════════════════════════════════════════════════════════════
// SAMPLE CONTENT — renders a complete proposal
// ═════════════════════════════════════════════════════════════════════════════

= Executive Summary

This proposal outlines a comprehensive digital marketing strategy designed to elevate brand presence across key platforms in Malaysia. Our approach combines data-driven insights with culturally resonant content creation to deliver measurable results within the first quarter.

The proposed engagement covers content strategy, visual asset production, and performance tracking across social media, search, and display channels.

= Problem Statement

== Current Challenges

The client currently faces the following challenges in the Malaysian digital landscape:

- *Inconsistent brand voice* across platforms and languages (BM/EN)
- *Low engagement rates* on social media content (below industry benchmark of 3.2%)
- *Manual content production* processes that limit output to 8–12 assets per month
- *No systematic quality assurance* framework for published content

== Market Context

The Malaysian digital advertising market continues to grow at 15% CAGR, with social media penetration reaching 91.7% of the population. Bilingual content (Bahasa Melayu and English) is essential for reaching both urban and suburban demographics.

= Proposed Solution

== Strategy Overview

#table(
  columns: (auto, 1fr, auto),
  [*Phase*], [*Description*], [*Duration*],
  [Discovery], [Brand audit, competitor analysis, audience research], [2 weeks],
  [Foundation], [Style guide, template library, content calendar], [2 weeks],
  [Production], [Ongoing content creation and publishing], [Ongoing],
  [Optimisation], [Performance analysis and strategy refinement], [Monthly],
)

== Deliverables

+ *Content Strategy Document* — comprehensive roadmap covering 6 months
+ *Visual Asset Library* — 40+ templates for social media, documents, and marketing
+ *Monthly Content Package* — 30 social posts, 4 blog articles, 2 email campaigns
+ *Performance Dashboard* — real-time tracking of KPIs and engagement metrics

= Timeline

== Project Milestones

#table(
  columns: (auto, 1fr, auto),
  [*Milestone*], [*Deliverable*], [*Date*],
  [M1], [Discovery report and brand audit], [Week 2],
  [M2], [Style guide and template library], [Week 4],
  [M3], [First content batch (Month 1)], [Week 6],
  [M4], [Performance review and optimisation], [Week 8],
)

= Investment

== Pricing

#table(
  columns: (1fr, auto),
  [*Item*], [*Amount (MYR)*],
  [Discovery & Strategy], [8,000],
  [Template & Asset Library (one-time)], [12,000],
  [Monthly Content Production], [6,500/month],
  [Performance Reporting], [1,500/month],
  [*Total (Month 1)*], [*28,000*],
  [*Monthly Recurring*], [*8,000*],
)

== Payment Terms

- 50% upon signing, 50% upon delivery of each milestone
- Monthly retainer invoiced on the 1st of each month, payable within 14 days
- All prices are exclusive of SST (6%)

= Team

Our team brings together expertise in content strategy, visual design, and data analytics:

- *Project Lead* — 10+ years in digital marketing strategy for Malaysian brands
- *Content Strategist* — bilingual content specialist (BM/EN) with SEO expertise
- *Visual Designer* — specialist in social media and marketing asset production
- *Data Analyst* — performance tracking, A/B testing, and optimisation

= Appendix

== Terms & Conditions

+ All intellectual property created during the engagement transfers to the client upon full payment.
+ Confidential information shared during the engagement is protected under NDA.
+ Either party may terminate the agreement with 30 days written notice.
+ Service level agreement: 48-hour response time for urgent requests.
