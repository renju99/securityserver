-- Migration: Rename washrooms -> locations, washroom_id -> location_id
-- Run this on an existing DB that has washrooms. For fresh installs use init.sql.

BEGIN;

-- 1. Create locations table (copy of washrooms structure)
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE,
    building VARCHAR(100),
    floor VARCHAR(50),
    room VARCHAR(50),
    qr_token VARCHAR(255) UNIQUE NOT NULL,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Copy data from washrooms to locations (only if washrooms exists and has rows)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'washrooms') THEN
        INSERT INTO locations (id, project_id, name, code, building, floor, room, qr_token, lat, lng, active, created_at)
        SELECT id, project_id, name, code, building, floor, room, qr_token, lat, lng, active, created_at
        FROM washrooms
        ON CONFLICT (id) DO NOTHING;
        PERFORM setval(pg_get_serial_sequence('locations', 'id'), (SELECT COALESCE(MAX(id), 1) FROM locations));
    END IF;
END $$;

-- 3. Add location_id to schedules if not exists, backfill, then drop washroom_id (only if washroom_id exists)
ALTER TABLE schedules ADD COLUMN IF NOT EXISTS location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'schedules' AND column_name = 'washroom_id') THEN
        UPDATE schedules s SET location_id = s.washroom_id WHERE s.washroom_id IS NOT NULL AND s.location_id IS NULL;
        ALTER TABLE schedules DROP CONSTRAINT IF EXISTS schedules_washroom_id_fkey;
        ALTER TABLE schedules DROP COLUMN washroom_id;
    END IF;
END $$;

-- 4. Add location_id to attendance if not exists, backfill, then drop washroom_id (only if washroom_id exists)
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS location_id INTEGER REFERENCES locations(id);
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'attendance' AND column_name = 'washroom_id') THEN
        UPDATE attendance a SET location_id = a.washroom_id WHERE a.washroom_id IS NOT NULL AND a.location_id IS NULL;
        ALTER TABLE attendance DROP CONSTRAINT IF EXISTS attendance_washroom_id_fkey;
        ALTER TABLE attendance DROP COLUMN washroom_id;
    END IF;
END $$;

-- 5. Add location_id to reports if not exists, backfill, then drop washroom_id (only if washroom_id exists)
ALTER TABLE reports ADD COLUMN IF NOT EXISTS location_id INTEGER REFERENCES locations(id);
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'reports' AND column_name = 'washroom_id') THEN
        UPDATE reports r SET location_id = r.washroom_id WHERE r.washroom_id IS NOT NULL AND r.location_id IS NULL;
        ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_washroom_id_fkey;
        ALTER TABLE reports DROP COLUMN washroom_id;
    END IF;
END $$;

-- 6. Indexes
DROP INDEX IF EXISTS idx_attendance_washroom;
CREATE INDEX IF NOT EXISTS idx_attendance_location ON attendance(location_id);
DROP INDEX IF EXISTS idx_washrooms_qr;
CREATE INDEX IF NOT EXISTS idx_locations_qr ON locations(qr_token);

-- 7. Drop old washrooms table
DROP TABLE IF EXISTS washrooms;

COMMIT;
