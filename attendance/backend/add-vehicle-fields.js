const { Pool } = require('pg');
const pool = new Pool({ connectionString: process.env.DATABASE_URL || 'postgres://user:password@db:5432/attendance' });

async function run() {
    try {
        await pool.query('ALTER TABLE employees ADD COLUMN IF NOT EXISTS is_vehicle BOOLEAN DEFAULT FALSE');
        await pool.query('ALTER TABLE employees ADD COLUMN IF NOT EXISTS vehicle_make VARCHAR(100)');
        await pool.query('ALTER TABLE employees ADD COLUMN IF NOT EXISTS vehicle_model VARCHAR(100)');
        await pool.query('ALTER TABLE employees ADD COLUMN IF NOT EXISTS vehicle_plate VARCHAR(100)');
        console.log("Vehicle fields added to employees table");
    } catch(e) { console.error(e); } finally { await pool.end(); }
}
run();
