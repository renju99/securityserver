export { };

require('dotenv').config();
const { assertProductionCoreConfig } = require('./utils/productionEnvCheck');
assertProductionCoreConfig();

const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const { createAdapter } = require('@socket.io/redis-adapter');
const { createClient } = require('redis');
const cors = require('cors');
const cookieParser = require('cookie-parser');
const fs = require('fs');
const path = require('path');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');

const authRoutes = require('./routes/auth');
const hrRoutes = require('./routes/hr');
const employeeRoutes = require('./routes/employee');
const { APP_TIMEZONE, isDuringShift } = require('./utils/time');
const { createMetrics, createRequestContextMiddleware } = require('./utils/observability');
const { JWT_SECRET, corsOptions, socketCorsOptions } = require('./config/serverConfig');
const { createPool } = require('./db/pool');
const { createAuthMiddleware } = require('./middleware/auth');
const { createRateLimiters } = require('./middleware/rateLimiters');
const { initializeStartupData } = require('./services/startupData');
const { createAutoCheckoutRunner, setupMaintenanceSchedulers } = require('./jobs/schedulers');
const { registerSocketHandlers } = require('./socket/registerSocketHandlers');

const app = express();
const server = http.createServer(app);
const io = new Server(server, { cors: socketCorsOptions });
const metrics = createMetrics();
const pool = createPool();

app.set('trust proxy', parseInt(process.env.TRUST_PROXY_HOPS || '1', 10));
app.get('/healthz', async (_req, res) => {
    try {
        await pool.query('SELECT 1');
        return res.status(200).json({ ok: true });
    } catch (_err) {
        return res.status(503).json({ ok: false });
    }
});

const { authLimiter, locationLimiter, apiLimiter } = createRateLimiters();
const { authenticateToken, authorizeRole } = createAuthMiddleware({ jwt, JWT_SECRET });
const DATA_RETENTION_DAYS = parseInt(process.env.DATA_RETENTION_DAYS || '180');
const REQUEST_BODY_LIMIT = process.env.REQUEST_BODY_LIMIT || '10mb';
const SOCKET_IO_REDIS_URL = process.env.SOCKET_IO_REDIS_URL || process.env.REDIS_URL || '';
const SOCKET_IO_REDIS_REQUIRED = (process.env.SOCKET_IO_REDIS_REQUIRED || 'false') === 'true';

const setupSocketAdapter = async () => {
    if (!SOCKET_IO_REDIS_URL) {
        console.warn('[SOCKET] Redis adapter disabled. Set SOCKET_IO_REDIS_URL or REDIS_URL before running multiple API replicas.');
        return;
    }
    const pubClient = createClient({ url: SOCKET_IO_REDIS_URL });
    const subClient = pubClient.duplicate();
    pubClient.on('error', (err) => console.error('[SOCKET][REDIS][PUB]', err.message));
    subClient.on('error', (err) => console.error('[SOCKET][REDIS][SUB]', err.message));
    try {
        await Promise.all([pubClient.connect(), subClient.connect()]);
        io.adapter(createAdapter(pubClient, subClient));
        console.log('[SOCKET] Redis adapter enabled for multi-instance Socket.IO.');
    } catch (err) {
        const message = `[SOCKET] Redis adapter unavailable: ${err.message}`;
        if (SOCKET_IO_REDIS_REQUIRED) throw new Error(message);
        console.warn(`${message}. Continuing in single-instance mode.`);
    }
};

app.use('/hr/', apiLimiter);
app.use(cors(corsOptions));
app.use(express.json({ limit: REQUEST_BODY_LIMIT }));
app.use(cookieParser());
app.use(express.urlencoded({ limit: REQUEST_BODY_LIMIT, extended: true }));

app.use(createRequestContextMiddleware(metrics));

const uploadsPath = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadsPath)) {
    fs.mkdirSync(uploadsPath, { recursive: true });
}
app.use('/uploads', express.static(uploadsPath));
// Backward-compatible path for stored photo URLs
app.use('/api/uploads', express.static(uploadsPath));

if (process.env.NODE_ENV !== 'production') {
    app.post('/debug/log', (req, res) => {
        console.log(`[PHONE_LOG] ${req.body.tag}: ${req.body.msg}`);
        res.sendStatus(200);
    });
}

const { runAutoCheckout, schedule: scheduleAutoCheckout } = createAutoCheckoutRunner({
    pool,
    io,
    metrics,
    APP_TIMEZONE
});
// Two router instances: mounting the same Router at /api/auth and /auth is brittle in Express 5.
app.use('/api/auth', authRoutes(pool, JWT_SECRET, authLimiter, authenticateToken));
app.use('/auth', authRoutes(pool, JWT_SECRET, authLimiter, authenticateToken));
app.get('/', (_req, res) => {
    res.send('Berkeley Workforce 360 API Running');
});
app.use('/', hrRoutes(pool, authenticateToken, authorizeRole, bcrypt, jwt, JWT_SECRET, null, null, io, runAutoCheckout, async () => {}, DATA_RETENTION_DAYS, metrics));
app.use('/', employeeRoutes(pool, authenticateToken, locationLimiter, isDuringShift, io));

const PORT = process.env.PORT || 3000;
const startServer = async () => {
    await initializeStartupData(pool);
    await setupSocketAdapter();
    registerSocketHandlers({ io, pool, isDuringShift, metrics, jwt, JWT_SECRET });
    setupMaintenanceSchedulers({ pool, APP_TIMEZONE, DATA_RETENTION_DAYS });
    scheduleAutoCheckout();
    server.listen(PORT, () => {
        console.log(`Server running on port ${PORT}`);
    });
};

startServer().catch((err) => {
    console.error('[FATAL] Failed to start server:', err);
    process.exit(1);
});
