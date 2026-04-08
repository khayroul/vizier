# VIZIER Control Tower — Handover Document

**Generated:** 2026-04-08 ~17:30
**Handover number:** 004
**Reason:** End of CT-004 session — metering fixes, Telegram bot hardening, token burn root cause analysis complete
**Prior handovers:** 001–003 (cumulative). This document is cumulative — successor needs ONLY this file + HANDOVER_003 for full session history.

---

## Current Status Board

```
SESSION | STATUS         | BLOCK | TESTS
--------|----------------|-------|------
S0–S21  | ✅ ALL MERGED  | 1–11  | 538 base
IT-1,3,5| ✅ DONE        | 12    | 47
IT-2    | ✅ MERGED      | 12    | +35
IT-4    | ✅ MERGED      | 12    | +24
S19     | ✅ MERGED      | 10    | +29
CODEX   | ✅ MERGED      | 12    | +13
CT-004  | ✅ METERING    | —     | +6 (embeddings + gateway)
--------|----------------|-------|------
TOTAL   |                |       | 645 passing, 0 failures
```

**HEAD:** 113e1d3 (fix(governance): artifact-aware readiness gate + pyright clean)
**Uncommitted:** 6 files — metering fixes (utils/embeddings.py, utils/spans.py, utils/call_llm.py, tests/test_embeddings.py, tests/test_gateway_metering.py, hermes-agent submodule patch)
**Remote:** git@github.com:khayroul/vizier.git — 5 commits ahead of origin/main

---

## What CT-004 Did

### 1. Full Test Suite Pass (Block 12)

639 → 645 tests. All green in 17s. Sprint code complete.

### 2. Token Metering Gaps Fixed

Two gaps found where LLM tokens were consumed without being tracked:

| Gap | File | Fix |
|-----|------|-----|
| **Embedding calls** | `utils/embeddings.py` | Added `record_span()` with model=`text-embedding-3-small`, token count from API response, cost at $0.02/1M. Optional `job_id` kwarg. |
| **Hermes gateway overhead** | `hermes-agent/gateway/run.py:2750` | Enriched `agent:end` hook emit with `input_tokens`, `output_tokens`, `model`, `api_calls`. Created `~/.hermes/hooks/vizier_token_tracker/` hook that records spans. |

Added `text-embedding-3-small` pricing to `_PRICING` dict in `utils/call_llm.py`.

New `gateway_turns` table in spans DB for per-session, per-turn token analysis:
```
gateway_turns (turn_id, session_id, turn_number, model,
               input_tokens, output_tokens, delta_input, delta_output,
               cost_usd, api_calls, user_message, timestamp)
```

### 3. Token Burn Root Cause Analysis (CRITICAL)

**Incident:** Operator produced 1 research + 2 posters via Telegram. Burned **4.7M tokens** ($0.70+) for virtually nothing.

**Root causes (all fixed):**

| # | Root Cause | Impact | Fix Applied |
|---|-----------|--------|-------------|
| 1 | `vizier_tools` plugin imported from dead `vizier-pro-max` repo | Vizier production tools (run_pipeline) non-functional | Rewrote plugin → `~/vizier`, uses `run_governed()` |
| 2 | No agent persona (`.hermes.md` empty, `SOUL.md` missing) | Agent acted as general-purpose coding bot | Created `SOUL.md` in both HERMES_HOMEs |
| 3 | All Hermes tools enabled (terminal, execute_code, patch, browser) | Agent wrote Python scripts for posters (29 execute_code, 16 terminal, 16 patch in one session) | `platform_toolsets.telegram` restricted to [web, vision, image_gen, skills, memory, clarify, todo, cronjob, messaging] |
| 4 | `max_turns: 90` | Agent ran 86 tool calls in one session | Reduced to 20 (Vizier) / 15 (Steward) |
| 5 | 15 pro-max skills teaching coding workflows | Skills reinforced "write PIL scripts" behavior | All archived to `_archived_pro_max/` |
| 6 | `terminal.cwd: vizier-pro-max` | Wrong repo | Fixed to `~/vizier` |
| 7 | `prompt_logger` plugin importing from pro-max | Broken import | Disabled (replaced by Vizier spans) |
| 8 | Session history carrying forward 196 messages | Each tool call re-sent full context: 196 msgs × ~47K = 4.6M tokens | max_turns cap + tool restriction prevents snowball |

### 4. Telegram Bot Hardening

**Both bots restarted and verified running.**

| Setting | Vizier (@MyVizierBot) | Steward (@vStewardBot) |
|---------|----------------------|----------------------|
| HERMES_HOME | `~/.hermes` | `~/.hermes-steward` |
| SOUL.md | Production engine persona | GTD personal assistant persona |
| max_turns | 20 | 15 |
| platform_toolsets.telegram | web, vision, image_gen, skills, memory, clarify, todo, cronjob, messaging | web, memory, clarify, todo, skills, cronjob, messaging |
| terminal.cwd | ~/vizier | ~ |
| Vizier plugin | v1.0.0 → `~/vizier`, `run_governed()` | N/A (no plugins) |
| Token tracker hook | Installed (direct file import) | Installed (direct file import) |
| Mention patterns | `^vizier\b` only | `^steward\b` |

**Key discovery:** Hermes loads persona from `HERMES_HOME/SOUL.md`, NOT `.hermes.md`. The `.hermes.md` file is for project-directory context (loaded from cwd). Both files should exist for completeness.

**Key discovery:** Hook imports must use `importlib.util.spec_from_file_location()`, not `sys.path` manipulation, because `hermes-agent/utils/` shadows `vizier/utils/`.

### 5. Pro-Max Ties Fully Cut

| Component | Before | After |
|-----------|--------|-------|
| vizier_tools plugin | `~/vizier-pro-max` | `~/vizier` |
| prompt_logger plugin | imported from pro-max | disabled (no-op) |
| Skills | 15 pro-max skills active | all archived |
| terminal.cwd | vizier-pro-max | vizier |
| config.yaml mention | `^hermes\b` | removed |

---

## Uncommitted Changes (MUST COMMIT)

```
Vizier repo (~/vizier):
  M  utils/embeddings.py      — embed_text() now records spans
  M  utils/call_llm.py        — text-embedding-3-small in _PRICING
  M  utils/spans.py            — gateway_turns table + record_gateway_turn()
  M  tests/test_embeddings.py  — 4 tests (span recording verification)
  A  tests/test_gateway_metering.py — 4 tests (hook handler verification)

Hermes submodule (hermes-agent):
  M  gateway/run.py            — agent:end hook emits token data (6 lines)

External (NOT in git):
  ~/.hermes/config.yaml                              — toolset restrictions, max_turns
  ~/.hermes/SOUL.md                                  — Vizier persona
  ~/.hermes/.hermes.md                               — Vizier persona (backup)
  ~/.hermes/hooks/vizier_token_tracker/handler.py     — gateway overhead tracking
  ~/.hermes/plugins/vizier_tools/__init__.py          — v1.0.0 using run_governed()
  ~/.hermes/plugins/prompt_logger/__init__.py         — disabled
  ~/.hermes-steward/config.yaml                      — toolset restrictions, max_turns
  ~/.hermes-steward/SOUL.md                          — Steward persona
  ~/.hermes-steward/hooks/vizier_token_tracker/handler.py — same hook
```

---

## Known Issues / Open Items

### P0 — Must fix next session

1. **Vizier `run_pipeline` untested end-to-end via Telegram.** The plugin registers `run_governed()` as a Hermes tool, but no live test has confirmed the full chain (Telegram → Hermes → run_pipeline tool → run_governed → WorkflowExecutor → tool_registry → actual tool execution). The production tool registry maps 46 tools but many are stubs or partially implemented.

2. **Gateway token tracking hook not yet confirmed live.** The `utils/` import collision was fixed (direct file import), but no Telegram message has been processed since the fix. Need to send test messages and verify `gateway_turns` table populates.

3. **Hermes submodule dirty.** `gateway/run.py` has a 6-line patch (agent:end token data). Must commit within the submodule, then update the parent repo's submodule pointer.

### P0.5 — Confirmed live (first data captured)

Token tracker hook confirmed working. First live data:

| Bot | Session | Turns | Total In | Total Out | Cost | Per-turn avg |
|-----|---------|-------|----------|-----------|------|-------------|
| Vizier (STALE session) | 2bea99 | 3 | 330K | 1.3K | $0.050 | $0.017 |
| Steward (CLEAN session) | f464048e | 2 | 12K | 295 | $0.002 | $0.001 |

Stale Vizier session carried 110K tokens of prior history — 16x per-turn cost vs clean. Sessions cleared after discovery. **Lesson: always `/new` or clear sessions after config changes.**

Healthy baseline: ~6K input tokens per turn for a simple Q&A = ~$0.001/turn.

### P1 — Quality & efficiency improvements (next session focus)

4. **Token efficiency per deliverable.** `gateway_turns` table enables per-session/per-turn analysis. After live testing, query:
   ```sql
   -- Per-session cost
   SELECT session_id, COUNT(*) turns, SUM(delta_input) in_tok,
          SUM(delta_output) out_tok, SUM(cost_usd) cost
   FROM gateway_turns GROUP BY session_id;

   -- Context snowball detection (input_tokens should NOT grow linearly)
   SELECT turn_number, input_tokens, delta_input
   FROM gateway_turns WHERE session_id = '...' ORDER BY turn_number;
   ```

5. **Production trace per-job analysis.** `run_governed()` returns `trace` with per-step breakdown (StepTrace: step_name, model, input_tokens, output_tokens, cost_usd, duration_ms, proof). Query via `jobs.production_trace` JSONB column once jobs start flowing.

6. **Compression tuning.** Both bots have `compression.threshold: 0.50` (compress at 50% context). May need tuning — too aggressive = lost context, too late = token waste.

7. **Context reuse across turns.** When producing multiple posters in one session, shared context (client info, design system) gets re-sent every turn. Consider session-level context caching or prompt prefix optimization.

### P2 — Nice to have

8. **launchd plists for bot persistence.** Both bots are nohup — die on reboot. Operator was informed. Create `~/Library/LaunchAgents/com.vizier.gateway.plist` and similar for Steward.

9. **Push to origin.** Repo is 5 commits ahead of origin/main. Push when ready.

10. **Stale git branches cleanup.** Multiple `claude/*` branches from worktree sessions. Safe to delete.

---

## Architecture Quick Reference

### Token Tracking Pipeline (fully wired as of CT-004)

```
User sends Telegram message
  → Hermes gateway processes (LLM calls for reasoning)
    → agent:end hook fires with cumulative token counts
      → vizier_token_tracker records to spans DB:
          - gateway_turns table (per-turn, with session_id + deltas)
          - spans table (aggregate, step_type='gateway_overhead')
  → Agent calls run_pipeline tool
    → run_governed() executes:
        route → readiness → policy → WorkflowExecutor
          → Each stage calls tools from registry
            → Tools call call_llm() → @track_span → spans table
            → Tools call embed_text() → record_span → spans table
          → TraceCollector aggregates → ProductionTrace
        → persist_trace() → jobs.production_trace JSONB
```

### Bot Launch Commands

```bash
# From hermes-agent dir (CRITICAL — avoids utils/ path conflict)
cd /Users/Executor/vizier/hermes-agent
set -a && source /Users/Executor/vizier/.env && set +a

# Vizier
nohup python3.11 -m gateway.run > /Users/Executor/vizier/logs/hermes_gateway.log 2>&1 &

# Steward
HERMES_HOME=/Users/Executor/.hermes-steward TELEGRAM_BOT_TOKEN="$STEWARD_BOT_TOKEN" \
nohup python3.11 -m gateway.run > /Users/Executor/vizier/logs/steward_gateway.log 2>&1 &
```

### Persona Loading

- **`SOUL.md`** in `HERMES_HOME` → agent identity (slot #1 in system prompt). This is what makes the bot "Vizier" or "Steward".
- **`.hermes.md`** in `terminal.cwd` → project context (walks to git root). Loaded AFTER SOUL.md.
- **`agent.system_prompt`** in config.yaml → ephemeral system prompt (rarely used).

---

## Next Session Directive

**Focus: Debugging, Quality, and Efficiency Improvement**

### Suggested approach:

1. **Verify live token tracking** — Send 2-3 test messages to each bot. Query `gateway_turns` and `spans` tables. Confirm hook works, deltas are correct, costs reasonable.

2. **End-to-end production test** — Tell Vizier to produce a simple poster via Telegram. Trace the full chain: run_pipeline → run_governed → workflow execution. Identify where it breaks (likely at tool_registry — stubs vs real implementations). Fix the highest-value production path first (poster_production).

3. **Token efficiency audit** — After a few Telegram interactions, analyze:
   - Gateway overhead per turn (should be <5K tokens for simple requests)
   - Context growth rate (should plateau, not grow linearly)
   - Production trace per-step cost (which stages are expensive?)
   - Compare: what SHOULD a poster cost vs what it DOES cost

4. **Quality gates** — Verify tripwire critique-then-revise works in practice. Check guardrail checks don't duplicate work. Ensure quality feedback (NIMA scores, brand voice match) appears in production traces.

5. **Commit the metering fixes** — 6 changed files + 1 new test file + hermes submodule patch. All 645 tests passing.

### Key files for the successor:

| Purpose | File |
|---------|------|
| Gateway overhead tracking | `~/.hermes/hooks/vizier_token_tracker/handler.py` |
| Embedding tracking | `utils/embeddings.py` |
| Spans DB + per-turn table | `utils/spans.py` |
| Governed execution chain | `tools/orchestrate.py` |
| Production tool registry | `tools/registry.py` |
| Workflow executor | `tools/executor.py` |
| Bot configs | `~/.hermes/config.yaml`, `~/.hermes-steward/config.yaml` |
| Bot personas | `~/.hermes/SOUL.md`, `~/.hermes-steward/SOUL.md` |
| Plugin (Vizier tools) | `~/.hermes/plugins/vizier_tools/__init__.py` |

### Memory files to read:
- `memory/hermes_gateway_setup.md` — full bot setup reference with root cause details
- `memory/infra_environment.md` — Python, API keys, paths
- `memory/s6_completion.md` — contract import paths
