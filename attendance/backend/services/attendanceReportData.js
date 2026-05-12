/**
 * Shared attendance report payloads for HTTP routes and scheduled export jobs.
 */

const { DateTime } = require('luxon');
const { APP_TIMEZONE } = require('../utils/time');

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

/**
 * @param {import('pg').Pool} pool
 * @param {{
 *   orgId: number;
 *   userRole: string;
 *   userSiteId: number | string | null | undefined;
 *   dataSource: 'app'|'biometrics';
 *   query: Record<string, unknown>;
 *   normalizeFilterDateToUtcIso: (v: unknown, isEnd?: boolean) => string | null;
 * }} opts
 */
async function fetchAttendanceReportBundle(pool, opts) {
    const { orgId, userRole, userSiteId, dataSource, query, normalizeFilterDateToUtcIso } = opts;
    const {
        startDate,
        endDate,
        roleId,
        roleIds,
        siteId,
        siteIds,
        shiftId,
        shiftIds,
        department
    } = query;

    let empQuery = `
            SELECT e.id, e.staff_id, e.first_name, e.last_name, e.department_name, e.site_id, e.shift_id,
                   r.name as role_name, s.name as site_name, sh.name as shift_name
            FROM employees e 
            LEFT JOIN roles r ON e.role_id = r.id 
            LEFT JOIN sites s ON e.site_id = s.id
            LEFT JOIN shifts sh ON e.shift_id = sh.id
            WHERE e.organization_id = $1
        `;
    const empParams = [orgId];
    const selectedRoleIds = parseIdList(roleIds || roleId);
    const selectedSiteIds = userRole === 'Site Supervisor'
        ? [Number.parseInt(String(userSiteId), 10)]
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

    const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
    const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);
    const startDateKey = normalizeDateOnly(startDate, normalizeFilterDateToUtcIso, false);
    const endDateKey = normalizeDateOnly(endDate, normalizeFilterDateToUtcIso, true);

    if (dataSource === 'app') {
        if (employees.length === 0) {
            return { employees: [], attendance: {}, calendar: { exceptions: {} } };
        }
        const empIds = employees.map((e) => e.id);
        let attQuery = `
            SELECT employee_id, check_in_time, check_out_time, site_id
            FROM attendance 
            WHERE employee_id = ANY($1)
              AND status NOT IN ('rejected', 'voided')
        `;
        const attParams = [empIds];
        let attParamIdx = 2;
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
        const attendanceMap = {};
        attResult.rows.forEach((row) => {
            if (!attendanceMap[row.employee_id]) attendanceMap[row.employee_id] = [];
            attendanceMap[row.employee_id].push(row);
        });
        const calendar = await buildCalendarPayload({ pool, employees, startDateKey, endDateKey });
        return { employees, attendance: attendanceMap, calendar };
    }

    const validStaffIds = employees.map((e) => e.staff_id).filter(Boolean);
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
        return { employees: [], attendance: {}, calendar: { exceptions: {} } };
    }
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
    const attendanceMap = {};
    const staffIdMap = {};
    employees.forEach((e) => {
        staffIdMap[e.staff_id] = e;
    });

    logResult.rows.forEach((log) => {
        const staffId = log.staff_id;
        if (!staffIdMap[staffId] && !hasFilters && staffId) {
            let rawDataObj = {};
            try {
                rawDataObj = JSON.parse(log.raw_data);
            } catch (_e) {
                /* ignore */
            }
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
    employees = employees.filter((e) => attendanceMap[e.id] && attendanceMap[e.id].length > 0);
    const calendar = await buildCalendarPayload({ pool, employees, startDateKey, endDateKey });
    return { employees, attendance: attendanceMap, calendar };
}

/**
 * Flatten report bundle to row objects (same keys as HR CSV export).
 * @param {{ employees: any[]; attendance: Record<string, any[]>; calendar: { exceptions: Record<string, Record<string, { code: string; label: string }>> } }} bundle
 */
function flattenAttendanceReportRows(bundle) {
    const rows = [];
    const employees = bundle.employees || [];
    const exceptions = bundle.calendar?.exceptions || {};
    for (const emp of employees) {
        const key = String(emp.id);
        const logs = bundle.attendance[key] || bundle.attendance[emp.id] || [];
        for (const log of logs) {
            const inRaw = log.check_in_time;
            const inDate = inRaw ? new Date(inRaw).toISOString().slice(0, 10) : '';
            const ex = exceptions[key]?.[inDate];
            rows.push({
                'Staff ID': emp.staff_id || '',
                Name: `${emp.first_name || ''} ${emp.last_name || ''}`.trim(),
                Department: emp.department_name || '',
                Site: emp.site_name || '',
                Role: emp.role_name || '',
                Date: inDate,
                'Check In': inRaw || '',
                'Check Out': log.check_out_time ? String(log.check_out_time) : '',
                'Day note': ex ? `${ex.code}: ${ex.label}` : ''
            });
        }
    }
    return rows;
}

module.exports = {
    fetchAttendanceReportBundle,
    flattenAttendanceReportRows,
};
