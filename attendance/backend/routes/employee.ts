export { };

const express = require('express');

// Helper: Calculate Distance (Haversine Formula) in meters
const calculateDistance = (lat1: any, lon1: any, lat2: any, lon2: any) => {
    const R = 6371e3; // metres
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180; // φ, λ in radians
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;

    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
        Math.cos(φ1) * Math.cos(φ2) *
        Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    const d = R * c; // in metres
    return d;
};

// Ray-casting algorithm to check if a point is inside a polygon
const isPointInPolygon = (lat: any, lng: any, polygon: any) => {
    let inside = false;
    const x = lng, y = lat;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i].lng, yi = polygon[i].lat;
        const xj = polygon[j].lng, yj = polygon[j].lat;
        const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
};

module.exports = (pool: any, authenticateToken: any, locationLimiter: any, isDuringShift: any, io: any) => {
    const router = express.Router();

    router.get('/attendance/status', authenticateToken, async (req, res) => {
        try {
            const { id } = req.user;
            const attResult = await pool.query(
                'SELECT * FROM attendance WHERE employee_id = $1 ORDER BY check_in_time DESC LIMIT 1',
                [id]
            );

            const empResult = await pool.query('SELECT first_name, last_name, staff_id FROM employees WHERE id = $1', [id]);
            const employee = empResult.rows[0];

            let status = 'checked_out';
            if (attResult.rows.length > 0 && !attResult.rows[0].check_out_time) {
                status = 'checked_in';
            }

            res.json({
                status,
                user: {
                    firstName: employee ? employee.first_name : null,
                    lastName: employee ? employee.last_name : null,
                    staffId: employee ? employee.staff_id : req.user.staffId
                }
            });
        } catch (err) {
            console.error(err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    /**
     * REST API: Foreground Service Location Update (TWA)
     * This endpoint handles background pings from the Android App.
     */
    // Location update
    router.post('/location/update', locationLimiter, authenticateToken, async (req, res) => {
        try {
            const { lat, lng, hw_id, ts } = req.body;
            const employeeId = req.user.staffId; // From JWT

            if (!lat || !lng) {
                return res.status(400).json({ error: 'Missing coordinates' });
            }

            console.log(`[TWA Update] ${employeeId} (${hw_id}): ${lat}, ${lng} at ${ts}`);

            // Get Employee Details including Shift and Site
            const empRes = await pool.query(
                `SELECT e.id, e.site_id, e.department_name, e.photo_url, e.is_tracking_enabled,
                   s.latitude as site_lat, s.longitude as site_lon, s.radius_meters, s.name as site_name, s.geofence_type, s.geofence_data, s.geofence_enabled,
                   sh.start_time, sh.end_time
             FROM employees e
             LEFT JOIN sites s ON e.site_id = s.id
             LEFT JOIN shifts sh ON e.shift_id = sh.id
             WHERE e.staff_id = $1`,
                [employeeId]
            );


            if (empRes.rows.length > 0) {
                const emp = empRes.rows[0];
                const internalId = emp.id;

                // 1. Check Global Tracking
                const globalRes = await pool.query('SELECT value FROM settings WHERE key = $1', ['global_tracking_enabled']);
                const globalEnabled = globalRes.rows.length > 0 ? (globalRes.rows[0].value === true) : true;

                if (!globalEnabled) {
                    return res.json({ message: 'Tracking disabled globally' });
                }

                // 2. Check Staff Level
                if (emp.is_tracking_enabled === false) {
                    return res.json({ message: 'Tracking disabled for this staff' });
                }

                // 3. Check Shift Timings
                if (emp.start_time && emp.end_time) {
                    if (!isDuringShift(emp.start_time, emp.end_time)) {
                        return res.json({ message: 'Outside shift hours' });
                    }
                }


                // 1. Broadcast to HR Dashboards (Socket.io)
                const payload = {
                    employeeId,
                    latitude: lat,
                    longitude: lng,
                    siteId: emp.site_id,
                    departmentName: emp.department_name,
                    photoUrl: emp.photo_url,
                    hw_id,
                    ts
                };
                io.to('hr-dashboard').emit('employee_location', payload);
                if (emp.site_id) {
                    io.to(`hr-site:${emp.site_id}`).emit('employee_location', payload);
                }

                // 2. Save to LiveLogs
                await pool.query(
                    'INSERT INTO live_logs (employee_id, current_coords) VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326))',
                    [internalId, lng, lat]
                );

                // 3. Geofence Check
                const { site_lat: siteLat, site_lon: siteLon, radius_meters: radiusMeters, site_name: siteName,
                    geofence_type: geofenceType, geofence_data: geofenceData, geofence_enabled: geofenceEnabled,
                    start_time: startTime, end_time: endTime, site_id: siteId } = emp;

                if (siteId && geofenceEnabled !== false) {
                    // If shift is assigned, only alert during shift window; otherwise alert anytime
                    let checkGeo = true;
                    if (startTime && endTime) {
                        const now = new Date();
                        const currentTimeVal = now.getHours() * 60 + now.getMinutes();
                        const [startH, startM] = startTime.split(':').map(Number);
                        const [endH, endM] = endTime.split(':').map(Number);
                        const startTimeVal = startH * 60 + startM;
                        const endTimeVal = endH * 60 + endM;
                        if (endTimeVal < startTimeVal) {
                            checkGeo = (currentTimeVal >= startTimeVal) || (currentTimeVal <= endTimeVal);
                        } else {
                            checkGeo = (currentTimeVal >= startTimeVal) && (currentTimeVal <= endTimeVal);
                        }
                    }

                    if (checkGeo) {
                        let isOutside = false;
                        let distance = 0;
                        const allowedRadius = radiusMeters || 100;

                        if (geofenceType === 'POLYGON' && geofenceData && Array.isArray(geofenceData)) {
                            const inside = isPointInPolygon(lat, lng, geofenceData);
                            if (!inside) {
                                isOutside = true;
                                if (siteLat && siteLon) distance = calculateDistance(lat, lng, siteLat, siteLon);
                            }
                        } else if (siteLat && siteLon) {
                            distance = calculateDistance(lat, lng, siteLat, siteLon);
                            if (distance > allowedRadius) isOutside = true;
                        }

                        if (isOutside) {
                            console.log(`[TWA] Geofence Alert: ${employeeId} is outside site ${siteName}`);
                            const recentAlert = await pool.query(
                                "SELECT id FROM geo_fence_alerts WHERE employee_id = $1 AND created_at > NOW() - INTERVAL '10 minutes'",
                                [internalId]
                            );
                            if (recentAlert.rows.length === 0) {
                                const context = startTime ? 'during shift hours' : 'while on duty';
                                const message = geofenceType === 'POLYGON'
                                    ? `${employeeId} outside designated polygon (${siteName}) ${context}.`
                                    : `${employeeId} outside site (${siteName}) ${context}. Distance: ${Math.round(distance)}m`;
                                const alertRes = await pool.query(
                                    `INSERT INTO geo_fence_alerts (employee_id, site_id, latitude, longitude, message) VALUES ($1, $2, $3, $4, $5) RETURNING *`,
                                    [internalId, siteId, lat, lng, message]
                                );
                                const alertData = { ...alertRes.rows[0], staff_id: employeeId, site_name: siteName };
                                io.to('hr-dashboard').emit('geo_fence_alert', alertData);
                                io.to(`hr-site:${siteId}`).emit('geo_fence_alert', alertData);
                            }
                        }
                    }
                }
            }

            res.status(200).json({ status: 'ok' });
        } catch (err) {
            console.error('Error tracking TWA location:', err);
            res.status(500).json({ error: 'Internal server error' });
        }
    });

    return router;
};
