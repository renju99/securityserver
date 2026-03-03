const db = require('../utils/db');
const { calculateDistance, isPointInPolygon } = require('../utils/geoUtils');
const { getIo } = require('../utils/socket');

const checkIn = async (req, res) => {
    const { qrToken, lat, lng, deviceSerial } = req.body;
    const employeeId = req.user.id;

    try {
        // 1. Find Washroom and Schedule
        const washroomResult = await db.query(
            `SELECT w.*, p.geofence_lat, p.geofence_lng, p.geofence_radius, p.geofence_polygon, p.use_polygon 
             FROM washrooms w 
             JOIN projects p ON w.project_id = p.id 
             WHERE w.qr_token = $1 AND w.active = true`,
            [qrToken]
        );

        if (washroomResult.rows.length === 0) {
            return res.status(404).json({ error: 'Washroom not found' });
        }

        const washroom = washroomResult.rows[0];

        // 2. Validate Geofence
        let distance = calculateDistance(lat, lng, washroom.geofence_lat, washroom.geofence_lng);
        let isWithin = false;

        if (washroom.use_polygon && washroom.geofence_polygon) {
            isWithin = isPointInPolygon(lat, lng, JSON.parse(washroom.geofence_polygon));
        } else {
            isWithin = distance <= (washroom.geofence_radius || 100.0);
        }

        if (!isWithin) {
            return res.status(403).json({ error: 'Outside geofence area', distance, limit: washroom.geofence_radius });
        }

        // 3. Find matching active schedule for this employee and washroom
        const scheduleResult = await db.query(
            `SELECT * FROM schedules 
             WHERE (washroom_id = $1 OR washroom_id IS NULL) 
             AND (employee_id = $2 OR employee_id IS NULL) 
             AND active = true 
             ORDER BY start_time ASC LIMIT 1`,
            [washroom.id, employeeId]
        );

        const scheduleId = scheduleResult.rows[0]?.id || null;

        // 4. Create Attendance Record
        const checkInResult = await db.query(
            `INSERT INTO attendance (employee_id, washroom_id, project_id, schedule_id, check_in, lat_in, lng_in, distance_from_target, device_serial, status)
             VALUES ($1, $2, $3, $4, NOW(), $5, $6, $7, $8, $9) RETURNING *`,
            [employeeId, washroom.id, washroom.project_id, scheduleId, lat, lng, distance, deviceSerial, 'in_progress']
        );

        const attendance = checkInResult.rows[0];

        res.status(201).json({ ...attendance, washroom_name: washroom.name });

    } catch (error) {
        console.error('Check-in error:', error);
        res.status(500).json({ error: 'Failed to process check-in' });
    }
};

const checkOut = async (req, res) => {
    const { attendanceId, lat, lng, notes } = req.body;
    const employeeId = req.user.id;

    try {
        const result = await db.query(
            `UPDATE attendance 
             SET check_out = NOW(), lat_out = $1, lng_out = $2, notes = $3, status = 'completed'
             WHERE id = $4 AND employee_id = $5 AND check_out IS NULL 
             RETURNING *`,
            [lat, lng, notes, attendanceId, employeeId]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({ error: 'No active check-in found for this ID' });
        }

        res.json(result.rows[0]);
    } catch (error) {
        console.error('Check-out error:', error);
        res.status(500).json({ error: 'Failed to process check-out' });
    }
};

const getMyStatus = async (req, res) => {
    const employeeId = req.user.id;
    try {
        const result = await db.query(
            `SELECT a.*, w.name as washroom_name 
             FROM attendance a 
             JOIN washrooms w ON a.washroom_id = w.id 
             WHERE a.employee_id = $1 AND a.check_out IS NULL 
             ORDER BY a.check_in DESC LIMIT 1`,
            [employeeId]
        );
        res.json({ checkedIn: result.rows.length > 0, currentAttendance: result.rows[0] });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

module.exports = { checkIn, checkOut, getMyStatus };
