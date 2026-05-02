ALTER TABLE employees
    ADD COLUMN IF NOT EXISTS face_descriptor JSONB,
    ADD COLUMN IF NOT EXISTS face_enrolled_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS face_enrolled_by INTEGER REFERENCES employees(id),
    ADD COLUMN IF NOT EXISTS face_auth_enabled BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS face_pin_hash TEXT,
    ADD COLUMN IF NOT EXISTS face_failed_attempts INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS face_locked_until TIMESTAMP;

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

UPDATE employees
SET
    face_auth_enabled = COALESCE(face_auth_enabled, TRUE),
    face_failed_attempts = COALESCE(face_failed_attempts, 0)
WHERE face_auth_enabled IS NULL OR face_failed_attempts IS NULL;
