-- Advanced scheduled exports: delivery options, schedules, webhooks, S3, run history, audit, templates.

ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS delivery_cc_emails TEXT;
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS delivery_bcc_emails TEXT;
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS reply_to TEXT;
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS email_subject TEXT;
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS email_body_text TEXT;
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS send_html BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS schedule_timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Dubai';
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS schedule_mode VARCHAR(24) NOT NULL DEFAULT 'interval'
    CHECK (schedule_mode IN ('interval', 'cron', 'daily_at'));
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS cron_expression TEXT;
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS daily_at_time VARCHAR(8);
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS pause_until TIMESTAMPTZ;
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS max_export_rows INTEGER
    CHECK (max_export_rows IS NULL OR (max_export_rows >= 1 AND max_export_rows <= 500000));
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS webhook_url TEXT;
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS webhook_secret TEXT;
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS webhook_signing_header VARCHAR(64) NOT NULL DEFAULT 'X-Webhook-Signature';
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS s3_upload BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS alert_emails_on_failure TEXT;
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS retry_backoff_minutes INTEGER NOT NULL DEFAULT 15
    CHECK (retry_backoff_minutes >= 5 AND retry_backoff_minutes <= 1440);
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS consecutive_failures INTEGER NOT NULL DEFAULT 0
    CHECK (consecutive_failures >= 0);
ALTER TABLE scheduled_report_exports ADD COLUMN IF NOT EXISTS encrypt_attachment_pgp BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS scheduled_report_export_runs (
    id SERIAL PRIMARY KEY,
    scheduled_export_id INTEGER NOT NULL REFERENCES scheduled_report_exports(id) ON DELETE CASCADE,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    triggered_by VARCHAR(32) NOT NULL DEFAULT 'cron',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(24) NOT NULL DEFAULT 'running',
    row_count INTEGER,
    truncated BOOLEAN NOT NULL DEFAULT false,
    file_name TEXT,
    email_ok BOOLEAN,
    sftp_ok BOOLEAN,
    s3_ok BOOLEAN,
    webhook_ok BOOLEAN,
    error_message TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_sched_export_runs_schedule ON scheduled_report_export_runs (scheduled_export_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sched_export_runs_org ON scheduled_report_export_runs (organization_id, started_at DESC);

CREATE TABLE IF NOT EXISTS scheduled_report_export_audit (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    scheduled_export_id INTEGER REFERENCES scheduled_report_exports(id) ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sched_export_audit_org ON scheduled_report_export_audit (organization_id, created_at DESC);

CREATE TABLE IF NOT EXISTS scheduled_report_export_templates (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, name)
);

CREATE INDEX IF NOT EXISTS idx_sched_export_templates_org ON scheduled_report_export_templates (organization_id);
