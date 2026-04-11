# Quality Gap Analysis: S21 vs Sellable Output

**Date:** 2026-04-11  
**Scope:** What the build plan promised by S21, what the repo actually delivers at `main`, and what still blocks a credible "sellable output" claim.

---

## Executive Verdict

The original build plan failed its S21 promise for one structural reason:

- it optimized for architecture completeness before output quality

The critical quality path was under-scoped or delayed:

- template corpus and template truth
- brief rescue and coaching
- dataset transformation into runtime artifacts
- calibrated QA thresholds
- governed end-to-end acceptance proof
- children's book / ebook deliverability truth

Current `main` is materially better than the original S21 stop-point. A post-S21 quality tranche now exists:

- `61da662` structured coaching with content gates
- `8da7755` industry-specific question patterns
- `4bd853a` template selector scores `industry_fit`
- `61e1927` D4 clustering added 28 poster archetypes
- `5343b41` existing templates tagged with `industry_fit`
- `c04e85e` NIMA calibration script
- `ae35802` cross-session quality integration tests

That is the strongest evidence that the original plan front-loaded the wrong work: the missing quality path had to be built later anyway.

---

## How This Was Assessed

Inputs reviewed:

- all `docs/handover/HANDOVER_*.md`
- `docs/HANDOVER_SPRINT_GPT.md`
- `docs/HANDOVER_SPRINT_GPT_FINAL.md`
- `docs/decisions/*.md`
- `docs/VIZIER_BUILD_v1_3_1.md`
- current runtime code in `tools/`, `contracts/`, `middleware/`, `plugins/`, `config/`

Graphify patterns surfaced four repeat clusters:

- `governed production path`: bridge -> orchestrator -> routing -> visual pipeline
- `delivery support matrix`: workflow config truth vs real delivery support
- `quality intelligence stack`: coaching + dataset transformation + operator exemplar taste layer
- `self-improvement loop`: calibration / experiments / drift detection that need production fuel

Verification run on current `main`:

- `pytest tests/test_vizier_tools_bridge.py tests/test_routing.py tests/test_orchestrate.py tests/test_integration_quality.py tests/test_coaching.py tests/test_visual_intelligence.py -q`
  - `177 passed`
- `pytest tests/test_illustrate.py tests/test_ebook_production.py tests/test_serial_fiction.py tests/integration/test_it2_childrens_book.py -q`
  - `88 passed`
- `pytest tests/test_nima_config.py tests/test_operator_exemplars.py -q`
  - `12 passed`
- `pytest tests/test_d4_templates.py tests/test_template_industry.py tests/test_user_pov_poster_acceptance.py -q`
  - template / industry tests passed
  - `4` poster acceptance cases failed in the governed user-POV suite

---

## What The Repo Now Has

### Poster lane

Live and materially improved:

- Playwright/HTML poster render spine is real.
- Template selector is runtime-wired.
- `38` poster HTML templates now exist, including `28` D4-derived `poster_d4_*` archetypes.
- Template metadata now includes `industry_fit`.
- Brief coaching now returns structured JSON via `CoachingResponse`.
- NIMA thresholds are config-driven through `config/quality_frameworks/nima_thresholds.yaml`.
- Cross-session quality tests exist and are green.

### Publishing lane

Stronger than the original S21 docs implied:

- illustration, ebook, serial fiction, and children-book tool-level tests are green
- but workflow-registry deliverability truth still says those lanes are not final-deliverable through the governed matrix

### Dataset and exemplar work

No longer "zero":

- D4 -> HTML templates is now implemented
- D5 -> `industry_fit` tagging is reflected in template metadata
- D8-derived coaching context exists
- operator exemplar ingestion script exists
- NIMA calibration script exists

But some of that still stops at "artifact exists" rather than "runtime uses it everywhere."

---

## Gap Table

| Capability | Should have been live by S21? | Current state | Gap to "sellable" |
|---|---|---|---|
| Poster render spine | Yes | Live | Not the blocker anymore |
| Professional template floor | Yes | Improved sharply: 28 D4 archetypes + existing templates | Still needs benchmarked taste floor, not just structure |
| Industry-aware template choice | Yes | Live via `industry_fit` scoring | Needs real benchmark matching, not only template metadata |
| Brief rescue / prompt help | Yes | Structured coaching + content gates live | `refine_request()` still dead in production, so clarification is still mostly templated rather than adaptive |
| Dataset-derived QA calibration | Yes | Config and script exist | `nima_thresholds.yaml` still explicitly says `uncalibrated`; calibration has not yet been committed as a verified runtime value |
| Taste layer from Canva/Envato-style refs | Yes, if sellable quality is the goal | Operator ingestion script exists | Not wired into exemplar retrieval, benchmark matching, or quality gates yet |
| Clientless benchmark matching | Yes | Industry inference exists | No true benchmark-selection object or retrieval path against curated taste references yet |
| Screenshot/photo adaptation | Yes for requested product direction | Reference-adapt lane exists | Still more "adapt" than governed clone/replicate workflow |
| Cost by stage/model/job | Should have been good enough for launch ops | Spans and trace totals exist | Stage `_tool_metrics` still omit model names, so model-level diagnosis is incomplete |
| Children's book / ebook sellability | Yes, because the user expectation included them | Tool and workflow tests are strong | Governed deliverability truth still marks these workflows `deliverable: false` |
| Governed sellable-proof suite | Yes | Exists | Still red on poster acceptance; launch claim is not yet re-proven |

---

## The Specific Breaks Between "Artifact Exists" and "Artifact Is Good"

### 1. Coaching is improved but not fully adaptive

What is live:

- `plugins/vizier_tools_bridge.py` returns structured coaching responses
- `tools/coaching.py` enforces semantic content gates

What is still missing:

- `contracts/routing.py:355` `refine_request()` exists, but production does not call it
- questions are still template-driven rather than dynamically shaped from spec state

Why it matters:

- this is enough to stop some bad briefs
- it is not yet the "system helps the user build the best prompt" promise

### 2. Calibration infrastructure exists, but runtime thresholds are still defaults

What is live:

- `tools.visual_scoring.py` reads `config/quality_frameworks/nima_thresholds.yaml`
- calibration and validation scripts exist

What is still missing:

- the YAML still declares `calibration_source: "uncalibrated — defaults pending D12 + operator exemplar calibration"`

Why it matters:

- config-driven thresholds are better than hardcoded thresholds
- but launch-quality proof requires calibrated values, not only a config file

### 3. Structure learned from datasets exists, taste learned from operator exemplars does not

What is live:

- D4 templates encode structural layout variety
- D5 industry tags influence selection

What is still missing:

- operator-curated Canva/Envato references are not in the runtime exemplar path
- `utils/retrieval.py` still retrieves exemplars only from the DB-backed `exemplars` table filtered by `client_id`
- there is no runtime consumer of `datasets/operator_exemplars/manifest.jsonl`

Why it matters:

- the current system can improve composition variety
- it still cannot claim a Malaysia-friendly, English-first commercial taste floor from curated references

### 4. Children's book and ebook quality are farther along than their delivery truth

What is live:

- publishing tests are green
- illustration and assembly tools are real

What is still missing:

- `config/workflow_registry.yaml` still marks:
  - `childrens_book_production: deliverable: false`
  - `ebook_production: deliverable: false`
  - `serial_fiction_production: deliverable: false`

Why it matters:

- the build plan treated these as "extended"
- the product goal treated them as core sellable outputs

### 5. The governed launch proof is still not green

Current failure mode in the acceptance suite:

- all four poster acceptance cases fail at the delivery-stage post-render QA gate
- the immediate cause is harness drift around mocked vision QA signatures / JSON responses
- the test environment also lacks `DATABASE_URL` and usable Langfuse config

What this means:

- this does **not** prove the poster lane is bad
- it **does** prove the repo still lacks one clean, trustworthy governed proof of sellable output

For launch planning, that distinction matters. The pipeline may be improving, but the proof layer is still unreliable.

---

## What Closed Already On Current HEAD

These items were genuine gaps in the original S21 plan and are now at least partly closed:

- D4 template clustering
- D5 industry tagging
- config-driven NIMA thresholds
- structured coaching contracts
- bridge-level content gates
- operator exemplar ingestion script
- cross-session integration tests for quality intelligence

That makes the root cause even clearer:

- the missing quality work was real
- it was simply not on the original critical path soon enough

---

## Remaining Blockers To Claim "Sellable Output"

These are the closures that still matter most:

1. Fix the governed poster acceptance harness so the sellable-proof suite is trustworthy again.
2. Resolve the `quality="high"` posture alias bug where the bridge maps to `quality_posture="production"` but `middleware/quality_posture.py` only accepts `canva_baseline`, `enhanced`, and `full`.
3. Either wire `refine_request()` into bridge-side coaching or explicitly narrow the promise to template-based clarification only.
4. Run and commit actual NIMA calibration, not just the calibration script and placeholder YAML.
5. Promote operator exemplar manifests into the runtime exemplar / benchmark layer.
6. Make `childrens_book_production` and `ebook_production` truthfully deliverable through the governed path, or stop describing them as launch outputs.

---

## Bottom Line

The repo is no longer in the same state described by the early handovers. A meaningful part of the missing quality path has now been implemented after S21.

But that does not rescue the original build plan.

The later commits show exactly what the original plan got wrong:

- quality-critical work arrived after the supposed finish line
- proof of sellable output was not treated as the primary gate
- publishing sellability was deferred behind infrastructure and ops work

The revised build plan should therefore treat poster quality, curated template/taste ingestion, publishing deliverability, and governed acceptance proof as the first-class path to S21, with governance, dashboard, steward, and self-improvement loops moved later.
