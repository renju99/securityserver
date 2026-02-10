-- Migration: Create missing incident_report_tag_rel table
-- Version: 18.0.1.0.4
-- Date: 2025-11-01
-- Purpose: Fix RPC_ERROR for incident.report model by creating the missing many2many relation table

-- Create the incident_report_tag_rel table if it doesn't exist
CREATE TABLE IF NOT EXISTS incident_report_tag_rel (
    incident_id INTEGER NOT NULL REFERENCES incident_report(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES incident_tag(id) ON DELETE CASCADE,
    PRIMARY KEY (incident_id, tag_id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS incident_report_tag_rel_incident_id_idx ON incident_report_tag_rel (incident_id);
CREATE INDEX IF NOT EXISTS incident_report_tag_rel_tag_id_idx ON incident_report_tag_rel (tag_id);

-- Log the migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 18.0.1.0.4: Created incident_report_tag_rel table';
END $$;











