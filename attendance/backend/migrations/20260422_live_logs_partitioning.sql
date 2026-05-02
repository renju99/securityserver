-- Monthly partitioning for high-write tables.
-- Uses dynamic partition creation and a DEFAULT partition so historical rows do not fail migration.

BEGIN;

-- 1) Create partitioned parent for live_logs
CREATE TABLE IF NOT EXISTS live_logs_p (
    id bigint generated always as identity,
    employee_id integer NOT NULL,
    current_coords geography(Point,4326) NOT NULL,
    timestamp timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- 2) Ensure fallback partition exists for out-of-range historical rows.
CREATE TABLE IF NOT EXISTS live_logs_p_default PARTITION OF live_logs_p DEFAULT;

-- 3) Create rolling monthly partitions around current month.
DO $$
DECLARE
    i integer;
    month_start timestamptz;
    month_end timestamptz;
    part_name text;
BEGIN
    FOR i IN -2..6 LOOP
        month_start := date_trunc('month', now()) + (i || ' month')::interval;
        month_end := month_start + interval '1 month';
        part_name := format('live_logs_p_%s', to_char(month_start, 'YYYY_MM'));
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF live_logs_p FOR VALUES FROM (%L) TO (%L)',
            part_name,
            month_start,
            month_end
        );
    END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS idx_live_logs_p_employee_time ON live_logs_p (employee_id, timestamp DESC);

-- 4) One-time copy (if original table exists and has rows)
INSERT INTO live_logs_p (employee_id, current_coords, timestamp)
SELECT employee_id, current_coords, timestamp
FROM live_logs
ON CONFLICT DO NOTHING;

-- 5) Swap names once validated
ALTER TABLE IF EXISTS live_logs RENAME TO live_logs_old;
ALTER TABLE live_logs_p RENAME TO live_logs;

COMMIT;

-- Cleanup strategy after migration:
-- DROP TABLE IF EXISTS live_logs_old;
-- Drop old partitions by month instead of DELETE.
