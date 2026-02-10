const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgres://user:password@db:5432/attendance'
});

const updateSchema = async () => {
    try {
        console.log('Updating schema...');

        // 1. Create Shifts Table
        await pool.query(`
            CREATE TABLE IF NOT EXISTS shifts (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        `);
        console.log('Created shifts table');

        // 2. Update Employees Table
        await pool.query(`
            ALTER TABLE employees 
            ADD COLUMN IF NOT EXISTS shift_id INTEGER REFERENCES shifts(id);
        `);
        console.log('Updated employees table');

        // 3. Update Sites Table
        // We'll use specific lat/long columns for easier calculations, though PostGIS point is also good.
        // Let's stick to adding precise columns if they don't exist, 
        // OR rely on the existing PostGIS logic? 
        // The existing code for sites uses 'location' as separate text and 'latitude'/'longitude' in the INSERT/UPDATE routes in index.js!
        // Wait, let me check index.js again.
        // Lines 435: INSERT INTO sites (name, location, latitude, longitude)
        // But init.sql (Lines 4-10) only showed:
        // CREATE TABLE IF NOT EXISTS sites (id, name, location);
        // So the backend code in index.js MIGHT be trying to insert columns that don't exist yet, or I missed them in init.sql.
        // Let's safe-add them.
        await pool.query(`
            ALTER TABLE sites 
            ADD COLUMN IF NOT EXISTS latitude DECIMAL(10, 8),
            ADD COLUMN IF NOT EXISTS longitude DECIMAL(11, 8),
            ADD COLUMN IF NOT EXISTS radius_meters INTEGER DEFAULT 100;
        `);
        console.log('Updated sites table');

        // 4. Create Geo Fence Alerts Table
        await pool.query(`
            CREATE TABLE IF NOT EXISTS geo_fence_alerts (
                id SERIAL PRIMARY KEY,
                employee_id INTEGER REFERENCES employees(id),
                site_id INTEGER REFERENCES sites(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                latitude DECIMAL(10, 8),
                longitude DECIMAL(11, 8),
                message TEXT,
                status VARCHAR(20) DEFAULT 'new'
            );
        `);
        console.log('Created geo_fence_alerts table');

        // 5. Insert some default shifts
        await pool.query(`
            INSERT INTO shifts (name, start_time, end_time) 
            VALUES 
            ('Morning Shift', '08:00', '17:00'),
            ('Night Shift', '20:00', '05:00')
            ON CONFLICT (name) DO NOTHING;
        `);
        console.log('Seeded default shifts');

    } catch (err) {
        console.error('Schema update error:', err);
    } finally {
        await pool.end();
    }
};

updateSchema();
