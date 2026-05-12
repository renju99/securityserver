const { Pool } = require('pg');
const bcrypt = require('bcryptjs');

const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgres://user:password@db:5432/attendance'
});

async function seed() {
    const isProd = process.env.NODE_ENV === 'production';
    const demoPassword = process.env.SEED_DEMO_PASSWORD || (isProd ? null : 'berkeley123');
    if (!demoPassword) {
        console.error('Refusing to seed: set SEED_DEMO_PASSWORD when NODE_ENV=production (never use a dev default in prod).');
        process.exit(1);
    }
    const passwordHash = await bcrypt.hash(demoPassword, 10);

    const employees = [
        { staffId: 'ST374', email: 'st374@berkeleyuae.com', roleId: 4, siteId: 1, name: 'Operations' },
        { staffId: 'HR101', email: 'hr101@berkeleyuae.com', roleId: 2, siteId: 1, name: 'Operations' },
        { staffId: 'HR999', email: 'admin@berkeleyuae.com', roleId: 1, siteId: null, name: 'HR Management' }
    ];

    for (const emp of employees) {
        try {
            await pool.query(
                `INSERT INTO employees (organization_id, staff_id, email, password_hash, role_id, site_id, department_name) 
         VALUES ((SELECT id FROM organizations WHERE slug = 'default' LIMIT 1), $1, $2, $3, $4, $5, $6)
         ON CONFLICT (organization_id, staff_id) DO UPDATE SET 
         password_hash = EXCLUDED.password_hash,
         role_id = EXCLUDED.role_id,
         site_id = EXCLUDED.site_id,
         department_name = EXCLUDED.department_name`,
                [emp.staffId, emp.email, passwordHash, emp.roleId, emp.siteId, emp.name]
            );
            console.log(`Seeded ${emp.staffId}`);
        } catch (err) {
            console.error(`Error seeding ${emp.staffId}:`, err.message);
        }
    }

    await pool.end();
}

seed();
