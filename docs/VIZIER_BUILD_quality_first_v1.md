# Vizier Build Plan: Quality-First Revision

**Date:** 2026-04-11  
**Revises:** `docs/VIZIER_BUILD_v1_3_1.md`  
**Goal:** By S21, Vizier must produce sellable posters and commercially usable illustrated books / ebooks.  
**Optimization target:** output quality by S21, not architecture completeness.

---

## S21 Success Criteria

By the end of S21, all of this must be true:

### Posters

- governed poster flow produces clean, professional output at least at a strong Canva free-tier floor
- template selection is driven by a meaningful layout corpus, not a tiny hand-made pool
- user can arrive with a thin brief and the system helps recover enough detail
- clientless requests still map to a reasonable niche benchmark
- post-render QA and governed acceptance proof are green

### Illustrated children's books / ebooks

- children's book flow can produce complete, consistent PDF + EPUB deliverables
- characters remain visually stable page-to-page
- text pacing and composition are commercially coherent
- ebook and long-form assembly are print-ready / deliverable
- these flows are truthfully marked deliverable in the governed matrix

### Operational minimum

- every job has usable cost trace by stage and model family
- deliverability truth matches runtime truth
- at least one governed acceptance suite per launch lane is green

---

## Core Principles

1. Sell one vertical before generalizing.
2. Template and taste ingestion come before clever routing.
3. A quality gate is only worth building after the artifact exists end-to-end.
4. Dataset work is incomplete until a runtime artifact consumes it.
5. A workflow is not "launch-ready" unless the governed entrypoint can deliver it.
6. Ops, dashboards, and self-improvement loops are post-proof work unless they directly unlock sellable output.

---

## Template Ingestion Strategy

### Grouping model

Primary grouping:

- `artifact_type -> layout_archetype -> use_case_or_niche`

Examples:

- `poster -> hero_offer -> food_promo`
- `poster -> editorial_split -> property_launch`
- `book_layout -> picture_text_below -> age_5_7`
- `ebook -> chapter_feature_open -> lead_magnet`

Secondary metadata:

- `source` (`canva`, `envato`, operator-made)
- `language`
- `region`
- `density`
- `cta_style`
- `industry`
- `tone`
- `audience`
- `quality_tier`
- `layout_notes`
- `text_zone_strategy`
- `why_selected`

### Why not group by source?

Source is provenance, not runtime utility.

Source helps with:

- license/provenance tracking
- taste analysis
- operator trust

But layout archetype helps with:

- render-template generation
- selection quality
- benchmark matching
- screenshot/photo adaptation

### Ingestion pipeline

1. Operator curates 100-200 references manually.
2. Convert PDFs/pages/screenshots into normalized PNG assets.
3. Auto-tag into a manifest with layout, niche, density, CTA, palette, and text-zone metadata.
4. Split the corpus into three layers:
   - `locked benchmark set`
   - `runtime exemplar set`
   - `layout blueprint set`
5. Promote 15-25 strongest references into locked acceptance/benchmark anchors.
6. Promote 20-40 into runtime exemplar retrieval.
7. Promote 10-20 into direct render blueprints or template specs.

### How they should influence output

- `selection`: choose layout family and template candidates
- `prompting`: provide taste anchors and composition hints
- `QA`: compare against locked benchmark expectations
- `matching`: when no client exists, map to same-industry / same-archetype references
- `adaptation`: screenshot/photo cloning should align to a known archetype and text-zone pattern

---

## Revised Session Order

## Phase 1: Poster Sellability First

| Session | Purpose | Why it moves here |
|---|---|---|
| S0 | Sellable rubric + governed acceptance harness + baseline audit | Quality must be measurable before architecture expands |
| S1 | Poster render spine: HTML/Playwright/Typst, copy overlay, real delivery packet | This is the first artifact customers will judge |
| S2 | Poster production loop: copy, image routing, no-text discipline, real post-render QA | Good posters need a real loop before governance sophistication |
| S3 | Curated template ingestion pipeline for operator references | Template/taste quality is more important than routing elegance |
| S4 | Template selector + metadata schema + benchmark matching shell | Selection only matters after worthwhile choices exist |
| S5 | Brief interpreter + bridge coaching + content gates | Thin-brief rescue must happen before wasting image tokens |
| S6 | Dataset transformation for poster structure: D4 clustering -> templates | This is the real S5/S-DATA work that should have been critical path |
| S7 | D5 industry tagging + D9 text-zone/saliency validation | Makes the template pool usable, not just large |
| S8 | Poster QA calibration: NIMA config + operator benchmark floor + governed acceptance green | Poster lane must be credibly sellable before anything else expands |

### Exit gate after S8

Must be true before moving on:

- poster acceptance suite is green through governed entrypoint
- template corpus is broad enough to cover major niches
- clientless poster request can choose a sane niche benchmark
- thin-brief flow produces coaching instead of silent low-quality generation

## Phase 2: Books and Ebooks Become Core, Not Extended

| Session | Purpose | Why it moves here |
|---|---|---|
| S9 | Publishing contracts trimmed to only what books/ebooks need | Publishing cannot stay blocked behind unrelated governance scope |
| S10 | Assembly foundation: Typst/EPUB/page composition/text zones | Delivery quality for books is as important as generation quality |
| S11 | Illustration pipeline consistency: character refs, iterative edits, anchor frames | This is the real quality core for illustrated books |
| S12 | Children's book story scaffold + pacing + print-ready page rules | Commercial pacing must exist before orchestration polish |
| S13 | End-to-end children's book specimen -> full governed pipeline | Books need the same governed proof posters got |
| S14 | Ebook long-form lane: section generation, rolling context, assembly | Ebook sellability is not an "extended lane"; it is a launch lane |
| S15 | Book/ebook QA + delivery truthfulness + acceptance gates | A lane is not done until it is both good and honestly deliverable |

### Exit gate after S15

Must be true before moving on:

- children's book flow is green through governed delivery
- ebook flow is green through governed delivery
- workflow registry truth matches runtime truth for these lanes

## Phase 3: Only Now Add General Infrastructure

| Session | Purpose | Why it moves later |
|---|---|---|
| S16 | Minimal governance hardening: policy, readiness, contracts needed by live lanes | Governance now protects something real |
| S17 | Core data foundation only for active lanes: jobs, artifacts, assets, deliveries, traces | Trim the schema to what live output actually uses |
| S18 | Exemplar retrieval + benchmark retrieval + clientless niche matching | Now the exemplar system has real template/taste material to consume |
| S19 | Cost observability by job/stage/model + launch diagnostics | Cost tracking matters once real lanes exist |
| S20 | Calibration and experiments that do not require large production history | Controlled pre-production improvement, not full self-improvement theater |
| S21 | Launch hardening: acceptance freeze, deliverability audit, polish pass across posters/books/ebooks | S21 becomes the launch-quality freeze, not a place to first add core lanes |

---

## What Moves, Merges, or Gets Cut

### Move later

- original `S6`, `S7`, `S8` governance/observability work
- most of original `S10a` data-foundation breadth
- original `S16` BizOps / Steward
- original `S17` Dashboard
- most of original `S18` Knowledge Spine
- most of original `S19` self-improvement loop

### Pull earlier

- original S15 publishing work
- original S21 children's book / ebook expansion
- post-S21 quality-intelligence work: D4 templates, D5 industry tagging, coaching, NIMA config, operator exemplar ingestion

### Merge

- original S5 dataset extraction + later S-DATA sprint -> one early quality-intelligence track
- original poster hardening and later acceptance work -> one continuous poster sellability track

### Cut from pre-S21 critical path

- dashboard
- steward / BizOps
- broad knowledge-spine architecture
- drift detection and experiment dashboards that need live production data
- any multi-model prose optimization beyond what directly improves launch output

These become post-S21 unless they directly unblock sellable output.

---

## Session-by-Session Acceptance Focus

Every session must end with one of these proofs:

- a governed artifact was delivered and judged acceptable
- an upstream artifact is consumed at runtime by a downstream component
- a benchmark or acceptance suite proves the quality delta

Examples:

- Template session proof:
  - a food brief selects a food-aligned template from the real template pool
- Coaching session proof:
  - a thin Malay brief returns helpful structured coaching and then succeeds on second pass
- Book session proof:
  - a sample children's book produces stable character identity and deliverable PDF + EPUB through the governed path

No session is allowed to ship with only isolated contract or stub tests.

---

## Must Exist By S21 vs Post-S21

### Must exist by S21

- posters at strong Canva free-tier floor
- governed poster proof suite green
- curated operator reference ingestion
- template corpus broad enough for key niches
- clientless niche matching
- structured coaching for incomplete briefs
- children's book governed delivery
- ebook governed delivery
- per-job cost trace good enough for operator diagnosis

### Can wait until post-S21

- steward / BizOps
- dashboard and remote access polish
- full knowledge-spine ambitions
- self-improvement loops that depend on production ratings
- local model training
- social/video/post-sprint expansion lanes

---

## Why This Plan Is Better

This plan treats the customer's judgment as the real architecture boundary.

The first half of the build is about:

- what the user sees
- what gets delivered
- whether the artifact looks professional
- whether the system rescues bad input

Only after that do we spend serious session budget on:

- governance breadth
- observability sophistication
- dashboarding
- self-improvement loops

That is the sequence the original build ended up discovering the hard way through post-S21 remediation.
