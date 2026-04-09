# Codex Round 3 Complete — Deployment Boundary Hardened

**Generated:** 2026-04-09  
**Handover number:** 013  
**Reason:** All 4 Codex Round 3 findings resolved; deployment boundary hardened; full test suite green (850 tests, 0 failures)  
**Prior context:** `HANDOVER_012_HARDENING_REVIEW_AND_ROOT_CAUSE.md` (graphify root-cause analysis + Codex-as-debugger workflow established)

---

## Executive Summary

This session completed the **Codex Round 3 review cycle** — the third iteration of the Codex-as-debugger workflow where Codex finds integration gaps and this session fixes them. All 4 open findings are now resolved. The session also answered the user's validation question: Codex's root cause analysis (runtime hardening is Python-centric, deployment hardening is shell-centric, tests validate proxy behavior not actual installed boundary) was confirmed as correct.

**Key outcome:** The deployment boundary between the Vizier repo and the Hermes plugin system is now deterministic, stamped, and tested end-to-end with real file operations — not just mocked paths.

---

## What Was Done

### Codex Round 3 Findings — All 4 Closed

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| F2 | media_manifest recency fallback unsafe for concurrency | P2 | Removed `next(iter(_SESSION_STATE.values()))` fallback. Manifest lookup uses exact `hermes_session_id` only; skips entirely if missing. |
| F4 | logo_treatment added to 4 layers but zero templates consume it | P2 | Deferred. Removed from `PosterContentSchema`, `_STRING_SLOTS`, `_OPTIONAL_SLOTS`, delivery loop in `registry.py`, Jinja context in `publish.py`. Comment marks re-add point when a template's CSS consumes it. |
| F3 | install_plugin.sh doesn't materialize VIZIER_ROOT — loader guesses | P1 | `install_plugin.sh` now stamps `REPO_DIR` into `.vizier_root` alongside installed plugin. `_resolve_bridge_path()` reads stamp as priority-2 fallback (after repo-relative, before env var). No guessing. |
| F1 | No integration tests for actual deployment boundary | P1 | New `tests/test_plugin_deployment.py` — 12 tests across 3 categories (see below). |

### New Test File: `tests/test_plugin_deployment.py` (12 tests)

**TestInstallParity (3 tests):**
- `test_install_creates_stamp_file` — runs install_plugin.sh against temp HOME, verifies `.vizier_root` exists with correct repo path
- `test_install_copies_match_source` — byte-compares installed files against source of truth
- `test_install_is_idempotent` — runs install twice, verifies same result

**TestDeploymentBoundary (5 tests):**
- `test_installed_loader_resolves_bridge_via_stamp` — copies loader to arbitrary temp dir, writes stamp, verifies `_BRIDGE_PATH` resolves to real bridge
- `test_installed_loader_register_works` — full `register()` call from installed location, verifies tools + hooks exposed
- `test_installed_loader_exposes_bridge_helpers` — `__getattr__` delegation from installed copy to bridge
- `test_loader_without_stamp_falls_back_to_env` — env var fallback when no stamp file exists
- `test_loader_without_stamp_or_env_falls_back_to_home` — final `~/vizier` fallback

**TestDriftDetection (4 tests):**
- `test_source_loader_resolves_bridge_in_repo` — source tree resolution sanity check
- `test_bridge_module_has_register_function` — bridge exposes required interface
- `test_plugin_yaml_tools_match_bridge_registration` — tools in `plugin.yaml` match what `register()` actually exposes
- `test_plugin_yaml_hooks_match_bridge_registration` — hooks in `plugin.yaml` match what `register()` actually exposes

### Bonus Fixes

- Removed unused `InterpretedIntent` import from `tools/quality_harness.py` (ruff F401)
- Removed unused `field` import from `tools/template_selector.py` (ruff F401)
- These fixed the pre-existing `test_no_dead_imports_or_variables` failure, taking the suite from 849+1fail to 850+0fail

---

## Files Modified (Unstaged)

All changes are **unstaged** — 10 modified files + 1 new test file, not yet committed.

| File | What changed |
|------|-------------|
| `contracts/poster.py` | Removed `logo_treatment` field, updated `active_optional_slots()` |
| `plugins/hermes_loader/__init__.py` | 4-tier `_resolve_bridge_path()` with stamp file as priority-2 |
| `plugins/vizier_tools_bridge.py` | Removed manifest recency fallback, session_id injection outside enrichment tracking |
| `scripts/install_plugin.sh` | Stamps `.vizier_root` with REPO_DIR |
| `tools/orchestrate.py` | `_persist_interpreted_intent()` helper, wired after `interpret_brief()` |
| `tools/publish.py` | Extended slots in Jinja context, `dict[str, Any]` signatures, removed logo_treatment |
| `tools/quality_harness.py` | Removed unused InterpretedIntent import |
| `tools/registry.py` | Intent threading to expand_brief/visual_qa, active_slots to template selector, extended slot delivery, removed logo_treatment |
| `tools/template_selector.py` | Removed unused `field` import |
| `tools/visual_pipeline.py` | Adherence scoring wired into pass/fail gate, interpreted_intent parameter |
| `tests/test_plugin_deployment.py` | **NEW** — 12 deployment boundary tests |

---

## Test Suite Status

```
850 passed, 0 failed, 3 skipped
Pyright: 0 errors across all modified files
Ruff F401/F841: clean
```

---

## Codex-as-Debugger Workflow — Summary of All 3 Rounds

| Round | P1s Found | P2s Found | Fixed | Regression? |
|-------|-----------|-----------|-------|-------------|
| 1 | 7 | 2 | 7 P1s + 2 P2s attempted | — |
| 2 | 1 regression + 2 partial | 0 | 4 clean, 2 partial, 1 regressed | Yes (loader path) |
| 3 | 2 (F1, F3) | 2 (F2, F4) | All 4 | No |

**Root cause confirmed by graphify analysis:** InterpretedIntent has betweenness centrality 0.307 across 20+ communities — the single highest bridge node. Most P1 gaps were manifestations of this cross-cutting contract not being threaded end-to-end. The deeper systemic issue was runtime hardening being Python-centric while deployment hardening remained shell-centric.

---

## What the Next Session Should Do

### Option A: Submit to Codex Round 4 (recommended)

Send the current diff to Codex for review. The prompt should be:

> Review the 10 modified files + 1 new test file. All 4 findings from Round 3 are addressed. Specifically verify:
> 1. `.vizier_root` stamp written by install and consumed by loader (Finding 3)
> 2. 12 deployment boundary tests exercise real file ops, not mocks (Finding 1)
> 3. media_manifest has no recency fallback anywhere (Finding 2)
> 4. logo_treatment is fully removed from all layers (Finding 4)
> 5. No new regressions introduced

If Codex returns clean, commit and push.

### Option B: Commit, push, proceed to revenue expansion

If the user decides hardening is sufficient:

1. Commit the Round 3 changes (10 modified + 1 new file)
2. Push to origin/main (currently 21 commits + this batch ahead)
3. Resume session dispatch per CONTROL_TOWER.md — sessions S11-S19 are all unblocked (S10a complete)
4. Priority sessions for revenue: S15 (publishing lane), S11 (routing), S12 (research + exemplar seeding)

### Option C: Continue hardening

Remaining known gaps (P1, not blocking but open):

| # | Gap | Effort | Impact |
|---|-----|--------|--------|
| 1 | Exemplar table empty (0 rows) | ~1hr: write seeding script, promote 5-10 outputs | Exemplar injection into prompts becomes real |
| 2 | Only 1 populated client config (DMB) | ~30min: fill autohub.yaml + default.yaml | Multi-client routing testable |
| 3 | 21+ commits unpushed | ~5min: git push | Backup + CI |
| 4 | `utils/retrieval.py` stubs still `raise NotImplementedError` | Depends on S11/S12 | Blocked until those sessions run |

---

## Architecture Context for Next Session

### Bridge Path Resolution (now 4-tier)

```
1. Repo-relative    — Path(__file__).parent.parent / "vizier_tools_bridge.py"
                      Works when running from source tree (development)

2. Stamped root     — .vizier_root file next to installed __init__.py
                      Written by install_plugin.sh, deterministic

3. VIZIER_ROOT env  — Explicit override for non-standard installs

4. ~/vizier         — Last resort fallback (default clone location)
```

### Session Correlation (now clean)

```
_pre_tool_call() injects _hermes_session_id into args
   → handler reads from args (not from _SESSION_STATE recency)
   → manifest lookup by exact session_id only
   → no fallback, no cross-session bleed
```

### Poster Content Flow (end-to-end)

```
raw_brief
  → interpret_brief() → InterpretedIntent (canonical parse)
  → _persist_interpreted_intent() → jobs.interpreted_intent JSONB
  → select_template() ← intent + active_slots
  → expand_brief() ← interpreted_intent
  → image generation → NIMA prescreen
  → evaluate_visual_artifact() ← interpreted_intent → adherence scoring
  → _deliver() → extended slots in content dict
  → publish.py → Jinja context includes all slots
```

### What's Deferred (intentionally)

- `logo_treatment` — removed from contract; re-add when a template's CSS consumes it
- `retrieve_similar_exemplars()` — stub; S11 fills it
- `contextualise_card()` — stub; S12 fills it
- Extended workflow stubs (social_batch, content_calendar, serial_fiction) — validate structurally, fail at runtime until S21/S22/S24

---

## Key File Paths

| Purpose | Path |
|---------|------|
| Navigation + rules | `CLAUDE.md` |
| Architecture | `docs/VIZIER_ARCHITECTURE_v5_4_1.md` |
| Build plan | `docs/VIZIER_BUILD_v1_3_1.md` |
| Sprint dispatch | `CONTROL_TOWER.md` |
| This handover | `docs/handover/HANDOVER_013_CODEX_ROUND3_COMPLETE.md` |
| Prior handover | `docs/handover/HANDOVER_012_HARDENING_REVIEW_AND_ROOT_CAUSE.md` |
| Deployment tests | `tests/test_plugin_deployment.py` |
| Bridge module | `plugins/vizier_tools_bridge.py` |
| Thin loader | `plugins/hermes_loader/__init__.py` |
| Install script | `scripts/install_plugin.sh` |
| Poster contract | `contracts/poster.py` |
| Intent contract | `contracts/interpreted_intent.py` |
| Orchestrator | `tools/orchestrate.py` |
| Tool registry | `tools/registry.py` |
| Visual pipeline | `tools/visual_pipeline.py` |
| Publisher | `tools/publish.py` |
