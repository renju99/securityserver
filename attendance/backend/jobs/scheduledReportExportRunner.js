const cron = require('node-cron');
const { APP_TIMEZONE } = require('../utils/time');
const { executeScheduledReportExport } = require('../services/scheduledExportExecute');

async function processDueExports(pool) {
    const sel = await pool.query(
        `SELECT * FROM scheduled_report_exports
         WHERE enabled = true
           AND next_run_at <= NOW()
           AND (pause_until IS NULL OR pause_until <= NOW())
         ORDER BY id ASC
         LIMIT 10`
    );
    for (const row of sel.rows) {
        try {
            await executeScheduledReportExport(pool, row, { triggeredBy: 'cron', advanceSchedule: true });
            console.info(`[SCHEDULED_EXPORT] ok id=${row.id} name=${row.name}`);
        } catch (err) {
            const msg = err?.message || String(err);
            console.error(`[SCHEDULED_EXPORT] failed id=${row.id}:`, msg);
        }
    }
}

function createScheduledReportExportRunner({ pool }) {
    const schedule = () => {
        cron.schedule(
            '*/5 * * * *',
            () => {
                processDueExports(pool).catch((e) => console.error('[SCHEDULED_EXPORT] runner:', e.message));
            },
            { timezone: APP_TIMEZONE || 'UTC' }
        );
        console.log('[SCHEDULED_EXPORT] Runner every 5 min (Asia/Dubai default timezone).');
    };
    return { schedule, processDueExports };
}

module.exports = { createScheduledReportExportRunner, processDueExports };
