CREATE TABLE IF NOT EXISTS odoo_instances (
    id SERIAL PRIMARY KEY,
    instance_code VARCHAR(32) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    base_url TEXT NOT NULL,
    db_name VARCHAR(128) NOT NULL,
    username VARCHAR(128) NOT NULL,
    password TEXT NOT NULL,
    employee_lookup_field VARCHAR(32) NOT NULL DEFAULT 'barcode',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS staff_odoo_routing (
    staff_id VARCHAR(50) PRIMARY KEY,
    instance_code VARCHAR(32) NOT NULL REFERENCES odoo_instances(instance_code),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS attendance_sync_mapping (
    attendance_id INTEGER PRIMARY KEY REFERENCES attendance(id) ON DELETE CASCADE,
    instance_code VARCHAR(32) NOT NULL REFERENCES odoo_instances(instance_code),
    odoo_attendance_id BIGINT,
    synced_check_in_at TIMESTAMPTZ,
    synced_check_out_at TIMESTAMPTZ,
    last_status VARCHAR(24) NOT NULL DEFAULT 'pending',
    last_error TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS attendance_sync_outbox (
    id BIGSERIAL PRIMARY KEY,
    attendance_id INTEGER NOT NULL REFERENCES attendance(id) ON DELETE CASCADE,
    staff_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(16) NOT NULL CHECK (event_type IN ('check_in', 'check_out')),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    route_instance_code VARCHAR(32),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attendance_sync_outbox_status_retry
    ON attendance_sync_outbox (status, next_retry_at, id);

CREATE INDEX IF NOT EXISTS idx_attendance_sync_outbox_attendance
    ON attendance_sync_outbox (attendance_id, event_type);

INSERT INTO odoo_instances (instance_code, name, base_url, db_name, username, password, employee_lookup_field, is_active)
VALUES
    ('dxb', 'Dubai Odoo', 'https://ops.dxb.berkeleyuae.com', 'odoo', 'integration@berkeleyuae.com', 'CHANGE_ME', 'code', true),
    ('auh', 'Abu Dhabi Odoo', 'https://ops.auh.berkeleyuae.com', 'odoo', 'integration@berkeleyuae.com', 'CHANGE_ME', 'barcode', true)
ON CONFLICT (instance_code) DO NOTHING;
