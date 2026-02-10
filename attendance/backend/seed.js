const { Pool } = require('pg');
const bcrypt = require('bcryptjs');

const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgres://user:password@db:5432/attendance'
});

async function seed() {
    const passwordHash = await bcrypt.hash('berkeley123', 10);

    const employees = [
        { staffId: 'ST374', email: 'st374@berkeleyuae.com', roleId: 4, siteId: 1, name: 'Operations' },
        { staffId: 'HR101', email: 'hr101@berkeleyuae.com', roleId: 2, siteId: 1, name: 'Operations' },
        { staffId: 'HR999', email: 'admin@berkeleyuae.com', roleId: 1, siteId: null, name: 'HR Management' }
    ];

    for (const emp of employees) {
        try {
            await pool.query(
                `INSERT INTO employees (staff_id, email, password_hash, role_id, site_id, department_name) 
         VALUES ($1, $2, $3, $4, $5, $6)
         ON CONFLICT (staff_id) DO UPDATE SET 
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
