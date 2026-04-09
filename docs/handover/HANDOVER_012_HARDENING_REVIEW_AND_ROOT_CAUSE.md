# Hardening Review, Open Findings, and Graphify Root-Cause Handover

**Generated:** 2026-04-09  
**Handover number:** 012  
**Reason:** Stop point after deep review of hardening status, Claude follow-up fixes, and graphify root-cause analysis  
**Prior context:** `HANDOVER_010_HERMES_INTEGRATION.md`, `HANDOVER_011_P0P2_TRIAGE_AND_BRIDGE.md`, Track 1/Track 2 hardening work

## Executive Summary

This session did **not** primarily build new runtime features. It did four things:

1. Reframed priorities around **hardening over revenue expansion**.
2. Evaluated the revised **two-track hardening design**:
   - Track 1: repo maturity and reliability
   - Track 2: output quality and variety
3. Reviewed Claude’s claimed hardening completions and separated:
   - real fixes
   - partial fixes
   - regressions / still-open gaps
4. Ran a focused **graphify** pass over the install/drift/smoke boundary and found a deeper root cause:
   - runtime hardening is **Python-centric**
   - deployment hardening is still **shell-centric**
   - validation is mostly **proxy-based**, not **boundary-based**

The most important conclusion is:

- **Hardening is still the correct priority.**
- Track 1 is materially improved but not fully hardened.
- Track 2 has strong foundations, but some claims were temporarily overstated until runtime wiring was checked.
- The next session should focus on the **remaining deployment-boundary and testability gaps**, not on revenue expansion.

## Strategic Decisions Made In This Session

### 1. Do not optimize for short-term revenue right now

The user explicitly chose to harden in two dimensions before revenue expansion:

- **overall repo maturity and reliability**
- **quality / adherence / variety**

Reason:

- too much progress was made in less than a week to risk carrying hidden debt
- the current risk is not lack of opportunity; it is compounding fragility
- revenue expansion should come **after** the system is reproducible, testable, and measurable

### 2. Hardening order is correct

The agreed order stayed:

1. Track 1 — reliability / maturity
2. Track 2 — quality / variety
3. only then broader quality expansion / revenue-facing growth

### 3. Ring separation remains the target model

We clarified that after the repair:

- **Ring 1** should own stable contracts / invariants
- **Ring 2** should own changeable runtime behavior (templates, prompts, scoring metadata)
- **Ring 3** should own per-job and learned data

Important nuance:

- Ring 3 must remain a **governed input layer**
- it must not silently redefine structure

## Hardening Plan Evaluation

The revised hardening design was judged to be the right shape after corrections:

### Track 1 — Repo Maturity & Reliability

Goal:

- a fresh machine can reproduce the running system
- no tribal knowledge required

Key corrections that were accepted into the design:

- add **job lifecycle hardening**
- keep **deployment boundary** as first-class work
- keep **session↔job correlation**
- keep **telemetry linkage**
- keep **media bridge extension**
- move **self-improvement / auto-promotion** later
- make the **smoke script** validate the hardened state, not just exist

### Track 2 — Output Quality & Variety

Goal:

- benchmark briefs produce brief-adherent outputs across multiple layout families at Canva-template level

Key corrections that were accepted into the design:

- add **poster content schema / slots**
- move **adherence rubric/harness** earlier
- make **interpreted intent** the canonical parse
- keep **template library + selector** as the main quality leverage
- keep **copy enrichment** and **runtime adherence gating**

## Architecture / Quality Conclusions Reached

### Hermes / integration conclusions

Earlier in the session we clarified:

- Hermes should remain the **outer shell**
- Vizier should remain the **inner governed engine**
- the subprocess boundary is acceptable for now, but it limits Hermes observability

The user also asked about token impact and benefits:

- hook work and structured media bridging should be low token overhead
- real token risk starts when memory/context injection grows
- the main benefit is not “magic quality,” but better:
  - control
  - session continuity
  - telemetry
  - operator memory
  - less brittle media handling

### Dataset intelligence conclusions

We also clarified what dataset intelligence is doing for quality today:

- strongest current value is improving the **floor**, not the **ceiling**
- it helps most with:
  - client/config adherence
  - exemplar-informed consistency
  - retrieval relevance
  - smarter QA
- it helps less with:
  - exceptional creative leap
  - Canva-level layout variety on its own

So the next quality leap after hardening will still require:

- a stronger template system
- better layout planning
- stricter brief adherence scoring

## Review Timeline And Findings

This session had several rounds of evaluation.

### Round 1 — broad hardening review

When Claude claimed both Track 1 and Track 2 were complete, the initial review found that Track 2 was overstated.

Initial review findings included:

1. `jobs.interpreted_intent` not persisted
2. `expand_brief()` not consuming interpreted intent in the main image path
3. extended poster slots not carried through runtime selection/render path
4. renderer still stripping newer poster fields
5. adherence scoring helper not wired into runtime QA pass/fail
6. bridge session correlation relying on recency
7. repo-owned loader hardcoding a machine path
8. smoke script not validating the real governed boundary
9. operational hardening scripts lacking direct tests

### Round 2 — Claude’s “7 P1 fixes are done”

Claude then claimed seven P1 fixes. Re-review found:

- several were real
- one introduced a loader regression
- some were only partial

At that point the assessment was:

- **4 clearly fixed**
- **2 partial**
- **1 regressed**

### Round 3 — second Claude follow-up

Claude then claimed to have fixed the remaining three issues:

- loader install path
- `logo_treatment`
- unsafe session fallback

After recheck, the final assessment for this session became:

- several important fixes are now real
- but not everything is fully closed

## Current Truth At End Of Session

### Real improvements confirmed

These improvements appear real in the current local working tree:

- interpreted intent persistence in `tools/orchestrate.py`
- `expand_brief()` consuming interpreted intent in `tools/registry.py`
- slot-aware template selection being wired from delivery
- richer poster payload being carried further into render
- adherence affecting QA pass/fail in `tools/visual_pipeline.py`
- installed live plugin importing the repo bridge correctly on this machine

### Remaining open issues

These are the meaningful remaining findings at the end of this session.

#### 1. Operational hardening scripts still appear untested

Files:

- `scripts/install_plugin.sh`
- `scripts/check_plugin_drift.sh`
- `scripts/smoke.sh`

Why still open:

- there is still no direct automated coverage for the install / parity / smoke boundary
- the repo can remain green while production install behavior regresses

This became the **final explicit review finding** at the end of the session.

#### 2. `media_manifest` fallback is still unsafe under concurrent sessions

File:

- `plugins/vizier_tools_bridge.py`

Status:

- `hermes_session_id` no longer falls back to recency
- but manifest lookup still can

Specifically, the remaining risky pattern is:

- no `hermes_session_id` in args
- fallback to another active `_SESSION_STATE` entry for the manifest

Meaning:

- attachment bleed across sessions is still possible in the manifest path

#### 3. Loader/install path is improved, but still not fully reproducible

Files:

- `plugins/hermes_loader/__init__.py`
- `scripts/install_plugin.sh`

Status:

- `_resolve_bridge_path()` now tries:
  - repo-relative
  - `VIZIER_ROOT`
  - `~/vizier`
- the installed live plugin imports successfully on this machine

Remaining concern:

- reproducibility still depends on:
  - clone path conventions, or
  - environment configuration

So:

- the “breaks immediately after install” bug looks addressed on this machine
- the broader “fully reproducible fresh-machine boundary” goal is **not** fully closed

#### 4. `logo_treatment` is structurally threaded, but not functionally used

Files:

- `contracts/poster.py`
- `tools/registry.py`
- `tools/publish.py`
- `templates/html/*`

Status:

- `logo_treatment` is now parsed and passed through the data/render path

Remaining concern:

- I did not find template behavior or metadata actually using it
- so it is now **plumbed**, but not yet a user-visible quality feature

Implication:

- either support it in templates for real
- or remove/defer it from the contract so the contract stays honest

## Graphify Root-Cause Analysis

The user explicitly asked for graphify to look for a deeper root cause behind the operational-script testing gap.

### What graphify was run on

A focused temporary corpus was created at:

- `/tmp/vizier_graphify_ops_real`

It included copies of:

- `scripts/install_plugin.sh`
- `scripts/check_plugin_drift.sh`
- `scripts/smoke.sh`
- `plugins/hermes_loader/__init__.py`
- `plugins/hermes_loader/plugin.yaml`
- `tests/test_vizier_tools_bridge.py`

### What graphify actually detected

Graphify detected only **2 supported code files**:

- `plugins/hermes_loader/__init__.py`
- `tests/test_vizier_tools_bridge.py`

The shell scripts did **not** enter the graph as first-class analyzable nodes.

This was already a signal.

### Graphify output

Artifacts were written under:

- `/tmp/vizier_graphify_ops_real/graphify-out/`

The graph report:

- `/tmp/vizier_graphify_ops_real/graphify-out/GRAPH_REPORT.md`

Key graph stats:

- 31 nodes
- 33 edges
- 5 communities

Top “god nodes”:

1. `_FakePluginContext`
2. `_load_bridge_module()`
3. `register()`
4. `__getattr__()`
5. `_resolve_bridge_path()`

### Root cause inferred from graphify

The deeper issue is **not merely “missing tests for a few scripts.”**

The deeper issue is:

1. **The deployment boundary is still second-class architecture.**
   - runtime hardening is modeled in Python modules, hooks, contracts, and tests
   - deployment hardening is still modeled largely in shell scripts and path conventions

2. **Validation is proxy-based, not boundary-based.**
   - tests exercise fake plugin contexts and repo-local imports
   - they do not strongly exercise the real installed/deployed boundary

3. **There is no single first-class install/deploy contract.**
   - loader logic is in Python
   - install/parity/smoke logic is in shell
   - the boundary is split across implementation styles and ownership models

The short version:

- runtime hardening is **Python-centric**
- deployment hardening is **shell-centric**
- the current confidence model is stronger for the former than the latter

This is the most important conceptual takeaway from the graphify pass.

## Claude Prompt Prepared During This Session

A ready-to-paste Claude Code prompt was drafted during this session to fix the remaining issues.

Its scope was:

1. add direct automated coverage for install / drift / smoke boundary
2. remove unsafe `media_manifest` fallback
3. make loader/install resolution deterministic and testable
4. either fully support `logo_treatment` in templates or remove/defer it honestly

Acceptance criteria in that prompt included:

- `pyright` clean on touched files
- relevant pytest suite green
- no recency fallback for manifest/session attachment
- temp-dir install/import test for the live plugin boundary
- drift-check behavior tested
- honest contract/template handling for `logo_treatment`

## Repo State At Handover

### Git status

At the stop point, the working tree has local modifications in:

- `contracts/poster.py`
- `plugins/hermes_loader/__init__.py`
- `plugins/vizier_tools_bridge.py`
- `tools/orchestrate.py`
- `tools/publish.py`
- `tools/registry.py`
- `tools/visual_pipeline.py`

These are **local uncommitted edits** from Claude’s follow-up fixes and should
be reviewed before committing.

### External state

The installed live plugin file outside the repo is at:

- `~/.hermes/plugins/vizier_tools/__init__.py`

During this session, I verified that importing the live plugin on this machine
currently resolves the bridge to:

- `/Users/Executor/vizier/plugins/vizier_tools_bridge.py`

That means the installed loader is currently functional on this machine.

### Temporary graphify artifacts

Created outside the repo:

- `/tmp/vizier_graphify_ops_real/`
- `/tmp/vizier_graphify_ops_real/graphify-out/GRAPH_REPORT.md`
- `/tmp/vizier_graphify_ops_real/graphify-out/graph.json`

These are analysis artifacts only and do not affect repo state.

## Verification Run In This Session

### Tests I ran

Focused suites only:

1. `python3 -m pytest -q tests/test_brief_interpreter.py tests/test_template_selector.py tests/test_quality_harness.py tests/test_orchestrate.py tests/test_poster_contract.py`
   - result: `38 passed`

2. `python3 -m pytest -q tests/test_vizier_tools_bridge.py tests/test_orchestrate.py tests/test_template_selector.py tests/test_quality_harness.py tests/test_poster_pipeline.py tests/test_poster_contract.py`
   - result: `63 passed`

3. `python3 -m pytest -q tests/test_vizier_tools_bridge.py tests/test_template_selector.py tests/test_quality_harness.py tests/test_poster_contract.py tests/test_poster_pipeline.py`
   - result: `49 passed`

### Type checks I ran

- `pyright` on the touched bridge / registry / publish / orchestrate / visual pipeline files
  - result: `0 errors`

### What I did NOT verify

- I did **not** rerun the full claimed `789 passed`
- I did **not** rerun the full claimed `796 passed`
- I did **not** validate full production Telegram end-to-end behavior

## Recommended First Move Next Session

Start with the **deployment-boundary hardening** gap, not general feature work.

### Recommended order

1. Add a **temp-dir install/import test** for the live plugin boundary.
   - this should validate:
     - install behavior
     - parity/drift behavior
     - import of the installed plugin
     - bridge registration from the installed plugin

2. Remove the remaining unsafe **manifest recency fallback** in:
   - `plugins/vizier_tools_bridge.py`

3. Decide whether `logo_treatment` should be:
   - truly supported in templates, or
   - removed/deferred from the contract

4. After the boundary is testable, revisit whether:
   - the shell scripts should stay as the source of truth, or
   - install/parity logic should move into Python with shell as a thin wrapper

## What NOT To Do First Next Session

- do not pivot to revenue expansion
- do not start broad new feature work
- do not treat Track 2 as “fully complete” without resolving the remaining boundary/contract honesty gaps
- do not rely on the full-suite pass count without rerunning it

## Files To Read First Next Session

1. `docs/handover/HANDOVER_012_HARDENING_REVIEW_AND_ROOT_CAUSE.md`
2. `plugins/hermes_loader/__init__.py`
3. `plugins/vizier_tools_bridge.py`
4. `scripts/install_plugin.sh`
5. `scripts/check_plugin_drift.sh`
6. `scripts/smoke.sh`
7. `contracts/poster.py`
8. `tools/registry.py`
9. `tools/publish.py`
10. `/tmp/vizier_graphify_ops_real/graphify-out/GRAPH_REPORT.md`

## Bottom Line

This session increased confidence in several hardening fixes, but it also made
the remaining weak seam much clearer:

- the current biggest risk is not inside the governed runtime
- it is the **deployment / install / parity boundary** and the fact that this
  seam is still less governed and less test-protected than the Python runtime

That is the next place to harden.
