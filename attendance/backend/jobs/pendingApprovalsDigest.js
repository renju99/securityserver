const cron = require('node-cron');
const { APP_TIMEZONE } = require('../utils/time');
const { notifyPendingApprovalsDigest } = require('../services/workforceNotifications');

function createPendingApprovalsDigestRunner({ pool }) {
    const schedule = () => {
        cron.schedule(
            process.env.NOTIFY_PENDING_DIGEST_CRON || '15 7 * * *',
            () => {
                notifyPendingApprovalsDigest(pool).catch((e) => console.error('[NOTIFY] digest:', e.message));
            },
            { timezone: APP_TIMEZONE || 'UTC' }
        );
        console.log('[NOTIFY] Pending-approvals digest scheduled.');
    };
    return { schedule };
}

module.exports = { createPendingApprovalsDigestRunner };
