ALTER TABLE biometric_logs
    ADD COLUMN IF NOT EXISTS process_status VARCHAR(24) NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS process_attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS process_last_error TEXT,
    ADD COLUMN IF NOT EXISTS attendance_id INTEGER REFERENCES attendance(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS attendance_event_type VARCHAR(16);

UPDATE biometric_logs
SET process_status = 'succeeded',
    processed_at = COALESCE(processed_at, created_at, NOW()),
    process_last_error = COALESCE(process_last_error, 'Existing biometric history marked processed during retry migration')
WHERE attendance_id IS NULL
  AND process_attempts = 0
  AND process_status = 'pending';

WITH duplicate_logs AS (
    SELECT id,
           row_number() OVER (
               PARTITION BY device_id, staff_id, timestamp
               ORDER BY id ASC
           ) AS rn
    FROM biometric_logs
    WHERE device_id IS NOT NULL
      AND staff_id IS NOT NULL
      AND timestamp IS NOT NULL
)
DELETE FROM biometric_logs b
USING duplicate_logs d
WHERE b.id = d.id
  AND d.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_biometric_logs_device_staff_timestamp_unique
    ON biometric_logs (device_id, staff_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_biometric_logs_process_retry
    ON biometric_logs (process_status, next_retry_at, timestamp, id);

CREATE INDEX IF NOT EXISTS idx_biometric_logs_attendance
    ON biometric_logs (attendance_id);
