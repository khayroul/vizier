# Decision: Config-Driven Workflow Deliverability

**Date:** 2026-04-09  
**Context:** GPT 7-Day Sprint, Day 2 — Workflow Truthfulness

## Problem

Three independent mechanisms governed whether a workflow could produce final output:

1. **Phase gate** (`config/phase.yaml`) — controls routing. `core` phase marked 9 workflows active.
2. **Delivery gate** (`tools/orchestrate.py`) — `_DELIVERABLE_WORKFLOWS` hardcoded frozenset of `{poster_production, document_production}`.
3. **Stub tools** (`tools/registry.py`) — 16 tools return placeholder responses.

These layers worked correctly (stubs never escaped to users), but:
- Adding a new deliverable workflow required a Python code change
- `phase.yaml` saying "active" while only 2 of 9 workflows could deliver was misleading
- No validation connected these layers

## Options Considered

**A. Narrow phase.yaml** — only list workflows where all tools are real. Would break routing tests and prevent routing to non-deliverable workflows that still serve useful intermediate purposes (e.g., research, refinement).

**B. Add `deliverable` field to workflow_registry.yaml** — keep routing broad, make deliverability explicit and config-driven. Orchestrator reads from YAML instead of hardcoded set.

**C. Keep layered defense, document it** — least work, doesn't fix the truthfulness or config-driven goal.

## Decision

**Option B.** Every workflow entry in `config/workflow_registry.yaml` now has an explicit `deliverable: true/false` field.

### What changed

- `config/workflow_registry.yaml` — added `deliverable` field to all 16 workflows
- `utils/workflow_registry.py` — added `get_deliverable_workflows()` and `is_document_family_workflow()`
- `tools/orchestrate.py` — replaced hardcoded `_DELIVERABLE_WORKFLOWS` with `get_deliverable_workflows()`
- `tools/registry.py` — replaced hardcoded `_DOCUMENT_WORKFLOWS` with `is_document_family_workflow()`
- Validation — `validate_workflow_registry()` now checks:
  - Every workflow has an explicit `deliverable` field (no silent defaults)
  - Deliverable workflows must have a delivery stage in their manifest

### What didn't change

- `_STUB_TOOL_NAMES` stays in code. Tool readiness is a code concern — you know a tool is real when you've written the implementation. Moving it to YAML would create a false sense that stub-ness is a config choice.
- Phase gate stays broad. Active-for-routing and deliverable are intentionally separate concepts.

## Risk Assessment

**Worst case for a YAML typo:** `deliverable: true` on a workflow with stub tools → orchestrator allows execution → delivery stage runs → delivery function returns `{"status": "stub"}` or fails with a clear error. The system doesn't silently succeed — it errors visibly.

This is acceptable because:
1. The validation catches missing `deliverable` fields
2. The validation catches deliverable workflows without delivery stages
3. Runtime still fails loudly if delivery can't produce output
