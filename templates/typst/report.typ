// ─────────────────────────────────────────────────────────────────────────────
// report.typ — Business report template (shorter than long-report.typ)
// Vizier — Typst 0.14.2, no external packages
//
// Sections: Cover, ToC, Executive Summary, Analysis, Findings, Recommendations
// ─────────────────────────────────────────────────────────────────────────────

// ── Brand inputs ─────────────────────────────────────────────────────────────
#let primary      = rgb(sys.inputs.at("primary_color",   default: "#1A1A2E"))
#let secondary    = rgb(sys.inputs.at("secondary_color", default: "#F0F0F5"))
#let accent       = rgb(sys.inputs.at("accent_color",    default: "#2563EB"))
#let heading-font = sys.inputs.at("headline_font", default: "Inter")
#let body-font    = sys.inputs.at("body_font",     default: "IBM Plex Serif")

#let report-title    = sys.inputs.at("title",       default: "Monthly Performance Report")
#let report-subtitle = sys.inputs.at("subtitle",    default: "")
#let report-client   = sys.inputs.at("client_name", default: "")
#let report-author   = sys.inputs.at("author",      default: "")
#let report-date     = sys.inputs.at("date",        default: "April 2026")
#let report-period   = sys.inputs.at("period",      default: "March 2026")

// ── Page setup ───────────────────────────────────────────────────────────────
#set page(
  paper: "a4",
  margin: (top: 2.5cm, bottom: 2cm, left: 2.5cm, right: 2cm),
  header: context {
    if counter(page).get().first() > 2 [
      #grid(
        columns: (1fr, 1fr),
        align: (left, right),
        text(size: 8pt, fill: luma(140))[#report-title],
        text(size: 8pt, fill: luma(140))[#report-period],
      )
      #line(length: 100%, stroke: 0.4pt + luma(200))
    ]
  },
  footer: context {
    if counter(page).get().first() > 1 [
      #align(center)[
        #text(size: 8pt, fill: luma(140))[#counter(page).display("1")]
      ]
    ]
  },
)

// ── Base typography ──────────────────────────────────────────────────────────
#set text(font: body-font, size: 11pt, fill: luma(30))
#set par(leading: 0.7em, spacing: 1.4em)

// ── Heading styles ───────────────────────────────────────────────────────────
#set heading(numbering: "1.1")

#show heading.where(level: 1): it => {
  v(1.5em)
  text(font: heading-font, size: 18pt, weight: "bold", fill: primary)[#it]
  v(0.4em)
  line(length: 100%, stroke: 0.5pt + luma(200))
  v(0.5em)
}

#show heading.where(level: 2): it => {
  v(1em)
  text(font: heading-font, size: 14pt, weight: "semibold", fill: primary)[#it]
  v(0.3em)
}

#show heading.where(level: 3): it => {
  v(0.6em)
  text(font: heading-font, size: 12pt, weight: "semibold", fill: primary.lighten(15%))[#it]
  v(0.2em)
}

// ── Table styling ────────────────────────────────────────────────────────────
#set table(stroke: 0.5pt + luma(200), inset: 8pt)
#show table.cell.where(y: 0): set text(fill: white, weight: "bold")
#show table.cell.where(y: 0): set block(fill: primary)

// ── Callout box ──────────────────────────────────────────────────────────────
#let callout(body) = {
  rect(
    width: 100%,
    inset: 14pt,
    radius: 4pt,
    fill: accent.lighten(90%),
    stroke: (left: 3pt + accent),
  )[#body]
}

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
  #rect(width: 100%, height: 7cm, fill: primary)[
    #pad(left: 2.5cm, right: 2.5cm, top: 2cm)[
      #text(font: heading-font, size: 28pt, weight: "bold", fill: white)[#report-title]
      #if report-subtitle != "" [
        #v(0.3em)
        #text(font: heading-font, size: 14pt, fill: white.darken(15%))[#report-subtitle]
      ]
    ]
  ]

  #pad(left: 2.5cm, right: 2.5cm, top: 2cm)[
    #line(length: 6cm, stroke: 1.5pt + accent)
    #v(1.5em)

    #if report-client != "" [
      #text(size: 12pt, fill: luma(50))[*Client:* #report-client] #v(0.3em)
    ]
    #if report-period != "" [
      #text(size: 12pt, fill: luma(50))[*Reporting Period:* #report-period] #v(0.3em)
    ]
    #if report-author != "" [
      #text(size: 12pt, fill: luma(50))[*Prepared by:* #report-author] #v(0.3em)
    ]
    #if report-date != "" [
      #text(size: 12pt, fill: luma(50))[*Date:* #report-date]
    ]
  ]
]

// ═════════════════════════════════════════════════════════════════════════════
// TABLE OF CONTENTS
// ═════════════════════════════════════════════════════════════════════════════
#page[
  #text(font: heading-font, size: 18pt, weight: "bold", fill: primary)[Contents]
  #v(0.6em)
  #line(length: 100%, stroke: 0.4pt + luma(200))
  #v(0.6em)
  #outline(indent: 1.5em, depth: 2)
]

// ═════════════════════════════════════════════════════════════════════════════
// SAMPLE CONTENT
// ═════════════════════════════════════════════════════════════════════════════

= Executive Summary

#callout[
  *Key Takeaway:* Social media engagement increased 42% month-over-month, driven by the Ramadan content series. Website traffic from organic search grew 18%. Two campaigns exceeded ROI targets.
]

This report covers digital marketing performance for #report-period across social media, content marketing, and paid advertising channels. Overall performance is trending positively, with three of four KPIs meeting or exceeding targets.

= Performance Overview

== Key Metrics

#table(
  columns: (1fr, auto, auto, auto),
  [*Metric*], [*Target*], [*Actual*], [*Status*],
  [Social Engagement Rate], [3.5%], [4.9%], [Above target],
  [Website Sessions], [12,000], [14,180], [Above target],
  [Lead Conversions], [85], [72], [Below target],
  [Email Open Rate], [22%], [24.3%], [Above target],
)

== Social Media Performance

Platform breakdown for the reporting period:

#table(
  columns: (1fr, auto, auto, auto, auto),
  [*Platform*], [*Posts*], [*Reach*], [*Engagement*], [*Growth*],
  [Instagram], [24], [45,200], [4.8%], [+320 followers],
  [Facebook], [18], [32,100], [3.2%], [+180 followers],
  [LinkedIn], [8], [12,400], [5.1%], [+95 followers],
  [TikTok], [12], [68,500], [6.4%], [+890 followers],
)

= Analysis

== Content Performance

The Ramadan content series (12 posts across Instagram and Facebook) was the top-performing content this month, achieving an average engagement rate of 7.2% — more than double the monthly average.

Top-performing content types:
+ *Cultural/seasonal content* — 7.2% average engagement
+ *Behind-the-scenes posts* — 5.4% average engagement
+ *Educational carousels* — 4.8% average engagement
+ *Product showcases* — 3.1% average engagement

== Channel Analysis

=== Organic Search

Organic search traffic grew 18% month-over-month. The blog article "Panduan Pemasaran Digital untuk PKS Malaysia" drove 2,400 sessions — now the #1 organic landing page.

=== Paid Advertising

Total ad spend: MYR 4,200. Return on ad spend (ROAS): 3.8×. The lead generation campaign underperformed (72 vs 85 target), likely due to form length. Recommendation: A/B test a shorter form variant.

= Recommendations

+ *Scale Ramadan content approach* to future cultural moments (Hari Raya, Merdeka, Malaysia Day)
+ *Shorten lead capture form* from 8 fields to 5 — test impact on conversion rate
+ *Increase TikTok investment* — highest engagement rate and fastest follower growth
+ *Publish 2 additional blog articles* targeting high-volume BM search queries
+ *Implement email automation* for lead nurturing (currently manual follow-up)

= Appendix

== Methodology

All metrics sourced from platform-native analytics (Meta Business Suite, LinkedIn Analytics, Google Analytics 4, TikTok Business Centre). Engagement rate calculated as (likes + comments + shares + saves) ÷ reach × 100.

== Glossary

- *ROAS* — Return on Ad Spend. Revenue generated per ringgit spent on advertising.
- *CTR* — Click-Through Rate. Percentage of impressions that resulted in a click.
- *PKS* — Perusahaan Kecil dan Sederhana (Small and Medium Enterprises).
