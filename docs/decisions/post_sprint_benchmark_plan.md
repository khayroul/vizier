# Post-Sprint Benchmark Plan

**Date:** 2026-04-08
**Author:** S19 self-improvement session
**Status:** Planned (execute Month 3)
**Prerequisite:** 20+ rated examples per artifact type in production

---

## Purpose

After Month 1-2 (GPT-5.4-mini only), benchmark alternative models before
activating them in WorkflowPack YAMLs. No model enters production without
matching or beating GPT-5.4-mini on quality AND cost.

---

## 1. Sonnet 4.6 vs Opus 4.6 — `en_creative` tasks

**Hypothesis:** Sonnet 4.6 delivers near-Opus quality at ~40% lower cost
($3/$15 vs $5/$25 per 1M tokens). If Sonnet matches Opus on EN creative
prose for marketing copy, use Sonnet for marketing and reserve Opus for
fiction/narratives only.

- **Test cases:** `config/evaluations/poster_production_*.yaml` (EN briefs)
  + 20 additional EN creative prose prompts
- **Scorer:** GPT-5.4-mini (consistent scorer across all benchmarks)
- **Metrics:** quality score (1-5 average), cost per job, tokens per job
- **Promotion gate:** Sonnet must score within 0.3 of Opus on quality AND
  cost less than Opus

---

## 2. Gemini 3.1 Flash-Lite — `routing` + `classification` tasks

**Hypothesis:** Gemini 3.1 Flash-Lite ($0.25/M input) may match fine-tuned
Qwen 3.5 2B for routing and classification at comparable latency, without
the training investment.

- **Test cases:** 20 routing decisions from production logs + 20
  classification decisions
- **Scorer:** GPT-5.4-mini
- **Metrics:** accuracy vs GPT-5.4-mini baseline, latency (p50, p95), cost
- **Promotion gate:** Must match GPT-5.4-mini accuracy AND cost less

---

## 3. Anthropic Native Web Search — S12 research pipeline alternative

**Hypothesis:** Anthropic native web search (GA, free with code execution)
may replace Tavily for the S12 research pipeline. Key question is
Malaysian market query coverage.

- **Test cases:** 20 Malaysian market research queries from
  `config/evaluations/` + 10 manual queries covering local brands, Malay
  cultural events, and Southeast Asian marketing trends
- **Scorer:** Human evaluation of result relevance + GPT-5.4-mini
  relevance scoring
- **Metrics:** result relevance (1-5), coverage (% queries with useful
  results), latency
- **Promotion gate:** Must match Tavily on relevance AND coverage >= 80%

---

## Evaluation Method

1. Use `config/evaluations/` test cases as primary evaluation set
2. Each model runs the same cases under identical conditions
3. All outputs scored by GPT-5.4-mini (consistent scorer)
4. 20 cases per task type minimum
5. Use the experiment framework (S19 `tools/experiment.py`) to track
   results in the `experiments` and `experiment_results` tables
6. Results surfaced via the improvement notification system

---

## Promotion Gate (Universal)

A model must meet ALL of:

- **Quality:** Match or beat GPT-5.4-mini on average quality score (within 0.2)
- **Cost:** Equal or lower cost per job
- **Reliability:** < 1% error rate across test cases

Before it enters any WorkflowPack YAML. Promotions are config changes
pushed via git, not code deployments.

---

## Implementation Notes

- VizierAdapter and eval_runner.py are Week 1 post-sprint builds
- S19 provides the experiment infrastructure they plug into
- GEPA preference pair support is ready in the experiments table
  (`winner_id`, `loser_id`, `preference_source` columns)
- The benchmark plan executes AFTER 10-15 anchor set examples exist from
  Month 1 production
