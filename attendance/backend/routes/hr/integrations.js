const { z } = require('zod');
const crypto = require('crypto');
const { organizationIdFromUser } = require('../../utils/organization');

const instanceSchema = z.object({
    instanceCode: z.string().trim().min(2),
    name: z.string().trim().min(1),
    baseUrl: z.string().trim().url(),
    dbName: z.string().trim().min(1),
    username: z.string().trim().min(1),
    password: z.string().trim().min(1),
    employeeLookupField: z.enum(['code', 'barcode']),
    isActive: z.boolean().optional(),
});

const routingSchema = z.object({
    instanceCode: z.string().trim().min(2),
    notes: z.string().trim().optional().nullable(),
    isActive: z.boolean().optional(),
});
const bulkRoutingSchema = z.object({
    mappings: z.array(z.object({
        staffId: z.string().trim().min(1),
        instanceCode: z.string().trim().min(2),
        notes: z.string().trim().optional().nullable(),
        isActive: z.boolean().optional(),
        sourceRow: z.number().int().positive().optional(),
    })).min(1),
    replaceExisting: z.boolean().optional(),
});
const kioskDeviceSchema = z.object({
    name: z.string().trim().min(2),
    siteId: z.union([z.number(), z.string()]),
    deviceKey: z.string().trim().min(8).optional(),
    isActive: z.boolean().optional(),
    notes: z.string().trim().max(500).optional().nullable(),
});

const odooRequeueSchema = z.object({
    ids: z.array(z.number().int().positive()).optional(),
    scope: z.enum(['dead_letter', 'failed', 'retryable']).optional(),
    limit: z.number().int().min(1).max(500).optional().default(100),
    confirm: z.boolean().optional(),
}).refine(
    (d) => (Array.isArray(d.ids) && d.ids.length > 0) || d.confirm === true,
    { message: 'Bulk requeue requires confirm:true, or pass explicit ids[]' }
);

const biometricReprocessSchema = z.object({
    ids: z.array(z.number().int().positive()).min(1).max(500).optional(),
    scope: z.enum(['failed', 'dead_letter', 'retryable']).optional(),
    limit: z.number().int().min(1).max(500).optional().default(100),
    confirm: z.boolean().optional(),
}).refine(
    (d) => (Array.isArray(d.ids) && d.ids.length > 0) || d.confirm === true,
    { message: 'Bulk reprocess requires confirm:true, or pass explicit ids[]' }
);

module.exports = ({ router, pool, authenticateToken, authorizeRole, runOdooSync, metrics }) => {
    const generateDeviceKey = () => `kiosk_${crypto.randomBytes(12).toString('hex')}`;

    router.get('/hr/integrations/odoo-instances', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                `SELECT instance_code, name, base_url, db_name, username, employee_lookup_field, is_active, updated_at
                 FROM odoo_instances
                 WHERE organization_id = $1
                 ORDER BY instance_code ASC`,
                [orgId]
            );
            return res.json(result.rows);
        } catch (err) {
            console.error('List Odoo instances error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/integrations/odoo-instances', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = instanceSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid instance payload' });
        }
        const data = parsed.data;
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                `INSERT INTO odoo_instances
                 (organization_id, instance_code, name, base_url, db_name, username, password, employee_lookup_field, is_active, updated_at)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, COALESCE($9, true), NOW())
                 ON CONFLICT (organization_id, instance_code) DO UPDATE SET
                    name = EXCLUDED.name,
                    base_url = EXCLUDED.base_url,
                    db_name = EXCLUDED.db_name,
                    username = EXCLUDED.username,
                    password = EXCLUDED.password,
                    employee_lookup_field = EXCLUDED.employee_lookup_field,
                    is_active = EXCLUDED.is_active,
                    updated_at = NOW()
                 RETURNING instance_code, name, base_url, db_name, username, employee_lookup_field, is_active, updated_at`,
                [
                    orgId,
                    data.instanceCode.toLowerCase(),
                    data.name,
                    data.baseUrl.replace(/\/$/, ''),
                    data.dbName,
                    data.username,
                    data.password,
                    data.employeeLookupField,
                    data.isActive,
                ]
            );
            return res.json(result.rows[0]);
        } catch (err) {
            console.error('Upsert Odoo instance error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/integrations/staff-routing', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const search = String(req.query.search || '').trim();
        try {
            const orgId = organizationIdFromUser(req.user);
            const params = [orgId];
            let where = 'WHERE r.organization_id = $1';
            if (search) {
                params.push(`%${search}%`);
                where += ` AND (r.staff_id ILIKE $2 OR e.first_name ILIKE $2 OR e.last_name ILIKE $2)`;
            }
            const result = await pool.query(
                `SELECT r.staff_id, r.instance_code, r.is_active, r.notes, r.updated_at,
                        e.first_name, e.last_name
                 FROM staff_odoo_routing r
                 LEFT JOIN employees e ON e.staff_id = r.staff_id AND e.organization_id = r.organization_id
                 ${where}
                 ORDER BY r.staff_id ASC
                 LIMIT 500`,
                params
            );
            return res.json(result.rows);
        } catch (err) {
            console.error('List staff routing error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.put('/hr/integrations/staff-routing/:staffId', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = routingSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid routing payload' });
        }
        const staffId = String(req.params.staffId || '').trim();
        if (!staffId) return res.status(400).json({ error: 'staffId is required' });
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                `INSERT INTO staff_odoo_routing (organization_id, staff_id, instance_code, notes, is_active, updated_at)
                 VALUES ($1, $2, $3, $4, COALESCE($5, true), NOW())
                 ON CONFLICT (organization_id, staff_id) DO UPDATE SET
                    instance_code = EXCLUDED.instance_code,
                    notes = EXCLUDED.notes,
                    is_active = EXCLUDED.is_active,
                    updated_at = NOW()
                 RETURNING *`,
                [orgId, staffId, parsed.data.instanceCode.toLowerCase(), parsed.data.notes || null, parsed.data.isActive]
            );
            return res.json(result.rows[0]);
        } catch (err) {
            console.error('Upsert staff routing error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/integrations/staff-routing/bulk', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = bulkRoutingSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid bulk routing payload' });
        }
        const { mappings, replaceExisting = false } = parsed.data;
        const normalized = mappings.map((row) => ({
            staffId: String(row.staffId).trim(),
            instanceCode: String(row.instanceCode).trim().toLowerCase(),
            notes: row.notes || null,
            isActive: row.isActive !== false,
            sourceRow: row.sourceRow || null,
        }));

        const dedupedMap = new Map();
        normalized.forEach((row) => dedupedMap.set(row.staffId, row));
        const deduped = Array.from(dedupedMap.values());

        const client = await pool.connect();
        try {
            await client.query('BEGIN');
            const orgId = organizationIdFromUser(req.user);

            const instanceSet = [...new Set(deduped.map((row) => row.instanceCode))];
            const instanceRes = await client.query(
                `SELECT instance_code FROM odoo_instances WHERE organization_id = $1 AND instance_code = ANY($2)`,
                [orgId, instanceSet]
            );
            const validSet = new Set(instanceRes.rows.map((r) => r.instance_code));
            const rejectedRows = [];
            const validInstanceRows = [];
            deduped.forEach((row) => {
                if (!validSet.has(row.instanceCode)) {
                    rejectedRows.push({
                        sourceRow: row.sourceRow,
                        staffId: row.staffId,
                        instanceCode: row.instanceCode,
                        reason: `Unknown instance_code: ${row.instanceCode}`,
                    });
                } else {
                    validInstanceRows.push(row);
                }
            });

            const staffSet = [...new Set(validInstanceRows.map((row) => row.staffId))];
            const employeeRes = await client.query(
                `SELECT staff_id FROM employees WHERE organization_id = $1 AND staff_id = ANY($2)`,
                [orgId, staffSet]
            );
            const employeeSet = new Set(employeeRes.rows.map((r) => r.staff_id));
            const validRows = [];
            validInstanceRows.forEach((row) => {
                if (!employeeSet.has(row.staffId)) {
                    rejectedRows.push({
                        sourceRow: row.sourceRow,
                        staffId: row.staffId,
                        instanceCode: row.instanceCode,
                        reason: 'staff_id not found in employees',
                    });
                } else {
                    validRows.push(row);
                }
            });

            if (replaceExisting) {
                await client.query('DELETE FROM staff_odoo_routing WHERE organization_id = $1', [orgId]);
            }

            let insertedOrUpdated = 0;
            for (const row of validRows) {
                // eslint-disable-next-line no-await-in-loop
                await client.query(
                    `INSERT INTO staff_odoo_routing (organization_id, staff_id, instance_code, notes, is_active, updated_at)
                     VALUES ($1, $2, $3, $4, $5, NOW())
                     ON CONFLICT (organization_id, staff_id) DO UPDATE SET
                        instance_code = EXCLUDED.instance_code,
                        notes = EXCLUDED.notes,
                        is_active = EXCLUDED.is_active,
                        updated_at = NOW()`,
                    [orgId, row.staffId, row.instanceCode, row.notes, row.isActive]
                );
                insertedOrUpdated += 1;
            }

            await client.query('COMMIT');
            return res.json({
                success: true,
                totalReceived: mappings.length,
                totalProcessed: deduped.length,
                totalValid: validRows.length,
                totalRejected: rejectedRows.length,
                insertedOrUpdated,
                replacedExisting: replaceExisting,
                rejectedRows,
            });
        } catch (err) {
            await client.query('ROLLBACK');
            console.error('Bulk routing import error:', err);
            return res.status(500).json({ error: 'Database error' });
        } finally {
            client.release();
        }
    });

    router.delete('/hr/integrations/staff-routing/:staffId', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            await pool.query(
                'DELETE FROM staff_odoo_routing WHERE staff_id = $1 AND organization_id = $2',
                [req.params.staffId, orgId]
            );
            return res.json({ success: true });
        } catch (err) {
            console.error('Delete staff routing error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/integrations/kiosk-devices', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const siteId = Number(req.query.siteId);
        try {
            const orgId = organizationIdFromUser(req.user);
            const params = [orgId];
            let where = 'WHERE d.organization_id = $1';
            if (Number.isFinite(siteId) && siteId > 0) {
                where += ' AND d.site_id = $2';
                params.push(siteId);
            }
            const result = await pool.query(
                `SELECT d.id, d.name, d.site_id, s.name as site_name, d.device_key, d.is_active, d.notes, d.last_seen_at, d.created_at, d.updated_at
                 FROM kiosk_devices d
                 JOIN sites s ON s.id = d.site_id
                 ${where}
                 ORDER BY d.updated_at DESC`,
                params
            );
            return res.json(result.rows);
        } catch (err) {
            console.error('List kiosk devices error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/integrations/kiosk-devices', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = kioskDeviceSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid kiosk device payload' });
        }
        const siteId = Number(parsed.data.siteId);
        if (!Number.isFinite(siteId) || siteId <= 0) {
            return res.status(400).json({ error: 'siteId must be a valid number' });
        }
        const deviceKey = (parsed.data.deviceKey || generateDeviceKey()).trim();
        try {
            const orgId = organizationIdFromUser(req.user);
            const siteOk = await pool.query(
                'SELECT 1 FROM sites WHERE id = $1 AND organization_id = $2 LIMIT 1',
                [siteId, orgId]
            );
            if (siteOk.rowCount === 0) return res.status(400).json({ error: 'Invalid site for this organization' });
            const result = await pool.query(
                `INSERT INTO kiosk_devices (organization_id, name, site_id, device_key, is_active, notes, updated_at)
                 VALUES ($1, $2, $3, $4, COALESCE($5, true), $6, NOW())
                 RETURNING id, name, site_id, device_key, is_active, notes, last_seen_at, created_at, updated_at`,
                [orgId, parsed.data.name, siteId, deviceKey, parsed.data.isActive, parsed.data.notes || null]
            );
            return res.json(result.rows[0]);
        } catch (err) {
            console.error('Create kiosk device error:', err);
            if (err.code === '23505') {
                return res.status(400).json({ error: 'device_key already exists. Use a unique key.' });
            }
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.patch('/hr/integrations/kiosk-devices/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = kioskDeviceSchema.partial().safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid kiosk device payload' });
        }
        const updates = [];
        const params = [];
        let idx = 1;
        const body = parsed.data;
        if (body.name !== undefined) { updates.push(`name = $${idx++}`); params.push(body.name); }
        if (body.siteId !== undefined) {
            const siteId = Number(body.siteId);
            if (!Number.isFinite(siteId) || siteId <= 0) return res.status(400).json({ error: 'siteId must be a valid number' });
            updates.push(`site_id = $${idx++}`); params.push(siteId);
        }
        if (body.deviceKey !== undefined) { updates.push(`device_key = $${idx++}`); params.push(String(body.deviceKey).trim()); }
        if (body.isActive !== undefined) { updates.push(`is_active = $${idx++}`); params.push(body.isActive); }
        if (body.notes !== undefined) { updates.push(`notes = $${idx++}`); params.push(body.notes || null); }
        if (updates.length === 0) {
            return res.status(400).json({ error: 'No update fields provided' });
        }
        updates.push('updated_at = NOW()');
        const orgId = organizationIdFromUser(req.user);
        params.push(req.params.id, orgId);
        try {
            const result = await pool.query(
                `UPDATE kiosk_devices
                 SET ${updates.join(', ')}
                 WHERE id = $${idx++} AND organization_id = $${idx}
                 RETURNING id, name, site_id, device_key, is_active, notes, last_seen_at, created_at, updated_at`,
                params
            );
            if (result.rows.length === 0) {
                return res.status(404).json({ error: 'Kiosk device not found' });
            }
            return res.json(result.rows[0]);
        } catch (err) {
            console.error('Update kiosk device error:', err);
            if (err.code === '23505') {
                return res.status(400).json({ error: 'device_key already exists. Use a unique key.' });
            }
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.delete('/hr/integrations/kiosk-devices/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                'DELETE FROM kiosk_devices WHERE id = $1 AND organization_id = $2 RETURNING id',
                [req.params.id, orgId]
            );
            if (result.rows.length === 0) return res.status(404).json({ error: 'Kiosk device not found' });
            return res.json({ success: true });
        } catch (err) {
            console.error('Delete kiosk device error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/integrations/odoo-sync/run', authenticateToken, authorizeRole(['HR Admin']), async (_req, res) => {
        runOdooSync().catch((err) => console.error('[ODOO_SYNC] manual run error:', err.message));
        return res.json({ success: true, message: 'Odoo sync runner started' });
    });

    router.get('/hr/integrations/odoo-sync/status', authenticateToken, authorizeRole(['HR Admin']), async (_req, res) => {
        try {
            const result = await pool.query(
                `SELECT status, COUNT(*)::int AS count
                 FROM attendance_sync_outbox
                 GROUP BY status`
            );
            const counts = { pending: 0, failed: 0, processing: 0, succeeded: 0, dead_letter: 0 };
            result.rows.forEach((row) => {
                counts[row.status] = row.count;
            });
            const deadSamples = await pool.query(
                `SELECT id, attendance_id, staff_id, event_type, attempts, last_error, updated_at
                 FROM attendance_sync_outbox
                 WHERE status = 'dead_letter'
                 ORDER BY updated_at DESC
                 LIMIT 20`
            );
            return res.json({ counts, deadSamples: deadSamples.rows });
        } catch (err) {
            console.error('Odoo sync status error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/integrations/operations-health', authenticateToken, authorizeRole(['HR Admin']), async (_req, res) => {
        try {
            const [bioCounts, bioOldest, outboxOldest, outboxPending] = await Promise.all([
                pool.query(
                    `SELECT process_status AS status, COUNT(*)::int AS count
                     FROM biometric_logs
                     GROUP BY process_status`
                ),
                pool.query(
                    `SELECT MIN(timestamp) AS oldest_pending
                     FROM biometric_logs
                     WHERE process_status = 'pending'`
                ),
                pool.query(
                    `SELECT MIN(next_retry_at) AS oldest_retry_at
                     FROM attendance_sync_outbox
                     WHERE status IN ('pending', 'failed')`
                ),
                pool.query(
                    `SELECT COUNT(*)::int AS count
                     FROM attendance_sync_outbox
                     WHERE status IN ('pending', 'failed', 'processing')`
                ),
            ]);

            const biometricQueue = { counts: {}, oldestPending: bioOldest.rows[0]?.oldest_pending || null };
            bioCounts.rows.forEach((row) => {
                biometricQueue.counts[row.status] = row.count;
            });

            return res.json({
                generatedAt: new Date().toISOString(),
                processCounters: metrics?.snapshot?.() || null,
                biometricQueue,
                odooOutbox: {
                    oldestRetryAt: outboxOldest.rows[0]?.oldest_retry_at || null,
                    actionableCount: outboxPending.rows[0]?.count ?? 0,
                },
            });
        } catch (err) {
            console.error('operations-health error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/integrations/odoo-sync/requeue', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = odooRequeueSchema.safeParse(req.body || {});
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid requeue payload' });
        }
        const { ids, scope, limit } = parsed.data;
        try {
            let result;
            if (ids && ids.length > 0) {
                result = await pool.query(
                    `UPDATE attendance_sync_outbox o
                     SET status = 'pending',
                         next_retry_at = NOW(),
                         attempts = 0,
                         last_error = NULL,
                         updated_at = NOW()
                     WHERE o.id = ANY($1::bigint[])
                       AND o.status IN ('dead_letter', 'failed')
                     RETURNING o.id`,
                    [ids]
                );
            } else {
                const scopeKey = scope || 'retryable';
                const statuses = scopeKey === 'failed'
                    ? ['failed']
                    : scopeKey === 'dead_letter'
                        ? ['dead_letter']
                        : ['dead_letter', 'failed'];
                result = await pool.query(
                    `WITH cte AS (
                        SELECT id FROM attendance_sync_outbox
                        WHERE status = ANY($1::varchar[])
                        ORDER BY updated_at ASC
                        LIMIT $2
                        FOR UPDATE SKIP LOCKED
                     )
                     UPDATE attendance_sync_outbox o
                     SET status = 'pending',
                         next_retry_at = NOW(),
                         attempts = 0,
                         last_error = NULL,
                         updated_at = NOW()
                     FROM cte
                     WHERE o.id = cte.id
                     RETURNING o.id`,
                    [statuses, limit]
                );
            }
            const requeuedIds = result.rows.map((r) => r.id);
            console.log(JSON.stringify({
                level: 'info',
                component: 'operations',
                event: 'odoo_outbox_requeue',
                actorStaffId: req.user?.staffId || null,
                count: requeuedIds.length,
            }));
            runOdooSync().catch((err) => console.error('[ODOO_SYNC] post-requeue run error:', err.message));
            return res.json({ success: true, requeued: requeuedIds.length, ids: requeuedIds });
        } catch (err) {
            console.error('odoo-sync requeue error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/integrations/biometric-logs/reprocess', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = biometricReprocessSchema.safeParse(req.body || {});
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid reprocess payload' });
        }
        const { ids, scope, limit } = parsed.data;
        try {
            let result;
            if (ids && ids.length > 0) {
                result = await pool.query(
                    `UPDATE biometric_logs b
                     SET process_status = 'pending',
                         next_retry_at = NOW()
                     WHERE b.id = ANY($1::int[])
                       AND b.process_status IN ('failed', 'dead_letter')
                     RETURNING b.id`,
                    [ids]
                );
            } else {
                const scopeKey = scope || 'retryable';
                const statuses = scopeKey === 'failed'
                    ? ['failed']
                    : scopeKey === 'dead_letter'
                        ? ['dead_letter']
                        : ['dead_letter', 'failed'];
                result = await pool.query(
                    `WITH cte AS (
                        SELECT id FROM biometric_logs
                        WHERE process_status = ANY($1::varchar[])
                        ORDER BY next_retry_at ASC, id ASC
                        LIMIT $2
                        FOR UPDATE SKIP LOCKED
                     )
                     UPDATE biometric_logs b
                     SET process_status = 'pending',
                         next_retry_at = NOW()
                     FROM cte
                     WHERE b.id = cte.id
                     RETURNING b.id`,
                    [statuses, limit]
                );
            }
            const idsOut = result.rows.map((r) => r.id);
            console.log(JSON.stringify({
                level: 'info',
                component: 'operations',
                event: 'biometric_logs_reprocess',
                actorStaffId: req.user?.staffId || null,
                count: idsOut.length,
            }));
            return res.json({ success: true, reset: idsOut.length, ids: idsOut });
        } catch (err) {
            console.error('biometric-logs reprocess error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });
};
