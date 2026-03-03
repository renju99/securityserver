/**
 * Runs reset-admin.sql. Tries DATABASE_URL from .env, then common local Postgres setups.
 * First run: npm run reset-admin   (generates the SQL file)
 * Then: npm run run-reset-admin
 *
 * If all fail, set DATABASE_URL in .env to your real Postgres URL, or:
 *   DATABASE_URL=postgres://USER:PASSWORD@localhost:5432/DATABASE npm run run-reset-admin
 */
const path = require('path');
const fs = require('fs');
require('dotenv').config({ path: path.resolve(__dirname, '..', '.env') });

const { Pool } = require('pg');

function createPool(connectionString) {
    if (!connectionString || !connectionString.trim()) {
        return new Pool({ host: 'localhost', port: 5432, user: 'postgres', database: 'postgres', password: '' });
    }
    try {
        const url = new URL(connectionString);
        const auth = url.username ? (url.password !== undefined ? url.password : '') : '';
        return new Pool({
            host: url.hostname || 'localhost',
            port: parseInt(url.port || '5432', 10),
            user: url.username || 'postgres',
            password: typeof auth === 'string' ? auth : '',
            database: (url.pathname || '/').replace(/^\//, '') || 'postgres',
            ssl: url.searchParams.get('sslmode') === 'require' ? { rejectUnauthorized: false } : false,
        });
    } catch {
        return new Pool({ connectionString });
    }
}

const toTry = [
    process.env.DATABASE_URL && String(process.env.DATABASE_URL).trim(),
    'postgres://admin:password123@localhost:5433/cleaner_attendance',
    'postgres://postgres:postgres@localhost:5432/cleaner_attendance',
    'postgres://postgres:postgres@localhost:5432/postgres',
    'postgres://postgres@localhost:5432/cleaner_attendance',
    'postgres://postgres@localhost:5432/postgres',
].filter(Boolean);

const sqlPath = path.resolve(__dirname, 'reset-admin.sql');
let sql = fs.readFileSync(sqlPath, 'utf8');
sql = sql.replace(/--[^\n]*/g, '').trim();
const statements = sql.split(';').map((s) => s.trim()).filter(Boolean);

async function tryConnect(poolToUse) {
    const c = await poolToUse.query('SELECT 1').catch(() => null);
    return c != null;
}

async function run() {
    let pool = createPool(toTry[0]);
    let connected = await tryConnect(pool);
    if (!connected && toTry.length > 1) {
        for (let i = 1; i < toTry.length; i++) {
            await pool.end().catch(() => {});
            pool = createPool(toTry[i]);
            connected = await tryConnect(pool);
            if (connected) break;
        }
    }
    if (!connected) {
        console.error('Could not connect to Postgres. Set DATABASE_URL in backend/.env to your real URL, e.g.:');
        console.error('  DATABASE_URL=postgres://USER:PASSWORD@localhost:5432/DATABASE');
        await pool.end().catch(() => {});
        process.exit(1);
    }
    try {
        for (const stmt of statements) {
            if (stmt) await pool.query(stmt + ';');
        }
        console.log('Admin password reset. Login: admin@example.com / admin123');
    } catch (err) {
        console.error('Failed:', err.message);
        if (err.message.includes('relation "employees"')) {
            console.error('Run init.sql first to create tables.');
        }
        process.exit(1);
    } finally {
        await pool.end();
    }
}

run();
