const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgres://user:password@db:5432/attendance'
});

const runMigration = async () => {
    try {
        console.log('Running Biometrics Migration...');

        // 1. Biometric Devices Table
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
        console.log('Created biometric_devices table');

        // 2. Biometric Logs Table
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
        console.log('Created biometric_logs table');

        console.log('Biometrics Migration completed successfully.');
    } catch (err) {
        console.error('Migration error:', err);
    } finally {
        await pool.end();
    }
};

runMigration();
