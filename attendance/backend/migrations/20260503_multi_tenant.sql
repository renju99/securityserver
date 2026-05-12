-- Multi-tenant: organizations + organization_id on core tables.
-- Existing rows attach to slug "default".

CREATE TABLE IF NOT EXISTS organizations (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(64) NOT NULL,
    name VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_slug ON organizations (slug);

INSERT INTO organizations (slug, name)
SELECT 'default', 'Default organization'
WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE slug = 'default');

-- Sites
ALTER TABLE sites ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id);
UPDATE sites s
SET organization_id = o.id
FROM organizations o
WHERE o.slug = 'default'
  AND s.organization_id IS NULL;
UPDATE sites SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
ALTER TABLE sites ALTER COLUMN organization_id SET NOT NULL;

ALTER TABLE sites DROP CONSTRAINT IF EXISTS sites_name_key;
DROP INDEX IF EXISTS sites_name_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_sites_org_name ON sites (organization_id, name);

-- Shifts (per-organization names)
ALTER TABLE shifts ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id);
UPDATE shifts sh
SET organization_id = o.id
FROM organizations o
WHERE o.slug = 'default'
  AND sh.organization_id IS NULL;
UPDATE shifts SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
ALTER TABLE shifts ALTER COLUMN organization_id SET NOT NULL;

ALTER TABLE shifts DROP CONSTRAINT IF EXISTS shifts_name_key;
DROP INDEX IF EXISTS shifts_name_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_shifts_org_name ON shifts (organization_id, name);

-- Employees (staff_id / email unique per org)
ALTER TABLE employees ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id);
-- Subquery avoids referencing update target alias "e" inside FROM (PostgreSQL error 42P01).
UPDATE employees e
SET organization_id = COALESCE(
        (SELECT s.organization_id FROM sites s WHERE s.id = e.site_id),
        o.id
    )
FROM organizations o
WHERE o.slug = 'default'
  AND e.organization_id IS NULL;
UPDATE employees SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
ALTER TABLE employees ALTER COLUMN organization_id SET NOT NULL;

ALTER TABLE employees DROP CONSTRAINT IF EXISTS employees_staff_id_key;
DROP INDEX IF EXISTS employees_staff_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_org_staff ON employees (organization_id, staff_id);

ALTER TABLE employees DROP CONSTRAINT IF EXISTS employees_email_key;
DROP INDEX IF EXISTS employees_email_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_org_email ON employees (organization_id, email) WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_employees_organization ON employees (organization_id);
CREATE INDEX IF NOT EXISTS idx_sites_organization ON sites (organization_id);
CREATE INDEX IF NOT EXISTS idx_shifts_organization ON shifts (organization_id);

-- Odoo instances: scoped per org; instance_code unique within org
ALTER TABLE odoo_instances ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id);
UPDATE odoo_instances oi
SET organization_id = org.id
FROM organizations org
WHERE org.slug = 'default'
  AND oi.organization_id IS NULL;
UPDATE odoo_instances SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
ALTER TABLE odoo_instances ALTER COLUMN organization_id SET NOT NULL;

-- These FKs target the old UNIQUE(instance_code) index; drop before replacing uniqueness.
ALTER TABLE staff_odoo_routing DROP CONSTRAINT IF EXISTS staff_odoo_routing_instance_code_fkey;
ALTER TABLE attendance_sync_mapping DROP CONSTRAINT IF EXISTS attendance_sync_mapping_instance_code_fkey;

ALTER TABLE odoo_instances DROP CONSTRAINT IF EXISTS odoo_instances_instance_code_key;
DROP INDEX IF EXISTS odoo_instances_instance_code_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_odoo_instances_org_code ON odoo_instances (organization_id, instance_code);

-- staff_odoo_routing: composite identity per org
ALTER TABLE staff_odoo_routing ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id);
UPDATE staff_odoo_routing r
SET organization_id = e.organization_id
FROM employees e
WHERE e.staff_id = r.staff_id;
UPDATE staff_odoo_routing SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
ALTER TABLE staff_odoo_routing ALTER COLUMN organization_id SET NOT NULL;

ALTER TABLE staff_odoo_routing DROP CONSTRAINT IF EXISTS staff_odoo_routing_pkey;
ALTER TABLE staff_odoo_routing ADD PRIMARY KEY (organization_id, staff_id);

ALTER TABLE staff_odoo_routing ADD CONSTRAINT staff_odoo_routing_odoo_instance_fkey
    FOREIGN KEY (organization_id, instance_code) REFERENCES odoo_instances(organization_id, instance_code);

ALTER TABLE attendance_sync_mapping ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id);
UPDATE attendance_sync_mapping m
SET organization_id = oi.organization_id
FROM odoo_instances oi
WHERE oi.instance_code = m.instance_code
  AND m.organization_id IS NULL;
UPDATE attendance_sync_mapping SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
ALTER TABLE attendance_sync_mapping ALTER COLUMN organization_id SET NOT NULL;
ALTER TABLE attendance_sync_mapping ADD CONSTRAINT attendance_sync_mapping_odoo_instance_fkey
    FOREIGN KEY (organization_id, instance_code) REFERENCES odoo_instances(organization_id, instance_code);

-- Kiosk devices
ALTER TABLE kiosk_devices ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id);
UPDATE kiosk_devices kd
SET organization_id = s.organization_id
FROM sites s
WHERE s.id = kd.site_id AND kd.organization_id IS NULL;
UPDATE kiosk_devices SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
ALTER TABLE kiosk_devices ALTER COLUMN organization_id SET NOT NULL;

-- Job codes
ALTER TABLE job_codes ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id);
UPDATE job_codes jc
SET organization_id = COALESCE(
        (SELECT s.organization_id FROM sites s WHERE s.id = jc.site_id),
        org.id
    )
FROM organizations org
WHERE org.slug = 'default' AND jc.organization_id IS NULL;
UPDATE job_codes SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
ALTER TABLE job_codes ALTER COLUMN organization_id SET NOT NULL;

ALTER TABLE job_codes DROP CONSTRAINT IF EXISTS job_codes_code_key;
DROP INDEX IF EXISTS job_codes_code_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_codes_org_code ON job_codes (organization_id, code);

-- Biometric devices
ALTER TABLE biometric_devices ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id);
UPDATE biometric_devices bd
SET organization_id = s.organization_id
FROM sites s
WHERE s.id = bd.site_id AND bd.organization_id IS NULL;
UPDATE biometric_devices SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
ALTER TABLE biometric_devices ALTER COLUMN organization_id SET NOT NULL;

-- Public holidays (optional site; org from site or default)
ALTER TABLE public_holidays ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id);
UPDATE public_holidays ph
SET organization_id = s.organization_id
FROM sites s
WHERE ph.site_id = s.id AND ph.organization_id IS NULL;
UPDATE public_holidays SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
ALTER TABLE public_holidays ALTER COLUMN organization_id SET NOT NULL;

-- Report presets
ALTER TABLE report_presets ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id);
UPDATE report_presets rp
SET organization_id = e.organization_id
FROM employees e
WHERE e.id = rp.created_by AND rp.organization_id IS NULL;
UPDATE report_presets SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
ALTER TABLE report_presets ALTER COLUMN organization_id SET NOT NULL;

-- Roster templates
ALTER TABLE roster_templates ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id);
UPDATE roster_templates rt
SET organization_id = s.organization_id
FROM sites s
WHERE rt.site_id = s.id AND rt.organization_id IS NULL;
UPDATE roster_templates SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
ALTER TABLE roster_templates ALTER COLUMN organization_id SET NOT NULL;

-- Settings: org-scoped key/value (legacy global key migrated to default org)
DO $$
BEGIN
    IF to_regclass('public.settings') IS NULL THEN
        CREATE TABLE settings (
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            key VARCHAR(100) NOT NULL,
            value JSONB NOT NULL DEFAULT '{}'::jsonb,
            PRIMARY KEY (organization_id, key)
        );
    ELSIF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'settings' AND column_name = 'organization_id'
    ) THEN
        ALTER TABLE settings ADD COLUMN organization_id INTEGER REFERENCES organizations(id);
        UPDATE settings SET organization_id = (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) WHERE organization_id IS NULL;
        ALTER TABLE settings ALTER COLUMN organization_id SET NOT NULL;
        ALTER TABLE settings DROP CONSTRAINT IF EXISTS settings_pkey;
        ALTER TABLE settings DROP CONSTRAINT IF EXISTS settings_key_key;
        ALTER TABLE settings ADD PRIMARY KEY (organization_id, key);
    END IF;
END $$;
