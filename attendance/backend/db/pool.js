const { Pool } = require('pg');

const createPool = () => {
    const pool = new Pool({
        connectionString: process.env.DATABASE_URL || 'postgres://user:password@db:5432/attendance',
        max: parseInt(process.env.PG_POOL_MAX || '20', 10),
        idleTimeoutMillis: parseInt(process.env.PG_IDLE_TIMEOUT_MS || '30000', 10),
        connectionTimeoutMillis: parseInt(process.env.PG_CONN_TIMEOUT_MS || '5000', 10),
    });

    const SLOW_QUERY_MS = parseInt(process.env.PG_SLOW_QUERY_MS || '500', 10);
    const baseQuery = pool.query.bind(pool);
    pool.query = async (...args) => {
        const started = Date.now();
        try {
            return await baseQuery(...args);
        } finally {
            const elapsed = Date.now() - started;
            if (elapsed >= SLOW_QUERY_MS) {
                const text = typeof args[0] === 'string' ? args[0] : (args[0]?.text || '');
                const compact = String(text).replace(/\s+/g, ' ').trim().slice(0, 220);
                console.warn(`[DB][SLOW_QUERY ${elapsed}ms] ${compact}`);
            }
        }
    };

    setInterval(() => {
        console.log(`[DB][POOL] total=${pool.totalCount} idle=${pool.idleCount} waiting=${pool.waitingCount}`);
    }, parseInt(process.env.PG_POOL_METRICS_INTERVAL_MS || '60000', 10));

    return pool;
};

module.exports = {
    createPool,
};
