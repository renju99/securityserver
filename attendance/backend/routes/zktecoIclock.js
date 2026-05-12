const express = require('express');
const { ingestBiometricLog } = require('../services/biometricIngest');
const { parseZkAttlogLines, zkTimestampToIso } = require('../services/zktecoIclockParser');

function sendZkOk(res) {
    res.status(200).type('text/plain').send('OK');
}

function sendZkRetry(res, message = 'ERROR') {
    res.status(503).type('text/plain').send(message);
}

function readSn(req) {
    const q = req.query || {};
    const sn = q.SN || q.sn || q.Sn || '';
    return String(sn).trim();
}

/**
 * Map ZK user PIN / user id to HR staff_id (same string, or with global prefix).
 */
function mapStaffId(userId) {
    const prefix = process.env.ZK_ATTLOG_STAFF_PREFIX || '';
    return `${prefix}${userId}`;
}

/**
 * @param {import('pg').Pool} pool
 */
function createCdataHandler(pool, metrics) {
    return async (req, res) => {
        const sn = readSn(req);
        const tableRaw = req.query.table || req.query.Table || '';
        const table = String(tableRaw).toUpperCase();
        const body = typeof req.body === 'string' ? req.body : Buffer.isBuffer(req.body) ? req.body.toString('utf8') : '';

        try {
            if (!sn) {
                console.warn('[ZK_ICLOCK] POST /iclock/cdata without SN');
                return sendZkOk(res);
            }

            const allowed = process.env.ZK_ICLOCK_ALLOWED_SN;
            if (allowed && allowed.trim().length > 0) {
                const set = new Set(
                    allowed
                        .split(',')
                        .map((s) => s.trim())
                        .filter(Boolean)
                );
                if (!set.has(sn)) {
                    console.warn('[ZK_ICLOCK] SN not in allowlist:', sn);
                    return sendZkOk(res);
                }
            }

            // Text-only integration: ingest ATTLOG lines only. Image/photo tables (e.g. ATTPHOTO) are
            // acknowledged with OK so the device does not retry, but payloads are never stored.
            if (table === 'ATTPHOTO' || table === 'ATT_PHOTO' || table === 'BIOPHOTO') {
                return sendZkOk(res);
            }

            if (table === 'ATTLOG' || table === '') {
                const records = parseZkAttlogLines(body);
                let transientFailure = false;
                let okLines = 0;
                for (const rec of records) {
                    const iso = zkTimestampToIso(rec.timestampStr);
                    if (!iso) {
                        console.warn('[ZK_ICLOCK] skip bad timestamp', rec.timestampStr);
                        continue;
                    }
                    const staffId = mapStaffId(rec.userId);
                    const rawData = {
                        source: 'zk_iclock',
                        sn,
                        table: table || 'ATTLOG',
                        inOutMode: rec.inOutMode,
                        verifyType: rec.verifyType,
                        line: rec.line,
                    };
                    const result = await ingestBiometricLog(pool, {
                        deviceKey: sn,
                        staffId,
                        timestamp: iso,
                        photoUrl: null,
                        rawData,
                    });
                    if (result.ok) {
                        okLines += 1;
                        metrics?.increment?.('zk_iclock_attlog_records_ok_total', 1);
                    }
                    if (!result.ok && result.status === 404) {
                        console.warn(
                            '[ZK_ICLOCK] device not registered for SN (add terminal with this device key):',
                            sn
                        );
                        transientFailure = true;
                    } else if (!result.ok) {
                        console.error('[ZK_ICLOCK] ingest failed', result.error);
                        if (result.status >= 500) transientFailure = true;
                    }
                }
                if (transientFailure) {
                    metrics?.increment?.('zk_iclock_attlog_batch_retry_total', 1);
                    console.log(JSON.stringify({
                        level: 'warn',
                        component: 'zk_iclock',
                        event: 'attlog_batch_retry',
                        sn,
                        table: table || 'ATTLOG',
                        records: records.length,
                        okLines,
                    }));
                    return sendZkRetry(res, 'ERROR');
                }
                if (okLines > 0) {
                    metrics?.increment?.('zk_iclock_attlog_batches_ok_total', 1);
                }
            } else if (table) {
                console.info('[ZK_ICLOCK] acknowledged table (no row stored):', table, 'SN=', sn);
            }

            return sendZkOk(res);
        } catch (err) {
            metrics?.increment?.('zk_iclock_cdata_errors_total', 1);
            console.log(JSON.stringify({
                level: 'error',
                component: 'zk_iclock',
                event: 'cdata_error',
                message: err?.message || String(err),
            }));
            console.error('[ZK_ICLOCK] cdata error:', err.message);
            return sendZkRetry(res, 'ERROR');
        }
    };
}

/**
 * @param {import('pg').Pool} pool
 * @param {{ increment?: (name: string, value?: number) => void }} [metrics]
 */
module.exports = function createZktecoIclockRouter(pool, metrics) {
    const router = express.Router();
    const enabled = (process.env.ZK_ICLOCK_ENABLED || 'true').toLowerCase() !== 'false';

    router.use((_req, res, next) => {
        if (!enabled) {
            return res.status(503).type('text/plain').send('DISABLED');
        }
        return next();
    });

    /** Device long-poll / heartbeat — must return plain OK */
    router.get('/getrequest', (_req, res) => sendZkOk(res));
    router.get('/Getrequest', (_req, res) => sendZkOk(res));

    router.get('/ping', (_req, res) => sendZkOk(res));
    router.get('/Ping', (_req, res) => sendZkOk(res));

    /** Some firmware probes */
    router.get('/fdata', (_req, res) => sendZkOk(res));
    router.post('/fdata', (_req, res) => sendZkOk(res));

    const cdata = createCdataHandler(pool, metrics);
    router.post('/cdata', cdata);
    router.post('/Cdata', cdata);

    return router;
};
