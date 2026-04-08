# CT-009 Successor Prompt

You are continuing the Vizier production hardening track. Read this file as your full briefing.

## Context

CT-008 completed the most critical infrastructure gap: intelligence plumbing. The poster pipeline now generates on-brand content using client config (tone, mood, colors), design system context, and the Playwright/Jinja2 HTML renderer for Canva-quality output. FLUX text hallucination is solved. 778 tests pass, 0 failures.

**The pipeline works end-to-end via Telegram.** An operator can send "Create a Raya poster for DMB halal catering" and get back a professional PDF + PNG preview.

## Your Briefing

1. Read `docs/handover/HANDOVER_009.md` — full session history, what changed, known issues
2. Read `CLAUDE.md` — project rules, anti-drift guards, navigation map
3. Run `git log --oneline -15` to see recent commit history
4. Run tests: `DATABASE_URL=postgresql://localhost/vizier /opt/homebrew/bin/python3.11 -m pytest tests/ -x -q --tb=short` to verify clean baseline (expect 778 passed, 3 skipped)

## Current Architecture (Poster Pipeline)

```
Telegram message
  → Hermes plugin (~/.hermes/plugins/vizier_tools/__init__.py)
    → subprocess: run_governed(raw_input, client_id, job_id)
      → route() — fast-path or LLM classification → RoutingResult with design_system
      → evaluate_readiness() — spec completeness check
      → PolicyEvaluator.evaluate() — phase gate, tool gate, budget gate
      → WorkflowExecutor.run() — poster_production.yaml stages:
          1. intake: classify_artifact
          2. production: generate_poster (brand-aware copy) + image_generate (brand-aware brief expansion)
          3. qa: visual_qa (4-dimension critique)
          4. delivery: _deliver → Playwright HTML → PDF + PNG
    → Hermes sends PDF + PNG to Telegram
```

## Known Issues (Priority Order)

### P0 — Blockers for production quality
1. **Rework rerun is a no-op.** `_trace_insight` and `_quality_gate` in registry.py return static stubs. When an operator says "fix this poster", nothing happens.
2. **Parallel guardrails not wired.** Workflow YAMLs define them but executor doesn't invoke them.

### P1 — Quality gaps
3. **Exemplar table empty.** Plumbing works, data doesn't exist yet. Need a seeding strategy or first few 5/5 rated jobs.
4. **Knowledge retrieval is a stub.** `_knowledge_retrieve` returns empty cards. S18 knowledge spine needs activation.
5. **Only 1 client config (DMB).** Other clients get default colors/fonts. Need onboarding flow.
6. **Template selection hardcoded.** Always `poster_default`. No theme routing.

### P2 — Polish
7. **Visual QA scores unused.** Critique runs but doesn't gate delivery.
8. **Hermes plugin outside repo.** Not version-controlled.
9. **14 commits not pushed to remote.**

## What To Work On

Choose based on operator priority. Suggested order:

### Option A: Rework Pipeline (P0)
Make rework actually replay a job with corrections. Wire `_trace_insight` to load the original job's trace, identify failing dimensions, and `_quality_gate` to re-evaluate. The rework workflow YAML already exists at `manifests/workflows/rework.yaml`.

### Option B: Template Selection + More Templates (P1)
Build a template selector that picks the right HTML template based on brief content (e.g., road safety → `poster_road_safety`, food → a food template). Add 3-4 more themed templates. Wire into `_deliver()`.

### Option C: Knowledge Retrieval Activation (P1)
Wire `_knowledge_retrieve` to actually query knowledge_cards table via embeddings. S18 built the infrastructure; this wires it into the pipeline like we did for exemplar_injection.

### Option D: Push to Remote + Production Hardening
Push the 14 commits, set up proper CI, ensure Hermes plugin is backed up.

## Key Files for Any Task

```
tools/registry.py          — ALL tool implementations (800+ lines)
tools/executor.py          — workflow executor, quality techniques, tripwire
tools/orchestrate.py       — run_governed() entry point
tools/publish.py           — Playwright/Jinja2 poster renderer
tools/image.py             — expand_brief(), generate_image(), select_image_model()
templates/html/            — Jinja2 poster templates
config/clients/dmb.yaml    — client brand config example
config/phase.yaml          — active phases and quality postures
manifests/workflows/       — all 16 workflow YAMLs
```

## Rules

- GPT-5.4-mini for ALL text tasks (anti-drift #54)
- FLUX never sees text, artifact language, or quoted strings
- Tests must stay green (778 passed, 0 failed)
- Conventional commits: `feat(scope):`, `fix(scope):`, `chore(scope):`
- `pip install --break-system-packages` for Python packages
- `/opt/homebrew/bin/python3.11` for all Python execution
