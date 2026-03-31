const db = require('../utils/db');

const getSchedules = async (req, res) => {
    try {
        const result = await db.query(
            `SELECT s.*, l.name as location_name, p.name as project_name, e.name as employee_name 
             FROM schedules s
             LEFT JOIN locations l ON s.location_id = l.id
             LEFT JOIN projects p ON l.project_id = p.id
             LEFT JOIN employees e ON s.employee_id = e.id
             ORDER BY s.start_time ASC`
        );
        res.json(result.rows);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

const createSchedule = async (req, res) => {
    const { location_id, employee_id, location_details, start_time, end_time, interval_value, interval_unit, checklist_type } = req.body;
    try {
        const result = await db.query(
            `INSERT INTO schedules (location_id, employee_id, location_details, start_time, end_time, interval_value, interval_unit, checklist_type) 
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *`,
            [location_id, employee_id || null, location_details || null, start_time, end_time || null, interval_value, interval_unit, checklist_type || 'daily_moderate']
        );
        res.status(201).json(result.rows[0]);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

const updateSchedule = async (req, res) => {
    const { id } = req.params;
    const { location_id, employee_id, location_details, start_time, end_time, interval_value, interval_unit, active, checklist_type } = req.body;
    try {
        const result = await db.query(
            `UPDATE schedules 
             SET location_id = $1, employee_id = $2, location_details = $3, start_time = $4, end_time = $5, 
                 interval_value = $6, interval_unit = $7, active = $8, checklist_type = $9
             WHERE id = $10 RETURNING *`,
            [location_id, employee_id || null, location_details || null, start_time, end_time || null, interval_value, interval_unit, active, checklist_type || 'daily_moderate', id]
        );
        res.json(result.rows[0]);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

const deleteSchedule = async (req, res) => {
    const { id } = req.params;
    try {
        await db.query('DELETE FROM schedules WHERE id = $1', [id]);
        res.status(204).send();
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

module.exports = { getSchedules, createSchedule, updateSchedule, deleteSchedule };
