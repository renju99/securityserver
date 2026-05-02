BEGIN;

ALTER TABLE IF EXISTS attendance
    ADD COLUMN IF NOT EXISTS source VARCHAR(32) NOT NULL DEFAULT 'app',
    ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'approved',
    ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS approved_by INTEGER REFERENCES employees(id),
    ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rejected_by INTEGER REFERENCES employees(id),
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
    ADD COLUMN IF NOT EXISTS break_minutes INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS overtime_minutes INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS work_context JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS attendance_policy_rules (
    id SERIAL PRIMARY KEY,
    site_id INTEGER REFERENCES sites(id) ON DELETE CASCADE,
    shift_id INTEGER REFERENCES shifts(id) ON DELETE CASCADE,
    overtime_after_minutes INTEGER NOT NULL DEFAULT 480,
    paid_break_minutes INTEGER NOT NULL DEFAULT 0,
    unpaid_break_minutes INTEGER NOT NULL DEFAULT 0,
    max_shift_minutes INTEGER,
    require_approval_manual BOOLEAN NOT NULL DEFAULT FALSE,
    require_approval_offline BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by INTEGER REFERENCES employees(id),
    updated_by INTEGER REFERENCES employees(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_policy_rules_scope
    ON attendance_policy_rules (COALESCE(site_id, -1), COALESCE(shift_id, -1))
    WHERE is_active = TRUE;

CREATE TABLE IF NOT EXISTS attendance_approval_logs (
    id BIGSERIAL PRIMARY KEY,
    attendance_id INTEGER NOT NULL REFERENCES attendance(id) ON DELETE CASCADE,
    action VARCHAR(16) NOT NULL CHECK (action IN ('submitted', 'approved', 'rejected')),
    actor_id INTEGER REFERENCES employees(id),
    reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    site_id INTEGER REFERENCES sites(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by INTEGER REFERENCES employees(id),
    updated_by INTEGER REFERENCES employees(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE IF EXISTS roster_assignments
    ADD COLUMN IF NOT EXISTS acceptance_status VARCHAR(16) NOT NULL DEFAULT 'assigned',
    ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS accepted_by INTEGER REFERENCES employees(id),
    ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
    ADD COLUMN IF NOT EXISTS notified_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_attendance_status_checkin ON attendance(status, check_in_time DESC);
CREATE INDEX IF NOT EXISTS idx_roster_assignments_acceptance ON roster_assignments(employee_id, work_date DESC, acceptance_status);

COMMIT;
