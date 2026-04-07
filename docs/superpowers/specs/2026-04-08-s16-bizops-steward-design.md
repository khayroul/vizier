# S16 Design — BizOps + Steward + Crons

**Date:** 2026-04-08
**Session:** S16
**Status:** Approved
**Depends on:** S10a (core tables), S7 (call_llm, spans), S15a (Typst templates)

---

## Overview

BizOps (invoicing, payment tracking, sales pipeline, client health, crons) + Steward personal assistant (GTD-based ADHD-friendly PA — inbox capture, task processing, /next recommendation, /done with streaks, /snapshot, /project decomposition). Creates 9 tables in `migrations/extended.sql` (3 BizOps + 6 Steward).

## File Layout

```
migrations/extended.sql              — 9 tables + payment trigger + invoice_number_seq
tools/invoice.py          (~80 lines) — generate_invoice(), _render_invoice_typst()
tools/bizops.py           (~100 lines) — pipeline CRUD, client_health, revenue_summary
tools/steward.py          (~180 lines) — inbox, process, next, done, snapshot, project, decompose
tools/briefing.py         (~80 lines)  — morning_brief(), maghrib_shutdown(), 3-gate checks
config/personas/steward.md            — review and update existing file
config/steward_domains.py             — 21 domain constants (flat list, no logic)
tests/test_s16_bizops.py              — invoice, payment, pipeline, revenue tests
tests/test_s16_steward.py             — all Steward command tests
tests/test_s16_briefing.py            — morning brief 3-gate, maghrib, silence check tests
```

## Key Design Decisions

### D1. Invoice Typst generation — programmatic, not `assemble_document_pdf()`

The existing `invoice.typ` template uses `sys.inputs` for metadata (company name, client, dates) but has **hardcoded sample line items** (lines 134-140). While `sys.inputs` can pass strings, Typst lacks convenient dynamic array iteration from string inputs for variable-length line items. Invoice generation therefore writes a `.typ` source file programmatically (matching the `_generate_book_typst` pattern in publish.py), injecting line items, client info, SSM, and bank details directly into Typst source. Dedicated `_render_invoice_typst()` function in `tools/invoice.py`.

### D2. Invoice status — overdue computed on read, never stored

Full chain: `draft → issued → partial → paid`. The architecture DDL defines `status text default 'draft'` — the build doc exit criteria use the word "pending" but the DDL is authoritative; `draft` is the initial state. Overdue is **computed at query time**: `status IN ('issued', 'partial') AND due_at < now()`. It is never stored as a status value. Tests verify the overdue query, not a stored state transition.

Payment trigger on `payments` INSERT: computes `SUM(payments.amount_rm) WHERE invoice_id = NEW.invoice_id` vs `invoices.amount_rm`. Updates invoice status to `partial` or `paid`. Only transitions from `issued` or `partial` — never from `draft`.

Invoice numbering: `CREATE SEQUENCE IF NOT EXISTS invoice_number_seq`. Format: `VIZ-YYYY-NNN` using `nextval('invoice_number_seq')`.

### D3. /next scoring — multiplicative with hard filters

```
candidates = filter(energy_ok AND context_ok AND not_deferred AND defer_until <= today)
score = deadline_urgency * domain_neglect_factor * energy_bonus
```

Energy and context are hard filters, not score components. After Asr prayer time, filter to `energy_level = 'low'` only. The system picks ONE task and explains why — never shows a list.

### D4. Morning brief state — stored in `steward_reviews`

Last morning brief tracked via `steward_reviews` with `review_type='daily_brief'`. The 3-gate check:
- Gate 1 (time): current time > today's Subuh prayer time
- Gate 2 (data): `MAX(created_at)` across jobs/invoices/payments/steward_inbox > last brief time
- Gate 3 (dedup): no `steward_reviews` row with `review_type='daily_brief'` for today's date

### D5. Prayer times — `adhan` library with static fallback

Use the `adhan` Python library for algorithmic prayer time calculation from Kuala Lumpur lat/long. Implement an actual static fallback table (not just documented — the fallback code exists and runs if adhan import fails). **Dependency note:** `adhan` is not currently in `pyproject.toml` — must be added and installed via `pip3.11 install adhan --break-system-packages`.

### D6. Module separation — briefing.py for cross-cutting crons

`morning_brief()` and `maghrib_shutdown()` live in `tools/briefing.py`, importing from both `bizops` and `steward`. Keeps each module's concerns clean. `feedback_check_silence()` (SQL function from S10a) called during morning brief via `cur.execute("SELECT feedback_check_silence()")`.

### D7. 21 Wisdom Vault domains — flat constants

Defined in `config/steward_domains.py` as a flat `DOMAINS: list[str]` constant. Domain heatmap thresholds: green (3+ tasks in 7 days), amber (1-2 tasks), red (0 tasks, 7+ days neglected).

### D8. Tax rate — parameterized

`tax_rate` is a parameter to `generate_invoice()` (default 0.0). SST applied only when explicitly passed. Malaysia SST is 8% for applicable services.

### D9. Currency — MYR only for Month 1

Single currency (MYR). No multi-currency handling. `amount_rm` columns are all in MYR.

### D10. `dual_trace` import dropped

`middleware/observability.py` does not exist. Use `@track_span` from `utils.spans` for all public functions. Use `TraceCollector` from `contracts.trace` for invoice generation tracing.

### D11. 70% cut line applied (per CLAUDE.md §8)

CLAUDE.md explicitly authorizes: "Cut habits, deep work, health import, learning system — these are Phase 1 post-sprint additions, not sprint blockers." Tables for `steward_health_log` and `steward_learning` created (schema completeness). No tool code for habits engine (§20.6), deep work (§20.7), health import (§20.8), or learning system (§20.9). The build doc lists exit criteria for these features but CLAUDE.md's 70% cut line takes precedence.

### D12. Telegram bot token — Hermes gateway configuration

The build doc requires a separate `STEWARD_TELEGRAM_TOKEN` in `.env` for `@steward_bot`. S16 adds the env var reference to `.env.example` and documents the expected Hermes gateway config (separate bot token → separate persona routing). The actual gateway wiring is a Hermes runtime concern — S16 builds the tools that the gateway calls, not the gateway routing itself. The persona file at `config/personas/steward.md` already exists and defines the Steward persona.

## Database Schema

### Table creation order (FK dependencies)

1. `invoices` (references `clients`, `assets`)
2. `payments` (references `invoices`, `clients`)
3. `pipeline` (references `clients`, `assets`)
4. `steward_inbox` (no FK to new tables)
5. `steward_projects` (self-referential)
6. `steward_tasks` (references `steward_inbox`, `steward_projects`)
7. `steward_reviews` (no FK to new tables)
8. `steward_health_log` (no FK)
9. `steward_learning` (no FK)

Plus: `invoice_number_seq` sequence, `update_invoice_status_on_payment()` trigger function.

### DDL

S16 populates `migrations/extended.sql` (currently empty placeholder) with all 9 table DDL statements from architecture §16.4 and §16.4a verbatim, using `CREATE TABLE IF NOT EXISTS`. Also adds `invoice_number_seq` sequence and `update_invoice_status_on_payment()` trigger function.

## Exit Criteria Mapping

| Criterion | Implementation |
|-----------|---------------|
| Invoice PDF via Typst | `tools/invoice.py` → `_render_invoice_typst()` |
| Payment state machine | Postgres trigger on payments INSERT |
| Pipeline CRUD | `tools/bizops.py` → `update_pipeline()` |
| Morning brief after Subuh | `tools/briefing.py` → `morning_brief()` with 3-gate |
| 3-gate cron | Gate 1: time > Subuh, Gate 2: new data, Gate 3: not fired today |
| Client health | `tools/bizops.py` → `get_client_health()` |
| Prayer scheduling | `adhan` library + after-Asr filter in /next |
| Maghrib shutdown | `tools/briefing.py` → `maghrib_shutdown()` |
| 9 tables IF NOT EXISTS | `migrations/extended.sql` |
| Inbox capture (zero tokens) | `tools/steward.py` → `capture_inbox()` |
| /process with GPT-5.4-mini | `tools/steward.py` → `process_inbox()` |
| /next ONE task | `tools/steward.py` → `get_next()` |
| /done with streak | `tools/steward.py` → `mark_done()` |
| /snapshot domain heatmap | `tools/steward.py` → `get_snapshot()` |
| /project decomposition | `tools/steward.py` → `decompose_project()` |
| Revenue summary | `tools/bizops.py` → `get_revenue_summary()` |
| Persona file | `config/personas/steward.md` (exists, adequate as-is) |
| Telegram bot token | `.env.example` + D12 documents Hermes gateway config |
| feedback_check_silence wired | Called in `morning_brief()` |
| steward_health_log table (DDL only) | `migrations/extended.sql` — 70% cut line per CLAUDE.md |
| steward_learning table (DDL only) | `migrations/extended.sql` — 70% cut line per CLAUDE.md |
| Habits/deep work/health/learning tools | **DEFERRED** — 70% cut line per CLAUDE.md §8 |
| All tests pass, pyright clean | 3 test files |
