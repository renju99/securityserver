const { sendMail } = require('./emailDispatch');
const { sendSms } = require('./smsTwilio');

const digestEnabled = () => (process.env.NOTIFY_PENDING_DIGEST_ENABLED || 'true').toLowerCase() !== 'false';

async function loadActor(pool, actorEmployeeId) {
    if (!actorEmployeeId) return { label: 'HR' };
    const r = await pool.query(
        `SELECT staff_id, first_name, last_name FROM employees WHERE id = $1 LIMIT 1`,
        [actorEmployeeId]
    );
    const row = r.rows[0];
    if (!row) return { label: 'HR' };
    const name = [row.first_name, row.last_name].filter(Boolean).join(' ').trim();
    return { label: name || row.staff_id || 'HR', staffId: row.staff_id };
}

/**
 * @param {import('pg').Pool} pool
 * @param {{ attendanceId: number; employeeId: number; decision: 'approved'|'rejected'; reason?: string | null; actorEmployeeId: number }} args
 */
async function notifyAttendanceDecision(pool, args) {
    const { attendanceId, employeeId, decision, reason, actorEmployeeId } = args;
    const notifyEmail = (process.env.NOTIFY_ATTENDANCE_EMAIL || 'true').toLowerCase() !== 'false';
    const notifySms = (process.env.NOTIFY_ATTENDANCE_SMS || 'false').toLowerCase() === 'true';

    const empRes = await pool.query(
        `SELECT staff_id, first_name, last_name, email, phone_e164, organization_id FROM employees WHERE id = $1 LIMIT 1`,
        [employeeId]
    );
    const emp = empRes.rows[0];
    if (!emp) return;

    const attRes = await pool.query(
        `SELECT check_in_time, check_out_time, site_id, s.name AS site_name
         FROM attendance a LEFT JOIN sites s ON s.id = a.site_id WHERE a.id = $1`,
        [attendanceId]
    );
    const att = attRes.rows[0] || {};
    const actor = await loadActor(pool, actorEmployeeId);
    const when = att.check_in_time ? new Date(att.check_in_time).toISOString() : '';
    const site = att.site_name || '';
    const subject = `Attendance ${decision}: ${emp.staff_id}`;
    const text = [
        `Hello ${emp.first_name || emp.staff_id},`,
        ``,
        `Your attendance record #${attendanceId} was ${decision} by ${actor.label}.`,
        when ? `Check-in (UTC): ${when}` : '',
        site ? `Site: ${site}` : '',
        decision === 'rejected' && reason ? `Reason: ${reason}` : '',
        ``,
        `— Workforce 360`,
    ]
        .filter(Boolean)
        .join('\n');

    if (notifyEmail && emp.email) {
        try {
            await sendMail({ to: emp.email, subject, text }, { pool, organizationId: emp.organization_id });
        } catch (e) {
            console.error('[NOTIFY] attendance email failed:', e.message);
        }
    }
    if (notifySms && emp.phone_e164) {
        try {
            await sendSms(emp.phone_e164, `${subject}. ${text.replace(/\n+/g, ' ').slice(0, 300)}`);
        } catch (e) {
            console.error('[NOTIFY] attendance SMS failed:', e.message);
        }
    }
}

/**
 * Morning digest to HR admins: pending attendance approvals count per org.
 * @param {import('pg').Pool} pool
 */
async function notifyPendingApprovalsDigest(pool) {
    if (!digestEnabled()) return;
    const pending = await pool.query(
        `SELECT e.organization_id, COUNT(*)::int AS c
         FROM attendance a
         JOIN employees e ON e.id = a.employee_id
         WHERE a.status = 'pending'
         GROUP BY e.organization_id
         HAVING COUNT(*) > 0`
    );
    for (const row of pending.rows) {
        const orgId = row.organization_id;
        const cnt = row.c;
        const hrRes = await pool.query(
            `SELECT DISTINCT e.email
             FROM employees e
             JOIN roles r ON r.id = e.role_id
             WHERE e.organization_id = $1
               AND r.name IN ('HR Admin', 'Site Supervisor')
               AND e.email IS NOT NULL
               AND TRIM(e.email) <> ''`,
            [orgId]
        );
        const emails = hrRes.rows.map((r) => r.email).filter(Boolean);
        if (!emails.length) continue;
        const subject = `[Workforce] ${cnt} attendance record(s) awaiting approval`;
        const text = `There are ${cnt} attendance row(s) in pending status for organization #${orgId}. Open the HR dashboard to review.`;
        try {
            await sendMail({ to: emails, subject, text }, { pool, organizationId: orgId });
        } catch (e) {
            console.error('[NOTIFY] digest email failed:', e.message);
        }
        const extra = process.env.NOTIFY_DIGEST_SMS_TO;
        if (extra) {
            for (const num of extra.split(',').map((s) => s.trim()).filter(Boolean)) {
                try {
                    await sendSms(num, `${subject} — ${text}`);
                } catch (_e) {
                    /* ignore */
                }
            }
        }
    }
}

module.exports = {
    notifyAttendanceDecision,
    notifyPendingApprovalsDigest,
};
