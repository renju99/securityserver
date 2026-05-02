/**
 * HR Admin "connection test" wizard checks — best-effort probes; not a full ZK SDK handshake.
 */
const net = require('net');
const dns = require('dns').promises;

/** @typedef {{ id: string, label: string, ok: boolean, detail: string, severity?: 'error' | 'warning' | 'info' }} ConnCheck */

/**
 * @param {string} host
 * @param {number} port
 * @param {number} timeoutMs
 * @returns {Promise<{ ok: boolean, detail: string, ms?: number }>}
 */
function tcpConnectProbe(host, port, timeoutMs) {
    return new Promise((resolve) => {
        const started = Date.now();
        const socket = net.createConnection({ host, port, family: 0 }, () => {
            const ms = Date.now() - started;
            socket.destroy();
            resolve({ ok: true, detail: `Connected in ${ms} ms`, ms });
        });
        socket.setTimeout(timeoutMs);
        socket.on('timeout', () => {
            socket.destroy();
            resolve({ ok: false, detail: `Timed out after ${timeoutMs} ms` });
        });
        socket.on('error', (err) => {
            resolve({ ok: false, detail: err.message || 'Connection failed' });
        });
    });
}

/**
 * @param {string} host
 * @returns {Promise<{ ok: boolean, detail: string }>}
 */
async function dnsLookup(host) {
    const h = String(host).trim();
    if (!h) return { ok: false, detail: 'No host' };
    try {
        const r = await dns.lookup(h);
        return { ok: true, detail: `Resolved to ${r.address} (${r.family === 6 ? 'IPv6' : 'IPv4'})` };
    } catch (e) {
        return { ok: false, detail: e.message || 'DNS lookup failed' };
    }
}

function parsePort(raw, fallback) {
    if (raw === undefined || raw === null || raw === '') return fallback;
    const n = parseInt(String(raw), 10);
    return Number.isFinite(n) && n > 0 && n <= 65535 ? n : fallback;
}

/**
 * Public base URL for same-origin checks (iClock, ingest path).
 * @param {import('express').Request} req
 */
function inferPublicBaseUrl(req) {
    const env = process.env.PUBLIC_APP_URL || process.env.APP_PUBLIC_URL;
    if (env && String(env).trim()) {
        return String(env).trim().replace(/\/$/, '');
    }
    const proto = (req.get('x-forwarded-proto') || req.protocol || 'http').split(',')[0].trim();
    const host = (req.get('x-forwarded-host') || req.get('host') || '').split(',')[0].trim();
    if (!host) return null;
    return `${proto}://${host}`;
}

/**
 * @param {string} baseUrl
 * @returns {Promise<{ ok: boolean, detail: string }>}
 */
async function httpProbeIclockPing(baseUrl) {
    const root = String(baseUrl).replace(/\/$/, '');
    const url = `${root}/iclock/ping`;
    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), 12000);
    try {
        const res = await fetch(url, { method: 'GET', signal: ac.signal, redirect: 'follow' });
        clearTimeout(t);
        const text = (await res.text()).trim().slice(0, 120);
        const ok = res.ok && (text === 'OK' || res.status === 200);
        return { ok, detail: ok ? `HTTP ${res.status}, body OK` : `HTTP ${res.status}: ${text || '(empty)'}` };
    } catch (e) {
        clearTimeout(t);
        const msg = e && e.name === 'AbortError' ? 'Request timed out' : String(e.message || e);
        return { ok: false, detail: msg };
    }
}

/**
 * @param {string} baseUrl
 * @returns {Promise<{ ok: boolean, detail: string }>}
 */
async function httpProbeIngestExists(baseUrl) {
    const root = String(baseUrl).replace(/\/$/, '');
    const url = `${root}/api/biometrics/log`;
    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), 12000);
    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}',
            signal: ac.signal,
            redirect: 'manual',
        });
        clearTimeout(t);
        if (res.status === 403) return { ok: true, detail: 'Endpoint reachable (403 without token, as expected)' };
        if (res.status === 400) return { ok: true, detail: 'Endpoint reachable (400 invalid body, as expected)' };
        return { ok: false, detail: `Unexpected HTTP ${res.status}` };
    } catch (e) {
        clearTimeout(t);
        const msg = e && e.name === 'AbortError' ? 'Request timed out' : String(e.message || e);
        return { ok: false, detail: msg };
    }
}

/**
 * @param {import('pg').Pool} pool
 * @param {object} input
 * @param {import('express').Request} req
 * @returns {Promise<{ ok: boolean, checks: ConnCheck[] }>}
 */
async function runBiometricConnectionTests(pool, input, req) {
    /** @type {ConnCheck[]} */
    const checks = [];
    const type = (input.type || 'RA08').trim();
    const deviceKey = input.deviceKey ? String(input.deviceKey).trim() : '';
    const host = input.ipAddress ? String(input.ipAddress).trim() : '';
    const excludeRaw = input.excludeDeviceId;
    const excludeIdNum =
        excludeRaw === undefined || excludeRaw === null || excludeRaw === ''
            ? null
            : parseInt(String(excludeRaw), 10);
    const excludeForDup = Number.isFinite(excludeIdNum) && excludeIdNum > 0;

    const portNum = parsePort(input.port, type === 'ZKTeco_TCP' ? 4370 : 443);

    const ingestToken = process.env.BIOMETRIC_INGEST_TOKEN || 'attendance_secret_token';
    const defaultInsecure = ingestToken === 'attendance_secret_token';

    // ── Device key / duplicate ─────────────────────────────────────────────
    if (deviceKey.length >= 4) {
        try {
            const dup = await pool.query(
                `SELECT id, name FROM biometric_devices WHERE device_key = $1 AND ($2::integer IS NULL OR id <> $2::integer) LIMIT 1`,
                [deviceKey, excludeForDup ? excludeIdNum : null]
            );
            if (dup.rows.length > 0) {
                checks.push({
                    id: 'device_key_unique',
                    label: 'Device key not already in use',
                    ok: false,
                    severity: 'error',
                    detail: `Another terminal is using this key: "${dup.rows[0].name}" (id ${dup.rows[0].id})`,
                });
            } else {
                checks.push({
                    id: 'device_key_unique',
                    label: 'Device key not already in use',
                    ok: true,
                    detail: excludeForDup ? 'OK to keep this key on save' : 'OK — no duplicate in directory',
                });
            }
        } catch (e) {
            checks.push({
                id: 'device_key_unique',
                label: 'Device key not already in use',
                ok: false,
                severity: 'error',
                detail: e.message || 'Database error',
            });
        }

        try {
            const exists = await pool.query(`SELECT id, name, last_seen FROM biometric_devices WHERE device_key = $1 LIMIT 1`, [
                deviceKey,
            ]);
            if (exists.rows.length > 0) {
                const row = exists.rows[0];
                const seen = row.last_seen ? new Date(row.last_seen).toISOString() : 'never';
                checks.push({
                    id: 'device_row',
                    label: 'Existing terminal row',
                    ok: true,
                    severity: 'info',
                    detail: `Found "${row.name}" — last activity ${seen}`,
                });
            } else if (!excludeForDup) {
                checks.push({
                    id: 'device_row',
                    label: 'Existing terminal row',
                    ok: true,
                    severity: 'info',
                    detail: 'No row yet — it will be created when you save this wizard',
                });
            }
        } catch (_e) {
            /* optional */
        }
    } else {
        checks.push({
            id: 'device_key_present',
            label: 'Device key length',
            ok: false,
            severity: 'warning',
            detail: 'Enter at least 4 characters in step 2 before relying on ingest / SN matching',
        });
    }

    const baseUrl = inferPublicBaseUrl(req);

    // ── Type-specific ──────────────────────────────────────────────────────
    if (type === 'ZKTeco_ADMS') {
        if (baseUrl) {
            const ic = await httpProbeIclockPing(baseUrl);
            checks.push({
                id: 'iclock_ping',
                label: 'Portal iClock path (/iclock/ping)',
                ok: ic.ok,
                severity: ic.ok ? 'info' : 'warning',
                detail: ic.detail + (ic.ok ? '' : ` — checked ${baseUrl}/iclock/ping`),
            });
        } else {
            checks.push({
                id: 'iclock_ping',
                label: 'Portal iClock path (/iclock/ping)',
                ok: false,
                severity: 'info',
                detail: 'Could not infer public URL from this request. Set PUBLIC_APP_URL on the API for reliable checks.',
            });
        }
        if (host) {
            const d = await dnsLookup(host);
            checks.push({
                id: 'host_dns',
                label: 'Reachability host (DNS)',
                ok: d.ok,
                severity: d.ok ? 'info' : 'warning',
                detail: d.detail + (d.ok ? '' : ' — optional for ADMS push; fix if you poll this host'),
            });
        } else {
            checks.push({
                id: 'host_dns',
                label: 'Reachability host (DNS)',
                ok: true,
                severity: 'info',
                detail: 'Skipped — ADMS push does not require a host in step 3',
            });
        }
    } else if (type === 'ZKTeco_TCP') {
        if (!host) {
            checks.push({
                id: 'tcp_reach',
                label: 'TCP reachability (ZK port)',
                ok: false,
                severity: 'warning',
                detail: 'Add hostname or IP in step 3 to probe port ' + portNum,
            });
        } else {
            const d = await dnsLookup(host);
            checks.push({
                id: 'host_dns',
                label: 'Hostname / IP resolves',
                ok: d.ok,
                severity: d.ok ? 'info' : 'warning',
                detail: d.detail,
            });
            if (d.ok) {
                const tcp = await tcpConnectProbe(host, portNum, 8000);
                checks.push({
                    id: 'tcp_reach',
                    label: `TCP port ${portNum}`,
                    ok: tcp.ok,
                    severity: tcp.ok ? 'info' : 'warning',
                    detail: tcp.detail + (tcp.ok ? '' : ' — firewall, offline device, or wrong port'),
                });
            }
        }
    } else if (type === 'RA08' || type === 'GENERIC_HTTP') {
        if (baseUrl) {
            const ing = await httpProbeIngestExists(baseUrl);
            checks.push({
                id: 'ingest_http',
                label: 'HTTP ingest route (/api/biometrics/log)',
                ok: ing.ok,
                severity: ing.ok ? 'info' : 'warning',
                detail: ing.detail,
            });
        } else {
            checks.push({
                id: 'ingest_http',
                label: 'HTTP ingest route (/api/biometrics/log)',
                ok: false,
                severity: 'info',
                detail: 'Could not infer public base URL (set PUBLIC_APP_URL)',
            });
        }
        checks.push({
            id: 'ingest_token',
            label: 'BIOMETRIC_INGEST_TOKEN configured',
            ok: !defaultInsecure,
            severity: defaultInsecure ? 'warning' : 'info',
            detail: defaultInsecure
                ? 'Using default token in env — change BIOMETRIC_INGEST_TOKEN in production'
                : 'Non-default ingest token is set',
        });
    } else {
        if (host) {
            const d = await dnsLookup(host);
            checks.push({
                id: 'host_dns',
                label: 'Hostname / IP resolves',
                ok: d.ok,
                severity: d.ok ? 'info' : 'warning',
                detail: d.detail,
            });
            if (d.ok) {
                const p = parsePort(input.port, 443);
                const tcp = await tcpConnectProbe(host, p, 8000);
                checks.push({
                    id: 'tcp_reach',
                    label: `TCP port ${p}`,
                    ok: tcp.ok,
                    severity: tcp.ok ? 'info' : 'warning',
                    detail: tcp.detail,
                });
            }
        } else {
            checks.push({
                id: 'generic_reach',
                label: 'Network probe',
                ok: true,
                severity: 'info',
                detail: 'No host in step 3 — add hostname/IP to run DNS/TCP checks for this preset',
            });
        }
    }

    const blocking = checks.filter((c) => c.severity === 'error' && c.ok === false);
    const ok = blocking.length === 0;

    return { ok, checks };
}

module.exports = { runBiometricConnectionTests, inferPublicBaseUrl };
