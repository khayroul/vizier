# Worker Prompt: Telegram Bot Debugging

## Your Task

The operator has 2 issues with the Telegram bots. Investigate, diagnose, and fix them.

**Ask the operator to describe the 2 issues before doing anything else.**

You are NOT building new features. You are debugging and fixing existing Telegram bot behavior.

---

## System Context

### Two Telegram Bots

| Bot | Username | HERMES_HOME | Token env var |
|-----|----------|-------------|---------------|
| Vizier | @MyVizierBot | ~/.hermes | TELEGRAM_BOT_TOKEN |
| Steward | @vStewardBot | ~/.hermes-steward | STEWARD_BOT_TOKEN |

### How They Run

Both bots run Hermes Agent's gateway. They MUST be launched from the `hermes-agent/` directory to avoid a `utils/` import collision (Hermes has its own `utils/` that shadows Vizier's).

```bash
# Check if running
pgrep -f "gateway.run" | xargs ps -o pid,command -p

# Vizier launch
cd /Users/Executor/vizier/hermes-agent
set -a && source /Users/Executor/vizier/.env && set +a
nohup python3.11 -m gateway.run > /Users/Executor/vizier/logs/hermes_gateway.log 2>&1 &

# Steward launch (separate HERMES_HOME to avoid PID lock conflict)
HERMES_HOME=/Users/Executor/.hermes-steward TELEGRAM_BOT_TOKEN="$STEWARD_BOT_TOKEN" \
nohup python3.11 -m gateway.run > /Users/Executor/vizier/logs/steward_gateway.log 2>&1 &
```

### Key Config Files

| Purpose | Path |
|---------|------|
| Vizier config | ~/.hermes/config.yaml |
| Vizier persona | ~/.hermes/SOUL.md |
| Vizier plugin | ~/.hermes/plugins/vizier_tools/__init__.py |
| Vizier token tracker | ~/.hermes/hooks/vizier_token_tracker/handler.py |
| Steward config | ~/.hermes-steward/config.yaml |
| Steward persona | ~/.hermes-steward/SOUL.md |
| Steward token tracker | ~/.hermes-steward/hooks/vizier_token_tracker/handler.py |
| Gateway logs (Vizier) | ~/vizier/logs/hermes_gateway.log |
| Gateway logs (Steward) | ~/vizier/logs/steward_gateway.log |
| Spans DB | ~/vizier/data/spans.db |

### Bot Configuration

| Setting | Vizier | Steward |
|---------|--------|---------|
| max_turns | 20 | 15 |
| Tools | web, vision, image_gen, skills, memory, clarify, todo, cronjob, messaging | web, memory, clarify, todo, skills, cronjob, messaging |
| terminal.cwd | ~/vizier | ~ |
| Persona | Production engine (NOT coding agent) | GTD personal assistant |

### Persona Loading Order
1. `SOUL.md` from HERMES_HOME → agent identity
2. `.hermes.md` from terminal.cwd (walks to git root) → project context
3. `agent.system_prompt` in config.yaml → ephemeral (rarely used)

---

## Recent Fixes (already committed)

These were fixed earlier today — if you see these symptoms, the fix is already in the code but the bots may need restarting to pick it up:

1. **OpenAI 400 error** — `utils/call_llm.py` was sending `max_tokens` instead of `max_completion_tokens` for gpt-5.4-mini. Fixed.
2. **fal.ai 404** — `tools/image.py` had wrong endpoint names (`flux-2-dev` → `flux/dev`, `flux-2-pro` → `flux-pro`). Fixed.
3. **Plugin import path** — `vizier_tools` plugin at `~/.hermes/plugins/vizier_tools/__init__.py` now points at `~/vizier` (was `~/vizier-pro-max`). Fixed.
4. **Token tracker import collision** — Hook uses `importlib.util.spec_from_file_location()` to avoid `utils/` shadow. Do NOT use `sys.path` manipulation.

---

## Debugging Checklist

### 1. Check bot processes
```bash
pgrep -f "gateway.run" | xargs ps -o pid,command -p
```
If not running, restart using launch commands above.

### 2. Check logs for errors
```bash
tail -100 ~/vizier/logs/hermes_gateway.log
tail -100 ~/vizier/logs/steward_gateway.log
```

### 3. Check token tracking
```bash
sqlite3 ~/vizier/data/spans.db "SELECT * FROM gateway_turns ORDER BY timestamp DESC LIMIT 5;"
```

### 4. Check plugin health
```bash
# Look for registration messages in Vizier log
grep -i "vizier" ~/vizier/logs/hermes_gateway.log | tail -20
```

### 5. Test the production chain locally
```bash
set -a && source ~/vizier/.env && set +a
python3.11 -c "
from tools.orchestrate import run_governed
result = run_governed(
    raw_input='produce a simple poster for a test business',
    client_id='default',
    job_id='debug-test-001',
)
print('Workflow:', result.get('workflow'))
print('Stages:', len(result.get('stages', [])))
"
```

---

## Hard Rules

- Do NOT change the model from gpt-5.4-mini (anti-drift #54)
- Do NOT modify the Hermes submodule without committing inside it first
- Do NOT add `sys.path` hacks — use `importlib.util.spec_from_file_location()`
- Do NOT run the gateway from `~/vizier/` — must `cd hermes-agent/` first
- Do NOT clear Hermes sessions without asking the operator
- Use `python3.11` explicitly (system python3 is 3.9.6)
- All pip installs: `pip3.11 install --break-system-packages`

---

## After Fixing

1. Verify the fix works by sending a test message to the bot
2. Check logs are clean
3. Check `gateway_turns` table is recording data
4. Commit any code changes with a descriptive message
5. Report what was wrong and what you changed
