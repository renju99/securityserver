-- Manual SQL script to add missing conflict detection columns to guard_shift table
-- Run this script if automatic migration fails
-- Execute as PostgreSQL superuser or database owner

-- Add has_conflict column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='guard_shift' AND column_name='has_conflict'
    ) THEN
        ALTER TABLE guard_shift ADD COLUMN has_conflict BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added has_conflict column';
    ELSE
        RAISE NOTICE 'has_conflict column already exists';
    END IF;
END $$;

-- Add conflict_type column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='guard_shift' AND column_name='conflict_type'
    ) THEN
        ALTER TABLE guard_shift ADD COLUMN conflict_type VARCHAR;
        RAISE NOTICE 'Added conflict_type column';
    ELSE
        RAISE NOTICE 'conflict_type column already exists';
    END IF;
END $$;

-- Add conflict_details column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='guard_shift' AND column_name='conflict_details'
    ) THEN
        ALTER TABLE guard_shift ADD COLUMN conflict_details TEXT;
        RAISE NOTICE 'Added conflict_details column';
    ELSE
        RAISE NOTICE 'conflict_details column already exists';
    END IF;
END $$;

-- Initialize default values for existing records
UPDATE guard_shift 
SET has_conflict = FALSE, 
    conflict_type = NULL, 
    conflict_details = NULL
WHERE has_conflict IS NULL;

-- Verify columns were added
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name='guard_shift' 
  AND column_name IN ('has_conflict', 'conflict_type', 'conflict_details')
ORDER BY column_name;











