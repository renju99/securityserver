const enqueueAttendanceSync = async (pool, event) => {
    if (!event?.attendanceId || !event?.staffId || !event?.eventType) return;
    const payload = {
        siteId: event.siteId || null,
        checkInTime: event.checkInTime || null,
        checkOutTime: event.checkOutTime || null,
        source: event.source || 'attendance-app',
    };
    try {
        const attendanceRes = await pool.query(
            `SELECT status
             FROM attendance
             WHERE id = $1`,
            [event.attendanceId]
        );
        const attendanceStatus = attendanceRes.rows[0]?.status || 'approved';
        if (attendanceStatus !== 'approved') {
            return;
        }
        await pool.query(
            `INSERT INTO attendance_sync_outbox (attendance_id, staff_id, event_type, payload, status, next_retry_at, updated_at)
             VALUES ($1, $2, $3, $4::jsonb, 'pending', NOW(), NOW())`,
            [event.attendanceId, event.staffId, event.eventType, JSON.stringify(payload)]
        );
    } catch (err) {
        console.error('[ODOO_SYNC][QUEUE] enqueue failed:', err.message);
    }
};

module.exports = {
    enqueueAttendanceSync,
};
