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

// Submit a completed checklist + auto check-out
const submitChecklist = async (req, res) => {
    const employeeId = req.user.id;
    const { attendanceId, washroomId, checklistType, items, notes, lat, lng } = req.body;
    // items = [{ item_id, checked, notes }]

    const client = await db.pool.connect();
    try {
        await client.query('BEGIN');

        // 1. Check out from attendance
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

        // 2. Create report
        const now = new Date();
        const periodLabel = now.toLocaleString('en-US', { month: 'long', year: 'numeric' });
        const reportResult = await client.query(
            `INSERT INTO reports (attendance_id, employee_id, washroom_id, checklist_type, period_label, date, status, notes)
             VALUES ($1, $2, $3, $4, $5, NOW(), 'completed', $6) RETURNING *`,
            [attendanceId, employeeId, washroomId, checklistType, periodLabel, notes]
        );
        const report = reportResult.rows[0];

        // 3. Insert checklist lines
        for (const item of items) {
            await client.query(
                `INSERT INTO report_lines (report_id, item_id, checked, notes, completed_at)
                 VALUES ($1, $2, $3, $4, NOW())`,
                [report.id, item.item_id, item.checked, item.notes || null]
            );
        }

        await client.query('COMMIT');
        res.status(201).json({ report, attendance: checkoutResult.rows[0] });

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
    const { washroom_id, month, year, checklist_type } = req.query;
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
                w.name as washroom_name,
                w.id as washroom_id,
                e.name as employee_name,
                DATE_PART('day', r.date) as day_of_period,
                DATE_PART('hour', a.check_in) as hour_of_day,
                COUNT(rl.id) FILTER (WHERE rl.checked = true) as items_completed,
                COUNT(rl.id) as items_total
             FROM reports r
             LEFT JOIN attendance a ON r.attendance_id = a.id
             LEFT JOIN washrooms w ON r.washroom_id = w.id
             LEFT JOIN employees e ON r.employee_id = e.id
             LEFT JOIN report_lines rl ON r.id = rl.report_id
             WHERE DATE_PART('month', r.date) = $1
               AND DATE_PART('year', r.date) = $2
               ${washroom_id ? 'AND r.washroom_id = $3' : ''}
               ${checklist_type ? `AND r.checklist_type = $${washroom_id ? 4 : 3}` : ''}
             GROUP BY r.id, r.checklist_type, r.period_label, r.date, r.status,
                      w.name, w.id, e.name, a.check_in
             ORDER BY w.name, r.date ASC`,
            [targetMonth, targetYear, ...(washroom_id ? [washroom_id] : []), ...(checklist_type ? [checklist_type] : [])]
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
            `SELECT r.*, w.name as washroom_name, e.name as employee_name,
                    COUNT(rl.id) FILTER (WHERE rl.checked = true) as items_completed,
                    COUNT(rl.id) as items_total
             FROM reports r
             LEFT JOIN washrooms w ON r.washroom_id = w.id
             LEFT JOIN employees e ON r.employee_id = e.id
             LEFT JOIN report_lines rl ON r.id = rl.report_id
             GROUP BY r.id, w.name, e.name
             ORDER BY r.date DESC
             LIMIT 200`
        );
        res.json(result.rows);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

// Get a single report with all checklist lines
const getReportDetail = async (req, res) => {
    const { id } = req.params;
    try {
        const report = await db.query(
            `SELECT r.*, w.name as washroom_name, e.name as employee_name
             FROM reports r
             LEFT JOIN washrooms w ON r.washroom_id = w.id
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
    getReportDetail
};
