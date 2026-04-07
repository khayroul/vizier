-- Dashboard views for S17 operator dashboard
-- Flatten JSONB and aggregate metrics for PostgREST consumption

-- Job trace summary (flattens production_trace JSONB)
CREATE OR REPLACE VIEW v_job_traces AS
SELECT
    j.id,
    j.client_id,
    j.job_type,
    j.status,
    j.priority,
    j.posture,
    j.created_at,
    j.updated_at,
    j.completed_at,
    j.production_trace->>'started_at' AS trace_started_at,
    j.production_trace->>'completed_at' AS trace_completed_at,
    jsonb_array_length(COALESCE(j.production_trace->'steps', '[]'::jsonb)) AS step_count,
    (SELECT SUM((s->>'input_tokens')::int + (s->>'output_tokens')::int)
     FROM jsonb_array_elements(COALESCE(j.production_trace->'steps', '[]'::jsonb)) s
    ) AS total_tokens,
    (SELECT SUM((s->>'cost_usd')::numeric)
     FROM jsonb_array_elements(COALESCE(j.production_trace->'steps', '[]'::jsonb)) s
    ) AS total_cost_usd,
    (j.production_trace->'steps'->-1)->>'step_name' AS last_step,
    j.production_trace AS raw_trace,
    j.goal_chain,
    c.name AS client_name
FROM jobs j
LEFT JOIN clients c ON j.client_id = c.id;

-- Token spend daily aggregation
CREATE OR REPLACE VIEW v_token_spend_daily AS
SELECT
    date_trunc('day', j.created_at)::date AS day,
    SUM(
        (SELECT SUM((s->>'input_tokens')::int + (s->>'output_tokens')::int)
         FROM jsonb_array_elements(j.production_trace->'steps') s)
    ) AS tokens,
    SUM(
        (SELECT SUM((s->>'cost_usd')::numeric)
         FROM jsonb_array_elements(j.production_trace->'steps') s)
    ) AS cost_usd,
    COUNT(*) AS job_count
FROM jobs j
WHERE j.production_trace IS NOT NULL
  AND j.production_trace->'steps' IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;

-- Token spend by model (for breakdown)
CREATE OR REPLACE VIEW v_token_spend_by_model AS
SELECT
    s->>'model' AS model,
    date_trunc('day', j.created_at)::date AS day,
    SUM((s->>'input_tokens')::int + (s->>'output_tokens')::int) AS tokens,
    SUM((s->>'cost_usd')::numeric) AS cost_usd,
    COUNT(*) AS step_count
FROM jobs j,
     jsonb_array_elements(j.production_trace->'steps') s
WHERE j.production_trace IS NOT NULL
GROUP BY 1, 2
ORDER BY 2 DESC, 4 DESC;

-- Feedback status summary
CREATE OR REPLACE VIEW v_feedback_summary AS
SELECT
    f.feedback_status AS status,
    COUNT(*) AS count,
    AVG(f.operator_rating) FILTER (WHERE f.feedback_status = 'explicitly_approved') AS avg_approved_rating,
    AVG(f.response_time_hours) FILTER (WHERE f.response_time_hours IS NOT NULL) AS avg_response_hours
FROM feedback f
WHERE f.anchor_set = false
GROUP BY f.feedback_status;

-- Pipeline summary by stage
CREATE OR REPLACE VIEW v_pipeline_summary AS
SELECT
    p.stage,
    COUNT(*) AS count,
    SUM(p.estimated_value_rm) AS total_value_rm,
    AVG(EXTRACT(EPOCH FROM (now() - p.created_at)) / 86400)::int AS avg_days_in_stage
FROM pipeline p
GROUP BY p.stage;

-- Pipeline detail (for kanban view)
CREATE OR REPLACE VIEW v_pipeline_detail AS
SELECT
    p.id,
    p.prospect_name,
    p.stage,
    p.estimated_value_rm,
    p.next_followup_at,
    p.source,
    p.notes,
    p.created_at,
    p.updated_at,
    EXTRACT(EPOCH FROM (now() - p.updated_at)) / 86400 AS days_in_stage,
    c.name AS client_name
FROM pipeline p
LEFT JOIN clients c ON p.client_id = c.id
ORDER BY p.stage, p.updated_at DESC;

-- Overdue invoices for client health
CREATE OR REPLACE VIEW v_overdue_invoices AS
SELECT
    i.id,
    i.client_id,
    c.name AS client_name,
    i.invoice_number,
    i.amount_rm,
    i.due_at,
    i.status,
    (now() - i.due_at) AS overdue_by
FROM invoices i
LEFT JOIN clients c ON i.client_id = c.id
WHERE i.status IN ('issued', 'partial')
  AND i.due_at < now();
