const xlsx = require('xlsx');
const db = require('../utils/db');

const importSchedules = async (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: 'No file uploaded' });
    }

    try {
        const workbook = xlsx.read(req.file.buffer, { type: 'buffer' });
        const sheetName = workbook.SheetNames[0];
        const sheet = workbook.Sheets[sheetName];
        const data = xlsx.utils.sheet_to_json(sheet);

        // Expected columns: LocationCode or WashroomCode, EmployeeEmail, StartTime, IntervalValue, IntervalUnit
        const results = [];
        for (const row of data) {
            const code = row.LocationCode ?? row.WashroomCode;
            const { EmployeeEmail, StartTime, IntervalValue, IntervalUnit } = row;

            // 1. Find Location
            const locationRes = await db.query('SELECT id FROM locations WHERE code = $1', [code]);
            const location_id = locationRes.rows[0]?.id || null;

            // 2. Find Employee
            const employeeRes = await db.query('SELECT id FROM employees WHERE email = $1', [EmployeeEmail]);
            const employee_id = employeeRes.rows[0]?.id || null;

            if (location_id && employee_id) {
                const insertRes = await db.query(
                    `INSERT INTO schedules (location_id, employee_id, start_time, interval_value, interval_unit) 
                     VALUES ($1, $2, $3, $4, $5) RETURNING id`,
                    [location_id, employee_id, StartTime, IntervalValue || 2, IntervalUnit || 'hours']
                );
                results.push(insertRes.rows[0].id);
            }
        }

        res.json({ message: `Successfully imported ${results.length} schedules`, count: results.length });
    } catch (error) {
        console.error('Import error:', error);
        res.status(500).json({ error: error.message });
    }
};

module.exports = { importSchedules };
