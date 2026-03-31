const db = require('../utils/db');

const CHECKLIST_TYPES = [
    { value: 'high_risk_hourly', label: 'High Risk – Hourly Checklist', frequency: 'hourly' },
    { value: 'daily_moderate', label: 'Moderate Risk – Daily Checklist', frequency: 'daily' },
    { value: 'daily_low', label: 'Low Risk – Daily Checklist', frequency: 'daily' },
    { value: 'daily_minimal', label: 'Minimal Risk – Daily Checklist', frequency: 'daily' },
    { value: 'weekly_minimal', label: 'Minimal Risk – Weekly Checklist', frequency: 'weekly' },
    { value: 'weekly_moderate_residential', label: 'Moderate Risk – Weekend Residential Checklist', frequency: 'weekly' },
];

const getChecklistTypes = (req, res) => {
    res.json(CHECKLIST_TYPES);
};

const getChecklistItems = async (req, res) => {
    const { type } = req.query;
    try {
        const query = type
            ? 'SELECT * FROM checklist_items WHERE checklist_type = $1 AND active = true ORDER BY sequence ASC'
            : 'SELECT * FROM checklist_items WHERE active = true ORDER BY checklist_type, sequence ASC';
        const params = type ? [type] : [];
        const result = await db.query(query, params);
        res.json(result.rows);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

// Submit a completed checklist + check-out. Saves checklist to attendance_checklist_lines only (no report; reports are created by managers).
const submitChecklist = async (req, res) => {
    const employeeId = req.user.id;
    const { attendanceId, locationId, checklistType, items, notes, lat, lng } = req.body;
    // items = [{ item_id, checked, notes }]

    const client = await db.pool.connect();
    try {
        await client.query('BEGIN');

        const checkoutResult = await client.query(
            `UPDATE attendance 
             SET check_out = NOW(), lat_out = $1, lng_out = $2, 
                 notes = $3, status = 'completed'
             WHERE id = $4 AND employee_id = $5 AND check_out IS NULL
             RETURNING *`,
            [lat, lng, notes, attendanceId, employeeId]
        );

        if (checkoutResult.rows.length === 0) {
            await client.query('ROLLBACK');
            return res.status(404).json({ error: 'No active check-in found' });
        }

        for (const item of items) {
            await client.query(
                `INSERT INTO attendance_checklist_lines (attendance_id, item_id, checked, notes)
                 VALUES ($1, $2, $3, $4)`,
                [attendanceId, item.item_id, item.checked, item.notes || null]
            );
        }

        await client.query('COMMIT');
        res.status(201).json({ attendance: checkoutResult.rows[0], message: 'Checklist saved. Report can be created by a manager.' });

    } catch (error) {
        await client.query('ROLLBACK');
        console.error('Checklist submit error:', error);
        res.status(500).json({ error: error.message });
    } finally {
        client.release();
    }
};

// Get monthly report data for admin view (like the PDF grid)
const getMonthlyReport = async (req, res) => {
    const { location_id, month, year, checklist_type } = req.query;
    const targetMonth = parseInt(month) || new Date().getMonth() + 1;
    const targetYear = parseInt(year) || new Date().getFullYear();

    try {
        const result = await db.query(
            `SELECT 
                r.id as report_id,
                r.checklist_type,
                r.period_label,
                r.date,
                r.status,
                l.name as location_name,
                l.id as location_id,
                e.name as employee_name,
                DATE_PART('day', r.date) as day_of_period,
                DATE_PART('hour', a.check_in) as hour_of_day,
                COUNT(rl.id) FILTER (WHERE rl.checked = true) as items_completed,
                COUNT(rl.id) as items_total
             FROM reports r
             LEFT JOIN attendance a ON r.attendance_id = a.id
             LEFT JOIN locations l ON r.location_id = l.id
             LEFT JOIN employees e ON r.employee_id = e.id
             LEFT JOIN report_lines rl ON r.id = rl.report_id
             WHERE DATE_PART('month', r.date) = $1
               AND DATE_PART('year', r.date) = $2
               ${location_id ? 'AND r.location_id = $3' : ''}
               ${checklist_type ? `AND r.checklist_type = $${location_id ? 4 : 3}` : ''}
             GROUP BY r.id, r.checklist_type, r.period_label, r.date, r.status,
                      l.name, l.id, e.name, a.check_in
             ORDER BY l.name, r.date ASC`,
            [targetMonth, targetYear, ...(location_id ? [location_id] : []), ...(checklist_type ? [checklist_type] : [])]
        );
        res.json(result.rows);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

// Get all reports with details
const getReports = async (req, res) => {
    try {
        const result = await db.query(
            `SELECT r.*, l.name as location_name, e.name as employee_name,
                    COUNT(rl.id) FILTER (WHERE rl.checked = true) as items_completed,
                    COUNT(rl.id) as items_total
             FROM reports r
             LEFT JOIN locations l ON r.location_id = l.id
             LEFT JOIN employees e ON r.employee_id = e.id
             LEFT JOIN report_lines rl ON r.id = rl.report_id
             GROUP BY r.id, l.name, e.name
             ORDER BY r.date DESC
             LIMIT 200`
        );
        res.json(result.rows);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

// Completed attendances that don't have a report yet (for managers to create report)
const getCompletedAttendancesForReports = async (req, res) => {
    try {
        const result = await db.query(
            `SELECT a.id, a.check_in, a.check_out, a.notes as attendance_notes,
                    l.name as location_name, l.id as location_id,
                    e.name as employee_name, p.name as project_name
             FROM attendance a
             LEFT JOIN locations l ON a.location_id = l.id
             LEFT JOIN projects p ON l.project_id = p.id
             LEFT JOIN employees e ON a.employee_id = e.id
             LEFT JOIN reports r ON r.attendance_id = a.id
             WHERE a.check_out IS NOT NULL AND r.id IS NULL
             ORDER BY a.check_out DESC
             LIMIT 100`
        );
        const rows = result.rows;
        const withChecklistType = await Promise.all(rows.map(async (row) => {
            const sched = await db.query(
                'SELECT checklist_type FROM schedules WHERE location_id = $1 AND active = true LIMIT 1',
                [row.location_id]
            );
            return { ...row, checklist_type: sched.rows[0]?.checklist_type || 'daily_moderate' };
        }));
        res.json(withChecklistType);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

// Create a report from a completed attendance (manager only)
const createReportFromAttendance = async (req, res) => {
    const { attendance_id } = req.body;
    if (!attendance_id) return res.status(400).json({ error: 'attendance_id required' });

    const client = await db.pool.connect();
    try {
        await client.query('BEGIN');
        const att = await client.query(
            `SELECT a.*, l.name as location_name
             FROM attendance a
             LEFT JOIN locations l ON a.location_id = l.id
             WHERE a.id = $1 AND a.check_out IS NOT NULL`,
            [attendance_id]
        );
        if (att.rows.length === 0) {
            await client.query('ROLLBACK');
            return res.status(404).json({ error: 'Completed attendance not found' });
        }
        const a = att.rows[0];
        const sched = await client.query(
            'SELECT checklist_type FROM schedules WHERE location_id = $1 AND active = true LIMIT 1',
            [a.location_id]
        );
        const checklistType = sched.rows[0]?.checklist_type || 'daily_moderate';
        const existing = await client.query('SELECT id FROM reports WHERE attendance_id = $1', [attendance_id]);
        if (existing.rows.length > 0) {
            await client.query('ROLLBACK');
            return res.status(400).json({ error: 'A report already exists for this attendance' });
        }
        const periodLabel = new Date().toLocaleString('en-US', { month: 'long', year: 'numeric' });
        const reportIns = await client.query(
            `INSERT INTO reports (attendance_id, employee_id, location_id, checklist_type, period_label, date, status, notes)
             VALUES ($1, $2, $3, $4, $5, NOW(), 'completed', $6) RETURNING *`,
            [attendance_id, a.employee_id, a.location_id, checklistType, periodLabel, a.notes]
        );
        const report = reportIns.rows[0];
        const lines = await client.query(
            'SELECT item_id, checked, notes FROM attendance_checklist_lines WHERE attendance_id = $1',
            [attendance_id]
        );
        for (const line of lines.rows) {
            await client.query(
                `INSERT INTO report_lines (report_id, item_id, checked, notes) VALUES ($1, $2, $3, $4)`,
                [report.id, line.item_id, line.checked, line.notes]
            );
        }
        await client.query('COMMIT');
        res.status(201).json(report);
    } catch (error) {
        await client.query('ROLLBACK');
        console.error('Create report error:', error);
        res.status(500).json({ error: error.message });
    } finally {
        client.release();
    }
};

// Get a single report with all checklist lines
const getReportDetail = async (req, res) => {
    const { id } = req.params;
    try {
        const report = await db.query(
            `SELECT r.*, l.name as location_name, e.name as employee_name
             FROM reports r
             LEFT JOIN locations l ON r.location_id = l.id
             LEFT JOIN employees e ON r.employee_id = e.id
             WHERE r.id = $1`, [id]
        );
        const lines = await db.query(
            `SELECT rl.*, ci.name as item_name, ci.category
             FROM report_lines rl
             JOIN checklist_items ci ON rl.item_id = ci.id
             WHERE rl.report_id = $1
             ORDER BY ci.sequence ASC`, [id]
        );
        res.json({ ...report.rows[0], lines: lines.rows });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

module.exports = {
    getChecklistTypes,
    getChecklistItems,
    submitChecklist,
    getMonthlyReport,
    getReports,
    getReportDetail,
    getCompletedAttendancesForReports,
    createReportFromAttendance,
};
