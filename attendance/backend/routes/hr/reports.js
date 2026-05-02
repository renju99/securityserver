const { DateTime } = require('luxon');
const { APP_TIMEZONE } = require('../../utils/time');

const parseIdList = (value) => {
    if (value === undefined || value === null || value === '') return [];
    const rawValues = Array.isArray(value) ? value : String(value).split(',');
    return rawValues
        .map((entry) => Number.parseInt(String(entry).trim(), 10))
        .filter((entry) => !Number.isNaN(entry));
};

const normalizeDateOnly = (value, normalizeFilterDateToUtcIso, isEnd = false) => {
    if (!value) return null;
    if (value instanceof Date) {
        const dt = DateTime.fromJSDate(value, { zone: 'utc' }).setZone(APP_TIMEZONE);
        return dt.isValid ? dt.toFormat('yyyy-LL-dd') : null;
    }
    const normalized = normalizeFilterDateToUtcIso(value, isEnd) || String(value).trim();
    const dt = DateTime.fromISO(normalized, { setZone: true }).setZone(APP_TIMEZONE);
    return dt.isValid ? dt.toFormat('yyyy-LL-dd') : null;
};

const enumerateDateKeys = (startDate, endDate) => {
    const start = startDate instanceof Date
        ? DateTime.fromJSDate(startDate, { zone: 'utc' }).setZone(APP_TIMEZONE).startOf('day')
        : DateTime.fromISO(String(startDate), { zone: APP_TIMEZONE }).startOf('day');
    const end = endDate instanceof Date
        ? DateTime.fromJSDate(endDate, { zone: 'utc' }).setZone(APP_TIMEZONE).startOf('day')
        : DateTime.fromISO(String(endDate), { zone: APP_TIMEZONE }).startOf('day');
    if (!start.isValid || !end.isValid || start > end) return [];

    const dates = [];
    let cursor = start;
    while (cursor <= end) {
        dates.push(cursor.toFormat('yyyy-LL-dd'));
        cursor = cursor.plus({ days: 1 });
    }
    return dates;
};

const applySiteFilter = ({ query, params, fieldName, siteIds }) => {
    if (!siteIds.length) return { query, params };

    const includeUnassigned = siteIds.includes(-1);
    const scopedSiteIds = siteIds.filter((siteId) => siteId > 0);

    if (includeUnassigned && scopedSiteIds.length === 0) {
        return { query: `${query} AND ${fieldName} IS NULL`, params };
    }

    if (includeUnassigned) {
        params.push(scopedSiteIds);
        return {
            query: `${query} AND (${fieldName} IS NULL OR ${fieldName} = ANY($${params.length}))`,
            params
        };
    }

    params.push(scopedSiteIds);
    return {
        query: `${query} AND ${fieldName} = ANY($${params.length})`,
        params
    };
};

const buildCalendarPayload = async ({ pool, employees, startDateKey, endDateKey }) => {
    const realEmployees = employees.filter((employee) => Number.isInteger(employee.id));
    if (!realEmployees.length || !startDateKey || !endDateKey) {
        return { exceptions: {} };
    }

    const employeeIds = realEmployees.map((employee) => employee.id);
    const siteIds = [...new Set(realEmployees.map((employee) => employee.site_id).filter((siteId) => siteId !== null && siteId !== undefined))];

    const holidayParams = [startDateKey, endDateKey];
    let holidayWhere = `WHERE h.is_active = true AND h.end_date >= $1::date AND h.start_date <= $2::date`;
    if (siteIds.length > 0) {
        holidayParams.push(siteIds);
        holidayWhere += ` AND (h.site_id IS NULL OR h.site_id = ANY($3))`;
    } else {
        holidayWhere += ` AND h.site_id IS NULL`;
    }

    const [holidayResult, leaveResult] = await Promise.all([
        pool.query(
            `SELECT h.id, h.name, h.start_date, h.end_date, h.site_id
             FROM public_holidays h
             ${holidayWhere}`,
            holidayParams
        ),
        pool.query(
            `SELECT l.id, l.employee_id, l.leave_type, l.start_date, l.end_date
             FROM employee_leaves l
             WHERE l.employee_id = ANY($1)
               AND l.status = 'approved'
               AND l.end_date >= $2::date
               AND l.start_date <= $3::date`,
            [employeeIds, startDateKey, endDateKey]
        )
    ]);

    const employeeExceptions = {};
    const employeeById = new Map(realEmployees.map((employee) => [employee.id, employee]));

    holidayResult.rows.forEach((holiday) => {
        const dateKeys = enumerateDateKeys(holiday.start_date, holiday.end_date);
        realEmployees.forEach((employee) => {
            const appliesToEmployee = holiday.site_id === null || holiday.site_id === employee.site_id;
            if (!appliesToEmployee) return;
            const target = employeeExceptions[employee.id] || {};
            dateKeys.forEach((dateKey) => {
                if (!target[dateKey]) {
                    target[dateKey] = {
                        code: 'H',
                        kind: 'holiday',
                        label: holiday.name
                    };
                }
            });
            employeeExceptions[employee.id] = target;
        });
    });

    leaveResult.rows.forEach((leave) => {
        if (!employeeById.has(leave.employee_id)) return;
        const target = employeeExceptions[leave.employee_id] || {};
        enumerateDateKeys(leave.start_date, leave.end_date).forEach((dateKey) => {
            target[dateKey] = {
                code: 'L',
                kind: 'leave',
                label: leave.leave_type || 'Approved Leave'
            };
        });
        employeeExceptions[leave.employee_id] = target;
    });

    return { exceptions: employeeExceptions };
};

module.exports = ({ router, pool, authenticateToken, authorizeRole, normalizeFilterDateToUtcIso }) => {
    router.get('/hr/reports/presets', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        try {
            const result = await pool.query(
                `SELECT *
                 FROM report_presets
                 WHERE created_by = $1
                 ORDER BY updated_at DESC, created_at DESC`,
                [req.user.id]
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
            const result = await pool.query(
                `INSERT INTO report_presets
                 (created_by, name, data_source, role_ids, site_ids, shift_ids, department, start_date, end_date, updated_at)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                 RETURNING *`,
                [
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
            const result = await pool.query(
                `DELETE FROM report_presets WHERE id = $1 AND created_by = $2 RETURNING id`,
                [req.params.id, req.user.id]
            );
            if (result.rows.length === 0) return res.status(404).json({ error: 'Preset not found' });
            res.json({ success: true });
        } catch (err) {
            console.error('Error deleting report preset:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Get attendance report data

    router.get('/hr/reports/attendance', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { startDate, endDate, roleId, roleIds, siteId, siteIds, shiftId, shiftIds, department } = req.query;

        try {
            // 1. Fetch Employees based on filters
            let empQuery = `
            SELECT e.id, e.staff_id, e.first_name, e.last_name, e.department_name, e.site_id, e.shift_id,
                   r.name as role_name, s.name as site_name, sh.name as shift_name
            FROM employees e 
            LEFT JOIN roles r ON e.role_id = r.id 
            LEFT JOIN sites s ON e.site_id = s.id
            LEFT JOIN shifts sh ON e.shift_id = sh.id
            WHERE 1=1
        `;
            const empParams = [];
            const selectedRoleIds = parseIdList(roleIds || roleId);
            const selectedSiteIds = req.user.role === 'Site Supervisor'
                ? [Number.parseInt(String(req.user.siteId), 10)]
                : parseIdList(siteIds || siteId);
            const selectedShiftIds = parseIdList(shiftIds || shiftId);

            if (selectedRoleIds.length > 0) {
                empParams.push(selectedRoleIds);
                empQuery += ` AND e.role_id = ANY($${empParams.length})`;
            }

            const siteFilter = applySiteFilter({
                query: empQuery,
                params: empParams,
                fieldName: 'e.site_id',
                siteIds: selectedSiteIds
            });
            empQuery = siteFilter.query;

            if (selectedShiftIds.length > 0) {
                siteFilter.params.push(selectedShiftIds);
                empQuery += ` AND e.shift_id = ANY($${siteFilter.params.length})`;
            }

            if (department) {
                siteFilter.params.push(`%${department}%`);
                empQuery += ` AND e.department_name ILIKE $${siteFilter.params.length}`;
            }

            empQuery += ` ORDER BY e.staff_id ASC`;

            const empResult = await pool.query(empQuery, siteFilter.params);
            const employees = empResult.rows;

            if (employees.length === 0) {
                return res.json({ employees: [], attendance: {}, calendar: { exceptions: {} } });
            }

            const empIds = employees.map(e => e.id);

            // 2. Fetch Attendance for these employees in date range
            let attQuery = `
            SELECT employee_id, check_in_time, check_out_time, site_id
            FROM attendance 
            WHERE employee_id = ANY($1)
        `;
            // Reset params for new query
            const attParams = [empIds];
            let attParamIdx = 2; // $1 is empIds

            const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
            const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);
            const startDateKey = normalizeDateOnly(startDate, normalizeFilterDateToUtcIso, false);
            const endDateKey = normalizeDateOnly(endDate, normalizeFilterDateToUtcIso, true);

            if (normalizedStartDate) {
                attQuery += ` AND check_in_time >= $${attParamIdx++}`;
                attParams.push(normalizedStartDate);
            }
            if (normalizedEndDate) {
                attQuery += ` AND check_in_time <= $${attParamIdx++}`;
                attParams.push(normalizedEndDate);
            }

            attQuery += ` ORDER BY check_in_time ASC`;

            const attResult = await pool.query(attQuery, attParams);

            // Group by Employee ID
            const attendanceMap = {};
            attResult.rows.forEach(row => {
                if (!attendanceMap[row.employee_id]) attendanceMap[row.employee_id] = [];
                attendanceMap[row.employee_id].push(row);
            });

            const calendar = await buildCalendarPayload({ pool, employees, startDateKey, endDateKey });

            res.json({ employees, attendance: attendanceMap, calendar });

        } catch (err) {
            console.error('Report error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // --- BIOMETRIC ATTENDANCE REPORT DEDICATED ENDPOINT ---
    router.get('/hr/reports/biometrics', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { startDate, endDate, roleId, roleIds, siteId, siteIds, shiftId, shiftIds, department } = req.query;

        try {
            // 1. Fetch relevant employees
            let empQuery = `
            SELECT e.id, e.staff_id, e.first_name, e.last_name, e.department_name, e.site_id, e.shift_id,
                   r.name as role_name, s.name as site_name, sh.name as shift_name
            FROM employees e 
            LEFT JOIN roles r ON e.role_id = r.id 
            LEFT JOIN sites s ON e.site_id = s.id
            LEFT JOIN shifts sh ON e.shift_id = sh.id
            WHERE 1=1
        `;
            const empParams = [];
            const selectedRoleIds = parseIdList(roleIds || roleId);
            const selectedSiteIds = req.user.role === 'Site Supervisor'
                ? [Number.parseInt(String(req.user.siteId), 10)]
                : parseIdList(siteIds || siteId);
            const selectedShiftIds = parseIdList(shiftIds || shiftId);

            if (selectedRoleIds.length > 0) {
                empParams.push(selectedRoleIds);
                empQuery += ` AND e.role_id = ANY($${empParams.length})`;
            }

            const siteFilter = applySiteFilter({
                query: empQuery,
                params: empParams,
                fieldName: 'e.site_id',
                siteIds: selectedSiteIds
            });
            empQuery = siteFilter.query;

            if (selectedShiftIds.length > 0) {
                siteFilter.params.push(selectedShiftIds);
                empQuery += ` AND e.shift_id = ANY($${siteFilter.params.length})`;
            }

            if (department) {
                siteFilter.params.push(`%${department}%`);
                empQuery += ` AND e.department_name ILIKE $${siteFilter.params.length}`;
            }

            empQuery += ` ORDER BY e.staff_id ASC`;
            const empResult = await pool.query(empQuery, siteFilter.params);
            let employees = empResult.rows;
            const validStaffIds = employees.map(e => e.staff_id).filter(id => id);

            // 2. Fetch biometric logs
            let logQuery = `
            SELECT staff_id, timestamp::date as log_date, min(timestamp) as check_in_time, max(timestamp) as check_out_time, min(raw_data::text) as raw_data
            FROM biometric_logs
            WHERE 1=1
        `;
            const logParams = [];
            let logParamIdx = 1;

            const hasFilters = selectedRoleIds.length > 0 || selectedSiteIds.length > 0 || selectedShiftIds.length > 0 || !!department;
            if (validStaffIds.length > 0) {
                if (hasFilters) {
                    logQuery += ` AND staff_id = ANY($${logParamIdx++})`;
                    logParams.push(validStaffIds);
                }
            } else if (hasFilters) {
                return res.json({ employees: [], attendance: {}, calendar: { exceptions: {} } });
            }

            const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
            const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);
            const startDateKey = normalizeDateOnly(startDate, normalizeFilterDateToUtcIso, false);
            const endDateKey = normalizeDateOnly(endDate, normalizeFilterDateToUtcIso, true);

            if (normalizedStartDate) {
                logQuery += ` AND timestamp >= $${logParamIdx++}`;
                logParams.push(normalizedStartDate);
            }
            if (normalizedEndDate) {
                logQuery += ` AND timestamp <= $${logParamIdx++}`;
                logParams.push(normalizedEndDate);
            }

            logQuery += ` GROUP BY staff_id, timestamp::date ORDER BY timestamp::date ASC`;

            const logResult = await pool.query(logQuery, logParams);

            // 3. Map logs to employees and handle unregistered terminals users (ghosts)
            const attendanceMap = {};
            const staffIdMap = {};
            employees.forEach(e => staffIdMap[e.staff_id] = e);

            logResult.rows.forEach(log => {
                const staffId = log.staff_id;

                if (!staffIdMap[staffId] && !hasFilters && staffId) {
                    let rawDataObj = {};
                    try { rawDataObj = JSON.parse(log.raw_data); } catch (e) { }
                    const fallbackName = rawDataObj?.personName || rawDataObj?.personId || staffId;
                    const ghostEmp = {
                        id: `ghost-${staffId}`,
                        staff_id: staffId,
                        first_name: fallbackName,
                        department_name: 'Terminal Data',
                        role_name: '-',
                        site_name: '-'
                    };
                    employees.push(ghostEmp);
                    staffIdMap[staffId] = ghostEmp;
                }

                if (staffIdMap[staffId]) {
                    const empId = staffIdMap[staffId].id;
                    if (!attendanceMap[empId]) attendanceMap[empId] = [];

                    const checkIn = new Date(log.check_in_time);
                    const checkOut = new Date(log.check_out_time);
                    const finalCheckOut = checkIn.getTime() === checkOut.getTime() ? null : log.check_out_time;

                    attendanceMap[empId].push({
                        check_in_time: log.check_in_time,
                        check_out_time: finalCheckOut
                    });
                }
            });

            // Filter out employees without logs to keep report clean
            employees = employees.filter(e => attendanceMap[e.id] && attendanceMap[e.id].length > 0);

            const calendar = await buildCalendarPayload({ pool, employees, startDateKey, endDateKey });

            res.json({ employees, attendance: attendanceMap, calendar });

        } catch (err) {
            console.error('Error fetching biometric report:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/reports/job-activity', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { startDate, endDate, siteId } = req.query;
        const params = [];
        const where = [`a.check_in_time IS NOT NULL`];
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
    router.get('/hr/admin/auto-closed', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
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
