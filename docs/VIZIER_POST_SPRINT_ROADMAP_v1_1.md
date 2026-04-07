# VIZIER — POST-SPRINT ROADMAP

**Version:** 1.1.0  
**Date:** 7 April 2026  
**Status:** Post-sprint execution plan. Companion to VIZIER_BUILD.md (v1.3.1).  
**Prerequisite:** Core + Publishing ships from 3-day sprint. Revenue flowing from children's books.

**Changes from v1.0.0:** Added S11 Enhancement (client template export/import, ~30 lines). Added S19 benchmark additions (Sonnet 4.6, Flash-Lite, Anthropic web search). Both are Phase 1 items requiring no architectural change.

---

## Principles

R1 — Revenue lanes first. Every session either directly produces revenue or unblocks a revenue lane.  
R2 — One session, one capability. Ship and move on.  
R3 — Content before apps. Content production uses the existing engine. Apps need S27.  
R4 — Each product line reuses the same engine. One creative workshop → multiple formats → multiple channels.  
R5 — Config before code. If a new capability only needs config files and a workflow YAML, it's not a session — it's an afternoon.

---

## Phase 1: Revenue Acceleration (Week 1-2, parallel with book production)

These sessions run alongside daily book production. Each is 3-4 hours. They extend Core capabilities to serve existing clients and open new revenue channels.

### S22 — YouTube Research Pipeline

```
duration: 3-4 hours
depends_on: [S12]
revenue_impact: Enriches content calendars, grounds production in competitor data
```

YouTube competitor research + transcript extraction for client industries. Feeds into knowledge cards that make content calendars and social posts informed rather than generic. Existing tool deps (yt-dlp, youtube-transcript-api) already in pyproject.toml.

### S23 — Education Content Production (CONFIG ONLY — no code)

```
duration: 4-6 hours (config authoring, not coding)
depends_on: [Core ship]
revenue_impact: DIRECT — worksheet PDFs on Shopee, RM 5-15 per set
```

This is NOT a build session. It's config authoring that unlocks education content from the existing engine:

- `config/education/kssr_structure.yaml` — all subjects × year levels × topics (Tahun 1-6)
- `config/education/kssm_structure.yaml` — Form 1-5 subjects × topics
- `config/education/spm_structure.yaml` — SPM exam format (Bahagian A/B/C per subject)
- `config/personas/education_content_bm.md` — BM education content expert persona
- `config/vocab/bm_education_primary.yaml` — primary school BM terminology
- `config/vocab/bm_education_secondary.yaml` — secondary school terminology
- `config/quality_frameworks/question_quality.md` — quality dimensions: curriculum alignment, difficulty calibration, mathematical/scientific accuracy, BM clarity, worked solution completeness
- `config/document_scaffolds/worksheet_kssr.yaml` — worksheet structure per subject
- `config/document_scaffolds/exam_paper_spm.yaml` — SPM exam paper format
- `config/critique_templates/education_accuracy.md` — factual accuracy + curriculum alignment checker
- `manifests/workflows/education_content_production.yaml` — workflow YAML

**Exit criteria:**

- "Buat 30 soalan Matematik Tahun 4 topik Pecahan" → produces 30 questions with answers + explanations in BM
- Typst renders worksheet PDF matching Malaysian school format
- Quality gate catches: wrong difficulty for year level, non-curriculum topic, BM naturalness issues
- First worksheet set listed on Shopee

**Revenue from Day 1 of this session.** Each worksheet set (30 questions per topic) costs near-zero to produce, sells for RM 5-15. Cover all Tahun 4-6 Matematik + Sains topics in Week 1 = 40+ worksheet sets live.

### S24 — Social Platform Publishers

```
duration: 3-4 hours
depends_on: [S10a]
revenue_impact: Client retainers — automated social posting reduces manual work
prerequisite: Meta Business verification (apply during sprint — takes weeks)
```

Social media posting automation for client accounts. Instagram, Facebook, TikTok integration. draft-approve autonomy model. Content batch workflow produces platform-adapted variants.

### S30 — Story Narration Tool

```
duration: 2-3 hours
depends_on: [S15]
revenue_impact: Enables video + audiobook formats from existing book production
new_code: ~20 lines (tools/narrate.py)
```

Page text → ElevenLabs (Pro, already subscribed) or edge-tts → audio clip per page. One tool that takes a completed book's page texts and produces narration audio for each page.

**Exit criteria:**

- 8-page children's book → 8 audio clips, natural BM narration
- Audio duration matches reading pace for target age group (slower for 3-5, normal for 5-7)
- Can switch between ElevenLabs (high quality) and edge-tts (free, acceptable quality)

### S11 Enhancement — Client Template Export/Import

```
duration: 1-2 hours
depends_on: [Core ship]
revenue_impact: Faster onboarding → faster time-to-first-invoice for new clients
new_code: ~30 lines (tools/onboarding.py)
```

Standardised export/import for client configurations. `export_client_template(client_id)` produces sanitised YAML (brand config, workflow overrides, quality posture, copy register, design system preferences — no API keys, no financials). `import_client_template(template_path, new_client_id)` populates new client config from template. Operator reviews and adjusts before first production job. Accelerates Ring 3 data compounding — each new client inherits learned patterns from similar clients.

### S19 Benchmark Additions (April 2026 Market Context)

When S19 runs (Month 3+), include these additional benchmark candidates alongside the original 10 briefs × Claude/Gemini/GPT × EN+BM plan:

- **Claude Sonnet 4.6 vs Opus 4.6 for `en_creative`.** Sonnet 4.6 delivers near-Opus quality at ~40% lower cost. If Sonnet matches Opus on EN creative prose for marketing copy, use Sonnet and reserve Opus for fiction/narratives only.
- **Gemini 3.1 Flash-Lite for `routing` and `classification`.** At $0.25/M input, Flash-Lite may match fine-tuned Qwen 2B at comparable latency without the training investment.
- **Anthropic native web search vs Tavily for research pipeline.** Anthropic web search is now GA and free with code execution. Test coverage and quality for Malaysian market research queries.

---

## Phase 2: Multi-Format Production (Week 3-4)

These sessions transform single-format production into multi-format. One story → book + video + song + app content.

### S31 — Video Assembly Tool

```
duration: 3-4 hours
depends_on: [S30]
revenue_impact: YouTube channel + video sales
new_code: ~50 lines (tools/video_assembly.py)
```

Illustrations + narration clips + transitions + background music → video. Remotion (React-based, programmatic) or FFmpeg (CLI, simpler). For 8-page children's stories, the video is 2-3 minutes: illustration displayed while narration plays, fade transition between pages, gentle background music.

**Exit criteria:**

- 8-page book → 2-3 minute .mp4 video
- Transitions between pages are smooth (fade or slide)
- Background music doesn't overpower narration
- Thumbnail auto-generated from cover illustration
- Video uploadable to YouTube directly

### S32 — Song Generation Tool

```
duration: 2-3 hours
depends_on: [S15]
revenue_impact: Spotify/Apple Music + app content + YouTube
new_code: ~30 lines (tools/song_generate.py)
```

StoryBible (theme, lesson, vocabulary) + NarrativeScaffold (emotional arc) + character names → prompt → Suno API → children's song in BM. The song captures the story's moral in a catchy, age-appropriate format.

**Exit criteria:**

- "Ahmad Belajar Membatik" story → 1-2 minute BM children's song about patience and batik
- Song is age-appropriate (simple melody, repetitive chorus, clear BM lyrics)
- Lyrics extractable for karaoke display in app
- Audio quality suitable for Spotify upload

### S33 — Multi-Format Story Workflow

```
duration: 2-3 hours
depends_on: [S30, S31, S32]
revenue_impact: Combines all formats into one production pipeline
new_code: ~40 lines (workflow YAML + orchestration)
```

One workflow YAML that chains: book production → narration → video assembly → song generation → multi-channel publish.

```yaml
# manifests/workflows/story_multiformat.yaml
name: story_multiformat
posture: production
creative_workshop: derivative  # or true for new style
stages:
  - name: book_production
    action: run childrens_book_production pipeline (existing)
  - name: narration
    tools: [narrate]
    action: generate audio per page from completed text
  - name: video_assembly
    tools: [video_assembly]
    action: sequence illustrations + narration + music → video
  - name: song_generation
    tools: [song_generate]
    action: generate children's song from story bible
  - name: multi_publish
    tools: [deliver]
    action: push to app + Shopee + YouTube + Spotify
```

**Exit criteria:**

- One prompt → book PDF + EPUB + narrated audio + video + song, all delivered
- Derivative workshop: 45-60 min operator time for all 4 formats (not 45 min × 4)
- Multi-channel delivery: Shopee (PDF), KDP (EPUB), YouTube (video), Spotify (song)

---

## Phase 3: App Platform (Month 2)

S27 is the gateway session. Once apps are buildable, education and storybook apps follow immediately.

### S27 — Webapp Building (Jarvis Mode)

```
duration: 4-6 hours
depends_on: [S15, S12]
revenue_impact: Enables SME app revenue lane + education app + storybook app
new_code: ~300-370 lines
```

Three additions:

1. `tools/scaffold_webapp.py` (~100-150 lines) — Claude Code CLI scaffolds Next.js + Postgres app from structured ArtifactSpec. Headless, no manual Bolt paste.
2. Codebase context contract (~80-100 lines) — RollingContext variant for codebases. Tracks pages, endpoints, models, components. Updates after each code change.
3. App health check cron (~50-80 lines) — Vercel deployment monitoring. Error detection → diagnosis → operator notification.

Plus:

- `config/webapp_blueprints/` directory with 10-15 SME app blueprints
- `config/quality_frameworks/webapp_quality.md` — quality dimensions for web apps
- `config/critique_templates/webapp_code.md` — code quality failure patterns
- Updated `manifests/workflows/web_production.yaml` — fully autonomous (no manual scaffold step)

**SME app blueprints to author:**

```
config/webapp_blueprints/
├── clinic_booking.yaml          # Dr. Aminah's appointment system
├── restaurant_ordering.yaml     # Online menu + WhatsApp order
├── inventory_tracker.yaml       # Simple stock management
├── customer_crm.yaml            # Customer list + follow-up reminders
├── appointment_scheduler.yaml   # Generic scheduling (salon, workshop)
├── invoice_generator.yaml       # Simple invoicing for freelancers
├── staff_attendance.yaml        # Clock in/out + monthly report
├── product_catalogue.yaml       # Catalogue + WhatsApp enquiry button
├── tuition_centre.yaml          # Student registration + class scheduling
├── event_registration.yaml      # Event signup + payment
├── homestay_booking.yaml        # Room listing + availability + booking
├── question_bank.yaml           # Education question bank app
├── storybook_platform.yaml      # Children's storybook app
├── portfolio_site.yaml          # Freelancer/business portfolio
└── loyalty_programme.yaml       # Points + rewards for retail
```

**Exit criteria:**

- "Buat booking system untuk klinik" → scaffolds app → deploys to Vercel → live URL delivered via Telegram
- "Tambah payment page" on existing app → codebase context loads current state → Claude Code adds feature → deploys
- Health check detects error on deployed app → alerts operator via Telegram

### S34 — Education Question Bank App

```
duration: 3-4 hours
depends_on: [S27, S23]
revenue_impact: DIRECT — RM 9.90/month subscription
```

Scaffold question bank app from `config/webapp_blueprints/question_bank.yaml`. Populate with all questions produced in S23. Deploy. Subscription model: RM 9.90/month or RM 49/year.

**Pages:** Library (browse by subject → topic), quiz mode (answer questions → instant feedback), results (score + explanation review), parent dashboard (child progress), admin (add/edit questions).

**Exit criteria:**

- App live with 200+ questions across Tahun 4-6 Maths + Science
- Student can: browse topics → take quiz → see score + explanations
- Parent can: view child's progress per subject
- Subscription payment via ToyyibPay or Stripe
- New questions loadable from Vizier production pipeline without code change

### S35 — Children's Storybook App

```
duration: 3-4 hours
depends_on: [S27, S33]
revenue_impact: DIRECT — RM 9.90/month subscription, bundles all content formats
```

Scaffold storybook platform from `config/webapp_blueprints/storybook_platform.yaml`. Load all produced stories with all formats (swipeable pages, video, song). Deploy.

**Pages:** Story library (grid of covers, filter by age), story reader (swipeable pages with audio play), story video (video player), story song (audio + lyrics), parent dashboard (reading progress, favourites, time spent).

**Exit criteria:**

- App live with 10+ stories, each with swipeable book + video + song
- Swipe navigation works on mobile (primary experience)
- Freemium: 3 free stories, subscription for full library
- New stories publishable from Vizier production pipeline directly to app
- YouTube video embeddable as alternative to hosted video

---

## Phase 4: Adaptive Learning (Month 3-4)

### S36 — FSRS Integration for Education App

```
duration: 3-4 hours
depends_on: [S34]
revenue_impact: Premium feature — adaptive revision, higher retention, higher subscription value
```

Port Miftah's FSRS spaced repetition to the question bank app. The app learns which topics the student is weak on and prioritises those for revision. This is Miftah's algorithm with exam questions instead of Quranic ayat.

**Exit criteria:**

- Student answers questions → FSRS schedules weak topics for revision
- Dashboard shows: mastered topics (green), needs revision (amber), struggling (red)
- Revision mode: system selects questions from weak topics automatically
- Price increase justified: RM 14.90/month for adaptive vs RM 9.90 for basic

### S37 — Tuition Centre White-Label

```
duration: 3-4 hours
depends_on: [S34, S36]
revenue_impact: B2B SaaS — RM 99-299/month per tuition centre
```

White-label the question bank + adaptive learning app for tuition centres. Each centre gets branded instance with their own question bank + student management + parent portal + class scheduling.

This is the first step toward multi-tenant (§28.1 Stage 5), but scoped narrowly: each centre is a separate Postgres database (not multi-tenant on one database). Simple to implement, easy to isolate.

**Exit criteria:**

- Tuition centre signs up → branded app deployed within 24 hours
- Centre admin can: add own questions, manage students, schedule classes, view analytics
- Parents can: view child progress, receive WhatsApp updates
- Billing: monthly subscription via manual invoice (automate later)

---

## Phase 5: Platform Convergence (Month 4-6)

### S26 — Campaign Planning

```
duration: 3-4 hours
depends_on: [S24]
```

Campaign decomposition, scheduling, KPI tracking. Multi-deliverable coordination for clients.

### S25 — Social Monitor + Analytics

```
duration: 3-4 hours
depends_on: [S24]
```

Comment monitoring, sentiment analysis, engagement analytics, weekly reporting.

### S28 — Decision Support

```
duration: 3-4 hours
depends_on: [S19]
```

Improvement loop enhancements, skill security, operator decision support.

### S29 — Wazir Core

```
duration: 6-8 hours
depends_on: [S16, S27]
```

Mobile personal assistant concept. Voice persona, phone agent integration. First step toward the SaaS platform.

---

## Revenue Timeline

```
Week 1 (post-sprint):
  Children's books → KDP + Shopee (RM 9.90-19.90 per book)
  Education worksheets → Shopee (RM 5-15 per set)   ← S23 (config only)

Week 2-3:
  Books 4-8 production (derivative, 1 every 2 days)
  YouTube channel launch with narrated story videos   ← S30 + S31
  Serial fiction weekly episodes
  30+ worksheet sets across Maths + Science

Week 4 (mid-May school holidays):
  10+ children's book titles listed
  40+ worksheet sets listed
  Songs on Spotify                                    ← S32
  Multi-format pipeline live                          ← S33

Month 2:
  SME apps for existing clients                       ← S27
  Question bank app live (RM 9.90/month)              ← S34
  Storybook app live (RM 9.90/month)                  ← S35
  50+ worksheet sets, growing weekly
  20+ stories in storybook app

Month 3:
  Adaptive learning (FSRS) in question bank           ← S36
  200+ production ratings → multi-model activation
  Self-improvement loop active
  Client retainer revenue stable

Month 4-6:
  Tuition centre white-label (RM 99-299/month)        ← S37
  SME apps as regular revenue lane
  Campaign planning for clients                       ← S26
  Platform convergence                                ← S25, S28, S29
```

---

## Revenue Streams (Projected Month 6)

| Stream | Model | Est. Monthly |
|--------|-------|-------------|
| Client retainers (3-5 clients) | Monthly fee | RM 3,000-8,000 |
| Children's books (KDP + Shopee) | Per-book sales | RM 500-2,000 |
| Education worksheets (Shopee) | Per-set sales | RM 500-1,500 |
| Storybook app subscriptions | RM 9.90/month | RM 1,000-5,000 |
| Question bank app subscriptions | RM 9.90/month | RM 1,000-5,000 |
| SME apps (one-time builds) | RM 1,500-5,000 per app | RM 3,000-10,000 |
| Tuition centre white-label | RM 99-299/month | RM 500-3,000 |
| YouTube ad revenue | CPM | RM 200-500 |
| Spotify streaming | Per-stream | RM 50-200 |
| **Total projected** | | **RM 9,750-35,200** |

All from one engine, one operator, near-zero marginal cost per additional product.

---

## Session Dependency Graph

```
SPRINT (Day 1-3):
  S0-S21 → Core + Publishing ship

PHASE 1 (Week 1-2, parallel):
  S22 (YouTube research) ← S12
  S23 (Education config) ← Core ship (NO code)
  S24 (Social publishers) ← S10a + Meta approval
  S30 (Narration tool) ← S15
  S11 Enhancement (Client templates) ← Core ship (~30 lines)

PHASE 2 (Week 3-4):
  S31 (Video assembly) ← S30
  S32 (Song generation) ← S15
  S33 (Multi-format workflow) ← S30 + S31 + S32

PHASE 3 (Month 2):
  S27 (Webapp building) ← S15 + S12
  S34 (Question bank app) ← S27 + S23
  S35 (Storybook app) ← S27 + S33

PHASE 4 (Month 3-4):
  S36 (FSRS education) ← S34
  S37 (Tuition white-label) ← S34 + S36

PHASE 5 (Month 4-6):
  S26 (Campaign planning) ← S24
  S25 (Social analytics) ← S24
  S28 (Decision support) ← S19
  S29 (Wazir core) ← S16 + S27
```

---

## What This Roadmap Does NOT Include (Deferred)

- **S20 — Local model training** (Month 3+ after 200+ ratings)
- **Wazir SaaS multi-tenant** (§28.1 Stage 5 — when B2B demand justifies it)
- **Mobile native app** (React Native/Expo — when app subscriptions prove product-market fit on web first)
- **Full novel production** (Month 3-4, after serial fiction validates chapter-level coherence)
- **Domain expansion beyond marketing + education** (when client demand appears)

Each deferred item has a clear promotion trigger. None are blocked by architecture — they're deferred by operator bandwidth and revenue priority.
