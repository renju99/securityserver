/**
 * ZKTeco pull-mode (TCP/UDP ZK protocol, default port 4370).
 *
 * Community PHP packages such as https://github.com/jmrashed/zkteco (Laravel) speak the same
 * proprietary ZK wire protocol; this stack is Node/Express, so we use `node-zklib` instead of
 * embedding PHP. Push-mode ADMS/iClock remains in `routes/zktecoIclock.js` (`/iclock/*`).
 * Both are intended to run together: disable pull only with ZK_TCP_PULL_ENABLED=false.
 */

const ZKLib = require('node-zklib');
const { ingestBiometricLog } = require('./biometricIngest');

function mapStaffId(userId) {
    const prefix = process.env.ZK_ATTLOG_STAFF_PREFIX || '';
    return `${prefix}${String(userId || '').trim()}`;
}

function parseDevicePort(raw) {
    const n = parseInt(String(raw ?? ''), 10);
    return Number.isFinite(n) && n > 0 && n <= 65535 ? n : 4370;
}

/**
 * @param {import('pg').Pool} pool
 * @param {{ id: number; device_key: string; ip_address: string; port: string | number | null }} device
 * @param {{ increment?: (name: string, value?: number) => void }} [metrics]
 * @returns {Promise<{ ingested: number; skipped: number; error?: string }>}
 */
async function pullZkTcpDeviceOnce(pool, device, metrics) {
    const ip = String(device.ip_address || '').trim();
    if (!ip) return { ingested: 0, skipped: 0, error: 'missing_ip' };

    const port = parseDevicePort(device.port);
    const timeoutMs = parseInt(process.env.ZK_TCP_PULL_TIMEOUT_MS || '20000', 10);
    const udpInPort = parseInt(process.env.ZK_TCP_PULL_UDP_INPORT || '4000', 10);

    const zk = new ZKLib(ip, port, timeoutMs, udpInPort);
    let ingested = 0;
    let skipped = 0;
    try {
        await zk.createSocket();
        const { data: records, err } = await zk.getAttendances();
        if (err) {
            return { ingested: 0, skipped: 0, error: err.message || String(err) };
        }
        const list = Array.isArray(records) ? records : [];
        for (const rec of list) {
            const staffId = mapStaffId(rec.deviceUserId);
            if (!staffId) {
                skipped += 1;
                continue;
            }
            const ts = rec.recordTime instanceof Date ? rec.recordTime : new Date(rec.recordTime);
            if (Number.isNaN(ts.getTime())) {
                skipped += 1;
                continue;
            }
            const rawData = {
                source: 'zk_tcp_pull',
                deviceUserId: rec.deviceUserId,
                userSn: rec.userSn,
                deviceIp: rec.ip || ip,
            };
            const result = await ingestBiometricLog(pool, {
                deviceKey: device.device_key,
                staffId,
                timestamp: ts.toISOString(),
                photoUrl: null,
                rawData,
            });
            if (result.ok) {
                ingested += 1;
                metrics?.increment?.('zk_tcp_pull_records_ok_total', 1);
            } else {
                skipped += 1;
                if (result.status === 404) {
                    metrics?.increment?.('zk_tcp_pull_device_unknown_total', 1);
                }
            }
        }
        return { ingested, skipped };
    } catch (e) {
        const msg = e?.message || String(e);
        metrics?.increment?.('zk_tcp_pull_device_errors_total', 1);
        return { ingested, skipped, error: msg };
    } finally {
        try {
            await zk.disconnect();
        } catch (_e) {
            /* ignore */
        }
    }
}

/**
 * Poll every active ZKTeco_TCP device that has an IP (sequential to avoid UDP local-port clashes).
 *
 * @param {{ pool: import('pg').Pool; metrics?: { increment?: (name: string, value?: number) => void } }} args
 */
async function pullAllZkTcpDevices({ pool, metrics }) {
    const res = await pool.query(
        `SELECT id, device_key, ip_address, port
         FROM biometric_devices
         WHERE type = 'ZKTeco_TCP'
           AND COALESCE(is_active, true) = true
           AND ip_address IS NOT NULL
           AND LENGTH(TRIM(ip_address)) > 0`
    );
    if (res.rowCount === 0) return { devices: 0, ingested: 0 };

    let totalIngested = 0;
    for (const row of res.rows) {
        const r = await pullZkTcpDeviceOnce(pool, row, metrics);
        totalIngested += r.ingested;
        if (r.error) {
            console.warn(`[ZK_TCP_PULL] device id=${row.id} key=${row.device_key} @ ${row.ip_address}: ${r.error}`);
        } else if (r.ingested > 0) {
            console.info(`[ZK_TCP_PULL] device id=${row.id} key=${row.device_key}: +${r.ingested} log(s)`);
        }
    }
    metrics?.increment?.('zk_tcp_pull_runs_total', 1);
    return { devices: res.rowCount, ingested: totalIngested };
}

module.exports = {
    pullZkTcpDeviceOnce,
    pullAllZkTcpDevices,
};
