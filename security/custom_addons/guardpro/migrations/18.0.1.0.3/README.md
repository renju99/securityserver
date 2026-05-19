# GuardLink Migration 18.0.1.0.3

## Issue Fixed

**Error:** `psycopg2.errors.UndefinedColumn: column guard_shift.has_conflict does not exist`

This error occurred when trying to access guard attendance records because the database schema was missing conflict detection columns that were added to the `guard.shift` model.

## Changes

This migration adds the following columns to the `guard_shift` table:

1. **has_conflict** (Boolean) - Indicates if this shift has scheduling conflicts
2. **conflict_type** (VARCHAR) - Type of conflict: 'overlap', 'rest_period', or 'both'
3. **conflict_details** (Text) - Detailed description of the conflict

## Automatic Migration

The migration will run automatically when you upgrade the module:

### Option 1: Via Odoo UI (Recommended)

1. Log in to Odoo as Administrator
2. Go to **Apps** menu
3. Remove the "Apps" filter to show installed modules
4. Search for "GuardLink"
5. Click the **Upgrade** button

### Option 2: Via Command Line

```bash
# Navigate to Odoo directory
cd /home/ranjith/odoo

# Stop Odoo if running
sudo systemctl stop odoo

# Run upgrade command
./odoo-bin -c /etc/odoo.conf -d YOUR_DATABASE_NAME -u guardpro

# Restart Odoo
sudo systemctl start odoo
```

Replace `YOUR_DATABASE_NAME` with your actual database name.

## Manual Migration (If Automatic Fails)

If the automatic migration doesn't work, you can run the SQL script manually:

```bash
# Connect to PostgreSQL
sudo -u postgres psql YOUR_DATABASE_NAME

# Run the SQL script
\i /home/ranjith/odoo/custom_addons/guardpro/migrations/18.0.1.0.3/add_conflict_columns.sql

# Exit PostgreSQL
\q
```

## Verification

After migration, verify the columns exist:

```sql
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name='guard_shift' 
  AND column_name IN ('has_conflict', 'conflict_type', 'conflict_details')
ORDER BY column_name;
```

Expected output:
```
  column_name   | data_type | is_nullable
----------------+-----------+-------------
 conflict_details | text      | YES
 conflict_type    | character varying | YES
 has_conflict     | boolean   | YES
```

## Post-Migration

After successful migration:

1. The error should be resolved
2. Existing shifts will have `has_conflict = FALSE` by default
3. Odoo will recompute conflicts for existing shifts on next access
4. New shifts will automatically detect conflicts

## Rollback (Not Recommended)

If you need to rollback, you can remove the columns:

```sql
ALTER TABLE guard_shift DROP COLUMN IF EXISTS has_conflict;
ALTER TABLE guard_shift DROP COLUMN IF EXISTS conflict_type;
ALTER TABLE guard_shift DROP COLUMN IF EXISTS conflict_details;
```

**Note:** This will remove all conflict detection functionality.











