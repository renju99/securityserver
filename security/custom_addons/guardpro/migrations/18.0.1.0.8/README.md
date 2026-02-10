# Migration 18.0.1.0.8

## Purpose
This migration adds the `sidebar_type` field to the `res_users` table to fix:
- `AttributeError: 'res.users' object has no attribute 'sidebar_type'`
- `UndefinedColumn: column res_users.sidebar_type does not exist`

## Changes
- Adds `sidebar_type` column to `res_users` table with default value `'invisible'`
- Updates existing records to have the default value

## How to Apply

### Option 1: Upgrade Module via Odoo UI (Recommended)
1. Log in to Odoo as Administrator
2. Go to **Apps** menu
3. Remove the **Apps** filter to show all modules
4. Search for `guardpro`
5. Click **Upgrade** button

### Option 2: Upgrade Module via Command Line
```bash
# Navigate to your Odoo installation directory
cd /path/to/odoo

# Run Odoo with upgrade flag
python odoo-bin -u guardpro -d your_database_name --stop-after-init
```

### Option 3: Manual SQL Execution (If upgrade doesn't work)
If the automatic upgrade doesn't apply the migration, you can manually execute the SQL:
```bash
psql -d your_database_name -f custom_addons/guardpro/migrations/18.0.1.0.8/pre-migration.sql
```

## Verification
After applying the migration, verify the column exists:
```sql
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'res_users' 
AND column_name = 'sidebar_type';
```

Expected result:
- `column_name`: `sidebar_type`
- `data_type`: `character varying`
- `column_default`: `'invisible'`

