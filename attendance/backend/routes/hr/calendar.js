const { z } = require('zod');
const { DateTime } = require('luxon');
const { APP_TIMEZONE } = require('../../utils/time');
const { organizationIdFromUser } = require('../../utils/organization');

const normalizeDateOnly = (value, normalizeFilterDateToUtcIso, isEnd = false) => {
    if (value instanceof Date) {
        const dt = DateTime.fromJSDate(value, { zone: 'utc' }).setZone(APP_TIMEZONE);
        return dt.isValid ? dt.toFormat('yyyy-LL-dd') : null;
    }
    const normalized = normalizeFilterDateToUtcIso(value, isEnd) || String(value || '').trim();
    const dt = DateTime.fromISO(normalized, { setZone: true }).setZone(APP_TIMEZONE);
    if (!dt.isValid) return null;
    return dt.toFormat('yyyy-LL-dd');
};

const isValidDateRange = (startDate, endDate) => {
    const start = DateTime.fromISO(String(startDate || ''));
    const end = DateTime.fromISO(String(endDate || ''));
    return start.isValid && end.isValid && start.startOf('day') <= end.startOf('day');
};

const holidaySchema = z.object({
    name: z.string().trim().min(1, 'Holiday name is required'),
    startDate: z.string().trim().min(1, 'Start date is required'),
    endDate: z.string().trim().min(1, 'End date is required'),
    siteId: z.union([z.number(), z.string()]).optional().nullable(),
    isActive: z.boolean().optional(),
}).refine((data) => isValidDateRange(data.startDate, data.endDate), {
    message: 'End date must be on or after start date',
    path: ['endDate'],
});

const leaveCreateSchema = z.object({
    employeeId: z.union([z.number(), z.string()]).optional().nullable(),
    staffId: z.string().trim().optional().nullable(),
    leaveType: z.string().trim().optional().nullable(),
    startDate: z.string().trim().min(1, 'Start date is required'),
    endDate: z.string().trim().min(1, 'End date is required'),
    status: z.enum(['pending', 'approved', 'rejected']).optional(),
    notes: z.string().trim().max(500).optional().nullable(),
}).refine((data) => data.employeeId || data.staffId, {
    message: 'Select an employee',
    path: ['employeeId'],
}).refine((data) => isValidDateRange(data.startDate, data.endDate), {
    message: 'End date must be on or after start date',
    path: ['endDate'],
});

const leaveUpdateSchema = z.object({
    leaveType: z.string().trim().optional(),
    startDate: z.string().trim().optional(),
    endDate: z.string().trim().optional(),
    status: z.enum(['pending', 'approved', 'rejected']).optional(),
    notes: z.string().trim().max(500).optional().nullable(),
}).refine((data) => {
    if (!data.startDate || !data.endDate) return true;
    return isValidDateRange(data.startDate, data.endDate);
}, {
    message: 'End date must be on or after start date',
    path: ['endDate'],
});

module.exports = ({ router, pool, authenticateToken, authorizeRole, normalizeFilterDateToUtcIso }) => {
    router.get('/hr/calendar/holidays', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor', 'Payroll', 'Finance']), async (req, res) => {
        const { startDate, endDate } = req.query;
        const orgId = organizationIdFromUser(req.user);
        const params = [orgId];
        const conditions = ['h.organization_id = $1', 'h.is_active = true'];

        if (req.user.role === 'Site Supervisor') {
            params.push(req.user.siteId);
            conditions.push(`(h.site_id IS NULL OR h.site_id = $${params.length})`);
        }

        const normalizedStart = normalizeDateOnly(startDate, normalizeFilterDateToUtcIso, false);
        const normalizedEnd = normalizeDateOnly(endDate, normalizeFilterDateToUtcIso, true);

        if (normalizedStart) {
            params.push(normalizedStart);
            conditions.push(`h.end_date >= $${params.length}::date`);
        }
        if (normalizedEnd) {
            params.push(normalizedEnd);
            conditions.push(`h.start_date <= $${params.length}::date`);
        }

        try {
            const result = await pool.query(
                `SELECT
                    h.id,
                    h.name,
                    h.start_date,
                    h.end_date,
                    h.site_id,
                    h.is_active,
                    s.name AS site_name
                 FROM public_holidays h
                 LEFT JOIN sites s ON h.site_id = s.id
                 WHERE ${conditions.join(' AND ')}
                 ORDER BY h.start_date DESC, h.name ASC`,
                params
            );
            res.json(result.rows);
        } catch (err) {
            console.error('Error fetching holidays:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/calendar/holidays', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        if (!req.body) return res.status(400).json({ error: 'Missing request body' });
        const parsed = holidaySchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid holiday payload' });
        }

        const normalizedStart = normalizeDateOnly(parsed.data.startDate, normalizeFilterDateToUtcIso, false);
        const normalizedEnd = normalizeDateOnly(parsed.data.endDate, normalizeFilterDateToUtcIso, true);
        if (!normalizedStart || !normalizedEnd) {
            return res.status(400).json({ error: 'Invalid holiday dates' });
        }

        const rawSiteId = parsed.data.siteId;
        const siteId = rawSiteId === '' || rawSiteId === null || rawSiteId === undefined ? null : Number.parseInt(String(rawSiteId), 10);
        if (siteId !== null && Number.isNaN(siteId)) {
            return res.status(400).json({ error: 'Invalid siteId' });
        }

        try {
            const orgId = organizationIdFromUser(req.user);
            if (siteId !== null) {
                const siteOk = await pool.query(
                    'SELECT 1 FROM sites WHERE id = $1 AND organization_id = $2 LIMIT 1',
                    [siteId, orgId]
                );
                if (siteOk.rowCount === 0) return res.status(400).json({ error: 'Invalid site for this organization' });
            }
            const result = await pool.query(
                `INSERT INTO public_holidays (organization_id, name, start_date, end_date, site_id, is_active, created_by)
                 VALUES ($1, $2, $3, $4, $5, $6, $7)
                 RETURNING *`,
                [orgId, parsed.data.name, normalizedStart, normalizedEnd, siteId, parsed.data.isActive !== false, req.user.id]
            );
            res.status(201).json(result.rows[0]);
        } catch (err) {
            console.error('Error creating holiday:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.delete('/hr/calendar/holidays/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                'DELETE FROM public_holidays WHERE id = $1 AND organization_id = $2 RETURNING id',
                [req.params.id, orgId]
            );
            if (result.rows.length === 0) {
                return res.status(404).json({ error: 'Holiday not found' });
            }
            res.json({ message: 'Holiday removed' });
        } catch (err) {
            console.error('Error deleting holiday:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/calendar/leaves', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor', 'Payroll', 'Finance']), async (req, res) => {
        const { startDate, endDate, status = '' } = req.query;
        const orgId = organizationIdFromUser(req.user);
        const params = [orgId];
        const conditions = ['e.organization_id = $1'];

        if (req.user.role === 'Site Supervisor') {
            params.push(req.user.siteId);
            conditions.push(`e.site_id = $${params.length}`);
        }

        const normalizedStart = normalizeDateOnly(startDate, normalizeFilterDateToUtcIso, false);
        const normalizedEnd = normalizeDateOnly(endDate, normalizeFilterDateToUtcIso, true);

        if (normalizedStart) {
            params.push(normalizedStart);
            conditions.push(`l.end_date >= $${params.length}::date`);
        }
        if (normalizedEnd) {
            params.push(normalizedEnd);
            conditions.push(`l.start_date <= $${params.length}::date`);
        }
        if (status) {
            params.push(status);
            conditions.push(`l.status = $${params.length}`);
        }

        const whereClause = `WHERE ${conditions.join(' AND ')}`;

        try {
            const result = await pool.query(
                `SELECT
                    l.id,
                    l.employee_id,
                    l.leave_type,
                    l.start_date,
                    l.end_date,
                    l.status,
                    l.notes,
                    l.created_at,
                    e.staff_id,
                    e.first_name,
                    e.last_name,
                    e.site_id,
                    s.name AS site_name
                 FROM employee_leaves l
                 JOIN employees e ON l.employee_id = e.id
                 LEFT JOIN sites s ON e.site_id = s.id
                 ${whereClause}
                 ORDER BY l.start_date DESC, e.staff_id ASC`,
                params
            );
            res.json(result.rows);
        } catch (err) {
            console.error('Error fetching leaves:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/calendar/leaves', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        if (!req.body) return res.status(400).json({ error: 'Missing request body' });
        const parsed = leaveCreateSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid leave payload' });
        }

        const normalizedStart = normalizeDateOnly(parsed.data.startDate, normalizeFilterDateToUtcIso, false);
        const normalizedEnd = normalizeDateOnly(parsed.data.endDate, normalizeFilterDateToUtcIso, true);
        if (!normalizedStart || !normalizedEnd) {
            return res.status(400).json({ error: 'Invalid leave dates' });
        }

        const employeeLookupField = parsed.data.employeeId ? 'id' : 'staff_id';
        const employeeLookupValue = parsed.data.employeeId ? Number.parseInt(String(parsed.data.employeeId), 10) : parsed.data.staffId;
        if (employeeLookupField === 'id' && Number.isNaN(employeeLookupValue)) {
            return res.status(400).json({ error: 'Invalid employeeId' });
        }

        try {
            const orgId = organizationIdFromUser(req.user);
            const employeeResult = await pool.query(
                `SELECT id, staff_id, site_id FROM employees WHERE ${employeeLookupField} = $1 AND organization_id = $2`,
                [employeeLookupValue, orgId]
            );

            if (employeeResult.rows.length === 0) {
                return res.status(404).json({ error: 'Employee not found' });
            }

            const employee = employeeResult.rows[0];
            if (req.user.role === 'Site Supervisor' && employee.site_id !== req.user.siteId) {
                return res.status(403).json({ error: 'You can only manage leave for employees from your site.' });
            }

            const result = await pool.query(
                `INSERT INTO employee_leaves (employee_id, leave_type, start_date, end_date, status, notes, created_by)
                 VALUES ($1, $2, $3, $4, $5, $6, $7)
                 RETURNING *`,
                [
                    employee.id,
                    parsed.data.leaveType || 'Annual Leave',
                    normalizedStart,
                    normalizedEnd,
                    parsed.data.status || 'approved',
                    parsed.data.notes || null,
                    req.user.id
                ]
            );

            res.status(201).json(result.rows[0]);
        } catch (err) {
            console.error('Error creating leave:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.patch('/hr/calendar/leaves/:id', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        if (!req.body) return res.status(400).json({ error: 'Missing request body' });
        const parsed = leaveUpdateSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid leave payload' });
        }

        try {
            const orgId = organizationIdFromUser(req.user);
            const existing = await pool.query(
                `SELECT l.id, l.start_date, l.end_date, l.leave_type, l.status, l.notes, e.site_id
                 FROM employee_leaves l
                 JOIN employees e ON l.employee_id = e.id
                 WHERE l.id = $1 AND e.organization_id = $2`,
                [req.params.id, orgId]
            );

            if (existing.rows.length === 0) {
                return res.status(404).json({ error: 'Leave record not found' });
            }

            const current = existing.rows[0];
            if (req.user.role === 'Site Supervisor' && current.site_id !== req.user.siteId) {
                return res.status(403).json({ error: 'You can only manage leave for employees from your site.' });
            }

            const startDate = parsed.data.startDate || current.start_date;
            const endDate = parsed.data.endDate || current.end_date;
            const normalizedStart = normalizeDateOnly(startDate, normalizeFilterDateToUtcIso, false);
            const normalizedEnd = normalizeDateOnly(endDate, normalizeFilterDateToUtcIso, true);

            if (!normalizedStart || !normalizedEnd || !isValidDateRange(normalizedStart, normalizedEnd)) {
                return res.status(400).json({ error: 'Invalid leave date range' });
            }

            const result = await pool.query(
                `UPDATE employee_leaves
                 SET leave_type = $1,
                     start_date = $2,
                     end_date = $3,
                     status = $4,
                     notes = $5
                 WHERE id = $6
                 RETURNING *`,
                [
                    parsed.data.leaveType || current.leave_type,
                    normalizedStart,
                    normalizedEnd,
                    parsed.data.status || current.status,
                    parsed.data.notes !== undefined ? (parsed.data.notes || null) : current.notes,
                    req.params.id
                ]
            );

            res.json(result.rows[0]);
        } catch (err) {
            console.error('Error updating leave:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.delete('/hr/calendar/leaves/:id', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const existing = await pool.query(
                `SELECT l.id, e.site_id
                 FROM employee_leaves l
                 JOIN employees e ON l.employee_id = e.id
                 WHERE l.id = $1 AND e.organization_id = $2`,
                [req.params.id, orgId]
            );

            if (existing.rows.length === 0) {
                return res.status(404).json({ error: 'Leave record not found' });
            }

            if (req.user.role === 'Site Supervisor' && existing.rows[0].site_id !== req.user.siteId) {
                return res.status(403).json({ error: 'You can only manage leave for employees from your site.' });
            }

            await pool.query('DELETE FROM employee_leaves WHERE id = $1', [req.params.id]);
            res.json({ message: 'Leave removed' });
        } catch (err) {
            console.error('Error deleting leave:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });
};
