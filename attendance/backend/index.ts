export { };

require('dotenv').config();
const { assertProductionBiometricsConfig } = require('./utils/productionEnvCheck');
assertProductionBiometricsConfig();

const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
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
const { createAttendanceSyncRunner } = require('./services/odooSync');
const createZktecoIclockRouter = require('./routes/zktecoIclock');

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

app.use('/hr/', apiLimiter);
app.use(cors(corsOptions));
app.use(express.json({ limit: '50mb' }));
app.use(cookieParser());
app.use(express.urlencoded({ limit: '50mb', extended: true }));

/** ZKTeco iClock / ADMS push (plain-text bodies; no JWT — register device_key = terminal SN) */
app.use(
    '/iclock',
    express.text({ type: '*/*', limit: '15mb', defaultCharset: 'utf-8' }),
    createZktecoIclockRouter(pool)
);

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
const { run: runOdooSync, schedule: scheduleOdooSync } = createAttendanceSyncRunner({
    pool,
    metrics
});

app.use('/auth', authRoutes(pool, JWT_SECRET, authLimiter));
app.get('/', (_req, res) => {
    res.send('Berkeley Workforce 360 API Running');
});
app.use('/', hrRoutes(pool, authenticateToken, authorizeRole, bcrypt, jwt, JWT_SECRET, null, null, io, runAutoCheckout, runOdooSync, DATA_RETENTION_DAYS, metrics));
app.use('/', employeeRoutes(pool, authenticateToken, locationLimiter, isDuringShift, io));

registerSocketHandlers({ io, pool, isDuringShift, metrics });

setupMaintenanceSchedulers({ pool, APP_TIMEZONE, DATA_RETENTION_DAYS });
scheduleAutoCheckout();
scheduleOdooSync();
initializeStartupData(pool);

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
