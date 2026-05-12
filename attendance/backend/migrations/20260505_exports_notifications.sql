-- Scheduled attendance exports (email + optional SFTP) and optional SMS target on employees.

CREATE TABLE IF NOT EXISTS scheduled_report_exports (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by INTEGER REFERENCES employees(id),
    name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    run_every_minutes INTEGER NOT NULL DEFAULT 1440 CHECK (run_every_minutes >= 15 AND run_every_minutes <= 10080),
    data_source VARCHAR(16) NOT NULL DEFAULT 'app' CHECK (data_source IN ('app', 'biometrics')),
    role_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    site_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    shift_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    department TEXT NOT NULL DEFAULT '',
    date_range_preset VARCHAR(32) NOT NULL DEFAULT 'last_30_days'
        CHECK (date_range_preset IN ('last_7_days', 'last_30_days', 'last_calendar_month', 'month_to_date')),
    export_format VARCHAR(16) NOT NULL DEFAULT 'csv' CHECK (export_format IN ('csv', 'xlsx', 'fixed_width')),
    fixed_width_profile VARCHAR(32) NOT NULL DEFAULT 'payroll_v1',
    delivery_emails TEXT,
    sftp_upload BOOLEAN NOT NULL DEFAULT false,
    next_run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_run_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_report_exports_org_next
    ON scheduled_report_exports (organization_id, enabled, next_run_at);

ALTER TABLE employees ADD COLUMN IF NOT EXISTS phone_e164 VARCHAR(24);
