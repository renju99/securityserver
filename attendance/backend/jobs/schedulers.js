const cron = require('node-cron');
const { enqueueAttendanceSync } = require('../services/attendanceSyncQueue');
const { hrDashboardRoom } = require('../utils/organization');

const createAutoCheckoutRunner = ({ pool, io, metrics, APP_TIMEZONE }) => {
    const AUTO_CHECKOUT_GRACE_HOURS = parseInt(process.env.AUTO_CHECKOUT_GRACE_HOURS || '2');
    const AUTO_CHECKOUT_NO_SHIFT_HOURS = parseInt(process.env.AUTO_CHECKOUT_NO_SHIFT_HOURS || '10');

    const runAutoCheckout = async () => {
        const started = Date.now();
        try {
            const openRecords = await pool.query(`
                SELECT
                    a.id AS attendance_id,
                    a.check_in_time,
                    a.employee_id,
                    a.site_id,
                    e.staff_id,
                    e.first_name,
                    e.last_name,
                    e.organization_id,
                    sh.name AS shift_name,
                    sh.end_time AS shift_end_time
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                LEFT JOIN shifts sh ON e.shift_id = sh.id
                WHERE a.check_out_time IS NULL
                  AND a.status NOT IN ('voided', 'rejected')
            `);

            if (openRecords.rows.length === 0) return;

            const now = new Date();
            const toClose = [];

            for (const row of openRecords.rows) {
                let shouldClose = false;
                let reason = '';
                if (row.shift_end_time) {
                    const [endHour, endMin] = row.shift_end_time.split(':').map(Number);
                    const checkInDate = new Date(row.check_in_time);
                    const shiftEnd = new Date(checkInDate);
                    shiftEnd.setHours(endHour, endMin, 0, 0);
                    if (shiftEnd <= checkInDate) shiftEnd.setDate(shiftEnd.getDate() + 1);
                    const cutoff = new Date(shiftEnd.getTime() + AUTO_CHECKOUT_GRACE_HOURS * 60 * 60 * 1000);
                    if (now >= cutoff) {
                        shouldClose = true;
                        reason = `Auto closed: shift ended at ${row.shift_end_time} (${row.shift_name}), grace period of ${AUTO_CHECKOUT_GRACE_HOURS}h exceeded.`;
                    }
                } else {
                    const checkInAge = (now.getTime() - new Date(row.check_in_time).getTime()) / 3600000;
                    if (checkInAge >= AUTO_CHECKOUT_NO_SHIFT_HOURS) {
                        shouldClose = true;
                        reason = `Auto closed: no shift assigned and check-in was ${checkInAge.toFixed(1)}h ago (limit: ${AUTO_CHECKOUT_NO_SHIFT_HOURS}h).`;
                    }
                }
                if (shouldClose) toClose.push({ ...row, reason });
            }

            if (toClose.length === 0) return;
            console.log(`[AUTO-CHECKOUT] Closing ${toClose.length} open record(s)...`);

            for (const record of toClose) {
                const updateRes = await pool.query(
                    `UPDATE attendance
                     SET check_out_time = NOW(), auto_closed = true, notes = $1
                     WHERE id = $2 AND check_out_time IS NULL
                       AND status NOT IN ('voided', 'rejected')`,
                    [record.reason, record.attendance_id]
                );
                if (updateRes.rowCount > 0) {
                    await enqueueAttendanceSync(pool, {
                        attendanceId: record.attendance_id,
                        staffId: record.staff_id,
                        eventType: 'check_out',
                        siteId: record.site_id,
                        source: 'auto_checkout',
                    });
                }
                io.to(hrDashboardRoom(record.organization_id)).emit('auto_checkout', {
                    attendanceId: record.attendance_id,
                    staffId: record.staff_id,
                    name: [record.first_name, record.last_name].filter(Boolean).join(' '),
                    siteId: record.site_id,
                    checkInTime: record.check_in_time,
                    checkOutTime: new Date().toISOString(),
                    reason: record.reason
                });
            }

            metrics.increment('auto_checkout_total', toClose.length);
            const elapsed = ((Date.now() - started) / 1000).toFixed(2);
            console.log(`[AUTO-CHECKOUT] Done. Closed ${toClose.length} record(s) in ${elapsed}s.`);
        } catch (err) {
            console.error('[AUTO-CHECKOUT] Error:', err.message);
        }
    };

    const schedule = () => {
        cron.schedule('*/30 * * * *', runAutoCheckout, { timezone: APP_TIMEZONE });
        console.log(`[AUTO-CHECKOUT] Scheduled every 30 min. Grace: ${AUTO_CHECKOUT_GRACE_HOURS}h after shift end. No-shift limit: ${AUTO_CHECKOUT_NO_SHIFT_HOURS}h.`);
    };

    return { runAutoCheckout, schedule };
};

const setupMaintenanceSchedulers = ({ pool, APP_TIMEZONE, DATA_RETENTION_DAYS }) => {
    const ensureLiveLogPartitions = async () => {
        try {
            await pool.query(`
                DO $$
                DECLARE
                    i integer;
                    month_start timestamptz;
                    month_end timestamptz;
                    part_name text;
                BEGIN
                    FOR i IN -1..6 LOOP
                        month_start := date_trunc('month', now()) + (i || ' month')::interval;
                        month_end := month_start + interval '1 month';
                        part_name := format('live_logs_p_%s', to_char(month_start, 'YYYY_MM'));
                        EXECUTE format(
                            'CREATE TABLE IF NOT EXISTS %I PARTITION OF live_logs FOR VALUES FROM (%L) TO (%L)',
                            part_name,
                            month_start,
                            month_end
                        );
                    END LOOP;
                END $$;
            `);
            console.log('[PARTITIONS] live_logs partitions ensured for current rolling window.');
        } catch (err) {
            console.error('[PARTITIONS] live_logs partition maintenance error:', err.message);
        }
    };

    ensureLiveLogPartitions();

    cron.schedule('15 1 1 * *', ensureLiveLogPartitions, { timezone: APP_TIMEZONE });

    cron.schedule('0 2 * * *', async () => {
        const started = Date.now();
        console.log(`[CLEANUP] Starting daily data cleanup (retention: ${DATA_RETENTION_DAYS} days)...`);
        try {
            const logsResult = await pool.query(
                `DELETE FROM live_logs WHERE timestamp < NOW() - INTERVAL '${DATA_RETENTION_DAYS} days'`
            );
            console.log(`[CLEANUP] live_logs: deleted ${logsResult.rowCount} rows.`);
            const alertsResult = await pool.query(
                `DELETE FROM geo_fence_alerts
                 WHERE created_at < NOW() - INTERVAL '${DATA_RETENTION_DAYS} days'
                   AND status = 'resolved'`
            );
            console.log(`[CLEANUP] geo_fence_alerts (resolved): deleted ${alertsResult.rowCount} rows.`);
            const elapsed = ((Date.now() - started) / 1000).toFixed(2);
            console.log(`[CLEANUP] Daily cleanup completed in ${elapsed}s.`);
        } catch (err) {
            console.error('[CLEANUP] Daily cleanup error:', err.message);
        }
    }, { timezone: APP_TIMEZONE });

    cron.schedule('0 3 * * 0', async () => {
        console.log('[CLEANUP] Starting weekly VACUUM ANALYZE...');
        try {
            await pool.query('VACUUM ANALYZE live_logs');
            await pool.query('VACUUM ANALYZE geo_fence_alerts');
            console.log('[CLEANUP] VACUUM ANALYZE completed.');
        } catch (err) {
            console.error('[CLEANUP] VACUUM error:', err.message);
        }
    }, { timezone: APP_TIMEZONE });

    console.log(`[CLEANUP] Scheduled: daily pruning at 02:00, weekly VACUUM at Sunday 03:00 (${APP_TIMEZONE}). Retention: ${DATA_RETENTION_DAYS} days.`);
};

module.exports = {
    createAutoCheckoutRunner,
    setupMaintenanceSchedulers,
};
