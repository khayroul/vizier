-- core.sql: 16 core Postgres tables (14 original + 2 document_set).
-- Created by S10a. All statements use CREATE TABLE IF NOT EXISTS for idempotent re-runs.
-- Re-running this file must not error or lose data.

-- Required extensions
CREATE EXTENSION IF NOT EXISTS "vector";       -- pgvector for embeddings

-- ============================================================================
-- §16.1  CORE 8 TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS clients (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    industry        text,
    brand_config    jsonb,
    style_profiles  jsonb,
    contact_info    jsonb,
    billing_config  jsonb,
    brand_mood      text[],
    status          text DEFAULT 'active',
    created_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           uuid REFERENCES clients(id),
    raw_input           text,
    interpreted_intent  jsonb,
    routing_result      jsonb,
    job_type            text,
    status              text DEFAULT 'received',
    hermes_session_id   text,
    priority            text DEFAULT 'normal',
    posture             text DEFAULT 'production',
    production_trace    jsonb,
    goal_chain          jsonb,
    created_at          timestamptz DEFAULT now(),
    updated_at          timestamptz DEFAULT now(),
    completed_at        timestamptz
);

-- assets must be created before artifacts (FK dependency)
CREATE TABLE IF NOT EXISTS assets (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    storage_path        text NOT NULL,
    filename            text,
    mime_type           text,
    size_bytes          bigint,
    asset_class         text,
    asset_category      text,
    dominant_colours    jsonb,
    colour_palette_type text,
    layout_type         text,
    width_px            int,
    height_px           int,
    aspect_ratio        text,
    tags                text[],
    seasons             text[],
    industries          text[],
    visual_embedding    vector(512),
    times_used          int DEFAULT 0,
    last_used_at        timestamptz,
    quality_tier        text,
    operator_rating     int,
    source              text,
    parent_asset_id     uuid REFERENCES assets(id),
    client_id           uuid REFERENCES clients(id),
    created_at          timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS artifact_specs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id            uuid REFERENCES jobs(id),
    revision_number   int DEFAULT 1,
    is_provisional    boolean DEFAULT true,
    spec_data         jsonb NOT NULL,
    confidence        float,
    completeness      float,
    status            text DEFAULT 'provisional',
    promoted_at       timestamptz,
    created_at        timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS artifacts (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              uuid REFERENCES jobs(id),
    spec_id             uuid REFERENCES artifact_specs(id),
    artifact_type       text,
    role                text DEFAULT 'draft',
    parent_artifact_id  uuid REFERENCES artifacts(id),
    asset_id            uuid REFERENCES assets(id),
    version_number      int DEFAULT 1,
    status              text DEFAULT 'created',
    created_at          timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deliveries (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          uuid REFERENCES jobs(id),
    artifact_id     uuid REFERENCES artifacts(id),
    destination     text,
    delivered_at    timestamptz,
    status          text DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS policy_logs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id     uuid,
    job_id          uuid REFERENCES jobs(id),
    client_id       uuid REFERENCES clients(id),
    capability      text,
    action          text NOT NULL,
    gate            text NOT NULL,
    reason          text NOT NULL,
    constraints     jsonb DEFAULT '{}'::jsonb,
    evaluated_at    timestamptz DEFAULT now()
);

-- Migrate existing policy_logs tables from old schema to new.
-- Safe to re-run: ADD COLUMN IF NOT EXISTS is idempotent.
ALTER TABLE policy_logs ADD COLUMN IF NOT EXISTS decision_id uuid;
ALTER TABLE policy_logs ADD COLUMN IF NOT EXISTS client_id uuid REFERENCES clients(id);
ALTER TABLE policy_logs ADD COLUMN IF NOT EXISTS capability text;
ALTER TABLE policy_logs ADD COLUMN IF NOT EXISTS gate text;
ALTER TABLE policy_logs ADD COLUMN IF NOT EXISTS constraints jsonb DEFAULT '{}'::jsonb;
-- Drop columns from old schema that no longer exist in the contract.
ALTER TABLE policy_logs DROP COLUMN IF EXISTS outcome;
ALTER TABLE policy_logs DROP COLUMN IF EXISTS context;
-- Ensure NOT NULL on columns that may have been nullable in the old schema.
-- Backfill NULLs first so ALTER doesn't fail on existing rows.
UPDATE policy_logs SET gate = 'unknown' WHERE gate IS NULL;
UPDATE policy_logs SET reason = '' WHERE reason IS NULL;
ALTER TABLE policy_logs ALTER COLUMN gate SET NOT NULL;
ALTER TABLE policy_logs ALTER COLUMN reason SET NOT NULL;

CREATE TABLE IF NOT EXISTS feedback (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id                  uuid REFERENCES jobs(id),
    artifact_id             uuid REFERENCES artifacts(id),
    client_id               uuid REFERENCES clients(id),
    -- Feedback state machine (§29.5)
    feedback_status         text DEFAULT 'awaiting'
        CHECK (feedback_status IN (
            'awaiting', 'explicitly_approved', 'revision_requested',
            'rejected', 'silence_flagged', 'prompted',
            'responded', 'unresponsive'
        )),
    delivered_at            timestamptz,
    feedback_received_at    timestamptz,
    prompted_at             timestamptz,
    silence_window_hours    int DEFAULT 24,
    -- Client feedback
    spec_revision           int,
    options_shown           jsonb,
    selected                text,
    rejected                jsonb,
    feedback_categories     jsonb,
    feedback_richness_level int,
    raw_text                text,
    -- Operator assessment (independent of client)
    operator_rating         int,
    operator_notes          text,
    operator_rated_at       timestamptz,
    -- Drift detection (§15.10)
    anchor_set              boolean DEFAULT false,
    benchmark_source        text,
    -- Derived
    response_time_hours     float,
    created_at              timestamptz DEFAULT now()
);

-- Migrate existing feedback tables: add CHECK constraint on feedback_status.
-- Postgres requires dropping + re-adding if the constraint already exists.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'feedback_feedback_status_check'
    ) THEN
        ALTER TABLE feedback ADD CONSTRAINT feedback_feedback_status_check
            CHECK (feedback_status IN (
                'awaiting', 'explicitly_approved', 'revision_requested',
                'rejected', 'silence_flagged', 'prompted',
                'responded', 'unresponsive'
            ));
    END IF;
END $$;

-- ============================================================================
-- §16.2  KNOWLEDGE 4 TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS knowledge_sources (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       uuid REFERENCES clients(id),
    source_type     text,
    title           text NOT NULL,
    description     text,
    asset_id        uuid REFERENCES assets(id),
    domain          text,
    language        text,
    quality_tier    text,
    status          text DEFAULT 'active',
    created_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_cards (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       uuid REFERENCES knowledge_sources(id),
    client_id       uuid REFERENCES clients(id),
    card_type       text,
    title           text,
    content         text NOT NULL,
    tags            text[],
    domain          text,
    embedding       vector(1536),
    confidence      float,
    status          text DEFAULT 'active',
    created_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS exemplars (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id         uuid REFERENCES artifacts(id),
    client_id           uuid REFERENCES clients(id),
    artifact_family     text,
    artifact_type       text,
    approval_quality    text,
    style_tags          text[],
    summary             text,
    status              text DEFAULT 'active',
    created_at          timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outcome_memory (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id                  uuid REFERENCES jobs(id),
    artifact_id             uuid REFERENCES artifacts(id),
    client_id               uuid REFERENCES clients(id),
    first_pass_approved     boolean,
    revision_count          int DEFAULT 0,
    accepted_as_on_brand    boolean,
    human_feedback_summary  text,
    cost_summary            jsonb,
    quality_summary         jsonb,
    promote_to_exemplar     boolean DEFAULT false,
    created_at              timestamptz DEFAULT now()
);

-- ============================================================================
-- §16.3  INFRASTRUCTURE 2 TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS visual_lineage (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              uuid REFERENCES jobs(id),
    artifact_id         uuid REFERENCES artifacts(id),
    asset_id            uuid REFERENCES assets(id),
    role                text NOT NULL,
    selection_reason    text,
    created_at          timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system_state (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    version                 text NOT NULL,
    change_type             text NOT NULL,
    change_description      text NOT NULL,
    changed_by              text NOT NULL,
    previous_state          jsonb,
    promoted_from_experiment text,
    created_at              timestamptz DEFAULT now()
);

-- ============================================================================
-- DOCUMENT SETS 2 TABLES (tech scout injection)
-- ============================================================================

CREATE TABLE IF NOT EXISTS document_sets (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       uuid REFERENCES clients(id),
    name            text NOT NULL,
    description     text,
    is_default      boolean DEFAULT false,
    status          text DEFAULT 'active',
    created_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_set_members (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_set_id     uuid REFERENCES document_sets(id) ON DELETE CASCADE,
    knowledge_card_id   uuid REFERENCES knowledge_cards(id) ON DELETE CASCADE,
    added_at            timestamptz DEFAULT now(),
    UNIQUE (document_set_id, knowledge_card_id)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Speed up common FK lookups
CREATE INDEX IF NOT EXISTS idx_jobs_client_id ON jobs(client_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_artifact_specs_job_id ON artifact_specs(job_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_job_id ON artifacts(job_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_spec_id ON artifacts(spec_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_parent ON artifacts(parent_artifact_id);
CREATE INDEX IF NOT EXISTS idx_assets_client_id ON assets(client_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_job_id ON deliveries(job_id);
CREATE INDEX IF NOT EXISTS idx_policy_logs_job_id ON policy_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_policy_logs_client_id ON policy_logs(client_id);
CREATE INDEX IF NOT EXISTS idx_policy_logs_gate ON policy_logs(gate);
CREATE INDEX IF NOT EXISTS idx_feedback_job_id ON feedback(job_id);
CREATE INDEX IF NOT EXISTS idx_feedback_client_id ON feedback(client_id);
CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(feedback_status);
CREATE INDEX IF NOT EXISTS idx_knowledge_cards_client_id ON knowledge_cards(client_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_cards_source_id ON knowledge_cards(source_id);
CREATE INDEX IF NOT EXISTS idx_exemplars_client_id ON exemplars(client_id);
CREATE INDEX IF NOT EXISTS idx_outcome_memory_job_id ON outcome_memory(job_id);
CREATE INDEX IF NOT EXISTS idx_outcome_memory_client_id ON outcome_memory(client_id);
CREATE INDEX IF NOT EXISTS idx_visual_lineage_job_id ON visual_lineage(job_id);
CREATE INDEX IF NOT EXISTS idx_visual_lineage_asset_id ON visual_lineage(asset_id);
CREATE INDEX IF NOT EXISTS idx_document_set_members_set_id ON document_set_members(document_set_id);
CREATE INDEX IF NOT EXISTS idx_document_set_members_card_id ON document_set_members(knowledge_card_id);

-- pgvector indexes for similarity search
CREATE INDEX IF NOT EXISTS idx_assets_visual_embedding ON assets USING ivfflat (visual_embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX IF NOT EXISTS idx_knowledge_cards_embedding ON knowledge_cards USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- System health: latest state + counts
CREATE OR REPLACE VIEW v_system_health AS
SELECT
    (SELECT version FROM system_state ORDER BY created_at DESC LIMIT 1) AS current_version,
    (SELECT count(*) FROM clients WHERE status = 'active') AS active_clients,
    (SELECT count(*) FROM jobs WHERE status NOT IN ('completed', 'failed')) AS active_jobs,
    (SELECT count(*) FROM jobs WHERE completed_at >= now() - interval '24 hours') AS jobs_completed_24h,
    (SELECT coalesce(sum((production_trace->>'total_cost_usd')::numeric), 0)
       FROM jobs
      WHERE completed_at >= now() - interval '24 hours') AS cost_24h_usd;

-- Client health: per-client summary
CREATE OR REPLACE VIEW v_client_health AS
SELECT
    c.id AS client_id,
    c.name AS client_name,
    count(DISTINCT j.id) AS total_jobs,
    count(DISTINCT j.id) FILTER (WHERE j.status = 'completed') AS completed_jobs,
    count(DISTINCT f.id) FILTER (WHERE f.feedback_status = 'explicitly_approved') AS approvals,
    count(DISTINCT f.id) FILTER (WHERE f.feedback_status = 'revision_requested') AS revision_requests,
    count(DISTINCT f.id) FILTER (
        WHERE f.feedback_status NOT IN ('silence_flagged', 'unresponsive')
          AND f.anchor_set = false
          AND f.feedback_status IS NOT NULL
    ) AS actionable_feedback_count,
    CASE
        WHEN count(DISTINCT f.id) > 0
        THEN round(
            count(DISTINCT f.id) FILTER (
                WHERE f.feedback_status NOT IN ('silence_flagged', 'unresponsive', 'awaiting')
            )::numeric
            / count(DISTINCT f.id)::numeric * 100, 1
        )
        ELSE 0
    END AS feedback_collection_rate_pct
FROM clients c
LEFT JOIN jobs j ON j.client_id = c.id
LEFT JOIN feedback f ON f.client_id = c.id
GROUP BY c.id, c.name;

-- Feedback quality: EXCLUDES anchor_set AND silence_flagged/unresponsive (anti-drift #13, #56)
CREATE OR REPLACE VIEW v_feedback_quality AS
SELECT
    f.client_id,
    c.name AS client_name,
    count(*) AS total_feedback,
    count(*) FILTER (WHERE f.feedback_status = 'explicitly_approved') AS approved,
    count(*) FILTER (WHERE f.feedback_status = 'revision_requested') AS revision_requested,
    count(*) FILTER (WHERE f.feedback_status = 'rejected') AS rejected,
    round(
        (avg(f.operator_rating) FILTER (WHERE f.operator_rating IS NOT NULL))::numeric, 2
    ) AS avg_operator_rating,
    round(
        (avg(f.response_time_hours) FILTER (WHERE f.response_time_hours IS NOT NULL))::numeric, 2
    ) AS avg_response_hours
FROM feedback f
JOIN clients c ON c.id = f.client_id
WHERE f.anchor_set = false
  AND f.feedback_status NOT IN ('silence_flagged', 'unresponsive')
GROUP BY f.client_id, c.name;

-- ============================================================================
-- FEEDBACK STATE MACHINE TRIGGER (§29.5)
-- ============================================================================
-- Auto-set delivered_at when feedback_status transitions to 'awaiting'.
-- Silence detection (awaiting → silence_flagged after 24h) is handled by
-- a periodic check function, not a per-row trigger (Postgres triggers cannot
-- fire on elapsed time). See feedback_check_silence() below.

-- Trigger: set delivered_at on insert when status is 'awaiting'
CREATE OR REPLACE FUNCTION feedback_on_insert()
RETURNS trigger AS $$
BEGIN
    IF NEW.feedback_status = 'awaiting' AND NEW.delivered_at IS NULL THEN
        NEW.delivered_at := now();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_feedback_on_insert ON feedback;
CREATE TRIGGER trg_feedback_on_insert
    BEFORE INSERT ON feedback
    FOR EACH ROW
    EXECUTE FUNCTION feedback_on_insert();

-- Trigger: validate state transitions and set timestamps on update
CREATE OR REPLACE FUNCTION feedback_on_update()
RETURNS trigger AS $$
DECLARE
    valid boolean := false;
BEGIN
    -- Allow same-state updates (idempotent)
    IF NEW.feedback_status = OLD.feedback_status THEN
        RETURN NEW;
    END IF;

    -- Valid transitions (§29.5):
    --   awaiting → explicitly_approved | revision_requested | rejected | silence_flagged
    --   silence_flagged → prompted
    --   prompted → responded | unresponsive
    CASE OLD.feedback_status
        WHEN 'awaiting' THEN
            valid := NEW.feedback_status IN (
                'explicitly_approved', 'revision_requested', 'rejected', 'silence_flagged'
            );
        WHEN 'silence_flagged' THEN
            valid := NEW.feedback_status = 'prompted';
        WHEN 'prompted' THEN
            valid := NEW.feedback_status IN ('responded', 'unresponsive');
        ELSE
            valid := false;
    END CASE;

    IF NOT valid THEN
        RAISE EXCEPTION 'Invalid feedback transition: % → %',
            OLD.feedback_status, NEW.feedback_status;
    END IF;

    -- Set timestamps for specific transitions
    IF NEW.feedback_status IN ('explicitly_approved', 'revision_requested', 'rejected', 'responded') THEN
        NEW.feedback_received_at := coalesce(NEW.feedback_received_at, now());
        IF NEW.delivered_at IS NOT NULL THEN
            NEW.response_time_hours := extract(EPOCH FROM (now() - NEW.delivered_at)) / 3600.0;
        END IF;
    END IF;

    IF NEW.feedback_status = 'prompted' THEN
        NEW.prompted_at := coalesce(NEW.prompted_at, now());
    END IF;

    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add updated_at column to feedback if not present (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'feedback' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE feedback ADD COLUMN updated_at timestamptz DEFAULT now();
    END IF;
END $$;

DROP TRIGGER IF EXISTS trg_feedback_on_update ON feedback;
CREATE TRIGGER trg_feedback_on_update
    BEFORE UPDATE ON feedback
    FOR EACH ROW
    EXECUTE FUNCTION feedback_on_update();

-- Function to flag stale awaiting feedback as silence_flagged.
-- Called periodically (e.g. via cron or application timer).
CREATE OR REPLACE FUNCTION feedback_check_silence()
RETURNS int AS $$
DECLARE
    flagged_count int;
BEGIN
    UPDATE feedback
       SET feedback_status = 'silence_flagged'
     WHERE feedback_status = 'awaiting'
       AND delivered_at IS NOT NULL
       AND delivered_at < now() - (silence_window_hours || ' hours')::interval;

    GET DIAGNOSTICS flagged_count = ROW_COUNT;
    RETURN flagged_count;
END;
$$ LANGUAGE plpgsql;

-- Auto-update updated_at on jobs table
CREATE OR REPLACE FUNCTION jobs_set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_jobs_updated_at ON jobs;
CREATE TRIGGER trg_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION jobs_set_updated_at();

-- ============================================================================
-- SEED: initial system_state row
-- ============================================================================
INSERT INTO system_state (version, change_type, change_description, changed_by)
SELECT '0.1.0', 'session_ship', 'S10a: core tables created', 'operator'
WHERE NOT EXISTS (
    SELECT 1 FROM system_state WHERE version = '0.1.0' AND change_type = 'session_ship'
);
