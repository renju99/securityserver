const { DateTime } = require('luxon');
const { APP_TIMEZONE } = require('../utils/time');

/**
 * @param {string} preset
 * @returns {{ startDate: string; endDate: string }} ISO yyyy-LL-dd in APP_TIMEZONE
 */
function resolveDateRangePreset(preset) {
    const now = DateTime.now().setZone(APP_TIMEZONE);
    let start;
    let end = now.endOf('day');
    switch (String(preset || 'last_30_days')) {
        case 'last_7_days':
            start = now.minus({ days: 7 }).startOf('day');
            break;
        case 'last_calendar_month':
            start = now.minus({ months: 1 }).startOf('month');
            end = now.minus({ months: 1 }).endOf('month');
            break;
        case 'month_to_date':
            start = now.startOf('month');
            end = now.endOf('day');
            break;
        case 'last_30_days':
        default:
            start = now.minus({ days: 30 }).startOf('day');
            end = now.endOf('day');
    }
    return { startDate: start.toISODate(), endDate: end.toISODate() };
}

module.exports = { resolveDateRangePreset };
