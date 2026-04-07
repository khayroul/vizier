-- extended.sql: Extended Postgres tables for BizOps and Steward.
-- Created by S16. All statements use CREATE TABLE IF NOT EXISTS for idempotent re-runs.
-- Re-running this file must not error or lose data.
-- Depends on: core.sql (clients, assets tables must exist first).

-- ============================================================================
-- §16.4  BUSINESS OPERATIONS (3 tables)
-- ============================================================================

CREATE TABLE IF NOT EXISTS invoices (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       uuid REFERENCES clients(id),
    job_ids         uuid[],
    amount_rm       decimal(10,2) NOT NULL,
    currency        text DEFAULT 'MYR',
    description     text,
    issued_at       timestamptz DEFAULT now(),
    due_at          timestamptz,
    paid_at         timestamptz,
    status          text DEFAULT 'draft',
    invoice_number  text,
    pdf_asset_id    uuid REFERENCES assets(id),
    notes           text
);

CREATE TABLE IF NOT EXISTS payments (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id       uuid REFERENCES invoices(id),
    client_id        uuid REFERENCES clients(id),
    amount_rm        decimal(10,2) NOT NULL,
    payment_method   text,
    reference_number text,
    received_at      timestamptz DEFAULT now(),
    notes            text
);

CREATE TABLE IF NOT EXISTS pipeline (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           uuid REFERENCES clients(id),
    prospect_name       text,
    stage               text DEFAULT 'lead',
    estimated_value_rm  decimal(10,2),
    proposal_asset_id   uuid REFERENCES assets(id),
    next_followup_at    timestamptz,
    source              text,
    notes               text,
    created_at          timestamptz DEFAULT now(),
    updated_at          timestamptz DEFAULT now()
);

-- Invoice number sequence for VIZ-YYYY-NNN format
CREATE SEQUENCE IF NOT EXISTS invoice_number_seq;

-- ============================================================================
-- §16.4a  STEWARD — PERSONAL ASSISTANT (6 tables)
-- ============================================================================

CREATE TABLE IF NOT EXISTS steward_inbox (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_input         text NOT NULL,
    input_type        text DEFAULT 'text',
    source_message_id text,
    processed         boolean DEFAULT false,
    processed_at      timestamptz,
    created_at        timestamptz DEFAULT now()
);

-- steward_projects before steward_tasks (FK dependency)
CREATE TABLE IF NOT EXISTS steward_projects (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title                   text NOT NULL,
    objective               text NOT NULL,
    domain                  text,
    status                  text DEFAULT 'active',
    decomposed              boolean DEFAULT false,
    decomposition_approved  boolean DEFAULT false,
    horizon                 text DEFAULT 'project',
    parent_project_id       uuid REFERENCES steward_projects(id),
    total_tasks             int DEFAULT 0,
    completed_tasks         int DEFAULT 0,
    created_at              timestamptz DEFAULT now(),
    updated_at              timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS steward_tasks (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inbox_id          uuid REFERENCES steward_inbox(id),
    project_id        uuid REFERENCES steward_projects(id),
    title             text NOT NULL,
    description       text,
    next_action       boolean DEFAULT false,
    context           text,
    energy_level      text,
    time_estimate_min int,
    domain            text,
    status            text DEFAULT 'active',
    waiting_for       text,
    due_date          date,
    defer_until       date,
    completed_at      timestamptz,
    completion_note   text,
    recurrence        text,
    recurrence_anchor text,
    streak_count      int DEFAULT 0,
    streak_last_date  date,
    created_at        timestamptz DEFAULT now(),
    updated_at        timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS steward_reviews (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    review_type       text NOT NULL,
    review_date       date NOT NULL,
    domain_scores     jsonb,
    completion_stats  jsonb,
    neglected_domains text[],
    thriving_domains  text[],
    stuck_projects    jsonb,
    energy_reflection text,
    wins              text[],
    adjustments       text[],
    created_at        timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS steward_health_log (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    log_date            date NOT NULL UNIQUE,
    sleep_hours         float,
    sleep_quality       text,
    bedtime             timestamptz,
    waketime            timestamptz,
    steps               int,
    active_calories     int,
    exercise_minutes    int,
    resting_heart_rate  int,
    mindful_minutes     int,
    raw_data            jsonb,
    created_at          timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS steward_learning (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type       text NOT NULL,
    resource_title      text NOT NULL,
    wisdom_vault_id     text,
    domain              text,
    total_units         int,
    completed_units     int DEFAULT 0,
    unit_type           text DEFAULT 'page',
    status              text DEFAULT 'active',
    takeaways           jsonb,
    last_reviewed_at    timestamptz,
    review_interval_days int DEFAULT 14,
    started_at          timestamptz DEFAULT now(),
    completed_at        timestamptz,
    created_at          timestamptz DEFAULT now(),
    updated_at          timestamptz DEFAULT now()
);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Payment state machine: update invoice status when payment received.
-- Only transitions from 'issued' or 'partial' — never from 'draft'.
-- Overdue is computed on read (status IN ('issued','partial') AND due_at < now()),
-- never stored as a status value.
CREATE OR REPLACE FUNCTION update_invoice_status_on_payment()
RETURNS trigger AS $$
DECLARE
    total_paid decimal(10,2);
    invoice_amount decimal(10,2);
    current_status text;
BEGIN
    SELECT COALESCE(SUM(amount_rm), 0) INTO total_paid
      FROM payments WHERE invoice_id = NEW.invoice_id;

    SELECT amount_rm, status INTO invoice_amount, current_status
      FROM invoices WHERE id = NEW.invoice_id;

    -- Only transition from issued or partial, never from draft
    IF current_status IN ('issued', 'partial') THEN
        IF total_paid >= invoice_amount THEN
            UPDATE invoices SET status = 'paid', paid_at = now()
             WHERE id = NEW.invoice_id;
        ELSE
            UPDATE invoices SET status = 'partial'
             WHERE id = NEW.invoice_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_invoice_on_payment ON payments;
CREATE TRIGGER trg_update_invoice_on_payment
    AFTER INSERT ON payments
    FOR EACH ROW
    EXECUTE FUNCTION update_invoice_status_on_payment();
