const { DateTime } = require('luxon');

const APP_TIMEZONE = process.env.APP_TIMEZONE || 'Asia/Dubai';

const toSeconds = (timeValue) => {
    if (!timeValue) return null;
    const [h, m, s] = String(timeValue).split(':').map(Number);
    if ([h, m, s].some((n) => Number.isNaN(n))) return null;
    return (h || 0) * 3600 + (m || 0) * 60 + (s || 0);
};

const isDuringShift = (startTime, endTime, now = DateTime.now().setZone(APP_TIMEZONE)) => {
    if (!startTime || !endTime) return true;

    const start = toSeconds(startTime);
    const end = toSeconds(endTime);
    if (start === null || end === null) return true;

    const currentSeconds = now.hour * 3600 + now.minute * 60 + now.second;
    if (start <= end) {
        return currentSeconds >= start && currentSeconds <= end;
    }
    // Overnight shifts crossing midnight.
    return currentSeconds >= start || currentSeconds <= end;
};

const normalizeFilterDateToUtcIso = (value, isEnd = false) => {
    if (!value) return null;
    const raw = String(value).trim();
    if (!raw) return null;

    const withZone = DateTime.fromISO(raw, { setZone: true });
    if (withZone.isValid && !!withZone.zoneName && !withZone.zone.isUniversal) {
        return withZone.toUTC().toISO();
    }
    if (withZone.isValid && raw.match(/([zZ]|[+-]\d{2}:\d{2})$/)) {
        return withZone.toUTC().toISO();
    }

    // Date-only values from input[type="date"].
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
        const dt = DateTime.fromISO(raw, { zone: APP_TIMEZONE });
        if (!dt.isValid) return raw;
        return (isEnd ? dt.endOf('day') : dt.startOf('day')).toUTC().toISO();
    }

    // datetime-local often arrives without seconds/timezone.
    const withSeconds = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(raw) ? `${raw}:${isEnd ? '59' : '00'}` : raw;
    const local = DateTime.fromISO(withSeconds, { zone: APP_TIMEZONE });
    if (!local.isValid) return withSeconds;
    return local.toUTC().toISO();
};

module.exports = {
    APP_TIMEZONE,
    isDuringShift,
    normalizeFilterDateToUtcIso,
};
