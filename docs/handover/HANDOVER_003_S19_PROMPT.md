# Worker Session: S19 — Self-Improvement + Calibration

## Working Directory
cd ~/executor/vizier

## Context Files
Read these files in this order:
1. ~/executor/vizier/CLAUDE.md — read FIRST
2. ~/executor/vizier/docs/VIZIER_ARCHITECTURE_v5_4_1.md — read ONLY: §15 (self-improvement loop — ALL subsections 15.1–15.10)
3. ~/executor/vizier/docs/VIZIER_BUILD_v1_3_1.md — read ONLY §7 session S19 spec (lines 1356-1397)

## What You Are Building
The self-improvement loop: pattern detection → failure analysis → improvement proposals → experimentation → promotion. The system learns from production traces and proposes changes to prompts, workflows, and knowledge — but never changes anything without operator approval.

Also: drift detection infrastructure (anchor set re-scoring, external benchmark ingestion, velocity decay alerting), exemplar set optimisation, prompt template versioning, and the experiment framework.

## Environment Setup
```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
set -a && source /Users/Executor/vizier/.env && set +a
```
Use `python3.11` explicitly. Use `pip3.11 install --break-system-packages` for any pip installs.

## Critical Rules
- GPT-5.4-mini for ALL text tasks. No exceptions. (Anti-drift #54)
- Anchor set feedback records (`anchor_set = true`) are NEVER included in exemplar libraries, training pools, or improvement loop pattern detection. (Anti-drift #56)
- Silence is NOT approval — exclude `silence_flagged` and `unresponsive` feedback from quality calculations. (Anti-drift #13)
- The system proposes, operator decides. No automatic promotion. (§15.8)
- Deterministic analysis first (SQL aggregations), LLM only when needed. (§15.2)
- `CREATE TABLE IF NOT EXISTS` for all table creation. (Idempotent migrations)
- Conventional commits: `feat(s19): ...`

## Existing Tables — DO NOT RECREATE
These tables already exist in `migrations/core.sql` and `migrations/extended.sql`:

**core.sql:**
- `feedback` — has `anchor_set boolean DEFAULT false`, `benchmark_source text`, `operator_rating int`
- `outcome_memory` — `job_id, artifact_id, client_id, first_pass_approved, revision_count, accepted_as_on_brand, human_feedback_summary, cost_summary jsonb, quality_summary jsonb, promote_to_exemplar`
- `system_state` — `version, change_type, change_description, changed_by, previous_state jsonb, promoted_from_experiment`
- `jobs` — `client_id, artifact_type, status, production_trace jsonb`
- `artifacts` — `artifact_type, job_id`
- `exemplars` — `artifact_id, client_id, artifact_family, artifact_type, approval_quality, status`
- `knowledge_cards` — with `context_prefix`, `search_vector` (FTS), `embedding` (pgvector)

**extended.sql:**
- `datasets` — `name text UNIQUE, description, source_type, status`
- `dataset_items` — `dataset_id uuid FK, content jsonb`

## Tables YOU Create — In `migrations/extended.sql` (append)

### experiments
```sql
CREATE TABLE IF NOT EXISTS experiments (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name                text NOT NULL,
    hypothesis          text NOT NULL,
    experiment_type     text NOT NULL,         -- 'prompt_variation' | 'step_elimination' | 'knowledge_injection' | 'model_comparison'
    control_config      jsonb NOT NULL,        -- snapshot of current config
    experiment_config   jsonb NOT NULL,        -- proposed change
    target_artifact_type text,                 -- which artifact types this applies to
    target_client_id    uuid REFERENCES clients(id),
    sample_size         int DEFAULT 10,        -- N jobs per arm
    control_count       int DEFAULT 0,
    experiment_count    int DEFAULT 0,
    status              text DEFAULT 'pending', -- pending | running | complete | promoted | rejected
    -- Results
    control_approval_rate   float,
    experiment_approval_rate float,
    control_avg_cost        float,
    experiment_avg_cost     float,
    winner              text,                  -- 'control' | 'experiment' | 'inconclusive'
    -- GEPA preference pair support (tech scout injection)
    winner_id           text,
    loser_id            text,
    preference_source   text,                  -- 'operator' | 'scorer' | 'gepa'
    -- Metadata
    proposed_by         text DEFAULT 'pattern_detector',
    decision_note       text,
    created_at          timestamptz DEFAULT now(),
    completed_at        timestamptz,
    promoted_at         timestamptz
);
```

### experiment_results
```sql
CREATE TABLE IF NOT EXISTS experiment_results (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id   uuid REFERENCES experiments(id) ON DELETE CASCADE,
    job_id          uuid REFERENCES jobs(id),
    arm             text NOT NULL,             -- 'control' | 'experiment'
    operator_rating int,
    first_pass_approved boolean,
    token_count     int,
    cost_usd        float,
    trace_summary   jsonb,
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_experiment_results_experiment ON experiment_results(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_experiments_type ON experiments(target_artifact_type);
```

## What To Build

### 1. tools/improvement.py — Pattern Detection + Proposals (~200 lines)

**PatternDetector class:**

`detect_approval_correlations(artifact_type: str, min_jobs: int = 20) -> list[dict]`
- SQL aggregation: group completed jobs by artifact_type
- Compare first_pass_approved vs not — what's different in production_trace JSONB?
- Look for: knowledge cards used, prompt template version, step sequence, client
- Return list of correlation dicts: `{pattern, approval_rate_with, approval_rate_without, sample_size, confidence}`
- EXCLUDE jobs where feedback.anchor_set = true (anti-drift #56)
- EXCLUDE jobs where feedback.feedback_status IN ('silence_flagged', 'unresponsive') (anti-drift #13)

`detect_cost_outliers(artifact_type: str, threshold_multiplier: float = 2.0) -> list[dict]`
- Find jobs costing 2x+ median for their artifact type
- Extract differentiating features from production_trace
- Return outlier dicts: `{job_id, cost, median_cost, multiplier, distinguishing_features}`

`detect_step_value(artifact_type: str) -> list[dict]`
- Compare quality between jobs that included a step vs skipped it
- Return: `{step_name, quality_with, quality_without, delta, sample_size}`

**generate_improvement_proposal(pattern: dict) -> dict**
- Takes a detected pattern, formats it as an ImprovementProposal
- Structure: `{id, observation, proposed_change, expected_impact, confidence, experiment_config}`
- Confidence levels: high (30+ jobs), medium (15-29), low (<15)

**FailureAnalysis class:**

`analyse_failures(artifact_type: str | None = None, min_rating: float = 3.0) -> list[dict]`
- Query traces WHERE operator_rating < min_rating
- Cluster by common features (artifact_type, client_id, quality dimensions from quality_summary)
- For each cluster: call GPT-5.4-mini to diagnose pattern and propose instruction change
- Return: `{cluster_id, common_features, sample_size, diagnosis, proposed_rule}`
- Store proposed rules in `config/improvement_rules/` as YAML files

`_cluster_failures(failures: list[dict]) -> list[list[dict]]`
- Simple clustering: group by (artifact_type, client_id) first
- Within groups, extract quality_summary dimensions, find common low-scoring dimensions
- No ML needed — SQL grouping + JSONB extraction

**RuleManager:**

`load_rules(artifact_type: str | None = None) -> list[dict]`
- Read YAML files from `config/improvement_rules/`
- Filter by artifact_type if provided
- Return list of rule dicts

`inject_rules_into_template(template: str, rules: list[dict]) -> str`
- Append relevant rules to prompt template as additional instructions
- Format: `\n\nIMPROVEMENT RULES:\n- {rule1}\n- {rule2}`

### 2. tools/experiment.py — Experiment Framework (~150 lines)

`create_experiment(proposal: dict) -> str`
- Insert into experiments table
- Return experiment_id
- Status: pending

`tag_job(job_id: str, experiment_id: str, arm: str) -> None`
- Insert into experiment_results with the job assignment
- Called by workflow executor when a matching job starts

`should_assign_experiment(job_id: str, artifact_type: str, client_id: str | None) -> dict | None`
- Check for running experiments matching this artifact_type + client
- If found and sample_size not reached: return `{experiment_id, arm}` (round-robin control/experiment)
- If no matching experiment: return None

`record_result(experiment_id: str, job_id: str, rating: int | None, approved: bool, tokens: int, cost: float) -> None`
- Update experiment_results row with outcome data
- Check if both arms have reached sample_size → if so, call `evaluate_experiment()`

`evaluate_experiment(experiment_id: str) -> dict`
- Compare control vs experiment arm results
- Calculate approval_rate, avg_cost for each arm
- Determine winner: experiment wins if approval_rate >= control AND cost <= control * 1.1
- Update experiment record with results
- Return summary dict for Telegram notification

### 3. tools/prompt_version.py — Template Versioning (~80 lines)

`get_template_version(template_path: str) -> dict`
- Read YAML front matter from template file
- Return: `{path, version, validation_score, last_promoted_at}`

`promote_template(template_path: str, new_content: str, decision_note: str) -> dict`
- Read current template
- Archive current version to `config/prompt_templates/archive/{name}_v{N}.md`
- Write new version with incremented version number
- Log to system_state table
- Log decision to `docs/decisions/` as markdown
- Return: `{path, old_version, new_version, archived_to}`

`revert_template(template_path: str) -> dict`
- Find most recent archive version
- Restore it as the active template
- Log revert to system_state
- Return: `{path, reverted_from, reverted_to}`

### 4. tools/calibration.py — Drift Detection + Benchmarks (~120 lines)

**70% CUT LINE: The drift detection CRON is CUT for this session. Build the detection FUNCTIONS but not the cron scheduler. Reason: needs 10-15 anchor set examples from Month 1 production.**

`score_anchor_set() -> dict`
- Query feedback WHERE anchor_set = true
- For each anchor: re-score using current scorer (GPT-5.4-mini) + current rubric
- Compare current scores against original operator_rating
- Return: `{anchor_count, original_avg, current_avg, drift, drifted_items: [...]}`
- Alert threshold: drift > 0.5

`check_velocity_decay(window_jobs: int = 100) -> dict`
- Count improvement proposals generated in last N completed jobs
- Compare against expected rate based on total jobs
- Return: `{total_jobs, proposals_in_window, expected_rate, actual_rate, alert: bool}`
- Alert if 0 proposals in 100+ jobs

`ingest_external_benchmark(image_data: bytes, metadata: dict) -> str`
- Create feedback record with `benchmark_source = 'external'`
- Tag for operator rating alongside production work
- Return feedback_id
- These records are EXCLUDED from improvement loop pattern detection

**ExemplarOptimiser:**

`optimise_exemplar_set(artifact_type: str, client_id: str, k: int = 3, n_trials: int = 10) -> dict`
- Requires 20+ exemplars for the artifact_type
- Try n_trials random combinations of k exemplars
- For each combination: score against 10 held-out test cases (from config/evaluations/)
- Use GPT-5.4-mini to rate each combination's diversity + coverage
- Keep the best combination
- Return: `{best_set: [exemplar_ids], score, trial_scores, improvement_over_default}`

**PromptVariationTester:**

`test_prompt_variations(template_path: str, artifact_type: str, n_variants: int = 3) -> dict`
- Requires 20+ rated examples for the artifact_type
- Read current template
- Generate n_variants via GPT-5.4-mini ("rewrite preserving intent")
- Score each variant against 10 held-out examples from config/evaluations/
- Return: `{current_score, variants: [{content, score}], best_variant, improvement}`

### 5. Notification Integration

Improvement proposals and experiment results are delivered via Hermes `send_message` tool (already available in the Hermes runtime). Your code generates the message text; the Hermes tool handles delivery.

**Proposal notification format:**
```
💡 IMPROVEMENT PROPOSAL: {name}

Observation: {observation}
Proposed change: {proposed_change}
Expected: {expected_impact}
Confidence: {confidence} ({sample_size} jobs)

/test — run experiment  |  /promote — apply now  |  /reject — discard
```

**Experiment complete format:**
```
✅ EXPERIMENT COMPLETE: {name}
Control: {control_approved}/{control_total} approved, {control_avg_cost} avg tokens
Experiment: {experiment_approved}/{experiment_total} approved, {experiment_avg_cost} avg tokens
/promote — lock it in  |  /extend — 5 more jobs  |  /reject — revert
```

**Drift alert format:**
```
⚠️ DRIFT ALERT: Quality baseline may be shifting.
Anchor set original avg: {original_avg}/5
Anchor set current scorer avg: {current_avg}/5 (+{drift} drift)
/review-anchors — open anchor review
```

For this session: implement `format_proposal_message()`, `format_experiment_result()`, `format_drift_alert()` as pure functions that return strings. The Hermes runtime calls these and sends via `send_message`. Do NOT import or call Hermes send_message directly — your tools return formatted messages, the runtime dispatches them.

### 6. Tests (~200 lines)

File: `tests/test_improvement.py`

Tests to implement:
- Pattern detector finds approval correlations from synthetic test data (insert 20+ jobs with known patterns)
- Pattern detector excludes anchor_set=true feedback (anti-drift #56)
- Pattern detector excludes silence_flagged feedback (anti-drift #13)
- Cost outlier detection finds 2x+ median jobs
- Step value detection compares quality with/without a step
- Failure analysis clusters low-rated jobs and proposes instruction changes
- Improvement proposal formats correctly with confidence levels
- Experiment creation, job tagging, result recording, evaluation
- Experiment round-robin assignment (control/experiment alternation)
- Experiment evaluation determines winner correctly
- Prompt template versioning: promote increments version, archive created
- Prompt template revert restores previous version
- Exemplar set optimisation selects best 3-combination from test pool (mock scorer)
- Prompt variation testing generates variants and scores (mock LLM)
- Anchor set scoring detects drift when scores shift > 0.5
- Velocity decay alert fires after 100 jobs with zero proposals
- External benchmark ingestion tags feedback with benchmark_source
- Improvement rules load from YAML and inject into templates
- `/promote` logs decision to docs/decisions/ and updates system_state table
- Message formatters produce correct Telegram-ready strings

**Test data strategy:** Use `get_cursor()` to insert synthetic jobs, feedback, outcome_memory records directly. Mock `call_llm` for LLM-dependent functions (failure diagnosis, prompt variation generation, exemplar scoring). Use `config/evaluations/poster_production_dmb.yaml` test cases where applicable.

## Existing Code — Import, Don't Rebuild

```python
from utils.database import get_cursor          # S10a — context manager, returns dict cursor
from utils.call_llm import call_llm            # S7 — stable_prefix + variable_suffix pattern
from utils.spans import track_span             # S7 — @track_span(step_type="improvement")
from utils.embeddings import embed_text, format_embedding  # S18 — text-embedding-3-small
from utils.retrieval import contextualise_card  # S12
from tools.knowledge import ingest_card         # S18 — canonical card ingestion
```

**Existing improvement rules directory:** `config/improvement_rules/mutation_operators.yaml` already exists (from S1). Your failure analysis writes additional YAML files here.

**Existing eval test cases:** `config/evaluations/poster_production_dmb.yaml`, `poster_production_ar_rawdhah.yaml`, `poster_production_rtm.yaml` exist (from S1). Use these as held-out test cases.

**Existing critique templates:** `config/critique_templates/poster_quality.md`, `childrens_narrative.md`, `document_coherence.md` exist (from S1). Prompt versioning applies to these + `config/prompt_templates/`.

## Tech Scout Injection (S19)
GEPA is installed (pyproject.toml). VizierAdapter and eval_runner.py are Week 1 post-sprint builds — S19 provides the infrastructure they plug into. Ensure experiments table schema supports preference pair storage (`winner_id`, `loser_id`, `preference_source`) alongside absolute ratings. DO NOT build VizierAdapter or eval_runner during this session.

## 70% Cut Line (from CLAUDE.md §2)
**Ship:** Pattern detection + failure analysis + experiment framework + prompt versioning + exemplar optimisation + prompt variation testing + improvement rules + message formatters + all notification formats.

**Cut:** Drift detection CRON (monthly scheduler). Build the detection functions (`score_anchor_set`, `check_velocity_decay`, `ingest_external_benchmark`) but not the cron. Reason: needs 10-15 anchor set examples from Month 1 production that don't exist yet.

## Benchmark Plan (Document, Don't Implement)
Create `docs/decisions/post_sprint_benchmark_plan.md` with:
- **Sonnet 4.6 vs Opus 4.6** for `en_creative` — Sonnet at ~40% lower cost ($3/$15 vs $5/$25). If Sonnet matches Opus on EN creative prose, use Sonnet for marketing, reserve Opus for fiction/narratives.
- **Gemini 3.1 Flash-Lite** ($0.25/M input) for `routing` + `classification` vs Qwen 3.5 2B fine-tuned. May match fine-tuned Qwen without training investment.
- **Anthropic native web search** (GA, free) as alternative to Tavily for S12 research pipeline. Test for Malaysian market query coverage.
- **Evaluation method:** Use config/evaluations/ test cases. Each model runs same cases, scored by GPT-5.4-mini (consistent scorer). 20 cases per task type minimum.
- **Promotion gate:** Model must match or beat GPT-5.4-mini on quality AND cost before it enters any WorkflowPack YAML.

## Exit Criteria
- Pattern detector finds approval correlations from test data
- Pattern detector correctly excludes anchor_set and silence_flagged feedback
- Failure analysis clusters low-rated jobs and proposes instruction changes
- Improvement proposal delivered as formatted Telegram message with /test /promote /reject
- Experiment tags jobs, compares results, reports winner
- Prompt template versioning: /promote increments version, /revert restores previous
- Exemplar set optimisation selects best 3-exemplar combination from test pool
- Prompt variation testing generates 3 variants and scores against held-out examples
- /promote updates system_state table and logs decision in docs/decisions/
- `config/improvement_rules/` directory exists and rules inject into templates
- `experiments`, `experiment_results` tables created with IF NOT EXISTS
- Drift detection functions built (score_anchor_set, check_velocity_decay, ingest_external_benchmark) — cron is CUT
- Anchor set scoring detects drift > 0.5
- External benchmark ingestion tags feedback with benchmark_source = 'external'
- Message formatters produce correct strings for all 3 notification types
- `docs/decisions/post_sprint_benchmark_plan.md` created
- All tests pass, pyright clean

## When Done
Commit with conventional commit message: `feat(s19): self-improvement loop — pattern detection, experiments, prompt versioning, calibration`
Report: Session ID, exit criteria pass/fail, decisions made, files created/modified, dependencies installed, test count, NEXT SESSION NEEDS TO KNOW.
