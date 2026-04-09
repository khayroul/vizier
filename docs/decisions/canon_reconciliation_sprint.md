# Canon Reconciliation: Architecture vs Repo (Sprint Day 5)

**Date:** 2026-04-09  
**Sections audited:** §8 (routing), §7.2/§7.4 (policy/quality), §18/§42 (publishing)

## Confirmed Matches

These implementations faithfully follow the architecture:

- **Routing 3-phase model** (§8) — fast-path deterministic, LLM fallback, RoutingResult emission
- **Policy 4-gate evaluator** (§7.2) — phase, tool, budget, cost in order
- **Text-image separation** (§42.3) — illustrations text-free, Typst overlays all text (#49)
- **illustration_shows field** (§42.3) — prompts from structured field, not raw text
- **Typst + ebooklib assembly** (§18) — both delivery paths implemented
- **NIMA + critique QA** (§42.5) — pre-screen + GPT-5.4-mini vision + adherence scoring

## Drift: Quality Gate Layers (§7.4)

Architecture defines 5 layers (0-4): structural, deterministic, tripwire, guardrails, operator feedback.

Code implements:
- Governance gates in `middleware/policy.py` (phase/tool/budget/cost)
- Visual QA in `tools/visual_pipeline.py` (NIMA + critique + guardrails)

Missing: no unified `quality_gate.py` module. Layers 0-1 (structural + deterministic) have no dedicated implementation. Quality checks are distributed across visual_pipeline.py and individual tool functions.

**Assessment:** This is a structural gap, not a behavioral one. The quality checks exist but aren't organized into the layered architecture described in §7.4. This is acceptable for Month 1-2 (only poster + document lanes are live) but should be addressed when publishing lanes (S15) ship and need the full quality stack.

## Not Yet Built (Expected)

These are architecture promises for future sessions, not drift:

| Feature | Architecture Section | Blocked On |
|---------|---------------------|------------|
| Creative workshop orchestration | §42.6 | S15 |
| Character consistency (CLIP loop) | §42.4 | S15 |
| Illustration tier selection | §42.4 | S15 |
| Derivative project fast-path | §42.6.1 | S21 |
| RollingContext per-page tracking | §43 | S15/S21 |
| Quality gate layers 0-4 as module | §7.4 | When publishing ships |
