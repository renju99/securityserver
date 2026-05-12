-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- Sites Table
CREATE TABLE IF NOT EXISTS sites (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    location VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Roles Table
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- Permissions Table
CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT
);

-- Role-Permissions Mapping
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER REFERENCES roles(id),
    permission_id INTEGER REFERENCES permissions(id),
    PRIMARY KEY (role_id, permission_id)
);

-- Employees Table (Updated with RBAC and Site)
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    staff_id VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    phone_e164 VARCHAR(24),
    password_hash TEXT,
    department_name VARCHAR(100),
    role_id INTEGER REFERENCES roles(id),
    site_id INTEGER REFERENCES sites(id),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    photo_url VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    face_descriptor JSONB,
    face_enrollment_photo_url TEXT,
    face_enrolled_at TIMESTAMP,
    face_enrolled_by INTEGER REFERENCES employees(id),
    face_auth_enabled BOOLEAN DEFAULT TRUE,
    face_pin_hash TEXT,
    face_failed_attempts INTEGER DEFAULT 0,
    face_locked_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Shifts Table
CREATE TABLE IF NOT EXISTS shifts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS face_auth_events (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    actor_id INTEGER REFERENCES employees(id),
    event_type VARCHAR(64) NOT NULL,
    result VARCHAR(32) NOT NULL DEFAULT 'success',
    similarity NUMERIC,
    threshold NUMERIC,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS kiosk_devices (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    device_key VARCHAR(128) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_employees_site_face_enrolled
ON employees (site_id)
WHERE face_descriptor IS NOT NULL
  AND COALESCE(face_auth_enabled, TRUE) = TRUE
  AND (is_active = TRUE OR is_active IS NULL);

CREATE INDEX IF NOT EXISTS idx_employees_role_site_active
    ON employees (role_id, site_id, is_active);

CREATE INDEX IF NOT EXISTS idx_employees_site_active_staff
    ON employees (site_id, is_active, staff_id);

-- Attendance Table
CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    check_in_time TIMESTAMP,
    check_out_time TIMESTAMP,
    check_in_coords GEOGRAPHY(POINT, 4326),
    check_out_coords GEOGRAPHY(POINT, 4326),
    site_id INTEGER REFERENCES sites(id),
    source VARCHAR(32) NOT NULL DEFAULT 'app',
    status VARCHAR(16) NOT NULL DEFAULT 'approved',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    approved_by INTEGER REFERENCES employees(id),
    rejected_at TIMESTAMPTZ,
    rejected_by INTEGER REFERENCES employees(id),
    rejection_reason TEXT,
    break_minutes INTEGER NOT NULL DEFAULT 0,
    overtime_minutes INTEGER NOT NULL DEFAULT 0,
    work_context JSONB NOT NULL DEFAULT '{}'::jsonb
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

CREATE INDEX IF NOT EXISTS idx_attendance_employee_checkin_desc
    ON attendance (employee_id, check_in_time DESC);

CREATE INDEX IF NOT EXISTS idx_attendance_site_checkin_desc
    ON attendance (site_id, check_in_time DESC);

CREATE INDEX IF NOT EXISTS idx_attendance_open_employee
    ON attendance (employee_id, check_in_time DESC)
    WHERE check_out_time IS NULL;

CREATE INDEX IF NOT EXISTS idx_attendance_open_site
    ON attendance (site_id, check_in_time DESC)
    WHERE check_out_time IS NULL;

CREATE INDEX IF NOT EXISTS idx_attendance_status_checkin
    ON attendance (status, check_in_time DESC);

CREATE INDEX IF NOT EXISTS idx_attendance_sync_outbox_status_retry
    ON attendance_sync_outbox (status, next_retry_at, id);

CREATE INDEX IF NOT EXISTS idx_attendance_sync_outbox_attendance
    ON attendance_sync_outbox (attendance_id, event_type);

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
    action VARCHAR(16) NOT NULL CHECK (action IN ('submitted', 'approved', 'rejected', 'merged', 'split', 'void_duplicate')),
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

CREATE TABLE IF NOT EXISTS geo_fence_alerts (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    site_id INTEGER REFERENCES sites(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    message TEXT,
    status VARCHAR(20) DEFAULT 'active',
    false_positive BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS biometric_devices (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    device_key VARCHAR(100) UNIQUE NOT NULL,
    site_id INTEGER REFERENCES sites(id),
    type VARCHAR(50) DEFAULT 'RA08',
    last_seen TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    ip_address VARCHAR(128),
    port VARCHAR(32),
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS biometric_logs (
    id SERIAL PRIMARY KEY,
    device_id INTEGER REFERENCES biometric_devices(id),
    staff_id VARCHAR(50),
    employee_id INTEGER REFERENCES employees(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    photo_url VARCHAR(255),
    raw_data JSONB,
    process_status VARCHAR(24) NOT NULL DEFAULT 'pending',
    process_attempts INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    process_last_error TEXT,
    attendance_id INTEGER REFERENCES attendance(id) ON DELETE SET NULL,
    attendance_event_type VARCHAR(16),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- LiveLogs Table with Partitioning
CREATE TABLE IF NOT EXISTS live_logs (
    id SERIAL,
    employee_id INTEGER REFERENCES employees(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    current_coords GEOGRAPHY(POINT, 4326),
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Default partition
CREATE TABLE IF NOT EXISTS live_logs_default PARTITION OF live_logs DEFAULT;

CREATE INDEX IF NOT EXISTS idx_live_logs_employee_time
    ON live_logs (employee_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_live_logs_time
    ON live_logs (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_geo_fence_alerts_employee_created
    ON geo_fence_alerts (employee_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_geo_fence_alerts_site_status_created
    ON geo_fence_alerts (site_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_biometric_devices_site_active
    ON biometric_devices (site_id, is_active);

CREATE INDEX IF NOT EXISTS idx_biometric_logs_device_timestamp
    ON biometric_logs (device_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_biometric_logs_staff_timestamp
    ON biometric_logs (staff_id, timestamp DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_biometric_logs_device_staff_timestamp_unique
    ON biometric_logs (device_id, staff_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_biometric_logs_process_retry
    ON biometric_logs (process_status, next_retry_at, timestamp, id);

CREATE INDEX IF NOT EXISTS idx_biometric_logs_attendance
    ON biometric_logs (attendance_id);

-- Initial Seeding
INSERT INTO roles (name) VALUES ('HR Admin'), ('Site Supervisor'), ('Payroll'), ('Finance'), ('Employee') ON CONFLICT DO NOTHING;
INSERT INTO sites (name, location) VALUES ('Dubai South', 'Dubai'), ('Sharjah Industrial', 'Sharjah'), ('Abu Dhabi Central', 'Abu Dhabi') ON CONFLICT DO NOTHING;
INSERT INTO permissions (name) VALUES ('view_live_gps'), ('delete_user'), ('export_payroll'), ('manage_sites') ON CONFLICT DO NOTHING;
INSERT INTO shifts (name, start_time, end_time)
VALUES ('Morning Shift', '08:00', '17:00'), ('Night Shift', '20:00', '05:00')
ON CONFLICT (name) DO NOTHING;
