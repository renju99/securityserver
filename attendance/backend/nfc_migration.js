const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgres://user:password@db:5432/attendance'
});

const updateSchema = async () => {
    try {
        console.log('Adding nfc_payload to sites table...');
        await pool.query(`
            ALTER TABLE sites 
            ADD COLUMN IF NOT EXISTS nfc_payload VARCHAR(255);
        `);
        console.log('Updated sites table');

    } catch (err) {
        console.error('Schema update error:', err);
    } finally {
        await pool.end();
    }
};

updateSchema();
