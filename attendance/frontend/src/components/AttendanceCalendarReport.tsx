import React, { useMemo, useState } from 'react';

type AttendanceRow = {
    check_in_time: string;
    check_out_time?: string | null;
};

type CalendarException = { code: string; kind?: string; label: string };

type ReportEmployee = {
    id: number | string;
    staff_id: string;
    first_name?: string;
    last_name?: string;
    department_name?: string;
    site_name?: string;
    role_name?: string;
};

type ReportPayload = {
    employees: ReportEmployee[];
    attendance: Record<string, AttendanceRow[]>;
    calendar: { exceptions: Record<string, Record<string, CalendarException>> };
};

function enumerateDays(startIso: string, endIso: string): string[] {
    const out: string[] = [];
    const start = new Date(`${startIso}T12:00:00`);
    const end = new Date(`${endIso}T12:00:00`);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return out;
    const cur = new Date(start);
    while (cur <= end) {
        out.push(cur.toISOString().slice(0, 10));
        cur.setDate(cur.getDate() + 1);
    }
    return out;
}

function logDayKey(iso: string): string {
    return new Date(iso).toISOString().slice(0, 10);
}

function formatHm(iso: string): string {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

const MAX_CALENDAR_DAYS = 45;

type Props = {
    report: ReportPayload | null;
    startDate: string;
    endDate: string;
    staffSearch: string;
};

const AttendanceCalendarReport: React.FC<Props> = ({ report, startDate, endDate, staffSearch }) => {
    const [hover, setHover] = useState<{ key: string; text: string } | null>(null);

    const dayKeys = useMemo(() => enumerateDays(startDate, endDate), [startDate, endDate]);
    const tooManyDays = dayKeys.length > MAX_CALENDAR_DAYS;

    const filteredEmployees = useMemo(() => {
        const list = report?.employees || [];
        const q = staffSearch.trim().toLowerCase();
        if (!q) return list;
        return list.filter((e) => {
            const blob = [e.staff_id, e.first_name, e.last_name, e.department_name, e.site_name, e.role_name]
                .filter(Boolean)
                .join(' ')
                .toLowerCase();
            return blob.includes(q);
        });
    }, [report?.employees, staffSearch]);

    const cellMap = useMemo(() => {
        if (!report || tooManyDays) return new Map<string, { logs: AttendanceRow[]; ex?: CalendarException }>();
        const exceptions = report.calendar?.exceptions || {};
        const map = new Map<string, { logs: AttendanceRow[]; ex?: CalendarException }>();
        for (const emp of filteredEmployees) {
            const key = String(emp.id);
            const logs = report.attendance[key] || report.attendance[emp.id as number] || [];
            for (const day of dayKeys) {
                const dayLogs = logs.filter((l) => l.check_in_time && logDayKey(l.check_in_time) === day);
                const ex = exceptions[key]?.[day];
                map.set(`${key}|${day}`, { logs: dayLogs, ex });
            }
        }
        return map;
    }, [report, filteredEmployees, dayKeys, tooManyDays]);

    if (!report) {
        return (
            <div style={{ padding: '1rem', color: '#94a3b8', fontSize: '0.9rem' }}>
                Generate a report to see the calendar matrix.
            </div>
        );
    }

    if (tooManyDays) {
        return (
            <div style={{ padding: '1rem', background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: '8px', color: '#9a3412', fontSize: '0.9rem' }}>
                Calendar view supports at most <strong>{MAX_CALENDAR_DAYS}</strong> consecutive days (currently {dayKeys.length}).
                Narrow the start and end dates, then generate again.
            </div>
        );
    }

    const legend = (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '0.75rem', fontSize: '0.75rem', color: '#475569' }}>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#bbf7d0', borderRadius: 2, marginRight: 4 }} />Closed day</span>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#fef08a', borderRadius: 2, marginRight: 4 }} />Open / no checkout</span>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#ddd6fe', borderRadius: 2, marginRight: 4 }} />Holiday</span>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#bfdbfe', borderRadius: 2, marginRight: 4 }} />Approved leave</span>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#f1f5f9', border: '1px solid #e2e8f0', borderRadius: 2, marginRight: 4 }} />No punch</span>
        </div>
    );

    return (
        <div style={{ marginTop: '1rem' }}>
            {legend}
            {hover && (
                <div style={{ marginBottom: '0.5rem', fontSize: '0.78rem', color: '#334155', padding: '0.35rem 0.5rem', background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0' }}>
                    {hover.text}
                </div>
            )}
            <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px', background: '#fff' }}>
                <table style={{ borderCollapse: 'collapse', fontSize: '0.68rem', minWidth: '100%' }}>
                    <thead>
                        <tr>
                            <th style={{ position: 'sticky', left: 0, zIndex: 2, background: '#f8fafc', padding: '6px 8px', textAlign: 'left', borderBottom: '1px solid #e2e8f0', borderRight: '1px solid #e2e8f0', minWidth: 76 }}>Staff</th>
                            <th style={{ position: 'sticky', left: 76, zIndex: 2, background: '#f8fafc', padding: '6px 8px', textAlign: 'left', borderBottom: '1px solid #e2e8f0', borderRight: '1px solid #e2e8f0', minWidth: 128 }}>Name</th>
                            <th style={{ position: 'sticky', left: 204, zIndex: 2, background: '#f8fafc', padding: '6px 8px', textAlign: 'left', borderBottom: '1px solid #e2e8f0', borderRight: '2px solid #cbd5e1', minWidth: 96 }}>Site</th>
                            {dayKeys.map((d) => {
                                const wd = new Date(`${d}T12:00:00`).getDay();
                                const wk = wd === 0 || wd === 6;
                                return (
                                    <th
                                        key={d}
                                        style={{
                                            padding: '4px 2px',
                                            borderBottom: '1px solid #e2e8f0',
                                            borderRight: '1px solid #f1f5f9',
                                            textAlign: 'center',
                                            minWidth: 26,
                                            background: wk ? '#fafafa' : '#f8fafc',
                                            color: wk ? '#94a3b8' : '#64748b',
                                            fontWeight: 600,
                                            writingMode: 'vertical-rl',
                                            transform: 'rotate(180deg)',
                                            height: 72,
                                        }}
                                    >
                                        {d.slice(5)}
                                    </th>
                                );
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {filteredEmployees.map((emp) => {
                            const key = String(emp.id);
                            const name = `${emp.first_name || ''} ${emp.last_name || ''}`.trim() || '—';
                            return (
                                <tr key={key}>
                                    <td style={{ position: 'sticky', left: 0, zIndex: 1, background: '#fff', padding: '4px 8px', borderRight: '1px solid #f1f5f9', borderBottom: '1px solid #f1f5f9', whiteSpace: 'nowrap', fontWeight: 600, minWidth: 76 }}>{emp.staff_id}</td>
                                    <td style={{ position: 'sticky', left: 76, zIndex: 1, background: '#fff', padding: '4px 8px', borderRight: '1px solid #f1f5f9', borderBottom: '1px solid #f1f5f9', maxWidth: 128, overflow: 'hidden', textOverflow: 'ellipsis' }}>{name}</td>
                                    <td style={{ position: 'sticky', left: 204, zIndex: 1, background: '#fff', padding: '4px 8px', borderRight: '2px solid #e2e8f0', borderBottom: '1px solid #f1f5f9', color: '#64748b', maxWidth: 96, overflow: 'hidden', textOverflow: 'ellipsis' }}>{emp.site_name || '—'}</td>
                                    {dayKeys.map((day) => {
                                        const cell = cellMap.get(`${key}|${day}`) || { logs: [], ex: undefined };
                                        const { logs, ex } = cell;
                                        const has = logs.length > 0;
                                        const open = has && logs.some((l) => !l.check_out_time);
                                        const closed = has && !open;
                                        let bg = '#f8fafc';
                                        if (ex?.kind === 'holiday') bg = '#ede9fe';
                                        else if (ex?.kind === 'leave') bg = '#dbeafe';
                                        else if (closed) bg = '#dcfce7';
                                        else if (open) bg = '#fef9c3';
                                        const wd = new Date(`${day}T12:00:00`).getDay();
                                        const wk = wd === 0 || wd === 6;
                                        const lines: string[] = [`${emp.staff_id} · ${day}`];
                                        if (ex) lines.push(`${ex.code}: ${ex.label}`);
                                        logs.forEach((l, i) => {
                                            lines.push(`Punch ${i + 1}: in ${formatHm(l.check_in_time)}${l.check_out_time ? ` → out ${formatHm(String(l.check_out_time))}` : ' (open)'}`);
                                        });
                                        if (!has && !ex) lines.push('No attendance record');
                                        const tip = lines.join('\n');
                                        return (
                                            <td
                                                key={`${key}-${day}`}
                                                title={tip}
                                                onMouseEnter={() => setHover({ key: `${key}|${day}`, text: tip.replace(/\n/g, ' · ') })}
                                                onMouseLeave={() => setHover((h) => (h?.key === `${key}|${day}` ? null : h))}
                                                style={{
                                                    textAlign: 'center',
                                                    padding: 2,
                                                    borderRight: '1px solid #f1f5f9',
                                                    borderBottom: '1px solid #f1f5f9',
                                                    background: wk && !has && !ex ? '#fafafa' : bg,
                                                    cursor: 'default',
                                                    verticalAlign: 'middle',
                                                }}
                                            >
                                                {ex && (
                                                    <span style={{ fontSize: '0.62rem', fontWeight: 700, color: '#5b21b6' }}>{ex.code}</span>
                                                )}
                                                {!ex && has && (
                                                    <span style={{ fontSize: '0.62rem', fontWeight: 700, color: closed ? '#166534' : '#a16207' }}>
                                                        {logs.length > 1 ? `${logs.length}×` : '✓'}
                                                    </span>
                                                )}
                                                {!ex && !has && <span style={{ color: '#cbd5e1' }}>·</span>}
                                            </td>
                                        );
                                    })}
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
            {filteredEmployees.length === 0 && (
                <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '0.5rem' }}>No staff match the name / ID filter.</p>
            )}
        </div>
    );
};

export default AttendanceCalendarReport;
