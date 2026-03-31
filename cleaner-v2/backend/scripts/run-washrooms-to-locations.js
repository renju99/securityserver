#!/usr/bin/env node
/**
 * Run washrooms-to-locations.sql using the app's db connection.
 * Usage: node scripts/run-washrooms-to-locations.js (from backend dir)
 * Or:    node backend/scripts/run-washrooms-to-locations.js (from project root, with dotenv path)
 */
const path = require('path');
const fs = require('fs');
require('dotenv').config({ path: path.resolve(__dirname, '..', '.env') });
const { pool } = require('../src/utils/db');

const sqlPath = path.resolve(__dirname, 'washrooms-to-locations.sql');
const sql = fs.readFileSync(sqlPath, 'utf8');

async function run() {
    try {
        await pool.query(sql);
        console.log('Migration washrooms-to-locations completed successfully.');
    } catch (err) {
        console.error('Migration failed:', err.message);
        process.exit(1);
    } finally {
        await pool.end();
    }
}

run();
