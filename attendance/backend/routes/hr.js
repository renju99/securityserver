const express = require('express');
const fs = require('fs');
const path = require('path');
const { APP_TIMEZONE, normalizeFilterDateToUtcIso } = require('../utils/time');

const uploadsDir = path.join(__dirname, '..', 'uploads');

if (!fs.existsSync(uploadsDir)) {
    fs.mkdirSync(uploadsDir, { recursive: true });
}

const saveBase64Image = (base64String, staffId) => {
    try {
        if (!base64String || !base64String.startsWith('data:image')) return null;

        const matches = base64String.match(/^data:image\/([A-Za-z-+/]+);base64,(.+)$/);
        if (!matches || matches.length !== 3) return null;

        const type = matches[1];
        const data = matches[2];
        const buffer = Buffer.from(data, 'base64');
        const safeStaffId = String(staffId || 'user').replace(/[^a-zA-Z0-9_-]/g, '');
        const fileName = `${safeStaffId}_${Date.now()}.${type}`;
        const filePath = path.join(uploadsDir, fileName);

        fs.writeFileSync(filePath, buffer);
        return `/api/uploads/${fileName}`;
    } catch (err) {
        console.error('Error saving image:', err);
        return null;
    }
};

module.exports = (pool, authenticateToken, authorizeRole, bcrypt, jwt, JWT_SECRET, getGeofenceAlerts, broadcastGeofenceAlert, io) => {
    const router = express.Router();

    // Helper to extract JWT if some functions need it

    // HR API: Get global settings
    router.get('/hr/settings', authenticateToken, async (req, res) => {
        try {
            const result = await pool.query('SELECT key, value FROM settings');
            const settings = {};
            result.rows.forEach(r => { settings[r.key] = r.value; });
            res.json(settings);
        } catch (err) {
            console.error('Error fetching settings:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Update global settings
    router.post('/hr/settings', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { key, value } = req.body;
        if (!key) return res.status(400).json({ error: 'Missing key' });
        try {
            await pool.query(
                'INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value',
                [key, JSON.stringify(value)]
            );
            res.json({ message: 'Setting updated' });
        } catch (err) {
            console.error('Error updating setting:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Get all employees
    router.get('/hr/employees', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        try {
            let query = `
            SELECT e.*, r.name as role_name, s.name as site_name, sh.name as shift_name, sh.start_time, sh.end_time 
            FROM employees e
            LEFT JOIN roles r ON e.role_id = r.id 
            LEFT JOIN sites s ON e.site_id = s.id
            LEFT JOIN shifts sh ON e.shift_id = sh.id
        `;
            const params = [];

            if (req.user.role === 'Site Supervisor') {
                query += ' WHERE e.site_id = $1';
                params.push(req.user.siteId);
            }

            query += ' ORDER BY e.staff_id ASC';
            const result = await pool.query(query, params);
            res.json(result.rows);
        } catch (err) {
            console.error(err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // ... (other routes unchanged)

    // HR API: Create/Update user
    router.post('/hr/users', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        if (!req.body) { return res.status(400).json({ error: 'Missing request body' }); }
        const { staffId, email, password, roleId, siteId, departmentName, firstName, lastName, photoHelper } = req.body;
        // photoHelper is the base64 string from frontend if updated

        try {
            let passwordHash = null;
            if (password) {
                passwordHash = await bcrypt.hash(password, 10);
            }

            let photoUrl = null;
            if (photoHelper) {
                photoUrl = saveBase64Image(photoHelper, staffId);
            }

            const query = `
            INSERT INTO employees (staff_id, email, password_hash, role_id, site_id, department_name, first_name, last_name, photo_url, shift_id, is_tracking_enabled)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (staff_id) DO UPDATE SET
            email = EXCLUDED.email,
            password_hash = COALESCE(EXCLUDED.password_hash, employees.password_hash),
            role_id = EXCLUDED.role_id,
            site_id = EXCLUDED.site_id,
            department_name = EXCLUDED.department_name,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            photo_url = COALESCE($9, employees.photo_url),
            shift_id = EXCLUDED.shift_id,
            is_tracking_enabled = COALESCE(EXCLUDED.is_tracking_enabled, employees.is_tracking_enabled)
            RETURNING *
        `;

            const sanitizedRoleId = roleId || null;
            const sanitizedSiteId = siteId || null;
            const sanitizedDept = departmentName || null;
            const sanitizedShiftId = req.body.shiftId || null;
            const sanitizedTracking = req.body.isTrackingEnabled !== undefined ? req.body.isTrackingEnabled : true;

            const result = await pool.query(query, [
                staffId,
                email,
                passwordHash,
                sanitizedRoleId,
                sanitizedSiteId,
                sanitizedDept,
                firstName || null,
                lastName || null,
                photoUrl,
                sanitizedShiftId,
                sanitizedTracking
            ]);

            res.json(result.rows[0]);
        } catch (err) {
            console.error('Error adding user:', err);
            if (err.code === '23505') {
                if (err.constraint === 'employees_email_key') {
                    return res.status(400).json({ error: 'Email already in use' });
                }
                if (err.constraint === 'employees_staff_id_key') {
                    return res.status(400).json({ error: 'Staff ID already exists' });
                }
            }
            res.status(500).json({ error: 'Database error' });
        }
    });


    // HR API: Get recent attendance (Filtered by site for Supervisors)
    router.get('/hr/attendance', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        try {
            let query = `
            SELECT a.*, e.staff_id, e.email, e.first_name, e.last_name, s.name as site_name 
            FROM attendance a 
            JOIN employees e ON a.employee_id = e.id 
            LEFT JOIN sites s ON a.site_id = s.id
        `;
            const params = [];

            if (req.user.role === 'Site Supervisor') {
                query += ' WHERE e.site_id = $1';
                params.push(req.user.siteId);
            }

            query += ' ORDER BY a.check_in_time DESC LIMIT 100';
            const result = await pool.query(query, params);
            res.json(result.rows);
        } catch (err) {
            console.error(err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Manual Check-In (supervisor logs check-in for an employee)
    router.post('/hr/attendance/manual-checkin', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { staffId, checkInTime, siteId, notes } = req.body;
        if (!staffId || !checkInTime) {
            return res.status(400).json({ error: 'staffId and checkInTime are required.' });
        }
        try {
            // Resolve employee
            const empResult = await pool.query(
                `SELECT e.id, e.first_name, e.last_name, e.site_id
             FROM employees e WHERE e.staff_id = $1`, [staffId]
            );
            if (empResult.rows.length === 0) return res.status(404).json({ error: 'Employee not found.' });
            const emp = empResult.rows[0];

            // Supervisors can only act on their own site's employees
            if (req.user.role === 'Site Supervisor' && emp.site_id !== req.user.siteId) {
                return res.status(403).json({ error: 'You can only check in employees from your site.' });
            }

            // Prevent duplicate open record on same day
            const existingOpen = await pool.query(
                `SELECT id FROM attendance
             WHERE employee_id = $1 AND check_out_time IS NULL
               AND DATE(check_in_time) = DATE($2)`,
                [emp.id, checkInTime]
            );
            if (existingOpen.rows.length > 0) {
                return res.status(409).json({ error: 'This employee already has an open check-in for that date. Please check out first.' });
            }

            const resolvedSiteId = siteId || emp.site_id;
            const noteText = `Manually logged by ${req.user.staffId} via HR Dashboard. ${notes || ''}`.trim();

            const result = await pool.query(
                `INSERT INTO attendance (employee_id, check_in_time, site_id, notes)
             VALUES ($1, $2, $3, $4) RETURNING *`,
                [emp.id, checkInTime, resolvedSiteId, noteText]
            );
            const record = result.rows[0];

            // Emit real-time event to dashboard
            io.to('hr-dashboard').emit('attendance_event', {
                type: 'manual_check_in',
                staffId,
                name: [emp.first_name, emp.last_name].filter(Boolean).join(' '),
                siteId: resolvedSiteId,
                checkInTime,
                loggedBy: req.user.staffId
            });

            console.log(`[MANUAL] Check-in: ${staffId} at ${checkInTime} logged by ${req.user.staffId}`);
            res.status(201).json({ success: true, record });
        } catch (err) {
            console.error('Manual check-in error:', err);
            res.status(500).json({ error: 'Database error', message: err.message });
        }
    });

    // HR API: Manual Check-Out (supervisor logs check-out for an employee)
    router.post('/hr/attendance/manual-checkout', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { staffId, checkOutTime, attendanceId, notes } = req.body;
        if (!staffId || !checkOutTime) {
            return res.status(400).json({ error: 'staffId and checkOutTime are required.' });
        }
        try {
            // Resolve employee
            const empResult = await pool.query(
                `SELECT e.id, e.site_id FROM employees e WHERE e.staff_id = $1`, [staffId]
            );
            if (empResult.rows.length === 0) return res.status(404).json({ error: 'Employee not found.' });
            const emp = empResult.rows[0];

            if (req.user.role === 'Site Supervisor' && emp.site_id !== req.user.siteId) {
                return res.status(403).json({ error: 'You can only check out employees from your site.' });
            }

            // Find the open record to close — use specific ID if provided
            let openRecord;
            if (attendanceId) {
                const r = await pool.query(
                    `SELECT id FROM attendance WHERE id = $1 AND employee_id = $2 AND check_out_time IS NULL`,
                    [attendanceId, emp.id]
                );
                openRecord = r.rows[0];
            } else {
                // Close the most recent open record
                const r = await pool.query(
                    `SELECT id FROM attendance
                 WHERE employee_id = $1 AND check_out_time IS NULL
                 ORDER BY check_in_time DESC LIMIT 1`,
                    [emp.id]
                );
                openRecord = r.rows[0];
            }

            if (!openRecord) {
                return res.status(404).json({ error: 'No open check-in record found for this employee.' });
            }

            const noteText = `Manually logged by ${req.user.staffId} via HR Dashboard. ${notes || ''}`.trim();

            const result = await pool.query(
                `UPDATE attendance
             SET check_out_time = $1, notes = COALESCE(notes || ' | ', '') || $2
             WHERE id = $3 RETURNING *`,
                [checkOutTime, noteText, openRecord.id]
            );

            const record = result.rows[0];

            io.to('hr-dashboard').emit('attendance_event', {
                type: 'manual_check_out',
                staffId,
                checkOutTime,
                loggedBy: req.user.staffId
            });

            console.log(`[MANUAL] Check-out: ${staffId} at ${checkOutTime} logged by ${req.user.staffId}`);
            res.json({ success: true, record });
        } catch (err) {
            console.error('Manual check-out error:', err);
            res.status(500).json({ error: 'Database error', message: err.message });
        }
    });

    // HR API: Get attendance report data

    router.get('/hr/reports/attendance', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { startDate, endDate, roleId, siteId, department } = req.query;

        try {
            // 1. Fetch Employees based on filters
            let empQuery = `
            SELECT e.id, e.staff_id, e.department_name, r.name as role_name, s.name as site_name 
            FROM employees e 
            LEFT JOIN roles r ON e.role_id = r.id 
            LEFT JOIN sites s ON e.site_id = s.id
            WHERE 1=1
        `;
            const empParams = [];
            let paramIdx = 1;

            if (roleId) {
                empQuery += ` AND e.role_id = $${paramIdx++}`;
                empParams.push(roleId);
            }

            // Site Logic: Supervisor is locked to their site. Admin can filter by site.
            const targetSiteId = req.user.role === 'Site Supervisor' ? req.user.siteId : siteId;
            if (targetSiteId) {
                empQuery += ` AND e.site_id = $${paramIdx++}`;
                empParams.push(targetSiteId);
            }

            if (department) {
                empQuery += ` AND e.department_name ILIKE $${paramIdx++}`;
                empParams.push(`%${department}%`);
            }

            empQuery += ` ORDER BY e.staff_id ASC`;

            const empResult = await pool.query(empQuery, empParams);
            const employees = empResult.rows;

            if (employees.length === 0) {
                return res.json({ employees: [], attendance: {} });
            }

            const empIds = employees.map(e => e.id);

            // 2. Fetch Attendance for these employees in date range
            let attQuery = `
            SELECT employee_id, check_in_time, check_out_time, site_id
            FROM attendance 
            WHERE employee_id = ANY($1)
        `;
            // Reset params for new query
            const attParams = [empIds];
            let attParamIdx = 2; // $1 is empIds

            const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
            const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);

            if (normalizedStartDate) {
                attQuery += ` AND check_in_time >= $${attParamIdx++}`;
                attParams.push(normalizedStartDate);
            }
            if (normalizedEndDate) {
                attQuery += ` AND check_in_time <= $${attParamIdx++}`;
                attParams.push(normalizedEndDate);
            }

            attQuery += ` ORDER BY check_in_time ASC`;

            const attResult = await pool.query(attQuery, attParams);

            // Group by Employee ID
            const attendanceMap = {};
            attResult.rows.forEach(row => {
                if (!attendanceMap[row.employee_id]) attendanceMap[row.employee_id] = [];
                attendanceMap[row.employee_id].push(row);
            });

            res.json({ employees, attendance: attendanceMap });

        } catch (err) {
            console.error('Report error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // --- BIOMETRIC ATTENDANCE REPORT DEDICATED ENDPOINT ---
    router.get('/hr/reports/biometrics', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { startDate, endDate, roleId, siteId, department } = req.query;

        try {
            // 1. Fetch relevant employees
            let empQuery = `
            SELECT e.id, e.staff_id, e.first_name, e.last_name, e.department_name, r.name as role_name, s.name as site_name 
            FROM employees e 
            LEFT JOIN roles r ON e.role_id = r.id 
            LEFT JOIN sites s ON e.site_id = s.id
            WHERE 1=1
        `;
            const empParams = [];
            let paramIdx = 1;

            if (roleId) {
                empQuery += ` AND e.role_id = $${paramIdx++}`;
                empParams.push(roleId);
            }

            const targetSiteId = req.user.role === 'Site Supervisor' ? req.user.siteId : siteId;
            if (targetSiteId) {
                empQuery += ` AND e.site_id = $${paramIdx++}`;
                empParams.push(targetSiteId);
            }

            if (department) {
                empQuery += ` AND e.department_name ILIKE $${paramIdx++}`;
                empParams.push(`%${department}%`);
            }

            empQuery += ` ORDER BY e.staff_id ASC`;
            const empResult = await pool.query(empQuery, empParams);
            let employees = empResult.rows;
            const validStaffIds = employees.map(e => e.staff_id).filter(id => id);

            // 2. Fetch biometric logs
            let logQuery = `
            SELECT staff_id, timestamp::date as log_date, min(timestamp) as check_in_time, max(timestamp) as check_out_time, min(raw_data::text) as raw_data
            FROM biometric_logs
            WHERE 1=1
        `;
            const logParams = [];
            let logParamIdx = 1;

            if (validStaffIds.length > 0) {
                if (roleId || siteId || department) {
                    logQuery += ` AND staff_id = ANY($${logParamIdx++})`;
                    logParams.push(validStaffIds);
                }
            } else if (roleId || siteId || department) {
                return res.json({ employees: [], attendance: {} });
            }

            const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
            const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);

            if (normalizedStartDate) {
                logQuery += ` AND timestamp >= $${logParamIdx++}`;
                logParams.push(normalizedStartDate);
            }
            if (normalizedEndDate) {
                logQuery += ` AND timestamp <= $${logParamIdx++}`;
                logParams.push(normalizedEndDate);
            }

            logQuery += ` GROUP BY staff_id, timestamp::date ORDER BY timestamp::date ASC`;

            const logResult = await pool.query(logQuery, logParams);

            // 3. Map logs to employees and handle unregistered terminals users (ghosts)
            const attendanceMap = {};
            const staffIdMap = {};
            employees.forEach(e => staffIdMap[e.staff_id] = e);

            logResult.rows.forEach(log => {
                const staffId = log.staff_id;

                if (!staffIdMap[staffId] && !roleId && !siteId && !department && staffId) {
                    let rawDataObj = {};
                    try { rawDataObj = JSON.parse(log.raw_data); } catch (e) { }
                    const fallbackName = rawDataObj?.personName || rawDataObj?.personId || staffId;
                    const ghostEmp = {
                        id: `ghost-${staffId}`,
                        staff_id: staffId,
                        first_name: fallbackName,
                        department_name: 'Terminal Data',
                        role_name: '-',
                        site_name: '-'
                    };
                    employees.push(ghostEmp);
                    staffIdMap[staffId] = ghostEmp;
                }

                if (staffIdMap[staffId]) {
                    const empId = staffIdMap[staffId].id;
                    if (!attendanceMap[empId]) attendanceMap[empId] = [];

                    const checkIn = new Date(log.check_in_time);
                    const checkOut = new Date(log.check_out_time);
                    const finalCheckOut = checkIn.getTime() === checkOut.getTime() ? null : log.check_out_time;

                    attendanceMap[empId].push({
                        check_in_time: log.check_in_time,
                        check_out_time: finalCheckOut
                    });
                }
            });

            // Filter out employees without logs to keep report clean
            employees = employees.filter(e => attendanceMap[e.id] && attendanceMap[e.id].length > 0);

            res.json({ employees, attendance: attendanceMap });

        } catch (err) {
            console.error('Error fetching biometric report:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // Audit Log Helper
    const logAudit = async (actorId, action, targetId = null, details = '') => {
        try {
            await pool.query(
                'INSERT INTO audit_logs (actor_id, action, target_id, details) VALUES ($1, $2, $3, $4)',
                [actorId, action, targetId, details]
            );
        } catch (err) {
            console.error('Audit log error:', err);
        }
    };

    // HR API: Get all sites
    router.get('/hr/sites', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        try {
            const result = await pool.query('SELECT * FROM sites ORDER BY name ASC');
            res.json(result.rows);
        } catch (err) {
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Create site
    router.post('/hr/sites', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { name, location, latitude, longitude, radiusMeters, geofenceType, geofenceData, geofenceEnabled, nfcPayload } = req.body;
        try {
            const result = await pool.query(
                'INSERT INTO sites (name, location, latitude, longitude, radius_meters, geofence_type, geofence_data, geofence_enabled, nfc_payload) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *',
                [name, location, latitude, longitude, radiusMeters || 100, geofenceType || 'CIRCLE', JSON.stringify(geofenceData), geofenceEnabled !== false, nfcPayload || null]
            );
            res.json(result.rows[0]);
        } catch (err) {
            console.error('Error creating site:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Update site
    router.patch('/hr/sites/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { id } = req.params;
        const { name, location, latitude, longitude, radiusMeters, geofenceType, geofenceData, geofenceEnabled, nfcPayload } = req.body;
        try {
            const result = await pool.query(
                'UPDATE sites SET name = $1, location = $2, latitude = $3, longitude = $4, radius_meters = $5, geofence_type = $6, geofence_data = $7, geofence_enabled = $8, nfc_payload = $9 WHERE id = $10 RETURNING *',
                [name, location, latitude, longitude, radiusMeters, geofenceType, JSON.stringify(geofenceData), geofenceEnabled !== false, nfcPayload || null, id]
            );
            res.json(result.rows[0]);
        } catch (err) {
            console.error('Error updating site:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Get all roles (with permissions)
    router.get('/hr/roles', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        try {
            const query = `
            SELECT r.id, r.name, 
                   COALESCE(
                       json_agg(
                           json_build_object('id', p.id, 'name', p.name, 'description', p.description)
                       ) FILTER (WHERE p.id IS NOT NULL),
                       '[]'
                   ) as permissions
            FROM roles r
            LEFT JOIN role_permissions rp ON r.id = rp.role_id
            LEFT JOIN permissions p ON rp.permission_id = p.id
            GROUP BY r.id
            ORDER BY r.name ASC
        `;
            const result = await pool.query(query);
            res.json(result.rows);
        } catch (err) {
            console.error('Error fetching roles:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Get all available permissions
    router.get('/hr/permissions', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            const result = await pool.query('SELECT * FROM permissions ORDER BY name ASC');
            res.json(result.rows);
        } catch (err) {
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Update role permissions
    router.post('/hr/roles/:id/permissions', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { id } = req.params;
        const { permissionIds } = req.body; // Array of permission IDs

        if (!Array.isArray(permissionIds)) {
            return res.status(400).json({ error: 'permissionIds must be an array' });
        }

        const client = await pool.connect();
        try {
            await client.query('BEGIN');

            // 1. Remove existing permissions for this role
            await client.query('DELETE FROM role_permissions WHERE role_id = $1', [id]);

            // 2. Insert new permissions
            if (permissionIds.length > 0) {
                // Generate value placeholders like ($1, $2), ($1, $3), ...
                // simpler loop is fine for moderate size
                for (const permId of permissionIds) {
                    await client.query(
                        'INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2)',
                        [id, permId]
                    );
                }
            }

            await client.query('COMMIT');
            res.json({ message: 'Permissions updated successfully' });
        } catch (err) {
            await client.query('ROLLBACK');
            console.error('Error updating role permissions:', err);
            res.status(500).json({ error: 'Database error' });
        } finally {
            client.release();
        }
    });

    // HR API: Get all users (paginated) - Updated
    router.get('/hr/users', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const page = parseInt(req.query.page) || 1;
        const limit = parseInt(req.query.limit) || 20;
        const offset = (page - 1) * limit;
        const search = req.query.search || '';

        try {
            const query = `
            SELECT e.*, r.name as role_name, s.name as site_name, sh.name as shift_name 
            FROM employees e
            LEFT JOIN roles r ON e.role_id = r.id
            LEFT JOIN sites s ON e.site_id = s.id
            LEFT JOIN shifts sh ON e.shift_id = sh.id
            WHERE (e.is_active = TRUE OR e.is_active IS NULL) AND (e.staff_id ILIKE $1 OR e.email ILIKE $1)
            ORDER BY e.created_at DESC
            LIMIT $2 OFFSET $3
        `;
            const result = await pool.query(query, [`%${search}%`, limit, offset]);

            const countRes = await pool.query('SELECT COUNT(*) FROM employees WHERE (is_active = TRUE OR is_active IS NULL) AND (staff_id ILIKE $1 OR email ILIKE $1)', [`%${search}%`]);

            res.json({
                users: result.rows,
                total: parseInt(countRes.rows[0].count),
                page,
                totalPages: Math.ceil(parseInt(countRes.rows[0].count) / limit)
            });
        } catch (err) {
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Delete or Archive user
    router.delete('/hr/users/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { id } = req.params;
        try {
            await pool.query('DELETE FROM employees WHERE id = $1', [id]);
            res.json({ message: 'User permanently deleted' });
        } catch (err) {
            if (err.code === '23503') { // Foreign key constraint violation
                try {
                    await pool.query('UPDATE employees SET is_active = FALSE WHERE id = $1', [id]);
                    res.json({ message: 'User archived properly due to existing records' });
                } catch (archiveErr) {
                    console.error('Error archiving user:', archiveErr);
                    res.status(500).json({ error: 'Failed to archive user' });
                }
            } else {
                console.error('Error deleting user:', err);
                res.status(500).json({ error: 'Database error' });
            }
        }
    });



    // HR API: Bulk update user fields (Shift, Site, Dept)
    router.patch('/hr/users/bulk-update', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { userIds, shiftId, siteId, departmentName } = req.body;
        if (!userIds || !Array.isArray(userIds) || userIds.length === 0) {
            return res.status(400).json({ error: 'Provide an array of user IDs' });
        }

        try {
            const updates = [];
            const params = [userIds];
            let paramIdx = 2;

            if (shiftId !== undefined) {
                updates.push(`shift_id = $${paramIdx++}`);
                params.push(shiftId === "" ? null : parseInt(shiftId));
            }
            if (siteId !== undefined) {
                updates.push(`site_id = $${paramIdx++}`);
                params.push(siteId === "" ? null : parseInt(siteId));
            }
            if (departmentName !== undefined) {
                updates.push(`department_name = $${paramIdx++}`);
                params.push(departmentName);
            }
            if (req.body.isTrackingEnabled !== undefined) {
                updates.push(`is_tracking_enabled = $${paramIdx++}`);
                params.push(req.body.isTrackingEnabled);
            }
            if (req.body.isActive !== undefined) {
                updates.push(`is_active = $${paramIdx++}`);
                params.push(req.body.isActive);
            }

            if (updates.length === 0) {
                return res.status(400).json({ error: 'No update data provided' });
            }

            const query = `UPDATE employees SET ${updates.join(', ')} WHERE id = ANY($1) RETURNING *`;
            const result = await pool.query(query, params);

            res.json({ message: `${result.rowCount} user(s) updated successfully`, count: result.rowCount });
        } catch (err) {
            console.error('Bulk update error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });
    // ── Biometrics API ──────────────────────────────────────────────────────────

    router.get('/hr/biometrics/devices', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        try {
            const result = await pool.query(`
            SELECT b.*, s.name as site_name 
            FROM biometric_devices b 
            LEFT JOIN sites s ON b.site_id = s.id 
            ORDER BY b.name ASC
        `);
            res.json(result.rows);
        } catch (err) {
            console.error('Error fetching biometric devices:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/biometrics/devices', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { name, deviceKey, siteId, type, ipAddress, port } = req.body;
        try {
            const result = await pool.query(
                'INSERT INTO biometric_devices (name, device_key, site_id, type, ip_address, port) VALUES ($1, $2, $3, $4, $5, $6) RETURNING *',
                [name, deviceKey, siteId || null, type || 'RA08', ipAddress || null, port || null]
            );
            res.json(result.rows[0]);
        } catch (err) {
            console.error('Error creating biometric device:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.patch('/hr/biometrics/devices/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { id } = req.params;
        const { name, siteId, type, isActive, ipAddress, port } = req.body;
        try {
            const result = await pool.query(
                'UPDATE biometric_devices SET name = COALESCE($1, name), site_id = $2, type = COALESCE($3, type), is_active = COALESCE($4, is_active), ip_address = COALESCE($5, ip_address), port = COALESCE($6, port) WHERE id = $7 RETURNING *',
                [name, siteId || null, type, isActive !== undefined ? isActive : true, ipAddress || null, port || null, id]
            );
            res.json(result.rows[0]);
        } catch (err) {
            console.error('Error updating biometric device:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.delete('/hr/biometrics/devices/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            await pool.query('DELETE FROM biometric_devices WHERE id = $1', [req.params.id]);
            res.json({ success: true });
        } catch (err) {
            console.error('Error deleting biometric device:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/biometrics/logs', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { staffId, deviceId } = req.query;
        try {
            let query = `
            SELECT l.*, d.name as device_name, e.first_name, e.last_name 
            FROM biometric_logs l
            JOIN biometric_devices d ON l.device_id = d.id
            LEFT JOIN employees e ON l.employee_id = e.id
            WHERE 1=1
        `;
            const params = [];
            let pIdx = 1;

            if (staffId) {
                query += ` AND (l.staff_id = $${pIdx} OR e.staff_id = $${pIdx})`;
                params.push(staffId);
                pIdx++;
            }
            if (deviceId) {
                query += ` AND l.device_id = $${pIdx}`;
                params.push(deviceId);
                pIdx++;
            }

            query += ' ORDER BY l.timestamp DESC LIMIT 100';
            const result = await pool.query(query, params);
            res.json(result.rows);
        } catch (err) {
            console.error('Error fetching biometric logs:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // Internal endpoint for RA08 listener (Basic shared token auth)
    router.post('/api/biometrics/log', async (req, res) => {
        const authHeader = req.headers['authorization'];
        const token = authHeader && authHeader.split(' ')[1];

        if (token !== 'attendance_secret_token') {
            console.warn(`[BIOMETRICS] Unauthorized log attempt with token: ${token}`);
            return res.status(403).json({ error: 'Forbidden' });
        }

        const { deviceKey, staffId, timestamp, photoUrl, rawData } = req.body;

        try {
            // Find device
            const deviceRes = await pool.query('SELECT id, site_id FROM biometric_devices WHERE device_key = $1', [deviceKey]);
            if (deviceRes.rows.length === 0) {
                return res.status(404).json({ error: 'Device not found' });
            }
            const deviceId = deviceRes.rows[0].id;

            // Find employee
            const empRes = await pool.query('SELECT id FROM employees WHERE staff_id = $1', [staffId]);
            const employeeId = empRes.rows.length > 0 ? empRes.rows[0].id : null;

            // Log biometric event
            await pool.query(
                'INSERT INTO biometric_logs (device_id, staff_id, employee_id, timestamp, photo_url, raw_data) VALUES ($1, $2, $3, $4, $5, $6)',
                [deviceId, staffId, employeeId, new Date(timestamp), photoUrl, JSON.stringify(rawData)]
            );

            // Update device last_seen
            await pool.query('UPDATE biometric_devices SET last_seen = NOW() WHERE id = $1', [deviceId]);

            res.json({ success: true });
        } catch (err) {
            console.error('Internal biometric log error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR Admin: Data Cleanup Stats
    router.get('/hr/admin/cleanup-stats', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            const [logsCount, logsOldest, alertsCount, alertsOldest, logsSize] = await Promise.all([
                pool.query('SELECT COUNT(*) FROM live_logs'),
                pool.query('SELECT MIN(timestamp) as oldest FROM live_logs'),
                pool.query('SELECT COUNT(*) FROM geo_fence_alerts'),
                pool.query('SELECT MIN(created_at) as oldest FROM geo_fence_alerts'),
                pool.query(`SELECT pg_size_pretty(pg_total_relation_size('live_logs')) as size`)
            ]);

            res.json({
                retentionDays: DATA_RETENTION_DAYS,
                nextCleanup: `Daily at 02:00 ${APP_TIMEZONE}`,
                live_logs: {
                    totalRows: parseInt(logsCount.rows[0].count),
                    oldestRecord: logsOldest.rows[0].oldest,
                    tableSize: logsSize.rows[0].size
                },
                geo_fence_alerts: {
                    totalRows: parseInt(alertsCount.rows[0].count),
                    oldestRecord: alertsOldest.rows[0].oldest
                }
            });
        } catch (err) {
            console.error('Cleanup stats error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR Admin: Manually trigger data cleanup (on-demand)
    router.post('/hr/admin/run-cleanup', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const started = Date.now();
        try {
            const retentionDays = req.body.retentionDays || DATA_RETENTION_DAYS;
            console.log(`[CLEANUP] Manual cleanup triggered by ${req.user.staffId}. Retention: ${retentionDays} days.`);

            const logsResult = await pool.query(
                `DELETE FROM live_logs WHERE timestamp < NOW() - INTERVAL '${parseInt(retentionDays)} days'`
            );
            const alertsResult = await pool.query(
                `DELETE FROM geo_fence_alerts
             WHERE created_at < NOW() - INTERVAL '${parseInt(retentionDays)} days'
               AND status = 'resolved'`
            );

            const elapsed = ((Date.now() - started) / 1000).toFixed(2);
            console.log(`[CLEANUP] Manual cleanup done in ${elapsed}s: live_logs=${logsResult.rowCount}, alerts=${alertsResult.rowCount}`);

            res.json({
                success: true,
                deleted: {
                    live_logs: logsResult.rowCount,
                    geo_fence_alerts: alertsResult.rowCount
                },
                retentionDays,
                elapsed: `${elapsed}s`
            });
        } catch (err) {
            console.error('[CLEANUP] Manual cleanup error:', err);
            res.status(500).json({ error: 'Cleanup failed', message: err.message });
        }
    });

    // HR Admin: View Auto-Closed attendance records
    router.get('/hr/admin/auto-closed', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        try {
            const { siteId, startDate, endDate, page = 1, limit = 50 } = req.query;
            const offset = (parseInt(page) - 1) * parseInt(limit);
            const params = [];
            const conditions = [`a.auto_closed = true`];

            // Supervisors can only see their own site
            if (req.user.role === 'Site Supervisor') {
                params.push(req.user.siteId);
                conditions.push(`a.site_id = $${params.length}`);
            } else if (siteId) {
                params.push(siteId);
                conditions.push(`a.site_id = $${params.length}`);
            }
            const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
            const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);

            if (normalizedStartDate) {
                params.push(normalizedStartDate);
                conditions.push(`a.check_in_time >= $${params.length}`);
            }
            if (normalizedEndDate) {
                params.push(normalizedEndDate);
                conditions.push(`a.check_in_time <= $${params.length}`);
            }

            const whereClause = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';

            const countResult = await pool.query(
                `SELECT COUNT(*) FROM attendance a ${whereClause}`, params
            );
            const total = parseInt(countResult.rows[0].count);

            params.push(parseInt(limit), offset);
            const result = await pool.query(
                `SELECT
                a.id, a.check_in_time, a.check_out_time, a.notes, a.auto_closed,
                e.staff_id, e.first_name, e.last_name,
                s.name as site_name,
                sh.name as shift_name
             FROM attendance a
             JOIN employees e ON a.employee_id = e.id
             LEFT JOIN sites s ON a.site_id = s.id
             LEFT JOIN shifts sh ON e.shift_id = sh.id
             ${whereClause}
             ORDER BY a.check_in_time DESC
             LIMIT $${params.length - 1} OFFSET $${params.length}`,
                params
            );

            res.json({
                records: result.rows,
                total,
                page: parseInt(page),
                totalPages: Math.ceil(total / parseInt(limit))
            });
        } catch (err) {
            console.error('Auto-closed query error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR Admin: Manually trigger auto-checkout job now
    router.post('/hr/admin/auto-checkout/run', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        console.log(`[AUTO-CHECKOUT] Manual run triggered by ${req.user.staffId}`);
        // Run async — respond immediately then process
        res.json({ success: true, message: 'Auto-checkout job started. Check logs for results.' });
        runAutoCheckout();
    });

    // HR API: Get all shifts


    router.get('/hr/shifts', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            const result = await pool.query('SELECT * FROM shifts ORDER BY name ASC');
            res.json(result.rows);
        } catch (err) {
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Create shift
    router.post('/hr/shifts', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { name, startTime, endTime } = req.body;
        try {
            const result = await pool.query(
                'INSERT INTO shifts (name, start_time, end_time) VALUES ($1, $2, $3) RETURNING *',
                [name, startTime, endTime]
            );
            res.json(result.rows[0]);
        } catch (err) {
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Update shift
    router.put('/hr/shifts/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const { id } = req.params;
        const { name, startTime, endTime } = req.body;
        try {
            const result = await pool.query(
                'UPDATE shifts SET name = $1, start_time = $2, end_time = $3 WHERE id = $4 RETURNING *',
                [name, startTime, endTime, id]
            );
            if (result.rows.length === 0) {
                return res.status(404).json({ error: 'Shift not found' });
            }
            res.json(result.rows[0]);
        } catch (err) {
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Get Alerts (paginated, filterable)
    router.get('/hr/alerts', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { staffId, siteId: filterSiteId, status, startDate, endDate, page = 1, limit = 50 } = req.query;
        const offset = (parseInt(page) - 1) * parseInt(limit);
        try {
            const conditions = [];
            const params = [];
            let idx = 1;

            // Site Supervisor: locked to their own site via employee's site
            if (req.user.role === 'Site Supervisor') {
                conditions.push(`e.site_id = $${idx++}`);
                params.push(req.user.siteId);
            } else if (filterSiteId) {
                conditions.push(`a.site_id = $${idx++}`);
                params.push(filterSiteId);
            }

            if (staffId) {
                conditions.push(`e.staff_id ILIKE $${idx++}`);
                params.push(`%${staffId}%`);
            }

            if (status) {
                conditions.push(`a.status = $${idx++}`);
                params.push(status);
            }

            const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
            const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);

            if (normalizedStartDate) {
                conditions.push(`a.created_at >= $${idx++}`);
                params.push(normalizedStartDate);
            }

            if (normalizedEndDate) {
                conditions.push(`a.created_at <= $${idx++}`);
                params.push(normalizedEndDate);
            }

            const where = conditions.length > 0 ? 'WHERE ' + conditions.join(' AND ') : '';

            const query = `
            SELECT a.*, e.staff_id, e.first_name, e.last_name, s.name as site_name
            FROM geo_fence_alerts a
            JOIN employees e ON a.employee_id = e.id
            LEFT JOIN sites s ON a.site_id = s.id
            ${where}
            ORDER BY a.created_at DESC
            LIMIT $${idx++} OFFSET $${idx++}
        `;
            params.push(parseInt(limit), offset);

            const countQuery = `
            SELECT COUNT(*) FROM geo_fence_alerts a
            JOIN employees e ON a.employee_id = e.id
            LEFT JOIN sites s ON a.site_id = s.id
            ${where}
        `;
            const countParams = params.slice(0, -2); // exclude limit/offset

            const [result, countRes] = await Promise.all([
                pool.query(query, params),
                pool.query(countQuery, countParams)
            ]);

            res.json({
                alerts: result.rows,
                total: parseInt(countRes.rows[0].count),
                page: parseInt(page),
                totalPages: Math.ceil(parseInt(countRes.rows[0].count) / parseInt(limit))
            });
        } catch (err) {
            console.error(err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Resolve a geo-fence alert
    router.patch('/hr/alerts/:id/resolve', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { id } = req.params;
        try {
            const result = await pool.query(
                `UPDATE geo_fence_alerts SET status = 'resolved' WHERE id = $1 RETURNING *`,
                [id]
            );
            if (result.rows.length === 0) return res.status(404).json({ error: 'Alert not found' });
            res.json(result.rows[0]);
        } catch (err) {
            console.error(err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Bulk resolve geo-fence alerts
    router.patch('/hr/alerts/bulk-resolve', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { ids } = req.body;
        if (!ids || !Array.isArray(ids) || ids.length === 0) {
            return res.status(400).json({ error: 'Provide an array of alert IDs' });
        }
        try {
            const result = await pool.query(
                `UPDATE geo_fence_alerts SET status = 'resolved' WHERE id = ANY($1) RETURNING *`,
                [ids]
            );
            res.json({ message: `${result.rowCount} alert(s) resolved`, resolved: result.rows });
        } catch (err) {
            console.error('Bulk resolve error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/location-logs', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { staffId, startDate, endDate, page = 1, limit = 100 } = req.query;
        const offset = (parseInt(page) - 1) * parseInt(limit);
        const params = [];
        const conditions = [];
        let idx = 1;

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

        const where = conditions.length > 0 ? 'WHERE ' + conditions.join(' AND ') : '';

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
        try {
            const result = await pool.query('DELETE FROM live_logs WHERE id = $1 RETURNING id', [id]);
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
            if (ids && Array.isArray(ids) && ids.length > 0) {
                await pool.query('DELETE FROM live_logs WHERE id = ANY($1)', [ids]);
                return res.json({ message: `${ids.length} log(s) deleted` });
            }

            const conditions = [];
            const params = [];
            let idx = 1;

            if (staffId) {
                const empRes = await pool.query(
                    `SELECT id
                     FROM employees
                     WHERE staff_id ILIKE $1
                        OR COALESCE(first_name, '') ILIKE $1
                        OR COALESCE(last_name, '') ILIKE $1
                        OR CONCAT_WS(' ', COALESCE(first_name, ''), COALESCE(last_name, '')) ILIKE $1`,
                    [`%${String(staffId).trim()}%`]
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

            const empQuery = `
            SELECT e.id, e.staff_id, e.first_name, e.last_name, e.site_id, s.name as site_name
            FROM employees e
            LEFT JOIN sites s ON e.site_id = s.id
            WHERE e.staff_id = $1
        `;
            const empResult = await pool.query(empQuery, [staffId]);

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

            const empQuery = `SELECT id, staff_id, first_name, last_name FROM employees WHERE staff_id = $1`;
            const empResult = await pool.query(empQuery, [staffId]);
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


    // Socket.io Middleware: Authenticate
    io.use((socket, next) => {
        const token = socket.handshake.auth.token;
        if (!token) {
            return next(new Error("Authentication error"));
        }
        jwt.verify(token, JWT_SECRET, (err, decoded) => {
            if (err) {
                return next(new Error("Authentication error"));
            }
            socket.user = decoded;
            next();
        });
    });

    return router;
};
