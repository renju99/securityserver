const db = require('../utils/db');
const { calculateDistance, isPointInPolygon } = require('../utils/geoUtils');
const { getIo } = require('../utils/socket');

const checkIn = async (req, res) => {
    const { qrToken, lat, lng, deviceSerial, employeeId } = req.body;
    const targetEmployeeId = employeeId || req.user.id;

    try {
        // 1. Find Washroom and Project
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
        let isWithin = false;
        let distance = 0;

        if (washroom.use_polygon && washroom.geofence_polygon) {
            const polygon = JSON.parse(washroom.geofence_polygon);
            isWithin = isPointInPolygon(lat, lng, polygon);
            distance = calculateDistance(lat, lng, washroom.geofence_lat, washroom.geofence_lng);
        } else {
            distance = calculateDistance(lat, lng, washroom.geofence_lat, washroom.geofence_lng);
            isWithin = distance <= washroom.geofence_radius;
        }

        if (!isWithin) {
            return res.status(403).json({
                error: 'Outside geofence',
                distance,
                limit: washroom.geofence_radius
            });
        }

        // 3. Create Attendance Record
        const result = await db.query(
            `INSERT INTO attendance (employee_id, washroom_id, project_id, check_in, lat_in, lng_in, distance_from_target, device_serial)
       VALUES ($1, $2, $3, NOW(), $4, $5, $6, $7) RETURNING *`,
            [targetEmployeeId, washroom.id, washroom.project_id, lat, lng, distance, deviceSerial]
        );

        const attendance = result.rows[0];

        // 4. Emit real-time update
        getIo().emit('new_attendance', {
            ...attendance,
            employee_name: req.user ? req.user.name : 'Unknown',
            washroom_name: washroom.name
        });

        res.status(201).json(attendance);

    } catch (error) {
        console.error('Check-in error:', error);
        res.status(500).json({ error: error.message });
    }
};

const getMyStatus = async (req, res) => {
    const employeeId = req.user.id;
    const result = await db.query(
        'SELECT * FROM attendance WHERE employee_id = $1 AND check_out IS NULL ORDER BY check_in DESC LIMIT 1',
        [employeeId]
    );
    res.json({ checkedIn: result.rows.length > 0, currentAttendance: result.rows[0] });
};

module.exports = { checkIn, getMyStatus };
