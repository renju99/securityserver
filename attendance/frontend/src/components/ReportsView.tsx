import React, { useEffect, useMemo, useState } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';
import FilterPanel from './FilterPanel';
import AttendanceCalendarReport from './AttendanceCalendarReport';
import { exportToCSV, exportToXlsx, exportToFixedWidthPayroll } from '../utils/exportUtils';

type ReportsViewProps = {
    /** Opens the dedicated Report schedules tab (HR Admin / Payroll / Finance). */
    onOpenReportSchedules?: () => void;
};

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

const thisMonthRange = () => {
    const end = new Date();
    const start = new Date(end.getFullYear(), end.getMonth(), 1);
    return {
        startDate: start.toISOString().slice(0, 10),
        endDate: end.toISOString().slice(0, 10)
    };
};

const lastMonthRange = () => {
    const ref = new Date();
    const start = new Date(ref.getFullYear(), ref.getMonth() - 1, 1);
    const end = new Date(ref.getFullYear(), ref.getMonth(), 0);
    return {
        startDate: start.toISOString().slice(0, 10),
        endDate: end.toISOString().slice(0, 10)
    };
};

const REPORT_PACKS_KEY = 'hrReportFilterPacksV1';

type SavedReportPack = {
    id: string;
    name: string;
    startDate: string;
    endDate: string;
    dataSource: 'app' | 'biometrics';
    department: string;
    roleIds: number[];
    siteIds: (number | string)[];
    shiftIds: (number | string)[];
};

const loadPacks = (): SavedReportPack[] => {
    try {
        const raw = localStorage.getItem(REPORT_PACKS_KEY);
        const p = raw ? JSON.parse(raw) : [];
        return Array.isArray(p) ? p : [];
    } catch {
        return [];
    }
};

const ReportsView = ({ onOpenReportSchedules }: ReportsViewProps) => {
    const { user } = useAuthStore();
    const {
        roles,
        sites,
        shifts,
        selectedRoles,
        selectedSites,
        selectedShifts,
        setSelectedRoles,
        setSelectedSites,
        setSelectedShifts,
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
    const [savedPacks, setSavedPacks] = useState<SavedReportPack[]>(() => loadPacks());
    const [packName, setPackName] = useState('');
    const [previewOpen, setPreviewOpen] = useState(false);
    const [reportViewMode, setReportViewMode] = useState<'list' | 'calendar'>('list');
    const [staffSearch, setStaffSearch] = useState('');

    const persistPacks = (packs: SavedReportPack[]) => {
        try {
            localStorage.setItem(REPORT_PACKS_KEY, JSON.stringify(packs.slice(0, 40)));
        } catch {
            /* ignore */
        }
        setSavedPacks(packs);
    };

    const saveCurrentPack = () => {
        const name = packName.trim();
        if (!name) {
            showToast('Enter a name for this report pack', 'warning');
            return;
        }
        const id = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `p_${Date.now()}`;
        const next: SavedReportPack = {
            id,
            name,
            startDate,
            endDate,
            dataSource,
            department,
            roleIds: [...selectedRoles],
            siteIds: [...selectedSites],
            shiftIds: [...selectedShifts],
        };
        persistPacks([next, ...savedPacks.filter((p) => p.name !== name)].slice(0, 40));
        setPackName('');
        showToast('Report pack saved on this browser', 'success');
    };

    const applyPack = (p: SavedReportPack) => {
        setRange({ startDate: p.startDate, endDate: p.endDate });
        setDataSource(p.dataSource);
        setDepartment(p.department || '');
        setSelectedRoles(p.roleIds || []);
        setSelectedSites(p.siteIds || []);
        setSelectedShifts(p.shiftIds || []);
        showToast(`Applied pack “${p.name}” — click Generate report`, 'info');
    };

    const deletePack = (id: string) => {
        persistPacks(savedPacks.filter((p) => p.id !== id));
        showToast('Pack removed', 'info');
    };

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
                dataSource === 'biometrics' ? '/hr/reports/biometrics' : '/hr/reports/attendance';
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

    const handleExportXlsx = async () => {
        if (!flatRows.length) {
            showToast('Run a report with data before exporting', 'error');
            return;
        }
        try {
            await exportToXlsx(
                flatRows as Record<string, unknown>[],
                `attendance_report_${dataSource}_${startDate}_${endDate}.xlsx`
            );
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Excel export failed', 'error');
        }
    };

    const handleExportFixed = () => {
        if (!flatRows.length) {
            showToast('Run a report with data before exporting', 'error');
            return;
        }
        exportToFixedWidthPayroll(flatRows, `attendance_report_${dataSource}_${startDate}_${endDate}.txt`);
    };

    const isFinancePortal = user?.role === 'Payroll' || user?.role === 'Finance';
    const canManageScheduledExports = user?.role === 'HR Admin' || user?.role === 'Payroll' || user?.role === 'Finance';
    const previewRows = flatRows.slice(0, 20);

    return (
        <div className="management-view animate-fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                <div>
                    <h2 style={{ margin: 0 }}>Attendance reports</h2>
                    <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '0.9rem' }}>
                        App data uses check-in records; biometrics uses terminal logs. Use filters below, then
                        generate. After loading, switch between list and calendar (≤45 days) for the same filters.
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button className="hr-btn secondary sm" type="button" onClick={runReport} disabled={loading}>
                        {loading ? 'Loading…' : 'Generate report'}
                    </button>
                    <button className="hr-btn secondary sm" type="button" onClick={() => setPreviewOpen(true)} disabled={!flatRows.length}>
                        Preview (20 rows)
                    </button>
                    <button className="hr-btn primary sm" type="button" onClick={handleExport} disabled={!flatRows.length}>
                        Export CSV
                    </button>
                    <button className="hr-btn secondary sm" type="button" onClick={handleExportXlsx} disabled={!flatRows.length}>
                        Export Excel
                    </button>
                    <button className="hr-btn secondary sm" type="button" onClick={handleExportFixed} disabled={!flatRows.length}>
                        Export fixed-width
                    </button>
                </div>
            </div>

            <div style={{
                marginBottom: '1rem',
                padding: '0.85rem 1rem',
                borderRadius: '10px',
                border: '1px solid #e2e8f0',
                background: '#fafafa',
            }}>
                <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#334155', marginBottom: '0.5rem' }}>Saved report packs (this browser)</div>
                <p style={{ margin: '0 0 0.5rem', fontSize: '0.78rem', color: '#64748b' }}>
                    Stores date range, source, department, and filter panel selections. Use for recurring payroll or site exports.
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <input
                        className="control-input"
                        style={{ maxWidth: '220px', fontSize: '0.85rem' }}
                        placeholder="Pack name e.g. March payroll"
                        value={packName}
                        onChange={(e) => setPackName(e.target.value)}
                    />
                    <button type="button" className="hr-btn secondary sm" onClick={saveCurrentPack}>Save current filters</button>
                </div>
                {savedPacks.length === 0 ? (
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>No packs yet.</span>
                ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                        {savedPacks.map((p) => (
                            <span key={p.id} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', background: '#fff', border: '1px solid #e2e8f0', borderRadius: '999px', padding: '0.15rem 0.5rem', fontSize: '0.78rem' }}>
                                <button type="button" className="hr-btn secondary sm" style={{ border: 'none', padding: '0.1rem 0.35rem' }} onClick={() => applyPack(p)}>{p.name}</button>
                                <button type="button" aria-label={`Delete ${p.name}`} onClick={() => deletePack(p.id)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#94a3b8', fontSize: '0.9rem' }}>×</button>
                            </span>
                        ))}
                    </div>
                )}
            </div>

            {previewOpen && (
                <div style={{
                    position: 'fixed', inset: 0, zIndex: 2000, background: 'rgba(15,23,42,0.45)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem',
                }}>
                    <div style={{ background: '#fff', borderRadius: '12px', maxWidth: '960px', width: '100%', maxHeight: '85vh', overflow: 'auto', padding: '1rem', boxShadow: '0 20px 50px rgba(0,0,0,0.2)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                            <strong>Export preview (first 20 rows)</strong>
                            <button type="button" className="hr-btn secondary sm" onClick={() => setPreviewOpen(false)}>Close</button>
                        </div>
                        <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: 0 }}>Total rows: {flatRows.length}. Use CSV, Excel, or fixed-width from the toolbar for the full set.</p>
                        <table className="mgmt-table" style={{ fontSize: '0.78rem' }}>
                            <thead>
                                <tr>
                                    {['Staff ID', 'Name', 'Site', 'Date', 'Check In', 'Check Out', 'Day note'].map((h) => (
                                        <th key={h}>{h}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {previewRows.map((row, i) => (
                                    <tr key={i}>
                                        <td>{row['Staff ID']}</td>
                                        <td>{row.Name}</td>
                                        <td>{row.Site}</td>
                                        <td>{row.Date}</td>
                                        <td>{row['Check In']}</td>
                                        <td>{row['Check Out']}</td>
                                        <td>{row['Day note']}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                            <button type="button" className="hr-btn secondary" onClick={() => setPreviewOpen(false)}>Close</button>
                            <button type="button" className="hr-btn primary" onClick={() => { handleExport(); setPreviewOpen(false); }} disabled={!flatRows.length}>Download CSV</button>
                        </div>
                    </div>
                </div>
            )}

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

            <div
                style={{
                    marginTop: '1rem',
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    gap: '0.75rem',
                    justifyContent: 'space-between'
                }}
            >
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>Result view</span>
                    <div style={{ display: 'inline-flex', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                        <button
                            type="button"
                            className={`hr-btn ${reportViewMode === 'list' ? 'primary' : 'secondary'} sm`}
                            style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}
                            onClick={() => setReportViewMode('list')}
                        >
                            List
                        </button>
                        <button
                            type="button"
                            className={`hr-btn ${reportViewMode === 'calendar' ? 'primary' : 'secondary'} sm`}
                            style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}
                            onClick={() => setReportViewMode('calendar')}
                        >
                            Calendar
                        </button>
                    </div>
                </div>
                {reportViewMode === 'calendar' && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', flex: '1 1 220px', justifyContent: 'flex-end' }}>
                        <input
                            type="search"
                            className="control-input"
                            placeholder="Filter staff (id, name, dept, site, role)"
                            value={staffSearch}
                            onChange={(e) => setStaffSearch(e.target.value)}
                            style={{ minWidth: '200px', flex: '1 1 180px', maxWidth: '360px' }}
                            aria-label="Filter staff in calendar"
                        />
                        <button type="button" className="hr-btn secondary sm" onClick={() => setRange(thisMonthRange())}>
                            This month
                        </button>
                        <button type="button" className="hr-btn secondary sm" onClick={() => setRange(lastMonthRange())}>
                            Last month
                        </button>
                    </div>
                )}
            </div>

            {reportViewMode === 'calendar' ? (
                <div style={{ marginTop: '0.75rem' }}>
                    <AttendanceCalendarReport
                        report={report}
                        startDate={startDate}
                        endDate={endDate}
                        staffSearch={staffSearch}
                    />
                </div>
            ) : (
                <div className="mgmt-table-container" style={{ marginTop: '0.75rem' }}>
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
                                        {report
                                            ? (isFinancePortal
                                                ? 'No rows in this date range for the selected filters. Try widening dates or clearing site/role filters, then Generate again.'
                                                : 'No rows in this range for the selected filters.')
                                            : 'Generate a report to preview rows here.'}
                                    </td>
                                </tr>
                            )}
                            {flatRows.length > 100 && (
                                <tr>
                                    <td colSpan={7} style={{ textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
                                        Showing first 100 of {flatRows.length} rows. Use export buttons for the full set.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            )}
            {canManageScheduledExports && onOpenReportSchedules ? (
                <div
                    style={{
                        marginTop: '1.25rem',
                        padding: '0.85rem 1rem',
                        borderRadius: '10px',
                        border: '1px solid #e2e8f0',
                        background: '#f8fafc',
                        display: 'flex',
                        flexWrap: 'wrap',
                        alignItems: 'center',
                        gap: '0.75rem',
                        justifyContent: 'space-between',
                    }}
                >
                    <p style={{ margin: 0, fontSize: '0.875rem', color: '#475569', maxWidth: '42rem' }}>
                        <strong>Automated exports</strong> — Schedule recurring attendance files by email (and optional SFTP) on the{' '}
                        <strong>Report schedules</strong> page. That uses the same report engine with date presets and optional role, site, shift, and department filters.
                    </p>
                    <button type="button" className="hr-btn secondary sm" onClick={onOpenReportSchedules}>
                        Open report schedules
                    </button>
                </div>
            ) : null}
        </div>
    );
};

export default ReportsView;
