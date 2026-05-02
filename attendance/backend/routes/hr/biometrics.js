const { z } = require('zod');
const { ingestBiometricLog } = require('../../services/biometricIngest');
const { runBiometricConnectionTests } = require('../../services/biometricConnectionTest');

const MAX_CONFIG_JSON_BYTES = 24000;
const MAX_CONFIG_KEYS = 48;
const MAX_CONFIG_STRING_LEN = 2048;

/** Flat vendor/integration settings (push URLs, ports, UAE timezone, etc.) */
const sanitizeBiometricConfig = (raw) => {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
    const out = {};
    for (const [k, v] of Object.entries(raw)) {
        if (Object.keys(out).length >= MAX_CONFIG_KEYS) break;
        if (!/^[a-zA-Z0-9_]{1,80}$/.test(k)) continue;
        if (typeof v === 'string') {
            out[k] = v.length > MAX_CONFIG_STRING_LEN ? v.slice(0, MAX_CONFIG_STRING_LEN) : v;
        } else if (typeof v === 'number' && Number.isFinite(v)) {
            out[k] = v;
        } else if (typeof v === 'boolean') {
            out[k] = v;
        } else if (v === null) {
            out[k] = null;
        }
    }
    const json = JSON.stringify(out);
    if (json.length > MAX_CONFIG_JSON_BYTES) return {};
    return out;
};

const configField = z.any().optional().transform((val) => sanitizeBiometricConfig(val));

const biometricDeviceCreateSchema = z.object({
    name: z.string().trim().min(1, 'Device name is required'),
    deviceKey: z.string().trim().min(4, 'deviceKey is required'),
    siteId: z.union([z.number(), z.string()]).optional().nullable(),
    type: z.string().trim().min(1).optional().nullable(),
    ipAddress: z.string().trim().max(128).optional().nullable(),
    port: z.union([z.number(), z.string()]).optional().nullable(),
    config: configField.optional(),
});

const biometricDevicePatchSchema = z.object({
    name: z.string().trim().min(1).optional(),
    siteId: z.union([z.number(), z.string()]).optional().nullable(),
    type: z.string().trim().min(1).optional(),
    isActive: z.boolean().optional(),
    ipAddress: z.string().trim().max(128).optional().nullable(),
    port: z.union([z.number(), z.string()]).optional().nullable(),
    config: configField.optional(),
});

const biometricConnectionTestSchema = z.object({
    type: z.string().trim().optional().nullable(),
    deviceKey: z.string().trim().optional().nullable(),
    ipAddress: z.string().trim().max(128).optional().nullable(),
    port: z.union([z.number(), z.string()]).optional().nullable(),
    config: configField.optional(),
    excludeDeviceId: z.union([z.number(), z.string()]).optional().nullable(),
});

const biometricLogSchema = z.object({
    deviceKey: z.string().trim().min(1, 'deviceKey is required'),
    staffId: z.string().trim().min(1, 'staffId is required'),
    timestamp: z.string().trim().min(1, 'timestamp is required'),
    photoUrl: z.string().trim().optional().nullable(),
    rawData: z.any().optional().nullable(),
});

module.exports = ({ router, pool, authenticateToken, authorizeRole }) => {
    // ── Biometrics API ──────────────────────────────────────────────────────────

    router.get('/hr/biometrics/devices', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        try {
            const staleMinutes = parseInt(process.env.BIOMETRIC_STALE_MINS || '10', 10);
            const offlineMinutes = parseInt(process.env.BIOMETRIC_OFFLINE_MINS || '30', 10);
            const result = await pool.query(`
            SELECT b.*, s.name as site_name,
                   CASE
                     WHEN b.last_seen IS NULL THEN 'offline'
                     WHEN b.last_seen < NOW() - ($2 || ' minutes')::interval THEN 'offline'
                     WHEN b.last_seen < NOW() - ($1 || ' minutes')::interval THEN 'stale'
                     ELSE 'healthy'
                   END AS health_status
            FROM biometric_devices b 
            LEFT JOIN sites s ON b.site_id = s.id 
            ORDER BY b.name ASC
        `, [staleMinutes, offlineMinutes]);
            res.json(result.rows);
        } catch (err) {
            console.error('Error fetching biometric devices:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post(
        '/hr/biometrics/devices/connection-test',
        authenticateToken,
        authorizeRole(['HR Admin']),
        async (req, res) => {
            const parsed = biometricConnectionTestSchema.safeParse(req.body);
            if (!parsed.success) {
                return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid payload' });
            }
            try {
                const result = await runBiometricConnectionTests(pool, parsed.data, req);
                return res.json(result);
            } catch (err) {
                console.error('biometric connection-test error:', err);
                return res.status(500).json({ error: 'Connection test failed' });
            }
        }
    );

    router.post('/hr/biometrics/devices', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = biometricDeviceCreateSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid biometric device payload' });
        }
        const { name, deviceKey, siteId, type, ipAddress, port, config } = parsed.data;
        const portStr = port === undefined || port === null || port === '' ? null : String(port);
        const cfg = config !== undefined ? config : sanitizeBiometricConfig({});
        try {
            const result = await pool.query(
                `INSERT INTO biometric_devices (name, device_key, site_id, type, ip_address, port, config)
                 VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb) RETURNING *`,
                [name, deviceKey, siteId || null, type || 'RA08', ipAddress || null, portStr, JSON.stringify(cfg)]
            );
            res.json(result.rows[0]);
        } catch (err) {
            if (err && err.code === '23505') {
                return res.status(409).json({
                    error: 'A terminal with this device key already exists. Use a different serial or key.',
                });
            }
            console.error('Error creating biometric device:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.patch('/hr/biometrics/devices/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { id } = req.params;
        const parsed = biometricDevicePatchSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid biometric device payload' });
        }
        const { name, siteId, type, isActive, ipAddress, port, config } = parsed.data;
        const portStr = port === undefined || port === null || port === '' ? null : String(port);
        const configJson = config !== undefined ? JSON.stringify(config) : null;
        try {
            const result = await pool.query(
                `UPDATE biometric_devices SET
                    name = COALESCE($1, name),
                    site_id = COALESCE($2, site_id),
                    type = COALESCE($3, type),
                    is_active = COALESCE($4, is_active),
                    ip_address = COALESCE($5, ip_address),
                    port = COALESCE($6, port),
                    config = COALESCE($7::jsonb, config)
                 WHERE id = $8 RETURNING *`,
                [name, siteId === '' ? null : siteId, type, isActive, ipAddress || null, portStr, configJson, id]
            );
            res.json(result.rows[0]);
        } catch (err) {
            console.error('Error updating biometric device:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.delete('/hr/biometrics/devices/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            await pool.query('DELETE FROM biometric_devices WHERE id = $1', [req.params.id]);
            res.json({ success: true });
        } catch (err) {
            console.error('Error deleting biometric device:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/biometrics/logs', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { staffId, deviceId } = req.query;
        try {
            let query = `
            SELECT l.*, d.name as device_name, e.first_name, e.last_name 
            FROM biometric_logs l
            JOIN biometric_devices d ON l.device_id = d.id
            LEFT JOIN employees e ON l.employee_id = e.id
            WHERE 1=1
        `;
            const params = [];
            let pIdx = 1;

            if (staffId) {
                query += ` AND (l.staff_id = $${pIdx} OR e.staff_id = $${pIdx})`;
                params.push(staffId);
                pIdx++;
            }
            if (deviceId) {
                query += ` AND l.device_id = $${pIdx}`;
                params.push(deviceId);
                pIdx++;
            }

            query += ' ORDER BY l.timestamp DESC LIMIT 100';
            const result = await pool.query(query, params);
            res.json(result.rows);
        } catch (err) {
            console.error('Error fetching biometric logs:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // Internal endpoint for RA08 listener (Basic shared token auth)
    router.post('/api/biometrics/log', async (req, res) => {
        const authHeader = req.headers['authorization'];
        const token = authHeader && authHeader.split(' ')[1];
        const BIOMETRIC_INGEST_TOKEN = process.env.BIOMETRIC_INGEST_TOKEN || 'attendance_secret_token';

        if (token !== BIOMETRIC_INGEST_TOKEN) {
            console.warn(`[BIOMETRICS] Unauthorized log attempt with token: ${token}`);
            return res.status(403).json({ error: 'Forbidden' });
        }

        const parsed = biometricLogSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid biometric log payload' });
        }
        const { deviceKey, staffId, timestamp, photoUrl, rawData } = parsed.data;

        try {
            const result = await ingestBiometricLog(pool, {
                deviceKey,
                staffId,
                timestamp,
                photoUrl,
                rawData,
            });
            if (!result.ok) {
                return res.status(result.status).json({ error: result.error });
            }
            return res.json({ success: true });
        } catch (err) {
            console.error('Internal biometric log error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });
};
