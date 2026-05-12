const initializeStartupData = async (pool) => {
    const seedPermissions = async () => {
        try {
            console.log('Seeding permissions...');
            await pool.query("INSERT INTO roles (name) VALUES ('HR Admin'), ('Site Supervisor'), ('Payroll'), ('Employee') ON CONFLICT (name) DO NOTHING");

            const permissions = [
                { name: 'view_dashboard', description: 'Access to HR Dashboard' },
                { name: 'manage_staff', description: 'Add/Edit Staff Members' },
                { name: 'view_map', description: 'View Live Map' },
                { name: 'manage_sites', description: 'Add/Edit Sites' },
                { name: 'view_reports', description: 'View Attendance Reports' },
                { name: 'export_data', description: 'Export Data to CSV' },
                { name: 'view_attendance', description: 'View Attendance Logs' }
            ];

            for (const p of permissions) {
                await pool.query(
                    "INSERT INTO permissions (name, description) VALUES ($1, $2) ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description",
                    [p.name, p.description]
                );
            }

            const roleMap = {
                'HR Admin': ['view_dashboard', 'manage_staff', 'view_map', 'manage_sites', 'view_reports', 'export_data', 'view_attendance'],
                'Site Supervisor': ['view_dashboard', 'view_map', 'view_attendance', 'view_reports'],
                'Payroll': ['view_dashboard', 'view_reports', 'export_data']
            };

            for (const [roleName, perms] of Object.entries(roleMap)) {
                const roleRes = await pool.query("SELECT id FROM roles WHERE name = $1", [roleName]);
                if (roleRes.rows.length === 0) continue;
                const roleId = roleRes.rows[0].id;

                for (const permName of perms) {
                    const permRes = await pool.query("SELECT id FROM permissions WHERE name = $1", [permName]);
                    if (permRes.rows.length === 0) continue;
                    const permId = permRes.rows[0].id;
                    await pool.query(
                        "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) ON CONFLICT (role_id, permission_id) DO NOTHING",
                        [roleId, permId]
                    );
                }
            }
            console.log('Permissions seeded successfully.');
        } catch (err) {
            console.error('Seeding error:', err);
        }
    };

    const runMigrations = async () => {
        try {
            await pool.query('ALTER TABLE employees ADD COLUMN IF NOT EXISTS photo_url VARCHAR(255)');
            await pool.query(`
                CREATE TABLE IF NOT EXISTS shifts (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(50) UNIQUE NOT NULL,
                    start_time TIME NOT NULL,
                    end_time TIME NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            `);
            await pool.query(`ALTER TABLE employees ADD COLUMN IF NOT EXISTS shift_id INTEGER REFERENCES shifts(id);`);
            await pool.query(`
                ALTER TABLE sites 
                ADD COLUMN IF NOT EXISTS latitude DECIMAL(10, 8),
                ADD COLUMN IF NOT EXISTS longitude DECIMAL(11, 8),
                ADD COLUMN IF NOT EXISTS radius_meters INTEGER DEFAULT 100,
                ADD COLUMN IF NOT EXISTS geofence_type VARCHAR(20) DEFAULT 'CIRCLE',
                ADD COLUMN IF NOT EXISTS geofence_data JSONB,
                ADD COLUMN IF NOT EXISTS geofence_enabled BOOLEAN DEFAULT true,
                ADD COLUMN IF NOT EXISTS nfc_payload VARCHAR(255);
            `);
            await pool.query(`
                CREATE TABLE IF NOT EXISTS geo_fence_alerts (
                    id SERIAL PRIMARY KEY,
                    employee_id INTEGER REFERENCES employees(id),
                    site_id INTEGER REFERENCES sites(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    latitude DECIMAL(10, 8),
                    longitude DECIMAL(11, 8),
                    message TEXT,
                    status VARCHAR(20) DEFAULT 'active'
                );
            `);
            await pool.query(`ALTER TABLE geo_fence_alerts ADD COLUMN IF NOT EXISTS false_positive BOOLEAN DEFAULT false`);
            const shiftOrgCol = await pool.query(`
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'shifts' AND column_name = 'organization_id'
            `);
            if (shiftOrgCol.rows.length > 0) {
                await pool.query(`
                    INSERT INTO shifts (organization_id, name, start_time, end_time)
                    SELECT o.id, v.name, v.start_time::time, v.end_time::time
                    FROM organizations o
                    CROSS JOIN (VALUES
                        ('Morning Shift', '08:00', '17:00'),
                        ('Night Shift', '20:00', '05:00')
                    ) AS v(name, start_time, end_time)
                    WHERE o.slug = 'default'
                    ON CONFLICT (organization_id, name) DO NOTHING
                `);
            } else {
                await pool.query(`
                    INSERT INTO shifts (name, start_time, end_time)
                    VALUES ('Morning Shift', '08:00', '17:00'), ('Night Shift', '20:00', '05:00')
                    ON CONFLICT (name) DO NOTHING
                `);
            }
            await pool.query(`ALTER TABLE attendance ADD COLUMN IF NOT EXISTS notes TEXT`);
            await pool.query(`ALTER TABLE attendance ADD COLUMN IF NOT EXISTS auto_closed BOOLEAN DEFAULT false`);
            await pool.query(`
                CREATE TABLE IF NOT EXISTS biometric_devices (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    device_key VARCHAR(100) UNIQUE NOT NULL,
                    site_id INTEGER REFERENCES sites(id),
                    type VARCHAR(50) DEFAULT 'RA08',
                    last_seen TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            `);
            await pool.query(`ALTER TABLE biometric_devices ADD COLUMN IF NOT EXISTS ip_address VARCHAR(128)`);
            await pool.query(`ALTER TABLE biometric_devices ADD COLUMN IF NOT EXISTS port VARCHAR(32)`);
            await pool.query(`ALTER TABLE biometric_devices ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{}'::jsonb`);
            await pool.query(`
                CREATE TABLE IF NOT EXISTS biometric_logs (
                    id SERIAL PRIMARY KEY,
                    device_id INTEGER REFERENCES biometric_devices(id),
                    staff_id VARCHAR(50), 
                    employee_id INTEGER REFERENCES employees(id),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    photo_url VARCHAR(255),
                    raw_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            `);
            await pool.query(`ALTER TABLE biometric_logs ADD COLUMN IF NOT EXISTS process_status VARCHAR(24) NOT NULL DEFAULT 'pending'`);
            await pool.query(`ALTER TABLE biometric_logs ADD COLUMN IF NOT EXISTS process_attempts INTEGER NOT NULL DEFAULT 0`);
            await pool.query(`ALTER TABLE biometric_logs ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`);
            await pool.query(`ALTER TABLE biometric_logs ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ`);
            await pool.query(`ALTER TABLE biometric_logs ADD COLUMN IF NOT EXISTS process_last_error TEXT`);
            await pool.query(`ALTER TABLE biometric_logs ADD COLUMN IF NOT EXISTS attendance_id INTEGER REFERENCES attendance(id) ON DELETE SET NULL`);
            await pool.query(`ALTER TABLE biometric_logs ADD COLUMN IF NOT EXISTS attendance_event_type VARCHAR(16)`);
            await pool.query(`CREATE UNIQUE INDEX IF NOT EXISTS idx_biometric_logs_device_staff_timestamp_unique ON biometric_logs (device_id, staff_id, timestamp)`);
            await pool.query(`CREATE INDEX IF NOT EXISTS idx_biometric_logs_process_retry ON biometric_logs (process_status, next_retry_at, timestamp, id)`);
            await pool.query(`CREATE INDEX IF NOT EXISTS idx_biometric_logs_attendance ON biometric_logs (attendance_id)`);
            await pool.query(`
                CREATE TABLE IF NOT EXISTS public_holidays (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(150) NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    site_id INTEGER REFERENCES sites(id),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_by INTEGER REFERENCES employees(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT public_holidays_date_check CHECK (end_date >= start_date)
                );
            `);
            await pool.query(`CREATE INDEX IF NOT EXISTS idx_public_holidays_dates ON public_holidays (start_date, end_date)`);
            await pool.query(`CREATE INDEX IF NOT EXISTS idx_public_holidays_site_dates ON public_holidays (site_id, start_date, end_date)`);
            await pool.query(`
                CREATE TABLE IF NOT EXISTS employee_leaves (
                    id SERIAL PRIMARY KEY,
                    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                    leave_type VARCHAR(80) DEFAULT 'Annual Leave',
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'approved',
                    notes TEXT,
                    created_by INTEGER REFERENCES employees(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT employee_leaves_date_check CHECK (end_date >= start_date),
                    CONSTRAINT employee_leaves_status_check CHECK (status IN ('pending', 'approved', 'rejected'))
                );
            `);
            await pool.query(`CREATE INDEX IF NOT EXISTS idx_employee_leaves_employee_dates ON employee_leaves (employee_id, start_date, end_date)`);
            await pool.query(`CREATE INDEX IF NOT EXISTS idx_employee_leaves_status_dates ON employee_leaves (status, start_date, end_date)`);
            await pool.query(`
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    token_id VARCHAR(64) PRIMARY KEY,
                    family_id VARCHAR(64) NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                    token_hash VARCHAR(128) NOT NULL,
                    issued_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    revoked_at TIMESTAMP,
                    revoke_reason VARCHAR(64),
                    replaced_by_token_id VARCHAR(64)
                );
            `);
            await pool.query(`CREATE UNIQUE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash)`);
            await pool.query(`CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_family ON refresh_tokens(user_id, family_id)`);
            await pool.query(`CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at)`);
            await pool.query(`
                CREATE TABLE IF NOT EXISTS report_presets (
                    id SERIAL PRIMARY KEY,
                    created_by INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                    name VARCHAR(120) NOT NULL,
                    data_source VARCHAR(20) NOT NULL DEFAULT 'app',
                    role_ids JSONB DEFAULT '[]'::jsonb,
                    site_ids JSONB DEFAULT '[]'::jsonb,
                    shift_ids JSONB DEFAULT '[]'::jsonb,
                    department VARCHAR(120),
                    start_date VARCHAR(32),
                    end_date VARCHAR(32),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            `);
            await pool.query(`CREATE INDEX IF NOT EXISTS idx_report_presets_creator ON report_presets(created_by, created_at DESC)`);
            await pool.query(`
                CREATE TABLE IF NOT EXISTS roster_templates (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(120) NOT NULL,
                    site_id INTEGER REFERENCES sites(id),
                    department_name VARCHAR(120),
                    rotation_type VARCHAR(20) NOT NULL DEFAULT 'fixed',
                    shift_sequence JSONB NOT NULL DEFAULT '[]'::jsonb,
                    start_date DATE NOT NULL,
                    end_date DATE,
                    created_by INTEGER REFERENCES employees(id),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            `);
            await pool.query(`
                CREATE TABLE IF NOT EXISTS roster_assignments (
                    id SERIAL PRIMARY KEY,
                    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                    shift_id INTEGER NOT NULL REFERENCES shifts(id),
                    work_date DATE NOT NULL,
                    source VARCHAR(20) NOT NULL DEFAULT 'manual',
                    template_id INTEGER REFERENCES roster_templates(id) ON DELETE SET NULL,
                    created_by INTEGER REFERENCES employees(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(employee_id, work_date)
                );
            `);
            await pool.query(`CREATE INDEX IF NOT EXISTS idx_roster_assignments_date ON roster_assignments(work_date)`);
            await pool.query(`CREATE INDEX IF NOT EXISTS idx_roster_assignments_employee_date ON roster_assignments(employee_id, work_date)`);

            console.log('Migrations: Schema updated for Shifts, Geo-Fencing, Biometrics, and Leave Calendar.');
        } catch (err) {
            console.error('Migration error:', err);
        }
    };

    await seedPermissions();
    await runMigrations();
};

module.exports = {
    initializeStartupData,
};
