export { };

const express = require('express');
const http = require('http');
const { Server } = require("socket.io");
const cors = require('cors');
const { Pool } = require('pg');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const rateLimit = require('express-rate-limit');
const cron = require('node-cron');
require('dotenv').config();
const fs = require('fs');
const path = require('path');
const authRoutes = require('./routes/auth'); // Added this line

const JWT_SECRET = process.env.JWT_SECRET || 'fallback_secret';

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    }
});

// Trust the Nginx reverse proxy so rate limiting uses the real client IP
app.set('trust proxy', 1);

// ── Rate Limiters ───────────────────────────────────────────────────────────

// 1. Auth limiter — strict: 10 attempts per 15 minutes per IP
//    Prevents brute-force attacks on /auth/login
const authLimiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 10,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Too many login attempts. Please try again in 15 minutes.' },
    handler: (req, res, next, options) => {
        console.warn(`[RATE LIMIT] Auth blocked: IP=${req.ip} after ${options.max} attempts`);
        res.status(429).json(options.message);
    }
});

// 2. Location update limiter — 120 requests per minute per IP
//    Allows frequent GPS pings while blocking floods
const locationLimiter = rateLimit({
    windowMs: 60 * 1000, // 1 minute
    max: 120,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Location update rate limit exceeded. Maximum 2 updates per second.' },
    handler: (req, res, next, options) => {
        console.warn(`[RATE LIMIT] Location flood blocked: IP=${req.ip}`);
        res.status(429).json(options.message);
    }
});

// 3. General HR API limiter — 300 requests per minute per IP
//    Protects all /hr/* endpoints from scraping or abuse
const apiLimiter = rateLimit({
    windowMs: 60 * 1000, // 1 minute
    max: 300,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'API rate limit exceeded. Please slow down.' },
    handler: (req, res, next, options) => {
        console.warn(`[RATE LIMIT] API abuse blocked: IP=${req.ip} on ${req.path}`);
        res.status(429).json(options.message);
    },
    skip: (req) => {
        // Skip rate limiting for internal health checks
        return req.path === '/';
    }
});

// Apply general API limiter to all HR routes up-front
// Individual limiters override this for specific routes below
app.use('/hr/', apiLimiter);

// ────────────────────────────────────────────────────────────────────────────

// Database pool
const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgres://user:password@db:5432/attendance'
});

// Seeding Function
const seedPermissions = async () => {
    try {
        console.log('Seeding permissions...');

        // 1. Roles
        await pool.query("INSERT INTO roles (name) VALUES ('HR Admin'), ('Site Supervisor'), ('Payroll'), ('Employee') ON CONFLICT (name) DO NOTHING");

        // 2. Permissions
        const permissions = [
            { name: 'view_dashboard', description: 'Access to HR Dashboard' },
            { name: 'manage_staff', description: 'Add/Edit Staff Members' },
            { name: 'view_map', description: 'View Live Map' },
            { name: 'manage_sites', description: 'Add/Edit Sites' },
            { name: 'view_reports', description: 'View Attendance Reports' },
            { name: 'export_data', description: 'Export Data to CSV' },
            { name: 'view_attendance', description: 'View Attendance Logs' }
        ];

        for (const p of permissions) {
            await pool.query(
                "INSERT INTO permissions (name, description) VALUES ($1, $2) ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description",
                [p.name, p.description]
            );
        }

        // 3. Map Roles
        const roleMap = {
            'HR Admin': ['view_dashboard', 'manage_staff', 'view_map', 'manage_sites', 'view_reports', 'export_data', 'view_attendance'],
            'Site Supervisor': ['view_dashboard', 'view_map', 'view_attendance', 'view_reports'],
            'Payroll': ['view_dashboard', 'view_reports', 'export_data']
        };

        for (const [roleName, perms] of Object.entries(roleMap)) {
            const roleRes = await pool.query("SELECT id FROM roles WHERE name = $1", [roleName]);
            if (roleRes.rows.length === 0) continue;
            const roleId = roleRes.rows[0].id;

            for (const permName of perms) {
                const permRes = await pool.query("SELECT id FROM permissions WHERE name = $1", [permName]);
                if (permRes.rows.length === 0) continue;
                const permId = permRes.rows[0].id;

                await pool.query(
                    "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) ON CONFLICT (role_id, permission_id) DO NOTHING",
                    [roleId, permId]
                );
            }
        }
        console.log('Permissions seeded successfully.');
    } catch (err) {
        console.error('Seeding error:', err);
    }
};

// Migration for Photos, Shifts, and Geo-Fencing
const runMigrations = async () => {
    try {
        await pool.query('ALTER TABLE employees ADD COLUMN IF NOT EXISTS photo_url VARCHAR(255)');

        // 1. Shifts Table
        await pool.query(`
            CREATE TABLE IF NOT EXISTS shifts (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        `);

        // 2. Employees - Shift ID
        await pool.query(`
            ALTER TABLE employees 
            ADD COLUMN IF NOT EXISTS shift_id INTEGER REFERENCES shifts(id);
        `);

        // 3. Sites - explicit lat/long/radius
        await pool.query(`
            ALTER TABLE sites 
            ADD COLUMN IF NOT EXISTS latitude DECIMAL(10, 8),
            ADD COLUMN IF NOT EXISTS longitude DECIMAL(11, 8),
            ADD COLUMN IF NOT EXISTS radius_meters INTEGER DEFAULT 100,
            ADD COLUMN IF NOT EXISTS geofence_type VARCHAR(20) DEFAULT 'CIRCLE',
            ADD COLUMN IF NOT EXISTS geofence_data JSONB,
            ADD COLUMN IF NOT EXISTS geofence_enabled BOOLEAN DEFAULT true,
            ADD COLUMN IF NOT EXISTS nfc_payload VARCHAR(255);
        `);

        // 4. Geo Fence Alerts Table
        await pool.query(`
            CREATE TABLE IF NOT EXISTS geo_fence_alerts (
                id SERIAL PRIMARY KEY,
                employee_id INTEGER REFERENCES employees(id),
                site_id INTEGER REFERENCES sites(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                latitude DECIMAL(10, 8),
                longitude DECIMAL(11, 8),
                message TEXT,
                status VARCHAR(20) DEFAULT 'active'
            );
        `);

        // 5. Default Shifts
        await pool.query(`
            INSERT INTO shifts (name, start_time, end_time) 
            VALUES 
            ('Morning Shift', '08:00', '17:00'),
            ('Night Shift', '20:00', '05:00')
            ON CONFLICT (name) DO NOTHING;
        `);

        // 6. Attendance: notes + auto_closed flag (idempotent)
        await pool.query(`ALTER TABLE attendance ADD COLUMN IF NOT EXISTS notes TEXT`);
        await pool.query(`ALTER TABLE attendance ADD COLUMN IF NOT EXISTS auto_closed BOOLEAN DEFAULT false`);

        // 7. Biometric Devices Table
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

        // 8. Biometric Logs Table
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

        console.log('Migrations: Schema updated for Shifts, Geo-Fencing, and Biometrics.');
    } catch (err) {
        console.error('Migration error:', err);
    }
};

// Run Seeding and Migration on startup
seedPermissions();
runMigrations();

// ── Scheduled Cleanup Jobs (node-cron) ─────────────────────────────────────────────────

const DATA_RETENTION_DAYS = parseInt(process.env.DATA_RETENTION_DAYS || '180');

/**
 * Daily Cleanup Job — runs every day at 02:00 AM server time
 * Deletes live_logs and geo_fence_alerts older than DATA_RETENTION_DAYS (default 90).
 */
cron.schedule('0 2 * * *', async () => {
    const started = Date.now();
    console.log(`[CLEANUP] Starting daily data cleanup (retention: ${DATA_RETENTION_DAYS} days)...`);
    try {
        // 1. Prune live_logs
        const logsResult = await pool.query(
            `DELETE FROM live_logs WHERE timestamp < NOW() - INTERVAL '${DATA_RETENTION_DAYS} days'`
        );
        console.log(`[CLEANUP] live_logs: deleted ${logsResult.rowCount} rows.`);

        // 2. Prune geo_fence_alerts (resolved ones older than retention; keep active regardless)
        const alertsResult = await pool.query(
            `DELETE FROM geo_fence_alerts
             WHERE created_at < NOW() - INTERVAL '${DATA_RETENTION_DAYS} days'
               AND status = 'resolved'`
        );
        console.log(`[CLEANUP] geo_fence_alerts (resolved): deleted ${alertsResult.rowCount} rows.`);

        const elapsed = ((Date.now() - started) / 1000).toFixed(2);
        console.log(`[CLEANUP] Daily cleanup completed in ${elapsed}s.`);
    } catch (err) {
        console.error('[CLEANUP] Daily cleanup error:', err.message);
    }
}, {
    timezone: 'Asia/Dubai'  // UTC+4 — adjust if needed
});

/**
 * Weekly VACUUM Job — runs every Sunday at 03:00 AM
 * Reclaims disk space from deleted rows. VACUUM ANALYZE also updates
 * query planner statistics so queries stay fast after bulk deletes.
 */
cron.schedule('0 3 * * 0', async () => {
    console.log('[CLEANUP] Starting weekly VACUUM ANALYZE...');
    try {
        // VACUUM cannot run inside a transaction, pool.query runs outside one by default
        await pool.query('VACUUM ANALYZE live_logs');
        await pool.query('VACUUM ANALYZE geo_fence_alerts');
        console.log('[CLEANUP] VACUUM ANALYZE completed.');
    } catch (err) {
        console.error('[CLEANUP] VACUUM error:', err.message);
    }
}, {
    timezone: 'Asia/Dubai'
});

console.log(`[CLEANUP] Scheduled: daily pruning at 02:00, weekly VACUUM at Sunday 03:00 (Asia/Dubai). Retention: ${DATA_RETENTION_DAYS} days.`);

// ── Auto Check-Out Cron Job ─────────────────────────────────────────────────
//
// Runs every 30 minutes. Finds open attendance records where:
//  (a) Employee HAS a shift  → auto-close if NOW > shift_end + 2 hours
//  (b) Employee has NO shift → auto-close if check_in_time is > 10 hours ago
// Sets check_out_time, marks auto_closed=true, writes a note, and emits
// a real-time socket event to the HR dashboard.

const AUTO_CHECKOUT_GRACE_HOURS = parseInt(process.env.AUTO_CHECKOUT_GRACE_HOURS || '2');
const AUTO_CHECKOUT_NO_SHIFT_HOURS = parseInt(process.env.AUTO_CHECKOUT_NO_SHIFT_HOURS || '10');

const runAutoCheckout = async () => {
    const started = Date.now();
    try {
        // Find all open attendance records, joined with shift info
        const openRecords = await pool.query(`
            SELECT
                a.id          AS attendance_id,
                a.check_in_time,
                a.employee_id,
                a.site_id,
                e.staff_id,
                e.first_name,
                e.last_name,
                sh.name       AS shift_name,
                sh.end_time   AS shift_end_time
            FROM attendance a
            JOIN employees e ON a.employee_id = e.id
            LEFT JOIN shifts sh ON e.shift_id = sh.id
            WHERE a.check_out_time IS NULL
        `);

        if (openRecords.rows.length === 0) return;

        const now = new Date();
        const toClose = [];

        for (const row of openRecords.rows) {
            let shouldClose = false;
            let reason = '';

            if (row.shift_end_time) {
                // Build today's shift-end datetime (handle overnight shifts)
                const [endHour, endMin] = row.shift_end_time.split(':').map(Number);
                const checkInDate = new Date(row.check_in_time);

                // Start from check-in date so overnight shifts resolve correctly
                const shiftEnd = new Date(checkInDate);
                shiftEnd.setHours(endHour, endMin, 0, 0);

                // If shift end is before check-in (overnight), push to next day
                if (shiftEnd <= checkInDate) shiftEnd.setDate(shiftEnd.getDate() + 1);

                const cutoff = new Date(shiftEnd.getTime() + AUTO_CHECKOUT_GRACE_HOURS * 60 * 60 * 1000);

                if (now >= cutoff) {
                    shouldClose = true;
                    reason = `Auto closed: shift ended at ${row.shift_end_time} (${row.shift_name}), grace period of ${AUTO_CHECKOUT_GRACE_HOURS}h exceeded.`;
                }
            } else {
                // No shift assigned — use max check-in duration
                const checkInAge = (now.getTime() - new Date(row.check_in_time).getTime()) / 3600000; // hours
                if (checkInAge >= AUTO_CHECKOUT_NO_SHIFT_HOURS) {
                    shouldClose = true;
                    reason = `Auto closed: no shift assigned and check-in was ${checkInAge.toFixed(1)}h ago (limit: ${AUTO_CHECKOUT_NO_SHIFT_HOURS}h).`;
                }
            }

            if (shouldClose) toClose.push({ ...row, reason });
        }

        if (toClose.length === 0) return;

        console.log(`[AUTO-CHECKOUT] Closing ${toClose.length} open record(s)...`);

        for (const record of toClose) {
            await pool.query(
                `UPDATE attendance
                 SET check_out_time = NOW(),
                     auto_closed    = true,
                     notes          = $1
                 WHERE id = $2 AND check_out_time IS NULL`,
                [record.reason, record.attendance_id]
            );

            console.log(`[AUTO-CHECKOUT] Closed attendance #${record.attendance_id} for ${record.staff_id}: ${record.reason}`);

            // Notify HR dashboard in real time
            io.to('hr-dashboard').emit('auto_checkout', {
                attendanceId: record.attendance_id,
                staffId: record.staff_id,
                name: [record.first_name, record.last_name].filter(Boolean).join(' '),
                siteId: record.site_id,
                checkInTime: record.check_in_time,
                checkOutTime: new Date().toISOString(),
                reason: record.reason
            });
        }

        const elapsed = ((Date.now() - started) / 1000).toFixed(2);
        console.log(`[AUTO-CHECKOUT] Done. Closed ${toClose.length} record(s) in ${elapsed}s.`);
    } catch (err) {
        console.error('[AUTO-CHECKOUT] Error:', err.message);
    }
};

// Run every 30 minutes
cron.schedule('*/30 * * * *', runAutoCheckout, { timezone: 'Asia/Dubai' });
console.log(`[AUTO-CHECKOUT] Scheduled every 30 min. Grace: ${AUTO_CHECKOUT_GRACE_HOURS}h after shift end. No-shift limit: ${AUTO_CHECKOUT_NO_SHIFT_HOURS}h.`);

// ────────────────────────────────────────────────────────────────────────────

app.use(cors());
// Configure body parser for larger payloads (photos)
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

// Serve uploaded photos statically under /uploads (Nginx proxies /api to backend and may strip prefix)
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

// Ensure uploads directory exists
if (!fs.existsSync('uploads')) {
    fs.mkdirSync('uploads');
}

// Helper to save base64 image
const saveBase64Image = (base64String, staffId) => {
    try {
        if (!base64String || !base64String.startsWith('data:image')) return null;

        const matches = base64String.match(/^data:image\/([A-Za-z-+\/]+);base64,(.+)$/);
        if (!matches || matches.length !== 3) return null;

        const type = matches[1];
        const data = matches[2];
        const buffer = Buffer.from(data, 'base64');

        const fileName = `${staffId}_${Date.now()}.${type}`;
        const filePath = path.join('uploads', fileName);

        fs.writeFileSync(filePath, buffer);
        return `/api/uploads/${fileName}`;
    } catch (err) {
        console.error('Error saving image:', err);
        return null;
    }
};

// Helper: Calculate Distance (Haversine Formula) in meters
const calculateDistance = (lat1, lon1, lat2, lon2) => {
    const R = 6371e3; // metres
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180; // φ, λ in radians
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;

    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
        Math.cos(φ1) * Math.cos(φ2) *
        Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    const d = R * c; // in metres
    return d;
};

// Helper: Check if current time is within shift timings (Asia/Dubai)
const isDuringShift = (startTime, endTime) => {
    if (!startTime || !endTime) return true;

    try {
        const dubaiStr = new Date().toLocaleString('en-US', { timeZone: 'Asia/Dubai' });
        const dubaiNow = new Date(dubaiStr);
        const currentSeconds = dubaiNow.getHours() * 3600 + dubaiNow.getMinutes() * 60 + dubaiNow.getSeconds();

        const toSeconds = (t) => {
            const [h, m, s] = t.split(':').map(Number);
            return h * 3600 + (m || 0) * 60 + (s || 0);
        };

        const start = toSeconds(startTime);
        const end = toSeconds(endTime);

        if (start <= end) {
            return currentSeconds >= start && currentSeconds <= end;
        } else {
            // crosses midnight
            return currentSeconds >= start || currentSeconds <= end;
        }
    } catch (e) {
        console.error('Shift check error:', e);
        return true;
    }
};

// Ray-casting algorithm to check if a point is inside a polygon
const isPointInPolygon = (lat, lng, polygon) => {
    let inside = false;
    const x = lng, y = lat;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i].lng, yi = polygon[i].lat;
        const xj = polygon[j].lng, yj = polygon[j].lat;
        const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
};

// Debug endpoint for remote Android logging
app.post('/debug/log', (req, res) => {
    console.log(`[PHONE_LOG] ${req.body.tag}: ${req.body.msg}`);
    res.sendStatus(200);
});

// App-wide logging
app.use((req, res, next) => { console.log(`${req.method} ${req.url}`); next(); });

// Middleware: Authenticate JWT
const authenticateToken = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) return res.status(401).json({ error: 'Access denied' });

    jwt.verify(token, JWT_SECRET, (err, user) => {
        if (err) {
            console.warn('Auth failed: Invalid token', err.message);
            return res.status(403).json({ error: 'Invalid token' });
        }
        req.user = user;
        next();
    });
};

// Middleware: Authorize Roles
const authorizeRole = (roles) => {
    return (req, res, next) => {
        if (!roles.includes(req.user.role)) {
            console.warn(`Permission denied for user ${req.user.staffId}: Role ${req.user.role} not in [${roles.join(', ')}]`);
            return res.status(403).json({ error: 'Permission denied' });
        }
        next();
    };
};

// Mount Auth Route
app.use('/auth', authRoutes(pool, JWT_SECRET, authLimiter));

app.get('/', (req, res) => {
    res.send('Berkeley Workforce 360 API Running');
});

const hrRoutes = require('./routes/hr');
app.use('/', hrRoutes(pool, authenticateToken, authorizeRole, bcrypt, jwt, JWT_SECRET, null, null, io));
// Check Attendance Status
const employeeRoutes = require('./routes/employee');
app.use('/', employeeRoutes(pool, authenticateToken, locationLimiter, isDuringShift, io));
// Socket.io logic
io.on('connection', (socket) => {
    console.log('a user connected', socket.id);

    // Join HR Dashboard (Global)
    socket.on('join_hr', () => {
        socket.join('hr-dashboard');
        console.log('User joined Global HR dashboard');
    });

    // Join Site Dashboard (Restricted)
    socket.on('join_site', (siteId) => {
        socket.join(`hr-site:${siteId}`);
        console.log(`User joined Site HR dashboard: ${siteId}`);
    });

    socket.on('disconnect', () => {
        console.log('user disconnected', socket.id);
    });

    socket.on('location_update', async (data) => {
        try {
            const { employeeId, latitude, longitude } = data || {};
            if (!employeeId) {
                console.warn(`Location update: Missing employeeId from ${socket.id}`);
                return;
            }

            // Get Employee Details including Shift and Site
            const empRes = await pool.query(
                `SELECT e.id, e.site_id, e.department_name, e.photo_url,
                       s.latitude as site_lat, s.longitude as site_lon, s.radius_meters, s.name as site_name, s.geofence_type, s.geofence_data, s.geofence_enabled,
                       sh.start_time, sh.end_time
                 FROM employees e
                 LEFT JOIN sites s ON e.site_id = s.id
                 LEFT JOIN shifts sh ON e.shift_id = sh.id
                 WHERE e.staff_id = $1`,
                [employeeId]
            );

            if (empRes.rows.length > 0) {
                const {
                    id: internalId, site_id: siteId, department_name: departmentName, photo_url: photoUrl,
                    site_lat: siteLat, site_lon: siteLon, radius_meters: radiusMeters, site_name: siteName,
                    geofence_type: geofenceType, geofence_data: geofenceData, geofence_enabled: geofenceEnabled,
                    start_time: startTime, end_time: endTime
                } = empRes.rows[0];

                const payload = { ...data, siteId, departmentName, photoUrl };

                // 2. Broadcast to Global HR
                io.to('hr-dashboard').emit('employee_location', payload);

                // 3. Broadcast to Site HR (if site assigned)
                if (siteId) {
                    io.to(`hr-site:${siteId}`).emit('employee_location', payload);
                }

                // 4. Save to LiveLogs
                await pool.query(
                    'INSERT INTO live_logs (employee_id, current_coords) VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326))',
                    [internalId, longitude, latitude]
                );

                // 5. GEO FENCING CHECK
                if (siteId && geofenceEnabled !== false) {
                    // If shift assigned, only alert during shift window; otherwise alert anytime
                    let checkGeo = true;
                    if (startTime && endTime) {
                        const now = new Date();
                        const currentTimeVal = now.getHours() * 60 + now.getMinutes();
                        const [startH, startM] = startTime.split(':').map(Number);
                        const [endH, endM] = endTime.split(':').map(Number);
                        const startTimeVal = startH * 60 + startM;
                        const endTimeVal = endH * 60 + endM;
                        if (endTimeVal < startTimeVal) {
                            checkGeo = (currentTimeVal >= startTimeVal) || (currentTimeVal <= endTimeVal);
                        } else {
                            checkGeo = (currentTimeVal >= startTimeVal) && (currentTimeVal <= endTimeVal);
                        }
                    }

                    if (checkGeo) {
                        let isOutside = false;
                        let distance = 0;
                        let allowedRadius = radiusMeters || 100;

                        if (geofenceType === 'POLYGON' && geofenceData && Array.isArray(geofenceData)) {
                            const inside = isPointInPolygon(latitude, longitude, geofenceData);
                            if (!inside) {
                                isOutside = true;
                                if (siteLat && siteLon) {
                                    distance = calculateDistance(latitude, longitude, siteLat, siteLon);
                                }
                            }
                        } else if (siteLat && siteLon) {
                            distance = calculateDistance(latitude, longitude, siteLat, siteLon);
                            if (distance > allowedRadius) {
                                isOutside = true;
                            }
                        }

                        if (isOutside) {
                            console.log(`Geofence Alert: ${employeeId} is outside site ${siteName}`);
                            const recentAlert = await pool.query(
                                "SELECT id FROM geo_fence_alerts WHERE employee_id = $1 AND created_at > NOW() - INTERVAL '10 minutes'",
                                [internalId]
                            );
                            if (recentAlert.rows.length === 0) {
                                const context = startTime ? 'during shift hours' : 'while on duty';
                                const message = geofenceType === 'POLYGON'
                                    ? `${employeeId} outside designated polygon (${siteName}) ${context}.`
                                    : `${employeeId} outside site (${siteName}) ${context}. Distance: ${Math.round(distance)}m`;
                                const alertRes = await pool.query(
                                    `INSERT INTO geo_fence_alerts (employee_id, site_id, latitude, longitude, message) 
                                     VALUES ($1, $2, $3, $4, $5) RETURNING *`,
                                    [internalId, siteId, latitude, longitude, message]
                                );
                                const alertData = {
                                    ...alertRes.rows[0],
                                    staff_id: employeeId,
                                    site_name: siteName
                                };
                                io.to('hr-dashboard').emit('geo_fence_alert', alertData);
                                if (siteId) {
                                    io.to(`hr-site:${siteId}`).emit('geo_fence_alert', alertData);
                                }
                            }
                        }
                    }
                }

            } else {
                // If unregistered guest/test ID
                io.to('hr-dashboard').emit('employee_location', data);
            }
        } catch (err) {
            console.error('Error handling location update for', data?.employeeId, ':', err.message);
        }
    });

    socket.on('check_in', async (data) => {
        console.log('[SOCKET] check_in received:', data);
        let { employeeId, latitude, longitude } = data || {};
        if (!employeeId) {
            console.error('[SOCKET] check_in missing employeeId');
            return;
        }

        try {
            const empRes = await pool.query(`
                SELECT e.id, e.first_name, e.last_name, e.site_id, s.name as site_name, s.nfc_payload as site_nfc_payload 
                FROM employees e 
                LEFT JOIN sites s ON e.site_id = s.id 
                WHERE e.staff_id = $1
            `, [employeeId]);

            if (empRes.rows.length > 0) {
                const { id: internalId, first_name: firstName, last_name: lastName, site_id: siteId, site_name: siteName, site_nfc_payload: siteNfcPayload } = empRes.rows[0];

                if (siteNfcPayload && siteNfcPayload.trim().length > 0) {
                    if (!data.nfcPayload || data.nfcPayload !== siteNfcPayload) {
                        socket.emit('error', { message: 'NFC Scan Required. Please tap the correct NFC tag to Check In.' });
                        return;
                    }
                }

                // Fallback: If no coordinates provided, try fetching last known location
                if (!latitude || !longitude) {
                    console.log('[SOCKET] check_in: No coords provided, attempting fallback to live_logs...');
                    const locRes = await pool.query(
                        'SELECT ST_X(current_coords::geometry) as lon, ST_Y(current_coords::geometry) as lat FROM live_logs WHERE employee_id = $1 ORDER BY timestamp DESC LIMIT 1',
                        [internalId]
                    );
                    if (locRes.rows.length > 0) {
                        latitude = locRes.rows[0].lat;
                        longitude = locRes.rows[0].lon;
                        console.log(`[SOCKET] check_in: Fallback success: ${latitude}, ${longitude}`);
                    } else {
                        console.warn('[SOCKET] check_in: Fallback failed - no live_logs found.');
                        socket.emit('error', { message: 'Location data unavailable. Please enable GPS.' });
                        return;
                    }
                }

                // Check if already checked in
                const checkRes = await pool.query(
                    'SELECT id FROM attendance WHERE employee_id = $1 AND check_out_time IS NULL',
                    [internalId]
                );

                if (checkRes.rows.length > 0) {
                    socket.emit('error', { message: 'Already checked in' });
                    return;
                }

                await pool.query(
                    'INSERT INTO attendance (employee_id, check_in_time, check_in_coords, site_id) VALUES ($1, CURRENT_TIMESTAMP, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4)',
                    [internalId, longitude, latitude, siteId]
                );

                console.log('[SOCKET] check_in: Success, event emitted.');
                socket.emit('check_in_success');

                // Notify HR Managers
                const eventData = {
                    type: 'check_in',
                    employeeId,
                    firstName,
                    lastName,
                    siteId,
                    siteName,
                    timestamp: new Date()
                };
                io.to('hr-dashboard').emit('attendance_event', eventData);
                if (siteId) {
                    io.to(`hr-site:${siteId}`).emit('attendance_event', eventData);
                }
            }
        } catch (err) {
            console.error('Error on check-in:', err);
        }
    });

    socket.on('check_out', async (data) => {
        let { employeeId, latitude, longitude } = data || {};
        if (!employeeId) return;
        try {
            const empRes = await pool.query(`
                SELECT e.id, e.first_name, e.last_name, e.site_id, s.name as site_name, s.nfc_payload as site_nfc_payload
                FROM employees e
                LEFT JOIN sites s ON e.site_id = s.id
                WHERE e.staff_id = $1
            `, [employeeId]);

            if (empRes.rows.length > 0) {
                const { id: internalId, first_name: firstName, last_name: lastName, site_id: siteId, site_name: siteName, site_nfc_payload: siteNfcPayload } = empRes.rows[0];

                if (siteNfcPayload && siteNfcPayload.trim().length > 0) {
                    if (!data.nfcPayload || data.nfcPayload !== siteNfcPayload) {
                        socket.emit('error', { message: 'NFC Scan Required. Please tap the correct NFC tag to Check Out.' });
                        return;
                    }
                }

                // Fallback: If no coordinates provided, try fetching last known location
                if (!latitude || !longitude) {
                    const locRes = await pool.query(
                        'SELECT ST_X(current_coords::geometry) as lon, ST_Y(current_coords::geometry) as lat FROM live_logs WHERE employee_id = $1 ORDER BY timestamp DESC LIMIT 1',
                        [internalId]
                    );
                    if (locRes.rows.length > 0) {
                        latitude = locRes.rows[0].lat;
                        longitude = locRes.rows[0].lon;
                    } else {
                        // For checkout, we might allow lenient checkout? No, still need location.
                        socket.emit('error', { message: 'Location data unavailable. Please enable GPS.' });
                        return;
                    }
                }

                // Find active check-in
                const checkRes = await pool.query(
                    'UPDATE attendance SET check_out_time = CURRENT_TIMESTAMP, check_out_coords = ST_SetSRID(ST_MakePoint($1, $2), 4326) WHERE employee_id = $3 AND check_out_time IS NULL RETURNING id',
                    [longitude, latitude, internalId]
                );

                if (checkRes.rows.length > 0) {
                    socket.emit('check_out_success');

                    // Notify HR Managers
                    const eventData = {
                        type: 'check_out',
                        employeeId,
                        firstName,
                        lastName,
                        siteId,
                        siteName,
                        timestamp: new Date()
                    };
                    io.to('hr-dashboard').emit('attendance_event', eventData);
                    if (siteId) {
                        io.to(`hr-site:${siteId}`).emit('attendance_event', eventData);
                    }
                } else {
                    socket.emit('error', { message: 'Not checked in' });
                }
            }
        } catch (err) {
            console.error('Error on check-out:', err);
        }
    });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`Server running on port ${PORT} at CURRENT_TIME`);
});
