const express = require('express');
const { APP_TIMEZONE } = require('../utils/time');
const { organizationIdFromUser } = require('../utils/organization');
const { z } = require('zod');
const registerUsersRoutes = require('./hr/users');
const registerAttendanceGovernanceRoutes = require('./hr/attendanceGovernance');
const { toPublic: emailMessagingToPublic } = require('../services/orgEmailMessagingSettings');

const siteSchema = z.object({
    name: z.string().trim().min(1, 'Site name is required'),
    location: z.string().trim().max(200).optional().nullable(),
    latitude: z.union([z.number(), z.string()]).optional().nullable(),
    longitude: z.union([z.number(), z.string()]).optional().nullable(),
    radiusMeters: z.union([z.number(), z.string()]).optional().nullable(),
    geofenceType: z.enum(['CIRCLE', 'POLYGON']).optional(),
    geofenceData: z.any().optional().nullable(),
    geofenceEnabled: z.boolean().optional(),
    nfcPayload: z.string().trim().max(255).optional().nullable(),
});

const shiftSchema = z.object({
    name: z.string().trim().min(1, 'Shift name is required'),
    startTime: z.string().regex(/^\d{2}:\d{2}(:\d{2})?$/, 'startTime must be HH:MM or HH:MM:SS'),
    endTime: z.string().regex(/^\d{2}:\d{2}(:\d{2})?$/, 'endTime must be HH:MM or HH:MM:SS'),
});

module.exports = (
    pool,
    authenticateToken,
    authorizeRole,
    bcrypt,
    jwt,
    JWT_SECRET,
    getGeofenceAlerts,
    broadcastGeofenceAlert,
    io,
    runAutoCheckout,
    runOdooSync,
    DATA_RETENTION_DAYS,
    metrics
) => {
    if (typeof runOdooSync !== 'function') {
        metrics = DATA_RETENTION_DAYS;
        DATA_RETENTION_DAYS = runOdooSync;
        runOdooSync = async () => { };
    }
    const router = express.Router();

    registerUsersRoutes({ router, pool, authenticateToken, authorizeRole, bcrypt, io });
    registerAttendanceGovernanceRoutes({ router, pool, authenticateToken, authorizeRole });

    // Helper to extract JWT if some functions need it

    // HR API: Get global settings
    router.get('/hr/settings', authenticateToken, async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                'SELECT key, value FROM settings WHERE organization_id = $1',
                [orgId]
            );
            const settings = {};
            result.rows.forEach((r) => {
                if (r.key === 'email_messaging') {
                    const raw = typeof r.value === 'object' && r.value && !Array.isArray(r.value) ? r.value : {};
                    settings[r.key] = emailMessagingToPublic(raw);
                } else {
                    settings[r.key] = r.value;
                }
            });
            res.json(settings);
        } catch (err) {
            console.error('Error fetching settings:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/organization', authenticateToken, async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                'SELECT id, slug, name, created_at FROM organizations WHERE id = $1 LIMIT 1',
                [orgId]
            );
            if (result.rowCount === 0) return res.status(404).json({ error: 'Organization not found' });
            return res.json(result.rows[0]);
        } catch (err) {
            console.error('Error fetching organization:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Update global settings
    router.post('/hr/settings', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { key, value } = req.body;
        if (!key) return res.status(400).json({ error: 'Missing key' });
        try {
            const orgId = organizationIdFromUser(req.user);
            await pool.query(
                `INSERT INTO settings (organization_id, key, value)
                 VALUES ($1, $2, $3::jsonb)
                 ON CONFLICT (organization_id, key) DO UPDATE SET value = EXCLUDED.value`,
                [orgId, key, JSON.stringify(value)]
            );
            res.json({ message: 'Setting updated' });
        } catch (err) {
            console.error('Error updating setting:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Get all employees

    // ... (other routes unchanged)

    // HR API: Create/Update user


    // HR API: Get recent attendance (Filtered by site for Supervisors)

    // HR API: Manual Check-In (supervisor logs check-in for an employee)

    // HR API: Manual Check-Out (supervisor logs check-out for an employee)

    // HR API: Get attendance report data


    // --- BIOMETRIC ATTENDANCE REPORT DEDICATED ENDPOINT ---

    // Audit Log Helper
    const logAudit = async (actorId, action, targetId = null, details = '') => {
        try {
            await pool.query(
                'INSERT INTO audit_logs (actor_id, action, target_id, details) VALUES ($1, $2, $3, $4)',
                [actorId, action, targetId, details]
            );
        } catch (err) {
            console.error('Audit log error:', err);
        }
    };

    // HR API: Get all sites
    router.get('/hr/sites', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor', 'Payroll', 'Finance']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                'SELECT * FROM sites WHERE organization_id = $1 ORDER BY name ASC',
                [orgId]
            );
            res.json(result.rows);
        } catch (err) {
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Create site
    router.post('/hr/sites', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = siteSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid site payload' });
        }
        const { name, location, latitude, longitude, radiusMeters, geofenceType, geofenceData, geofenceEnabled, nfcPayload } = parsed.data;
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                `INSERT INTO sites (organization_id, name, location, latitude, longitude, radius_meters, geofence_type, geofence_data, geofence_enabled, nfc_payload)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING *`,
                [orgId, name, location, latitude, longitude, radiusMeters || 100, geofenceType || 'CIRCLE', JSON.stringify(geofenceData), geofenceEnabled !== false, nfcPayload || null]
            );
            res.json(result.rows[0]);
        } catch (err) {
            console.error('Error creating site:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Update site
    router.patch('/hr/sites/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { id } = req.params;
        const parsed = siteSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid site payload' });
        }
        const { name, location, latitude, longitude, radiusMeters, geofenceType, geofenceData, geofenceEnabled, nfcPayload } = parsed.data;
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                `UPDATE sites SET name = $1, location = $2, latitude = $3, longitude = $4, radius_meters = $5, geofence_type = $6, geofence_data = $7, geofence_enabled = $8, nfc_payload = $9
                 WHERE id = $10 AND organization_id = $11 RETURNING *`,
                [name, location, latitude, longitude, radiusMeters, geofenceType, JSON.stringify(geofenceData), geofenceEnabled !== false, nfcPayload || null, id, orgId]
            );
            if (result.rows.length === 0) return res.status(404).json({ error: 'Site not found' });
            res.json(result.rows[0]);
        } catch (err) {
            console.error('Error updating site:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Get all roles (with permissions)
    router.get('/hr/roles', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor', 'Payroll', 'Finance']), async (req, res) => {
        try {
            const query = `
            SELECT r.id, r.name, 
                   COALESCE(
                       json_agg(
                           json_build_object('id', p.id, 'name', p.name, 'description', p.description)
                       ) FILTER (WHERE p.id IS NOT NULL),
                       '[]'
                   ) as permissions
            FROM roles r
            LEFT JOIN role_permissions rp ON r.id = rp.role_id
            LEFT JOIN permissions p ON rp.permission_id = p.id
            GROUP BY r.id
            ORDER BY r.name ASC
        `;
            const result = await pool.query(query);
            res.json(result.rows);
        } catch (err) {
            console.error('Error fetching roles:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Get all available permissions
    router.get('/hr/permissions', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            const result = await pool.query('SELECT * FROM permissions ORDER BY name ASC');
            res.json(result.rows);
        } catch (err) {
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Update role permissions
    router.post('/hr/roles/:id/permissions', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { id } = req.params;
        const { permissionIds } = req.body; // Array of permission IDs

        if (!Array.isArray(permissionIds)) {
            return res.status(400).json({ error: 'permissionIds must be an array' });
        }

        const client = await pool.connect();
        try {
            await client.query('BEGIN');

            // 1. Remove existing permissions for this role
            await client.query('DELETE FROM role_permissions WHERE role_id = $1', [id]);

            // 2. Insert new permissions
            if (permissionIds.length > 0) {
                // Generate value placeholders like ($1, $2), ($1, $3), ...
                // simpler loop is fine for moderate size
                for (const permId of permissionIds) {
                    await client.query(
                        'INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2)',
                        [id, permId]
                    );
                }
            }

            await client.query('COMMIT');
            res.json({ message: 'Permissions updated successfully' });
        } catch (err) {
            await client.query('ROLLBACK');
            console.error('Error updating role permissions:', err);
            res.status(500).json({ error: 'Database error' });
        } finally {
            client.release();
        }
    });

    // HR API: Get all users (paginated) - Updated

    // HR API: Delete or Archive user



    // HR API: Bulk update user fields (Shift, Site, Dept)
    // ── Biometrics API ──────────────────────────────────────────────────────────






    // Internal endpoint for RA08 listener (Basic shared token auth)

    // HR Admin: Data Cleanup Stats
    router.get('/hr/admin/metrics', authenticateToken, authorizeRole(['HR Admin']), async (_req, res) => {
        try {
            return res.json(metrics.snapshot());
        } catch (err) {
            console.error('Metrics snapshot error:', err);
            return res.status(500).json({ error: 'Metrics unavailable' });
        }
    });

    // HR Admin: Data Cleanup Stats
    router.get('/hr/admin/cleanup-stats', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            const [logsCount, logsOldest, alertsCount, alertsOldest, logsSize] = await Promise.all([
                pool.query('SELECT COUNT(*) FROM live_logs'),
                pool.query('SELECT MIN(timestamp) as oldest FROM live_logs'),
                pool.query('SELECT COUNT(*) FROM geo_fence_alerts'),
                pool.query('SELECT MIN(created_at) as oldest FROM geo_fence_alerts'),
                pool.query(`SELECT pg_size_pretty(pg_total_relation_size('live_logs')) as size`)
            ]);

            res.json({
                retentionDays: DATA_RETENTION_DAYS,
                nextCleanup: `Daily at 02:00 ${APP_TIMEZONE}`,
                live_logs: {
                    totalRows: parseInt(logsCount.rows[0].count),
                    oldestRecord: logsOldest.rows[0].oldest,
                    tableSize: logsSize.rows[0].size
                },
                geo_fence_alerts: {
                    totalRows: parseInt(alertsCount.rows[0].count),
                    oldestRecord: alertsOldest.rows[0].oldest
                }
            });
        } catch (err) {
            console.error('Cleanup stats error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR Admin: Manually trigger data cleanup (on-demand)
    router.post('/hr/admin/run-cleanup', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const started = Date.now();
        try {
            const retentionDays = req.body.retentionDays || DATA_RETENTION_DAYS;
            console.log(`[CLEANUP] Manual cleanup triggered by ${req.user.staffId}. Retention: ${retentionDays} days.`);

            const logsResult = await pool.query(
                `DELETE FROM live_logs WHERE timestamp < NOW() - INTERVAL '${parseInt(retentionDays)} days'`
            );
            const alertsResult = await pool.query(
                `DELETE FROM geo_fence_alerts
             WHERE created_at < NOW() - INTERVAL '${parseInt(retentionDays)} days'
               AND status = 'resolved'`
            );

            const elapsed = ((Date.now() - started) / 1000).toFixed(2);
            console.log(`[CLEANUP] Manual cleanup done in ${elapsed}s: live_logs=${logsResult.rowCount}, alerts=${alertsResult.rowCount}`);

            res.json({
                success: true,
                deleted: {
                    live_logs: logsResult.rowCount,
                    geo_fence_alerts: alertsResult.rowCount
                },
                retentionDays,
                elapsed: `${elapsed}s`
            });
        } catch (err) {
            console.error('[CLEANUP] Manual cleanup error:', err);
            res.status(500).json({ error: 'Cleanup failed', message: err.message });
        }
    });

    // HR Admin: View Auto-Closed attendance records

    // HR Admin: Manually trigger auto-checkout job now
    router.post('/hr/admin/auto-checkout/run', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        console.log(`[AUTO-CHECKOUT] Manual run triggered by ${req.user.staffId}`);
        // Run async — respond immediately then process
        res.json({ success: true, message: 'Auto-checkout job started. Check logs for results.' });
        runAutoCheckout();
    });

    // HR API: Get all shifts


    router.get('/hr/shifts', authenticateToken, authorizeRole(['HR Admin', 'Payroll', 'Finance']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                'SELECT * FROM shifts WHERE organization_id = $1 ORDER BY name ASC',
                [orgId]
            );
            res.json(result.rows);
        } catch (err) {
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Create shift
    router.post('/hr/shifts', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = shiftSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid shift payload' });
        }
        const { name, startTime, endTime } = parsed.data;
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                'INSERT INTO shifts (organization_id, name, start_time, end_time) VALUES ($1, $2, $3, $4) RETURNING *',
                [orgId, name, startTime, endTime]
            );
            res.json(result.rows[0]);
        } catch (err) {
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Update shift
    router.put('/hr/shifts/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { id } = req.params;
        const parsed = shiftSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid shift payload' });
        }
        const { name, startTime, endTime } = parsed.data;
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                'UPDATE shifts SET name = $1, start_time = $2, end_time = $3 WHERE id = $4 AND organization_id = $5 RETURNING *',
                [name, startTime, endTime, id, orgId]
            );
            if (result.rows.length === 0) {
                return res.status(404).json({ error: 'Shift not found' });
            }
            res.json(result.rows[0]);
        } catch (err) {
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Get Alerts (paginated, filterable)

    // HR API: Resolve a geo-fence alert

    // HR API: Bulk resolve geo-fence alerts


    // HR API: Delete a single location log entry

    // HR API: Bulk delete location logs (by employee and/or date range)

    // HR API: Get Route Tracking Data



    // Socket.io Middleware: Authenticate
    io.use((socket, next) => {
        const token = socket.handshake.auth.token;
        if (!token) {
            return next(new Error("Authentication error"));
        }
        jwt.verify(token, JWT_SECRET, (err, decoded) => {
            if (err) {
                return next(new Error("Authentication error"));
            }
            socket.user = decoded;
            next();
        });
    });

    return router;
};