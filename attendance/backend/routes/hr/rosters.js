const { z } = require('zod');
const { organizationIdFromUser } = require('../../utils/organization');

const applyRosterSchema = z.object({
    mode: z.enum(['fixed', 'rotating']),
    startDate: z.string().trim().min(1),
    endDate: z.string().trim().min(1),
    siteId: z.union([z.number(), z.string()]).optional().nullable(),
    departmentName: z.string().trim().optional().nullable(),
    employeeIds: z.array(z.union([z.number(), z.string()])).optional().default([]),
    shiftId: z.union([z.number(), z.string()]).optional().nullable(),
    name: z.string().trim().optional().nullable(),
    shiftSequence: z.array(z.union([z.number(), z.string()])).optional().default([]),
    cycleDays: z.union([z.number(), z.string()]).optional().nullable(),
});

module.exports = ({ router, pool, authenticateToken, authorizeRole }) => {
    router.get('/hr/rosters/templates', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                `SELECT id, name, rotation_type, start_date, end_date, shift_sequence, cycle_days, created_at
                 FROM roster_templates
                 WHERE organization_id = $1
                 ORDER BY created_at DESC
                 LIMIT 200`,
                [orgId]
            );
            return res.json(result.rows);
        } catch (err) {
            if (err?.code === '42P01') return res.json([]);
            console.error('Roster templates error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/rosters/assignments', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const startDate = req.query.startDate;
        const endDate = req.query.endDate;
        try {
            const orgId = organizationIdFromUser(req.user);
            const params = [orgId];
            const conditions = ['e.organization_id = $1'];
            if (req.user.role === 'Site Supervisor') {
                params.push(req.user.siteId);
                conditions.push(`e.site_id = $${params.length}`);
            }
            if (startDate) {
                params.push(startDate);
                conditions.push(`a.work_date >= $${params.length}::date`);
            }
            if (endDate) {
                params.push(endDate);
                conditions.push(`a.work_date <= $${params.length}::date`);
            }
            const where = `WHERE ${conditions.join(' AND ')}`;
            const result = await pool.query(
                `SELECT a.id, a.work_date, a.employee_id, a.shift_id, a.site_id,
                        e.staff_id, sft.name as shift_name, st.name as site_name
                 FROM roster_assignments a
                 JOIN employees e ON e.id = a.employee_id
                 LEFT JOIN shifts sft ON sft.id = a.shift_id
                 LEFT JOIN sites st ON st.id = a.site_id
                 ${where}
                 ORDER BY a.work_date DESC, e.staff_id ASC
                 LIMIT 1000`,
                params
            );
            return res.json(result.rows);
        } catch (err) {
            if (err?.code === '42P01') return res.json([]);
            console.error('Roster assignments error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/rosters/apply', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const parsed = applyRosterSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid roster payload' });
        }
        const payload = parsed.data;

        const client = await pool.connect();
        try {
            await client.query('BEGIN');
            const selectedEmployeeIds = (payload.employeeIds || []).map((id) => Number.parseInt(String(id), 10)).filter((id) => Number.isInteger(id));
            const supervisorSiteId = Number(req.user.siteId);
            if (req.user.role === 'Site Supervisor' && (!Number.isFinite(supervisorSiteId) || supervisorSiteId <= 0)) {
                await client.query('ROLLBACK');
                return res.status(403).json({ error: 'Supervisor account is not assigned to a site.' });
            }
            if (req.user.role === 'Site Supervisor' && payload.siteId && Number.parseInt(String(payload.siteId), 10) !== supervisorSiteId) {
                await client.query('ROLLBACK');
                return res.status(403).json({ error: 'You can only apply rosters for your assigned site.' });
            }

            const orgId = organizationIdFromUser(req.user);
            const params = [orgId];
            const where = ['e.organization_id = $1'];
            if (req.user.role === 'Site Supervisor') {
                params.push(supervisorSiteId);
                where.push(`e.site_id = $${params.length}`);
            }
            if (selectedEmployeeIds.length > 0) {
                params.push(selectedEmployeeIds);
                where.push(`e.id = ANY($${params.length})`);
            }
            if (payload.siteId) {
                params.push(Number.parseInt(String(payload.siteId), 10));
                where.push(`e.site_id = $${params.length}`);
            }
            if (payload.departmentName) {
                params.push(`%${payload.departmentName}%`);
                where.push(`COALESCE(e.department_name, '') ILIKE $${params.length}`);
            }
            const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : '';
            const employeeRes = await client.query(`SELECT e.id, e.site_id FROM employees e ${whereSql}`, params);
            if (employeeRes.rows.length === 0) {
                await client.query('ROLLBACK');
                return res.status(404).json({ error: 'No matching employees for roster apply.' });
            }

            let templateId = null;
            let sequence = [];
            let cycleDays = null;
            if (payload.mode === 'rotating') {
                sequence = (payload.shiftSequence || []).map((id) => Number.parseInt(String(id), 10)).filter((id) => Number.isInteger(id));
                cycleDays = Number.parseInt(String(payload.cycleDays || '1'), 10) || 1;
                const tplRes = await client.query(
                    `INSERT INTO roster_templates (organization_id, name, rotation_type, shift_sequence, cycle_days, start_date, end_date, created_by)
                     VALUES ($1, $2, 'rotating', $3::jsonb, $4, $5::date, $6::date, $7)
                     RETURNING id`,
                    [orgId, payload.name || `Rotation ${payload.startDate}`, JSON.stringify(sequence), cycleDays, payload.startDate, payload.endDate, req.user.id]
                );
                templateId = tplRes.rows[0].id;
            }

            const start = new Date(payload.startDate);
            const end = new Date(payload.endDate);
            const dates = [];
            for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
                dates.push(new Date(d));
            }

            let assignmentsUpserted = 0;
            for (const emp of employeeRes.rows) {
                for (let idx = 0; idx < dates.length; idx += 1) {
                    const workDate = dates[idx].toISOString().slice(0, 10);
                    let shiftId = null;
                    if (payload.mode === 'fixed') {
                        shiftId = Number.parseInt(String(payload.shiftId || ''), 10);
                    } else if (sequence.length > 0) {
                        shiftId = sequence[idx % sequence.length];
                    }
                    // eslint-disable-next-line no-await-in-loop
                    await client.query(
                        `INSERT INTO roster_assignments (employee_id, work_date, shift_id, site_id, template_id, created_by, acceptance_status, notified_at)
                         VALUES ($1, $2::date, $3, $4, $5, $6, 'assigned', NOW())
                         ON CONFLICT (employee_id, work_date) DO UPDATE SET
                            shift_id = EXCLUDED.shift_id,
                            site_id = EXCLUDED.site_id,
                            template_id = EXCLUDED.template_id,
                            acceptance_status = 'assigned',
                            notified_at = NOW()`,
                        [emp.id, workDate, shiftId || null, req.user.role === 'Site Supervisor' ? supervisorSiteId : (payload.siteId ? Number.parseInt(String(payload.siteId), 10) : emp.site_id || null), templateId, req.user.id]
                    );
                    assignmentsUpserted += 1;
                }
            }

            await client.query('COMMIT');
            return res.json({
                success: true,
                assignmentsUpserted,
                templateId,
            });
        } catch (err) {
            await client.query('ROLLBACK');
            if (err?.code === '42P01') {
                return res.status(500).json({ error: 'Roster tables not found. Run roster migrations first.' });
            }
            console.error('Roster apply error:', err);
            return res.status(500).json({ error: 'Database error' });
        } finally {
            client.release();
        }
    });
};
