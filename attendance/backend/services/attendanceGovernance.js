const SOURCE_MANUAL = new Set(['manual', 'manual_bulk']);
const SOURCE_OFFLINE = new Set(['offline_batch']);

const getEffectiveAttendancePolicy = async (pool, { siteId = null, shiftId = null }) => {
    const normalizedSiteId = Number.isFinite(Number(siteId)) ? Number(siteId) : null;
    const normalizedShiftId = Number.isFinite(Number(shiftId)) ? Number(shiftId) : null;
    const result = await pool.query(
        `SELECT *
         FROM attendance_policy_rules
         WHERE is_active = TRUE
           AND (site_id = $1 OR site_id IS NULL)
           AND (shift_id = $2 OR shift_id IS NULL)
         ORDER BY
            CASE WHEN site_id IS NULL THEN 1 ELSE 0 END,
            CASE WHEN shift_id IS NULL THEN 1 ELSE 0 END,
            updated_at DESC
         LIMIT 1`,
        [normalizedSiteId, normalizedShiftId]
    );
    return result.rows[0] || null;
};

const shouldRequireApproval = (policy, source) => {
    const src = String(source || '').toLowerCase();
    if (!policy) return false;
    if (SOURCE_MANUAL.has(src)) return Boolean(policy.require_approval_manual);
    if (SOURCE_OFFLINE.has(src)) return Boolean(policy.require_approval_offline);
    return false;
};

const addApprovalLog = async (pool, { attendanceId, action, actorId = null, reason = null, metadata = {} }) => {
    await pool.query(
        `INSERT INTO attendance_approval_logs (attendance_id, action, actor_id, reason, metadata)
         VALUES ($1, $2, $3, $4, $5::jsonb)`,
        [attendanceId, action, actorId, reason, JSON.stringify(metadata || {})]
    );
};

const applyCheckoutPolicy = async (pool, { attendanceId, checkInTime, checkOutTime, siteId = null, shiftId = null }) => {
    if (!attendanceId || !checkInTime || !checkOutTime) return;
    const policy = await getEffectiveAttendancePolicy(pool, { siteId, shiftId });
    if (!policy) return;
    const inTs = new Date(checkInTime);
    const outTs = new Date(checkOutTime);
    if (!Number.isFinite(inTs.getTime()) || !Number.isFinite(outTs.getTime()) || outTs <= inTs) return;

    const totalMinutes = Math.max(Math.round((outTs.getTime() - inTs.getTime()) / 60000), 0);
    const unpaidBreak = Math.max(Number(policy.unpaid_break_minutes || 0), 0);
    const paidBreak = Math.max(Number(policy.paid_break_minutes || 0), 0);
    const effectiveWorkedMinutes = Math.max(totalMinutes - unpaidBreak, 0);
    const overtimeAfter = Math.max(Number(policy.overtime_after_minutes || 480), 0);
    const overtimeMinutes = Math.max(effectiveWorkedMinutes - overtimeAfter, 0);
    const breakMinutes = Math.max(unpaidBreak + paidBreak, 0);
    const maxShiftMinutes = Number(policy.max_shift_minutes || 0);

    const contextPatch = {
        policyApplied: true,
        policyId: policy.id,
        effectiveWorkedMinutes,
        exceedsMaxShift: Number.isFinite(maxShiftMinutes) && maxShiftMinutes > 0 ? effectiveWorkedMinutes > maxShiftMinutes : false,
    };

    await pool.query(
        `UPDATE attendance
         SET overtime_minutes = $1,
             break_minutes = $2,
             work_context = COALESCE(work_context, '{}'::jsonb) || $3::jsonb
         WHERE id = $4`,
        [overtimeMinutes, breakMinutes, JSON.stringify(contextPatch), attendanceId]
    );
};

module.exports = {
    getEffectiveAttendancePolicy,
    shouldRequireApproval,
    addApprovalLog,
    applyCheckoutPolicy,
};
