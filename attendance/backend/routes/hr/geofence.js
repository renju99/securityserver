const { organizationIdFromUser } = require('../../utils/organization');

module.exports = ({ router, pool, authenticateToken, authorizeRole, normalizeFilterDateToUtcIso }) => {
    router.get('/hr/location-logs', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { staffId, startDate, endDate, page = 1, limit = 100 } = req.query;
        const offset = (parseInt(page) - 1) * parseInt(limit);
        const orgId = organizationIdFromUser(req.user);
        const params = [orgId];
        const conditions = ['e.organization_id = $1'];
        let idx = 2;

        if (req.user.role === 'Site Supervisor') {
            conditions.push(`e.site_id = $${idx++}`);
            params.push(req.user.siteId);
        }

        if (staffId) {
            conditions.push(`(
                e.staff_id ILIKE $${idx}
                OR COALESCE(e.first_name, '') ILIKE $${idx}
                OR COALESCE(e.last_name, '') ILIKE $${idx}
                OR CONCAT_WS(' ', COALESCE(e.first_name, ''), COALESCE(e.last_name, '')) ILIKE $${idx}
            )`);
            params.push(`%${String(staffId).trim()}%`);
            idx++;
        }
        const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
        const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);

        if (normalizedStartDate) {
            conditions.push(`ll.timestamp >= $${idx++}`);
            params.push(normalizedStartDate);
        }
        if (normalizedEndDate) {
            conditions.push(`ll.timestamp <= $${idx++}`);
            params.push(normalizedEndDate);
        }

        const where = 'WHERE ' + conditions.join(' AND ');

        try {
            const countRes = await pool.query(
                `SELECT COUNT(*) FROM live_logs ll JOIN employees e ON ll.employee_id = e.id ${where}`,
                params
            );
            const total = parseInt(countRes.rows[0].count);

            const result = await pool.query(
                `SELECT ll.id,
                    e.staff_id, e.first_name, e.last_name,
                    ST_Y(ll.current_coords::geometry) as latitude,
                    ST_X(ll.current_coords::geometry) as longitude,
                    ll.timestamp
             FROM live_logs ll
             JOIN employees e ON ll.employee_id = e.id
             ${where}
             ORDER BY ll.timestamp DESC
             LIMIT $${idx++} OFFSET $${idx++}`,
                [...params, parseInt(limit), offset]
            );

            res.json({
                logs: result.rows,
                total,
                page: parseInt(page),
                totalPages: Math.ceil(total / parseInt(limit))
            });
        } catch (err) {
            console.error('Error fetching location logs:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Delete a single location log entry
    router.delete('/hr/location-logs/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { id } = req.params;
        const orgId = organizationIdFromUser(req.user);
        try {
            const result = await pool.query(
                `DELETE FROM live_logs ll
                 USING employees e
                 WHERE ll.id = $1 AND ll.employee_id = e.id AND e.organization_id = $2
                 RETURNING ll.id`,
                [id, orgId]
            );
            if (result.rows.length === 0) return res.status(404).json({ error: 'Log not found' });
            res.json({ message: 'Log deleted' });
        } catch (err) {
            console.error('Error deleting location log:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Bulk delete location logs (by employee and/or date range)
    router.delete('/hr/location-logs', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { staffId, startDate, endDate, ids } = req.body;

        try {
            // Delete by explicit ID list
            const orgId = organizationIdFromUser(req.user);
            if (ids && Array.isArray(ids) && ids.length > 0) {
                await pool.query(
                    `DELETE FROM live_logs ll
                     USING employees e
                     WHERE ll.id = ANY($1) AND ll.employee_id = e.id AND e.organization_id = $2`,
                    [ids, orgId]
                );
                return res.json({ message: `${ids.length} log(s) deleted` });
            }

            const conditions = [];
            const params = [];
            let idx = 1;

            if (staffId) {
                const empRes = await pool.query(
                    `SELECT id
                     FROM employees
                     WHERE organization_id = $2 AND (
                        staff_id ILIKE $1
                        OR COALESCE(first_name, '') ILIKE $1
                        OR COALESCE(last_name, '') ILIKE $1
                        OR CONCAT_WS(' ', COALESCE(first_name, ''), COALESCE(last_name, '')) ILIKE $1
                     )`,
                    [`%${String(staffId).trim()}%`, orgId]
                );
                const empIds = empRes.rows.map(r => r.id);
                if (empIds.length === 0) return res.json({ message: '0 logs deleted' });
                conditions.push(`employee_id = ANY($${idx++})`);
                params.push(empIds);
            }
            const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
            const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);

            if (normalizedStartDate) { conditions.push(`timestamp >= $${idx++}`); params.push(normalizedStartDate); }
            if (normalizedEndDate) { conditions.push(`timestamp <= $${idx++}`); params.push(normalizedEndDate); }

            if (conditions.length === 0) return res.status(400).json({ error: 'Provide at least one filter for bulk delete' });

            const result = await pool.query(
                `DELETE FROM live_logs WHERE ${conditions.join(' AND ')}`,
                params
            );
            res.json({ message: `${result.rowCount} log(s) deleted` });
        } catch (err) {
            console.error('Error bulk-deleting location logs:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Get Route Tracking Data
    router.get('/hr/route-tracking', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { staffId, startDate, endDate } = req.query;

        if (!staffId || !startDate || !endDate) {
            return res.status(400).json({ error: 'staffId, startDate, and endDate are required' });
        }

        try {
            const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
            const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);

            const orgId = organizationIdFromUser(req.user);
            const empQuery = `
            SELECT e.id, e.staff_id, e.first_name, e.last_name, e.site_id, s.name as site_name
            FROM employees e
            LEFT JOIN sites s ON e.site_id = s.id
            WHERE e.staff_id = $1 AND e.organization_id = $2
        `;
            const empResult = await pool.query(empQuery, [staffId, orgId]);

            if (empResult.rows.length === 0) {
                return res.status(404).json({ error: 'Employee not found' });
            }

            const employee = empResult.rows[0];

            if (req.user.role === 'Site Supervisor' && employee.site_id !== req.user.siteId) {
                return res.status(403).json({ error: 'Access denied to this employee' });
            }

            const locationQuery = `
            SELECT 
                ST_Y(current_coords::geometry) as latitude,
                ST_X(current_coords::geometry) as longitude,
                timestamp
            FROM live_logs
            WHERE employee_id = $1
                AND timestamp >= $2
                AND timestamp <= $3
            ORDER BY timestamp ASC
        `;

            const locationResult = await pool.query(locationQuery, [
                employee.id,
                normalizedStartDate || startDate,
                normalizedEndDate || endDate
            ]);

            let locations = locationResult.rows;
            const totalPoints = locations.length;

            // Backend Sampling to prevent Network Error / Timeout
            // If more than 3000 points, take every Nth point
            if (totalPoints > 3000) {
                const samplingFactor = Math.ceil(totalPoints / 3000);
                locations = locations.filter((_, index) => index % samplingFactor === 0 || index === totalPoints - 1);
            }

            res.json({
                employee: {
                    staffId: employee.staff_id,
                    firstName: employee.first_name,
                    lastName: employee.last_name,
                    siteName: employee.site_name
                },
                locations: locations,
                totalPoints: totalPoints,
                sampled: totalPoints > 3000
            });
        } catch (err) {
            console.error('Route tracking error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/idle-report', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { staffId, startDate, endDate, thresholdMins } = req.query;
        const threshold = parseInt(thresholdMins) || 30;

        if (!staffId || !startDate || !endDate) {
            return res.status(400).json({ error: 'staffId, startDate, and endDate are required' });
        }

        try {
            const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
            const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);

            const orgId = organizationIdFromUser(req.user);
            const empQuery = 'SELECT id, staff_id, first_name, last_name FROM employees WHERE staff_id = $1 AND organization_id = $2';
            const empResult = await pool.query(empQuery, [staffId, orgId]);
            if (empResult.rows.length === 0) return res.status(404).json({ error: 'Employee not found' });
            const employee = empResult.rows[0];

            const locationQuery = `
            SELECT ST_Y(current_coords::geometry) as lat, ST_X(current_coords::geometry) as lng, timestamp
            FROM live_logs WHERE employee_id = $1 AND timestamp >= $2 AND timestamp <= $3 ORDER BY timestamp ASC
        `;
            const locationResult = await pool.query(locationQuery, [
                employee.id,
                normalizedStartDate || startDate,
                normalizedEndDate || endDate
            ]);
            const rows = locationResult.rows;

            // Server-side Idle Detection Logic
            const idleSpots = [];
            if (rows.length >= 2) {
                let currentGroup = [rows[0]];
                const thresholdMs = threshold * 60 * 1000;

                const getDist = (p1, p2) => {
                    const R = 6371e3;
                    const f1 = p1.lat * Math.PI / 180;
                    const f2 = p2.lat * Math.PI / 180;
                    const df = (p2.lat - p1.lat) * Math.PI / 180;
                    const dl = (p2.lng - p1.lng) * Math.PI / 180;
                    const a = Math.sin(df / 2) * Math.sin(df / 2) + Math.cos(f1) * Math.cos(f2) * Math.sin(dl / 2) * Math.sin(dl / 2);
                    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
                };

                for (let i = 1; i < rows.length; i++) {
                    const dist = getDist(currentGroup[0], rows[i]);
                    if (dist < 30) {
                        currentGroup.push(rows[i]);
                    } else {
                        const duration = new Date(currentGroup[currentGroup.length - 1].timestamp) - new Date(currentGroup[0].timestamp);
                        if (duration >= thresholdMs) {
                            idleSpots.push({
                                lat: currentGroup[0].lat, lng: currentGroup[0].lng,
                                duration: Math.round(duration / 60000),
                                startTime: currentGroup[0].timestamp, endTime: currentGroup[currentGroup.length - 1].timestamp
                            });
                        }
                        currentGroup = [rows[i]];
                    }
                }
                const duration = new Date(currentGroup[currentGroup.length - 1].timestamp) - new Date(currentGroup[0].timestamp);
                if (duration >= thresholdMs) {
                    idleSpots.push({
                        lat: currentGroup[0].lat, lng: currentGroup[0].lng,
                        duration: Math.round(duration / 60000),
                        startTime: currentGroup[0].timestamp, endTime: currentGroup[currentGroup.length - 1].timestamp
                    });
                }
            }

            res.json({ employee: { firstName: employee.first_name, lastName: employee.last_name, staffId: employee.staff_id }, idleSpots });
        } catch (err) {
            console.error('Idle report error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });
};
