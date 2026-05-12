const { organizationIdFromUser } = require('../../utils/organization');
const { fetchAttendanceReportBundle } = require('../../services/attendanceReportData');

const REPORT_READER_ROLES = ['HR Admin', 'Site Supervisor', 'Payroll', 'Finance'];

module.exports = ({ router, pool, authenticateToken, authorizeRole, normalizeFilterDateToUtcIso }) => {
    router.get('/hr/reports/presets', authenticateToken, authorizeRole(REPORT_READER_ROLES), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                `SELECT *
                 FROM report_presets
                 WHERE created_by = $1 AND organization_id = $2
                 ORDER BY updated_at DESC, created_at DESC`,
                [req.user.id, orgId]
            );
            res.json(result.rows);
        } catch (err) {
            console.error('Error fetching report presets:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/reports/presets', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const {
            name,
            dataSource = 'app',
            roleIds = [],
            siteIds = [],
            shiftIds = [],
            department = '',
            startDate = '',
            endDate = ''
        } = req.body || {};
        if (!name || !String(name).trim()) {
            return res.status(400).json({ error: 'Preset name is required' });
        }
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                `INSERT INTO report_presets
                 (organization_id, created_by, name, data_source, role_ids, site_ids, shift_ids, department, start_date, end_date, updated_at)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
                 RETURNING *`,
                [
                    orgId,
                    req.user.id,
                    String(name).trim(),
                    dataSource,
                    JSON.stringify(roleIds),
                    JSON.stringify(siteIds),
                    JSON.stringify(shiftIds),
                    department || '',
                    startDate || '',
                    endDate || ''
                ]
            );
            res.status(201).json(result.rows[0]);
        } catch (err) {
            console.error('Error creating report preset:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.delete('/hr/reports/presets/:id', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                `DELETE FROM report_presets WHERE id = $1 AND created_by = $2 AND organization_id = $3 RETURNING id`,
                [req.params.id, req.user.id, orgId]
            );
            if (result.rows.length === 0) return res.status(404).json({ error: 'Preset not found' });
            res.json({ success: true });
        } catch (err) {
            console.error('Error deleting report preset:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Get attendance report data

    router.get('/hr/reports/attendance', authenticateToken, authorizeRole(REPORT_READER_ROLES), async (req, res) => {
        const { startDate, endDate, roleId, roleIds, siteId, siteIds, shiftId, shiftIds, department } = req.query;

        try {
            const orgId = organizationIdFromUser(req.user);
            const payload = await fetchAttendanceReportBundle(pool, {
                orgId,
                userRole: req.user.role,
                userSiteId: req.user.siteId,
                dataSource: 'app',
                query: { startDate, endDate, roleId, roleIds, siteId, siteIds, shiftId, shiftIds, department },
                normalizeFilterDateToUtcIso,
            });
            res.json(payload);
        } catch (err) {
            console.error('Report error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // --- BIOMETRIC ATTENDANCE REPORT DEDICATED ENDPOINT ---
    router.get('/hr/reports/biometrics', authenticateToken, authorizeRole(REPORT_READER_ROLES), async (req, res) => {
        const { startDate, endDate, roleId, roleIds, siteId, siteIds, shiftId, shiftIds, department } = req.query;

        try {
            const orgId = organizationIdFromUser(req.user);
            const payload = await fetchAttendanceReportBundle(pool, {
                orgId,
                userRole: req.user.role,
                userSiteId: req.user.siteId,
                dataSource: 'biometrics',
                query: { startDate, endDate, roleId, roleIds, siteId, siteIds, shiftId, shiftIds, department },
                normalizeFilterDateToUtcIso,
            });
            res.json(payload);
        } catch (err) {
            console.error('Error fetching biometric report:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/reports/job-activity', authenticateToken, authorizeRole(REPORT_READER_ROLES), async (req, res) => {
        const { startDate, endDate, siteId } = req.query;
        const params = [];
        const where = [`a.check_in_time IS NOT NULL`, `a.status NOT IN ('rejected', 'voided')`];
        if (req.user.role === 'Site Supervisor') {
            params.push(Number(req.user.siteId));
            where.push(`a.site_id = $${params.length}`);
        } else if (siteId) {
            params.push(Number(siteId));
            where.push(`a.site_id = $${params.length}`);
        }
        const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
        const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);
        if (normalizedStartDate) {
            params.push(normalizedStartDate);
            where.push(`a.check_in_time >= $${params.length}`);
        }
        if (normalizedEndDate) {
            params.push(normalizedEndDate);
            where.push(`a.check_in_time <= $${params.length}`);
        }
        try {
            const result = await pool.query(
                `SELECT
                    COALESCE(a.work_context->>'jobCode', 'UNSPECIFIED') AS job_code,
                    COALESCE(a.work_context->>'activityName', 'General Duty') AS activity_name,
                    COUNT(*)::int AS attendance_days,
                    SUM(
                      CASE
                        WHEN a.check_out_time IS NOT NULL
                        THEN GREATEST(EXTRACT(EPOCH FROM (a.check_out_time - a.check_in_time)) / 3600, 0)
                        ELSE 0
                      END
                    )::numeric(10,2) AS worked_hours,
                    SUM(COALESCE(a.overtime_minutes, 0))::int AS overtime_minutes
                 FROM attendance a
                 WHERE ${where.join(' AND ')}
                 GROUP BY 1, 2
                 ORDER BY attendance_days DESC, worked_hours DESC`,
                params
            );
            res.json(result.rows);
        } catch (err) {
            console.error('Job activity report error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR Admin: View Auto-Closed attendance records
    router.get('/hr/admin/auto-closed', authenticateToken, authorizeRole(REPORT_READER_ROLES), async (req, res) => {
        try {
            const { siteId, startDate, endDate, page = 1, limit = 50 } = req.query;
            const offset = (parseInt(page) - 1) * parseInt(limit);
            const params = [];
            const conditions = [`a.auto_closed = true`];

            // Supervisors can only see their own site
            if (req.user.role === 'Site Supervisor') {
                params.push(req.user.siteId);
                conditions.push(`a.site_id = $${params.length}`);
            } else if (siteId) {
                params.push(siteId);
                conditions.push(`a.site_id = $${params.length}`);
            }
            const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
            const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);

            if (normalizedStartDate) {
                params.push(normalizedStartDate);
                conditions.push(`a.check_in_time >= $${params.length}`);
            }
            if (normalizedEndDate) {
                params.push(normalizedEndDate);
                conditions.push(`a.check_in_time <= $${params.length}`);
            }

            const whereClause = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';

            const countResult = await pool.query(
                `SELECT COUNT(*) FROM attendance a ${whereClause}`, params
            );
            const total = parseInt(countResult.rows[0].count);

            params.push(parseInt(limit), offset);
            const result = await pool.query(
                `SELECT
                a.id, a.check_in_time, a.check_out_time, a.notes, a.auto_closed,
                e.staff_id, e.first_name, e.last_name,
                s.name as site_name,
                sh.name as shift_name
             FROM attendance a
             JOIN employees e ON a.employee_id = e.id
             LEFT JOIN sites s ON a.site_id = s.id
             LEFT JOIN shifts sh ON e.shift_id = sh.id
             ${whereClause}
             ORDER BY a.check_in_time DESC
             LIMIT $${params.length - 1} OFFSET $${params.length}`,
                params
            );

            res.json({
                records: result.rows,
                total,
                page: parseInt(page),
                totalPages: Math.ceil(total / parseInt(limit))
            });
        } catch (err) {
            console.error('Auto-closed query error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });
};
