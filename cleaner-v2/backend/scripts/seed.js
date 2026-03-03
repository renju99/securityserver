/**
 * Seed default admin user for local/dev use.
 * Run from backend dir: npm run seed
 * Login: admin@example.com / admin123
 */
const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '..', '.env') });

const { Pool } = require('pg');
const bcrypt = require('bcryptjs');

// Ensure password is always a string (pg rejects undefined)
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

// Try: .env DATABASE_URL, then common local setups (Docker db often on 5433 if 5432 is taken)
const toTry = [
    process.env.DATABASE_URL && String(process.env.DATABASE_URL).trim(),
    'postgres://admin:password123@localhost:5433/cleaner_attendance',
    'postgres://postgres:postgres@localhost:5432/cleaner_attendance',
    'postgres://postgres:postgres@localhost:5432/postgres',
    'postgres://postgres@localhost:5432/postgres',
].filter(Boolean);

let pool = createPool(toTry[0]);

const DEFAULT_ADMIN = {
    name: 'Admin',
    email: 'admin@example.com',
    password: 'admin123',
    role: 'admin',
};

async function tryConnect(poolToUse) {
    const c = await poolToUse.query('SELECT 1').catch(() => null);
    return c != null;
}

async function seed() {
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
        console.error('Seed failed: could not connect to Postgres.');
        console.error('Set DATABASE_URL in backend/.env to your Postgres URL, e.g.:');
        console.error('  DATABASE_URL=postgres://USER:PASSWORD@localhost:5432/DATABASE');
        await pool.end().catch(() => {});
        process.exit(1);
    }
    try {
        const password_hash = await bcrypt.hash(DEFAULT_ADMIN.password, 10);
        const existing = await pool.query('SELECT id FROM employees WHERE email = $1', [DEFAULT_ADMIN.email]);
        if (existing.rows.length > 0) {
            await pool.query(
                'UPDATE employees SET name = $1, password_hash = $2, role = $3, active = true WHERE email = $4',
                [DEFAULT_ADMIN.name, password_hash, DEFAULT_ADMIN.role, DEFAULT_ADMIN.email]
            );
            console.log('Admin password reset.');
        } else {
            await pool.query(
                'INSERT INTO employees (name, email, password_hash, role) VALUES ($1, $2, $3, $4)',
                [DEFAULT_ADMIN.name, DEFAULT_ADMIN.email, password_hash, DEFAULT_ADMIN.role]
            );
            console.log('Default admin created.');
        }
        console.log('Login: admin@example.com / admin123');
    } catch (err) {
        if (err.message && err.message.includes('relation "employees" does not exist')) {
            console.error('Seed failed: tables missing. Run init.sql first, e.g.:');
            console.error('  psql -U postgres -d cleaner_attendance -f backend/init.sql');
        } else {
            console.error('Seed failed:', err.message);
        }
        process.exit(1);
    } finally {
        await pool.end();
    }
}

seed();
