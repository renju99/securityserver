const fs = require('fs');
const path = require('path');
const { z } = require('zod');
const { createClient } = require('redis');
const { parseDescriptor } = require('../../utils/faceAuth');
const { enqueueAttendanceSync } = require('../../services/attendanceSyncQueue');
const {
    getEffectiveAttendancePolicy,
    shouldRequireApproval,
    addApprovalLog,
    applyCheckoutPolicy,
} = require('../../services/attendanceGovernance');
const { organizationIdFromUser, hrDashboardRoom } = require('../../utils/organization');

const uploadsDir = path.join(__dirname, '..', '..', 'uploads');
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

const userUpsertSchema = z.object({
    staffId: z.string().min(1, 'staffId is required'),
    email: z.string().email().optional().or(z.literal('')).nullable(),
    password: z.string().min(6).optional().or(z.literal('')).nullable(),
    roleId: z.union([z.number(), z.string()]).optional().nullable(),
    siteId: z.union([z.number(), z.string()]).optional().nullable(),
    departmentName: z.string().optional().nullable(),
    firstName: z.string().optional().nullable(),
    lastName: z.string().optional().nullable(),
    shiftId: z.union([z.number(), z.string()]).optional().nullable(),
    photoHelper: z.string().optional().nullable(),
    isTrackingEnabled: z.boolean().optional(),
    faceAuthEnabled: z.boolean().optional(),
    facePin: z.string().trim().regex(/^\d{4,10}$/, 'facePin must be 4-10 digits').optional().nullable().or(z.literal('')),
    phoneE164: z.string().trim().max(24).optional().nullable().or(z.literal('')),
});

const faceEnrollmentSchema = z.object({
    descriptor: z.array(z.number()).min(64, 'A valid face descriptor is required'),
    enrollmentImage: z.string().optional().nullable(),
});

const bulkUpdateSchema = z.object({
    userIds: z.array(z.union([z.number(), z.string()])).min(1, 'Provide an array of user IDs'),
    shiftId: z.union([z.number(), z.string()]).optional().nullable(),
    siteId: z.union([z.number(), z.string()]).optional().nullable(),
    departmentName: z.string().optional().nullable(),
    isTrackingEnabled: z.boolean().optional(),
    isActive: z.boolean().optional(),
});

const manualCheckinSchema = z.object({
    staffId: z.string().trim().min(1, 'staffId is required'),
    checkInTime: z.string().trim().min(1, 'checkInTime is required'),
    siteId: z.union([z.number(), z.string()]).optional().nullable(),
    notes: z.string().trim().max(500).optional().nullable(),
    jobCode: z.string().trim().max(64).optional().nullable(),
    activityName: z.string().trim().max(120).optional().nullable(),
});

const manualCheckoutSchema = z.object({
    staffId: z.string().trim().min(1, 'staffId is required'),
    checkOutTime: z.string().trim().min(1, 'checkOutTime is required'),
    attendanceId: z.union([z.number(), z.string()]).optional().nullable(),
    notes: z.string().trim().max(500).optional().nullable(),
    jobCode: z.string().trim().max(64).optional().nullable(),
    activityName: z.string().trim().max(120).optional().nullable(),
});

const bulkManualCheckoutSchema = z.object({
    staffIds: z.array(z.string().trim().min(1)).optional(),
    siteId: z.union([z.number(), z.string()]).optional().nullable(),
    departmentName: z.string().trim().optional().nullable(),
    checkOutTime: z.string().trim().optional().nullable(),
    notes: z.string().trim().max(500).optional().nullable(),
}).refine((data) => (Array.isArray(data.staffIds) && data.staffIds.length > 0) || data.siteId || data.departmentName, {
    message: 'Provide staffIds, siteId, or departmentName to select employees',
});

module.exports = ({ router, pool, authenticateToken, authorizeRole, bcrypt, io }) => {
    let redisClient = null;
    let redisReady = false;
    if (process.env.REDIS_URL) {
        redisClient = createClient({ url: process.env.REDIS_URL });
        redisClient.on('error', (err) => {
            redisReady = false;
            console.error('[HR_USERS] Redis error:', err.message);
        });
        redisClient.connect()
            .then(() => { redisReady = true; })
            .catch((err) => {
                redisReady = false;
                console.error('[HR_USERS] Redis connect failed:', err.message);
            });
    }

    const safeEmployeeSelect = `
        e.id, e.staff_id, e.email, e.phone_e164, e.role_id, e.site_id, e.department_name, e.first_name, e.last_name,
        e.photo_url, e.is_active, e.created_at, e.shift_id, e.is_tracking_enabled, e.face_auth_enabled,
        e.face_enrolled_at, e.face_enrollment_photo_url, (e.face_descriptor IS NOT NULL) as face_enrolled
    `;
    const safeEmployeeReturning = `
        id, staff_id, email, phone_e164, role_id, site_id, department_name, first_name, last_name,
        photo_url, is_active, created_at, shift_id, is_tracking_enabled, face_auth_enabled, face_enrollment_photo_url,
        face_enrolled_at, (face_descriptor IS NOT NULL) as face_enrolled
    `;
    const logFaceEvent = async ({ employeeId, actorId, eventType, result = 'success', metadata = {} }) => {
        try {
            await pool.query(
                `INSERT INTO face_auth_events (employee_id, actor_id, event_type, result, metadata)
                 VALUES ($1, $2, $3, $4, $5::jsonb)`,
                [employeeId, actorId || null, eventType, result, JSON.stringify(metadata || {})]
            );
        } catch (err) {
            console.error('Face audit log error:', err);
        }
    };

    const invalidateKioskSiteCandidates = async (siteId) => {
        const numericSiteId = Number(siteId);
        if (!Number.isFinite(numericSiteId) || numericSiteId <= 0) return;
        if (!(redisClient && redisReady)) return;
        try {
            await redisClient.del(`kiosk:site:candidates:${numericSiteId}`);
            await redisClient.incr(`kiosk:site:version:${numericSiteId}`);
        } catch (err) {
            console.error('[HR_USERS] Failed to invalidate kiosk cache:', err.message);
        }
    };

    // HR API: Get all employees
    router.get('/hr/employees', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor', 'Payroll', 'Finance']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            let query = `
            SELECT ${safeEmployeeSelect}, r.name as role_name, s.name as site_name, sh.name as shift_name, sh.start_time, sh.end_time
            FROM employees e
            LEFT JOIN roles r ON e.role_id = r.id 
            LEFT JOIN sites s ON e.site_id = s.id
            LEFT JOIN shifts sh ON e.shift_id = sh.id
            WHERE e.organization_id = $1
        `;
            const params = [orgId];

            if (req.user.role === 'Site Supervisor') {
                query += ` AND e.site_id = $${params.length + 1}`;
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
        const parsed = userUpsertSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid user payload' });
        }
        const { staffId, email, password, roleId, siteId, departmentName, firstName, lastName, photoHelper, shiftId, isTrackingEnabled, faceAuthEnabled, facePin, phoneE164 } = parsed.data;
        // photoHelper is the base64 string from frontend if updated

        try {
            let passwordHash = null;
            if (password) {
                passwordHash = await bcrypt.hash(password, 10);
            }
            let facePinHash = null;
            if (facePin && String(facePin).trim()) {
                facePinHash = await bcrypt.hash(String(facePin).trim(), 10);
            }

            let photoUrl = null;
            if (photoHelper) {
                photoUrl = saveBase64Image(photoHelper, staffId);
            }

            const orgId = organizationIdFromUser(req.user);
            const query = `
            INSERT INTO employees (organization_id, staff_id, email, phone_e164, password_hash, role_id, site_id, department_name, first_name, last_name, photo_url, shift_id, is_tracking_enabled, face_auth_enabled, face_pin_hash)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            ON CONFLICT (organization_id, staff_id) DO UPDATE SET
            email = EXCLUDED.email,
            phone_e164 = EXCLUDED.phone_e164,
            password_hash = COALESCE(EXCLUDED.password_hash, employees.password_hash),
            role_id = EXCLUDED.role_id,
            site_id = EXCLUDED.site_id,
            department_name = EXCLUDED.department_name,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            photo_url = COALESCE(EXCLUDED.photo_url, employees.photo_url),
            shift_id = EXCLUDED.shift_id,
            is_tracking_enabled = COALESCE(EXCLUDED.is_tracking_enabled, employees.is_tracking_enabled),
            face_auth_enabled = COALESCE(EXCLUDED.face_auth_enabled, employees.face_auth_enabled),
            face_pin_hash = COALESCE(EXCLUDED.face_pin_hash, employees.face_pin_hash)
            RETURNING ${safeEmployeeReturning}
        `;

            const sanitizedRoleId = roleId || null;
            const sanitizedSiteId = siteId || null;
            const sanitizedDept = departmentName || null;
            const sanitizedShiftId = shiftId || null;
            const sanitizedTracking = isTrackingEnabled !== undefined ? isTrackingEnabled : true;
            const sanitizedFaceAuthEnabled = faceAuthEnabled !== undefined ? faceAuthEnabled : null;

            const result = await pool.query(query, [
                orgId,
                staffId,
                email,
                phoneE164 && String(phoneE164).trim() ? String(phoneE164).trim() : null,
                passwordHash,
                sanitizedRoleId,
                sanitizedSiteId,
                sanitizedDept,
                firstName || null,
                lastName || null,
                photoUrl,
                sanitizedShiftId,
                sanitizedTracking,
                sanitizedFaceAuthEnabled,
                facePinHash
            ]);

            res.json(result.rows[0]);
        } catch (err) {
            console.error('Error adding user:', err);
            if (err.code === '23505') {
                if (String(err.constraint || '').includes('email')) {
                    return res.status(400).json({ error: 'Email already in use' });
                }
                if (String(err.constraint || '').includes('staff')) {
                    return res.status(400).json({ error: 'Staff ID already exists' });
                }
            }
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Get recent attendance (Filtered by site for Supervisors)
    router.get('/hr/attendance', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor', 'Payroll', 'Finance']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const lateMins = parseInt(process.env.LATE_THRESHOLD_MINS || '15', 10);
            let query = `
            SELECT a.*, e.staff_id, e.email, e.first_name, e.last_name, s.name as site_name,
                   sh.start_time as shift_start_time,
                   CASE
                     WHEN sh.start_time IS NULL THEN false
                     ELSE (a.check_in_time::time > (sh.start_time + ($1 || ' minutes')::interval))
                   END as is_late
            FROM attendance a 
            JOIN employees e ON a.employee_id = e.id 
            LEFT JOIN sites s ON a.site_id = s.id
            LEFT JOIN shifts sh ON e.shift_id = sh.id
            WHERE e.organization_id = $2
        `;
            const params = [lateMins, orgId];

            if (req.user.role === 'Site Supervisor') {
                query += ` AND e.site_id = $${params.length + 1}`;
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

    router.get('/hr/attendance/current-summary', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const lateMins = parseInt(process.env.LATE_THRESHOLD_MINS || '15', 10);
            const params = [orgId];
            const conditions = [`a.check_out_time IS NULL`, `a.status NOT IN ('voided', 'rejected')`, 'e.organization_id = $1'];
            if (req.user.role === 'Site Supervisor') {
                params.push(req.user.siteId);
                conditions.push(`e.site_id = $${params.length}`);
            }

            const query = `
                SELECT
                    a.id as attendance_id,
                    a.check_in_time,
                    e.id as employee_id,
                    e.staff_id,
                    e.first_name,
                    e.last_name,
                    e.department_name,
                    e.site_id,
                    s.name as site_name,
                    sh.start_time as shift_start_time,
                    CASE
                        WHEN sh.start_time IS NULL THEN false
                        ELSE (a.check_in_time::time > (sh.start_time + ($${params.length + 1} || ' minutes')::interval))
                    END as is_late
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                LEFT JOIN sites s ON e.site_id = s.id
                LEFT JOIN shifts sh ON e.shift_id = sh.id
                WHERE ${conditions.join(' AND ')}
                ORDER BY a.check_in_time DESC
                LIMIT 500
            `;
            const result = await pool.query(query, [...params, lateMins]);
            const rows = result.rows;

            const bySite = {};
            let lateCount = 0;
            rows.forEach((row) => {
                const key = row.site_name || 'Unassigned';
                bySite[key] = (bySite[key] || 0) + 1;
                if (row.is_late) lateCount += 1;
            });

            res.json({
                totalCheckedIn: rows.length,
                lateCount,
                lateThresholdMins: lateMins,
                perSiteCounts: bySite,
                records: rows
            });
        } catch (err) {
            console.error('Current attendance summary error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Manual Check-In (supervisor logs check-in for an employee)
    router.post('/hr/attendance/manual-checkin', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const parsed = manualCheckinSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid manual check-in payload' });
        }
        const { staffId, checkInTime, siteId, notes, jobCode, activityName } = parsed.data;
        try {
            const orgId = organizationIdFromUser(req.user);
            // Resolve employee
            const empResult = await pool.query(
                `SELECT e.id, e.first_name, e.last_name, e.site_id, e.shift_id
             FROM employees e WHERE e.staff_id = $1 AND e.organization_id = $2`, [staffId, orgId]
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
               AND status NOT IN ('voided', 'rejected')
               AND DATE(check_in_time) = DATE($2)`,
                [emp.id, checkInTime]
            );
            if (existingOpen.rows.length > 0) {
                return res.status(409).json({ error: 'This employee already has an open check-in for that date. Please check out first.' });
            }

            const resolvedSiteId = siteId === '' || siteId === null || siteId === undefined ? emp.site_id : siteId;
            const noteText = `Manually logged by ${req.user.staffId} via HR Dashboard. ${notes || ''}`.trim();
            const policy = await getEffectiveAttendancePolicy(pool, { siteId: resolvedSiteId || emp.site_id, shiftId: emp.shift_id || null });
            const requireApproval = shouldRequireApproval(policy, 'manual');
            const workContext = {
                ...(jobCode ? { jobCode } : {}),
                ...(activityName ? { activityName } : {}),
            };

            const result = await pool.query(
                `INSERT INTO attendance (employee_id, check_in_time, site_id, notes, source, status, work_context)
             VALUES ($1, $2, $3, $4, 'manual', $5, $6::jsonb) RETURNING *`,
                [emp.id, checkInTime, resolvedSiteId, noteText, requireApproval ? 'pending' : 'approved', JSON.stringify(workContext)]
            );
            const record = result.rows[0];
            if (record.status === 'pending') {
                await addApprovalLog(pool, {
                    attendanceId: record.id,
                    action: 'submitted',
                    actorId: req.user.id,
                    metadata: { source: 'manual' },
                });
            }

            // Emit real-time event to dashboard
            io.to(hrDashboardRoom(orgId)).emit('attendance_event', {
                type: 'manual_check_in',
                staffId,
                name: [emp.first_name, emp.last_name].filter(Boolean).join(' '),
                siteId: resolvedSiteId,
                checkInTime,
                loggedBy: req.user.staffId
            });

            console.log(`[MANUAL] Check-in: ${staffId} at ${checkInTime} logged by ${req.user.staffId}`);
            await enqueueAttendanceSync(pool, {
                attendanceId: record.id,
                staffId,
                eventType: 'check_in',
                siteId: resolvedSiteId,
                checkInTime: record.check_in_time || checkInTime,
                source: 'manual',
            });
            res.status(201).json({ success: true, record });
        } catch (err) {
            console.error('Manual check-in error:', err);
            res.status(500).json({ error: 'Database error', message: err.message });
        }
    });

    // HR API: Manual Check-Out (supervisor logs check-out for an employee)
    router.post('/hr/attendance/manual-checkout', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const parsed = manualCheckoutSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid manual check-out payload' });
        }
        const { staffId, checkOutTime, attendanceId, notes, jobCode, activityName } = parsed.data;
        try {
            const orgId = organizationIdFromUser(req.user);
            // Resolve employee
            const empResult = await pool.query(
                `SELECT e.id, e.site_id FROM employees e WHERE e.staff_id = $1 AND e.organization_id = $2`, [staffId, orgId]
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
                    `SELECT id FROM attendance WHERE id = $1 AND employee_id = $2 AND check_out_time IS NULL
                     AND status NOT IN ('voided', 'rejected')`,
                    [attendanceId, emp.id]
                );
                openRecord = r.rows[0];
            } else {
                // Close the most recent open record
                const r = await pool.query(
                    `SELECT id FROM attendance
                 WHERE employee_id = $1 AND check_out_time IS NULL
                   AND status NOT IN ('voided', 'rejected')
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
             SET check_out_time = $1,
                 notes = COALESCE(notes || ' | ', '') || $2,
                 source = COALESCE(source, 'manual'),
                 work_context = COALESCE(work_context, '{}'::jsonb) || $4::jsonb
             WHERE id = $3 RETURNING *`,
                [
                    checkOutTime,
                    noteText,
                    openRecord.id,
                    JSON.stringify({
                        ...(jobCode ? { jobCode } : {}),
                        ...(activityName ? { activityName } : {}),
                    })
                ]
            );

            const record = result.rows[0];
            await applyCheckoutPolicy(pool, {
                attendanceId: record.id,
                checkInTime: record.check_in_time,
                checkOutTime: record.check_out_time || checkOutTime,
                siteId: emp.site_id,
                shiftId: null,
            });

            io.to(hrDashboardRoom(orgId)).emit('attendance_event', {
                type: 'manual_check_out',
                staffId,
                checkOutTime,
                loggedBy: req.user.staffId
            });

            console.log(`[MANUAL] Check-out: ${staffId} at ${checkOutTime} logged by ${req.user.staffId}`);
            await enqueueAttendanceSync(pool, {
                attendanceId: record.id,
                staffId,
                eventType: 'check_out',
                siteId: emp.site_id,
                checkOutTime: record.check_out_time || checkOutTime,
                source: 'manual',
            });
            res.json({ success: true, record });
        } catch (err) {
            console.error('Manual check-out error:', err);
            res.status(500).json({ error: 'Database error', message: err.message });
        }
    });

    // HR API: Bulk Manual Check-Out (emergency operations)
    router.post('/hr/attendance/manual-bulk-checkout', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const parsed = bulkManualCheckoutSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid bulk check-out payload' });
        }
        const { staffIds = [], siteId, departmentName, checkOutTime, notes } = parsed.data;

        try {
            const orgId = organizationIdFromUser(req.user);
            const params = [orgId];
            const conditions = [`a.check_out_time IS NULL`, `a.status NOT IN ('voided', 'rejected')`, 'e.organization_id = $1'];
            let idx = 2;

            if (staffIds.length > 0) {
                conditions.push(`e.staff_id = ANY($${idx++})`);
                params.push(staffIds);
            }

            if (req.user.role === 'Site Supervisor') {
                conditions.push(`e.site_id = $${idx++}`);
                params.push(req.user.siteId);
            } else if (siteId) {
                conditions.push(`e.site_id = $${idx++}`);
                params.push(Number.parseInt(String(siteId), 10));
            }

            if (departmentName) {
                conditions.push(`COALESCE(e.department_name, '') ILIKE $${idx++}`);
                params.push(`%${departmentName}%`);
            }

            const targetRes = await pool.query(
                `SELECT a.id, a.employee_id, a.check_in_time, e.staff_id, e.first_name, e.last_name, e.site_id
                 FROM attendance a
                 JOIN employees e ON a.employee_id = e.id
                 WHERE ${conditions.join(' AND ')}`,
                params
            );

            if (targetRes.rows.length === 0) {
                return res.status(404).json({ error: 'No open attendance records found for the provided filters.' });
            }

            const closeTime = checkOutTime || new Date().toISOString();
            const noteText = `Bulk manual check-out by ${req.user.staffId}. ${notes || ''}`.trim();
            const attendanceIds = targetRes.rows.map((row) => row.id);

            const updateRes = await pool.query(
                `UPDATE attendance
                 SET check_out_time = $1,
                     notes = COALESCE(notes || ' | ', '') || $2,
                     source = COALESCE(source, 'manual_bulk')
                 WHERE id = ANY($3)
                 RETURNING id`,
                [closeTime, noteText, attendanceIds]
            );

            io.to(hrDashboardRoom(orgId)).emit('attendance_event', {
                type: 'manual_bulk_check_out',
                count: updateRes.rowCount,
                checkOutTime: closeTime,
                loggedBy: req.user.staffId
            });

            for (const row of targetRes.rows) {
                // eslint-disable-next-line no-await-in-loop
                await applyCheckoutPolicy(pool, {
                    attendanceId: row.id,
                    checkInTime: row.check_in_time,
                    checkOutTime: closeTime,
                    siteId: row.site_id,
                    shiftId: null,
                });
                // eslint-disable-next-line no-await-in-loop
                await enqueueAttendanceSync(pool, {
                    attendanceId: row.id,
                    staffId: row.staff_id,
                    eventType: 'check_out',
                    siteId: row.site_id,
                    checkOutTime: closeTime,
                    source: 'manual_bulk',
                });
            }

            res.json({
                success: true,
                closedCount: updateRes.rowCount,
                attendanceIds
            });
        } catch (err) {
            console.error('Bulk manual check-out error:', err);
            res.status(500).json({ error: 'Database error', message: err.message });
        }
    });

    // HR API: Get all users (paginated) - Updated
    router.get('/hr/users', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const page = parseInt(req.query.page) || 1;
        const limit = parseInt(req.query.limit) || 20;
        const offset = (page - 1) * limit;
        const search = req.query.search || '';

        try {
            const orgId = organizationIdFromUser(req.user);
            const query = `
            SELECT ${safeEmployeeSelect}, r.name as role_name, s.name as site_name, sh.name as shift_name
            FROM employees e
            LEFT JOIN roles r ON e.role_id = r.id
            LEFT JOIN sites s ON e.site_id = s.id
            LEFT JOIN shifts sh ON e.shift_id = sh.id
            WHERE e.organization_id = $4 AND (e.is_active = TRUE OR e.is_active IS NULL) AND (e.staff_id ILIKE $1 OR e.email ILIKE $1)
            ORDER BY e.created_at DESC
            LIMIT $2 OFFSET $3
        `;
            const result = await pool.query(query, [`%${search}%`, limit, offset, orgId]);

            const countRes = await pool.query(
                'SELECT COUNT(*) FROM employees WHERE organization_id = $2 AND (is_active = TRUE OR is_active IS NULL) AND (staff_id ILIKE $1 OR email ILIKE $1)',
                [`%${search}%`, orgId]
            );

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
        const orgId = organizationIdFromUser(req.user);
        try {
            await pool.query('DELETE FROM employees WHERE id = $1 AND organization_id = $2', [id, orgId]);
            res.json({ message: 'User permanently deleted' });
        } catch (err) {
            if (err.code === '23503') { // Foreign key constraint violation
                try {
                    await pool.query('UPDATE employees SET is_active = FALSE WHERE id = $1 AND organization_id = $2', [id, orgId]);
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
        const parsed = bulkUpdateSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid bulk update payload' });
        }
        const { userIds, shiftId, siteId, departmentName, isTrackingEnabled, isActive } = parsed.data;

        try {
            const updates = [];
            const params = [userIds];
            let paramIdx = 2;

            if (shiftId !== undefined) {
                updates.push(`shift_id = $${paramIdx++}`);
                const parsedShift = shiftId === "" || shiftId === null ? null : Number.parseInt(String(shiftId), 10);
                if (parsedShift !== null && Number.isNaN(parsedShift)) {
                    return res.status(400).json({ error: 'shiftId must be a number or empty' });
                }
                params.push(parsedShift);
            }
            if (siteId !== undefined) {
                updates.push(`site_id = $${paramIdx++}`);
                const parsedSite = siteId === "" || siteId === null ? null : Number.parseInt(String(siteId), 10);
                if (parsedSite !== null && Number.isNaN(parsedSite)) {
                    return res.status(400).json({ error: 'siteId must be a number or empty' });
                }
                params.push(parsedSite);
            }
            if (departmentName !== undefined) {
                updates.push(`department_name = $${paramIdx++}`);
                params.push(departmentName);
            }
            if (isTrackingEnabled !== undefined) {
                updates.push(`is_tracking_enabled = $${paramIdx++}`);
                params.push(isTrackingEnabled);
            }
            if (isActive !== undefined) {
                updates.push(`is_active = $${paramIdx++}`);
                params.push(isActive);
            }

            if (updates.length === 0) {
                return res.status(400).json({ error: 'No update data provided' });
            }

            const orgId = organizationIdFromUser(req.user);
            const query = `UPDATE employees SET ${updates.join(', ')} WHERE id = ANY($1) AND organization_id = $${paramIdx++} RETURNING *`;
            params.push(orgId);
            const result = await pool.query(query, params);

            res.json({ message: `${result.rowCount} user(s) updated successfully`, count: result.rowCount });
        } catch (err) {
            console.error('Bulk update error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/users/:id/face-enrollment', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = faceEnrollmentSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid face enrollment payload' });
        }
        const descriptor = parseDescriptor(parsed.data.descriptor);
        if (!descriptor) {
            return res.status(400).json({ error: 'Descriptor contains invalid values' });
        }
        const enrollmentImageUrl = parsed.data.enrollmentImage
            ? saveBase64Image(parsed.data.enrollmentImage, `face_${req.params.id}`)
            : null;
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                `UPDATE employees
                 SET face_descriptor = $1::jsonb,
                     face_enrolled_at = NOW(),
                     face_enrolled_by = $2,
                     face_auth_enabled = true,
                     face_enrollment_photo_url = COALESCE($4, face_enrollment_photo_url),
                     face_failed_attempts = 0,
                     face_locked_until = NULL
                 WHERE id = $3 AND organization_id = $5
                 RETURNING id, staff_id, site_id, face_enrolled_at, face_auth_enabled, face_enrollment_photo_url`,
                [JSON.stringify(descriptor), req.user.id, req.params.id, enrollmentImageUrl, orgId]
            );
            if (result.rows.length === 0) {
                return res.status(404).json({ error: 'Employee not found' });
            }
            await logFaceEvent({
                employeeId: result.rows[0].id,
                actorId: req.user.id,
                eventType: 'enrollment',
                metadata: { staffId: result.rows[0].staff_id }
            });
            await invalidateKioskSiteCandidates(result.rows[0].site_id);
            return res.json({
                success: true,
                faceEnrolled: true,
                enrollmentPhotoUrl: result.rows[0].face_enrollment_photo_url || null,
                user: result.rows[0]
            });
        } catch (err) {
            console.error('Face enrollment error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });

    router.delete('/hr/users/:id/face-enrollment', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const result = await pool.query(
                `UPDATE employees
                 SET face_descriptor = NULL,
                     face_enrolled_at = NULL,
                     face_enrolled_by = NULL,
                     face_enrollment_photo_url = NULL,
                     face_failed_attempts = 0,
                     face_locked_until = NULL
                 WHERE id = $1 AND organization_id = $2
                 RETURNING id, staff_id, site_id`,
                [req.params.id, orgId]
            );
            if (result.rows.length === 0) {
                return res.status(404).json({ error: 'Employee not found' });
            }
            await logFaceEvent({
                employeeId: result.rows[0].id,
                actorId: req.user.id,
                eventType: 'enrollment_removed',
                metadata: { staffId: result.rows[0].staff_id }
            });
            await invalidateKioskSiteCandidates(result.rows[0].site_id);
            return res.json({
                success: true,
                faceEnrolled: false
            });
        } catch (err) {
            console.error('Face enrollment remove error:', err);
            return res.status(500).json({ error: 'Database error' });
        }
    });
};
