-- Normalize timestamp columns to timestamptz for UTC-at-boundary handling.
-- Assumes existing values are UTC.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'attendance' AND column_name = 'check_in_time'
    ) THEN
        ALTER TABLE attendance
            ALTER COLUMN check_in_time TYPE timestamptz USING check_in_time AT TIME ZONE 'UTC';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'attendance' AND column_name = 'check_out_time'
    ) THEN
        ALTER TABLE attendance
            ALTER COLUMN check_out_time TYPE timestamptz USING check_out_time AT TIME ZONE 'UTC';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'attendance' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE attendance
            ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
    END IF;
END $$;

-- live_logs may already be partitioned by timestamp; altering a partition key type is not allowed.
-- Keep existing type for live_logs to avoid blocking deployments.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'geo_fence_alerts' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE geo_fence_alerts
            ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'geo_fence_alerts' AND column_name = 'resolved_at'
    ) THEN
        ALTER TABLE geo_fence_alerts
            ALTER COLUMN resolved_at TYPE timestamptz USING resolved_at AT TIME ZONE 'UTC';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'employees' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE employees
            ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC';
    END IF;
END $$;

COMMIT;
