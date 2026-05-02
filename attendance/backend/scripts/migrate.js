const fs = require('fs');
const path = require('path');
const { Pool } = require('pg');

const databaseUrl = process.env.DATABASE_URL || 'postgres://user:password@db:5432/attendance';
const migrationsDir = path.join(__dirname, '..', 'migrations');

const run = async () => {
    const pool = new Pool({ connectionString: databaseUrl });
    const client = await pool.connect();
    try {
        await client.query(`
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        `);

        const files = fs.readdirSync(migrationsDir)
            .filter((file) => file.endsWith('.sql'))
            .sort();

        for (const file of files) {
            const existing = await client.query(
                'SELECT 1 FROM schema_migrations WHERE filename = $1',
                [file]
            );
            if (existing.rowCount > 0) continue;

            const sql = fs.readFileSync(path.join(migrationsDir, file), 'utf8');
            await client.query('BEGIN');
            await client.query(sql);
            await client.query(
                'INSERT INTO schema_migrations (filename) VALUES ($1)',
                [file]
            );
            await client.query('COMMIT');
            console.log(`[MIGRATE] applied ${file}`);
        }

        console.log('[MIGRATE] complete');
    } catch (err) {
        try { await client.query('ROLLBACK'); } catch (_e) { /* no-op */ }
        console.error('[MIGRATE] failed:', err.message);
        process.exitCode = 1;
    } finally {
        client.release();
        await pool.end();
    }
};

run();
