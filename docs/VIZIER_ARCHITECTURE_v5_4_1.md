# VIZIER — COMPLETE ARCHITECTURE

**Version:** 5.4.1  
**Date:** 7 April 2026  
**Author:** Khairul / Premier Marketing  
**Status:** Canonical. Single source of truth for ARCHITECTURE. Supersedes all prior architecture documents.

**Execution:** VIZIER_BUILD.md (v1.3.1) governs HOW to build. This document defines WHAT to build.

**Changes from v5.4.0:** Added §0.1 Three-Ring Architecture Model (Structure / Config / Data) — a decision framework for reading, building, and evolving Vizier. Maps all 43 sections to their ring. No structural, build sequence, or session priority changes.

**Changes from v5.3.3:** Renamed from vizier-supreme to vizier (canonical build — all future upgrades base on this codebase). §16 title corrected (37 tables). §16 body text corrected (37 not 35). §20.2 title corrected (6 Steward tables). §25 extended.sql description corrected (Postgres only, LibSQL created by S7 separately).

**Changes from v5.3.2:** §20 replaced with Steward personal assistant (was LifeOS REMOVED). GTD-based, ADHD-friendly, separate Telegram bot on same engine. 6 tables (steward_inbox, steward_tasks, steward_projects, steward_reviews, steward_health_log, steward_learning). §16.4a added. Atomic Habits engine (§20.6): four-law habit design, 2-minute rule, never-miss-twice, habit stacking, identity-based tracking. Deep Work integration (§20.7): time blocking between prayers, deep/shallow ratio, WIGs, productive meditation. Apple Health integration (§20.8): daily batch import, sleep/activity-informed energy recommendations, health-habit correlation. Learning system (§20.9): Wisdom Vault integration, spaced repetition nudges, domain-linked learning goals, Miftah progress surface. §21 persona layer updated to three-mode system. Table counts: 35→37 total, 33→35 Postgres, 19→21 extended.

**Changes from v5.3.1:** Local-first data stack: Supabase replaced with local Postgres + pgvector + MinIO (S3-compatible storage). Zero cost, zero tier limits, zero network latency. LifeOS bridge (§20) removed — LifeOS data stripped. Dashboard data layer: Refine via PostgREST. Promotion path inverted — managed Postgres is the scale-up option, not the starting point.

**Changes from v5.3.0:** Table count corrected. §30.2 Visual DNA tools aligned with §5 stack. §35 capability summary session references corrected. `tools/illustrate.py` added to §25 repo structure. Duplicate DDL example fixed.

---

## Supersession

This document replaces:

- VIZIER_COMPLETE_ARCHITECTURE_v4.md (v4.0.0)
- Vizier Platform Architecture v6.2
- VIZIER_CANONICAL_ARCHITECTURE.md (Prime)
- PHASE1_STACK_LOCK_v3.md
- VIZIER_UNIFIED_ARCHITECTURE.md v1.0.0 and its addendum
- VIZIER_ARCHITECTURE v5.2.0
- All prior stack locks and architecture summaries

**Repository:** vizier (canonical build). Replaces vizier-pro-max as the active codebase. Pro-max is retained as reference only — not archived, not built upon.

**Assets ported from pro-max (assets only, no data):**

- Templates (visual, documents, Typst, web)
- Listening engine code
- Visual QA utilities (into middleware/quality_gate.py)
- 354 stock images
- Typst templates
- Document templates
- pyproject.toml dependencies

**NOT ported from pro-max (mock data, discard):**

- No client deliverables
- No knowledge cards
- No exemplars
- No swipe file extractions
- No feedback records
- No production traces

All client knowledge, exemplars, and swipe data are built fresh from config authoring, operator-curated materials, and production seeding. The first 5-10 jobs per client are deliberate calibration rounds. The exemplar library grows entirely from production output rated 5/5 by the operator.

**Supporting config files governed by this document:**

- config/phase.yaml — phase activation
- config/artifact_taxonomy.yaml — artifact classification
- config/fast_paths.yaml — deterministic routing patterns
- config/retrieval_profiles.yaml — knowledge retrieval by artifact type
- config/brand_patterns/ — international brand pattern library
- config/copy_patterns/ — copy formula library
- config/calendar/ — Malaysian events and seasonal calendar
- config/stock_assets.yaml — graphic element registry
- config/design_systems/ — 55 web/UI design systems (DESIGN.md)
- config/design_system_index.yaml — design system selector tags (industry, density, mood, colour_temperature)
- config/layout_systems/ — 6 print/document layout systems (LAYOUT.md)
- config/prompt_templates/ — visual brief expander, tripwire feedback templates
- config/quality_frameworks/ — poster quality dimensions, scoring rubrics
- config/content_strategies/ — industry × channel × objective mappings
- config/infographic_templates/ — antvis component templates
- config/course_templates/ — slide layouts, handouts, worksheets, quizzes
- config/code_switching/ — BM-EN switching triggers, particle grammar, register-ratio mapping
- config/dialect_systems/ — 10 Malaysian dialect adaptation files
- Decision notes in docs/decisions/

---

## 0. Architecture Summary

Vizier is a governed, self-improving AI production engine. An operator directs it. Vizier executes, traces, learns, and gets better with every job. Domain-agnostic by architecture. The current deployment is digital marketing in Malaysia — the first instantiation, not the ceiling.

**Stack:** Hermes Agent v0.7.0 (runtime) + Pydantic (contracts) + Local Postgres 16 + pgvector (35 tables + views + triggers) + LibSQL (2 local tracing tables) + MinIO (S3-compatible asset storage) + Langfuse (observability + token tracking) + Refine (dashboard data layer via PostgREST) + multi-model routing (GPT-5.4-mini primary, Claude Opus/Sonnet, Gemini, Qwen 3.5 local, Nano Banana Pro, FLUX.2). 37 tables total. Full stack in §5.

**Principles:** 14 principles (§3). Key: governed execution (P1), self-improvement through use (P5), one engine many doors (P6), warm from day one (P11), architecture defines engine not deployment (P12), complexity behind glass (P13), use existing systems before writing custom code (P14).

**Data model:** 37 tables total (35 in local Postgres, 2 in local LibSQL) in 10 groups split across two migration files plus LibSQL DDL. `migrations/core.sql` (14 Postgres tables): Core (8), Knowledge (4), Infrastructure (2). `migrations/extended.sql` (21 Postgres tables): BizOps (3), Steward (6), Compound (2), Calibration (4), Campaign (2), Social (3), Course (1). LibSQL (2 tables): spans, memory_routing_log — created by S7 directly. Core tables created during foundation session. Extended tables created on-demand by the session that needs them. Plus Postgres views for metrics. Full schema in §16.

**Governance:** ArtifactSpec contracts → ReadinessGate (ready/shapeable/blocked) → PolicyEvaluator (allow/block/degrade/escalate) → Tripwire mid-production checks → Parallel guardrails on GPT-5.4-mini (Month 1-2) / Qwen local (Month 3+) → Structural assertions → Feedback state machine (silence is not approval). Full governance in §7-9.

**Operator experience:** Surface (engine talks to you — adaptive, context-aware, one screen) + Depth (you talk to the engine — pull-to-inspect via Refine data layer over PostgREST, every layer accessible, no layer uninvited). Full UX in §31.

**Build plan:** Core Sessions 0-6 (~2,500-3,200 lines custom code), then ship. Extended Sessions 7-9 (~1,000-1,400 lines custom code). Total custom code: ~3,500-4,600 lines. External systems handle the rest. Full plan in §26.

**Build efficiency principle:** Custom code is reserved for domain-specific logic no existing system handles: governance contracts, refinement loop, production orchestration, self-improvement proposals, and the Surface layer UX. Everything else — data access, CRUD, auth, scheduling, token tracking, image analysis, readability scoring — uses existing systems. Full efficiency map in §27.

---

### 0.1 Three-Ring Architecture Model

The 43 sections of this document are comprehensive but flat — every section sits at the same level. The three-ring model provides a decision framework for reading, building, and evolving Vizier.

**Ring 1 — Structure.** The governance spine. Contracts, gates, policy, feedback state machine. Topology-independent and domain-agnostic — works identically whether one agent or fifty processes the work (anti-drift #57). Changes here are rare and high-stakes: they affect every workflow downstream. Built during the sprint, then mostly left alone.

Sections: §7 (governance layers), §8 (routing model), §9 (iterative refinement + rework), §14 (production traces), §16 (data model), §34 (anti-drift rules).

**Ring 2 — Config.** The production engine. WorkflowPack YAMLs, model preferences, client configs, design systems, copy patterns, personas, critique templates, image routing, cold start assets. Deployment-specific by design — new client, new artifact type, new revenue lane = new config on unchanged structure. Changes here are frequent and low-risk. The entire post-sprint roadmap (S22-S37) is Ring 2 expansion.

Sections: §4 (quality postures + techniques), §6 (model roster + routing), §10 (workflow packs), §11 (cold start), §17 (artifact taxonomy), §24 (renderers), §38 (design intelligence), §42 (publishing intelligence).

**Ring 3 — Data.** The learning loop. Production traces, exemplar libraries, improvement proposals, anchor sets, outcome memory, RollingContext. This ring doesn't get built — it gets fed. Every job makes it smarter. The structure governs it, the config directs it, the data compounds into the moat.

Sections: §15 (self-improvement loop + drift detection), §22 (knowledge spine), §23 (distillation pipeline), §43 (RollingContext).

**Decision rule: structure once, configure often, feed constantly.**

Before any build decision, ask "which ring?" If Ring 2, it's a config afternoon. If Ring 1, it's a careful session with anti-drift review. If Ring 3, it might not need building at all — it might just need more production data.

When evaluating external tools or patterns for absorption: identify which ring they map to first. Ring 2 patterns (workflow contracts, template formats) integrate cheaply. Ring 1 patterns (governance changes, new gate layers) require careful design. Ring 3 patterns (learning algorithms, drift detection) may already be handled by accumulated production data.

---

## 1. What Vizier Is

Vizier is a governed, self-improving AI production engine.

An operator directs it. Vizier executes: producing artifacts to spec, researching markets, shaping vague briefs into production-ready contracts, delivering outputs, tracking costs, managing business operations, and maintaining operational rhythm. It learns from every job and gets better over time — progressively requiring less operator intervention, trending production costs toward zero, and compounding institutional knowledge with every completed deliverable.

Vizier is domain-agnostic by architecture. The governance layer (contracts, policy, readiness gates, quality gates), the routing model, the iterative refinement loop, the research pipeline, the self-improvement system, and the trace infrastructure — none of these are bound to any specific industry, artifact type, operator, or scale. They are engine patterns. The current deployment is digital marketing in Malaysia. That is the first instantiation, not the ceiling.

Vizier is not a chatbot. It is not a prompt wrapper. It is not an uncontrolled autonomous agent. It is not Canva. It is not an empty engine waiting for content. It is not defined by any particular number of clients, any particular domain, or any particular operator's current bandwidth.

It is:

- a production engine — operator directs, Vizier executes, the system learns
- governed — every action passes through policy
- contract-driven — every artifact has a spec before production begins
- artifact-centric — outputs are first-class objects with identity, QA, and delivery paths
- research-grounded — market trends, competitor analysis, content gaps, and seasonal planning feed into production
- pre-loaded — templates, patterns, copy formulas, brand knowledge, and quality references exist before the first request
- phase-controlled — capabilities activate explicitly, not by assumption
- self-improving — feedback compounds into institutional knowledge, refinement cycles reduce over time, production costs trend toward zero
- scale-independent — serves one client or one thousand, one domain or many, one operator or a team

The architecture supports a trajectory from solo operator to billion-dollar production company — not by adding headcount, but by compounding system intelligence. Every job teaches the engine. Every refinement cycle trains preferences. Every trace feeds distillation. The operator's role shifts from hands-on production to strategic direction as the system absorbs patterns and automates decisions.

One governed engine, many artifact doors. Domain-agnostic. Scale-independent. Loaded from day one.

---

## 2. Problem Statement

Most AI production systems fail in one of four ways.

**Too brittle.** Only works with complete inputs. Real requests arrive vague.

**Too loose.** Vague prompts, shallow memory, inconsistent outputs. Hard to trust.

**Too empty.** The engine works but has no templates, no patterns, no references, no quality standards. Like Canva with zero templates — technically capable, practically useless.

**Too small.** Built around a fixed number of clients, a fixed domain, a fixed operator. The system works at current scale and breaks at the next level. Architecture that defines itself by its deployment can never outgrow its deployment.

Vizier solves all four: governed execution for trust, iterative refinement for vagueness, pre-loaded assets for immediate production quality, and domain-agnostic architecture for unlimited scale.

---

## 3. Architecture Principles

**P1** — Governed execution over open-ended autonomy.  
**P2** — Deterministic where correctness matters.  
**P3** — Retrieval before generation. When references, exemplars, brand rules, or patterns exist, ground with them.  
**P4** — Narrow roles, clear boundaries.  
**P5** — Self-improvement through use.  
**P6** — One engine, many doors.  
**P7** — Reliability over features.  
**P8** — Simplicity. Follow Anthropic's hierarchy. Move up only when the layer below fails.  
**P9** — Artifacts are first-class. Identity, purpose, structure, QA, approval, delivery path.  
**P10** — Iterative refinement is first-class. Not all requests begin ready.  
**P11** — Warm from day one. No cold start. Pre-loaded patterns, templates, copy formulas, quality references, and brand knowledge before the first request.  
**P12** — Architecture defines the engine, not the deployment. No hard-coded assumptions about operator count, client count, domain, geography, or scale. The current deployment is one instantiation. The engine supports any.  
**P13** — Complexity behind glass. The engine is powerful. The operator experience is graceful. The system surfaces insights, not data. Every layer of depth is accessible, but no layer appears uninvited. Surface: the engine talks to you. Depth: you talk to the engine. Both are intentional. Both are beautiful.  
**P14** — Use existing systems before writing custom code. If an existing open-source system, library, or infrastructure feature handles a capability with acceptable quality, use it. Custom code is reserved for domain-specific logic no existing system can handle.

---

## 4. Operating Modes

**Direct production** — request is clear and complete. Route straight to production.  
**Iterative refinement** — request is shapeable but incomplete. Structured clarification loop.  
**Blocked** — critical input missing. Hard stop with checklist.

**Exploration posture** — proving new lanes. Thinner contracts, lighter QA.  
**Production posture** — delivery-grade execution. Full contracts, formal QA.

### 4.1 Quality Postures

Quality capabilities activate progressively based on accumulated production data, not build completion.

**Canva-baseline** — Template-driven production. Deterministic sizing and client palette. Structural QA only (Layer 0). Expert persona + domain vocabulary in prompts. Self-refine on text output. Launch default for all clients.

**Enhanced** — Exemplar injection (2-5 approved outputs per call). Visual brief expansion before image generation. Copy formula grounding from pattern library. Structured critique chain (2-3 dimension-specific passes). Activates when 10+ exemplars exist per client AND per artifact type.

**Full** — All design intelligence layers active. Research-grounded production. Parallel guardrails. Fine-tuned local quality scorers. Golden dataset calibration. Activates when fine-tuned models prove >80% correlation with operator ratings AND golden dataset v1.0 is locked.

Quality posture governed by `config/phase.yaml`, same mechanism as capability phases. Each client can be at a different quality posture — a new client starts at Canva-baseline while an established client with 50+ approved outputs operates at Enhanced.

### 4.2 Quality Techniques (8 proven methods)

Eight research-validated techniques for raising output quality, configured per-workflow via `quality_techniques` in WorkflowPack YAML:

1. **Self-Refine loop** — Generate → Critique (specific issues) → Revise. Not score-retry but critique-then-fix. The critique prompt names what's wrong; the revision addresses it.
2. **Iterative rubric refinement** — Start with minimal rubric. After 20 operator ratings, refine rubric where scorer disagrees with operator. Rubric evolves from YOUR data, not from external datasets.
3. **Few-shot exemplar injection** — 2-5 approved outputs as examples in production prompt. Most impactful single technique. Cold start: first 5-10 jobs per client are deliberate calibration rounds.
4. **Structured critique chain** — 2-3 dimension-specific critique passes (e.g., copy quality, layout compliance, brand alignment). Narrow passes catch more than broad review.
5. **Expert persona prompting** — Role-specific persona in system prompt. "You are a senior Malaysian marketing director with 15 years experience in traditional textile marketing."
6. **Silver→Gold progressive ratchet** — AI-generated outputs start as silver. Operator review promotes best to gold exemplar status. Quality library grows organically from production.
7. **Contrastive examples** — 1 good exemplar + 1 failure-with-fix as boundary teaching. Shows the model the BOUNDARY between acceptable and unacceptable.
8. **Domain vocabulary injection** — 20-30 must-use-correctly terms per language/domain. Prevents BM copy failures (Indonesian BM vs Malaysian BM, overly formal vocabulary for casual platforms).

Per-workflow configuration:

```yaml
quality_techniques:
  self_refine: per_section | on_prompt | false
  exemplar_injection: true | false
  contrastive_examples: true | false
  critique_chain: [dimension_1, dimension_2]
  persona: config/personas/{role}.md
  domain_vocab: config/vocab/{language}.yaml
  diversity_instruction: "Generate 3 variants using DIFFERENT visual approaches"
```

---

## 5. Hybrid Stack

| Role | Component | Why |
|------|-----------|-----|
| Runtime + orchestration + gateway + cron | Hermes Agent v0.7.0 | Superagent with tool registry, session persistence, credential pools, pluggable memory, multi-platform gateway, cron scheduling |
| Contract layer | Pydantic | Zero infrastructure. Every payload validated |
| Operational data spine | Local Postgres 16 + pgvector (triggers, FTS, views) | 35 Postgres tables + views. Core 14 created day one, extended 21 created on-demand. Plus 2 tracing tables in local LibSQL (created by S7). 37 total. |
| Binary asset storage | MinIO (local, S3-compatible) | Unlimited storage, zero cost. Uploads, generated assets, PDFs. Thumbnails via Pillow |
| Observability + token tracking | Langfuse (cloud free tier) + @observe SDK | Per-trace cost breakdown, latency, prompt tracking. Token attribution via custom metadata (client_id, tier, job_id) |
| Model routing | Hermes credential pools + direct provider SDKs | Multi-model: GPT-5.4-mini primary (ALL tasks Month 1-2), Claude/Gemini/Qwen (Month 3+ after S19 benchmark). Full roster in §6.1 |
| Policy engine | Python middleware (PolicyEvaluator) | allow/block/degrade/escalate |
| Phase governance | config/phase.yaml | One YAML, one gate function |
| Dashboard data layer | Refine + PostgREST | Headless React framework. CRUD, auth, realtime, table browsing, relationship navigation — all via PostgREST (same REST API Supabase uses internally, fully open source) |
| Dashboard API | PostgREST (local) | Auto-generates REST API from Postgres schema. Zero custom endpoints. Refine's `@refinedev/simple-rest` provider connects directly |
| Visual analysis | colorthief + open_clip + mediapipe | Colour extraction, CLIP embedding, face detection. Pip installs, not custom code |
| Copy analysis | textstat + langdetect | Readability scores, language detection. Pip installs |

**Dropped:** LiteLLM (supply chain compromise), Temporal (overkill for solo operator), OPA (Python functions suffice), Supabase (tier limits on storage/database, network latency, paid tier pressure — replaced by local Postgres + MinIO), n8n (Hermes gateway + cron + MCP replace it), pg_cron (Hermes cron handles scheduling).

Each dropped component has an explicit promotion trigger documented in §28.

---

## 6. Core Runtime: Hermes Agent v0.7.0

Hermes provides: agent loop, tool registry (`registry.register()`), session persistence (SQLite + FTS5), memory (MEMORY.md + USER.md, pluggable provider ABC), skills (SKILL.md, progressive disclosure, self-improvement), gateway (Telegram, Discord, Slack, WhatsApp, Signal, CLI), cron scheduling, credential pools (multi-key, least_used, 401 auto-failover), subagent delegation, token metering (`/usage`, `/insights`), execution backends (local, Docker, SSH, Daytona, Singularity, Modal), ACP editor integration, dangerous command approval, secret exfiltration blocking.

**Submodule:** Pinned to upstream NousResearch/hermes-agent v0.7.0 — no fork unless patches are needed. The vizier-gate2-patch fork (on pro-max) should be diffed against v0.7.0 before Session 1: if the patches are small or absorbed by v0.7.0, use upstream directly and eliminate the rebase session. If significant patches remain, fork minimally.

**Integration rules:** Hermes is the runtime, not the system sovereign. Every request enters as an ArtifactSpec, not raw chat. No Hermes-native types leak into domain contracts. Hermes session IDs link to Postgres job records.

**Model strategy:** GPT-5.4-mini (free 10M/day) handles ALL tasks Month 1-2, including scoring, routing, guardrails, AND creative prose (EN and BM). Current daily usage at full load: ~310K tokens = 3.1% of budget. Claude Opus, Claude Sonnet, Gemini 3.1 Pro, and Gemini 2.5 Pro are available in credential pools but NOT routed to by any WorkflowPack YAML until S19 benchmark validates the prose routing map (anti-drift #54). Qwen local models enter production path ONLY after fine-tuning proves >80% correlation with operator ratings (Month 3+). Full model roster below.

### 6.1 Model Roster

| Model | Provider | Cost | Role | Status Month 1-2 | Where |
|-------|----------|------|------|-------------------|-------|
| GPT-5.4-mini | OpenAI | Free (10M/day) | ALL tasks: production, scoring, routing, guardrails, creative prose (EN+BM) | **ACTIVE** | Cloud |
| GPT-5.4 | OpenAI | Free (1M/day) | Creative work when available | ACTIVE (overflow) | Cloud |
| Claude Opus 4.6 | Anthropic | $5/$25 per 1M tokens | English creative prose, fiction, narratives | **INACTIVE — activates after S19 benchmark** | Cloud |
| Claude Sonnet 4.6 | Anthropic | $3/$15 per 1M tokens | Business documents, proposals, reports | **INACTIVE — activates after S19 benchmark** | Cloud |
| Gemini 3.1 Pro | Google | $2/$12 per 1M tokens | BM creative prose, natural BM register (provisional) | **INACTIVE — activates after S19 benchmark** | Cloud |
| Gemini 2.5 Pro | Google | $1.25/$10 per 1M tokens | BM creative (fallback if 3.1 Pro not significantly better) | **INACTIVE — activates after S19 benchmark** | Cloud |
| Qwen 3.5 9B | Local (Ollama) | Free | Month 3+: complex guardrail reasoning, memory summarisation | **INACTIVE — installed, unused** | Mac Mini |
| Qwen 3.5 4B | Local (Ollama) | Free | Month 3+: quality scoring (after fine-tuning) | **INACTIVE — installed, unused** | Mac Mini |
| Qwen 3.5 2B | Local (Ollama) | Free | Month 3+: fast routing, BM register check (after fine-tuning) | **INACTIVE — installed, unused** | Mac Mini |
| Gemini 3.1 Flash-Lite | Google | $0.25/$1 per 1M tokens | S19 benchmark candidate for routing/classification — may replace Qwen 2B fine-tuning if quality matches | **INACTIVE — benchmark at S19** | Cloud |
| FLUX.1 Kontext [pro] | BFL/fal.ai | ~$0.05-0.10/image | Character consistency (iterative), image editing, style transfer | ACTIVE | Cloud |
| FLUX.1 Kontext [max] | BFL/fal.ai | ~$0.08-0.15/image | Premium character consistency, typography, editing | ACTIVE | Cloud |
| FLUX General + IP-Adapter | fal.ai | ~$0.075/MP | Reference-anchored character consistency, style conditioning | ACTIVE | Cloud |
| Nano Banana Pro | Google/fal.ai | ~$0.134/image | Text-heavy posters, marketing graphics with BM copy, up to 14 references | ACTIVE | Cloud |
| Nano Banana 2 | Google/fal.ai | ~$0.10/image | Fast drafts, preview generation | ACTIVE | Cloud |
| FLUX.2 [pro] | fal.ai | ~$0.03/MP | Photorealistic scenes, product photography, up to 4 references | ACTIVE | Cloud |
| FLUX.2 [dev] | fal.ai | ~$0.012/MP | Bulk element generation, fast iteration, draft previews | ACTIVE | Cloud |

Month 1-2: All text/reasoning models route to GPT-5.4-mini. Claude, Gemini, and Qwen are available in credential pools but receive zero traffic. Image models are active from Day 1 (no text model alternative exists).

Month 3+: S19 benchmark validates prose routing map. Fine-tuned Qwen 4B/2B replace GPT-5.4-mini for narrow tasks only after validation.

### 6.2 Prose Routing

```yaml
# WorkflowPack YAML — model_preference (Month 1-2)
# ALL prose routes to GPT-5.4-mini. Multi-model activates after S19 benchmark.
model_preference:
  en_creative: gpt-5.4-mini       # TARGET: claude-sonnet-4.6 (after S19 — benchmark Sonnet before Opus; near-Opus quality at 40% lower cost)
  bm_creative: gpt-5.4-mini       # TARGET: gemini-3.1-pro (after S19)
  en_business: gpt-5.4-mini       # TARGET: claude-sonnet-4.6 (after S19)
  bm_business: gpt-5.4-mini       # TARGET: gemini-2.5-pro (after S19)
  short_copy: gpt-5.4-mini
  routing: gpt-5.4-mini           # TARGET: gemini-3.1-flash-lite or qwen-3.5-2b (after S19 — Flash-Lite at $0.25/M may beat local fine-tuning cost)
  scoring: gpt-5.4-mini
  classification: gpt-5.4-mini    # TARGET: gemini-3.1-flash-lite or qwen-3.5-2b (after S19)
```

**Routing logic:** read `model_preference` from WorkflowPack YAML for current stage, detect language from client config or langdetect on input, determine task type from stage role field (creative/business/short/routing/scoring), select model from language × task type preference map, call selected model via Hermes credential pool.

**Post-S19 activation:** After benchmarking 10 briefs × Claude/Gemini/GPT × EN+BM, update `model_preference` in each WorkflowPack YAML with validated assignments. This is a config change, not a code change.

**S19 benchmark additions (April 2026 market context):**

- Benchmark Claude Sonnet 4.6 alongside Opus 4.6 for `en_creative`. Sonnet 4.6 delivers near-Opus quality at ~40% lower cost ($3/$15 vs $5/$25). If Sonnet matches Opus on EN creative prose for marketing copy, use Sonnet and reserve Opus for fiction/narratives only.
- Benchmark Gemini 3.1 Flash-Lite ($0.25/M input) for `routing` and `classification` tasks alongside Qwen 3.5 2B fine-tuned. Flash-Lite may match fine-tuned Qwen at comparable latency without the training investment — eliminates a provider dependency if quality holds.
- Evaluate Anthropic native web search (now GA, free with code execution) as alternative to Tavily for the S12 research pipeline. Reduces a dependency if quality and coverage are sufficient for Malaysian market research.

### 6.3 Image Routing

Illustration consistency pipeline (validated in endpoint testing):

```
Character bible YAML
 │
 ├── Generate 10-15 candidate reference images
 │   Operator selects 2-3 as references (30 min per character)
 │
 ├── PATH A: Kontext iterative (RECOMMENDED for sequential production)
 │   Page N image + "same character, new scene" → Kontext → Page N+1
 │   Pro: no reference setup, consistency compounds. Con: drift over 8+ pages
 │
 ├── PATH B: FLUX General + IP-Adapter (anchor-based)
 │   Reference images + scene prompt → IP-Adapter conditioning per page
 │   Pro: consistent anchor, no drift. Con: requires good references upfront
 │
 ├── PATH C: Nano Banana Pro multi-reference (up to 14 images)
 │   Pro: best BM text rendering. Con: most expensive per page
 │
 └── PATH D: FLUX.2 multi-reference (up to 4 images)
     Pro: cheapest. Con: limited references
```

Path selection validated in endpoint testing (S4). Choice is per-project config, not hardcoded.

```yaml
image_model_preference:
  text_heavy: nano-banana-pro
  photorealistic: flux-2-pro
  character_iterative: flux-kontext-pro
  character_anchored: flux-general-ip
  illustration: nano-banana-pro
  draft: flux-2-dev
  element: flux-2-dev
```

**Routing logic:** read `image_model_preference` from WorkflowPack YAML, check ArtifactSpec for overlay text (→ text_heavy), check for sequential character consistency requirement (→ character_iterative), check artifact type for product/background/scene (→ photorealistic), check posture for exploration (→ draft), select image model accordingly.

### 6.4 Local Model Tiering

Month 1-2: ALL tasks route to GPT-5.4-mini (cloud, free). Qwen local is installed but unused in production. This eliminates latency bottlenecks (Qwen 9B: 3-20s per call vs GPT-5.4-mini: 0.5-1.5s) and simplifies debugging during launch phase. Daily token usage including all tasks: ~310K = 3.1% of 10M/day budget.

Month 3+ (after fine-tuning):

```
Request arrives
 │
 ├── Routing/classification → Qwen 3.5 2B fine-tuned (<0.5s)
 ├── Quality scoring → Qwen 3.5 4B fine-tuned (<1s)
 ├── Complex reasoning → Qwen 3.5 9B (3-5s)
 └── Production writing → Cloud model per routing map
```

Only one local Qwen model loaded at a time via Ollama. Hermes manages model switching via credential pool configuration. `scorer_fallback` in WorkflowPack YAML enables graceful degradation to GPT-5.4-mini if local model is slow or unavailable.

---

## 7. Governance Layers

### 7.1 Contracts (`contracts/`)

- **ArtifactSpec** — production contract with structural, style, QA, delivery requirements
- **ProvisionalArtifactSpec** — structured hypothesis during refinement with confidence, completeness, shaping viability scores
- **PolicyDecision** — allow/block/degrade/escalate with reason and constraints
- **RoutingResult** — inspectable routing output stored on job record
- **RefinementLimits** — per-workflow bounds on cycles, clarifications, prototypes, cost ceiling
- **FeedbackRecord** — structured client feedback with categories and polarity
- **PlanningObject** — compound artifact planning (chapters, pages, scenes)
- **CharacterRegistry** — entity consistency for publishing
- **StyleLock** — locked illustration parameters for visual coherence

### 7.2 Policy Engine (`middleware/policy.py`)

PolicyEvaluator with budget gate, tool gate, phase gate, cost gate. Python functions, not OPA. Auditable via policy_logs table.

**Future: Atomic budget enforcement (post-sprint, when client count grows).** Currently the budget gate checks at the job level. Atomic enforcement would reserve estimated tokens per workflow stage before execution and degrade gracefully (stop after current stage, deliver partial) if budget exhausts mid-workflow rather than discovering overspend after completion. ~20 lines added to PolicyEvaluator. Promotion trigger: 5+ clients with distinct monthly budgets.

### 7.3 Readiness Gate (`contracts/readiness.py`)

Returns ready/shapeable/blocked. Thresholds configurable per artifact family in WorkflowPack YAML.

### 7.4 Quality Gate (`middleware/quality_gate.py`)

Five progressive layers. Each layer adds cost only when the previous layer can't provide sufficient assurance.

**Layer 0 — Structural assertions (zero tokens, zero cost).** Valid file format, correct dimensions, required zones populated. Python checks that throw errors on failure. These are preconditions, not scoring. Runs on every artifact, every time, no exceptions.

**Layer 1 — Deterministic design checks (zero tokens, zero cost).** From the design intelligence layer: poster layout matches heatmap conventions (CTA in bottom zone, adequate text-to-image ratio). BM copy naturalness heuristic: sentence length, formal vocabulary density, passive voice frequency. Ad copy linguistic quality: noun density, structural markers present. Platform content density: text word count within bounds for target format.

**Layer 2 — Tripwire mid-production checks (GPT-5.4-mini Month 1-2, Qwen local Month 3+, zero/near-zero cost).** After each production stage, check output against tripwire threshold. Scorer loaded with quality framework as system prompt. Feedback is critique-then-revise (specific issues named), not score-only retry. If score < threshold: retry with critique feedback. Max 2 retries before escalating to operator. Supports section-level checking for long-form documents (per-chapter, per-section). `scorer_fallback` + `latency_threshold_ms` in WorkflowPack YAML for graceful degradation. Full mechanism in §37.

**Layer 3 — Parallel guardrails (GPT-5.4-mini Month 1-2, Qwen local Month 3+).** Async subagents running alongside production. Brand voice check: compare output against client swipe bank + brand config. Register consistency: verify casual/formal matches client copy_register setting. Factual claim check (for course materials): flag unverified claims. Multiple guardrails run simultaneously. Flags collected by GuardrailMailbox — deduplicated by issue type before QA stage processes. Full mechanism in §37.

**Layer 4 — Operator rating + client feedback (human judgement).** Operator rates 1-5 on every deliverable. Client feedback via structured categories (copy ✓/✗, layout ✓/✗, colour ✓/✗, tone ✓/✗). Silence is not approval — only explicit approval counts as quality signal. Feedback collection rate tracked as first-class metric. This layer generates the training data for future fine-tuning.

Output quality is measured by operator rating (1-5 on feedback table) and first-pass approval from real client feedback. Multi-dimensional automated scoring (brand consistency, copy quality, exemplar distance) is a future addition when 100+ jobs provide enough data to know which dimensions matter.

### 7.5 Posture (`middleware/posture.py`)

Reads `posture: exploration | production` from workflow definition. Adjusts contract strictness accordingly.

### 7.6 Golden Dataset

The golden dataset calibrates quality judgements. It splits into two distinct datasets serving different purposes:

**Quality Dataset (convergent by design):** Structural rules, failure detection, minimum standards. Strictness is appropriate — there's one correct answer for "is the text readable?" and "do the dimensions match the platform?"

- Composition grammar from CGL (element positions, whitespace budgets, collision rules) → deterministic Layer 1 checks
- Failure taxonomy from PosterCraft Reflect-120K (diagnosed failures with fix instructions) → tripwire feedback templates
- Content density rules from AdImageNet (word budgets per platform/format) → structural assertions
- Linguistic quality indicators from AdParaphrase → copy quality checks

**Creative Dataset (diverse by design):** Exemplars, preference pairs, style references. Must represent the FULL RANGE of acceptable styles, not just the average approved style. Grows with diversity (adding new approved styles), never narrows (removing unused styles).

- Exemplar library — 5/5 rated outputs across artifact families. Seeds from PosterCraft (top 500) + production outputs promoted to exemplar status
- Preference pairs — "this is better because…" Seeds from PosterCraft Preference-100K (5,000 pairs)
- Style references — diverse design directions per client, not converged to one look
- `diversity_score` field on datasets table (CLIP embedding variance) — alerts if exemplar diversity drops below threshold

**Diversity protection mechanisms:**

- Contrastive exemplar injection: 2 approved + 1 deliberately different design from another brand/industry
- Composition rules as advisory, not strict (flag deviations, don't block — except structural requirements)
- Periodic creative drift: every Nth job for established clients, generate one variant using a different design system
- Production data quarantine: rated output contributes to training ONLY for dimensions where operator rating diverges from system prediction. Agreeing data points teach nothing.

Rubric evolution: Start with minimal rubric ("rate 1-5 on quality"). After 20 operator ratings, refine rubric where scorer disagrees with operator. Rubric evolves from YOUR disagreements with the scorer, not from 120K PosterCraft reflections. Full PosterCraft extraction is enrichment (post-Core), not foundation (blocking).

Both datasets versioned and immutable once locked (stored in datasets and dataset_items tables, §16.7). Quality dataset v1.0 bootstrapped from deterministic rules (2 days). Creative dataset v1.0 bootstrapped from first 5-10 approved outputs per client. Production data progressively enriches both.

---

## 8. Routing Model

One function in `contracts/routing.py`. Three phases:

**Phase 1 — Interpret.** Receive trigger (Hermes gateway), normalise raw input, classify artifact (from `config/artifact_taxonomy.yaml`), form spec (ArtifactSpec or ProvisionalArtifactSpec). Fast-path: if input matches a pattern in `config/fast_paths.yaml` (e.g. "poster" + known client), skip LLM classification entirely — deterministic routing at zero tokens.

**Phase 2 — Evaluate.** Readiness gate (ready/shapeable/blocked), workflow selection (from `manifests/workflows/`), policy evaluation (PolicyEvaluator), phase activation check (`config/phase.yaml`). Returns: proceed / refine / block.

**Phase 3 — Execute.** Emit RoutingResult (stored on job record), hand off to selected workflow.

Fast-path handles 60-70% of requests at zero tokens. LLM classification activates only when the fast-path can't resolve.

---

## 9. Iterative Refinement

When readiness gate returns `shapeable`:

1. Create ProvisionalArtifactSpec with scores
2. Analyse missing fields (critical vs shaping)
3. Select lowest-cost shaping move (retrieve exemplars → ask focused question → show direction options → show preview → generate sample → generate prototype)
4. Present via gateway
5. Capture structured FeedbackRecord
6. Revise spec, update scores
7. Re-evaluate readiness
8. Repeat until ready, blocked, or limits exhausted

**Limits:** Max 4 cycles, max 2 unanswered clarifications, max 3 prototype rounds, shaping cost ceiling before approval. Non-convergence detected if readiness doesn't improve by 0.1 across 2 cycles.

**Promotion:** Explicit `promote()` method — new ArtifactSpec revision, audit log, routes to production. No silent drift.

### 9.1 Post-Delivery Rework

When a delivered artifact receives `revision_requested` feedback, the rework workflow produces a corrected version while recording what went wrong as a learning signal.

**Distinction from iterative refinement:** Refinement shapes the spec before production. Rework corrects the output after delivery. Different triggers, different data flow, same governance.

**Rework flow:**

```
Feedback: revision_requested on delivered artifact
 │
 ├── Load original ArtifactSpec
 ├── Load original ProductionTrace (full step chain)
 ├── Load client feedback (categories, raw text, operator notes)
 │
 ├── Diagnose: which production stage produced the problem?
 │   GPT-5.4-mini analyses trace + feedback → identifies failing step
 │   (e.g., "copy generation produced overly formal register")
 │   Diagnosis checks the FULL trace including input_data at each step,
 │   not just output. If the root cause is a config error (wrong
 │   copy_register, missing brand config, wrong persona loaded), the
 │   rework flags config correction to the operator instead of re-running
 │   production with the same wrong inputs.
 │
 ├── Re-run from failing step with feedback injected as context
 │   Original spec unchanged — the spec was correct, execution was wrong
 │   Feedback becomes additional production constraint
 │
 ├── QA: standard quality gate (Layer 0-4)
 │
 ├── Deliver revised version
 │   New artifact version linked to original (parent_artifact_id)
 │   revision_number incremented
 │
 └── Learn: rework trace is the richest learning signal
     What went wrong (diagnosed step)
     What feedback said (structured categories)
     What the fix was (re-run with constraints)
     → Feeds improvement loop (§15) as high-value training data
     → outcome_memory records rework event
```

**Workflow YAML:**

```yaml
# manifests/workflows/rework.yaml
name: rework
posture: production
model_preference:
  # inherits from original job's workflow — all gpt-5.4-mini Month 1-2
plan_enabled: false
stages:
  - name: diagnose
    role: qa
    tools: [trace_insight]
    action: analyse original trace + feedback to identify failing step
  - name: rerun
    role: production
    tools: []  # inherits from original workflow
    action: re-run from failing step with feedback as additional context
  - name: qa
    role: qa
    tools: [quality_gate]
    action: validate revised output against original spec
  - name: delivery
    role: delivery
    tools: [deliver]
    action: deliver revised version, link to original artifact
```

**Anti-drift:** Rework never modifies the original ArtifactSpec. If the spec itself was wrong (not the execution), that's a new refinement cycle, not a rework.

---

## 10. Workflow Packs

Each workflow is one YAML file in `manifests/workflows/`. Each stage declares its role, tools, knowledge permissions, and validation gates inline. One file per workflow — no separate staff definitions.

```yaml
# manifests/workflows/poster_production.yaml
name: poster_production
posture: production
model_preference:
  en_creative: gpt-5.4-mini       # Month 1-2 (all GPT-5.4-mini)
  bm_creative: gpt-5.4-mini
  short_copy: gpt-5.4-mini
image_model_preference:
  text_heavy: nano-banana-pro
  photorealistic: flux-2-pro
  draft: flux-2-dev
tripwire:
  enabled: true
  scorer_model: gpt-5.4-mini
  scorer_fallback: gpt-5.4-mini
  latency_threshold_ms: 5000
  threshold: 3.0
  max_retries: 2
  feedback_template: config/critique_templates/poster_quality.md
parallel_guardrails:
  - name: brand_voice
    model: gpt-5.4-mini
    check: compare output against client swipe bank + brand config
  - name: register_consistency
    model: gpt-5.4-mini
    check: verify casual/formal matches client copy_register setting
plan_enabled: false
stages:
  - name: intake
    role: intake
    tools: [classify_artifact]
    action: normalise and classify
  - name: production
    role: production
    tools: [generate_poster, image_generate]
    knowledge: [client, brand_pattern, swipe]
    action: produce poster from spec
    section_tripwire: false
  - name: qa
    role: qa
    tools: [visual_qa]
    action: validate against spec
  - name: delivery
    role: delivery
    tools: [deliver]
    action: deliver via gateway
```

**YAML fields:**

- `model_preference` — prose model routing per language × task type. All set to gpt-5.4-mini Month 1-2. Overrides system default when present.
- `image_model_preference` — image model routing map per visual task type. Includes `character_iterative` and `character_anchored` for illustration consistency.
- `tripwire` — mid-production quality check configuration. `enabled`, `scorer_model`, `scorer_fallback`, `latency_threshold_ms`, `threshold` (1-5 scale), `max_retries`, `feedback_template` path. Feedback template should be critique-then-revise, not score-only.
- `parallel_guardrails` — list of async guardrail subagents. Each declares `name`, `model`, and `check` description. Flags collected by GuardrailMailbox (dedup by issue type) before QA stage processes them.
- `section_tripwire` — per-stage override. When true on a stage, tripwire fires after that stage completes before proceeding. Used for long-form documents where per-section quality matters.
- `plan_enabled` — whether this workflow supports campaign plan decomposition (§39). When true, the workflow can receive tasks from a campaign plan and report progress back.
- `quality_techniques` — per-workflow activation of 8 quality-raising techniques (§4.2). Declares self_refine mode, exemplar_injection, critique_chain dimensions, persona, domain_vocab, contrastive_examples, diversity_instruction.
- `context_strategy` — graduated context compaction for long-form workflows. Values: simple (default), rolling_summary (three-tier for sequential production), aggressive (extreme context pressure). When `rolling_summary`, the workflow executor runs a `post_step_update` stage after each sequential production step.
- `rolling_context` — configuration for RollingContext contract (§43). Declares recent_window, medium_scope, entity tracking, checkpoint targets.
- `creative_workshop` — `true` for full workshop, `"derivative"` for inherited projects (§42.6.1), `false` for no workshop.
- `derivative_source` — project ID to inherit from when `creative_workshop: derivative`.

Phase 1 roles defined inline: Intake, Strategy, Brand/Style, Production, QA/Reviewer, Delivery. Later: BizOps, Knowledge. If cross-workflow role reuse becomes complex, extract staff definitions at that point — not before.

The generic workflow executor reads the YAML, iterates stages, calls tools, validates. New workflows = new YAML files, zero code.

Workflows referencing tools from Extended sessions (S16-S29) validate structurally from S9 but fail at runtime until those tools are built. This is intentional — the YAML is the spec, the tool comes later. The phase gate (`config/phase.yaml`) prevents premature routing to unbuilt workflows.

---

## 11. Cold Start Prevention

### 11.1 The Problem

An empty engine is useless. Without pre-loaded templates, patterns, copy formulas, brand knowledge, and quality references, every request is a cold start — expensive, slow, and low quality.

### 11.2 Template Library

50-60 template variants covering every common client request:

```
templates/visual/
├── promotional/ (sale, new_product, seasonal, bundle_offer × 3 ratios)
├── festive/ (raya, mawlid, national_day, generic × 3 ratios)
├── social/ (instagram_post, instagram_story, facebook_post, facebook_cover)
├── information/ (menu_pricelist, event, operating_hours, hiring, testimonial)
├── showcase/ (product_card, before_after, comparison)
└── document_covers/ (proposal, report, ebook)
```

Generated from the 8 existing design patterns applied to each use case category. Pattern A (minimal) + promotional/sale = one template. Curate the top 30, keep the rest as functional defaults.

### 11.3 Graphic Element Library

50-100 graphic elements as transparent PNGs in MinIO storage:

- Decorative borders and frames (Islamic geometric, modern minimal, festive gold)
- Background textures (paper, marble, fabric, gradient)
- Overlay patterns (geometric, floral, abstract)
- Icon sets (food, shopping, contact, social media, Islamic)
- Festive assets: Raya (ketupat, pelita, crescent, Malay motifs), Ramadan (lanterns, dates), National Day (Jalur Gemilang, Twin Towers)

Generated via fal.ai in a pre-Session 1 sprint. Catalogued in `config/stock_assets.yaml`.

### 11.4 Copy Pattern Library

100-150 copy pattern cards covering Malaysian marketing conventions:

```
config/copy_patterns/
├── greetings/ (raya, mawlid, ramadan, generic — BM formal/casual variants)
├── cta/ (retail, services, food — "Dapatkan sekarang", "Tempah sekarang")
├── headlines/ (promotional, awareness, educational — formula patterns)
├── industry/ (food_beverage, fashion_textile, beauty_wellness, education)
└── dialect/ (terengganu.yaml — legacy, migrated to config/dialect_systems/)
```

Each file generates 5-10 knowledge cards on ingestion.

### 11.5 Brand Pattern Library

20-30 international brand pattern files extracted from training knowledge:

```
config/brand_patterns/
├── nike.yaml (voice: imperative, visual: minimal bold, lessons for SME)
├── apple.yaml (voice: benefit-led, visual: premium minimal)
├── petronas.yaml (voice: emotional storytelling, festive: Malaysian unity, cinematic)
├── grab.yaml (voice: SE Asian warmth, multilingual, community-driven)
├── shopee.yaml (voice: playful urgency, visual: bright, promo-heavy)
├── airasia.yaml (voice: cheeky accessible, visual: red-dominant, deal-focused)
├── ikea.yaml (voice: democratic design, visual: lifestyle, warm)
├── uniqlo.yaml (voice: understated quality, visual: clean lifestyle)
└── ... (20-30 total across global + SEA + Malaysian brands)
```

Each pattern file documents: voice (register, tone, signature devices), visual (density, typography, imagery, colour philosophy), campaign patterns (festive, product launch, social), and lessons for SME — how the pattern scales down to small business budgets. Generates 3-5 knowledge cards per file. Total: 60-150 cards.

### 11.6 Document Scaffolds

6-8 content scaffolds for common document types:

```
config/document_scaffolds/
├── proposal.yaml (cover, exec summary, scope, timeline, pricing, terms)
├── marketing_plan.yaml (situation, objectives, strategy, tactics, budget, KPIs)
├── report.yaml (exec summary, findings, analysis, recommendations)
├── company_profile.yaml (about, services, portfolio, team, contact)
├── invoice.yaml (SSM number, bank details, itemised, terms)
└── content_calendar.yaml (weekly grid, platform columns, content type tags)
```

Each defines: required sections, typical length, tone guidance, example stubs. Feeds into ArtifactSpec when a document job enters production.

### 11.7 Quality Reference Corpus

30-50 calibrated examples across artifact families:

```
evaluations/reference_corpus/
├── posters/ (excellent: 5, good: 5, acceptable: 5)
├── proposals/ (excellent: 3, good: 3, acceptable: 3)
├── brochures/ (excellent: 3, good: 3, acceptable: 3)
├── social_graphics/ (excellent: 5, good: 5, acceptable: 5)
└── documents/ (excellent: 3, good: 3)
```

Quality gate compares output against these tiers. "Is this closer to excellent or acceptable?" Needs real examples, not vibes.

### 11.8 Malaysian Calendar and Events

One YAML file with ~50 events for the year:

```yaml
# config/calendar/malaysia_2026.yaml
events:
  - name: Hari Raya Aidilfitri
    date: 2026-03-20
    type: festive
    prep_window_days: 30
    industries_affected: [all]
    content_themes: [family, gratitude, forgiveness, new_beginnings]
  - name: Back to School
    date: 2026-01-05
    type: commercial
    prep_window_days: 21
    industries_affected: [education, stationery, fashion, food]
  # ... full year
```

Morning brief checks this: "Raya is 30 days away. DMB hasn't started Raya campaign. Suggest: initiate planning."

### 11.9 Client Pre-Seeding

For existing clients (DMB, Ar-Rawdhah, Rempah Tok Ma):

- `config/clients/{id}.yaml` with brand config from operator knowledge
- 8-12 seed knowledge cards per client (business facts, products, audience, positioning)
- No prior deliverables to promote — all three clients start with zero exemplars. Quality posture begins at Canva-baseline. Exemplar library grows from production.

For new clients — a client onboarding workflow:

1. Brief intake (voice note, text, uploaded collateral)
2. Brand config generation from intake + brand pattern matching ("your taste aligns with Uniqlo's minimal + Petronas' warmth")
3. Style profile seeding (vision + OCR on uploaded designs, or pick from template directions)
4. Knowledge card seeding (8-12 cards from intake)
5. First calibration artifact (low-stakes poster as preference learning)

Output: warm client in one session.

### 11.10 Client Template Export/Import (Post-Sprint)

Standardised export format for client configurations — enables faster onboarding by cloning from similar clients. When onboarding client #4, start from DMB's template (similar industry) and modify rather than authoring from scratch. Each new client inherits learned patterns from similar clients, accelerating Ring 3 data compounding.

**Export:** `export_client_template(client_id)` → sanitised YAML with brand config, workflow overrides, quality posture, copy register, design system preferences. No API keys, no financials, no client-specific knowledge cards. Secret scrubbing via allowlist (only export fields explicitly marked as portable).

**Import:** `import_client_template(template_path, new_client_id)` → populates `config/clients/{id}.yaml` with template defaults. Operator reviews and adjusts before first production job.

~30 lines total across two functions in `tools/onboarding.py`. Built post-sprint as S11 enhancement.

### 11.10 Swipe File Ingestion

Tool: `tools/swipe_ingest.py` — takes a screenshot/image of a design that works, runs vision + OCR, extracts layout, palette, typography, tone, CTA pattern. Creates 2-3 knowledge cards + optional StyleProfile. This is how the pattern library grows over time. Every good design you encounter becomes institutional knowledge.

### 11.11 Day-1 Asset Manifest

| Category | Count | Source |
|----------|-------|--------|
| Visual template variants | 50-60 | Generated from 8 patterns |
| Stock hero images | 354 | Ported from pro-max |
| Graphic elements | 50-100 | Generated via fal.ai |
| Festive asset packs | 30-50 | Generated via fal.ai |
| Copy pattern cards | 100-150 | Authored + training knowledge |
| Brand pattern files | 20-30 | Training knowledge |
| Document scaffolds | 6-8 | Authored |
| Swipe file cards | 50-100 | Operator's swipe collection |
| Quality reference corpus | 30-50 calibrated examples | Operator's best prior work |
| Malaysian calendar | ~50 events | Authored |
| Client configs | 3 files | Manual pre-seeding |
| Client seed cards | 24-36 | Manual from briefs |

Total pre-loaded knowledge: ~350-550 cards + 50-60 templates + 100-150 graphic assets + calibrated quality corpus.

---

## 12. Research Capabilities

Research is Core, not Extended. Without research, production is ungrounded — generic output that loses clients.

### 12.1 Why Research Is Core

When you receive "buatkan content calendar untuk DMB bulan depan," you need to know what's trending in batik this month, what competitors are posting, what seasonal events are coming, and what content gaps exist. Without that, the calendar is generic. Research is what makes the difference between "AI-generated" and "informed output that happens to be AI-produced." Research directly affects the quality of revenue-producing work.

### 12.2 Available Research Tools

| Tool | Capability | In deps? |
|------|-----------|----------|
| Listening engine | 5 social sources + 2 ads library adapters | Yes |
| pytrends | Google Trends data for Malaysia | Yes |
| yt-dlp + youtube-transcript-api | YouTube competitor research + transcript extraction | Yes |
| Hermes web search | General research via web tools | Built-in |
| Hermes browser tool | Page scraping and screenshot analysis | Built-in |

### 12.3 Two Research Modes

**Production-embedded (automatic).** When a job enters production, the routing function checks: does this artifact type benefit from fresh context? If yes, run a lightweight gather step. A poster for a food business during Ramadan → quick pytrends pull for trending iftar topics → inject as context. Adds seconds, improves output.

**Standalone (requested).** You request: "research batik industry trends" or "apa competitor DMB buat bulan ni." Routing classifies as research artifact, runs the full research workflow, delivers a structured report or populates knowledge cards for future production.

### 12.4 Research Workflow

```yaml
# manifests/workflows/market_research.yaml
stages:
  - name: scope
    staff: strategy
    action: define research questions from brief or calendar trigger
  - name: gather
    staff: strategy
    tools: [listening_engine, pytrends, youtube_research, web_search]
    action: collect signals from multiple sources
  - name: synthesise
    staff: strategy
    action: compress into structured research cards
  - name: store
    staff: delivery
    action: create knowledge cards, store research artifact if requested
```

### 12.5 Research Artifact Types

```yaml
research:
  families:
    market_analysis: [competitor_report, trend_report, audience_analysis, content_gap_analysis]
    content_research: [topic_brief, industry_overview]
```

### 12.6 Calendar-Triggered Proactive Research

The Malaysian calendar (`config/calendar/malaysia_2026.yaml`) drives proactive research via Hermes cron. "Raya is 30 days away → run trend research for Raya + client industries → store as knowledge cards → surface to you on Telegram." You decide whether to act on it, not the system.

### 12.7 Knowledge Retrieval

One retrieval function. One query. One config that maps artifact types to relevant card types:

```yaml
# config/retrieval_profiles.yaml
profiles:
  poster: [client, swipe, brand_pattern, seasonal]
  document: [client, copy_pattern]
  brochure: [client, brand_pattern, copy_pattern, swipe]
  research: [client, research]
  content_calendar: [client, research, seasonal, copy_pattern]
  default: [client, seasonal]
```

The retrieval function takes artifact type + client ID, looks up the profile, queries `knowledge_cards WHERE card_type IN (profile types) AND (client_id = X OR client_id IS NULL)`, returns ranked results. Always inject client brand config (~200 tokens from YAML) and seasonal context (~50 tokens, deterministic). Everything else is profile-driven.

Not five named pools with five code paths — one function, one query, one config file.

---

## 13. Token Efficiency

**Principle:** Every token spent must either improve the artifact the client receives or prevent an error the client would notice. If a token doesn't do either, don't spend it. Never sacrifice quality for efficiency. Never be wasteful either.

### 13.1 Three Operation Tiers

**Tier A — Deterministic (zero tokens).** Operations where the answer is computable without LLM reasoning: pattern-matched routing for clear requests, readiness checks when all fields are present, structural QA (file valid, dimensions correct, zones populated), spec revision from structured feedback, calendar lookups, client config loading, template selection by ID.

**Tier B — GPT-5.4-mini Month 1-2 / Local model Month 3+ (near-zero cost).** Operations where light reasoning is needed but the output isn't client-facing: ambiguous routing classification, readiness scoring for borderline cases, knowledge card relevance filtering, QA scoring for repeat patterns, research query formulation.

**Tier C — Cloud model (full budget).** Operations where quality directly affects what the client receives: production drafting, client-facing refinement questions, research synthesis, creative direction generation, QA for new patterns or new clients, first job for any client. GPT-5.4-mini Month 1-2. Multi-model Month 3+. No shortcuts.

**Escalation rule:** If Tier A can't resolve with confidence, escalate to Tier B. If Tier B output quality is uncertain, escalate to Tier C. Never skip tiers downward unless the distillation pipeline has qualified that specific artifact type for local model production.

### 13.2 Fast-Path Routing

Not every request needs LLM classification. A deterministic fast-path handles unambiguous requests at zero tokens: "poster" + known client → poster workflow. "Invoice DMB" → invoice workflow. Pattern matching handles 60-70% of requests. The LLM routing path activates only when the fast-path can't resolve.

### 13.3 Lazy Knowledge Retrieval

Don't inject all 5 knowledge pools into every prompt. Always inject client brand config (~200 tokens from YAML) and seasonal context (~50 tokens, deterministic). Inject brand patterns only for visual artifacts. Copy patterns only for text-heavy artifacts. Research cards only for content planning. Swipe matches only for visual replication. A simple poster reprint with a new date needs ~200 tokens of context, not 2,000.

### 13.4 Progressive Quality Gate

Level 0 — Structural (zero tokens). Valid file, correct dimensions, required text zones populated. Deterministic Python checks.

Level 1 — Template conformance (zero tokens). Output matches template structure, all zones populated. Visual QA via scikit-image, pixelmatch, opencv.

Level 2 — LLM quality scoring (~2,000 tokens). Compare against reference corpus. Only triggered for: new artifact types, exploration posture, first job for a new client, or when Level 0-1 flags an anomaly.

Most production jobs (repeat patterns, standard documents) pass Level 0-1 and never hit Level 2.

### 13.5 Pack Progressive Disclosure

System prompt includes pack names and one-line descriptions only (~200 tokens total). Full pack content loaded only when the routing function selects that workflow. The production prompt for a poster job includes only the poster workflow pack and production staff pack, not all packs.

### 13.6 Where to Spend Fully

Never economise on: production drafting (the client sees this), client-facing refinement questions (professionalism matters), research synthesis (cheap synthesis is useless), first job for any new client (first impression), exploration posture jobs (false negatives waste more than tokens). Quality comes from the production draft and the knowledge grounding, not from routing classification or QA on repeat patterns.

### 13.7 Research-Validated Efficiency Techniques

**Prompt caching** (Day 1, ~20 lines in call_llm wrapper). Every LLM call structured as stable prefix (persona + templates + client config, ~1,200 tokens) + variable suffix (job-specific content). Stable prefix uses provider prompt caching headers (Anthropic cache_control, OpenAI cached input). 90% savings on cached input tokens for repeat patterns. The persona files, vocabulary files, and critique templates become cached prompt blocks.

**Structured output for utility calls** (Day 1, ~15 lines per critique template). Every non-creative LLM call (scoring, routing, classification, extraction) requests JSON with specific fields. The critique template outputs `{"dimension": "text_visibility", "score": 3, "issues": [...], "revision_instruction": "..."}` — not prose paragraphs. Creative calls (text generation, prose) remain unstructured. Output tokens cost 3-5x more than input.

**Observation masking** (Day 1, ~30 lines in workflow executor). After each workflow stage completes, compress that stage's tool output before passing to the next stage. Keep reasoning trace, summarise observation data. Prevents context accumulation across 5+ stage workflows. Stage 2 research output (2,000 tokens) summarises to 200 tokens after production uses it.

**Token-Efficient Tool Use** (Day 1, ~5 lines). When using Claude 4 models, enable token-efficient-tools header. Reduces tool output verbosity by 14-70%.

**Semantic caching for retrieval** (Month 2+, ~30 lines). When retrieval volume exceeds 50 queries/day, add cache-check before full retrieval pipeline: embed query → check pgvector for similar recent queries → if similarity > 0.92, return cached result. Store in retrieval_cache table with TTL.

**LLMLingua prompt compression** (Month 4+). When daily token usage exceeds 50% of free tier (5M tokens/day), implement LLMLingua for aggressive prompt compression (up to 20x with 1.5% quality loss). Not needed at current scale.

---

## 14. Production Chain Traces

### 14.1 Why Chains, Not Flat Traces

Most Vizier jobs are multi-step chains where intermediate outputs feed the next step. A flat trace that captures the final prompt and output misses the critical question: what happened between steps, what worked, why, and at what cost?

### 14.2 The StepTrace Model

Every step in the production chain is a link:

```python
class StepTrace:
    step_number: int
    step_name: str       # "routing", "refinement_1", "copy_generation"
    step_type: str       # "llm", "deterministic", "retrieval", "human"
    input_summary: str   # human-readable
    input_data: dict     # structured
    prompt: str | None   # exact prompt if LLM step
    model: str | None    # which model
    output_summary: str  # human-readable
    output_data: dict    # structured — retrievable intermediate output
    tokens_in: int
    tokens_out: int
    cost_rm: float
    duration_ms: int
    tier: str            # "A", "B", or "C" — which efficiency tier
    proof: dict | None   # optional structured evidence of step success
                         # e.g. {"nima_score": 6.8, "brand_voice_match": 0.92,
                         #        "readability": 78, "clip_similarity": 0.81}
                         # Populated by QA stages, tripwire scorers, and guardrails.
                         # Feeds improvement loop (§15) — enables correlation of specific
                         # proof dimensions with operator approval at the step level.

class ProductionTrace:
    job_id: str
    client_id: str
    artifact_type: str
    steps: list[StepTrace]   # the full chain, ordered
    total_tokens: int
    total_cost_rm: float
    first_pass_approved: bool
```

### 14.3 The TraceCollector

A context manager that instruments the pipeline silently:

```python
class TraceCollector:
    @contextmanager
    def step(self, name: str, step_type: str):
        trace = StepTrace(step_number=len(self.steps) + 1, ...)
        self.current_step = trace
        yield trace
        self.steps.append(trace)
```

Every pipeline function wraps its work in `collector.step()`. The prompt, input, output, tokens, cost, and tier are captured automatically. One context manager per step. Data accumulates from the first production job.

### 14.4 Retrieving Intermediate Outputs

Every step's `output_data` is queryable. "Show me the copy from step 6 of job DMB-0042" returns the raw copy text. "Get me the direction options from step 3" returns the 3 options and which one the client selected. Full chain visibility, any step, any job.

### 14.5 Interaction Model — Three Levels

**Level 1 — Passive (zero effort).** Post-delivery insight appears in the delivery message: "This poster used 40% fewer tokens than average because fast-path routing skipped refinement." Morning brief (Session 7) includes 5-line production insights from the last 7 days.

**Level 2 — Conversational (low effort).** Ask Hermes in natural language: "Which poster prompts work best?" "What happens if I skip research for DMB?" "Compare the chains for DMB-0042 and DMB-0038." The insight tool queries production_trace JSONB and synthesises answers. Same Telegram interface.

**Level 3 — Experiment (intentional effort).** "Next 5 DMB posters, skip brand pattern injection. Compare against last 5." System registers experiment, applies condition, auto-compares after 5 jobs, reports results.

### 14.6 Storage

`production_trace` JSONB column on the jobs table. The steps array holds the full chain. JSONB path queries reach into individual steps for analysis.

---

## 15. Self-Improvement Loop

### 15.1 The Closed Loop

The system doesn't just produce — it learns how to produce better. The loop: trace → detect patterns → propose improvements → you approve → test → validate → promote → improved production.

### 15.2 Pattern Detection (Automatic)

After every 10 completed jobs of a given artifact type (minimum 20 total), the system analyses traces for:

- **Approval correlations** — which knowledge cards, prompt structures, and step sequences correlate with first-pass approval
- **Cost outliers** — jobs that cost 2x+ more than median and what was different
- **Step value** — quality delta between jobs that included a step and jobs that didn't
- **Prompt patterns** — structural commonalities in approved vs revision-needed prompts
- **Refinement convergence** — which shaping moves resolve ambiguity fastest

Deterministic analysis — SQL aggregations, not LLM calls. Cheap.

### 15.3 Improvement Proposals (Surfaced to You)

When patterns are actionable, the system generates a proposal delivered via Telegram:

```
💡 IMPROVEMENT PROPOSAL: poster-cta-exact

Observation: DMB poster prompts with exact CTA text from spec
get 93% approval vs 68% when CTA is LLM-generated.

Proposed change: Add instruction "Use CTA text exactly as provided."
Expected: +25% approval, -200 tokens
Confidence: high (34 jobs)

/test — run experiment  |  /promote — apply now  |  /reject — discard
```

Proposal types: prompt refinement, step elimination, step reordering, knowledge injection optimisation, readiness threshold adjustment, new fast-path pattern, refinement strategy change, model downgrade candidate.

### 15.4 Experimentation (Automatic After Your Approval)

`/test` registers an experiment. Next N matching jobs get the experimental condition. Traces are tagged. After N jobs, automatic comparison:

```
✅ EXPERIMENT COMPLETE: poster-cta-exact
Control: 3/5 approved, 2,400 tokens avg
Experiment: 5/5 approved, 2,200 tokens avg
/promote — lock it in  |  /extend — 5 more jobs  |  /reject — revert
```

### 15.5 Promotion (One Command)

`/promote` updates the WorkflowPack YAML (or prompt template, or knowledge config), logs a decision note, and all future jobs use the improved version.

### 15.6 Refinement ↔ Improvement Feedback Loop

Iterative refinement produces the richest traces — structured feedback at each cycle with options shown, selected, rejected, and preference reasons. The improvement system learns from this:

- Client preferences emerge — "DMB always picks warm traditional. Stop showing modern minimal for DMB."
- Shaping moves get ranked per client — "For DMB, show options first. For Ar-Rawdhah, ask questions first."
- Readiness thresholds auto-calibrate — "Brochures consistently ready at 0.7, not configured 0.8. Lower it."
- Fast-path templates emerge — After 15 identical DMB poster refinement paths, propose a pre-filled template that skips refinement entirely.

The refinement loop collects structured preference data. The improvement system analyses it and feeds lessons back. Each subsequent refinement is faster, cheaper, and more accurate.

### 15.7 Research-Validated Optimisation Techniques

**Failure analysis mode** (S19). In addition to correlation-based pattern detection, actively diagnose failures: query traces WHERE operator_rating < 3.0, cluster by common features (artifact type, client, quality dimension), ask GPT-5.4-mini to diagnose patterns and propose instruction changes. Reflective improvement rules accumulate in `config/improvement_rules/` and inject into relevant prompt templates. This is the GEPA/SIMBA pattern adapted for the existing improvement detector.

**Exemplar set optimisation** (S19, after 20+ exemplars per artifact type). Instead of individually curated exemplars, find the optimal COMBINATION of 3 exemplars that maximises quality across a validation batch. Try 10 random combinations, score each against 10 held-out test cases, keep the best. ~50 lines. Run monthly or when 10+ new exemplars are promoted. Different exemplar combinations produce different results — the optimal set is not the 3 individually-best exemplars.

**Prompt template versioning.** Every template in `config/prompt_templates/` and `config/critique_templates/` has a `version` field and `validation_score`. When improvements are approved via `/promote`, version increments, old version archived in `config/prompt_templates/archive/`. Revertible — `/revert` restores previous version.

**Automated prompt variation testing** (S19, after 20+ rated examples per artifact type). Generate 3 prompt variants via GPT-5.4-mini ("rewrite this template 3 different ways while preserving the intent"). Score each against 10 held-out examples. Present best improvement with before/after scores. ~80 lines. This is the DSPy compile-time optimisation pattern without the framework dependency.

**Future: GEPA autonomous evolution** (Month 3+). When 100+ rated examples exist per artifact type, GEPA (`pip install gepa`, also available as `dspy.GEPA`) can autonomously evolve ALL prompt templates using reflective prompt evolution. The architecture notes the integration point. For now, the manual improvement loop with reflective failure analysis is sufficient.

### 15.8 Safety Boundary

The system proposes. You decide. It never modifies a production prompt, skips a step, downgrades a model, or changes a workflow without your explicit `/promote` command. Two human gates: approve the test, approve the promotion. Optional auto-promote rules for high-confidence, low-risk improvements after the system earns trust.

### 15.9 Trajectory Over Time

Month 1: Generic defaults. 3-4 refinement cycles per brochure. Every client gets the same treatment.

Month 3: System proposes improvements. DMB refinement drops to 1-2 cycles. Research step skipped for repeat patterns. Readiness thresholds calibrated per type.

Month 6: Fast-path templates for common patterns. "DMB promotional poster" goes from 4 refinement cycles to 0. Production cost per job drops ~50%.

Month 12: Refinement has trained itself out of most jobs for established clients. New clients converge faster because the system recognises preference clusters. Distillation moves proven patterns to Qwen local. Near-zero marginal cost.

### 15.10 Drift Detection

The improvement loop has two human gates (approve test, approve promotion) but can still drift in three ways that the gates don't catch: metric gaming (optimizing for spurious correlations), diversity collapse (exemplar library converging on a narrow aesthetic), and rubric drift (operator and scorer gradually training each other into a local optimum). Three mechanisms detect and counteract this.

**Holdout anchor set.** During Month 1, lock 10-15 calibration examples rated by the operator at peak attention, spanning the full quality spectrum from 2/5 to 5/5, across multiple artifact types and clients. Tag these as `anchor_set: true` on the feedback table. These never enter the exemplar library, never enter the training pool, never influence the improvement loop. Every 30 days, re-score these same examples using the current scorer + current rubric. If average scores on the anchor set drift by more than 0.5 from their original ratings, surface a warning via Telegram:

```
⚠️ DRIFT ALERT: Quality baseline may be shifting.

Anchor set original avg: 3.4/5
Anchor set current scorer avg: 4.1/5 (+0.7 drift)

Your rubric may have relaxed, or the scorer may have adapted to
your rating patterns. Please re-rate these 15 anchors with fresh
eyes and compare against your original Month 1 ratings.

/review-anchors — open anchor review
```

This is a monthly Hermes cron job. ~15 scorer calls per month (free on GPT-5.4-mini). The anchor set is the fixed reference point that prevents the system and operator from co-drifting.

**External benchmark injection.** Every 30 days, inject 5 outputs sourced from outside the system — competitor designs, international marketing examples, different visual approaches — into the operator's rating queue alongside production work. The operator rates them without knowing which are external vs production. Track the ratings:

- External consistently rated LOWER than production → healthy. Vizier output is genuinely better than the market.
- External rated EQUAL to production → the system's quality ceiling may not be rising despite the improvement loop claiming gains.
- External rated HIGHER than production → the system may have plateaued or regressed. Trigger manual review of recent promotions.

The external examples are stored as `benchmark_source: external` on feedback records. They are excluded from the improvement loop's pattern detection — they exist only as a reality check. The operator curates 5 examples monthly from competitor social media, design award sites, or international brand campaigns. 15 minutes of collection, significant protection against closed-loop drift.

**Improvement velocity decay alert.** Track improvement proposals generated per 50 completed jobs. Expected pattern:

- Month 1-3: 3-5 proposals per 50 jobs (many patterns to discover)
- Month 3-6: 1-2 proposals per 50 jobs (major patterns learned)
- Month 6+: 0-1 proposals per 50 jobs (system approaching optimum)

If proposals drop to zero for 100+ consecutive jobs while quality metrics are stable, the system may have stopped learning — not because it's optimal, but because the rubric has converged with the scorer and there are no disagreements left to learn from. Surface an alert:

```
ℹ️ LEARNING PLATEAU: No improvement proposals in 112 jobs.

This could mean: (a) production is truly optimal, or (b) the scorer
and rubric have converged and can no longer detect improvement
opportunities.

Recommended: review anchor set, inject external benchmarks, or
manually rate 10 recent outputs with deliberate critical attention.

/review-anchors — open anchor review
/run-benchmark — inject external examples
```

The three mechanisms work together: the anchor set detects absolute drift (is the baseline shifting?), external benchmarks detect relative drift (is the system keeping up with the market?), and velocity decay detects learning stagnation (has the loop stopped improving?). All three are lightweight — monthly cron, minimal tokens, operator action only when alerts fire.

**Implementation:** Anchor set tagging is a boolean field on the feedback table (added in S10a). The monthly cron, scorer re-evaluation, and alerts are built in S19 alongside the rest of the improvement system. External benchmark injection is an operator discipline with a simple ingestion tool (variant of swipe_ingest that tags `benchmark_source: external`). Total implementation: ~50 lines in S19 + 1 column in S10a.

---

## 16. Data Model — 37 Tables

All 37 tables (35 in local Postgres, 2 in local LibSQL) created progressively. Core Postgres tables during foundation session. Extended Postgres tables on-demand by the session that needs them. LibSQL tracing tables created by S7 directly. Empty tables cost nothing. Populated progressively as sessions activate them.

**Migration safety:** All CREATE TABLE statements use `IF NOT EXISTS`. All trigger creation checks for existence before creating. This ensures migrations can be re-run safely if they fail partway through. No data loss, no manual cleanup, no DROP CASCADE risk. Applies to both `migrations/core.sql` and `migrations/extended.sql`.

```sql
-- Example pattern for all tables:
CREATE TABLE IF NOT EXISTS example_table (
  id uuid primary key default gen_random_uuid(),
  -- ... columns
);

-- Example pattern for all triggers:
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'feedback_silence_trigger'
  ) THEN
    CREATE TRIGGER feedback_silence_trigger ...;
  END IF;
END $$;
```

**Table relationships (quick reference):**

- A **client** has many **jobs**. A client has many **knowledge_cards** (client-specific) and **exemplars**.
- A **job** has one **client**. A job has many **artifact_specs** (revisions). A job has many **artifacts** (drafts, finals). A job has one **feedback** record. A job has many **policy_logs**. A job has one **production_trace** (JSONB on jobs table).
- An **artifact_spec** belongs to one job. An artifact references one spec.
- An **artifact** belongs to one job and one spec. An artifact has one **asset** (the file). An artifact can have a **parent_artifact** (self-referential — NULL for first versions, populated by rework workflow §9.1). An artifact can be promoted to an **exemplar**.
- An **asset** is the binary file. Assets have visual metadata (colours, layout, CLIP embedding) as nullable columns. Assets link to **visual_lineage** entries recording which jobs used them and why. Assets track `times_used` for utilisation analysis.
- **feedback** links to one job, one artifact, one client. Feedback drives the state machine (§29.5). Operator rating is independent of client feedback.
- **knowledge_cards** belong to one **knowledge_source** and optionally one client. Cards have embeddings for retrieval.
- **exemplars** link to one artifact and one client. Exemplars are the "approved output" reference library.
- **outcome_memory** links to one job, one artifact, one client. Records what worked and what was rejected.
- **visual_lineage** links one job + one artifact + one asset with a role (template, stock_image, exemplar_reference, etc.).

**Split into two migration files:**

### migrations/core.sql — 14 tables (created during foundation session S10a)

### 16.1 Core (8 tables — active from Session 4)

```sql
CREATE TABLE IF NOT EXISTS clients (
  id uuid primary key default gen_random_uuid(),
  name text not null, industry text,
  brand_config jsonb, style_profiles jsonb,
  contact_info jsonb, billing_config jsonb,
  brand_mood text[],  -- maps to design system mood tags for §38.1.1 selector
  status text default 'active',
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS jobs (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id),
  raw_input text, interpreted_intent jsonb, routing_result jsonb,
  job_type text, status text default 'received',
  hermes_session_id text, priority text default 'normal',
  posture text default 'production',
  production_trace jsonb,  -- full step chain as JSONB
  goal_chain jsonb,        -- optional: links job to campaign/business goal ancestry
                           -- e.g. {"campaign": "Raya 2026", "objective": "increase festive sales 30%",
                           --        "strategy": "4-week countdown content", "this_job": "week 1 teaser poster"}
                           -- Populated by S16 BizOps when job originates from campaign plan.
                           -- NULL for standalone jobs. Feeds improvement loop (§15) for goal-level pattern detection.
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS artifact_specs (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id),
  revision_number int default 1, is_provisional boolean default true,
  spec_data jsonb not null, confidence float, completeness float,
  status text default 'provisional', promoted_at timestamptz,
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS artifacts (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id), spec_id uuid references artifact_specs(id),
  artifact_type text, role text default 'draft',
  parent_artifact_id uuid references artifacts(id),
  asset_id uuid references assets(id),
  version_number int default 1, status text default 'created',
  created_at timestamptz default now()
);
```

`parent_artifact_id` is self-referential: NULL for first versions, populated by the rework workflow (§9.1) when a revised artifact links back to the original. Test this FK in S10a exit criteria — insert artifact with NULL parent, insert child pointing to parent, verify both queries work.

```sql
CREATE TABLE IF NOT EXISTS assets (
  id uuid primary key default gen_random_uuid(),
  storage_path text not null, filename text,
  mime_type text, size_bytes bigint,
  -- Visual metadata (nullable for non-visual assets like data exports)
  asset_class text,        -- 'source', 'template', 'generated', 'exemplar', 'reference'
  asset_category text,     -- 'stock_hero', 'graphic_element', 'festive', 'swipe', 'client_upload'
  dominant_colours jsonb,  -- extracted via colorthief
  colour_palette_type text, -- 'warm', 'cool', 'neutral', 'vibrant', 'muted'
  layout_type text,        -- 'minimal', 'dense', 'centered', 'split', 'grid', 'full_bleed'
  width_px int, height_px int, aspect_ratio text,
  tags text[], seasons text[], industries text[],
  visual_embedding vector(512), -- CLIP ViT-B/32 via open_clip, queried via pgvector
  times_used int default 0,
  last_used_at timestamptz,
  quality_tier text,
  operator_rating int,
  source text,             -- 'fal.ai', 'uploaded', 'generated', 'swipe_ingest', 'stock'
  parent_asset_id uuid references assets(id),
  client_id uuid references clients(id),
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS deliveries (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id), artifact_id uuid references artifacts(id),
  destination text, delivered_at timestamptz, status text default 'pending'
);

CREATE TABLE IF NOT EXISTS policy_logs (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id),
  action text, outcome text, reason text, context jsonb,
  evaluated_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS feedback (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id),
  artifact_id uuid references artifacts(id),
  client_id uuid references clients(id),
  -- Feedback state machine
  -- awaiting → explicitly_approved | revision_requested | rejected | silence_flagged
  -- silence_flagged → prompted → responded | unresponsive
  feedback_status text default 'awaiting',
  delivered_at timestamptz,
  feedback_received_at timestamptz,
  prompted_at timestamptz,
  silence_window_hours int default 24,
  -- Client feedback
  spec_revision int,
  options_shown jsonb,
  selected text,
  rejected jsonb,
  feedback_categories jsonb,  -- {copy: 'approved', layout: 'revision', colour: 'approved'}
  feedback_richness_level int, -- 0=binary, 1=categorical, 2=directional, 3=comparative
  raw_text text,
  -- Operator assessment (independent of client)
  operator_rating int,        -- 1-5
  operator_notes text,
  operator_rated_at timestamptz,
  -- Drift detection (§15.10)
  anchor_set boolean default false,       -- true = locked calibration example, excluded from training
  benchmark_source text,                  -- NULL = production, 'external' = injected benchmark
  -- Derived
  response_time_hours float,  -- delivery to first feedback
  created_at timestamptz default now()
);
```

Silence is not approval. Only `explicitly_approved` counts as a positive quality signal. `silence_flagged` and `unresponsive` are excluded from quality calculations entirely — they are tracked as feedback collection rate, a separate operational metric. When silence is flagged, Vizier sends one low-pressure follow-up via the delivery channel. One prompt, not nagging.

### 16.2 Knowledge (4 tables — populated Session 8/12)

```sql
CREATE TABLE IF NOT EXISTS knowledge_sources (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id), source_type text,
  title text not null, description text,
  asset_id uuid references assets(id), domain text,
  language text, quality_tier text, status text default 'active',
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS knowledge_cards (
  id uuid primary key default gen_random_uuid(),
  source_id uuid references knowledge_sources(id),
  client_id uuid references clients(id),
  card_type text, title text, content text not null,
  tags text[], domain text, embedding vector(1536),
  confidence float, status text default 'active',
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS exemplars (
  id uuid primary key default gen_random_uuid(),
  artifact_id uuid references artifacts(id),
  client_id uuid references clients(id),
  artifact_family text, artifact_type text,
  approval_quality text, style_tags text[], summary text,
  status text default 'active', created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS outcome_memory (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id), artifact_id uuid references artifacts(id),
  client_id uuid references clients(id),
  first_pass_approved boolean, revision_count int default 0,
  accepted_as_on_brand boolean, human_feedback_summary text,
  cost_summary jsonb, quality_summary jsonb,
  promote_to_exemplar boolean default false,
  created_at timestamptz default now()
);
```

### 16.3 Infrastructure (2 tables — populated progressively)

```sql
CREATE TABLE IF NOT EXISTS visual_lineage (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id),
  artifact_id uuid references artifacts(id),
  asset_id uuid references assets(id),
  role text not null,  -- 'template', 'stock_image', 'graphic_element', 'texture',
                       -- 'overlay', 'exemplar_reference', 'swipe_reference'
  selection_reason text,
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS system_state (
  id uuid primary key default gen_random_uuid(),
  version text not null,          -- '0.1.0', '0.2.0', etc.
  change_type text not null,      -- 'session_ship', 'improvement_promotion', 'config_change'
  change_description text not null,
  changed_by text not null,       -- 'operator', 'improvement_loop'
  previous_state jsonb,           -- snapshot of what changed (for rollback)
  promoted_from_experiment text,
  created_at timestamptz default now()
);
```

Engine versioning: Session ships = minor version (0.1.0 → 0.2.0). Improvement promotions = patch version (0.2.0 → 0.2.1). Manual config changes = patch version. Every system_state row captures previous_state as JSONB for rollback.

### migrations/extended.sql — 21 tables (created on-demand by the session that needs them)

Note: 2 additional tracing tables (spans, memory_routing_log) are created by S7 in local LibSQL, not in extended.sql. Total extended tables: 23 (21 Postgres + 2 LibSQL).

### 16.4 Business Operations (3 tables — created by S16)

```sql
CREATE TABLE IF NOT EXISTS invoices (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id), job_ids uuid[],
  amount_rm decimal(10,2) not null, currency text default 'MYR',
  description text, issued_at timestamptz default now(),
  due_at timestamptz, paid_at timestamptz,
  status text default 'draft', invoice_number text,
  pdf_asset_id uuid references assets(id), notes text
);

CREATE TABLE IF NOT EXISTS payments (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid references invoices(id), client_id uuid references clients(id),
  amount_rm decimal(10,2) not null, payment_method text,
  reference_number text, received_at timestamptz default now(), notes text
);

CREATE TABLE IF NOT EXISTS pipeline (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id), prospect_name text,
  stage text default 'lead', estimated_value_rm decimal(10,2),
  proposal_asset_id uuid references assets(id),
  next_followup_at timestamptz, source text, notes text,
  created_at timestamptz default now(), updated_at timestamptz default now()
);
```

### 16.4a Steward — Personal Assistant (6 tables — created by S16)

```sql
CREATE TABLE IF NOT EXISTS steward_inbox (
  id uuid primary key default gen_random_uuid(),
  raw_input text not null,
  input_type text default 'text',
  source_message_id text,
  processed boolean default false,
  processed_at timestamptz,
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS steward_projects (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  objective text not null,
  domain text,
  status text default 'active',
  decomposed boolean default false,
  decomposition_approved boolean default false,
  horizon text default 'project',
  parent_project_id uuid references steward_projects(id),
  total_tasks int default 0,
  completed_tasks int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS steward_tasks (
  id uuid primary key default gen_random_uuid(),
  inbox_id uuid references steward_inbox(id),
  project_id uuid references steward_projects(id),
  title text not null,
  description text,
  next_action boolean default false,
  context text,
  energy_level text,
  time_estimate_min int,
  domain text,
  status text default 'active',
  waiting_for text,
  due_date date,
  defer_until date,
  completed_at timestamptz,
  completion_note text,
  recurrence text,
  recurrence_anchor text,
  streak_count int default 0,
  streak_last_date date,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS steward_reviews (
  id uuid primary key default gen_random_uuid(),
  review_type text not null,
  review_date date not null,
  domain_scores jsonb,
  completion_stats jsonb,
  neglected_domains text[],
  thriving_domains text[],
  stuck_projects jsonb,
  energy_reflection text,
  wins text[],
  adjustments text[],
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS steward_health_log (
  id uuid primary key default gen_random_uuid(),
  log_date date not null unique,
  sleep_hours float,
  sleep_quality text,
  bedtime timestamptz,
  waketime timestamptz,
  steps int,
  active_calories int,
  exercise_minutes int,
  resting_heart_rate int,
  mindful_minutes int,
  raw_data jsonb,
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS steward_learning (
  id uuid primary key default gen_random_uuid(),
  resource_type text not null,
  resource_title text not null,
  wisdom_vault_id text,
  domain text,
  total_units int,
  completed_units int default 0,
  unit_type text default 'page',
  status text default 'active',
  takeaways jsonb,
  last_reviewed_at timestamptz,
  review_interval_days int default 14,
  started_at timestamptz default now(),
  completed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
```

### 16.5 Compound Artifacts (2 tables — created by S21)

```sql
CREATE TABLE IF NOT EXISTS bundles (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id), bundle_type text,
  bundle_name text, status text default 'planning',
  delivery_id uuid references deliveries(id),
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS bundle_members (
  id uuid primary key default gen_random_uuid(),
  bundle_id uuid references bundles(id),
  artifact_id uuid references artifacts(id),
  member_role text, sequence_order int
);
```

### 16.6 Tracing & Memory — Extended (2 tables — created by S7 in LibSQL)

```sql
-- Note: spans stored in local LibSQL as first tracing layer. Schema shown here
-- for completeness. Coexists with Langfuse cloud tracing.

CREATE TABLE IF NOT EXISTS spans (
  id uuid primary key default gen_random_uuid(),
  trace_id uuid,
  parent_span_id uuid references spans(id),
  name text not null,         -- 'routing', 'production', 'quality_gate'
  span_type text not null,    -- 'llm', 'tool', 'retrieval', 'deterministic'
  model text,
  input_tokens int,
  output_tokens int,
  cost_rm float,
  duration_ms int,
  status text default 'ok',  -- 'ok', 'error', 'degraded'
  metadata jsonb,
  started_at timestamptz default now(),
  ended_at timestamptz
);

CREATE TABLE IF NOT EXISTS memory_routing_log (
  id uuid primary key default gen_random_uuid(),
  session_id text,
  memory_operation text not null,  -- 'summarise', 'compress', 'retrieve', 'store'
  model_used text not null,        -- 'gpt-5.4-mini' (Month 1-2)
  input_tokens int,
  output_tokens int,
  routed_to_local boolean default true,
  reason text,
  created_at timestamptz default now()
);
```

### 16.7 Calibration — Extended (4 tables — created by S19)

```sql
CREATE TABLE IF NOT EXISTS datasets (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  dataset_type text not null,  -- 'quality_calibration', 'routing_training', 'preference_pairs'
  version int default 1,
  item_count int default 0,
  diversity_score float,       -- CLIP embedding variance — alerts if diversity drops
  status text default 'draft', -- 'draft', 'locked', 'archived'
  locked_at timestamptz,
  metadata jsonb,
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS dataset_items (
  id uuid primary key default gen_random_uuid(),
  dataset_id uuid references datasets(id),
  input_data jsonb not null,
  expected_output jsonb,
  actual_output jsonb,
  score float,
  tags text[],
  source text,  -- 'production', 'synthetic', 'external'
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS experiments (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  experiment_type text not null,  -- 'prompt_variant', 'model_comparison', 'step_elimination'
  dataset_id uuid references datasets(id),
  config jsonb not null,
  status text default 'pending',  -- 'pending', 'running', 'completed', 'cancelled'
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS experiment_results (
  id uuid primary key default gen_random_uuid(),
  experiment_id uuid references experiments(id),
  variant_name text not null,
  metrics jsonb not null,  -- {approval_rate, avg_tokens, avg_cost, quality_scores}
  winner boolean default false,
  notes text,
  created_at timestamptz default now()
);
```

### 16.8 Campaign — Extended (2 tables — created by S22+)

```sql
CREATE TABLE IF NOT EXISTS plans (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id),
  plan_name text not null,
  plan_type text default 'campaign',  -- 'campaign', 'content_calendar', 'launch'
  brief text,
  kpis jsonb,              -- [{metric, target, current}]
  status text default 'draft',
  start_date date,
  end_date date,
  replanning_triggers jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS plan_tasks (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid references plans(id),
  job_id uuid references jobs(id),
  task_name text not null,
  task_type text,           -- artifact type to produce
  scheduled_at timestamptz,
  dependencies uuid[],     -- other plan_task IDs that must complete first
  status text default 'pending',
  cron_job_id text,        -- Hermes cron reference
  completed_at timestamptz,
  created_at timestamptz default now()
);
```

### 16.9 Social Media — Extended (3 tables — created by S24)

```sql
CREATE TABLE IF NOT EXISTS social_accounts (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id),
  platform text not null,           -- 'instagram', 'facebook', 'tiktok', 'whatsapp'
  account_handle text,
  credentials_ref text,             -- Hermes credential pool reference (never store raw tokens)
  autonomy_level text default 'draft_approve',
  posting_config jsonb,
  status text default 'active',
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS social_posts (
  id uuid primary key default gen_random_uuid(),
  social_account_id uuid references social_accounts(id),
  job_id uuid references jobs(id),
  plan_task_id uuid references plan_tasks(id),
  platform text not null,
  content_text text,
  asset_ids uuid[],
  scheduled_at timestamptz,
  posted_at timestamptz,
  platform_post_id text,
  status text default 'draft',
  engagement_metrics jsonb,
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS social_interactions (
  id uuid primary key default gen_random_uuid(),
  social_account_id uuid references social_accounts(id),
  social_post_id uuid references social_posts(id),
  interaction_type text not null,    -- 'comment', 'dm', 'mention', 'review'
  platform_interaction_id text,
  author_handle text,
  content_text text,
  sentiment text,                    -- 'positive', 'neutral', 'negative', 'question'
  response_status text default 'pending',
  response_text text,
  responded_at timestamptz,
  created_at timestamptz default now()
);
```

### 16.10 Course — Extended (1 table — created by S23)

```sql
CREATE TABLE IF NOT EXISTS course_projects (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id),
  job_id uuid references jobs(id),
  course_name text not null,
  target_audience text,
  module_count int,
  modules jsonb,
  status text default 'planning',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
```

**Token tracking:** Handled by Langfuse, not a custom table. Every LLM call tagged with `{client_id, tier, job_id}` via Langfuse SDK custom metadata. Query Langfuse API for cost breakdowns.

**Quality metrics:** Computed from source tables via Postgres views, not materialised snapshots. First-pass approval rate, feedback collection rate, refinement cycles — all derivable from jobs, feedback, and artifacts with timestamp filters. Promote to materialised views when tables exceed 10K rows.

**Visual metadata** lives on the assets table as nullable columns. No separate table.

---

## 17. Artifact Taxonomy

Complete taxonomy in `config/artifact_taxonomy.yaml`:

**Classes:** editable_office, final_form, visual, media, system, bizops, research, bundles.

**Key families:** documents, spreadsheets, presentations, business_pdf, illustrated_books, long_form, promotional, multi_panel, brochure, web, short_video, narrated, automation, data, financial, pipeline, client_health, market_analysis, content_research, marketing_bundle, educational_bundle.

**Classification rules:** Editable? → editable_office. Finished document? → final_form. Visual/brand-led? → visual. Time-based? → media. Multiple coordinated outputs? → bundle. Business operations? → bizops. Information gathering? → research. Automation/code? → system.

---

## 18. Publishing Lane

Compound artifact production for ebooks, illustrated children's books, serialised fiction, and novels. A first-class revenue lane, not a future consideration.

Requires: PlanningObject, CharacterRegistry, StyleLock, StoryBible, NarrativeScaffold, RollingContext (§43), illustration consistency pipeline (§6.3).

**Publishing types and timeline:**

| Product | When | Dependencies |
|---------|------|-------------|
| Ebook / industry guide | Core ship | Typst + GPT-5.4-mini + assembly |
| Children's illustrated book (BM) | Core ship | Illustration pipeline validated + creative workshop |
| Serialised short fiction | Week 2+ | RollingContext validated on ebook sections |
| Full novel | Month 2-3 | Serial validates chapter-level coherence |

**Workflow:** Creative workshop (§42.6) → readiness gate → planning object with narrative scaffolding → page/chapter-by-page production with RollingContext → self-refine per page/chapter → illustration generation with character consistency → post-page-update (rolling summary + entity extraction + consistency verification) → assembly (ebooklib/Typst) → operator review checkpoint → delivery.

**Renderers:** ebooklib (EPUB), Typst (PDF), fal.ai via Kontext/IP-Adapter/Nano Banana Pro (illustrations — path selected during endpoint testing).

Full publishing intelligence specification in §42.

---

## 19. Business Operations

Invoicing, payment tracking, sales pipeline, revenue visibility, client health monitoring. Not a separate system — additional artifact types and workflows on the same engine.

**Invoice flow:** Request → create record → Typst template → PDF → MinIO storage → deliver via Telegram/email.

**Revenue cron (weekly):** Total invoiced, received, outstanding, overdue, trend.

**Client health cron (daily):** Last job per client, overdue invoices, pipeline followups.

**Pipeline:** Conversational CRUD via Telegram. lead → contacted → proposal_sent → negotiating → won/lost.

---

## 20. Steward — Personal Assistant

A GTD-based, ADHD-friendly personal assistant running on the same engine as Vizier. Separate Telegram bot (`@steward_bot`), separate persona, same Postgres, same Hermes runtime. Not a separate system — another door on the same engine.

### 20.1 Design Principles

**GTD pipeline:** Capture → Process → Organize → Review → Engage. Every interaction maps to one of these. The system is the "trusted external brain" — nothing captured is ever lost, nothing processed requires re-thinking.

**ADHD-friendly by default:**

- **Zero-friction capture.** Voice note, text dump, forwarded message — all go to inbox. No forms, no categories, no structure required at capture time. Processing happens later (by Steward, not by you).
- **Never show the full list.** The `/next` command shows ONE task. Not a list of 47 things that triggers overwhelm. One thing. Do it or skip it.
- **No open-ended questions.** Steward presents options, you tap. "Which domain?" with 4 buttons, not "What would you like to work on?"
- **Time blindness protection.** Steward tells you what's happening NOW. Prayer-anchored scheduling creates temporal landmarks. "45 minutes until Asr — enough for one focused task."
- **Hyperfocus interrupts.** Gentle nudges at prayer times, not aggressive nagging. One message, not a countdown. If you're deep in flow, `/snooze 30m` defers without guilt.
- **Decision fatigue reduction.** `/next` picks FOR you based on energy, context, deadline, and domain balance. You don't choose from a list — you either do the suggested task or tap "skip" for the next suggestion.
- **Dopamine visibility.** Every `/done` shows: streak count, domain progress bar, and a one-line win summary. Progress is always visible, never buried in a dashboard you won't open.
- **Working memory offload.** Steward remembers context across conversations. "Continue the thing from yesterday" works. Brain dump at 2am, process at 10am — no information lost.

### 20.2 Data Model (6 tables — created by S16)

```sql
CREATE TABLE IF NOT EXISTS steward_inbox (
  id uuid primary key default gen_random_uuid(),
  raw_input text not null,          -- voice transcript, text, forwarded content
  input_type text default 'text',   -- 'text', 'voice', 'forward', 'image'
  source_message_id text,           -- Telegram message ID for reference
  processed boolean default false,
  processed_at timestamptz,
  created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS steward_tasks (
  id uuid primary key default gen_random_uuid(),
  inbox_id uuid references steward_inbox(id),  -- NULL if created directly
  project_id uuid references steward_projects(id),  -- NULL if standalone
  title text not null,
  description text,
  -- GTD dimensions
  next_action boolean default false,  -- true = actionable now, false = someday/waiting
  context text,                       -- 'home', 'office', 'errands', 'phone', 'computer', 'anywhere'
  energy_level text,                  -- 'high', 'medium', 'low' — what energy this task REQUIRES
  time_estimate_min int,              -- estimated minutes
  -- Domain tracking (21 Wisdom Vault domains)
  domain text,                        -- maps to one of 21 life domains
  -- Status
  status text default 'active',       -- 'active', 'waiting', 'someday', 'done', 'cancelled'
  waiting_for text,                   -- who/what you're waiting on (GTD waiting-for list)
  due_date date,                      -- hard deadline (NULL = no deadline)
  defer_until date,                   -- don't show before this date
  -- Completion
  completed_at timestamptz,
  completion_note text,               -- optional reflection on what you learned/felt
  -- Recurrence
  recurrence text,                    -- 'daily', 'weekly', 'monthly', NULL
  recurrence_anchor text,             -- 'prayer:subuh', 'prayer:maghrib', 'weekday:monday', 'month:1'
  streak_count int default 0,
  streak_last_date date,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS steward_projects (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  objective text not null,            -- "What does DONE look like?" — single sentence
  domain text,                        -- primary life domain
  status text default 'active',       -- 'active', 'someday', 'done', 'cancelled'
  -- Decomposition
  decomposed boolean default false,   -- true after GPT-5.4-mini breaks objective into tasks
  decomposition_approved boolean default false,  -- operator confirms task list
  -- GTD horizons
  horizon text default 'project',     -- 'project' (outcome), 'area' (ongoing), 'goal' (12-month)
  parent_project_id uuid references steward_projects(id),  -- for sub-projects
  -- Progress
  total_tasks int default 0,
  completed_tasks int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS steward_reviews (
  id uuid primary key default gen_random_uuid(),
  review_type text not null,          -- 'daily', 'weekly', 'monthly'
  review_date date not null,
  -- Snapshot data (JSONB for flexibility)
  domain_scores jsonb,                -- {domain: {tasks_done, tasks_active, hours_invested, trend}}
  completion_stats jsonb,             -- {done, added, overdue, waiting, inbox_unprocessed}
  neglected_domains text[],           -- domains with zero activity in review period
  thriving_domains text[],            -- domains with above-average activity
  stuck_projects jsonb,               -- projects with zero task completions in review period
  -- Operator input (filled during review ritual)
  energy_reflection text,             -- "How was your energy this week?"
  wins text[],                        -- manually noted wins
  adjustments text[],                 -- what to change next period
  created_at timestamptz default now()
);
```

### 20.3 Interaction Model

All interactions via dedicated Telegram bot (`@steward_bot`). Same Hermes runtime, different gateway bot token, different persona.

**Capture (zero friction):**

- Text message → `steward_inbox` immediately. No processing, no acknowledgment beyond "✓ Captured."
- Voice note → Whisper transcription → `steward_inbox`. Same zero-friction.
- `/dump` → multi-line brain dump mode. Everything until `/end` goes to inbox as one entry.

**Process (Steward does the work, you confirm):**

- Steward processes inbox items via GPT-5.4-mini: extracts task title, suggests project/domain/context/energy/time estimate.
- Presents as: "📥 *Buy groceries for Ramadan* — Home / Low energy / 30min / Domain: Health. ✅ Confirm | ✏️ Edit | 🗑 Skip"
- Batch processing: `/process` shows unprocessed inbox items one by one. Tap-tap-tap.

**Engage (one task at a time):**

```
/next                    → Steward picks ONE task. Shows title + why this one.
                           "This is high-energy and you said you're at peak energy.
                            Due tomorrow. Domain: Career (neglected 5 days)."
/next low                → Pick a low-energy task specifically
/next [domain]           → Pick from a specific domain
/done                    → Complete current task. Show streak + domain progress.
/done "learned X"        → Complete with reflection note
/skip                    → Skip suggested task, show next suggestion
/waiting "Ahmad reply"   → Move to waiting-for list with note
/snooze 30m              → Defer current task suggestion for 30 minutes
/defer friday            → Don't show this task until Friday
```

**Organize:**

```
/project "Learn Typst"           → Create project, Steward decomposes objective into tasks
                                    Presents decomposition for confirmation
/projects                        → List active projects with progress bars
/someday                         → Move task/project to someday/maybe
/contexts                        → List tasks grouped by context (for errand batching)
```

**Review:**

```
/snapshot                → NOW: active tasks, overdue count, today's completions,
                           domain heatmap (green/amber/red), current streak
/review                  → Weekly review prep:
                           - Inbox: X unprocessed items
                           - Done this week: N tasks across M domains
                           - Neglected: [domains with 0 activity]
                           - Thriving: [domains with most activity]
                           - Stuck projects: [zero completions this week]
                           - Waiting-for: [items with no response]
                           - Proposed priorities for next week
                           Operator confirms or adjusts.
/stats                   → Completion rate, avg tasks/day, domain distribution chart,
                           streak history, energy pattern (when do you complete most?)
/stats [domain]          → Deep dive on one domain
```

**Energy + Prayer integration:**

```
/energy high|medium|low  → Sets energy level for task recommendations
                           Auto-adjusts: morning after Subuh = high (default),
                           after Zohor = medium, after Asr = low
```

**Prayer-anchored scheduling:**

- **Subuh** → Morning brief: overnight inbox captures, today's top 3 (auto-selected by priority + domain balance), prayer times for the day, any deadlines today.
- **Zohor** → Mid-day pulse (only if requested or if something is overdue): "2 tasks done, 1 overdue, 3 remaining. Energy adjustment?"
- **Asr** → No new heavy tasks suggested. Low-energy items only. "Wind down. 2 hours until Maghrib."
- **Maghrib** → Shutdown trigger: "Done for today? 4 tasks completed. Domain: Career +2, Health +1, Deen +1. Streak: 12 days. Tomorrow's top 3: [auto-selected]."
- **Isyak** → System quiet. Only responds if you initiate. No proactive messages after Isyak.

### 20.4 Domain Balance System

The 21 Wisdom Vault domains serve as life balance categories. Each task and project maps to one domain. Steward tracks activity per domain and surfaces imbalances.

**Domain heatmap (in /snapshot and /review):**

```
🟢 Career      ████████░░  8 tasks this week
🟢 Deen        ██████░░░░  6 tasks
🟡 Health      ███░░░░░░░  3 tasks
🟡 Family      ██░░░░░░░░  2 tasks
🔴 Finance     ░░░░░░░░░░  0 tasks (7 days neglected)
🔴 Learning    ░░░░░░░░░░  0 tasks (12 days neglected)
```

**Nudge mechanism:** When `/next` picks a task, it considers domain balance. If Finance has been neglected for 7+ days and there's an active Finance task, it gets priority boost. Not forced — just nudged. The explanation says "Domain: Finance (neglected 7 days)" so you understand why.

**Weekly review surfaces patterns:** "You consistently neglect Finance and Learning on busy weeks. These domains have 4 active tasks between them. Consider: 1 Finance task Monday morning, 1 Learning task Friday afternoon."

### 20.5 Project Decomposition

When you create a project with `/project "objective"`, Steward decomposes it:

```
You: /project "Set up children's book publishing pipeline on KDP and Shopee"

Steward: Breaking down this project...

📋 *KDP + Shopee Publishing Pipeline* (Career)
Objective: Set up children's book publishing pipeline on KDP and Shopee

Proposed tasks:
1. Research KDP account requirements (🏠 Low 20min)
2. Create KDP publisher account (💻 Medium 30min)
3. Research Shopee digital product listing rules (💻 Low 20min)
4. Prepare Book 1 manuscript PDF for KDP format (💻 High 45min)
5. Design KDP product listing (cover, description, keywords) (💻 High 60min)
6. Submit Book 1 to KDP review (💻 Low 15min)
7. Create Shopee seller listing for Book 1 (💻 Medium 30min)
8. Test purchase flow on both platforms (📱 Low 15min)

✅ Approve all | ✏️ Edit | ➕ Add more | 🗑 Start over
```

Decomposition via GPT-5.4-mini (~2K tokens, free). You confirm, edit, or reject. Tasks are created with suggested context, energy, and time estimates. All linked to the project.

### 20.6 Atomic Habits Engine

Habit tracking built on James Clear's four laws framework. Each habit is a designed behaviour loop, not just a checkbox.

**Habit design template:**

```yaml
# Example habit entry
habit_id: morning_quran
title: "Read 1 page of Quran after Subuh"
identity: "I am someone who starts every day with Quran"
domain: deen
# Four Laws
cue:
  trigger: "prayer:subuh"           # fires after Subuh prayer time
  stacking: null                     # or: "after:morning_quran" for chaining
  environment: "musolla/bedroom"
craving:
  motivation: "Connection with Allah, calm start to day"
  visual_cue: "Quran on nightstand"  # environment design reminder
response:
  action: "Read 1 page of Quran"
  minimum_version: "Read 1 ayat"     # 2-minute rule: the version that always counts
  time_estimate_min: 10
  energy_level: low
reward:
  satisfaction: "Mark complete → streak visible → domain progress"
  celebration: "Alhamdulillah ✓"     # micro-celebration text shown on completion
# Tracking
frequency: daily
streak_count: 0
streak_best: 0
grace_period_days: 1                  # miss 1 day without breaking streak (never miss twice)
active: true
```

**The four laws as system design:**

1. **Make it obvious (Cue):** Habits trigger from prayer times, other habits (stacking), time of day, or context. Steward sends ONE cue at the right moment — not a list of everything due. "Subuh done. Time for Quran? Just 1 ayat counts."
2. **Make it attractive (Craving):** Identity statements connect habits to who you're becoming. `/snapshot` shows "You are 47 days into being someone who reads Quran daily." Dopamine from identity reinforcement, not just streak numbers.
3. **Make it easy (Response):** Every habit has a `minimum_version` — the 2-minute version that always counts. Steward never asks "did you do your full 30-minute workout?" It asks "did you do at least 1 pushup?" The minimum version removes the activation energy barrier that ADHD amplifies.
4. **Make it satisfying (Reward):** Every completion triggers: streak update, domain progress bar, celebration micro-text, and — for milestone streaks (7, 21, 30, 66, 100 days) — a larger acknowledgment. The reward is immediate and visible, not delayed.

**Habit scorecard (daily):**

Part of the morning brief. Not asking "what habits do you want to do today?" but presenting: "Here's your habit scorecard from yesterday. +1 for each done, -1 for each missed, 0 for non-applicable."

```
Yesterday's scorecard:
+1 Quran after Subuh (streak: 47)
+1 10min walk after Zohor (streak: 12)
-1 Journal before sleep (missed — streak reset to 0)
+1 No phone after Isyak (streak: 5)

Score: +2 | Habit completion: 75%
```

**Habit stacking chains:** Habits can reference other habits as triggers. "After morning Quran → morning journal → morning walk" creates a chain where completing one cues the next. Steward presents the NEXT habit in the chain, not the whole chain.

**Never miss twice logic:** `grace_period_days: 1` means missing one day doesn't break the streak. Missing two consecutive days does. Steward's messaging on a miss: "Missed journal yesterday. That's fine — one miss doesn't break the chain. Today's the day that matters. Just write 1 sentence." No guilt, no lectures.

### 20.7 Deep Work Integration

Structured deep work tracking built on Cal Newport's principles. Steward manages the boundary between deep and shallow work.

**Deep work blocks:**

```
/deep [duration]         → Start a deep work timer. Steward goes silent.
                           No messages, no nudges, no habit cues until timer ends.
                           Only interrupts for: prayer time arrival (gentle, one message).
/deep end                → End deep work session. Log hours + what you worked on.
/shallow                 → Tag current work as shallow (email, admin, errands).
                           Helps calculate deep/shallow ratio.
```

**Time blocking between prayers:**

Steward proposes daily time blocks anchored to prayer times — the natural rhythm already in the architecture:

```
Morning brief (post-Subuh):
  06:00-06:30  Habits chain (Quran, journal, walk)
  06:30-08:30  DEEP WORK BLOCK 1 (2 hrs — highest energy)
  08:30-09:00  Shallow: email, messages
  09:00-12:00  DEEP WORK BLOCK 2 (3 hrs — Vizier production)
  12:00-12:30  Zohor + break
  12:30-15:00  DEEP WORK BLOCK 3 (2.5 hrs — declining energy)
  15:00-15:30  Asr + no new intake
  15:30-17:00  Shallow: admin, follow-ups, planning
  17:00-18:30  Personal / family
  18:30         Maghrib → shutdown ritual
```

This is a SUGGESTION, not a schedule. Steward proposes it in the morning brief. You tap "Accept" or adjust. The structure exists to combat time blindness — you can see where you are in the day.

**Lead vs lag measures (4DX):**

- **Lag measures** = outcomes (revenue, books published, clients served). Tracked by Vizier.
- **Lead measures** = behaviours that drive outcomes (deep work hours, tasks completed, habits done). Tracked by Steward.
- Weekly review shows both: "This week: 14 deep work hours (lead) → 3 posters + 1 book chapter delivered (lag)."

**Wildly Important Goals (WIGs):** Steward limits active deep goals to 2-3 max. These connect to domains and projects. `/goals` shows your current WIGs with lead measure progress. "Goal: Publish 10 books by mid-May. Lead measure: 2 deep work hours/day on publishing. This week: 11.5 hours (target: 14)."

**Deep/shallow ratio tracking:**

```
/ratio                   → This week's deep/shallow split
                           Deep: 18 hrs (64%) | Shallow: 10 hrs (36%)
                           Target: 70/30 | Trend: improving ↑
```

**Productive meditation:** During low-energy periods (post-Asr), Steward can suggest: "Good time for a walk. Thinking prompt: How should the illustration style evolve for Book 3?" Captures any thoughts you voice-note during the walk as inbox items.

### 20.8 Apple Health Integration

Apple Health data informs Steward's recommendations. Not real-time — daily batch import. Steward reads your body's signals to adjust task difficulty, energy estimates, and habit nudges.

**Data flow:**

```
Apple Health (iPhone)
 │
 ├── Apple Shortcut runs daily at midnight
 │   Exports today's health data as JSON to iCloud/local file
 │
 ├── Hermes cron picks up the file (or manual /health-sync)
 │
 ├── Parse and store in steward_health_log table
 │
 └── Steward uses health context in:
     ├── Energy recommendation (bad sleep → suggest low-energy tasks)
     ├── Habit correlation ("You complete more tasks on 7+ hour sleep days")
     ├── Health habits tracking (steps, exercise, sleep as habit metrics)
     └── Weekly health summary in /review
```

**Health data table:**

```sql
CREATE TABLE IF NOT EXISTS steward_health_log (
  id uuid primary key default gen_random_uuid(),
  log_date date not null unique,
  -- Sleep
  sleep_hours float,
  sleep_quality text,            -- 'good', 'fair', 'poor' (derived from Apple Health sleep analysis)
  bedtime timestamptz,
  waketime timestamptz,
  -- Activity
  steps int,
  active_calories int,
  exercise_minutes int,
  -- Vitals
  resting_heart_rate int,
  -- Mindfulness
  mindful_minutes int,
  -- Raw export (full Apple Health JSON for future analysis)
  raw_data jsonb,
  created_at timestamptz default now()
);
```

**How health data affects recommendations:**

- **Sleep < 6 hours:** Morning brief says "Light sleep last night. Today's tasks adjusted to low-medium energy. Deep work blocks shortened to 90 min max." `/next` deprioritises high-energy tasks.
- **Sleep > 7.5 hours:** "Well rested. Good day for deep work. Block 1 extended to 3 hours." High-energy tasks get priority.
- **Steps < 3000 yesterday:** Habit nudge: "You moved less yesterday. Walk after Zohor? Even 10 minutes helps." Links to walking habit.
- **Exercise streak:** "5 days of 30+ exercise minutes. Longest streak this month." Dopamine.
- **Weekly pattern detection:** "You consistently sleep poorly on nights after no exercise. On days you walk 6000+ steps, your sleep averages 7.2 hours vs 5.8 hours without." Data-driven habit design.

**Privacy:** Health data stays local. Same Postgres on Mac Mini. Never sent to cloud models. The GPT-5.4-mini calls for recommendations receive only derived signals ("energy: low, reason: poor sleep") not raw health metrics.

### 20.9 Learning System

Structured learning tracking integrated with the Wisdom Vault (421 books, 21 domains) and Miftah (Quranic learning).

**Learning goals:**

```
/learn "Read 2 books on Islamic finance this quarter"
                         → Creates learning goal linked to Finance domain
                           Steward suggests books from Wisdom Vault in that domain
                           Tracks: books started, progress, key takeaways captured
```

**Learning data:**

```sql
CREATE TABLE IF NOT EXISTS steward_learning (
  id uuid primary key default gen_random_uuid(),
  -- What
  resource_type text not null,        -- 'book', 'course', 'article', 'quran', 'podcast'
  resource_title text not null,
  wisdom_vault_id text,               -- links to Wisdom Vault book if applicable
  domain text,
  -- Progress
  total_units int,                    -- pages, chapters, episodes, juz
  completed_units int default 0,
  unit_type text default 'page',      -- 'page', 'chapter', 'episode', 'juz', 'lesson'
  status text default 'active',       -- 'active', 'paused', 'done', 'dropped'
  -- Learning capture
  takeaways jsonb,                    -- array of key insights captured during reading
  last_reviewed_at timestamptz,       -- for spaced repetition nudges
  review_interval_days int default 14,-- next review after N days
  -- Tracking
  started_at timestamptz default now(),
  completed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
```

**Interactions:**

```
/reading                 → Current reading list with progress bars
/reading "Atomic Habits" 45    → Log 45 pages read. Update progress.
/takeaway "The 2-minute rule means..."
                         → Capture key insight, linked to current active reading
/review-learning         → Spaced repetition: "You read about habit stacking 14 days ago.
                           Key takeaway: 'Chain habits to existing routines.'
                           Still applies? Any update?"
```

**Wisdom Vault integration:** When Steward recommends a book for a learning goal, it checks the Wisdom Vault first. "For Islamic finance, your Vault has 3 unread books: [titles]. Start with the shortest?" No need to buy or find — you already own the knowledge.

**Miftah integration:** Quranic learning progress from Miftah (FSRS-based, already deployed) feeds into the Deen domain. "Miftah: 4 new ayat memorised this week. Deen domain: active. Retention rate: 87%." Read-only — Steward doesn't duplicate Miftah's spaced repetition, just surfaces its progress in domain reviews.

**Learning in weekly review:**

```
📚 Learning this week:
  "Atomic Habits" — 120/268 pages (45%) — 3 takeaways captured
  Quran memorisation (Miftah) — 4 new ayat, 87% retention
  
  Domains learning-active: Productivity, Deen
  Domains with unread Vault books: Finance (3), Health (2), Leadership (4)
  
  Due for review: "Deep Work" takeaways (last reviewed 21 days ago)
```

### 20.10 Implementation Notes

**Same engine, different door.** Steward uses the same Hermes runtime, same Postgres, same GPT-5.4-mini. The Telegram gateway distinguishes Vizier bot vs Steward bot by bot token. The persona file (`config/personas/steward.md`) defines Steward's voice: warm, concise, ADHD-aware, never overwhelming.

**Token cost:** Steward is lightweight. Inbox capture = zero tokens. Task processing = ~500 tokens per item via GPT-5.4-mini (free). Project decomposition = ~2K tokens (free). `/next` recommendation = ~1K tokens (free). Morning brief = ~2K tokens (free). Habit cues = ~200 tokens each (free). Health analysis = ~1K tokens daily (free). Total daily Steward usage: ~8K-15K tokens = 0.08-0.15% of 10M/day budget.

**No quality gate needed.** Steward tasks are personal, not client deliverables. No ArtifactSpec, no tripwire, no guardrails. The governance layer applies to Vizier production, not Steward. Steward's "quality" is measured by: inbox items processed within 24 hours, tasks completed per day, domain balance score, habit completion rate, deep work hours, and streak maintenance.

**Morning brief integration (S16).** The morning brief after Subuh synthesises BOTH Vizier data (jobs, revenue, pipeline, calendar) AND Steward data (yesterday's habit scorecard, today's top 3 personal tasks, energy recommendation from health data, domain balance snapshot, deep work block proposal, active streaks). One message, two systems, one operator.

**Shutdown ritual integration (S16).** The Maghrib shutdown synthesises both: Vizier production summary + Steward personal summary (tasks done, habits completed, deep work hours, health snapshot) + tomorrow's top 3 from both.

**Apple Health setup:** Create an Apple Shortcut that exports daily health summary (sleep, steps, calories, exercise, heart rate) as JSON to a shared folder. Hermes cron reads the file daily. Setup guide in `docs/decisions/apple_health_setup.md`. If Shortcut automation isn't configured, `/health-sync` accepts manual JSON paste. Health features degrade gracefully — Steward works fully without health data, just without body-informed recommendations.

**Table count impact:** 2 additional tables (`steward_health_log`, `steward_learning`) bring Steward from 4 to 6 tables. Total: 37 tables (35 Postgres + 2 LibSQL). Extended Postgres: 21 tables.

---

## 21. Persona Layer

Not a separate agent. Configuration in `.hermes.md` + `config/clients/{id}.yaml` + `config/personas/steward.md`.

The persona layer is deployment-specific configuration, not engine architecture. The current deployment configures three modes:

**Vizier (operator mode):** Production engine persona. Operator sees tool output, system state, debugging. Accessed via `@vizier_bot` Telegram. Full governance pipeline active.

**Vizier (recipient mode):** Client-facing delivery. Recipients see only polished responses and delivered artifacts. Distinguished by Hermes gateway DM pairing role.

**Steward (personal assistant mode):** GTD-based, ADHD-friendly personal assistant. Accessed via `@steward_bot` Telegram (separate bot token, same Hermes runtime). Warm, concise, never overwhelming. Presents options via buttons, not open-ended questions. Shows ONE task at a time. No governance pipeline — personal tasks are not client deliverables. Full spec in §20.

**Language detection:** Respond in same language as recipient (BM, English, mix). Code-switching level per `config/code_switching/rules.yaml` and client `code_switching` setting (auto/heavy/light/none). Loghat dialect for recipients with dialect configured, using dialect YAML from `config/dialect_systems/`. Steward uses operator's natural register.

**Interaction rules:** Never expose internals. Keep questions short. Maximum 2 questions before showing something visual. Use Islamic greetings naturally.

Other deployments configure their own persona rules via the same mechanism — language, tone, interaction patterns, cultural context. The engine doesn't assume any of these.

---

## 22. Knowledge Spine

Three tiers:

1. **Raw sources** (`knowledge_sources`) — books, PDFs, swipe files, collateral
2. **Knowledge cards** (`knowledge_cards`) — compressed 50-150 word retrieval cards with embeddings
3. **Exemplars** (`exemplars`) — approved prior outputs that influence future work

### 22.1 Contextual Retrieval (preprocessing — one-time per card)

Before embedding, every knowledge card is contextualised: an LLM-generated prefix (50-100 tokens) that explains what the card is about in the context of its source document. This reduces retrieval failures by 35-67% (Anthropic research).

Raw card: "Diskaun 30% untuk semua produk batik."
Contextualised: "This card is from DMB's Raya 2025 promotional campaign targeting middle-class Malay women. Diskaun 30% untuk semua produk batik."

The contextualised version is embedded. The raw version is what the production model sees. One-time preprocessing cost during seeding: ~50 tokens per card via GPT-5.4-mini (free). For ~200 initial cards: ~10K tokens total.

The contextualisation function (`utils/retrieval.py:contextualise_card()`) is built once by S12 and imported by S18. Single implementation, two consumers.

### 22.2 Retrieval Pipeline (built right first time — no phased migration)

```
Production request arrives
 │
 ├── Query transformation (GPT-5.4-mini, ~500 tokens, free)
 │   Generate 3-4 variants (BM + EN + expanded synonyms)
 │   Parallel retrieval across all variants
 │
 ├── Hybrid search (per variant, parallel)
 │   ├── pgvector semantic search → top 20
 │   └── Postgres FTS keyword search → top 20
 │   Merge via RRF (weight: dense 1.0, sparse 0.25)
 │   Deduplicate by card_id → top 20 unique
 │
 ├── Cross-encoder reranking (GPT-5.4-mini, ~3K tokens, free)
 │   Score all 20 candidates jointly with query
 │   Select top 5 by relevance score
 │
 ├── Lost-in-the-middle reordering (zero cost)
 │   Best → position 1, second-best → position 5
 │   Remaining fill positions 2-4
 │
 └── Inject into production prompt
     5 high-quality, contextualised knowledge cards
```

Why no phased migration: Postgres already has FTS. pgvector is a standard extension. GPT-5.4-mini handles contextualisation, query transformation, and reranking within the free tier. All four layers (contextual + hybrid + reranking + query transform) are ~150 lines total across S12 and S18. Building naive first and upgrading later is strictly worse than building right once.

Configuration in `config/retrieval_profiles.yaml`:

```yaml
default:
  embedding_model: text-embedding-3-small
  embedding_dim: 1536
  min_score: 0.65
  rrf_weights: { dense: 1.0, sparse: 0.25 }
  reranker: gpt-5.4-mini
  reranker_candidates: 20
  reranker_top_k: 5
  query_variants: 4
  lost_in_middle: true
```

The exemplar retrieval function (`utils/retrieval.py:retrieve_similar_exemplars()`) is built once by S11 and imported by S13 for exemplar-anchored quality scoring. Single implementation, two consumers.

### 22.3 Card Lifecycle and Wisdom Vault

Card lifecycle: DRAFT→ACTIVE→REVIEW→DEPRECATED→ARCHIVED via status field. 127 seed cards; peak corpus 348-423 + ~8-12 per client.

Wisdom Vault integration: 421 books → knowledge_sources. Dual-layer atoms/cards → knowledge_cards. Obsidian vault unchanged — Vizier reads, never modifies.

---

## 23. Distillation Pipeline & Fine-Tuned Local Models

### 23.1 Fine-Tuned Model Roster

Three fine-tuned local models exist as part of the model stack (§6.1). These are narrow-task specialists trained on production data and external datasets, not general-purpose replacements for cloud models. ALL deferred to Month 3+ — GPT-5.4-mini handles these tasks Month 1-2 (anti-drift #31, #54).

**Qwen 3.5 4B — Quality Scorer.** Trained on poster preference pairs and production ratings. Scores outputs on quality dimensions (text legibility, layout balance, colour harmony, visual hierarchy, text-background contrast). Replaces GPT-5.4-mini for quality scoring after training, freeing budget for creative tasks. Used in Layer 2 tripwire checks (§7.4).

**Qwen 3.5 2B — Routing Classifier.** Trained on synthesised routing examples from workflow YAMLs. Classifies intent in <0.5 seconds (vs 3-5 seconds on prompted 9B). Dedicated classifier for fast-path overflow — when deterministic pattern matching can't resolve but full LLM reasoning isn't needed.

**Qwen 3.5 2B — Register Classifier.** Same base model, different LoRA adapter — swapped at runtime. Trained on labelled BM copy samples. 3-class classification (casual/formal/mixed). Used in Layer 3 parallel guardrails (§7.4) to verify BM register consistency.

### 23.2 Distillation Concept

Progressively move workloads from cloud models to local models without quality loss. Requires 20+ exemplar traces per artifact type — at current scale, 6-12 months of production data needed. GPT-5.4-mini at 10M free tokens/day means token cost is near-zero today.

**When to build full distillation:** When token cost becomes a real constraint (free tier changes, scale exceeds 200+ jobs/day, or new model opportunities emerge). The production traces and exemplar collection built in Core provide the data foundation. The fine-tuned models above are the first concrete step — narrow-task distillation that's already proven.

Training methodology, dataset preparation, hardware requirements, and retraining schedules are governed by the master plan — not this document.

---

## 24. Renderers

| Renderer | Use |
|----------|-----|
| Playwright | Posters, brochures, visual PDFs, landing pages, layout-heavy assets |
| WeasyPrint | PDF from HTML/CSS, illustrated pages |
| Typst | Structured PDFs, reports, ebooks, children's books, invoices |
| python-docx | Word documents |
| openpyxl | Spreadsheets |
| python-pptx | Slide decks |
| ebooklib | EPUB generation |
| FLUX.1 Kontext [pro/max] | Character-consistent illustrations (iterative), image editing, style transfer |
| FLUX General + IP-Adapter | Reference-anchored character consistency, style conditioning |
| Nano Banana Pro | Text-heavy posters, marketing graphics with BM copy, up to 14 references |
| Nano Banana 2 | Fast drafts, preview generation |
| FLUX.2 [pro] | Photorealistic product scenes, composed backgrounds, up to 4 references |
| FLUX.2 [dev] | Bulk element generation, graphic elements, textures, borders, fast iteration |
| edge-tts | Text-to-speech (Phase 2+) |

Image model routing: The workflow selects the image model based on job characteristics (§6.3). Text-heavy posters route to Nano Banana Pro. Photorealistic scenes route to FLUX.2 Pro. Sequential character consistency (children's books, series) routes to Kontext iterative or IP-Adapter anchored — path selected during endpoint testing. The visual brief expander (§38.3) runs before every image generation call regardless of model.

Every renderer behind a stable wrapper contract.

---

## 25. Repository Structure

```
vizier/
├── hermes-agent/               # Submodule: upstream NousResearch/hermes-agent v0.7.0
├── .hermes.md                  # Agent instructions (persona rules)
├── AGENTS.md                   # Build conventions, phase governance
├── CLAUDE.md                   # Claude Code context
│
├── contracts/                  # Governance as Python
│   ├── artifact_spec.py        # ArtifactSpec, ProvisionalArtifactSpec
│   ├── policy.py               # PolicyDecision, PolicyEvaluator, phase gate
│   ├── readiness.py            # ReadinessGate, refinement loop, limits
│   ├── routing.py              # route_request() (3-phase), RoutingResult, fast-path, design system selector
│   ├── trace.py                # StepTrace, ProductionTrace, TraceCollector (Core)
│   ├── context.py              # RollingContext (§43) — serves novels, campaigns, documents, client memory
│   ├── packs.py                # Unified WorkflowPack loader (incl quality_techniques, context_strategy)
│   ├── publishing.py           # PlanningObject, CharacterBible, StoryBible, NarrativeScaffold, StyleLock
│   ├── bizops.py               # Invoice, Payment, Pipeline models (Extended)
│   ├── steward.py              # Steward personal assistant tools: inbox, next, done, snapshot, review, project decomposition (Extended)
│   ├── knowledge.py            # KnowledgeSource, Card, Exemplar, retrieval
│   ├── improvement.py          # PatternDetector, ImprovementProposal, Experiment (Extended)
│   └── visual_dna.py           # Visual DNA extraction orchestrator (colorthief, open_clip, mediapipe)
│
├── middleware/
│   ├── quality_gate.py         # Structural assertions + GuardrailMailbox + operator rating collection
│   └── posture.py              # Exploration vs production + quality posture strictness
│
├── tools/                      # Custom Hermes tools
│   ├── poster.py               # generate_poster (ported from pro-max)
│   ├── image.py                # image_generate — generic fal.ai wrapper for posters, marketing graphics, elements
│   ├── illustrate.py           # Publishing illustration pipeline — character consistency, LoRA composition,
│   │                           #   reference anchoring, CLIP verification, anchor frame reset (Core, S15)
│   │                           #   Split from image.py: image.py handles fire-and-forget generation,
│   │                           #   illustrate.py handles stateful sequential production where each page
│   │                           #   depends on prior pages. If the two converge (same API calls, same error
│   │                           #   handling), re-merge into image.py with an `illustration_mode` flag.
│   ├── publish.py              # ebook/PDF assembly
│   ├── research.py             # market research orchestration (Core)
│   ├── swipe_ingest.py         # swipe file → knowledge cards + visual DNA (Core)
│   ├── trace_insight.py        # chain trace queries + experiment management (Core)
│   ├── improvement.py          # self-improvement proposals + promotion (Extended)
│   ├── invoice.py              # Typst template → PDF (Extended)
│   ├── knowledge.py            # ingest, search, embed (Extended)
│   ├── wisdom_vault.py         # Obsidian vault reader (Extended)
│   ├── deploy.py               # Vercel/Netlify deployment (Extended)
│   └── codegen.py              # code generation with QA (Extended)
│
├── utils/                      # Shared functions (built once, imported by multiple sessions)
│   ├── __init__.py
│   └── retrieval.py            # contextualise_card() (S12→S18), retrieve_similar_exemplars() (S11→S13)
│
├── plugins/
│   └── langfuse_hook.py        # Langfuse @observe integration
│
├── manifests/
│   └── workflows/              # 16 Unified WorkflowPack YAMLs (includes rework.yaml)
│
├── migrations/                 # Database migrations (idempotent)
│   ├── core.sql                # 14 core tables + views + triggers
│   └── extended.sql            # 21 Postgres extended tables (created on-demand)
│
├── config/
│   ├── phase.yaml              # Phase activation
│   ├── artifact_taxonomy.yaml  # Complete taxonomy
│   ├── fast_paths.yaml         # Deterministic routing patterns (zero-token)
│   ├── retrieval_profiles.yaml # Knowledge retrieval by artifact type
│   ├── stock_assets.yaml       # Graphic element registry
│   ├── design_system_index.yaml # Tags 55 systems: industry, density, mood, colour_temperature
│   ├── social_platforms.yaml   # Platform content density + adaptation rules
│   ├── autonomy_rules.yaml     # Social media autonomy levels per action type
│   ├── content_strategies.yaml # Objective → content strategy mapping
│   ├── calendar/malaysia_2026.yaml
│   ├── brand_patterns/         # 20-30 international brand files
│   ├── copy_patterns/          # Greetings, CTAs, headlines, industry, dialect
│   ├── document_scaffolds/     # Proposal, plan, report, profile, invoice, calendar
│   ├── design_systems/         # 55 web/UI design systems (DESIGN.md files)
│   ├── layout_systems/         # 6 print/document layout systems (LAYOUT.md files)
│   ├── prompt_templates/       # Visual brief expander, tripwire feedback templates
│   ├── quality_frameworks/     # Poster quality dimensions, scoring rubrics
│   ├── content_strategies/     # Industry × channel × objective mappings
│   ├── infographic_templates/  # antvis Infographic component templates
│   ├── course_templates/       # Slide layouts, handouts, worksheets, quizzes
│   ├── code_switching/         # Switching triggers, particle grammar, register-ratio mapping
│   ├── dialect_systems/        # 10 Malaysian dialect YAMLs (3-layer: lexical, grammatical, register)
│   ├── personas/               # Expert role prompts per artifact type (§4.2)
│   ├── vocab/                  # Domain-specific vocabulary per language (§4.2)
│   ├── critique_templates/     # Dimension-specific critique prompts for quality chains (§4.2)
│   ├── character_templates/    # Character bible YAML templates (§42.1)
│   ├── story_bible_templates/  # Story bible YAML templates (§42.2)
│   ├── product_placement/      # Per-client product placement configs (§42.4.1)
│   ├── improvement_rules/      # Accumulated reflective improvement rules from failure analysis
│   ├── prompt_templates/archive/ # Versioned prompt template history (§15.7, never deleted)
│   └── clients/{id}.yaml      # Per-client brand config (includes brand_mood for design system selection)
│
├── templates/                  # Ported from pro-max (ASSETS ONLY — no client data)
│   ├── visual/                 # 8-10 core template patterns (Canva-baseline quality posture)
│   ├── documents/              # 6 document templates
│   ├── typst/                  # Ebook, long-report, invoice, children's book (5 layouts)
│   └── web/                    # Landing page templates
│
├── augments/listening/         # Listening engine (ported from pro-max)
├── evaluations/reference_corpus/ # Calibrated quality examples
├── dashboard/                  # Refine + custom Surface layer (Extended, Session 17)
├── docs/
│   ├── decisions/              # Architecture decision records
│   └── parity_audit.yaml      # Capability implementation tracking (§35 vs actual)
├── tests/                      # Mirrors source
├── exceptions.py
└── pyproject.toml              # Deps ported from pro-max + new
```

Ported from vizier-pro-max (ASSETS ONLY): `templates/`, `augments/listening/`, visual QA utilities (into `middleware/quality_gate.py`), stock images, Typst templates, document templates, `pyproject.toml` dependencies. No client data, no knowledge cards, no exemplars ported. Everything else is written fresh, governance-aware from line one.

---

## 26. Build Plan

Execution is governed by VIZIER_BUILD.md (v1.3.1). This architecture document defines WHAT Vizier is. The build plan defines HOW to build it, in what order, with what dependencies. See VIZIER_BUILD.md for the complete session-by-session execution plan with dependency graph, parallel build markers, and Claude Code-executable specs.

Summary: 3-day marathon build. Core + Publishing ships Day 4. Publishing is a first-class Core capability, not Extended. Extended Operations and Extended Capabilities build from revenue after Core ships.

### 26.1 Ship Criteria

Core is shippable when all three gates pass:

**Gate 1 — Poster Production End-to-End:** Vague BM brief → LLM routing or fast-path → refinement (if shapeable) → production with visual brief expansion → NIMA pre-screen → 4-dimension critique → trace captured (StepTrace + Langfuse) → feedback state machine triggers → delivery message via Telegram.

**Gate 2 — Children's Book Specimen:** Creative workshop loads CharacterBible + StoryBible + NarrativeScaffold → specimen page produced (text with self-refine + illustration from `illustration_shows` field) → Typst assembly with text overlay on text-free illustration → operator review checkpoint functional.

**Gate 3 — Gateway Routing:** Telegram gateway receives a request → Hermes processes → fast-path resolves "poster DMB" at zero tokens OR LLM classification resolves ambiguous request → correct workflow selected → RoutingResult stored on job record.

If all three gates pass, Core ships. Extended sessions shipping at partial completion is acceptable — they build from revenue.

### 26.2 Integration Test Suite

Five integration tests that must pass before SHIP. Execution schedule: VIZIER_BUILD.md §5.

**IT-1: Poster from vague brief.** Input: "buatkan poster Raya untuk DMB" via Telegram. Expected: LLM routing → poster_production workflow → refinement (1-2 cycles) → production → NIMA pre-screen → 4-dim critique → visual lineage recorded → trace in Langfuse → feedback trigger fires → delivery message.

**IT-2: Children's book specimen page.** Input: Load Book 1 creative workshop outputs. Expected: text_gen produces page 1 text with persona + self-refine → illustrate produces text-free image from `illustration_shows` → CLIP similarity against character references > 0.75 → Typst assembly renders PDF with text overlay → operator_review stage presents for approval.

**IT-3: Fast-path routing.** Input: "poster DMB" via Telegram. Expected: fast-path pattern match → poster_production workflow at zero tokens → no LLM classification call → RoutingResult stored with `routing_method: fast_path`.

**IT-4: Knowledge retrieval pipeline.** Input: query "Raya batik promotion DMB". Expected: query transformation generates 4 variants (BM + EN) → hybrid search returns results from both pgvector AND Postgres FTS → RRF merge → cross-encoder reranking selects top 5 → lost-in-the-middle reordering applied → contextual prefixes present on all returned cards.

**IT-5: Feedback state machine.** Input: deliver artifact → wait 24hrs (simulated via direct DB timestamp manipulation). Expected: `awaiting_feedback` → `silence_flagged` trigger fires → one follow-up message sent → if response received: `responded` state → if no response: `unresponsive` state. Verify: `silence_flagged` excluded from quality calculations.

---

## 27. Build Efficiency — External Systems (P14)

Custom code is reserved for domain-specific logic no existing system handles. Everything else uses existing systems.

| Capability | External System | What It Replaces |
|-----------|----------------|-----------------|
| Dashboard data layer, CRUD, auth, realtime | Refine + PostgREST | Custom table browsing, data fetching, auth, pagination, filtering |
| Token tracking + cost attribution | Langfuse SDK (@observe decorator + custom metadata) | Custom token_ledger table + cost_tracker middleware |
| Feedback state transitions | Postgres triggers | Custom feedback_tracker.py state machine |
| All scheduled jobs | Hermes cron | pg_cron (adds complexity to local Postgres) |
| Colour extraction from images | colorthief (pip) | Custom opencv k-means clustering |
| CLIP visual embeddings | open_clip (pip) | Custom embedding pipeline |
| Face detection | mediapipe (pip) | Custom opencv haar cascades |
| Readability scoring | textstat (pip) | Custom copy quality pipeline |
| Language detection | langdetect (pip) | Custom language identification |
| Invoice PDF generation | Typst templates (already in stack) | Custom invoice generation tool |
| Image thumbnails | Pillow (pip, already in deps) | Custom thumbnail pipeline |
| Metrics computation | Postgres views (standard SQL) | Custom learning_snapshots table + cron |
| Quality scoring | Operator rating on feedback table | Custom multi-dimensional quality_scores table |

Principle: When a pip install or a database feature does the job, don't write Python. When Refine scaffolds the CRUD, don't build a custom admin panel. When Langfuse tracks tokens, don't build a parallel ledger. Custom code exists for: governance contracts, iterative refinement, production orchestration, self-improvement proposals, and the Surface layer UX.

---

## 28. Infrastructure Promotion Triggers

| Component | Trigger |
|-----------|---------|
| Managed Postgres (Supabase/Neon/Railway) | Multi-operator deployment, need for hosted auth, or ops burden of local Postgres backup/monitoring exceeds 1 hr/week |
| Temporal | 24+ hour approval-gated workflows that Hermes session resume can't handle |
| OPA | 10+ policy rules needing formal audit |
| Standalone S3 (cloud) | MinIO local storage exceeds Mac Mini disk or need remote access to assets |
| Self-hosted Langfuse | Cloud free tier limits hit (50K observations/month) |
| n8n | 5+ external API integrations needing complex branching |
| ElevenLabs | Narrated outputs become revenue lane |
| Remotion + FFmpeg | Video composition genuinely required |
| pg_cron | Hermes cron insufficient for critical scheduled jobs |
| Distillation pipeline | Token cost becomes real constraint (free tier changes or 200+ jobs/day) |
| Hermes Tool Search | Hermes Agent v0.8+ adopts OpenAI Tool Search pattern (on-demand tool schema lookup instead of full registry in system prompt). Reduces per-call token consumption. Watch upstream releases. |
| Materialised views | Postgres view queries slow down (10K+ jobs) |

### 28.1 Agent Topology Evolution

Vizier's agent model scales through five stages. Each stage is additive — add orchestration on top of existing contracts, tools, configs, and data model. No stage requires rewriting the governance layer, the quality gate, the WorkflowPack YAMLs, or the data model. The thick layers (contracts, tools, configs, data) are topology-independent. The thin layer (orchestration) is what changes.

**Stage 1: Single Superagent (current — Month 1-12)**

Hermes does everything. One context window, one session, sequential execution. Roles defined inline per workflow stage. No staff definitions. Works for 1-3 operators, ~50 jobs/day.

This is the current architecture. No change needed.

**Stage 2: Superagent + Staff Definitions**

Extract specialist roles into staff configs with focused system prompts and tool sets. Each specialist runs in its own Hermes session. The orchestrator (still Hermes) routes work to specialists. Specialists run concurrently.

Staff definition example:

```yaml
# config/staff/marketing_production.yaml
name: marketing_production
persona: config/personas/marketing_director_my.md
tools: [generate_poster, image_generate, deliver]
knowledge: [client, brand_pattern, swipe, seasonal]
model_preference:
  bm_creative: gemini-3.1-pro  # post-S19
  en_creative: claude-opus-4.6
  short_copy: gpt-5.4-mini

# config/staff/codegen.yaml
name: codegen
persona: config/personas/codegen.md
tools: [codegen, deploy]
knowledge: [code_patterns]
execution_backend: local  # Claude Code CLI
model_preference:
  code: claude-sonnet-4.6
```

**Promotion triggers for Stage 2:**

| Signal | Threshold | What it means |
|--------|-----------|--------------|
| Context window pressure | Production prompts regularly exceed 80% of context window | System prompt includes too many role contexts simultaneously |
| Concurrent job contention | Operator waits for one job to finish before another starts, 3+ times per week | Sequential execution is a client SLA risk |
| Codegen frequency | `/diagnose` → code fix occurs weekly, not monthly | Code tasks need persistent codebase context that marketing production doesn't |
| Cross-workflow role duplication | Same persona + tools + knowledge copied across 5+ workflow YAMLs | Inline roles have become maintenance overhead, staff definitions are config DRY |

**What changes:** Add `config/staff/` directory with specialist YAMLs. Workflow stages reference staff by name instead of defining roles inline. Hermes orchestrator spawns specialist sessions. Each specialist has its own context window, system prompt, and tool set.

**What doesn't change:** ArtifactSpec, PolicyEvaluator, ReadinessGate, quality gate, tripwires, guardrails, WorkflowPack YAML structure (stages still exist — they just reference staff configs instead of inline roles), data model, knowledge spine, improvement loop, feedback state machine. All topology-independent.

**Stage 3: Framework-Assisted Multi-Agent**

When inter-specialist coordination becomes complex (5+ specialists with cross-dependencies, research results needed mid-production, QA specialist feeding back to production specialist), adopt a multi-agent orchestration framework on top of Hermes.

Hermes remains the runtime (gateway, tools, cron, credentials). The orchestration framework (LangGraph, CrewAI, or whatever the current best option is at the time) handles inter-specialist routing, state passing, and coordination protocols.

**Promotion triggers for Stage 3:**

| Signal | Threshold | What it means |
|--------|-----------|--------------|
| Inter-specialist handoffs | 10+ handoffs per job with context loss or latency issues | Staff definitions can't coordinate complex multi-step work |
| Specialist count | 8+ active specialists with cross-dependencies | Manual coordination in YAML is insufficient |
| State management complexity | Specialists need shared state beyond what Postgres provides in real-time | Need a proper state machine for agent coordination |

**What changes:** Add orchestration framework as a layer between Hermes and specialists. Specialists become framework-managed workers. Hermes remains the gateway and tool provider.

**What doesn't change:** Everything from Stage 2, plus the staff definitions themselves. The framework orchestrates existing specialists, not new ones.

**Stage 4: Distributed Execution**

When single-machine compute is the bottleneck (Mac Mini M4 can't run enough concurrent specialists), distribute specialists across multiple machines.

Hermes already supports execution backends (Docker, SSH, Daytona, Modal). Specialists deploy to cloud workers. Langfuse is already a cloud service — no observability layer change. Data layer (Postgres + MinIO) promotes to managed hosting (Supabase/Neon + S3) when multi-machine access is required.

**Promotion triggers for Stage 4:**

| Signal | Threshold | What it means |
|--------|-----------|--------------|
| Local compute saturation | Mac Mini M4 CPU/RAM consistently above 80% during production hours | Can't run more concurrent specialists locally |
| Job throughput ceiling | 200+ jobs/day with specialists queuing despite concurrent execution | Need horizontal scaling |
| Latency requirements | Client-facing latency exceeds 30 seconds due to local compute contention | Need dedicated compute per specialist |

**What changes:** Specialist deployment configs specify remote execution backends. Network latency between specialists becomes a design consideration. Secrets management extends to remote workers.

**What doesn't change:** Everything from Stage 3. Specialists are the same — they just run somewhere else.

**Stage 5: Multi-Operator with Delegation Hierarchies**

When Vizier serves multiple operators (the Wazir SaaS concept), the governance layer extends with operator identity.

**Promotion triggers for Stage 5:**

| Signal | Threshold | What it means |
|--------|-----------|--------------|
| Second operator | Any | PolicyEvaluator needs operator identity, jobs need assignment, Surface layer needs per-operator views |
| Role differentiation | Operators need different permission levels | RBAC required on policy, workflow access, and client visibility |
| Audit requirements | Client or regulatory need for per-operator action trails | Change logs need operator attribution |

**What changes:** PolicyEvaluator gains operator_id. Jobs gain assigned_operator. Surface layer shows per-operator dashboards. Approval chains for multi-operator workflows. RBAC on workflow access and client visibility.

**What doesn't change:** The production engine. ArtifactSpec, quality gate, knowledge spine, improvement loop — all operator-agnostic. They don't care who directed the job.

**Key principle across all stages:** The governance contracts, quality system, data model, knowledge spine, and improvement loop are topology-independent. They work identically whether one agent or fifty agents process them. What scales is the orchestration — how work gets from request to specialist to output. The orchestration layer is deliberately the thinnest layer in the architecture so that topology changes are additive, not reconstructive.

---

## 29. Metrics & Observability Model

### 29.1 Dual Tracing Architecture

**Local spans (first layer).** Every LLM call, tool dispatch, and significant operation is recorded in a local LibSQL spans table (§16.6). Lightweight, zero-cost, always-on. Provides: execution traces with parent-child span relationships, per-call token counts, latency, model attribution, and error status. Five diagnostic SQL queries built-in: slowest spans, most expensive spans, error rate by span type, token distribution by model, and idle token detection.

**Langfuse (second layer).** Cloud observability via @observe decorator with custom metadata (client_id, tier, job_id). Provides: cost breakdowns, prompt tracking, cross-job analytics, dashboards. Both layers coexist — local spans for immediate debugging, Langfuse for long-term analytics.

### 29.2 Memory Routing

Memory operations (summarisation, compression, retrieval, storage) routed to GPT-5.4-mini Month 1-2. The memory_routing_log table (§16.6) tracks every memory operation.

### 29.3 Idle Token Detection

An hourly Hermes cron job scans the local spans table for idle token patterns: LLM calls with no associated production job, memory operations exceeding expected token budgets, repeated routing calls for the same input. When detected, an alert surfaces on the dashboard.

### 29.4 Five Metric Categories

**Operational metrics** — token spend, cost attribution, model routing distribution, tier breakdown (A/B/C), latency per step, throughput (jobs per period), error rates, policy block rates, idle token burn rate.

**Output quality metrics** — first-pass approval rate (from real feedback only, never from silence), revision depth and revision categories, operator rating (1-5), feedback collection rate.

**Business impact metrics** — delivery-to-feedback time, client velocity (jobs per client per period), revenue per artifact type, pipeline conversion rates, capacity utilisation.

**Learning metrics** — knowledge base growth (net cards, exemplar promotions), preference convergence (refinement cycles trending down per client), fast-path adoption rate, improvement proposal acceptance rate.

**System health metrics** — model availability and latency, Postgres row counts and MinIO storage usage, gateway health (webhook latency, delivery confirmation), cron execution success rate.

### 29.5 Feedback State Machine

```
delivered → awaiting_feedback → [explicitly_approved | revision_requested | rejected | silence_flagged]
silence_flagged → prompted → [responded | unresponsive]
```

State transitions driven by Postgres triggers (for immediate transitions) and Hermes cron (for time-based silence detection). Only `explicitly_approved` counts as a positive quality signal. `silence_flagged` and `unresponsive` are excluded from quality calculations. One low-pressure follow-up via delivery channel when silence is flagged. One prompt, not nagging.

**Feedback richness levels:** Level 0 = binary (approved/not). Level 1 = categorical (copy ✓ layout ✗ colour ✓ tone ✓). Level 2 = directional ("warmer," "more professional"). Level 3 = comparative ("prefer A over B because…"). Quick-tap inline keyboards on Telegram make Level 1+ easy.

**Operator assessment:** Independent of client feedback. Operator rates outputs from dashboard (1-5) with optional notes. Divergence between operator rating and client feedback is the most valuable learning signal.

**Feedback collection rate** is a first-class metric. If below 60%, quality metrics are unreliable. Dashboard surfaces this prominently.

### 29.6 Quantisation Views

Postgres views (not materialised — regular views until 10K+ jobs) pre-compute quantised signals:

**System health score (0-100)** — aggregates feedback collection rate, first-pass approval rate, average refinement cycles, fast-path rate, error rate. Green/amber/red.

**Per-client health score** — feedback velocity, approval rate, revision depth, job frequency trend, outstanding invoices, upcoming calendar events without planned content.

**Knowledge base health** — total cards, active vs deprecated, coverage gaps per artifact type, exemplar coverage.

**Feedback quality index** — feedback collection rate × average feedback richness level.

### 29.7 Token Tracking

Handled entirely by Langfuse — no custom token ledger table. Every LLM call instrumented via Langfuse @observe decorator with custom metadata: `{client_id, tier, job_id, step_name}`. Production traces (TraceCollector) store step-level token counts in production_trace JSONB for per-job chain analysis.

---

## 30. Visual Asset Intelligence

### 30.1 The Problem

Visual assets are the engine's raw material. Without rich metadata, usage tracking, and visual similarity search, they are opaque blobs with filepaths.

### 30.2 Visual DNA Extraction Pipeline

Every visual asset entering the system — uploaded, generated, ingested from a swipe file — passes through automatic extraction:

**Colour extraction** — dominant colours via colorthief (pip). Palette classification (warm/cool/vibrant/muted/festive). Brand colour match scoring against client config.

**Layout analysis** — zone detection via opencv contour analysis. Text region detection via OCR. Visual density calculation (0-1). Layout type classification (minimal/dense/centered/split/grid/full_bleed).

**Content detection** — face detection via mediapipe (pip). Product/food detection via CLIP zero-shot classification. Scene classification.

**CLIP embedding** — 512-dim visual embedding via CLIP ViT-B/32, run locally on Mac Mini M4 with MPS acceleration. Stored in visual_embedding vector column, queried via pgvector. Enables visual similarity search.

**LLM tagging** — one GPT-5.4-mini vision call per asset (~500 tokens). Describes style, mood, content, suitable industries, suitable seasons. Cached permanently. One-time ingestion cost.

Pipeline runs once per asset at ingestion.

### 30.3 Visual Lineage

Every production job that uses visual assets records what it used and why in the visual_lineage table. The dashboard renders actual images inline in trace views.

### 30.4 Usage Tracking

Every time the engine selects a visual asset for production, `times_used` increments. Enables utilisation rate, dead asset detection, workhorse identification.

### 30.5 NIMA Aesthetic Pre-Screening

NIMA (Neural Image Assessment) is a pre-trained CNN that scores image aesthetic quality locally on Mac Mini M4. Runs in <100ms, costs zero tokens. Produces a distribution of ratings 1-10.

Integration as Layer 0b (between structural checks and tripwire):

- Score < 4.0 → REGENERATE immediately (don't waste tripwire LLM tokens)
- Score 4.0-7.0 → proceed with caution flag for tripwire
- Score > 7.0 → aesthetic baseline confirmed

### 30.6 4-Dimension Design Quality Scoring

Research-validated scoring framework for poster/graphic design evaluation:

1. **Text visibility** — is text legible, properly sized, good contrast against background?
2. **Design layout** — is the layout clean, balanced, consistent with clear visual hierarchy?
3. **Colour harmony + image quality** — are colours harmonious, images high quality, consistent with brand?
4. **Overall design coherence** — does everything work together as a unified design?

Each dimension scored via separate GPT-5.4-mini critique pass (~1,000 tokens each, free). Issues are SPECIFIC, not generic.

**Exemplar-anchored scoring:** When evaluating a completed design, the scorer receives the design being evaluated + 2-3 similar approved designs from the same client/style (retrieved via `utils/retrieval.py:retrieve_similar_exemplars()`). "Is this new design at least as good as these approved ones?" is more reliable than absolute scoring.

```
Generated image
 → Layer 0a: Deterministic checks (dimensions, format, text overflow)
 → Layer 0b: NIMA aesthetic pre-screen (<100ms, local)
 → Layer 2: 4-dimension critique (4 × GPT-5.4-mini, ~4K tokens total, free)
     Each pass receives: the image + 2-3 similar approved exemplars
     Output: specific issues per dimension
     Issues found → Self-Refine revision targeting named issues
 → Layer 4: Operator rating (human)
```

---

## 31. Operator Experience — Surface & Depth

### 31.1 Design Philosophy

The Vizier Dashboard follows P13: complexity behind glass. Two layers, both graceful.

**Surface — the engine talks to you.** One intelligent view that adapts to context. It synthesises 37 tables, five metric categories, and hundreds of assets into the few things that matter right now. The operator never navigates to data — insights come to them.

**Depth — you talk to the engine.** Every surface element is a doorway. Pull on any insight and it opens gracefully into the data behind it. Pull again and you're at the trace level. Every layer of the engine is inspectable. No layer appears uninvited.

The Mac analogy: macOS doesn't hide the terminal. It just doesn't put it on the desktop.

### 31.2 Infrastructure

Next.js application, accessible via Cloudflare Tunnel + Cloudflare Access.

**Read path:** Postgres LISTEN/NOTIFY for live data (dashboard subscribes to channel, PostgREST relays notifications). Standard queries via PostgREST for historical data. Postgres views for quantised metrics.

**Write path:** Every operator action flows through Hermes as the write gateway. The dashboard sends structured commands to Hermes, Hermes processes them through the standard governance layer. One engine, many doors — the dashboard is another door.

### 31.3 Surface Layer

One adaptive view. Context-aware. Changes based on time of day, active jobs, pending feedback, and operational state.

**Morning (post-Subuh):** Morning brief — overnight results, today's priorities, pending feedback, upcoming calendar events, system health. One screen.

**Active production hours:** Live pulse — active jobs with current step, recent deliveries with feedback status, anything that needs attention.

**Review mode (triggered by pending feedback):** The artifact, the spec it was built against, quality scores, visual lineage, and action buttons.

**End of day (Maghrib):** Shutdown summary — jobs completed, feedback received, token spend, tomorrow's top 3.

### 31.4 Depth Layer

Every surface element is interactive. Pull on it and the next layer opens inline — not in a new page, not in a modal. Inline expansion that preserves context.

Pull on a health score → the metrics behind it. Pull on a job → full production trace. Pull on an approval rate → the jobs behind it. Pull on a visual asset → visual DNA, usage history, similar assets. Pull on a knowledge card → content, usage frequency, quality correlation. Pull on token spend → breakdown by any dimension.

At maximum depth: raw table rows, exact SQL, JSONB contents. Takes 3-4 intentional pulls to reach.

### 31.5 Write Actions

Actions appear in context. All writes flow through Hermes — same governance, same policy, same audit logging.

### 31.6 Visual Asset Experience

Visual assets appear where they're relevant: in job review (thumbnails in lineage section), in quality review (template and exemplar visible inline), in dedicated browse space (grid with filter, usage heatmap, similarity search, seasonal readiness).

---

## 32. Failure Modes & Recovery

### 32.1 Production Step Failure

No silent failures. Every failure is traced, every degradation is visible.

```
Step fails → TraceCollector records failure →
  Retry strategy per step type:
    Deterministic (Tier A): no retry, immediate error
    LLM (Tier B/C): retry once, then retry with fallback model
    External API: retry with exponential backoff (max 3)
  After retries exhausted:
    Quality-critical: job status → 'failed', operator notified
    Non-critical: skip step, continue with degraded context, flag in trace
```

### 32.2 Gateway & Dashboard Failure

Postgres LISTEN/NOTIFY drops → polling mode (30s interval via PostgREST). Hermes write gateway slow → optimistic UI. Hermes down → dashboard read-only. Telegram webhook failure → messages queue.

### 32.3 Model Failure

GPT-5.4-mini unavailable → escalate to GPT-5.4. Both unavailable → fall back to Qwen local for Tier B, queue Tier C. All models down → maintenance mode (Tier A continues).

### 32.4 Data Recovery

**Recoverable from Git:** Templates, brand patterns, copy patterns, calendar, config files, document scaffolds, artifact taxonomy, phase config, workflow packs, all code.

**Recoverable from re-ingestion:** Visual DNA metadata, knowledge cards from patterns, CLIP embeddings, quality reference corpus scores.

**Irreplaceable (requires backup):** Production traces, feedback records, quality scores, learned preferences, improvement experiment results, client-specific knowledge cards from production experience, exemplar promotions, outcome memory, system_state change log.

**Backup strategy:** Daily cron `pg_dump` of full database to timestamped file in `~/backups/` (retain 7 days). Weekly compressed archive to external drive or cloud (B2/S3). MinIO data backed up via `mc mirror` to secondary location. Git-committed exports of config-as-data.

### 32.5 Empty State

Dashboard shows onboarding guide, not empty charts. "Welcome to Vizier. Let's set up your first deployment."

---

## 33. Capacity Envelope

Current deployment throughput estimates (Mac Mini M4 16GB):

| Resource | Capacity | Limit | Source |
|----------|----------|-------|--------|
| Qwen 3.5 9B inference | ~15-20 requests/minute | Mac Mini M4 RAM/compute | |
| CLIP embedding | ~20 images/second (batch) | MPS acceleration | |
| OpenCV DNA extraction | ~5 images/second (full pipeline) | CPU-bound | |
| GPT-5.4-mini | 10M tokens/day | OpenAI free tier | |
| GPT-5.4 | 1M tokens/day | OpenAI free tier | |
| Langfuse observations | 50K/month | Cloud free tier | |
| Local Postgres | Limited by Mac Mini disk (~200GB+ available) | Hardware | |
| MinIO storage | Limited by Mac Mini disk (~200GB+ available) | Hardware | |

Estimated daily capacity: ~50-80 production jobs/day (mixed artifact types), ~10-15 concurrent Tier B operations, ~500 knowledge card retrievals/day, ~20 visual similarity searches/day.

**Bottleneck cascade at scale:**

1. First: Qwen inference queue (above ~80 jobs/day) → solution: second Ollama instance
2. Second: Langfuse observation limit (above ~1,600 jobs/month) → solution: self-hosted Langfuse
3. Third: GPT-5.4-mini token budget (above ~200 token-heavy jobs/day) → solution: accelerate distillation
4. Fourth: Mac Mini disk (above ~150GB of visual assets) → solution: external SSD or cloud S3

These tell the operator "10x growth headroom before the first bottleneck" and connect to the infrastructure promotion triggers in §28. Note: local Postgres and MinIO remove the tier-based bottlenecks that existed with Supabase (500MB database / 1GB storage free tier). The first real constraint is now hardware disk space, not plan pricing.

---

## 34. Anti-Drift Rules

### Architecture

1. This document is canonical. No competing architecture sources.
2. Phase activation governed by `config/phase.yaml`, not schema richness.
3. Iterative refinement must not become a loophole for prohibited lanes.
4. Policy centralised in PolicyEvaluator, not scattered conditionals.
5. Deterministic rendering where correctness matters.
6. Hermes-native types don't leak into domain contracts.
7. Binaries in MinIO, structured data in Postgres. Always.
8. No infrastructure without a promotion trigger.
9. Exploration artifacts are not production deliverables without explicit promotion.
10. No LiteLLM. Supply chain compromise confirmed.
11. No empty engine. Pre-loaded templates, patterns, cards, and references before first request.
12. The governance layer is domain-agnostic. The production layer is deployment-specific by design. Domain-agnostic expansion requires new config authoring, not architectural change.
13. Silence is not approval. Quality metrics computed only from explicit feedback.
14. Every visual asset has extracted visual DNA on the assets table. No opaque blobs.
15. The operator experience surfaces insights, not data. No raw tables on default views.
16. Use existing systems before writing custom code (P14).

### Quality + Production

17. Image model selection driven by job characteristics, not cost.
18. Prose model selection driven by language + task type. Routing map provisional until S19 benchmark.
19. No model downgrade without benchmark evidence.
20. Local spans table is first tracing layer. Langfuse is second. Both coexist.
21. Tripwires fire during production, quality gates fire after. Both needed. Tripwire feedback is critique-then-revise, not score-only.
22. Parallel guardrails run on GPT-5.4-mini (Month 1-2), Qwen local (Month 3+). Flags collected by GuardrailMailbox — dedup by issue type before QA processes.
23. Campaign plans decompose into jobs. One-way dependency.
24. Datasets are fuel, not features. No hard dependency on external datasets.
25. Visual brief expansion runs before every image generation call. No exceptions.
26. DESIGN.md for web/poster. LAYOUT.md for print/document.
27. Social media autonomy levels are config, not code.

### Claw-Code Absorbed Patterns

28. Retrieved knowledge is a hint. Production workflows verify against source data before incorporating.
29. Hermes cron jobs gate on (a) time elapsed, (b) minimum new data, (c) operational relevance. No fixed-schedule crons without gates.
30. `docs/parity_audit.yaml` tracks capability implementation status. Updated at each session ship.

### Model Strategy

31. Month 1-2: GPT-5.4-mini for ALL scoring/routing/guardrails. Qwen local enters production path only after fine-tuned models prove >80% correlation with operator ratings (Month 3+).
32. WorkflowPack YAML includes `scorer_fallback` and `latency_threshold_ms` for graceful model degradation.
33. Train later, produce now. No fine-tuning before 200+ production ratings exist.
34. Fine-tuned models replace prompted models for NARROW tasks only. General reasoning stays on base 9B.
35. LoRA adapters are reversible. Delete and revert if quality regresses.

### Quality Techniques

36. Quality posture (Canva-baseline → Enhanced → Full) governed by phase.yaml. Progression based on accumulated production data, not build completion.
37. First 5-10 jobs per client are deliberate calibration rounds. Extra review time invested knowing approved outputs become exemplar library.
38. Self-refine uses critique-then-revise (specific issues), not generic retry. Feedback template names what's wrong.
39. Iterative rubric refinement from operator rating disagreements replaces upfront rubric extraction as primary calibration method.

### Golden Dataset + Diversity

40. Golden dataset splits into quality dataset (convergent — structural rules, failure detection) and creative dataset (diverse — exemplars, style references, preference pairs). Different purposes, different curation principles.
41. Composition grammar rules from CGL are advisory (flag deviations), not strict (block deviations), except for structural requirements (dimensions, format, text overflow).
42. Diversity-aware variant generation: variants must use DIFFERENT approaches, not 3 slight variations. `diversity_instruction` in WorkflowPack YAML.
43. Production data contributes to training ONLY for dimensions where operator rating diverges from system prediction. Agreeing data points teach nothing — disagreements are the valuable signal.

### Publishing

44. Publishing (children's books, ebooks) is Core, not Extended. Revenue lane with deadline (school holidays).
45. Every publishing project starts with a creative workshop: premise → character bible → story bible → structural scaffold → checkpoint definition → style direction → specimen approval. 2-4 hours of operator-guided creative development.
46. Character bible is exhaustive structured YAML (physical appearance with hex colours, clothing variants, style notes, operator-curated reference images). Not a text description.
47. Illustration consistency path (Kontext iterative vs IP-Adapter anchored vs multi-reference) selected during endpoint testing and configured per-project, not hardcoded.
48. RollingContext contract (§43) serves novels, campaigns, multi-section documents, and client memory. One contract, multiple applications.
49. Illustrations for publishing are ALWAYS text-free. Text is overlaid by Typst in the assembly stage, never rendered inside the AI-generated image.
50. LoRA training is the recommended path for any project with 2+ characters or 8+ illustrated pages.
51. Product placement must be natural. Products appear because they fit the story context. The story must work without the products.
52. Prompt template improvements require validation against held-out production examples before promotion. No untested prompt changes in production.
53. Prompt template versions are archived, never deleted. Every `/promote` creates a new version. Every `/revert` restores the previous version.

### New Rules (v5.3.0)

54. **Month 1-2: GPT-5.4-mini for ALL tasks including creative prose.** Multi-model prose routing (Claude Opus, Gemini, etc.) activates ONLY after S19 benchmark validates the routing map. All 16 WorkflowPack YAMLs set `model_preference` to `gpt-5.4-mini` for every language × task type combination until benchmark results are locked. One model to debug, one credential pool to manage, one failure mode to handle during launch phase.
55. **Derivative publishing projects inherit creative workshop outputs.** Books 2-10 that share art style, age group, and cultural context with an approved prior project use `creative_workshop: derivative` — inheriting StyleLock, story bible template, typography settings, and illustration tier. Only new premise, new characters, new scaffold, and specimen approval are required. Full workshop is reserved for new style/age/context combinations.
56. **Anchor set examples are sacred.** The 10-15 Month 1 calibration examples tagged `anchor_set: true` on the feedback table never enter the exemplar library, never enter training pools, and never influence the improvement loop. They exist solely as a fixed reference point for drift detection (§15.10). Monthly re-scoring against the anchor set is the primary mechanism for detecting rubric drift, diversity collapse, and learning stagnation.
57. **Agent topology changes are additive, not reconstructive.** Governance contracts, quality gate, data model, knowledge spine, and improvement loop are topology-independent — they work identically whether one agent or fifty process them. Topology evolution (§28.1) changes only the orchestration layer. No topology change justifies rewriting contracts, quality systems, or data schemas.

---

## 35. Complete Capability Summary

### CORE (Sessions 0-6) — The Production Engine

| Capability | Session | Mode |
|-----------|---------|------|
| Poster generation (complete + vague) | S0-S4 | Direct + refinement |
| Document production | S1-S4 | Direct |
| Spreadsheet production | S1-S4 | Direct |
| Brochure (weak brief) | S1-S4 | Refinement → production |
| Screenshot replication | S1-S4 | Direct + style-lock |
| Market research (production-embedded) | S12 | Automatic context enrichment |
| Market research (standalone) | S12 | Research workflow → cards/report |
| Calendar-triggered proactive research | S12 | Hermes cron |
| Production chain traces | S7+S8 | Automatic per-job via Langfuse + TraceCollector |
| Token tracking | S8 | Langfuse SDK with client/tier attribution |
| Fast-path routing | S11 | YAML pattern matcher, 60-70% at zero tokens |
| Knowledge retrieval (config-driven) | S11 | Single function, retrieval_profiles.yaml |
| Swipe file ingestion + visual DNA | S12+S13 | colorthief + open_clip + mediapipe |
| Brand pattern grounding | S12 | Pre-loaded 20-30 brands |
| Copy pattern grounding | S12 | Pre-loaded 100-150 cards |
| Seasonal/calendar awareness | S12 | Cron + production context |
| Client onboarding (warm start) | S11 | Workflow |
| Policy enforcement | S8 | Active |
| Observability | S8 | Langfuse @observe |
| Governed workflows | S9 | Unified WorkflowPack YAMLs |
| Feedback state machine | S10a | Postgres triggers + Hermes cron |
| Visual lineage tracking | S13 | Every visual input → output linked |
| Visual similarity search | S13 | CLIP embeddings + pgvector |
| Multi-channel delivery | S11 | Hermes gateway |
| Scheduled automations | S16 | Hermes cron |
| Children's illustrated book (discovery) | S15 | Refinement only |
| Ebook production (discovery) | S15 | Refinement only |
| Post-delivery rework | S9+S10a | Rework workflow (§9.1) |

### EXTENDED (Sessions 7-9) — The Operations Layer

| Capability | Session | Mode |
|-----------|---------|------|
| Invoicing + payments | S16 | Typst template → PDF |
| Sales pipeline | S16 | Active |
| Revenue visibility | S16 | Hermes cron (weekly) |
| Client health monitoring | S16 | Hermes cron (daily) |
| Morning brief | S16 | Daily after Subuh |
| Shutdown ritual | S16 | Hermes skill |
| Prayer-anchored scheduling | S16 | Hermes cron |
| Steward personal assistant | S16 | GTD + ADHD-friendly via separate Telegram bot |
| Two-way dashboard | S17 | Refine (depth) + custom Surface layer |
| Visual assets in context | S17 | Inline in job review, dedicated browse space |
| Knowledge cards + semantic retrieval | S18 | pgvector (upgrades Core FTS) |
| Exemplar library | S18 | Auto-promotion |
| Wisdom Vault bridge | S18 | Bulk import |
| Outcome memory | S18 | Learning from every job |
| Self-improvement proposals | S19 | Auto-detect → propose → operator approves |
| Automated experiments | S19 | Register → test → compare → promote |
| Refinement ↔ improvement feedback loop | S19 | Preferences compound, cycles reduce |
| Landing page generation + deploy | S21 | 3-pass hardening pipeline |
| Web production (marketing sites) | S21 | Plan → scaffold → harden → deploy |
| Code/system generation | S21 | Direct |
| Children's book (full production) | S21 | Upgrades S15 discovery |
| Ebook (full production) | S21 | Upgrades S15 discovery |

---

## 36. Final Architecture Statement

Vizier is a governed, self-improving AI production engine.

**Core** — the production engine. Any artifact type, any domain, any scale — from vague voice notes to delivered production assets. Grounded in market research, proven patterns, and a pre-loaded knowledge base. Governed by contracts, policy, and structural assertions. Every job traced at step-level. Token-efficient by design — full budget where quality demands it, zero where it doesn't. Warm from day one. One model (GPT-5.4-mini) handles everything Month 1-2 for maximum debuggability and zero token cost.

**Extended** — the operations layer. Invoicing, payments, pipeline, revenue visibility, operational health — surfaced through a dashboard that talks to you (Surface) and lets you inspect anything (Depth). Knowledge spine compounding institutional memory from every completed job and every ingested source. Self-improvement loop that learns from every trace — proposes refinements, tests them automatically, and promotes winners with operator approval.

**The trajectory.** Every job teaches the engine. Every refinement cycle trains preferences. Every trace feeds the improvement loop. Month 3: S19 benchmark unlocks multi-model prose routing. Fine-tuned Qwen replaces GPT-5.4-mini for narrow tasks. The operator's role shifts from hands-on production to strategic direction as the system absorbs patterns, automates decisions, and compounds institutional knowledge. One operator with Vizier can outproduce a team of fifty — not by working harder, but by building a system that learns.

The architecture is not bound to any specific domain, client count, geography, or operator. Digital marketing in Malaysia is the first deployment. The engine pattern — governed contracts, iterative refinement, research-grounded production, step-level tracing, closed-loop self-improvement — applies to any domain where an operator directs production of knowledge artifacts.

The first deployment runs on one Mac Mini M4 16GB, one local Postgres instance, one MinIO container, one Hermes Agent, one Telegram account. ~3,700-4,850 lines of custom code, leveraging Refine, PostgREST, Langfuse, Hermes, Postgres triggers, and open-source libraries for everything that isn't unique domain logic. The architecture scales beyond that without structural change. Infrastructure promotes when operational triggers are met, not when the architecture demands it.

37 tables (14 core Postgres, 21 extended Postgres, 2 local LibSQL). 13+ models (1 active Month 1-2, rest activated progressively). 5-layer quality gate. Design intelligence from 100K+ poster judgements and 55 web design systems. Core ships first, Extended earns its place.

**One governed engine that learns from every job. Domain-agnostic. Scale-independent. Loaded from day one.**

The vision: a one-person company with the production capacity of a corporation and the institutional memory that compounds with every job. Not by adding headcount. By building an engine that gets smarter.

That is Vizier.

---

## 37. Tripwire Contracts & Parallel Guardrail Subagents

### 37.1 Tripwire Mechanism

Tripwires are mid-production quality checks that fire during a workflow, not after. They complement the post-production quality gate (§7.4 Layers 0-1) by catching problems before they propagate through subsequent stages. Tripwires are the difference between "the poster is bad" and "the copy was bad, so the poster was bad — catch it at the copy stage."

How it works:

```
Production stage completes
 │
 ▼
Tripwire scorer evaluates output (GPT-5.4-mini Month 1-2, zero cost)
 │
 ├── Score ≥ threshold → proceed to next stage
 │
 └── Score < threshold → retry with feedback
     │
     ├── Retry 1: inject feedback template with specific criticism
     │   Re-run production stage with feedback as additional context
     │   Re-score
     │   ├── Score ≥ threshold → proceed
     │   └── Score < threshold → retry 2
     │
     └── Retry 2: same mechanism
         ├── Score ≥ threshold → proceed
         └── Score < threshold → escalate to operator
             Operator sees: original output, feedback, both retries
             Operator decides: accept, manually revise, or kill job
```

**Configuration:** Per-workflow in WorkflowPack YAML (§10). Each workflow declares whether tripwires are enabled, the scorer model, the score threshold (1-5 scale), maximum retries, and the path to the feedback template. The feedback template is a prompt template that translates a low score into specific, actionable criticism the production model can use to improve.

**Section-level tripwires:** For long-form documents (proposals, reports, ebooks, course materials), tripwires can fire per-section rather than per-workflow-stage. Each chapter or section is scored independently. A weak section gets retried before the next section begins, preventing error accumulation across a 20-page document. Enabled via `section_tripwire: true` on the relevant stage in the WorkflowPack YAML.

### 37.2 Parallel Guardrail Subagents

Parallel guardrails are async quality checks that run alongside production, not in sequence. They do not block the production pipeline — they flag issues for post-production review or trigger a hold before delivery.

How it works:

```
Production stage begins
 │
 ├── Main pipeline: produce output (cloud model)
 │
 └── Parallel guardrails (GPT-5.4-mini Month 1-2, async):
     ├── Brand voice check: compare output against client swipe bank + brand config
     ├── Register consistency: verify casual/formal matches client copy_register
     └── Factual claim check: flag unverified claims (course materials only)

Production stage completes
 │
 ▼
Guardrail results collected
 │
 ├── All pass → proceed to next stage
 └── Any flag → attach flags to trace, surface in QA stage
     QA stage sees: "brand voice guardrail flagged register mismatch in paragraph 3"
     Decision: auto-retry that section, or surface to operator
```

**Key constraints:**

- Guardrails always run on GPT-5.4-mini Month 1-2 (Qwen local Month 3+). Never route guardrail checks to expensive cloud models.
- Guardrails are advisory, not blocking by default. The QA stage decides whether to act on flags. This prevents false positives from halting production.
- Multiple guardrails run simultaneously. The production model works on the next section while guardrails evaluate the current one.
- Guardrail configuration lives in the WorkflowPack YAML (§10), not in code. Adding a new guardrail is a YAML edit, not a code change.
- Flags collected by GuardrailMailbox — deduplicated by issue type before QA stage processes them.

---

## 38. Design Intelligence Layer

The design intelligence layer is a structured knowledge base — extracted from external datasets, professional design systems, and curated exemplars — that tells every production pipeline what good looks like before a single pixel or word is generated. This is a first-class architectural component, not a nice-to-have.

### 38.1 Web & UI Design Systems (55 systems)

Format: DESIGN.md files following Google Stitch specification.

Content per system: Visual theme and atmosphere, colour palette with semantic roles, typography hierarchy, component styles with states, layout principles, depth and elevation, do's and don'ts, responsive behaviour, agent prompt guide.

Systems included: Stripe, Apple, Airbnb, Notion, Supabase, Spotify, Linear, Figma, Framer, BMW, Uber, SpaceX, NVIDIA, IBM, Pinterest, Coinbase, and 40 more.

**Use in Vizier:**

- Landing page generation: production model reads DESIGN.md, generates matching HTML/CSS
- Poster production: colour palettes and typography philosophy extracted for image generation prompts
- Dashboard: design system applied to Vizier's own Surface layer
- Client onboarding: show 5 design directions, client picks, that system becomes their poster_style
- Brand pattern library enrichment: 55 forensic-level design analyses supplement the 20-30 manually-authored brand patterns

Storage: `config/design_systems/` — all 55 copied into repo. ~3.8MB total. Zero runtime cost.

#### 38.1.1 Design System Selection

55 design systems create a selection problem. A deterministic selector narrows 55 → 3 candidates based on structured attributes.

**Index file:** `config/design_system_index.yaml`

```yaml
# config/design_system_index.yaml
systems:
  stripe:
    industry: [tech, fintech, saas]
    density: minimal
    mood: [clean, professional]
    colour_temperature: cool
  apple:
    industry: [tech, consumer, luxury]
    density: minimal
    mood: [premium, elegant]
    colour_temperature: neutral
  shopee:
    industry: [retail, ecommerce, marketplace]
    density: dense
    mood: [bold, energetic, playful]
    colour_temperature: warm
  petronas:
    industry: [energy, corporate, malaysia]
    density: moderate
    mood: [warm, cinematic, emotional]
    colour_temperature: warm
  # ... all 55 systems tagged
```

**Attributes per system:**

- `industry` — list of 1-5 industry tags (food, fashion, tech, education, corporate, retail, beauty, healthcare, finance, energy, malaysia, general)
- `density` — minimal | moderate | dense
- `mood` — list of 1-3 mood tags (warm, cool, bold, elegant, playful, professional, premium, energetic, clean, cinematic, emotional)
- `colour_temperature` — warm | cool | neutral

**Selection logic (~20 lines in `contracts/routing.py`):**

1. Read client config `industry` and `brand_mood` fields
2. Read artifact type (poster → moderate density, landing page → varies, document → minimal)
3. Score each system using **set intersection** (any tag overlap counts, not exact match):
   - Industry: +2 if ANY tag in client's industry list matches ANY tag in system's industry list
   - Mood: +1 if ANY tag in client's brand_mood matches ANY tag in system's mood list
   - Density: +1 if artifact type density matches system density
   - Colour temperature: +1 if client colour preference matches (default warm if unset)
4. Return top 3 systems by score
5. Production prompt receives 3 DESIGN.md references, not 55

No fuzzy matching, no semantic similarity. Exact tag overlap only. Simple and debuggable.

**Client config additions:**

```yaml
# config/clients/dmb.yaml
brand_mood: [warm, traditional]  # maps to design system mood tags
workflow_overrides:               # optional — per-client overrides merged at runtime
  tripwire:
    threshold: 3.5               # stricter than default 3.0 for this client
  quality_techniques:
    exemplar_injection: true      # always inject exemplars for DMB (even if posture is baseline)
  parallel_guardrails:
    - name: halal_compliance
      model: gpt-5.4-mini
      check: verify no non-halal products, imagery, or messaging
```

`workflow_overrides` is optional. When present, the workflow executor merges overrides onto the WorkflowPack YAML defaults at runtime (~10 lines in S9 executor). This allows per-client quality tuning without duplicating workflow YAMLs. If no overrides are set, the workflow runs with its default configuration.

If no client config mood is set, default to `[warm, professional]`.

### 38.2 Print & Document Layout Systems (6 systems)

Format: LAYOUT.md files — adapted from DESIGN.md structure for print.

Content per system: Page setup and atmosphere, typography system, page templates (cover, TOC, body, chapter opener, endmatter), component patterns (boxes, pullquotes, figures, tables, captions, footnotes), image and figure rules, running elements (headers, footers, page numbers), colour system, do's and don'ts.

LAYOUT.md files:

1. professional-book/LAYOUT.md — full book (novel, non-fiction)
2. children-book/LAYOUT.md — illustrated children's book (5 page layout variants)
3. business-proposal/LAYOUT.md — proposals, company profiles
4. course-material/LAYOUT.md — handouts, worksheets
5. report/LAYOUT.md — business/research reports
6. poster/LAYOUT.md — marketing poster layouts (from CGL + PosterCraft data)

Storage: `config/layout_systems/`.

### 38.3 Poster Design Intelligence

**Element position heatmaps** (from CGL 60K annotated posters):

- Where logos typically go (top-left 62%, top-right 24%, bottom-centre 8%)
- Where CTA text sits (bottom-centre 45%, bottom-right 30%, bottom-left 15%)
- Text-to-image area ratios by product category
- Product category → layout family mapping

**Quality evaluation framework** (from PosterCraft Reflect-120K):

- Extracted quality dimensions: text legibility, layout balance, colour harmony, visual hierarchy, text-background contrast, white space usage, CTA visibility
- Each dimension documented with good/bad examples and scoring rubric
- Stored as `config/quality_frameworks/poster_quality.md`
- Used by Layer 2 tripwire scorer (§7.4) as system prompt context

**Visual brief expansion** (from PosterCraft recap agent methodology):

- 4-step methodology: analyse core requirements → expand with specifics → handle text precisely → output under 300 words
- Applied universally to ALL image generation, not just posters
- Runs on GPT-5.4-mini (Month 1-2) or as part of the production prompt
- Stored as `config/prompt_templates/visual_brief_expander.md`

**Preference calibration** (from PosterCraft Preference-100K):

- 5,000 pairs available for immediate use as few-shot examples
- Full 100K available for future Qwen fine-tuning

### 38.4 Ad Copy & Marketing Intelligence

**CTA formula library** (from ad copy datasets): 50+ structural templates. Stored as `config/copy_patterns/cta_formulas.yaml`.

**Headline formula library:** 30+ structural templates. Stored as `config/copy_patterns/headline_formulas.yaml`.

**Ad size → content density model** (from AdImageNet 9K): Words-per-pixel-ratio by ad/post format. Deterministic rules: Instagram 1:1 = 40 words max, Story 9:16 = 15 words, Facebook post = 80 words. Used by Layer 1 checks.

**Objective → content strategy mapping:** Stored as `config/content_strategies.yaml`.

**Linguistic quality rules** (from AdParaphrase research): Preferred ad texts have higher fluency, longer length, more nouns, use of structural markers. Implemented as deterministic checks in Layer 1 (zero-cost).

### 38.5 Infographic Rendering Engine

A universal visual information renderer supporting: lists, sequences, comparisons, hierarchies, timelines, funnels, mind maps, flow charts, word clouds, SWOT analyses, pie/bar/line charts — all with theming, icons, and custom palettes.

Application across every output type: proposals (stat cards, process diagrams), reports (data visualisation), social media (infographic carousels), course materials (concept diagrams), content calendars (visual grids), morning brief (daily stats in Telegram).

Integration: One markdown-like DSL syntax → publication-quality visual. Every document workflow includes an infographic assessment step.

Storage: Templates in `config/infographic_templates/`.

### 38.6 Code-Switching Intelligence

Malaysian marketing copy is inherently code-switched — BM, English, and discourse particles ("lah," "kan," "eh") mix within single sentences. This is not a bug to be corrected — it is the natural register of Malaysian social media.

**Extracted knowledge:**

- **Switching trigger taxonomy:** Noun insertion (most common), discourse marker switching, phrase-boundary switching. Always-English categories (brand names, technical terms, social media terms). Always-BM categories (greetings, cultural terms, food terms, respect terms).
- **Particle grammar:** "Lah" (softener), "Kan" (seeking agreement), "Mah" (obviousness), "Lor" (resignation), "Wei/eh" (attention), "Tau" (emphasis).
- **Register-to-ratio mapping:** Casual = 60% BM / 30% EN / 10% particles. Semi-formal = 80% BM / 15% EN / 5% particles. Formal = 95% BM / 5% EN / 0% particles.
- **Platform-specific patterns:** Twitter/X switching is heavier than Instagram, heavier than Facebook. Children's books = zero switching.

Storage: `config/code_switching/rules.yaml`.

Toggle mechanism: Code-switching is on/off per workflow YAML. Client config can override. Three layers of control: workflow YAML → client config → operator override.

### 38.7 Dialect Production Systems

Structured dialect adaptation for all 10 major Malaysian dialect groups: Terengganu, Kelantan, Kedah/Perlis, Perak, Negeri Sembilan, Johor-Selangor, Pahang, Melaka, Sarawak, Sabah.

Format: One YAML file per dialect in `config/dialect_systems/`, each with three layers:

- **Layer 1 — Lexical:** Direct word/phrase substitutions ("saya" → "ambe" in Terengganu)
- **Layer 2 — Grammatical:** Structural transformations (verb-modifier ordering, particle placement)
- **Layer 3 — Register:** What "casual" and "warm" mean in each dialect

Validation: MaLLaM (Malaysian LLM, 200B tokens of Malaysian text including dialect exposure) serves as dialect naturalness scorer via perplexity measurement.

---

## 39. Campaign Planning Layer

### 39.1 Plan → Job Relationship

Campaign planning introduces an orchestration layer above individual jobs. A plan is a strategic container that decomposes a campaign brief into a sequence of coordinated jobs with dependencies, scheduling, and KPI tracking.

```
Campaign Brief
 │
 ▼
Plan (plans table)
 │
 ├── plan_task: "Design Raya hero visual" → job (poster_production workflow)
 ├── plan_task: "Write 4 social captions" → job (copy_production workflow)
 ├── plan_task: "Create content calendar" → job (content_calendar workflow)
 ├── plan_task: "Post to Instagram" → job (social_posting workflow)
 │   depends_on: hero visual + captions
 └── plan_task: "Post to Facebook" → job (social_posting workflow)
     depends_on: hero visual + captions
```

One-way dependency: Plans decompose into jobs. Jobs do not know about plans — they execute normally through the standard governance pipeline. The plan layer tracks progress by observing job completion.

### 39.2 Campaign Decomposition

The campaign decomposer takes a high-level brief and produces a structured plan with tasks, artifact types, scheduled dates, dependencies, KPIs, and platform adaptation.

### 39.3 Scheduling & Execution

Plan tasks map to Hermes cron for automated execution. When a task's scheduled time arrives and all dependencies are met, the system creates a job and routes it through the standard pipeline. If a dependency is blocked, downstream tasks automatically defer.

### 39.4 KPI Tracking & Re-Planning

Each plan tracks KPIs against targets. Re-planning is a suggestion, not an autonomous action. The operator approves, modifies, or ignores.

---

## 40. Social Media Management

### 40.1 Social Account Management

Each client can have multiple social accounts across platforms. Credentials stored as Hermes credential pool references. Raw API tokens never stored in Postgres.

### 40.2 Posting Autonomy Model

**Auto** — Vizier posts directly without operator approval. For pre-approved content.

**Draft-and-approve** — Vizier prepares the post and presents for approval via Telegram. This is the default.

**Manual** — Vizier prepares nothing. For crisis responses and sensitive topics.

Autonomy levels are config, not code.

### 40.3 Platform Adaptation Rules

One content concept adapts to multiple platform formats automatically using the content density model (§38.4). The social batch workflow produces platform-adapted variants for all configured accounts from one brief.

### 40.4 Comment Monitoring

Hermes cron (30-60 minute interval) pulls comments and DMs. Each interaction classified by sentiment and stored. Negative comments and questions get draft responses. Escalation for potential crises.

### 40.5 Engagement Analytics

Engagement metrics stored on social_posts. Weekly social performance report. Feeds into campaign KPI tracking (§39.4) and the self-improvement loop (§15).

---

## 41. Web Production Lane

### 41.1 Two-Phase Production Model

Vizier is a marketing production engine, not a software development platform. Web production follows a model that leverages external scaffolding tools for rapid prototyping and Claude Code for systematic hardening.

**Phase 1 — Vizier plans and specifies.** Campaign planning layer or direct brief → structured spec with sections, copy, CTA placement, design system reference, content density targets, CRO patterns, SEO structure. Issued as Linear tickets.

**Phase 2 — Scaffold externally.** Bolt.new or Lovable produces a working first draft. Currently a manual step (operator pastes spec into Bolt, exports code to repo).

**Phase 3 — Claude Code hardens.** Three hardening passes.

### 41.2 Hardening Pipeline (3 passes)

```
Scaffolded code arrives in repo
 │
 ├── Pass 1: STRUCTURAL (deterministic, zero tokens)
 │   Dimensions and responsive breakpoints correct
 │   WCAG contrast ratios and keyboard navigation
 │   SEO: meta tags, heading hierarchy, schema markup, image alt text
 │   Semantic HTML validation
 │   Content density: text-to-visual ratios per section (from AdImageNet)
 │
 ├── Pass 2: CONTENT (one LLM pass, structured output)
 │   Copy quality against golden dataset rubrics
 │   BM register check and code-switching consistency
 │   CRO compliance: hero section, social proof, CTA positioning,
 │   objection handling (from marketingskills)
 │   Linguistic quality rules (from AdParaphrase)
 │   Output: structured JSON with issues per dimension
 │
 └── Pass 3: VISUAL (Playwright + comparison)
     Screenshots at mobile, tablet, desktop breakpoints
     Compare rendered output against design spec
     Quality gate Layer 0-1
     Deploy to Vercel, verify live site matches screenshots
     Surface to operator for final review
```

### 41.3 Linear Integration

Vizier decomposes web projects into Linear issues programmatically. Each issue maps to a plan_task with acceptance criteria, dependencies, and labels. Hermes executes codegen tasks via `tools/codegen.py`, which delegates to Claude Code CLI for implementation. Hermes provides job context and acceptance criteria. Claude Code handles code editing, testing, and committing. Issues are processed in dependency order.

### 41.4 Workflow Definition

```yaml
# manifests/workflows/web_production.yaml
name: web_production
posture: production
model_preference:
  en_creative: gpt-5.4-mini       # Month 1-2
  bm_creative: gpt-5.4-mini
  short_copy: gpt-5.4-mini
plan_enabled: true
stages:
  - name: spec
    role: strategy
    tools: [classify_artifact, research]
    knowledge: [client, brand_pattern, design_system]
    action: produce structured web project spec
  - name: linear_issues
    role: delivery
    tools: [linear_create_issues]
    action: decompose spec into Linear issues
  - name: scaffold
    role: production
    tools: []
    action: MANUAL — operator scaffolds in Bolt/Lovable, exports to repo
  - name: harden_structural
    role: qa
    tools: [accessibility_check, seo_audit]
    action: deterministic structural checks (dimensions, a11y, SEO, density)
  - name: harden_content
    role: qa
    tools: [quality_gate, code_review]
    action: copy quality + CRO compliance (one LLM pass, structured output)
  - name: visual_qa
    role: qa
    tools: [playwright_screenshot, visual_qa]
    action: screenshot at breakpoints, compare against spec, deploy
```

### 41.5 Scope & Boundaries

**CAN deliver:** Marketing landing pages, company profile/portfolio sites, simple lead capture pages, content-driven microsites, blog/article pages with SEO.

**CANNOT reliably deliver:** E-commerce with cart/checkout/payment, complex web apps with state management/auth, multi-tenant SaaS, real-time collaborative apps, applications requiring ongoing engineering.

### 41.6 Scaffolding Tool Dependency

Bolt.new and Lovable are kept as personal prototyping tools only — not integrated into Vizier's runtime. Neither has a headless API as of April 2026.

At current scale (3 clients, 1-2 pages/month): 15 minutes of manual work per page. Manageable.

Infrastructure promotion trigger: When manual scaffold time exceeds 2 hours/week, evaluate Claude Code direct scaffolding as replacement.

---

## 42. Publishing Intelligence

The publishing intelligence layer provides the creative infrastructure for producing children's books, ebooks, serialised fiction, and novels. This is the difference between "generate a story" (amateur) and "execute a fully-specified creative vision" (professional).

### 42.1 Character Bible Contract

Every character in a publishing project has an exhaustive structured YAML specification:

```yaml
# config/character_templates/character_bible.yaml
character_id: ahmad
name: Ahmad
role: protagonist
physical:
  age: 8
  ethnicity: Malay
  skin_tone: "#8D6E63"
  height: "120cm, slightly short for age"
  build: "slim but not skinny"
  face:
    shape: round
    eyes: "large, dark brown, curious expression"
    nose: "small, button"
    mouth: "wide smile, gap between front teeth"
    distinctive: "dimple on left cheek"
  hair:
    style: "short, straight, parted left"
    colour: "#1A1A1A"
clothing:
  default: "blue baju Melayu with gold buttons, white seluar"
  school: "white shirt, dark blue shorts, black shoes"
  festive: "green baju Melayu with songkok"
style_notes:
  art_style: "soft watercolour, Studio Ghibli influence"
  line_weight: "thin, delicate"
  colour_palette: "warm earth tones, soft pastels"
  never: "realistic/photographic, sharp lines, dark shadows"
  always: "gentle lighting, warm undertones"
reference_images:
  front_view: "assets/characters/ahmad_front.png"
  three_quarter: "assets/characters/ahmad_3q.png"
  profile: "assets/characters/ahmad_profile.png"
lora:  # When Tier 1 selected
  character_lora_url: "https://fal.ai/trained/ahmad_char_v1.safetensors"
  trigger_word: "ahmad_char"
  training_images: 15
  training_cost: "$4.00"
  trained_at: "2026-04-10"
```

Operator curation workflow: Generate 10-15 candidate images from bible description → operator selects best 2-3 → selected images locked as reference_images. Budget 30 minutes per character. Characters cannot enter production without curated references.

### 42.2 Story Bible Contract

The story bible holds world facts, settings, cultural context, and narrative constraints. Separate from character bibles — characters inhabit the world the story bible defines.

```yaml
title: "Ahmad Belajar Membatik"
target_age: 5-7
language: BM
world:
  setting: "Kampung di Terengganu, masa kini"
  sensory:
    visual: "Rumah kayu, halaman luas, pokok kelapa, kain batik digantung kering"
    auditory: "Bunyi ayam berkokok, angin laut, suara nenek bercerita"
    olfactory: "Bau lilin panas, pewarna batik, nasi lemak pagi"
  cultural_context:
    values: [kesabaran, hormat orang tua, warisan budaya]
    practices: [batik-making process, kampung community life]
    religion: "Islamic context — natural, not preachy"
thematic_constraints:
  lesson: "Patience and respecting tradition lead to beautiful results"
  avoid: [violence, fear, disrespect to elders, modern technology focus]
immutable_facts: []  # populated during production, never contradicted
```

Immutable facts start empty. As production proceeds, established facts are captured and locked. The consistency verification step flags any contradiction.

### 42.3 Narrative Scaffolding

PlanningObject connects to age-calibrated structural templates:

| Age group | Words/page | Vocabulary | Sentence pattern | Arc |
|-----------|-----------|------------|-----------------|-----|
| 3-5 | 10-20 | Simple nouns, basic verbs | Repetitive, rhythmic | Discover → try → succeed |
| 5-7 | 20-40 | Expanded vocab, emotions | Short sentences, dialogue | Problem → attempt → fail → learn → succeed |
| 8-10 | 80-120 | Complex vocabulary | Varied sentence length | Multi-chapter arc with subplot |
| 10-12 | 120-200 | Full vocabulary range | Complex structures | Multiple characters, moral ambiguity |

Scaffolding specifies per-page/chapter:

```yaml
page: 3
word_target: 30
emotional_beat: frustration
characters_present: [ahmad, nenek]
checkpoint_progress: "Ahmad's first failed attempt — wax drips"
text_image_relationship: complementary
illustration_shows: >
  Ahmad's small hands gripping the canting too tightly, wax dripping
  onto the wrong part of the white fabric. His face scrunched in
  frustration. In the background, nenek's hands rest calmly on a
  perfectly patterned cloth — the contrast between mastery and
  first attempt.
page_turn_effect: continuation
composition_guide:
  camera: close_up
  character_position: centre
  background_detail: medium
  colour_temperature: cool
  text_zone: bottom_third
```

**Text-image relationship modes:**

- **Symmetrical** — text and illustration tell the same thing. Best for age 3-5.
- **Complementary** — each adds what the other doesn't. Professional standard for age 5-7+.
- **Contradictory** — text says one thing, illustration shows another. Sparingly for age 7+.

The illustration prompt is generated FROM the `illustration_shows` field, NOT from the page text. This produces illustrations that extend the narrative rather than repeat it.

**Typography requirements for children:**

- Age 3-5: minimum 20pt body text, 150% line spacing
- Age 5-7: minimum 16pt body text, 130-150% line spacing
- Age 8-10: minimum 14pt body text, 130% line spacing
- Maximum 3-4 lines per page for age 5-7. Maximum 6-8 lines for age 8-10.

### 42.4 Illustration Consistency Pipeline

Character bible → reference generation → operator curation → (optional LoRA training) → sequential production.

**3-Tier Pipeline:**

**Tier 1: LoRA Training (HIGHEST CONSISTENCY — recommended for books).** Train character LoRA(s) + style LoRA on fal.ai. ~95%+ consistency. Mandatory for series/recurring characters. Recommended for any project with 2+ characters or 8+ pages.

**Tier 2: Reference-Based (GOOD CONSISTENCY — no training needed).** Kontext iterative + anchor frames, IP-Adapter anchored, FLUX.2 multi-ref. ~80-90% consistency.

**Tier 3: Multi-Reference (BROADEST STYLE RANGE).** Nano Banana Pro with up to 14 references. Best BM text rendering.

**Visual Consistency Verification:** After each page, crop character bounding box, compute CLIP cosine similarity against references. Threshold: 0.75 on cropped region.

**Fallback if no path achieves ≥80% consistency in S4 endpoint testing:** Use the best-performing path with operator review checkpoint every 4 pages. The operator visually confirms character consistency mid-production rather than relying solely on CLIP verification. This is slower but ensures quality while the illustration pipeline matures. Document the decision and actual consistency scores in `docs/decisions/illustration_pipeline.md`.

#### 42.4.1 Product Placement Pipeline

For client-commissioned books where client products appear naturally in illustrations. Brand LoRA trained on full product catalogue. Caption-selected variants at inference. Products appear naturally — never promotional.

### 42.5 Publishing Quality Techniques

**Children's books:** self-refine per page, exemplar injection, expert persona, contrastive examples, domain vocabulary.

**Novels/serial fiction:** self-refine per chapter, 3-pass structured critique chain, rolling summary with consistency verification, checkpoint alignment, expert persona.

**Ebooks:** self-refine per section, critique chain (claims, coherence, exec summary alignment), domain vocabulary, exemplar injection.

### 42.6 Pre-Production Creative Workshop

Before any publishing project enters production:

1. Premise development — 1 sentence → expanded synopsis
2. Character bible authoring — YAML per character, operator-curated visual references
3. LoRA training (Tier 1 projects) — train character + style LoRAs on fal.ai
4. Product LoRA training (client-commissioned books) — if product placement enabled
5. Story bible authoring — world, settings, cultural context, constraints
6. Structural scaffolding — age-appropriate template → page/chapter decomposition
7. Storyboard — visual overview of ALL pages as thumbnails. Review pacing, composition variety, arc progression. 15-20 minutes.
8. Checkpoint definition — target states at key narrative points
9. Style direction → locked as StyleLock. Includes `text_placement_strategy`.
10. Specimen page — produce 1 page through full pipeline. Operator approves before full production.

**Critical production rule:** Illustrations are ALWAYS text-free. Text is overlaid by Typst in the assembly stage, never rendered inside the AI-generated image. This ensures editability, consistent typography, multilingual capability, and proper font control. (Anti-drift #49.)

**Workshop duration:** 2-4 hours. Operator-guided, AI-assisted.

#### 42.6.1 Derivative Project Fast-Path

For publishing projects that share art style, age group, and cultural context with an approved prior project, the creative workshop inherits existing assets instead of creating them from scratch.

**What a derivative project inherits:**

- StyleLock (art style, palette, typography, text placement strategy) — locked, not re-decided
- Story bible template (world structure, sensory template, cultural context framework) — cloned and modified
- Typography settings (font sizes, line spacing, max lines per page) — locked per age group
- Character bible schema (structure only, not characters themselves) — template reused
- Quality techniques configuration — proven settings carried forward
- Illustration tier selection — validated pipeline reused

**What a derivative project requires (new):**

- New premise (1 sentence → expanded synopsis)
- New or modified characters (new CharacterBible YAMLs, new reference image curation)
- New structural scaffold (page decomposition with word targets, arc beats, text-image relationships)
- New checkpoints
- Specimen page approval

**What a derivative project skips:**

- Art style selection (inherited)
- Typography decisions (inherited)
- Text placement strategy (inherited)
- Illustration pipeline tier selection (inherited from S4 + first project validation)
- Full story bible authoring from scratch (clone + modify)

**Estimated duration:** 45-60 minutes (vs 2-4 hours for full workshop).

**Activation:** Set `creative_workshop: derivative` in WorkflowPack YAML. The workflow executor loads the referenced source project's StyleLock and story bible template, presents for operator confirmation, then proceeds to new-content-only steps.

```yaml
# manifests/workflows/childrens_book_production.yaml
creative_workshop: derivative     # "true" for full, "derivative" for inherited
derivative_source: "project_id"   # source project to inherit from
```

---

## 43. RollingContext — Sequential Production Coherence

### 43.1 The Contract

A generic contract for maintaining coherence across any sequential production process where each step's output depends on everything before it.

```python
class RollingContext:
    context_type: str       # "narrative", "campaign", "document", "client", "social"
    # Three-tier rolling summary
    recent: list[dict]      # last N items at full fidelity
    medium: list[dict]      # current arc/period at beat level
    long_term: list[dict]   # compressed permanent knowledge
    # Entity/fact tracking
    entities: list[dict]    # auto-captured entities with state
    immutable_facts: list[dict]  # facts that can never be contradicted
    # Target states
    checkpoints: list[dict]      # future states the sequence must reach
    # Config
    recent_window: int
    medium_scope: str       # "arc", "week", "section", "quarter"
    compression_model: str
```

### 43.2 Applications

| Application | recent_window | medium_scope | entities track | checkpoints |
|------------|---------------|--------------|---------------|-------------|
| Novel (30 chapters) | 2 chapters | story arc | characters, locations, objects | plot milestones |
| Children's book (8 pages) | all pages | not needed | characters | moral/lesson |
| Campaign (14 posts) | 3 posts | campaign week | products, prices, claims | messaging milestones |
| Proposal (10 sections) | 2 sections | document act | numbers, promises, scope | section alignment |
| Client memory (50+ jobs) | 5 jobs | quarter | preferences, approvals | quality trajectory |
| Social comments | 5 interactions | week | customer issues, promises | resolution targets |

### 43.3 Post-Step Update

After any sequential production step, the workflow executor runs (when `context_strategy: rolling_summary`):

1. **Update rolling summary** — compress completed step into appropriate fidelity tier
2. **Extract entities** — "What new characters/products/claims were introduced? What existing entities changed state?"
3. **Verify consistency** — "Does this step's content contradict any immutable facts or previous steps?"
4. **Update state** — character states, plot progress, campaign status

All 4 steps run on GPT-5.4-mini (~3,000 tokens total, free). Same code path regardless of whether it's a novel chapter, campaign post, or proposal section.

### 43.4 Checkpoint Alignment

**For publishing:** checkpoints define target narrative states ("by page 7, Ahmad must have succeeded at batik-making"). Flag if not on track.

**For campaigns:** checkpoints define messaging milestones ("by day 7, urgency messaging must have started; 50% discount must NOT appear before day 10").

**For documents:** checkpoints define structural alignment ("section 5 must address the claims made in section 3's executive summary").

### 43.5 Integration with Publishing Workflow

```yaml
# manifests/workflows/childrens_book_production.yaml
name: childrens_book_production
posture: production
context_strategy: rolling_summary
creative_workshop: true          # or "derivative"
derivative_source: null          # project ID when derivative
model_preference:
  bm_creative: gpt-5.4-mini     # Month 1-2 (all GPT-5.4-mini)
  en_creative: gpt-5.4-mini
  summarisation: gpt-5.4-mini
  extraction: gpt-5.4-mini
  verification: gpt-5.4-mini
image_model_preference:
  character_iterative: flux-kontext-pro  # or character_anchored based on S4
quality_techniques:
  self_refine: per_page
  exemplar_injection: true
  persona: config/personas/childrens_author_bm.md
  domain_vocab: config/vocab/bm_children_5_7.yaml
  contrastive_examples: true
rolling_context:
  recent_window: 8               # all pages for children's book
  medium_scope: not_needed       # book is short enough
  checkpoints: true
tripwire:
  enabled: true
  scorer_model: gpt-5.4-mini
  scorer_fallback: gpt-5.4-mini
  threshold: 3.0
  max_retries: 2
  feedback_template: config/critique_templates/childrens_narrative.md
stages:
  - name: creative_workshop
    role: strategy
    action: load/create character bibles + story bible + scaffold + checkpoints
  - name: specimen
    role: production
    action: produce page 1 through full pipeline, operator approves before continuing
  - name: page_production
    role: production
    action: sequential page generation (text + illustration per page)
    section_tripwire: true
  - name: post_page_update
    role: qa
    action: rolling summary update + entity extraction + consistency verification
  - name: assembly
    role: delivery
    action: Typst → PDF, ebooklib → EPUB
  - name: operator_review
    role: qa
    action: operator reviews complete book, approves or requests revisions
  - name: delivery
    role: delivery
    action: deliver final files
```
