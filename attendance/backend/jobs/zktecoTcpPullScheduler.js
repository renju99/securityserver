const cron = require('node-cron');
const { pullAllZkTcpDevices } = require('../services/zktecoTcpPull');

/**
 * Optional scheduled pull of attendance from ZKTeco_TCP terminals (ZK protocol via node-zklib).
 * Complements ADMS push (`/iclock`) for sites that use client-side poll instead of cloud push.
 */
function createZkTcpPullRunner({ pool, metrics, APP_TIMEZONE }) {
    // On by default so deployments support push + pull; set ZK_TCP_PULL_ENABLED=false to disable.
    const enabled = (process.env.ZK_TCP_PULL_ENABLED || 'true').toLowerCase() !== 'false';
    const cronExpr = (process.env.ZK_TCP_PULL_CRON || '*/3 * * * *').trim();

    const run = async () => {
        await pullAllZkTcpDevices({ pool, metrics });
    };

    const schedule = () => {
        if (!enabled) {
            console.log('[ZK_TCP_PULL] Disabled (ZK_TCP_PULL_ENABLED=false).');
            return;
        }
        cron.schedule(
            cronExpr,
            () => {
                run().catch((err) => console.error('[ZK_TCP_PULL] run error:', err.message));
            },
            { timezone: APP_TIMEZONE || 'UTC' }
        );
        console.log(`[ZK_TCP_PULL] Enabled — cron "${cronExpr}" (${APP_TIMEZONE || 'UTC'}) for devices type ZKTeco_TCP with IP.`);
    };

    return { run, schedule };
}

module.exports = { createZkTcpPullRunner };
