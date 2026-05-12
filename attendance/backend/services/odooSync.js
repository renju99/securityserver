const MAX_BATCH = parseInt(process.env.ODOO_SYNC_BATCH_SIZE || '25', 10);
const RETRY_BASE_SECONDS = parseInt(process.env.ODOO_SYNC_RETRY_BASE_SECONDS || '30', 10);
const RETRY_MAX_SECONDS = parseInt(process.env.ODOO_SYNC_RETRY_MAX_SECONDS || '900', 10);
const MAX_ATTEMPTS = parseInt(process.env.ODOO_SYNC_MAX_ATTEMPTS || '288', 10);

const odooJsonRpc = async ({ baseUrl, path, payload, sessionId }) => {
    const headers = { 'Content-Type': 'application/json' };
    if (sessionId) headers.Cookie = `session_id=${sessionId}`;

    const response = await fetch(`${baseUrl}${path}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok || body?.error) {
        const message = body?.error?.data?.message || body?.error?.message || `Odoo HTTP ${response.status}`;
        throw new Error(message);
    }
    return { body, setCookie: response.headers.get('set-cookie') || '' };
};

const extractSessionId = (setCookieHeader) => {
    const match = String(setCookieHeader || '').match(/session_id=([^;]+)/);
    return match ? match[1] : null;
};

const createOdooClient = async (instance) => {
    const authPayload = {
        jsonrpc: '2.0',
        method: 'call',
        params: {
            db: instance.db_name,
            login: instance.username,
            password: instance.password,
        },
        id: Date.now(),
    };
    const { body, setCookie } = await odooJsonRpc({
        baseUrl: instance.base_url,
        path: '/web/session/authenticate',
        payload: authPayload,
    });
    const uid = body?.result?.uid;
    if (!uid) {
        throw new Error(`Authentication failed for instance ${instance.instance_code}`);
    }
    const sessionId = extractSessionId(setCookie);
    if (!sessionId) {
        throw new Error(`No session cookie from instance ${instance.instance_code}`);
    }

    const callKw = async (model, method, args = [], kwargs = {}) => {
        const payload = {
            jsonrpc: '2.0',
            method: 'call',
            params: {
                model,
                method,
                args,
                kwargs,
            },
            id: Date.now(),
        };
        const res = await odooJsonRpc({
            baseUrl: instance.base_url,
            path: `/web/dataset/call_kw/${encodeURIComponent(model)}/${encodeURIComponent(method)}`,
            payload,
            sessionId,
        });
        return res.body.result;
    };

    return {
        instance,
        uid,
        callKw,
    };
};

const getRetryDelaySeconds = (attempts) => {
    const exp = Math.max(0, attempts - 1);
    const raw = RETRY_BASE_SECONDS * (2 ** exp);
    return Math.min(raw, RETRY_MAX_SECONDS);
};

const resolveRoute = async (pool, staffId) => {
    const routingRes = await pool.query(
        `SELECT r.instance_code, r.organization_id, i.base_url, i.db_name, i.username, i.password, i.employee_lookup_field, i.is_active
         FROM staff_odoo_routing r
         JOIN odoo_instances i ON i.organization_id = r.organization_id AND i.instance_code = r.instance_code
         WHERE r.staff_id = $1 AND r.is_active = true`,
        [staffId]
    );
    if (routingRes.rows.length === 0) {
        throw new Error(`No Odoo route configured for staff ${staffId}`);
    }
    const instance = routingRes.rows[0];
    if (!instance.is_active) {
        throw new Error(`Mapped Odoo instance ${instance.instance_code} is inactive`);
    }
    return instance;
};

const resolveOdooEmployeeId = async (client, staffId) => {
    const lookupField = client.instance.employee_lookup_field || 'barcode';
    const records = await client.callKw(
        'hr.employee',
        'search_read',
        [[ [lookupField, '=', staffId] ]],
        { fields: ['id', lookupField], limit: 2 }
    );
    if (!Array.isArray(records) || records.length === 0) {
        throw new Error(`No Odoo employee found by ${lookupField}=${staffId}`);
    }
    if (records.length > 1) {
        throw new Error(`Multiple Odoo employees found by ${lookupField}=${staffId}`);
    }
    return records[0].id;
};

const upsertMapping = async ({ pool, attendanceId, organizationId, instanceCode, odooAttendanceId, status, error, eventType }) => {
    const setCheckIn = eventType === 'check_in' ? 'NOW()' : 'attendance_sync_mapping.synced_check_in_at';
    const setCheckOut = eventType === 'check_out' ? 'NOW()' : 'attendance_sync_mapping.synced_check_out_at';
    const numericAttendanceId = Number.isFinite(Number(odooAttendanceId)) ? Number(odooAttendanceId) : null;
    await pool.query(
        `INSERT INTO attendance_sync_mapping
         (attendance_id, organization_id, instance_code, odoo_attendance_id, synced_check_in_at, synced_check_out_at, last_status, last_error, updated_at)
         VALUES ($1::integer, $2::integer, $3::varchar, $4::bigint, ${eventType === 'check_in' ? 'NOW()' : 'NULL'}, ${eventType === 'check_out' ? 'NOW()' : 'NULL'}, $5::varchar, $6::text, NOW())
         ON CONFLICT (attendance_id) DO UPDATE SET
            organization_id = EXCLUDED.organization_id,
            instance_code = EXCLUDED.instance_code,
            odoo_attendance_id = COALESCE(EXCLUDED.odoo_attendance_id, attendance_sync_mapping.odoo_attendance_id),
            synced_check_in_at = ${setCheckIn},
            synced_check_out_at = ${setCheckOut},
            last_status = EXCLUDED.last_status,
            last_error = EXCLUDED.last_error,
            updated_at = NOW()`,
        [attendanceId, organizationId, instanceCode || null, numericAttendanceId, status, error || null]
    );
};

const markOutboxSuccess = async (pool, outboxId, instanceCode) => {
    await pool.query(
        `UPDATE attendance_sync_outbox
         SET status = 'succeeded',
             route_instance_code = $2,
             last_error = NULL,
             updated_at = NOW()
         WHERE id = $1`,
        [outboxId, instanceCode]
    );
};

const markOutboxFailure = async (pool, row, errMessage) => {
    const attempts = (row.attempts || 0) + 1;
    const dead = attempts >= MAX_ATTEMPTS;
    const delay = getRetryDelaySeconds(attempts);
    await pool.query(
        `UPDATE attendance_sync_outbox
         SET attempts = $2::integer,
             status = $3::varchar,
             last_error = $4::text,
             next_retry_at = CASE WHEN $3::varchar = 'dead_letter' THEN next_retry_at ELSE NOW() + make_interval(secs => $5::integer) END,
             updated_at = NOW()
         WHERE id = $1::integer`,
        [row.id, attempts, dead ? 'dead_letter' : 'failed', errMessage, delay]
    );
    let organizationId = null;
    const code = row.route_instance_code || null;
    if (code) {
        const oi = await pool.query(
            'SELECT organization_id FROM odoo_instances WHERE instance_code = $1 ORDER BY id ASC LIMIT 1',
            [code]
        );
        organizationId = oi.rows[0]?.organization_id ?? null;
    }
    if (organizationId == null) {
        const r = await pool.query(
            'SELECT organization_id FROM staff_odoo_routing WHERE staff_id = $1 AND is_active = true LIMIT 1',
            [row.staff_id]
        );
        organizationId = r.rows[0]?.organization_id ?? null;
    }
    if (organizationId == null) {
        const d = await pool.query(`SELECT id FROM organizations WHERE slug = 'default' LIMIT 1`);
        organizationId = d.rows[0]?.id ?? null;
    }
    await upsertMapping({
        pool,
        attendanceId: row.attendance_id,
        organizationId,
        instanceCode: code,
        odooAttendanceId: null,
        status: dead ? 'dead_letter' : 'failed',
        error: errMessage,
        eventType: row.event_type,
    });
};

const processOutboxRow = async ({ pool, row, metrics }) => {
    const instance = await resolveRoute(pool, row.staff_id);
    await pool.query(
        `UPDATE attendance_sync_outbox
         SET status = 'processing',
             route_instance_code = $2,
             updated_at = NOW()
         WHERE id = $1`,
        [row.id, instance.instance_code]
    );

    const mappingRes = await pool.query(
        `SELECT attendance_id, odoo_attendance_id, synced_check_in_at, synced_check_out_at
         FROM attendance_sync_mapping
         WHERE attendance_id = $1`,
        [row.attendance_id]
    );
    const mapping = mappingRes.rows[0] || null;

    if (row.event_type === 'check_in' && mapping?.synced_check_in_at) {
        await markOutboxSuccess(pool, row.id, instance.instance_code);
        return;
    }
    if (row.event_type === 'check_out' && mapping?.synced_check_out_at) {
        await markOutboxSuccess(pool, row.id, instance.instance_code);
        return;
    }

    const client = await createOdooClient(instance);
    const odooEmployeeId = await resolveOdooEmployeeId(client, row.staff_id);
    const payload = row.payload || {};
    let odooAttendanceId = mapping?.odoo_attendance_id || null;

    if (row.event_type === 'check_in') {
        if (!odooAttendanceId) {
            const checkInTs = payload.checkInTime || new Date().toISOString();
            odooAttendanceId = await client.callKw(
                'hr.attendance',
                'create',
                [[{ employee_id: odooEmployeeId, check_in: checkInTs }]],
                {}
            );
        }
        await upsertMapping({
            pool,
            attendanceId: row.attendance_id,
            organizationId: instance.organization_id,
            instanceCode: instance.instance_code,
            odooAttendanceId,
            status: 'succeeded',
            error: null,
            eventType: row.event_type,
        });
    } else if (row.event_type === 'check_out') {
        if (!odooAttendanceId) {
            const openRows = await client.callKw(
                'hr.attendance',
                'search_read',
                [[['employee_id', '=', odooEmployeeId], ['check_out', '=', false]]],
                { fields: ['id', 'check_in'], order: 'check_in desc', limit: 1 }
            );
            if (Array.isArray(openRows) && openRows.length > 0) {
                odooAttendanceId = openRows[0].id;
            }
        }
        if (!odooAttendanceId) {
            throw new Error(`No mapped/open Odoo attendance found for staff ${row.staff_id} to check out`);
        }
        const checkOutTs = payload.checkOutTime || new Date().toISOString();
        await client.callKw(
            'hr.attendance',
            'write',
            [[odooAttendanceId], { check_out: checkOutTs }],
            {}
        );
        await upsertMapping({
            pool,
            attendanceId: row.attendance_id,
            organizationId: instance.organization_id,
            instanceCode: instance.instance_code,
            odooAttendanceId,
            status: 'succeeded',
            error: null,
            eventType: row.event_type,
        });
    }

    await markOutboxSuccess(pool, row.id, instance.instance_code);
    metrics.increment('odoo_sync_success_total', 1);
};

const createAttendanceSyncRunner = ({ pool, metrics }) => {
    let running = false;

    const run = async () => {
        if (running) return;
        running = true;
        try {
            const outboxRes = await pool.query(
                `SELECT id, attendance_id, staff_id, event_type, payload, attempts, status, route_instance_code
                 FROM attendance_sync_outbox
                 WHERE status IN ('pending', 'failed')
                   AND next_retry_at <= NOW()
                 ORDER BY id ASC
                 LIMIT $1`,
                [MAX_BATCH]
            );
            for (const row of outboxRes.rows) {
                try {
                    // eslint-disable-next-line no-await-in-loop
                    await processOutboxRow({ pool, row, metrics });
                } catch (err) {
                    metrics.increment('odoo_sync_failed_total', 1);
                    const message = err?.message || 'Unknown sync error';
                    console.error(`[ODOO_SYNC] row=${row.id} failed:`, message);
                    // eslint-disable-next-line no-await-in-loop
                    await markOutboxFailure(pool, row, message);
                }
            }
        } catch (err) {
            console.error('[ODOO_SYNC] runner failure:', err.message);
        } finally {
            running = false;
        }
    };

    const schedule = () => {
        const intervalMs = parseInt(process.env.ODOO_SYNC_INTERVAL_MS || '15000', 10);
        setInterval(() => {
            run().catch((err) => console.error('[ODOO_SYNC] schedule run error:', err.message));
        }, intervalMs);
        console.log(`[ODOO_SYNC] Scheduled sync runner every ${intervalMs}ms`);
    };

    return { run, schedule };
};

module.exports = {
    createAttendanceSyncRunner,
};
