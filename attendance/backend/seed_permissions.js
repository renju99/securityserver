const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgres://user:password@db:5432/attendance'
});

async function seed() {
    try {
        console.log('Checking roles and permissions...');

        // 1. Ensure Roles exist
        const roles = ['HR Admin', 'Site Supervisor', 'Payroll', 'Employee'];
        for (const role of roles) {
            await pool.query('INSERT INTO roles (name) VALUES ($1) ON CONFLICT (name) DO NOTHING', [role]);
        }

        // 2. Ensure Permissions exist
        const permissions = [
            { name: 'view_dashboard', description: 'Access to HR Dashboard' },
            { name: 'manage_staff', description: 'Add/Edit Staff Members' },
            { name: 'view_map', description: 'View Live Map' },
            { name: 'manage_sites', description: 'Add/Edit Sites' },
            { name: 'view_reports', description: 'View Attendance Reports' },
            { name: 'export_data', description: 'Export Data to CSV' },
            { name: 'view_attendance', description: 'View Attendance Logs' }
        ];

        for (const perm of permissions) {
            await pool.query(
                'INSERT INTO permissions (name, description) VALUES ($1, $2) ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description',
                [perm.name, perm.description]
            );
        }

        // 3. Map Roles to Permissions
        const roleMap = {
            'HR Admin': ['view_dashboard', 'manage_staff', 'view_map', 'manage_sites', 'view_reports', 'export_data', 'view_attendance'],
            'Site Supervisor': ['view_dashboard', 'view_map', 'view_attendance', 'view_reports'],
            'Payroll': ['view_dashboard', 'view_reports', 'export_data'],
            'Employee': []
        };

        for (const [roleName, perms] of Object.entries(roleMap)) {
            const roleRes = await pool.query('SELECT id FROM roles WHERE name = $1', [roleName]);
            if (roleRes.rows.length === 0) continue;
            const roleId = roleRes.rows[0].id;

            for (const permName of perms) {
                const permRes = await pool.query('SELECT id FROM permissions WHERE name = $1', [permName]);
                if (permRes.rows.length === 0) continue;
                const permId = permRes.rows[0].id;

                await pool.query(
                    'INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) ON CONFLICT (role_id, permission_id) DO NOTHING',
                    [roleId, permId]
                );
            }
        }

        console.log('Seeding completed successfully.');
    } catch (err) {
        console.error('Seeding error:', err);
    } finally {
        await pool.end();
    }
}

seed();
