# GEPA Model Strategy

**Date:** 7 April 2026
**Status:** Planned (post-sprint Week 1)

## Strategy

GEPA (Generalized Preference Alignment) provides preference-based optimization
for Vizier's production quality loop.

### Bootstrap (Sprint — S5)
- Convert D2, D3, D12 poster datasets to GEPA preference pair format
- ~13,000 preference examples before first production job
- Stored in datasets/gepa_bootstrap/

### Month 1-2 (Production)
- GPT-5.4-mini judges production output quality (anti-drift #54)
- Human operator ratings (1-5) generate preference pairs
- GEPA preference pairs accumulate from production feedback

### Month 3+ (Optimization)
- VizierAdapter wraps Vizier's prompt generation as GEPA-optimizable
- eval_runner.py runs A/B experiments via S19 experiment framework
- Preference Arena compares prompt variants head-to-head
- GPT-5.4 (full, not mini) judges preference pairs for validation

### Model Rules
- ❌ Do NOT build VizierAdapter during sprint
- ❌ Do NOT run GEPA optimization during sprint
- ❌ Do NOT use GPT-5.4 for production tasks (only GEPA validation judging)
- ✅ DO install GEPA and create bootstrap data during sprint
- ✅ DO ensure S19 experiments table supports preference pairs
