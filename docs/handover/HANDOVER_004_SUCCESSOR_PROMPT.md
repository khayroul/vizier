# Vizier — Debug, Quality & Efficiency Session

## Who You Are

You are picking up the Vizier project after a 3-day build sprint. All code sessions are merged (645 tests passing). The sprint is functionally complete. Your predecessor (CT-004) spent the session fixing token metering gaps and hardening the Telegram bots after discovering a 4.7M token burn incident caused by misconfiguration.

**Your focus: debugging, quality improvement, and token efficiency.** You are NOT building new features. You are making what exists work reliably and cheaply.

---

## First Steps (do these in order)

### 1. Read context files

```bash
cd ~/vizier
```

Read these files in order:
- `CLAUDE.md` — navigation map, shared interfaces, anti-drift rules
- `docs/handover/HANDOVER_004.md` — cumulative handover from previous session (THIS IS YOUR PRIMARY BRIEFING)

Then read memory files for infrastructure context:
- Check `~/.claude/projects/-Users-Executor-vizier/memory/` for `hermes_gateway_setup.md`, `infra_environment.md`, `s6_completion.md`

### 2. Commit the uncommitted metering fixes

CT-004 left 6 changed files + 1 new test file uncommitted, plus a hermes submodule patch. Verify tests pass, then commit:

```
Vizier repo:
  M  utils/embeddings.py       — embed_text() now records spans
  M  utils/call_llm.py         — text-embedding-3-small in _PRICING
  M  utils/spans.py            — gateway_turns table + record_gateway_turn()
  M  tests/test_embeddings.py  — 4 tests (span recording verification)
  A  tests/test_gateway_metering.py — 4 tests (hook handler verification)

Hermes submodule (hermes-agent/):
  M  gateway/run.py            — agent:end hook emits token data (6 lines)
```

Commit the hermes submodule first (`cd hermes-agent && git add gateway/run.py && git commit`), then commit the parent repo with the submodule pointer update.

### 3. Verify live token tracking

The token tracker hook was fixed (import collision resolved via `importlib.util.spec_from_file_location`) but needs live verification. Both bots should be running:

```bash
pgrep -f "gateway.run" | xargs ps -o pid,command -p
```

If not running, see launch commands in HANDOVER_004 § "Bot Launch Commands".

Query the spans database for recent data:

```bash
sqlite3 data/spans.db "SELECT * FROM gateway_turns ORDER BY timestamp DESC LIMIT 10;"
```

If `gateway_turns` has data from today, the hook is working. If empty after the operator has sent messages, check `~/.hermes/logs/gateway.log` for `vizier_token_tracker` warnings.

**Healthy baseline:** ~6K input tokens per turn for simple Q&A = ~$0.001/turn.

---

## Primary Tasks

### Task 1: Token Efficiency Audit

The operator burned 4.7M tokens on 3 trivial tasks before CT-004 intervened. The root causes are fixed (toolset restriction, max_turns cap, persona, stale session clearing). Now verify the fixes hold and establish cost baselines.

**Approach:**

1. Query `gateway_turns` table for all sessions since the fix:
```sql
-- Per-session summary
SELECT session_id, COUNT(*) as turns, 
       SUM(delta_input) as total_in, SUM(delta_output) as total_out,
       printf('$%.4f', SUM(cost_usd)) as total_cost
FROM gateway_turns GROUP BY session_id ORDER BY MIN(timestamp) DESC;

-- Context snowball detection (cumulative input should plateau, not grow linearly)
SELECT turn_number, input_tokens as cumulative_ctx, delta_input as turn_cost,
       substr(user_message, 1, 50) as msg
FROM gateway_turns WHERE session_id = '<latest>' ORDER BY turn_number;
```

2. Establish cost targets:
   - Simple Q&A turn: <$0.002
   - Research request (with web_search): <$0.01
   - Poster production (via run_pipeline): <$0.05 total
   - If any of these are exceeded, investigate why

3. Check compression behavior — both bots have `compression.threshold: 0.50`. After 5+ turns in one session, verify context size plateaus rather than growing unbounded.

### Task 2: End-to-End Production Test

The `run_pipeline` tool was rewired from pro-max to the new vizier repo in CT-004 but was never tested end-to-end via Telegram. The chain is:

```
Telegram message → Hermes agent → run_pipeline tool call → run_governed() 
  → route() → readiness gate → policy gate → WorkflowExecutor → tool_registry → actual tools
```

**Approach:**

1. Read the governed execution chain: `tools/orchestrate.py`, `tools/executor.py`, `tools/registry.py`
2. Read the Vizier plugin: `~/.hermes/plugins/vizier_tools/__init__.py`
3. Ask the operator to tell the Vizier bot: "list available pipelines" — this tests the basic tool registration
4. If that works, try: "produce a simple poster for a car wash business called SparkleWash" — this tests the full chain
5. Trace where it breaks. The production tool registry (`tools/registry.py`) maps 46 YAML tool names to Python implementations, but many tools are stubs. Identify the minimum set needed for the poster workflow and fix them.
6. Check the production trace after a job runs:
```sql
-- If jobs table exists and has production_trace
SELECT job_id, production_trace FROM jobs ORDER BY created_at DESC LIMIT 1;
```

### Task 3: Quality Gate Verification

The architecture defines several quality mechanisms. Verify they work in practice:

1. **Tripwire critique-then-revise** (`tools/executor.py:run_tripwire`) — not score-only retry (anti-drift #21, #38). Check that when a scorer returns below threshold, specific critique is passed to the reviser.

2. **Parallel guardrails** (defined in workflow YAMLs) — check that brand voice and other guardrails run without duplicating work.

3. **Production traces** — verify that `TraceCollector` captures per-step metrics (tokens, cost, duration) and that `persist_trace()` writes to the database.

4. **NIMA scoring** — check if `tools/visual_scoring.py` produces quality scores that appear in step traces as `proof`.

### Task 4: Debugging Any Issues Found

As you work through Tasks 1-3, you'll find things that break. Fix them systematically:

1. Read `tools/orchestrate.py` to understand the governed execution chain
2. Read `tools/registry.py` to understand what tools are mapped
3. Read `config/phase.yaml` to understand which workflows are active
4. When something breaks, check:
   - Is the tool registered in `tools/registry.py`?
   - Is the workflow active in `config/phase.yaml`?
   - Does the tool's implementation exist and have the right signature?
   - Does pyright pass on the file?

---

## Key Architecture Context

### Token Tracking Pipeline

```
Telegram → Hermes gateway (LLM overhead)
  → agent:end hook → gateway_turns table (per-turn) + spans table (aggregate)
  → run_pipeline tool → run_governed()
    → WorkflowExecutor stages → call_llm() → @track_span → spans table
    → embed_text() → record_span → spans table
    → TraceCollector → ProductionTrace → jobs.production_trace JSONB
```

### Model Rules (Month 1-2)

**GPT-5.4-mini for EVERYTHING.** No Claude, no Gemini, no Qwen. Anti-drift #54. Image models (FLUX, Kontext) and text-embedding-3-small are the only exceptions.

### Bot Configuration

| Setting | Vizier | Steward |
|---------|--------|---------|
| HERMES_HOME | ~/.hermes | ~/.hermes-steward |
| Persona | ~/.hermes/SOUL.md | ~/.hermes-steward/SOUL.md |
| max_turns | 20 | 15 |
| Tools | web, vision, image_gen, skills, memory, clarify, todo, cronjob, messaging | web, memory, clarify, todo, skills, cronjob, messaging |

### Persona Loading Order
1. `SOUL.md` from HERMES_HOME → agent identity
2. `.hermes.md` from terminal.cwd (walks to git root) → project context
3. `agent.system_prompt` in config.yaml → ephemeral (rarely used)

### Import Collision Warning
Hermes `utils/` shadows Vizier `utils/`. Any code that needs to import Vizier modules from within Hermes context must use `importlib.util.spec_from_file_location()`, NOT `sys.path` manipulation. The gateway hook (`~/.hermes/hooks/vizier_token_tracker/handler.py`) demonstrates the correct pattern.

---

## Key Files

| Purpose | Path |
|---------|------|
| Governed execution chain | `tools/orchestrate.py` |
| Workflow executor | `tools/executor.py` |
| Production tool registry | `tools/registry.py` |
| Phase config (active workflows) | `config/phase.yaml` |
| Spans DB + gateway_turns | `utils/spans.py`, `data/spans.db` |
| Embedding tracker | `utils/embeddings.py` |
| LLM call point + pricing | `utils/call_llm.py` |
| Production trace contracts | `contracts/trace.py` |
| Vizier bot config | `~/.hermes/config.yaml` |
| Vizier persona | `~/.hermes/SOUL.md` |
| Vizier plugin | `~/.hermes/plugins/vizier_tools/__init__.py` |
| Token tracker hook | `~/.hermes/hooks/vizier_token_tracker/handler.py` |
| Steward config | `~/.hermes-steward/config.yaml` |
| Steward persona | `~/.hermes-steward/SOUL.md` |

---

## What NOT To Do

- Do NOT build new features — fix and optimize what exists
- Do NOT change the model from gpt-5.4-mini (anti-drift #54)
- Do NOT modify the Hermes submodule without committing inside it first, then updating the parent pointer
- Do NOT add `sys.path` hacks for cross-module imports — use `importlib.util.spec_from_file_location()`
- Do NOT trust that tools in `tools/registry.py` actually work — many map to stubs
- Do NOT clear Hermes sessions without warning the operator (they may have context they want to keep)
- Do NOT run the Hermes gateway from the vizier root directory — must `cd hermes-agent/` first to avoid utils/ collision
