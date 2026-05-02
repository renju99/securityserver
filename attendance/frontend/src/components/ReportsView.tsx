import React, { useEffect, useMemo, useState } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';
import FilterPanel from './FilterPanel';
import { exportToCSV } from '../utils/exportUtils';

type AttendanceRow = {
    check_in_time: string;
    check_out_time?: string | null;
    site_id?: number | null;
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

const defaultDateRange = () => {
    const end = new Date();
    const start = new Date(end.getFullYear(), end.getMonth(), 1);
    return {
        startDate: start.toISOString().slice(0, 10),
        endDate: end.toISOString().slice(0, 10)
    };
};

const ReportsView = () => {
    const { user } = useAuthStore();
    const {
        roles,
        sites,
        shifts,
        selectedRoles,
        selectedSites,
        selectedShifts,
        fetchRoles,
        fetchSites,
        fetchShifts
    } = useDataStore();
    const { showToast } = useUIStore();

    const [{ startDate, endDate }, setRange] = useState(defaultDateRange);
    const [dataSource, setDataSource] = useState<'app' | 'biometrics'>('app');
    const [department, setDepartment] = useState('');
    const [loading, setLoading] = useState(false);
    const [report, setReport] = useState<ReportPayload | null>(null);

    useEffect(() => {
        if (!user?.token) return;
        if (!roles.length) void fetchRoles(user.token);
        if (!sites.length) void fetchSites(user.token);
        if (!shifts.length) void fetchShifts(user.token);
    }, [user?.token, roles.length, sites.length, shifts.length, fetchRoles, fetchSites, fetchShifts]);

    const flatRows = useMemo(() => {
        if (!report?.employees?.length) return [];
        const rows: Record<string, string>[] = [];
        const exceptions = report.calendar?.exceptions || {};
        for (const emp of report.employees) {
            const key = String(emp.id);
            const logs = report.attendance[key] || report.attendance[emp.id as number] || [];
            for (const log of logs) {
                const inRaw = log.check_in_time;
                const inDate = inRaw ? new Date(inRaw).toISOString().slice(0, 10) : '';
                const ex = exceptions[key]?.[inDate];
                rows.push({
                    'Staff ID': emp.staff_id || '',
                    Name: `${emp.first_name || ''} ${emp.last_name || ''}`.trim(),
                    Department: emp.department_name || '',
                    Site: emp.site_name || '',
                    Role: emp.role_name || '',
                    Date: inDate,
                    'Check In': inRaw || '',
                    'Check Out': log.check_out_time ? String(log.check_out_time) : '',
                    'Day note': ex ? `${ex.code}: ${ex.label}` : ''
                });
            }
        }
        return rows;
    }, [report]);

    const runReport = async () => {
        if (!user?.token) return;
        setLoading(true);
        try {
            const qs = new URLSearchParams();
            qs.set('startDate', startDate);
            qs.set('endDate', endDate);
            if (selectedRoles.length) qs.set('roleIds', selectedRoles.join(','));
            if (selectedSites.length) qs.set('siteIds', selectedSites.map(String).join(','));
            if (selectedShifts.length) qs.set('shiftIds', selectedShifts.map(String).join(','));
            if (department.trim()) qs.set('department', department.trim());

            const path =
                dataSource === 'biometrics' ? '/api/hr/reports/biometrics' : '/api/hr/reports/attendance';
            const res = await fetch(`${path}?${qs.toString()}`, {
                headers: { Authorization: `Bearer ${user.token}` }
            });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Failed to load report');
            setReport(body as ReportPayload);
            showToast(`Loaded ${(body as ReportPayload).employees?.length || 0} staff`, 'success');
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : 'Failed to load report';
            showToast(msg, 'error');
            setReport(null);
        } finally {
            setLoading(false);
        }
    };

    const handleExport = () => {
        if (!flatRows.length) {
            showToast('Run a report with data before exporting', 'error');
            return;
        }
        exportToCSV(flatRows, `attendance_report_${dataSource}_${startDate}_${endDate}.csv`);
    };

    return (
        <div className="management-view animate-fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                <div>
                    <h2 style={{ margin: 0 }}>Attendance reports</h2>
                    <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '0.9rem' }}>
                        App data uses check-in records; biometrics uses terminal logs. Use filters below, then
                        generate.
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button className="btn-secondary" type="button" onClick={runReport} disabled={loading}>
                        {loading ? 'Loading…' : 'Generate report'}
                    </button>
                    <button className="btn-primary" type="button" onClick={handleExport} disabled={!flatRows.length}>
                        Export CSV
                    </button>
                </div>
            </div>

            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: '0.75rem',
                    marginBottom: '1rem'
                }}
            >
                <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Start date</span>
                    <input
                        type="date"
                        className="control-input"
                        value={startDate}
                        onChange={(e) => setRange((r) => ({ ...r, startDate: e.target.value }))}
                    />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    <span style={{ fontSize: '0.8rem', color: '#64748b' }}>End date</span>
                    <input
                        type="date"
                        className="control-input"
                        value={endDate}
                        onChange={(e) => setRange((r) => ({ ...r, endDate: e.target.value }))}
                    />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Data source</span>
                    <select
                        className="control-input"
                        value={dataSource}
                        onChange={(e) => setDataSource(e.target.value as 'app' | 'biometrics')}
                    >
                        <option value="app">App attendance</option>
                        <option value="biometrics">Biometrics</option>
                    </select>
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Department contains</span>
                    <input
                        type="text"
                        className="control-input"
                        placeholder="Optional filter"
                        value={department}
                        onChange={(e) => setDepartment(e.target.value)}
                    />
                </label>
            </div>

            <FilterPanel />

            <div className="mgmt-table-container" style={{ marginTop: '1rem' }}>
                <table className="mgmt-table">
                    <thead>
                        <tr>
                            <th>Staff ID</th>
                            <th>Name</th>
                            <th>Site</th>
                            <th>Date</th>
                            <th>Check in</th>
                            <th>Check out</th>
                            <th>Day note</th>
                        </tr>
                    </thead>
                    <tbody>
                        {flatRows.slice(0, 100).map((row, i) => (
                            <tr key={`${row['Staff ID']}-${row.Date}-${i}`}>
                                <td>{row['Staff ID']}</td>
                                <td>{row.Name}</td>
                                <td>{row.Site}</td>
                                <td>{row.Date}</td>
                                <td>{row['Check In']}</td>
                                <td>{row['Check Out']}</td>
                                <td>{row['Day note']}</td>
                            </tr>
                        ))}
                        {flatRows.length === 0 && (
                            <tr>
                                <td colSpan={7} style={{ textAlign: 'center', color: '#94a3b8' }}>
                                    {report ? 'No rows in this range for the selected filters.' : 'Generate a report to preview rows here.'}
                                </td>
                            </tr>
                        )}
                        {flatRows.length > 100 && (
                            <tr>
                                <td colSpan={7} style={{ textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
                                    Showing first 100 of {flatRows.length} rows. Export CSV for the full set.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default ReportsView;
