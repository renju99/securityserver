export { };

const express = require('express');
const { enqueueAttendanceSync } = require('../services/attendanceSyncQueue');
const {
    getEffectiveAttendancePolicy,
    shouldRequireApproval,
    addApprovalLog,
    applyCheckoutPolicy,
} = require('../services/attendanceGovernance');
const { organizationIdFromUser, hrDashboardRoom, hrSiteRoom } = require('../utils/organization');

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
            const openRes = await pool.query(
                `SELECT a.id, a.check_in_time, a.source, a.status, s.name AS site_name
                 FROM attendance a
                 LEFT JOIN sites s ON s.id = a.site_id
                 WHERE a.employee_id = $1 AND a.check_out_time IS NULL
                   AND a.status NOT IN ('voided', 'rejected')
                 ORDER BY a.check_in_time DESC LIMIT 1`,
                [id]
            );

            const empResult = await pool.query(
                `SELECT e.first_name, e.last_name, e.staff_id, s.name AS assigned_site_name
                 FROM employees e
                 LEFT JOIN sites s ON s.id = e.site_id
                 WHERE e.id = $1`,
                [id]
            );
            const employee = empResult.rows[0];

            const status = openRes.rows.length > 0 ? 'checked_in' : 'checked_out';
            const open = openRes.rows[0] || null;

            res.json({
                status,
                openAttendanceId: open?.id ?? null,
                openCheckInTime: open?.check_in_time ?? null,
                openSource: open?.source ?? null,
                siteName: open?.site_name || employee?.assigned_site_name || null,
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

    router.post('/attendance/offline-sync', authenticateToken, async (req, res) => {
        const entries = Array.isArray(req.body?.entries) ? req.body.entries : [];
        if (!entries.length) {
            return res.status(400).json({ error: 'entries[] is required' });
        }
        try {
            const empRes = await pool.query(
                `SELECT e.id, e.staff_id, e.site_id, e.shift_id, s.nfc_payload
                 FROM employees e
                 LEFT JOIN sites s ON s.id = e.site_id
                 WHERE e.id = $1`,
                [req.user.id]
            );
            if (empRes.rows.length === 0) {
                return res.status(404).json({ error: 'Employee not found' });
            }
            const employee = empRes.rows[0];
            const capped = entries.slice(0, 200);
            const results = new Array(capped.length);
            const sorted = capped
                .map((entry, originalIndex) => ({ entry, originalIndex }))
                .sort((a, b) => {
                    const ta = new Date(a.entry?.timestamp || 0).getTime();
                    const tb = new Date(b.entry?.timestamp || 0).getTime();
                    return ta - tb || a.originalIndex - b.originalIndex;
                });

            for (const { entry, originalIndex } of sorted) {
                const action = entry?.action === 'check_out' ? 'check_out' : 'check_in';
                const ts = entry?.timestamp ? new Date(entry.timestamp) : new Date();
                let latitude = Number(entry?.latitude);
                let longitude = Number(entry?.longitude);
                if ((!Number.isFinite(latitude) || !Number.isFinite(longitude)) && Number.isFinite(employee.id)) {
                    const locRes = await pool.query(
                        `SELECT ST_X(current_coords::geometry) AS lon, ST_Y(current_coords::geometry) AS lat
                         FROM live_logs WHERE employee_id = $1 ORDER BY timestamp DESC LIMIT 1`,
                        [employee.id]
                    );
                    if (locRes.rows.length > 0) {
                        latitude = Number(locRes.rows[0].lat);
                        longitude = Number(locRes.rows[0].lon);
                    }
                }
                if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || !Number.isFinite(ts.getTime())) {
                    results[originalIndex] = { ok: false, action, error: 'Invalid timestamp or coordinates' };
                    // eslint-disable-next-line no-continue
                    continue;
                }
                if (employee.nfc_payload && String(employee.nfc_payload).trim() && entry?.nfcPayload !== employee.nfc_payload) {
                    results[originalIndex] = { ok: false, action, error: 'NFC payload mismatch' };
                    // eslint-disable-next-line no-continue
                    continue;
                }
                if (action === 'check_in') {
                    // eslint-disable-next-line no-await-in-loop
                    const openRes = await pool.query(
                        `SELECT id FROM attendance
                         WHERE employee_id = $1 AND check_out_time IS NULL
                           AND status NOT IN ('voided', 'rejected')`,
                        [employee.id]
                    );
                    if (openRes.rowCount > 0) {
                        results[originalIndex] = {
                            ok: false,
                            action,
                            error: 'Already checked in',
                            conflict: 'duplicate_open_check_in',
                        };
                        // eslint-disable-next-line no-continue
                        continue;
                    }
                    // eslint-disable-next-line no-await-in-loop
                    const policy = await getEffectiveAttendancePolicy(pool, { siteId: employee.site_id, shiftId: employee.shift_id || null });
                    const requireApproval = shouldRequireApproval(policy, 'offline_batch');
                    // eslint-disable-next-line no-await-in-loop
                    const inserted = await pool.query(
                        `INSERT INTO attendance (employee_id, check_in_time, check_in_coords, site_id, source, status, work_context)
                         VALUES ($1, $2, ST_SetSRID(ST_MakePoint($3, $4), 4326), $5, 'offline_batch', $6, $7::jsonb)
                         RETURNING id, check_in_time, status`,
                        [
                            employee.id,
                            ts.toISOString(),
                            longitude,
                            latitude,
                            employee.site_id,
                            requireApproval ? 'pending' : 'approved',
                            JSON.stringify(entry?.workContext || {}),
                        ]
                    );
                    if (inserted.rows[0].status === 'pending') {
                        // eslint-disable-next-line no-await-in-loop
                        await addApprovalLog(pool, {
                            attendanceId: inserted.rows[0].id,
                            action: 'submitted',
                            actorId: employee.id,
                            metadata: { source: 'offline_batch' },
                        });
                    }
                    // eslint-disable-next-line no-await-in-loop
                    await enqueueAttendanceSync(pool, {
                        attendanceId: inserted.rows[0].id,
                        staffId: employee.staff_id,
                        eventType: 'check_in',
                        siteId: employee.site_id,
                        checkInTime: inserted.rows[0].check_in_time,
                        source: 'offline_batch',
                    });
                    results[originalIndex] = { ok: true, action, attendanceId: inserted.rows[0].id, status: inserted.rows[0].status };
                } else {
                    // eslint-disable-next-line no-await-in-loop
                    const updated = await pool.query(
                        `UPDATE attendance
                         SET check_out_time = $1,
                             check_out_coords = ST_SetSRID(ST_MakePoint($2, $3), 4326),
                             source = COALESCE(source, 'offline_batch'),
                             work_context = COALESCE(work_context, '{}'::jsonb) || $4::jsonb
                         WHERE employee_id = $5 AND check_out_time IS NULL
                           AND status NOT IN ('voided', 'rejected')
                         RETURNING id, check_in_time, check_out_time, status`,
                        [ts.toISOString(), longitude, latitude, JSON.stringify(entry?.workContext || {}), employee.id]
                    );
                    if (updated.rowCount === 0) {
                        results[originalIndex] = {
                            ok: false,
                            action,
                            error: 'No open check-in found',
                            conflict: 'checkout_without_open',
                        };
                        // eslint-disable-next-line no-continue
                        continue;
                    }
                    // eslint-disable-next-line no-await-in-loop
                    await applyCheckoutPolicy(pool, {
                        attendanceId: updated.rows[0].id,
                        checkInTime: updated.rows[0].check_in_time,
                        checkOutTime: updated.rows[0].check_out_time,
                        siteId: employee.site_id,
                        shiftId: employee.shift_id || null,
                    });
                    // eslint-disable-next-line no-await-in-loop
                    await enqueueAttendanceSync(pool, {
                        attendanceId: updated.rows[0].id,
                        staffId: employee.staff_id,
                        eventType: 'check_out',
                        siteId: employee.site_id,
                        checkOutTime: updated.rows[0].check_out_time,
                        source: 'offline_batch',
                    });
                    results[originalIndex] = { ok: true, action, attendanceId: updated.rows[0].id, status: updated.rows[0].status };
                }
            }
            return res.json({ success: true, processed: capped.length, results });
        } catch (err) {
            console.error('Offline attendance sync error:', err);
            return res.status(500).json({ error: 'Offline attendance sync failed' });
        }
    });

    router.get('/shifts/assignments', authenticateToken, async (req, res) => {
        const startDate = req.query.startDate;
        const endDate = req.query.endDate;
        const params = [req.user.id];
        const where = ['a.employee_id = $1'];
        if (startDate) {
            params.push(startDate);
            where.push(`a.work_date >= $${params.length}::date`);
        }
        if (endDate) {
            params.push(endDate);
            where.push(`a.work_date <= $${params.length}::date`);
        }
        try {
            const result = await pool.query(
                `SELECT a.id, a.work_date, a.shift_id, a.site_id, a.acceptance_status, a.accepted_at, a.rejected_at, a.rejection_reason,
                        sh.name AS shift_name, sh.start_time, sh.end_time, s.name AS site_name
                 FROM roster_assignments a
                 LEFT JOIN shifts sh ON sh.id = a.shift_id
                 LEFT JOIN sites s ON s.id = a.site_id
                 WHERE ${where.join(' AND ')}
                 ORDER BY a.work_date ASC
                 LIMIT 200`,
                params
            );
            return res.json(result.rows);
        } catch (err) {
            if (err?.code === '42P01') return res.json([]);
            console.error('Employee shift assignments error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/shifts/assignments/:id/respond', authenticateToken, async (req, res) => {
        const assignmentId = Number(req.params.id);
        const decision = req.body?.decision === 'reject' ? 'reject' : 'accept';
        const reason = req.body?.reason ? String(req.body.reason).trim().slice(0, 500) : null;
        if (!Number.isFinite(assignmentId)) {
            return res.status(400).json({ error: 'Invalid assignment id' });
        }
        try {
            const result = await pool.query(
                `UPDATE roster_assignments
                 SET acceptance_status = $3,
                     accepted_at = CASE WHEN $3 = 'accepted' THEN NOW() ELSE accepted_at END,
                     accepted_by = CASE WHEN $3 = 'accepted' THEN $1 ELSE accepted_by END,
                     rejected_at = CASE WHEN $3 = 'rejected' THEN NOW() ELSE rejected_at END,
                     rejection_reason = CASE WHEN $3 = 'rejected' THEN $4 ELSE rejection_reason END
                 WHERE id = $2 AND employee_id = $1
                 RETURNING *`,
                [req.user.id, assignmentId, decision === 'accept' ? 'accepted' : 'rejected', reason]
            );
            if (result.rowCount === 0) {
                return res.status(404).json({ error: 'Shift assignment not found' });
            }
            return res.json({ success: true, record: result.rows[0] });
        } catch (err) {
            console.error('Shift assignment response error:', err);
            return res.status(500).json({ error: 'Database error' });
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
            const orgId = organizationIdFromUser(req.user);
            const empRes = await pool.query(
                `SELECT e.id, e.site_id, e.department_name, e.photo_url, e.is_tracking_enabled,
                   s.latitude as site_lat, s.longitude as site_lon, s.radius_meters, s.name as site_name, s.geofence_type, s.geofence_data, s.geofence_enabled,
                   sh.start_time, sh.end_time
             FROM employees e
             LEFT JOIN sites s ON e.site_id = s.id
             LEFT JOIN shifts sh ON e.shift_id = sh.id
             WHERE e.staff_id = $1 AND e.organization_id = $2`,
                [employeeId, orgId]
            );


            if (empRes.rows.length > 0) {
                const emp = empRes.rows[0];
                const internalId = emp.id;

                // 1. Check Global Tracking
                const globalRes = await pool.query(
                    'SELECT value FROM settings WHERE key = $1 AND organization_id = $2',
                    ['global_tracking_enabled', orgId]
                );
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
                io.to(hrDashboardRoom(orgId)).emit('employee_location', payload);
                if (emp.site_id) {
                    const siteRoom = hrSiteRoom(orgId, emp.site_id);
                    if (siteRoom) io.to(siteRoom).emit('employee_location', payload);
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
                                io.to(hrDashboardRoom(orgId)).emit('geo_fence_alert', alertData);
                                const siteRoom = hrSiteRoom(orgId, siteId);
                                if (siteRoom) io.to(siteRoom).emit('geo_fence_alert', alertData);
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
