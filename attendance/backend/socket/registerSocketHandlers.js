const calculateDistance = (lat1, lon1, lat2, lon2) => {
    const R = 6371e3;
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
        Math.cos(φ1) * Math.cos(φ2) *
        Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
};

const isPointInPolygon = (lat, lng, polygon) => {
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
const { enqueueAttendanceSync } = require('../services/attendanceSyncQueue');
const {
    getEffectiveAttendancePolicy,
    shouldRequireApproval,
    addApprovalLog,
    applyCheckoutPolicy,
} = require('../services/attendanceGovernance');

const registerSocketHandlers = ({ io, pool, isDuringShift, metrics }) => {
    io.on('connection', (socket) => {
        console.log('a user connected', socket.id);
        const locationMinIntervalMs = parseInt(process.env.LOCATION_UPDATE_MIN_INTERVAL_MS || '10000', 10);
        const locationBatchFlushMs = parseInt(process.env.LOCATION_BATCH_FLUSH_MS || '5000', 10);
        const lastProcessedByEmployee = new Map();
        const pendingLiveLogs = [];
        let flushTimer = null;

        const flushLiveLogs = async () => {
            if (pendingLiveLogs.length === 0) return;
            const rows = pendingLiveLogs.splice(0, pendingLiveLogs.length);
            const valuesSql = rows
                .map((_, idx) => {
                    const base = idx * 3;
                    return `($${base + 1}, ST_SetSRID(ST_MakePoint($${base + 2}, $${base + 3}), 4326))`;
                })
                .join(', ');
            const params = rows.flatMap((r) => [r.employeeId, r.longitude, r.latitude]);
            try {
                await pool.query(`INSERT INTO live_logs (employee_id, current_coords) VALUES ${valuesSql}`, params);
            } catch (err) {
                console.error('[LOCATION] Failed batched live_logs insert:', err.message);
            }
        };

        const queueLiveLog = (row) => {
            pendingLiveLogs.push(row);
            if (!flushTimer) {
                flushTimer = setTimeout(async () => {
                    flushTimer = null;
                    await flushLiveLogs();
                }, locationBatchFlushMs);
            }
        };

        socket.on('join_hr', () => socket.join('hr-dashboard'));
        socket.on('join_site', (siteId) => socket.join(`hr-site:${siteId}`));
        socket.on('disconnect', () => {
            if (flushTimer) {
                clearTimeout(flushTimer);
                flushTimer = null;
            }
            flushLiveLogs().catch((err) => console.error('[LOCATION] Flush on disconnect failed:', err.message));
        });

        socket.on('location_update', async (data) => {
            try {
                const { employeeId, latitude, longitude } = data || {};
                if (!employeeId) return;
                const nowMs = Date.now();
                const lastProcessed = lastProcessedByEmployee.get(employeeId) || 0;
                if (nowMs - lastProcessed < locationMinIntervalMs) return;
                lastProcessedByEmployee.set(employeeId, nowMs);

                const empRes = await pool.query(
                    `SELECT e.id, e.site_id, e.department_name, e.photo_url,
                           s.latitude as site_lat, s.longitude as site_lon, s.radius_meters, s.name as site_name, s.geofence_type, s.geofence_data, s.geofence_enabled,
                           sh.start_time, sh.end_time
                     FROM employees e
                     LEFT JOIN sites s ON e.site_id = s.id
                     LEFT JOIN shifts sh ON e.shift_id = sh.id
                     WHERE e.staff_id = $1`,
                    [employeeId]
                );

                if (empRes.rows.length > 0) {
                    const {
                        id: internalId, site_id: siteId, department_name: departmentName, photo_url: photoUrl,
                        site_lat: siteLat, site_lon: siteLon, radius_meters: radiusMeters, site_name: siteName,
                        geofence_type: geofenceType, geofence_data: geofenceData, geofence_enabled: geofenceEnabled,
                        start_time: startTime, end_time: endTime
                    } = empRes.rows[0];

                    const payload = { ...data, siteId, departmentName, photoUrl };
                    io.to('hr-dashboard').emit('employee_location', payload);
                    if (siteId) io.to(`hr-site:${siteId}`).emit('employee_location', payload);
                    queueLiveLog({ employeeId: internalId, longitude, latitude });

                    if (siteId && geofenceEnabled !== false) {
                        const hasShift = !!(startTime && endTime);
                        const checkGeo = hasShift && isDuringShift(startTime, endTime);
                        if (checkGeo) {
                            let isOutside = false;
                            let distance = 0;
                            const allowedRadius = radiusMeters || 100;
                            if (geofenceType === 'POLYGON' && geofenceData && Array.isArray(geofenceData)) {
                                const inside = isPointInPolygon(latitude, longitude, geofenceData);
                                if (!inside) {
                                    isOutside = true;
                                    if (siteLat && siteLon) distance = calculateDistance(latitude, longitude, siteLat, siteLon);
                                }
                            } else if (siteLat && siteLon) {
                                distance = calculateDistance(latitude, longitude, siteLat, siteLon);
                                if (distance > allowedRadius) isOutside = true;
                            }

                            if (isOutside) {
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
                                        `INSERT INTO geo_fence_alerts (employee_id, site_id, latitude, longitude, message) 
                                         VALUES ($1, $2, $3, $4, $5) RETURNING *`,
                                        [internalId, siteId, latitude, longitude, message]
                                    );
                                    const alertData = { ...alertRes.rows[0], staff_id: employeeId, site_name: siteName };
                                    io.to('hr-dashboard').emit('geo_fence_alert', alertData);
                                    if (siteId) io.to(`hr-site:${siteId}`).emit('geo_fence_alert', alertData);
                                }
                            }
                        }
                    }
                } else {
                    io.to('hr-dashboard').emit('employee_location', data);
                }
            } catch (err) {
                console.error('Error handling location update for', data?.employeeId, ':', err.message);
            }
        });

        socket.on('check_in', async (data) => {
            let { employeeId, latitude, longitude } = data || {};
            const emitCheckInError = (message) => {
                metrics.increment('failed_checkins_total', 1);
                socket.emit('error', { message });
            };
            if (!employeeId) {
                metrics.increment('failed_checkins_total', 1);
                return;
            }
            try {
                const empRes = await pool.query(`
                    SELECT e.id, e.first_name, e.last_name, e.site_id, s.name as site_name, s.nfc_payload as site_nfc_payload 
                    FROM employees e LEFT JOIN sites s ON e.site_id = s.id WHERE e.staff_id = $1
                `, [employeeId]);
                if (empRes.rows.length > 0) {
                    const { id: internalId, first_name: firstName, last_name: lastName, site_id: siteId, site_name: siteName, site_nfc_payload: siteNfcPayload } = empRes.rows[0];
                    if (siteNfcPayload && siteNfcPayload.trim().length > 0 && (!data.nfcPayload || data.nfcPayload !== siteNfcPayload)) {
                        emitCheckInError('NFC Scan Required. Please tap the correct NFC tag to Check In.');
                        return;
                    }
                    if (!latitude || !longitude) {
                        const locRes = await pool.query(
                            'SELECT ST_X(current_coords::geometry) as lon, ST_Y(current_coords::geometry) as lat FROM live_logs WHERE employee_id = $1 ORDER BY timestamp DESC LIMIT 1',
                            [internalId]
                        );
                        if (locRes.rows.length > 0) {
                            latitude = locRes.rows[0].lat;
                            longitude = locRes.rows[0].lon;
                        } else {
                            emitCheckInError('Location data unavailable. Please enable GPS.');
                            return;
                        }
                    }
                    const checkRes = await pool.query('SELECT id FROM attendance WHERE employee_id = $1 AND check_out_time IS NULL', [internalId]);
                    if (checkRes.rows.length > 0) {
                        emitCheckInError('Already checked in');
                        return;
                    }
                    const policy = await getEffectiveAttendancePolicy(pool, { siteId, shiftId: null });
                    const requireApproval = shouldRequireApproval(policy, 'socket');
                    const inserted = await pool.query(
                        `INSERT INTO attendance (employee_id, check_in_time, check_in_coords, site_id, source, status)
                         VALUES ($1, CURRENT_TIMESTAMP, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4, 'socket', $5)
                         RETURNING id, check_in_time, status`,
                        [internalId, longitude, latitude, siteId, requireApproval ? 'pending' : 'approved']
                    );
                    if (inserted.rows[0].status === 'pending') {
                        await addApprovalLog(pool, {
                            attendanceId: inserted.rows[0].id,
                            action: 'submitted',
                            actorId: internalId,
                            metadata: { source: 'socket' },
                        });
                    }
                    socket.emit('check_in_success');
                    const eventData = { type: 'check_in', employeeId, firstName, lastName, siteId, siteName, timestamp: new Date() };
                    io.to('hr-dashboard').emit('attendance_event', eventData);
                    if (siteId) io.to(`hr-site:${siteId}`).emit('attendance_event', eventData);
                    if (inserted?.rows?.[0]?.id) {
                        await enqueueAttendanceSync(pool, {
                            attendanceId: inserted.rows[0].id,
                            staffId: employeeId,
                            eventType: 'check_in',
                            siteId,
                            checkInTime: inserted.rows[0].check_in_time,
                            source: 'socket',
                        });
                    }
                }
            } catch (err) {
                console.error('Error on check-in:', err);
                metrics.increment('failed_checkins_total', 1);
            }
        });

        socket.on('check_out', async (data) => {
            let { employeeId, latitude, longitude } = data || {};
            if (!employeeId) return;
            try {
                const empRes = await pool.query(`
                    SELECT e.id, e.first_name, e.last_name, e.site_id, s.name as site_name, s.nfc_payload as site_nfc_payload
                    FROM employees e LEFT JOIN sites s ON e.site_id = s.id WHERE e.staff_id = $1
                `, [employeeId]);
                if (empRes.rows.length > 0) {
                    const { id: internalId, first_name: firstName, last_name: lastName, site_id: siteId, site_name: siteName, site_nfc_payload: siteNfcPayload } = empRes.rows[0];
                    if (siteNfcPayload && siteNfcPayload.trim().length > 0 && (!data.nfcPayload || data.nfcPayload !== siteNfcPayload)) {
                        socket.emit('error', { message: 'NFC Scan Required. Please tap the correct NFC tag to Check Out.' });
                        return;
                    }
                    if (!latitude || !longitude) {
                        const locRes = await pool.query(
                            'SELECT ST_X(current_coords::geometry) as lon, ST_Y(current_coords::geometry) as lat FROM live_logs WHERE employee_id = $1 ORDER BY timestamp DESC LIMIT 1',
                            [internalId]
                        );
                        if (locRes.rows.length > 0) {
                            latitude = locRes.rows[0].lat;
                            longitude = locRes.rows[0].lon;
                        } else {
                            socket.emit('error', { message: 'Location data unavailable. Please enable GPS.' });
                            return;
                        }
                    }
                    const checkRes = await pool.query(
                        'UPDATE attendance SET check_out_time = CURRENT_TIMESTAMP, check_out_coords = ST_SetSRID(ST_MakePoint($1, $2), 4326) WHERE employee_id = $3 AND check_out_time IS NULL RETURNING id',
                        [longitude, latitude, internalId]
                    );
                    if (checkRes.rows.length > 0) {
                        const attendanceRes = await pool.query(
                            `SELECT id, check_in_time, check_out_time, status
                             FROM attendance
                             WHERE id = $1`,
                            [checkRes.rows[0].id]
                        );
                        const attendanceRow = attendanceRes.rows[0];
                        await applyCheckoutPolicy(pool, {
                            attendanceId: attendanceRow.id,
                            checkInTime: attendanceRow.check_in_time,
                            checkOutTime: attendanceRow.check_out_time,
                            siteId,
                            shiftId: null,
                        });
                        socket.emit('check_out_success');
                        const eventData = { type: 'check_out', employeeId, firstName, lastName, siteId, siteName, timestamp: new Date() };
                        io.to('hr-dashboard').emit('attendance_event', eventData);
                        if (siteId) io.to(`hr-site:${siteId}`).emit('attendance_event', eventData);
                        await enqueueAttendanceSync(pool, {
                            attendanceId: checkRes.rows[0].id,
                            staffId: employeeId,
                            eventType: 'check_out',
                            siteId,
                            source: 'socket',
                        });
                    } else {
                        socket.emit('error', { message: 'Not checked in' });
                    }
                }
            } catch (err) {
                console.error('Error on check-out:', err);
            }
        });
    });
};

module.exports = {
    registerSocketHandlers,
};
