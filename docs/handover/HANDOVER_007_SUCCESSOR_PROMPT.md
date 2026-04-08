# CT-007 Successor Prompt — E2E Test Pyramid

You are continuing the Vizier debug/hardening track. Read this file as your full briefing.

## Context

CT-006 classified 22 bugs into 7 categories and implemented 6 structural prevention gates (all passing). The codebase is clean — 704 tests, 0 errors. The next step is building functional E2E tests from the user's perspective, layered from primitive to compound.

## Your Briefing

1. Read `docs/handover/HANDOVER_007.md` — full session history and current state
2. Read `CLAUDE.md` — project rules and anti-drift guards
3. Read `tests/test_ring_enforcement.py` — the 6 prevention gates you're building on top of
4. Read `tests/conftest.py` — the marker infrastructure (requires_db, requires_api)

## What to Build

Implement the E2E test pyramid, one layer at a time. **Start from Layer 1, validate it passes, then move up.**

### Layer 0 — DONE (TestModuleImports in test_ring_enforcement.py)

### Layer 1 — Service Connectivity
File: `tests/test_e2e_layer1_connectivity.py`

Smoke tests for each external dependency:
- Postgres: connect, verify core tables exist (clients, jobs, artifacts, feedback)
- OpenAI: single completion call, verify non-empty response
- OpenAI embeddings: embed one string, verify 1536-dim vector
- MinIO: upload + download a 1-byte file to vizier-assets bucket
- fal.ai: submit a tiny image generation, verify URL returned
- Typst: render a minimal .typ file to PDF bytes
- spans.db: write + read a span record

Use `requires_db` for Postgres/MinIO tests, `requires_api` for OpenAI/fal.ai tests.

### Layer 2 — Single-Function Primitives
File: `tests/test_e2e_layer2_primitives.py`

Mock external calls. Test each primitive in isolation:
- `call_llm()` → returns content string
- `embed_text()` → returns float vector
- `record_span()` → persists to SQLite
- `get_workflow_family()` → correct mapping
- `evaluate_readiness()` → ready/shapeable/blocked classification
- `fast_path_classify()` → "make a poster" routes to poster_production

**Audit existing tests first.** Many of these may already be covered. Only add what's missing.

### Layer 3 — Middleware Chains
File: `tests/test_e2e_layer3_middleware.py`

Test the gates and guardrails as a chain:
- Policy: allow active workflow, block inactive, block over-budget
- Quality gate: pass good score, fail bad score
- Guardrails: flag register mismatch (advisory, not blocking)

### Layer 4 — Tool Integration
File: `tests/test_e2e_layer4_tools.py`

Test tools produce correct artifacts (mock external calls):
- Poster pipeline: brief → image → scored → stored
- Research: query → sources → synthesized
- Knowledge retrieval: query + client → ranked cards
- Invoice: line items → Typst → PDF bytes

### Layer 5 — Full Workflow E2E
File: `tests/test_e2e_layer5_workflows.py`

Raw input → delivered artifact, full chain (mock external calls):
- Poster: input → route → policy → generate → score → store → trace
- Document: input → route → research → outline → sections → deliver
- Rework: feedback → analyze → revise → re-score → deliver

Two modes:
- Default (mocked): mock call_llm, fal_client, MinIO — test wiring
- `--run-api`: hit real services — test actual output

## Rules

- Run tests after each layer: `/opt/homebrew/bin/python3.11 -m pytest tests/test_e2e_layer*.py -v`
- Use existing markers: `requires_db`, `requires_api`
- Follow existing test patterns in `tests/` (pytest, fixtures, no unittest)
- Don't duplicate tests that already exist — audit first
- Commit after each layer passes
- GPT-5.4-mini for ALL model calls (anti-drift #54)

## Key Files

```
tests/conftest.py                    ← markers + auto-skip logic
tests/test_ring_enforcement.py       ← 6 prevention gates (27 tests)
utils/call_llm.py                    ← LLM wrapper (mock target)
contracts/routing.py                 ← fast_path_route, llm_route
middleware/policy.py                 ← PolicyEvaluator (4 gates)
middleware/quality_gate.py           ← 6 validation layers
tools/orchestrate.py                 ← governed execution entry point
config/workflow_registry.yaml        ← workflow metadata
config/phase.yaml                    ← phase gating
```
