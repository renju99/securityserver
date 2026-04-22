import { DateTime } from 'luxon';

export const APP_TIMEZONE = import.meta.env.VITE_APP_TIMEZONE || 'Asia/Dubai';

export const toUtcIso = (value?: string, isEnd = false): string => {
    if (!value) return '';
    const raw = value.trim();
    if (!raw) return '';

    const withZone = DateTime.fromISO(raw, { setZone: true });
    if (withZone.isValid && /([zZ]|[+-]\d{2}:\d{2})$/.test(raw)) {
        return withZone.toUTC().toISO() || raw;
    }

    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
        const dt = DateTime.fromISO(raw, { zone: APP_TIMEZONE });
        if (!dt.isValid) return raw;
        return (isEnd ? dt.endOf('day') : dt.startOf('day')).toUTC().toISO() || raw;
    }

    const withSeconds = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(raw) ? `${raw}:${isEnd ? '59' : '00'}` : raw;
    const local = DateTime.fromISO(withSeconds, { zone: APP_TIMEZONE });
    if (!local.isValid) return withSeconds;
    return local.toUTC().toISO() || withSeconds;
};

export const parseDateInput = (value: string): Date => {
    const dt = DateTime.fromISO(value, { zone: APP_TIMEZONE }).startOf('day');
    return dt.isValid ? dt.toJSDate() : new Date(value);
};

export const toDateInputValue = (date: Date): string => {
    const dt = DateTime.fromJSDate(date, { zone: APP_TIMEZONE });
    return dt.isValid ? dt.toFormat('yyyy-LL-dd') : '';
};

export const toLocalDateKey = (value: Date | string): string => {
    const dt = value instanceof Date
        ? DateTime.fromJSDate(value, { zone: APP_TIMEZONE })
        : DateTime.fromJSDate(new Date(value), { zone: APP_TIMEZONE });
    return dt.isValid ? dt.toFormat('yyyy-LL-dd') : '';
};
