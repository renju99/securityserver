const { DateTime } = require('luxon');
const cron = require('node-cron');
const { APP_TIMEZONE } = require('../utils/time');

/**
 * @param {object} row scheduled_report_exports row (snake_case from pg)
 * @param {Date} fromDate anchor instant (usually NOW)
 * @returns {Date} UTC Date for next_run_at
 */
function computeNextRunAt(row, fromDate = new Date()) {
    const tz =
        row.schedule_timezone ||
        row.scheduleTimezone ||
        process.env.APP_TIMEZONE ||
        APP_TIMEZONE ||
        'UTC';
    const mode = row.schedule_mode || row.scheduleMode || 'interval';
    const cronExpr = row.cron_expression || row.cronExpression;
    const dailyTime = row.daily_at_time || row.dailyAtTime;
    const runEvery = row.run_every_minutes ?? row.runEveryMinutes;

    if (mode === 'cron' && cronExpr) {
        if (!cron.validate(cronExpr)) {
            return DateTime.fromJSDate(fromDate).plus({ hours: 2 }).toJSDate();
        }
        const cronParser = require('cron-parser');
        const interval = cronParser.parseExpression(cronExpr, {
            currentDate: fromDate,
            tz,
        });
        return interval.next().toDate();
    }

    if (mode === 'daily_at' && dailyTime) {
        const m = String(dailyTime).match(/^(\d{1,2}):(\d{2})$/);
        if (!m) return DateTime.fromJSDate(fromDate).plus({ days: 1 }).toJSDate();
        const hh = Math.min(23, parseInt(m[1], 10));
        const mm = Math.min(59, parseInt(m[2], 10));
        let dt = DateTime.fromJSDate(fromDate, { zone: 'utc' }).setZone(tz);
        dt = dt.set({ hour: hh, minute: mm, second: 0, millisecond: 0 });
        if (dt.toJSDate() <= fromDate) dt = dt.plus({ days: 1 });
        return dt.toUTC().toJSDate();
    }

    const mins = Math.max(15, Math.min(10080, Number(runEvery) || 1440));
    return DateTime.fromJSDate(fromDate).plus({ minutes: mins }).toJSDate();
}

module.exports = { computeNextRunAt };
