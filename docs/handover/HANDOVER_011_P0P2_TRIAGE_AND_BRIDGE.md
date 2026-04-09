# P0-P2 Triage, Intelligence Audit, and Hermes Bridge Evaluation

**Generated:** 2026-04-09
**Handover number:** 011
**Reason:** Context window saturation after deep multi-pass review session
**Prior context:** HANDOVER_009 (CT-008 intelligence plumbing), HANDOVER_010 (Hermes integration audit)

## What Was Done In This Session

### 1. P0-P2 Full Triage

The user asked to "settle P0-P2" — all 9 known issues from HANDOVER_009. Before
implementing, we mapped the current state of each issue.

### 2. Intelligence Plumbing Audit

Traced 10 data flows end-to-end through the codebase. Found CT-008's claim of
"complete intelligence plumbing" was ~30% true:

- **3 fully wired:** routing→design system, brand→copy patterns, feedback→exemplar promotion (code paths exist)
- **3 partial:** brand→image prompts (hardcoded fallback), exemplar injection (empty table), knowledge cards (was stub, now fixed)
- **4 unwired:** visual QA gating (was stub, now fixed), design system→template (was hardcoded, now fixed), tripwire→improvement (one-way only), language detection→copy (present but shallow)

### 3. Codex Commit Evaluation

Analyzed 6 Codex commits (`10dd09d` through `8e9b4c2`). Found that commit
`10dd09d` (3,572 insertions) addressed 5 of 9 P0-P2 issues but introduced two
regressions (missing `memory_labels` column, dead `allow_deep_search` variable).
Subsequent commits fixed the regressions. Net: the engine improved.

### 4. Graphify Three-Way Comparison

Built knowledge graphs at three points (original Apr 8, v0.3.15, v0.3.17). The
`.graphify.toml` file added by Codex (commit `c824015`) defines 6 profiles for
profile-aware scanning. v0.3.17 correctly pruned noisy edges and normalized god
node distribution.

### 5. Hermes Bridge Evaluation

Codex created a repo-owned Hermes bridge (`plugins/vizier_tools_bridge.py`) and
reduced the live plugin to a thin loader. Evaluation: **solid B+**.

Strengths:
- Correct repo-first pattern (thin loader imports repo module via importlib)
- All 4 Chunk 1 hooks registered (pre/post LLM call, session start/end)
- Bilingual production request heuristic (English + Malay)
- Subprocess isolation preserved
- 8 tests passing, including backward compatibility check

Minor gaps:
- `Any` annotations lack justifying comments
- `_pre_llm_call` skips guidance on non-first non-reference turns (possibly intentional)
- No tests for `_run_pipeline_handler` or `_query_logs_handler`
- `uuid` imported inside function body instead of at module top

## Current P0-P2 Status

| # | Priority | Issue | Status | What Fixed It |
|---|----------|-------|--------|---------------|
| 1 | P0 | Rework pipeline rerun stage empty | ✅ Fixed | Codex `10dd09d` |
| 2 | P0 | Parallel guardrails never called | ✅ Fixed | Codex `10dd09d` wired `_run_stage_guardrails()` |
| 3 | P1 | Exemplar table empty | ❌ Open | No seeding strategy exists |
| 4 | P1 | Knowledge retrieval was stub | ✅ Fixed | Codex `10dd09d` wired `embed_text()` + `assemble_context()` |
| 5 | P1 | Only 1 client config (DMB) | ❌ Open | Need 2+ more configs |
| 6 | P1 | Template selection hardcoded | ✅ Fixed | Codex `10dd09d` added `_resolve_template_name()` |
| 7 | P1 | Visual QA gating | ✅ Fixed | Codex `10dd09d` wired `evaluate_visual_artifact()` |
| 8 | P2 | Hermes plugin hook versioning | ✅ Fixed | Codex bridge module + thin loader |
| 9 | P2 | ~20+ commits unpushed | ❌ Open | 21 commits ahead of origin/main |

### Remaining work: 3 items

**P1 #3 — Exemplar seeding strategy:**
The `exemplars` table exists but has 0 rows. No seeding script, no anchor set,
no promotion pipeline has been run. The architecture requires 15 anchor set
exemplars for drift detection (§15.10). The exemplar injection flow in
`tools/registry.py` calls `retrieve_similar_exemplars()` which does CLIP
similarity search — but against an empty table.

Recommended approach:
- Write a seeding script that takes 5-10 approved poster outputs and promotes
  them into the exemplars table with quality scores
- Mark a subset as `anchor_set: true` for drift detection
- This does NOT require new architecture — the table schema and retrieval
  function already exist

**P1 #5 — Client configs:**
Only `config/clients/dmb.yaml` exists (33 lines: brand colors, tone, language).
Need at least 2 more configs for testing multi-client routing. Candidates:
- `autohub.yaml` — automotive client, English-primary
- `generic.yaml` or `default.yaml` — fallback config for unknown clients

These are small YAML files (~30 lines each) following the DMB pattern.

**P2 #9 — Git push:**
21 commits ahead of `origin/main`. These include all of Codex's work plus
earlier CT sessions. A straightforward `git push` after verifying tests pass.

### Also: housekeeping

**8 `.tmp_graphify_*.py` files** exist in the repo root from Codex commit
`8e9b4c2`. These are snapshots of the graphify package source code — no value in
the repo. They should be:
1. Added to `.gitignore`
2. Removed via `git rm --cached` if tracked, or just deleted if untracked

Files:
- `.tmp_graphify_analyze.py`
- `.tmp_graphify_build.py`
- `.tmp_graphify_detect.py`
- `.tmp_graphify_main.py`
- `.tmp_graphify_query.py`
- `.tmp_graphify_report.py`
- `.tmp_graphify_serve.py`
- `.tmp_graphify_watch.py`

## Repo State At Handover

### Test suite
- **807 passed, 3 skipped, 10 warnings** (41.46s)
- All 8 bridge tests pass

### Git status
- 21 commits ahead of `origin/main`
- 6 untracked files (bridge module, bridge tests, handover docs, decision records)
- 8 `.tmp_graphify_*.py` files tracked from commit `8e9b4c2`
- `hermes-agent` submodule shows modified content (expected — local runtime)

### Untracked files to decide on

| File | Recommendation |
|------|---------------|
| `plugins/vizier_tools_bridge.py` | ✅ Commit — repo-owned bridge source of truth |
| `tests/test_vizier_tools_bridge.py` | ✅ Commit — 8 passing tests |
| `docs/handover/HANDOVER_010_HERMES_INTEGRATION.md` | ✅ Commit — Hermes audit |
| `docs/superpowers/plans/2026-04-09-hermes-vizier-integration.md` | ✅ Commit — integration roadmap |
| `docs/decisions/promote_sysstate_test_2026-04-09.md` | ✅ Commit — decision record |
| `docs/decisions/promote_test_template_2026-04-09.md` | ✅ Commit — decision record |

### Key file paths

**Bridge (new):**
- `plugins/vizier_tools_bridge.py` — repo-owned bridge (710 lines)
- `tests/test_vizier_tools_bridge.py` — bridge tests (162 lines)
- `~/.hermes/plugins/vizier_tools/__init__.py` — thin loader (55 lines)

**Runtime controls (from Codex):**
- `middleware/runtime_controls.py` — BudgetProfileConfig + resolve_runtime_controls()
- `config/phase.yaml` — budget profiles (standard/economy/premium)

**Intelligence plumbing (fixed by Codex):**
- `tools/registry.py` — quality_gate, knowledge_retrieve, visual_qa, trace_insight, deliver
- `tools/executor.py` — _run_stage_guardrails(), rework prep, tripwire enhancements

**Client configs:**
- `config/clients/dmb.yaml` — only existing client config

## The Next Best Move

### Priority order for next session

1. **Commit the 6 untracked files** listed above (bridge, tests, docs)

2. **Clean up `.tmp_graphify_*.py` files**
   - `git rm .tmp_graphify_*.py`
   - Add `.tmp_graphify_*.py` to `.gitignore`
   - Commit as `chore: remove graphify source snapshots`

3. **Create 2 additional client configs**
   - `config/clients/autohub.yaml` — automotive, English-primary
   - `config/clients/default.yaml` — generic fallback
   - Follow DMB pattern: brand colors, tone, language, any special rules
   - Commit as `feat(config): add autohub and default client configs`

4. **Implement exemplar seeding**
   - Write `tools/seeding.py` or a script in `scripts/seed_exemplars.py`
   - Promote 5-10 approved poster outputs into the exemplars table
   - Mark 3-5 as `anchor_set: true`
   - Test with `retrieve_similar_exemplars()` to verify CLIP search works
   - This is the last P1 blocker

5. **Push to origin** — `git push` after all above are committed and tests pass

### What NOT to do next session

- Do not start Chunk 2 (structured media bridge) until the P1 items are closed
- Do not modify the governed runtime contract
- Do not add new Hermes memory provider work (Chunk 3+)
- Do not restructure the bridge — it's clean enough

## Files To Read First Next Session

1. This file (`docs/handover/HANDOVER_011_P0P2_TRIAGE_AND_BRIDGE.md`)
2. `plugins/vizier_tools_bridge.py` — skim to know the bridge shape
3. `config/clients/dmb.yaml` — pattern for new client configs
4. `tools/registry.py` lines 180-240 — exemplar injection + knowledge retrieval
5. `utils/retrieval.py` — `retrieve_similar_exemplars()` signature

## Verification

- 807 tests passing
- 8 bridge tests passing
- All P0 issues resolved
- 3 P1/P2 items documented with clear next steps
