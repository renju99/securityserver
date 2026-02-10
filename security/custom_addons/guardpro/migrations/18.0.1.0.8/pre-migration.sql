-- Migration: Add sidebar_type field to res_users table
-- Version: 18.0.1.0.8
-- Date: 2025-12-12
-- Purpose: Add sidebar_type field to res_users model to fix AttributeError and UndefinedColumn errors

-- Add the sidebar_type column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'res_users' 
        AND column_name = 'sidebar_type'
    ) THEN
        ALTER TABLE res_users 
        ADD COLUMN sidebar_type VARCHAR DEFAULT 'invisible';
        
        -- Update existing records to have the default value
        UPDATE res_users 
        SET sidebar_type = 'invisible' 
        WHERE sidebar_type IS NULL;
        
        RAISE NOTICE 'Migration 18.0.1.0.8: Added sidebar_type column to res_users table';
    ELSE
        RAISE NOTICE 'Migration 18.0.1.0.8: sidebar_type column already exists, skipping';
    END IF;
END $$;

