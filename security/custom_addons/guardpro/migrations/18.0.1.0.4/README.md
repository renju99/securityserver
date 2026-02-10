# Migration 18.0.1.0.4

## Date
2025-11-01

## Issue
RPC_ERROR on incident.report model due to missing relation table `incident_report_tag_rel`.

### Error Details
```
psycopg2.errors.UndefinedTable: relation "incident_report_tag_rel" does not exist
```

## Root Cause
The many2many relationship between `incident.report` and `incident.tag` requires a database relation table `incident_report_tag_rel`, which was not created during module installation or a previous upgrade.

## Solution
This migration creates the missing relation table with proper foreign key constraints and indexes.

### Files Changed
1. **pre-migration.sql**: Creates the `incident_report_tag_rel` table
2. **post-migration.py**: Verifies table creation and logs results
3. **README.md**: Documentation

## Database Changes

### New Table: incident_report_tag_rel
```sql
CREATE TABLE incident_report_tag_rel (
    incident_id INTEGER NOT NULL REFERENCES incident_report(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES incident_tag(id) ON DELETE CASCADE,
    PRIMARY KEY (incident_id, tag_id)
);
```

### Indexes Created
- `incident_report_tag_rel_incident_id_idx` on `incident_id`
- `incident_report_tag_rel_tag_id_idx` on `tag_id`

## How to Apply

### Option 1: Upgrade Module (Recommended)
```bash
# Update module version in __manifest__.py to 18.0.1.0.4
# Then restart Odoo with upgrade flag
./odoo-bin -u guardpro -d your_database
```

### Option 2: Manual SQL Execution (If upgrade fails)
```bash
# Connect to PostgreSQL
psql -d your_database -U your_user

# Run the migration SQL
\i /path/to/guardpro/migrations/18.0.1.0.4/pre-migration.sql
```

## Verification

After migration, verify the table exists:
```sql
SELECT * FROM information_schema.tables 
WHERE table_name = 'incident_report_tag_rel';
```

## Affected Models
- `incident.report` (tag_ids field)
- `incident.tag`

## Testing
1. Open an incident report in Odoo
2. Add tags to the incident
3. Save and reload - tags should persist
4. No RPC_ERROR should occur

## Rollback
If needed, you can drop the table (data will be lost):
```sql
DROP TABLE IF EXISTS incident_report_tag_rel CASCADE;
```

## Notes
- This migration is safe to run multiple times (uses IF NOT EXISTS)
- Existing data in the table (if any) will be preserved
- Foreign key constraints ensure data integrity











