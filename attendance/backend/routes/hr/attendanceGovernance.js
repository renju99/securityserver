const { z } = require('zod');
const { addApprovalLog } = require('../../services/attendanceGovernance');
const { enqueueAttendanceSync } = require('../../services/attendanceSyncQueue');

const policySchema = z.object({
    siteId: z.union([z.number(), z.string()]).optional().nullable(),
    shiftId: z.union([z.number(), z.string()]).optional().nullable(),
    overtimeAfterMinutes: z.union([z.number(), z.string()]).optional(),
    paidBreakMinutes: z.union([z.number(), z.string()]).optional(),
    unpaidBreakMinutes: z.union([z.number(), z.string()]).optional(),
    maxShiftMinutes: z.union([z.number(), z.string()]).optional().nullable(),
    requireApprovalManual: z.boolean().optional(),
    requireApprovalOffline: z.boolean().optional(),
    isActive: z.boolean().optional(),
});

const approvalSchema = z.object({
    reason: z.string().trim().max(500).optional().nullable(),
});

const contextSchema = z.object({
    jobCode: z.string().trim().max(64).optional().nullable(),
    activityName: z.string().trim().max(120).optional().nullable(),
    notes: z.string().trim().max(500).optional().nullable(),
});

const jobCodeSchema = z.object({
    code: z.string().trim().min(1).max(64),
    name: z.string().trim().min(1).max(120),
    siteId: z.union([z.number(), z.string()]).optional().nullable(),
    isActive: z.boolean().optional(),
});

module.exports = ({ router, pool, authenticateToken, authorizeRole }) => {
    router.get('/hr/attendance/policies', authenticateToken, authorizeRole(['HR Admin']), async (_req, res) => {
        try {
            const result = await pool.query(
                `SELECT p.*, s.name AS site_name, sh.name AS shift_name
                 FROM attendance_policy_rules p
                 LEFT JOIN sites s ON s.id = p.site_id
                 LEFT JOIN shifts sh ON sh.id = p.shift_id
                 ORDER BY p.updated_at DESC`
            );
            res.json(result.rows);
        } catch (err) {
            console.error('Attendance policy list error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/attendance/policies', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = policySchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid policy payload' });
        }
        const body = parsed.data;
        const siteId = body.siteId === '' || body.siteId === undefined ? null : Number(body.siteId);
        const shiftId = body.shiftId === '' || body.shiftId === undefined ? null : Number(body.shiftId);
        const overtimeAfterMinutes = Math.max(Number(body.overtimeAfterMinutes ?? 480), 0);
        const paidBreakMinutes = Math.max(Number(body.paidBreakMinutes ?? 0), 0);
        const unpaidBreakMinutes = Math.max(Number(body.unpaidBreakMinutes ?? 0), 0);
        const maxShiftMinutes = body.maxShiftMinutes === '' || body.maxShiftMinutes === undefined || body.maxShiftMinutes === null
            ? null
            : Math.max(Number(body.maxShiftMinutes), 0);
        try {
            const result = await pool.query(
                `INSERT INTO attendance_policy_rules
                 (site_id, shift_id, overtime_after_minutes, paid_break_minutes, unpaid_break_minutes,
                  max_shift_minutes, require_approval_manual, require_approval_offline, is_active, created_by, updated_by, updated_at)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, COALESCE($9, TRUE), $10, $10, NOW())
                 ON CONFLICT ((COALESCE(site_id, -1)), (COALESCE(shift_id, -1)))
                 WHERE is_active = TRUE
                 DO UPDATE SET
                    overtime_after_minutes = EXCLUDED.overtime_after_minutes,
                    paid_break_minutes = EXCLUDED.paid_break_minutes,
                    unpaid_break_minutes = EXCLUDED.unpaid_break_minutes,
                    max_shift_minutes = EXCLUDED.max_shift_minutes,
                    require_approval_manual = EXCLUDED.require_approval_manual,
                    require_approval_offline = EXCLUDED.require_approval_offline,
                    is_active = EXCLUDED.is_active,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = NOW()
                 RETURNING *`,
                [
                    Number.isFinite(siteId) ? siteId : null,
                    Number.isFinite(shiftId) ? shiftId : null,
                    overtimeAfterMinutes,
                    paidBreakMinutes,
                    unpaidBreakMinutes,
                    Number.isFinite(maxShiftMinutes) ? maxShiftMinutes : null,
                    body.requireApprovalManual ?? false,
                    body.requireApprovalOffline ?? true,
                    body.isActive ?? true,
                    req.user.id,
                ]
            );
            res.json(result.rows[0]);
        } catch (err) {
            console.error('Attendance policy upsert error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/attendance/pending-approvals', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const params = [];
        const where = [`a.status = 'pending'`];
        if (req.user.role === 'Site Supervisor') {
            params.push(req.user.siteId);
            where.push(`a.site_id = $${params.length}`);
        }
        try {
            const result = await pool.query(
                `SELECT a.id, a.employee_id, a.check_in_time, a.check_out_time, a.site_id, a.source, a.work_context, a.notes,
                        e.staff_id, e.first_name, e.last_name, s.name AS site_name
                 FROM attendance a
                 JOIN employees e ON e.id = a.employee_id
                 LEFT JOIN sites s ON s.id = a.site_id
                 WHERE ${where.join(' AND ')}
                 ORDER BY a.check_in_time DESC
                 LIMIT 300`,
                params
            );
            res.json(result.rows);
        } catch (err) {
            console.error('Pending approval list error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/attendance/:id/approve', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const id = Number(req.params.id);
        if (!Number.isFinite(id)) return res.status(400).json({ error: 'Invalid attendance id' });
        try {
            const existing = await pool.query(
                `SELECT a.id, a.site_id, a.status, a.employee_id, e.staff_id
                 FROM attendance a
                 JOIN employees e ON e.id = a.employee_id
                 WHERE a.id = $1`,
                [id]
            );
            if (existing.rowCount === 0) return res.status(404).json({ error: 'Attendance entry not found' });
            const row = existing.rows[0];
            if (req.user.role === 'Site Supervisor' && Number(row.site_id) !== Number(req.user.siteId)) {
                return res.status(403).json({ error: 'Not allowed for this site' });
            }
            const updated = await pool.query(
                `UPDATE attendance
                 SET status = 'approved',
                     approved_at = NOW(),
                     approved_by = $2,
                     rejected_at = NULL,
                     rejected_by = NULL,
                     rejection_reason = NULL
                 WHERE id = $1
                 RETURNING *`,
                [id, req.user.id]
            );
            await addApprovalLog(pool, { attendanceId: id, action: 'approved', actorId: req.user.id, metadata: { previousStatus: row.status } });
            // enqueue now that it is approved
            if (updated.rows[0]?.check_in_time && !updated.rows[0]?.check_out_time) {
                await enqueueAttendanceSync(pool, {
                    attendanceId: id,
                    staffId: row.staff_id,
                    eventType: 'check_in',
                    siteId: row.site_id,
                    checkInTime: updated.rows[0].check_in_time,
                    source: 'approval',
                });
            } else if (updated.rows[0]?.check_out_time) {
                await enqueueAttendanceSync(pool, {
                    attendanceId: id,
                    staffId: row.staff_id,
                    eventType: 'check_out',
                    siteId: row.site_id,
                    checkOutTime: updated.rows[0].check_out_time,
                    source: 'approval',
                });
            }
            res.json({ success: true, record: updated.rows[0] });
        } catch (err) {
            console.error('Approve attendance error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/attendance/:id/reject', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const id = Number(req.params.id);
        if (!Number.isFinite(id)) return res.status(400).json({ error: 'Invalid attendance id' });
        const parsed = approvalSchema.safeParse(req.body || {});
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid reject payload' });
        }
        try {
            const existing = await pool.query('SELECT id, site_id, status FROM attendance WHERE id = $1', [id]);
            if (existing.rowCount === 0) return res.status(404).json({ error: 'Attendance entry not found' });
            const row = existing.rows[0];
            if (req.user.role === 'Site Supervisor' && Number(row.site_id) !== Number(req.user.siteId)) {
                return res.status(403).json({ error: 'Not allowed for this site' });
            }
            const updated = await pool.query(
                `UPDATE attendance
                 SET status = 'rejected',
                     rejected_at = NOW(),
                     rejected_by = $2,
                     rejection_reason = $3
                 WHERE id = $1
                 RETURNING *`,
                [id, req.user.id, parsed.data.reason || 'Rejected by reviewer']
            );
            await addApprovalLog(pool, {
                attendanceId: id,
                action: 'rejected',
                actorId: req.user.id,
                reason: parsed.data.reason || null,
                metadata: { previousStatus: row.status },
            });
            res.json({ success: true, record: updated.rows[0] });
        } catch (err) {
            console.error('Reject attendance error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.patch('/hr/attendance/:id/context', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const id = Number(req.params.id);
        if (!Number.isFinite(id)) return res.status(400).json({ error: 'Invalid attendance id' });
        const parsed = contextSchema.safeParse(req.body || {});
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid context payload' });
        }
        try {
            const existing = await pool.query('SELECT id, site_id, work_context FROM attendance WHERE id = $1', [id]);
            if (existing.rowCount === 0) return res.status(404).json({ error: 'Attendance entry not found' });
            const row = existing.rows[0];
            if (req.user.role === 'Site Supervisor' && Number(row.site_id) !== Number(req.user.siteId)) {
                return res.status(403).json({ error: 'Not allowed for this site' });
            }
            const merged = {
                ...(row.work_context || {}),
                ...(parsed.data.jobCode ? { jobCode: parsed.data.jobCode } : {}),
                ...(parsed.data.activityName ? { activityName: parsed.data.activityName } : {}),
                ...(parsed.data.notes ? { contextNote: parsed.data.notes } : {}),
            };
            const updated = await pool.query(
                `UPDATE attendance
                 SET work_context = $2::jsonb
                 WHERE id = $1
                 RETURNING id, work_context`,
                [id, JSON.stringify(merged)]
            );
            res.json({ success: true, record: updated.rows[0] });
        } catch (err) {
            console.error('Attendance context update error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/job-codes', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const siteId = req.query.siteId ? Number(req.query.siteId) : null;
        const params = [];
        let where = 'WHERE is_active = TRUE';
        if (req.user.role === 'Site Supervisor') {
            params.push(Number(req.user.siteId));
            where += ` AND (site_id = $${params.length} OR site_id IS NULL)`;
        } else if (Number.isFinite(siteId)) {
            params.push(siteId);
            where += ` AND (site_id = $${params.length} OR site_id IS NULL)`;
        }
        try {
            const result = await pool.query(
                `SELECT jc.*, s.name AS site_name
                 FROM job_codes jc
                 LEFT JOIN sites s ON s.id = jc.site_id
                 ${where}
                 ORDER BY jc.code ASC`,
                params
            );
            res.json(result.rows);
        } catch (err) {
            console.error('Job code list error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/job-codes', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = jobCodeSchema.safeParse(req.body || {});
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid job code payload' });
        }
        const body = parsed.data;
        try {
            const result = await pool.query(
                `INSERT INTO job_codes (code, name, site_id, is_active, created_by, updated_by, updated_at)
                 VALUES ($1, $2, $3, COALESCE($4, TRUE), $5, $5, NOW())
                 ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    site_id = EXCLUDED.site_id,
                    is_active = EXCLUDED.is_active,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = NOW()
                 RETURNING *`,
                [body.code, body.name, body.siteId ? Number(body.siteId) : null, body.isActive ?? true, req.user.id]
            );
            res.json(result.rows[0]);
        } catch (err) {
            console.error('Job code upsert error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });
};
