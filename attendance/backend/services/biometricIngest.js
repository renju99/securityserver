/**
 * Shared biometric log write used by HTTP ingest and ZKTeco iClock adapter.
 */

/**
 * @param {import('pg').Pool} pool
 * @param {{ deviceKey: string; staffId: string; timestamp: string | Date; photoUrl?: string | null; rawData?: unknown }} input
 * @returns {Promise<{ ok: true } | { ok: false; status: number; error: string }>}
 */
async function ingestBiometricLog(pool, input) {
    const { deviceKey, staffId, timestamp, photoUrl, rawData } = input;
    if (!deviceKey || !staffId || !timestamp) {
        return { ok: false, status: 400, error: 'deviceKey, staffId, and timestamp are required' };
    }

    try {
        const deviceRes = await pool.query('SELECT id, site_id FROM biometric_devices WHERE device_key = $1', [deviceKey]);
        if (deviceRes.rows.length === 0) {
            return { ok: false, status: 404, error: 'Device not found' };
        }
        const deviceId = deviceRes.rows[0].id;

        const empRes = await pool.query('SELECT id FROM employees WHERE staff_id = $1', [staffId]);
        const employeeId = empRes.rows.length > 0 ? empRes.rows[0].id : null;

        const ts = timestamp instanceof Date ? timestamp : new Date(timestamp);
        if (Number.isNaN(ts.getTime())) {
            return { ok: false, status: 400, error: 'Invalid timestamp' };
        }

        await pool.query(
            'INSERT INTO biometric_logs (device_id, staff_id, employee_id, timestamp, photo_url, raw_data) VALUES ($1, $2, $3, $4, $5, $6)',
            [deviceId, staffId, employeeId, ts, photoUrl || null, JSON.stringify(rawData ?? {})]
        );

        await pool.query('UPDATE biometric_devices SET last_seen = NOW() WHERE id = $1', [deviceId]);

        return { ok: true };
    } catch (err) {
        console.error('[BIOMETRIC_INGEST]', err.message);
        return { ok: false, status: 500, error: 'Database error' };
    }
}

module.exports = { ingestBiometricLog };
