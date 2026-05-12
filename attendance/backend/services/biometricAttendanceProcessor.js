const { enqueueAttendanceSync } = require('./attendanceSyncQueue');
const { hrDashboardRoom, hrSiteRoom } = require('../utils/organization');
const {
    getEffectiveAttendancePolicy,
    shouldRequireApproval,
    addApprovalLog,
    applyCheckoutPolicy,
} = require('./attendanceGovernance');

const MAX_BATCH = parseInt(process.env.BIOMETRIC_ATTENDANCE_BATCH_SIZE || '50', 10);
const RETRY_BASE_SECONDS = parseInt(process.env.BIOMETRIC_ATTENDANCE_RETRY_BASE_SECONDS || '30', 10);
const RETRY_MAX_SECONDS = parseInt(process.env.BIOMETRIC_ATTENDANCE_RETRY_MAX_SECONDS || '900', 10);
const MAX_ATTEMPTS = parseInt(process.env.BIOMETRIC_ATTENDANCE_MAX_ATTEMPTS || '20', 10);

const getRetryDelaySeconds = (attempts) => {
    const exp = Math.max(0, attempts - 1);
    return Math.min(RETRY_BASE_SECONDS * (2 ** exp), RETRY_MAX_SECONDS);
};

const normalizeInOutMode = (rawData) => {
    const mode = rawData?.inOutMode ?? rawData?.punch ?? rawData?.action;
    if (mode === undefined || mode === null || mode === '') return null;
    const text = String(mode).trim().toLowerCase();
    if (['0', 'check_in', 'in', 'i', '4'].includes(text)) return 'check_in';
    if (['1', 'check_out', 'out', 'o', '5'].includes(text)) return 'check_out';
    return null;
};

const resolveAction = async (pool, row) => {
    const explicitAction = normalizeInOutMode(row.raw_data || {});
    if (explicitAction) return explicitAction;

    const openRes = await pool.query(
        `SELECT id FROM attendance
         WHERE employee_id = $1 AND check_out_time IS NULL
           AND status NOT IN ('voided', 'rejected')
         ORDER BY check_in_time DESC LIMIT 1`,
        [row.employee_id]
    );
    return openRes.rowCount > 0 ? 'check_out' : 'check_in';
};

const markFailure = async (pool, row, message) => {
    const attempts = (row.process_attempts || 0) + 1;
    const dead = attempts >= MAX_ATTEMPTS;
    const delay = getRetryDelaySeconds(attempts);
    await pool.query(
        `UPDATE biometric_logs
         SET process_status = $2,
             process_attempts = $3,
             process_last_error = $4,
             next_retry_at = CASE WHEN $2 = 'dead_letter' THEN next_retry_at ELSE NOW() + make_interval(secs => $5::integer) END
         WHERE id = $1`,
        [row.id, dead ? 'dead_letter' : 'failed', attempts, message, delay]
    );
};

const emitAttendanceEvent = (io, action, employee, timestamp) => {
    if (!io) return;
    const eventData = {
        type: action,
        employeeId: employee.staff_id,
        firstName: employee.first_name,
        lastName: employee.last_name,
        siteId: employee.site_id,
        siteName: employee.site_name,
        timestamp,
        source: 'biometric',
    };
    const orgId = Number(employee.organization_id) > 0 ? Number(employee.organization_id) : 1;
    io.to(hrDashboardRoom(orgId)).emit('attendance_event', eventData);
    if (employee.site_id) {
        const sr = hrSiteRoom(orgId, employee.site_id);
        if (sr) io.to(sr).emit('attendance_event', eventData);
    }
};

const processBiometricLog = async ({ pool, io, row }) => {
    if (!row.employee_id) {
        throw new Error(`No employee found for biometric staff ${row.staff_id}`);
    }

    const employeeRes = await pool.query(
        `SELECT e.id, e.staff_id, e.first_name, e.last_name, e.site_id, e.shift_id, e.organization_id, s.name AS site_name
         FROM employees e
         LEFT JOIN sites s ON s.id = e.site_id
         WHERE e.id = $1`,
        [row.employee_id]
    );
    const employee = employeeRes.rows[0];
    if (!employee) {
        throw new Error(`Employee ${row.employee_id} no longer exists`);
    }

    const action = await resolveAction(pool, row);
    const eventTs = row.timestamp || new Date();

    if (action === 'check_in') {
        const openRes = await pool.query(
            `SELECT id, check_in_time, status FROM attendance
             WHERE employee_id = $1 AND check_out_time IS NULL
               AND status NOT IN ('voided', 'rejected')
             ORDER BY check_in_time DESC LIMIT 1`,
            [employee.id]
        );
        if (openRes.rowCount > 0) {
            const openAttendance = openRes.rows[0];
            await enqueueAttendanceSync(pool, {
                attendanceId: openAttendance.id,
                staffId: employee.staff_id,
                eventType: 'check_in',
                siteId: employee.site_id,
                checkInTime: openAttendance.check_in_time,
                source: 'biometric',
            });
            await pool.query(
                `UPDATE biometric_logs
                 SET process_status = 'succeeded',
                     processed_at = NOW(),
                     attendance_id = $2,
                     attendance_event_type = 'check_in',
                     process_last_error = 'Duplicate check-in ignored because an open attendance record already exists'
                 WHERE id = $1`,
                [row.id, openAttendance.id]
            );
            return;
        }

        const policy = await getEffectiveAttendancePolicy(pool, { siteId: employee.site_id, shiftId: employee.shift_id || null });
        const requireApproval = shouldRequireApproval(policy, 'biometric');
        const inserted = await pool.query(
            `INSERT INTO attendance (employee_id, check_in_time, site_id, source, status, work_context)
             VALUES ($1, $2, $3, 'biometric', $4, $5::jsonb)
             RETURNING id, check_in_time, status`,
            [
                employee.id,
                eventTs,
                employee.site_id,
                requireApproval ? 'pending' : 'approved',
                JSON.stringify({ biometricLogId: row.id, deviceId: row.device_id }),
            ]
        );
        const attendance = inserted.rows[0];
        if (attendance.status === 'pending') {
            await addApprovalLog(pool, {
                attendanceId: attendance.id,
                action: 'submitted',
                actorId: employee.id,
                metadata: { source: 'biometric', biometricLogId: row.id },
            });
        }
        await enqueueAttendanceSync(pool, {
            attendanceId: attendance.id,
            staffId: employee.staff_id,
            eventType: 'check_in',
            siteId: employee.site_id,
            checkInTime: attendance.check_in_time,
            source: 'biometric',
        });
        await pool.query(
            `UPDATE biometric_logs
             SET process_status = 'succeeded',
                 processed_at = NOW(),
                 attendance_id = $2,
                 attendance_event_type = 'check_in',
                 process_last_error = NULL
             WHERE id = $1`,
            [row.id, attendance.id]
        );
        emitAttendanceEvent(io, 'check_in', employee, eventTs);
        return;
    }

    const updated = await pool.query(
        `UPDATE attendance
         SET check_out_time = $1,
             source = COALESCE(source, 'biometric'),
             work_context = COALESCE(work_context, '{}'::jsonb) || $2::jsonb
         WHERE employee_id = $3 AND check_out_time IS NULL
           AND status NOT IN ('voided', 'rejected')
         RETURNING id, check_in_time, check_out_time, status`,
        [
            eventTs,
            JSON.stringify({ biometricCheckoutLogId: row.id, checkoutDeviceId: row.device_id }),
            employee.id,
        ]
    );
    if (updated.rowCount === 0) {
        const alreadyClosed = await pool.query(
            `SELECT id, check_in_time, check_out_time, status
             FROM attendance
             WHERE employee_id = $1
               AND (
                   check_out_time = $2
                   OR work_context->>'biometricCheckoutLogId' = $3
               )
             ORDER BY check_out_time DESC
             LIMIT 1`,
            [employee.id, eventTs, String(row.id)]
        );
        if (alreadyClosed.rowCount === 0) {
            throw new Error(`No open check-in found for biometric checkout staff ${employee.staff_id}`);
        }
        const attendance = alreadyClosed.rows[0];
        await enqueueAttendanceSync(pool, {
            attendanceId: attendance.id,
            staffId: employee.staff_id,
            eventType: 'check_out',
            siteId: employee.site_id,
            checkOutTime: attendance.check_out_time,
            source: 'biometric',
        });
        await pool.query(
            `UPDATE biometric_logs
             SET process_status = 'succeeded',
                 processed_at = NOW(),
                 attendance_id = $2,
                 attendance_event_type = 'check_out',
                 process_last_error = NULL
             WHERE id = $1`,
            [row.id, attendance.id]
        );
        return;
    }

    const attendance = updated.rows[0];
    await applyCheckoutPolicy(pool, {
        attendanceId: attendance.id,
        checkInTime: attendance.check_in_time,
        checkOutTime: attendance.check_out_time,
        siteId: employee.site_id,
        shiftId: employee.shift_id || null,
    });
    await enqueueAttendanceSync(pool, {
        attendanceId: attendance.id,
        staffId: employee.staff_id,
        eventType: 'check_out',
        siteId: employee.site_id,
        checkOutTime: attendance.check_out_time,
        source: 'biometric',
    });
    await pool.query(
        `UPDATE biometric_logs
         SET process_status = 'succeeded',
             processed_at = NOW(),
             attendance_id = $2,
             attendance_event_type = 'check_out',
             process_last_error = NULL
         WHERE id = $1`,
        [row.id, attendance.id]
    );
    emitAttendanceEvent(io, 'check_out', employee, eventTs);
};

const createBiometricAttendanceProcessor = ({ pool, io, metrics }) => {
    let running = false;

    const run = async () => {
        if (running) return;
        running = true;
        try {
            const locked = await pool.query(
                `UPDATE biometric_logs b
                 SET process_status = 'processing'
                 WHERE b.id IN (
                    SELECT id
                    FROM biometric_logs
                    WHERE process_status IN ('pending', 'failed')
                      AND next_retry_at <= NOW()
                    ORDER BY timestamp ASC, id ASC
                    LIMIT $1
                    FOR UPDATE SKIP LOCKED
                 )
                 RETURNING b.id, b.device_id, b.staff_id, b.employee_id, b.timestamp, b.raw_data, b.process_attempts`,
                [MAX_BATCH]
            );

            for (const row of locked.rows) {
                try {
                    // eslint-disable-next-line no-await-in-loop
                    await processBiometricLog({ pool, io, row });
                    metrics?.increment?.('biometric_attendance_processed_total', 1);
                } catch (err) {
                    const message = err?.message || 'Unknown biometric attendance processing error';
                    console.error(`[BIOMETRIC_ATTENDANCE] log=${row.id} failed:`, message);
                    metrics?.increment?.('biometric_attendance_failed_total', 1);
                    // eslint-disable-next-line no-await-in-loop
                    await markFailure(pool, row, message);
                }
            }
        } catch (err) {
            console.error('[BIOMETRIC_ATTENDANCE] runner failure:', err.message);
        } finally {
            running = false;
        }
    };

    const schedule = () => {
        const intervalMs = parseInt(process.env.BIOMETRIC_ATTENDANCE_INTERVAL_MS || '10000', 10);
        setInterval(() => {
            run().catch((err) => console.error('[BIOMETRIC_ATTENDANCE] schedule run error:', err.message));
        }, intervalMs);
        console.log(`[BIOMETRIC_ATTENDANCE] Scheduled processor every ${intervalMs}ms`);
    };

    return { run, schedule };
};

module.exports = {
    createBiometricAttendanceProcessor,
    normalizeInOutMode,
};
