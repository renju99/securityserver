import React, { useState, useEffect, useMemo, Fragment } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';
import { Employee } from '../types';

const HR_MESSAGE_TEMPLATES: { label: string; body: string }[] = [
    {
        label: 'Reminder: check out',
        body: 'Hi — please remember to check out in the Workforce app when you finish so your hours stay accurate. Thanks.',
    },
    {
        label: 'Reminder: check in',
        body: 'Hi — please check in when you arrive on site today. If GPS is weak, move to an open area and tap Check in again.',
    },
    {
        label: 'NFC site tag',
        body: 'Your site uses NFC verification. Please tap the site tag before check-in or check-out as instructed on the poster.',
    },
];

const ManualAttendanceView = () => {
    const { user } = useAuthStore();
    const canManageAttendance = user?.role === 'HR Admin' || user?.role === 'Site Supervisor';
    const {
        employees, sites, attendanceLogs, setAttendanceLogs,
        logSearch, setLogSearch
    } = useDataStore();
    const { showToast } = useUIStore();

    const [showPanel, setShowPanel] = useState(false);
    const [entryType, setEntryType] = useState<'checkin' | 'checkout'>('checkin');
    const [staffSearch, setStaffSearch] = useState('');
    const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
    const [showSuggest, setShowSuggest] = useState(false);
    const [dateTime, setDateTime] = useState('');
    const [siteId, setSiteId] = useState<string | number>('');
    const [notes, setNotes] = useState('');
    const [jobCode, setJobCode] = useState('');
    const [activityName, setActivityName] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [formError, setFormError] = useState('');
    const [bulkSiteId, setBulkSiteId] = useState<string>('');
    const [bulkDepartment, setBulkDepartment] = useState('');
    const [bulkDateTime, setBulkDateTime] = useState('');
    const [bulkNotes, setBulkNotes] = useState('');
    const [bulkSubmitting, setBulkSubmitting] = useState(false);
    const [pendingApprovals, setPendingApprovals] = useState<any[]>([]);
    const [loadingApprovals, setLoadingApprovals] = useState(false);
    const [auditPanelFor, setAuditPanelFor] = useState<number | string | null>(null);
    const [auditLoading, setAuditLoading] = useState(false);
    const [auditCache, setAuditCache] = useState<Record<string, { attendance: any; events: any[] }>>({});
    const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'completed'>('all');
    const [siteFilter, setSiteFilter] = useState<string>('all');
    const [page, setPage] = useState(1);
    const pageSize = 12;

    const token = user?.token;

    useEffect(() => {
        if (showPanel) {
            const now = new Date();
            now.setSeconds(0, 0);
            setDateTime(now.toISOString().slice(0, 16));
            setBulkDateTime(now.toISOString().slice(0, 16));
            setFormError('');
        }
    }, [showPanel]);

    const suggestions = useMemo(() => {
        if (staffSearch.length < 1) return [];
        return employees.filter(e =>
            e.staff_id?.toLowerCase().includes(staffSearch.toLowerCase()) ||
            `${e.first_name || ''} ${e.last_name || ''}`.toLowerCase().includes(staffSearch.toLowerCase())
        ).slice(0, 8);
    }, [employees, staffSearch]);

    const handleSelectEmployee = (emp: Employee) => {
        setSelectedEmployee(emp);
        setStaffSearch(`${emp.staff_id} – ${emp.first_name || ''} ${emp.last_name || ''}`.trim());
        setSiteId(emp.site_id || '');
        setShowSuggest(false);
    };

    const copyTemplate = async (body: string) => {
        try {
            await navigator.clipboard.writeText(body);
            showToast('Message copied to clipboard', 'success');
        } catch {
            showToast('Could not copy — select and copy manually', 'error');
        }
    };

    const toggleAttendanceAudit = async (logId: number | string) => {
        const key = String(logId);
        if (auditPanelFor === logId) {
            setAuditPanelFor(null);
            return;
        }
        setAuditPanelFor(logId);
        if (auditCache[key]) return;
        if (!token) return;
        setAuditLoading(true);
        try {
            const res = await fetch(`/hr/attendance/${encodeURIComponent(key)}/activity-log`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to load audit');
            setAuditCache((prev) => ({ ...prev, [key]: { attendance: data.attendance, events: data.events || [] } }));
        } catch (e: any) {
            showToast(e?.message || 'Audit load failed', 'error');
            setAuditPanelFor(null);
        } finally {
            setAuditLoading(false);
        }
    };

    const refreshLogs = async () => {
        if (!token) return;
        try {
            const res = await fetch('/hr/attendance', { headers: { 'Authorization': `Bearer ${token}` } });
            const data = await res.json();
            if (Array.isArray(data)) setAttendanceLogs(data);
            if (canManageAttendance) {
                setLoadingApprovals(true);
                const approvalsRes = await fetch('/hr/attendance/pending-approvals', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                const approvalsData = await approvalsRes.json();
                if (Array.isArray(approvalsData)) setPendingApprovals(approvalsData);
                setLoadingApprovals(false);
            }
        } catch (err) {
            console.error('Error refreshing logs:', err);
            setLoadingApprovals(false);
        }
    };

    const handleSubmit = async () => {
        setFormError('');
        if (!selectedEmployee) return setFormError('Please select an employee.');
        if (!dateTime) return setFormError('Please select a date and time.');

        setSubmitting(true);
        const endpoint = entryType === 'checkin'
            ? '/hr/attendance/manual-checkin'
            : '/hr/attendance/manual-checkout';

        const body = entryType === 'checkin'
            ? { staffId: selectedEmployee.staff_id, checkInTime: dateTime, siteId: siteId || undefined, notes, jobCode: jobCode || undefined, activityName: activityName || undefined }
            : { staffId: selectedEmployee.staff_id, checkOutTime: dateTime, notes, jobCode: jobCode || undefined, activityName: activityName || undefined };

        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            if (!res.ok) {
                setFormError(data.error || 'Failed to save entry.');
            } else {
                showToast(`${entryType === 'checkin' ? 'Check-in' : 'Check-out'} logged for ${selectedEmployee.staff_id}`, 'success');
                setShowPanel(false);
                setSelectedEmployee(null);
                setStaffSearch('');
                setNotes('');
                setJobCode('');
                setActivityName('');
                refreshLogs();
            }
        } catch {
            setFormError('Network error. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    const handleBulkCheckout = async () => {
        if (!token) return;
        setBulkSubmitting(true);
        setFormError('');
        try {
            const body: any = {
                checkOutTime: bulkDateTime || undefined,
                notes: bulkNotes || undefined,
                siteId: bulkSiteId || undefined,
                departmentName: bulkDepartment || undefined
            };
            const res = await fetch('/hr/attendance/manual-bulk-checkout', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Bulk checkout failed');
            showToast(`Bulk check-out completed (${data.closedCount} records)`, 'success');
            refreshLogs();
        } catch (err: any) {
            setFormError(err.message || 'Bulk checkout failed');
        } finally {
            setBulkSubmitting(false);
        }
    };

    const filteredLogs = useMemo(() => {
        return attendanceLogs.filter(log => {
            const name = `${log.first_name || ''} ${log.last_name || ''}`.toLowerCase();
            const sId = (log.staff_id || '').toLowerCase();
            const statusOk = statusFilter === 'all'
                ? true
                : statusFilter === 'active'
                    ? !log.check_out_time
                    : !!log.check_out_time;
            const siteOk = siteFilter === 'all' ? true : String(log.site_id || '') === siteFilter;
            return (name.includes(logSearch.toLowerCase()) || sId.includes(logSearch.toLowerCase())) && statusOk && siteOk;
        });
    }, [attendanceLogs, logSearch, statusFilter, siteFilter]);

    const totalPages = Math.max(1, Math.ceil(filteredLogs.length / pageSize));
    const pagedLogs = useMemo(
        () => filteredLogs.slice((page - 1) * pageSize, page * pageSize),
        [filteredLogs, page]
    );
    const logMetrics = useMemo(() => {
        const total = attendanceLogs.length;
        const active = attendanceLogs.filter((l) => !l.check_out_time).length;
        const completed = Math.max(total - active, 0);
        const late = attendanceLogs.filter((l: any) => !!l.is_late).length;
        const manual = attendanceLogs.filter((l) => (l.notes || '').includes('Manually logged')).length;
        return { total, active, completed, late, manual };
    }, [attendanceLogs]);

    useEffect(() => {
        setPage(1);
    }, [logSearch, statusFilter, siteFilter]);

    useEffect(() => {
        if (page > totalPages) setPage(totalPages);
    }, [page, totalPages]);

    const handleApprovalAction = async (attendanceId: number, action: 'approve' | 'reject') => {
        if (!token) return;
        let reason: string | undefined;
        if (action === 'reject') {
            const entered = window.prompt(
                'Optional: add a short reason for rejection (or leave blank).\n\nPress Cancel to go back without rejecting.'
            );
            if (entered === null) return;
            reason = entered.trim() || undefined;
        }
        try {
            const res = await fetch(`/hr/attendance/${attendanceId}/${action}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ reason })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || `Failed to ${action} attendance`);
            showToast(action === 'approve' ? 'Attendance approved.' : 'Attendance rejected.', 'success');
            refreshLogs();
        } catch (err: any) {
            showToast(err.message || 'Approval action failed', 'error');
        }
    };

    const inputStyle: React.CSSProperties = {
        width: '100%', padding: '0.5rem 0.75rem', borderRadius: '7px',
        border: '1px solid #e2e8f0', fontSize: '0.875rem', boxSizing: 'border-box',
        outline: 'none', background: '#fff'
    };

    const formatPendingSource = (source?: string) => {
        const value = String(source || '').toLowerCase();
        if (!value) return 'Unknown source';
        if (value === 'offline_batch') return 'Offline sync';
        if (value === 'manual') return 'Manual entry';
        if (value === 'mobile') return 'Mobile app';
        if (value === 'biometric') return 'Biometric device';
        return source;
    };

    return (
        <div className="logs-container">
            <div className="logs-card">
                <div className="logs-header">
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                        <h2 style={{ margin: 0 }}>Attendance</h2>
                        <div className="logs-search-wrapper">
                            <svg className="search-icon-svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="11" cy="11" r="8"></circle>
                                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                            </svg>
                            <input
                                type="text"
                                placeholder="Search by name or staff ID…"
                                className="logs-search-input"
                                value={logSearch}
                                onChange={e => setLogSearch(e.target.value)}
                                aria-label="Filter attendance list"
                            />
                        </div>
                        </div>
                        <p style={{ margin: 0, fontSize: '0.82rem', color: '#64748b', maxWidth: '42rem' }}>
                            {canManageAttendance
                                ? 'Review check-ins, approve pending entries, and log manual check-in or check-out when needed.'
                                : 'View-only: browse and filter attendance for your access level.'}
                        </p>
                    </div>
                    <div style={{ display: 'flex', gap: '0.75rem', flexShrink: 0 }}>
                        {canManageAttendance && (
                            <button
                                type="button"
                                className={showPanel ? 'hr-btn secondary' : 'hr-btn primary'}
                                onClick={() => setShowPanel(p => !p)}
                            >
                                {showPanel ? 'Close manual form' : 'Add manual record'}
                            </button>
                        )}
                        <button
                            type="button"
                            className="hr-btn secondary"
                            onClick={() => { refreshLogs(); showToast('List updated', 'info'); }}
                        >
                            Refresh
                        </button>
                    </div>
                </div>

                <div className="attendance-kpi-row">
                    <div className="attendance-kpi-card blue">
                        <div className="attendance-kpi-value">{logMetrics.total}</div>
                        <div className="attendance-kpi-label">Total</div>
                    </div>
                    <div className="attendance-kpi-card green">
                        <div className="attendance-kpi-value">{logMetrics.active}</div>
                        <div className="attendance-kpi-label">In</div>
                    </div>
                    <div className="attendance-kpi-card amber">
                        <div className="attendance-kpi-value">{logMetrics.completed}</div>
                        <div className="attendance-kpi-label">Out</div>
                    </div>
                    <div className="attendance-kpi-card red">
                        <div className="attendance-kpi-value">{logMetrics.late}</div>
                        <div className="attendance-kpi-label">Late</div>
                    </div>
                    <div className="attendance-kpi-card purple">
                        <div className="attendance-kpi-value">{logMetrics.manual}</div>
                        <div className="attendance-kpi-label">Manual</div>
                    </div>
                </div>

                {canManageAttendance && showPanel && (
                    <div style={{
                        margin: '0 0 1.25rem 0', padding: '1.25rem 1.5rem',
                        background: 'linear-gradient(135deg, #f8f6ff 0%, #fff 100%)',
                        border: '1.5px solid #c7bbff', borderRadius: '12px',
                        animation: 'slideDown 0.2s ease'
                    }}>
                        <div style={{ marginBottom: '1rem' }}>
                            <div style={{ fontWeight: 700, fontSize: '1rem', color: '#1e293b', marginBottom: '0.35rem' }}>
                                Manual attendance
                            </div>
                            <p style={{ margin: 0, fontSize: '0.82rem', color: '#64748b' }}>
                                Only use this when someone could not check in or out in the app. Every manual change is recorded in audit history.
                            </p>
                        </div>

                        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                            {(['checkin', 'checkout'] as const).map(type => (
                                <button
                                    key={type}
                                    type="button"
                                    className={`hr-btn sm ${entryType === type ? 'primary' : 'secondary'}`}
                                    onClick={() => setEntryType(type)}
                                >
                                    {type === 'checkin' ? 'Check-In' : 'Check-Out'}
                                </button>
                            ))}
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.9rem' }}>
                            <div style={{ position: 'relative', gridColumn: '1 / 2' }}>
                                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#475569', marginBottom: '0.3rem' }}>
                                    Employee *
                                </label>
                                <input
                                    style={inputStyle}
                                    placeholder="Search by name or ID…"
                                    value={staffSearch}
                                    onChange={e => { setStaffSearch(e.target.value); setSelectedEmployee(null); setShowSuggest(true); }}
                                    onFocus={() => setShowSuggest(true)}
                                    onBlur={() => setTimeout(() => setShowSuggest(false), 150)}
                                    autoComplete="off"
                                />
                                {showSuggest && suggestions.length > 0 && (
                                    <div style={{
                                        position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 50,
                                        background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px',
                                        boxShadow: '0 4px 16px rgba(0,0,0,0.1)', maxHeight: '200px', overflowY: 'auto'
                                    }}>
                                        {suggestions.map(emp => (
                                            <div
                                                key={emp.id}
                                                onMouseDown={() => handleSelectEmployee(emp)}
                                                style={{
                                                    padding: '0.55rem 0.85rem', cursor: 'pointer',
                                                    borderBottom: '1px solid #f1f5f9', fontSize: '0.85rem'
                                                }}
                                                onMouseEnter={e => e.currentTarget.style.background = '#f5f3ff'}
                                                onMouseLeave={e => e.currentTarget.style.background = ''}
                                            >
                                                <span style={{ fontWeight: 600, color: '#1e293b' }}>{emp.staff_id}</span>
                                                <span style={{ color: '#64748b', marginLeft: '0.5rem' }}>
                                                    {[emp.first_name, emp.last_name].filter(Boolean).join(' ')}
                                                </span>
                                                {emp.site_name && (
                                                    <span style={{ color: '#94a3b8', fontSize: '0.75rem', marginLeft: '0.5rem' }}>
                                                        · {emp.site_name}
                                                    </span>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div>
                                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#475569', marginBottom: '0.3rem' }}>
                                    {entryType === 'checkin' ? 'Check-In Time *' : 'Check-Out Time *'}
                                </label>
                                <input
                                    type="datetime-local"
                                    style={inputStyle}
                                    value={dateTime}
                                    onChange={e => setDateTime(e.target.value)}
                                />
                            </div>

                            {user?.role === 'HR Admin' && entryType === 'checkin' && (
                                <div>
                                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#475569', marginBottom: '0.3rem' }}>
                                        Site (optional)
                                    </label>
                                    <select style={inputStyle} value={siteId} onChange={e => setSiteId(e.target.value)}>
                                        <option value="">Auto (employee's assigned site)</option>
                                        {sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                                    </select>
                                </div>
                            )}

                            <div style={{ gridColumn: '1 / -1' }}>
                                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#475569', marginBottom: '0.3rem' }}>
                                    Job Code (optional)
                                </label>
                                <input
                                    style={inputStyle}
                                    placeholder="e.g. JOB-DXB-01"
                                    value={jobCode}
                                    onChange={e => setJobCode(e.target.value)}
                                />
                            </div>

                            <div style={{ gridColumn: '1 / -1' }}>
                                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#475569', marginBottom: '0.3rem' }}>
                                    Activity (optional)
                                </label>
                                <input
                                    style={inputStyle}
                                    placeholder="e.g. Site induction, Loading, Inspection"
                                    value={activityName}
                                    onChange={e => setActivityName(e.target.value)}
                                />
                            </div>

                            <div style={{ gridColumn: '1 / -1' }}>
                                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#475569', marginBottom: '0.3rem' }}>
                                    Notes (optional)
                                </label>
                                <input
                                    style={inputStyle}
                                    placeholder="Reason for manual entry…"
                                    value={notes}
                                    onChange={e => setNotes(e.target.value)}
                                    maxLength={200}
                                />
                            </div>
                        </div>

                        {formError && (
                            <div style={{
                                marginTop: '0.75rem', padding: '0.5rem 0.85rem', background: '#fee2e2',
                                color: '#dc2626', borderRadius: '7px', fontSize: '0.83rem', fontWeight: 500
                            }}>
                                {formError}
                            </div>
                        )}

                        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
                            <button
                                type="button"
                                className="hr-btn primary"
                                onClick={handleSubmit}
                                disabled={submitting}
                            >
                                {submitting ? 'Saving…' : `Save ${entryType === 'checkin' ? 'Check-In' : 'Check-Out'}`}
                            </button>
                            <button
                                type="button"
                                className="hr-btn secondary"
                                onClick={() => { setShowPanel(false); setFormError(''); }}
                            >
                                Cancel
                            </button>
                        </div>

                        <details style={{ marginTop: '1rem', borderTop: '1px solid #e2e8f0', paddingTop: '0.8rem' }}>
                            <summary style={{ cursor: 'pointer', fontSize: '0.82rem', fontWeight: 700, color: '#475569' }}>
                                Advanced tools (use only when needed)
                            </summary>
                            <div style={{ marginTop: '0.75rem', display: 'grid', gap: '0.85rem' }}>
                                <div style={{
                                    padding: '0.85rem',
                                    border: '1px solid #e2e8f0',
                                    borderRadius: '10px',
                                    background: '#fafafa',
                                }}>
                                    <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#334155', marginBottom: '0.45rem' }}>
                                        Message snippets
                                    </div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                        {HR_MESSAGE_TEMPLATES.map((t) => (
                                            <button
                                                key={t.label}
                                                type="button"
                                                className="hr-btn secondary sm"
                                                onClick={() => copyTemplate(t.body)}
                                                title="Copy text to send to staff"
                                            >
                                                {t.label}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div style={{ padding: '0.85rem', border: '1px dashed #f59e0b', borderRadius: '10px', background: '#fffbea' }}>
                                    <div style={{ fontWeight: 700, color: '#92400e', marginBottom: '0.45rem' }}>Emergency bulk check-out</div>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '0.65rem' }}>
                                        {user?.role === 'HR Admin' && (
                                            <select style={inputStyle} value={bulkSiteId} onChange={(e) => setBulkSiteId(e.target.value)}>
                                                <option value="">All Sites</option>
                                                {sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                                            </select>
                                        )}
                                        <input style={inputStyle} placeholder="Department (optional)" value={bulkDepartment} onChange={(e) => setBulkDepartment(e.target.value)} />
                                        <input type="datetime-local" style={inputStyle} value={bulkDateTime} onChange={(e) => setBulkDateTime(e.target.value)} />
                                        <input style={inputStyle} placeholder="Reason/Note" value={bulkNotes} onChange={(e) => setBulkNotes(e.target.value)} />
                                    </div>
                                    <button type="button" className="hr-btn secondary" style={{ marginTop: '0.65rem' }} onClick={handleBulkCheckout} disabled={bulkSubmitting}>
                                        {bulkSubmitting ? 'Running bulk check-out...' : 'Run bulk check-out'}
                                    </button>
                                </div>
                            </div>
                        </details>
                    </div>
                )}

                {canManageAttendance && (
                    <div style={{ marginBottom: '1rem', padding: '0.85rem 1rem', border: '1px solid #e2e8f0', borderRadius: '10px', background: '#fff' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.45rem', gap: '0.75rem', flexWrap: 'wrap' }}>
                            <strong style={{ fontSize: '0.95rem' }}>Needs your action</strong>
                            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>{loadingApprovals ? 'Loading...' : `${pendingApprovals.length} items`}</span>
                        </div>
                        <p style={{ margin: '0 0 0.8rem', fontSize: '0.82rem', color: '#64748b', lineHeight: 1.45 }}>
                            1) Check employee and time. 2) If valid, choose <strong>Approve</strong>. 3) If not valid, choose <strong>Reject</strong>.
                        </p>
                        {pendingApprovals.length === 0 ? (
                            <div style={{ fontSize: '0.82rem', color: '#94a3b8' }}>Nothing to review right now.</div>
                        ) : (
                            <div style={{ display: 'grid', gap: '0.55rem' }}>
                                {pendingApprovals.slice(0, 10).map((item) => (
                                    <div key={item.id} style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '0.75rem', display: 'grid', gap: '0.6rem' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.8rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                                            <div style={{ fontSize: '0.85rem' }}>
                                                <div style={{ fontWeight: 700, color: '#0f172a' }}>
                                                    {item.first_name || item.last_name
                                                        ? `${item.first_name || ''} ${item.last_name || ''}`.trim()
                                                        : item.staff_id}
                                                    {item.staff_id ? ` (${item.staff_id})` : ''}
                                                </div>
                                                <div style={{ color: '#64748b', marginTop: '0.2rem' }}>
                                                    {new Date(item.check_in_time).toLocaleString()}
                                                </div>
                                            </div>
                                            <span style={{
                                                fontSize: '0.72rem',
                                                fontWeight: 700,
                                                color: '#1d4ed8',
                                                background: '#eff6ff',
                                                border: '1px solid #bfdbfe',
                                                borderRadius: '999px',
                                                padding: '0.2rem 0.55rem'
                                            }}>
                                                Review required
                                            </span>
                                        </div>

                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.45rem', fontSize: '0.78rem' }}>
                                            <div style={{ background: '#f8fafc', borderRadius: '6px', padding: '0.4rem 0.5rem' }}>
                                                <div style={{ color: '#64748b' }}>Site</div>
                                                <div style={{ fontWeight: 600, color: '#334155' }}>{item.site_name || 'Unassigned'}</div>
                                            </div>
                                            <div style={{ background: '#f8fafc', borderRadius: '6px', padding: '0.4rem 0.5rem' }}>
                                                <div style={{ color: '#64748b' }}>Type</div>
                                                <div style={{ fontWeight: 600, color: '#334155' }}>{formatPendingSource(item.source)}</div>
                                            </div>
                                            <div style={{ background: '#f8fafc', borderRadius: '6px', padding: '0.4rem 0.5rem' }}>
                                                <div style={{ color: '#64748b' }}>Action needed</div>
                                                <div style={{ fontWeight: 600, color: '#334155' }}>Approve or reject this entry</div>
                                            </div>
                                        </div>

                                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                            <button
                                                type="button"
                                                className="hr-btn sm primary"
                                                onClick={() => handleApprovalAction(item.id, 'approve')}
                                                style={{ minWidth: '120px' }}
                                            >
                                                Approve
                                            </button>
                                            <button
                                                type="button"
                                                className="hr-btn sm secondary"
                                                onClick={() => handleApprovalAction(item.id, 'reject')}
                                                style={{ minWidth: '120px' }}
                                            >
                                                Reject
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                <div className="attendance-filters-bar">
                    <select style={inputStyle} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as any)}>
                        <option value="all">Status: All</option>
                        <option value="active">Status: Active</option>
                        <option value="completed">Status: Completed</option>
                    </select>
                    <select style={inputStyle} value={siteFilter} onChange={(e) => setSiteFilter(e.target.value)}>
                        <option value="all">Site: All</option>
                        {sites.map((s) => <option key={s.id} value={String(s.id)}>{s.name}</option>)}
                    </select>
                    <div style={{ ...inputStyle, display: 'flex', alignItems: 'center', background: '#f8fafc' }}>
                        Rows: {filteredLogs.length}
                    </div>
                </div>

                <div className="logs-table-container">
                    <table className="mgmt-table">
                        <thead>
                            <tr>
                                <th>Staff Member</th>
                                <th>Check In</th>
                                <th>Check Out</th>
                                <th>Site Location</th>
                                <th style={{ textAlign: 'center' }}>Status</th>
                                <th style={{ textAlign: 'center' }}>Audit</th>
                            </tr>
                        </thead>
                        <tbody>
                            {pagedLogs.map((log, i) => {
                                const hasCheckOut = !!log.check_out_time;
                                const checkIn = new Date(log.check_in_time);
                                const checkOut = hasCheckOut ? new Date(log.check_out_time!) : null;
                                const isManual = log.notes && log.notes.includes('Manually logged');
                                const isAutoClosed = !!log.auto_closed;
                                const isLate = !!log.is_late;
                                const rowKey = log.id ?? i;
                                const numericId =
                                    typeof log.id === 'number'
                                        ? log.id
                                        : (typeof log.id === 'string' && /^\d+$/.test(log.id) ? Number(log.id) : null);
                                const auditKey = numericId != null ? String(numericId) : '';

                                return (
                                    <Fragment key={rowKey}>
                                    <tr className={log.is_live ? 'live-row' : ''}>
                                        <td className="attendance-table-staff">
                                            <div className="staff-info-cell">
                                                <div className="staff-avatar-mini">
                                                    {(log.first_name || log.staff_id || '?')[0].toUpperCase()}
                                                </div>
                                                <div>
                                                    <div style={{ fontWeight: 600, color: '#1e293b' }}>
                                                        {log.first_name || log.last_name
                                                            ? `${log.first_name || ''} ${log.last_name || ''}`.trim()
                                                            : 'Unnamed Employee'}
                                                    </div>
                                                    <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{log.staff_id}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td>
                                            <div className="time-display">
                                                <span className="date">{checkIn.toLocaleDateString()}</span>
                                                <span className="time">{checkIn.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                            </div>
                                        </td>
                                        <td>
                                            {hasCheckOut ? (
                                                <div className="time-display">
                                                    <span className="date">{checkOut?.toLocaleDateString()}</span>
                                                    <span className="time">{checkOut?.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                                </div>
                                            ) : (
                                                <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>--:--</span>
                                            )}
                                        </td>
                                        <td>
                                            <span style={{ fontSize: '0.9rem', color: '#334155' }}>{log.site_name || 'Unassigned'}</span>
                                        </td>
                                        <td style={{ textAlign: 'center' }}>
                                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '3px' }}>
                                                <span className={`status-badge-pill ${hasCheckOut ? 'completed' : 'active'}`}>
                                                    {hasCheckOut ? 'Completed' : 'Active Now'}
                                                </span>
                                                {isAutoClosed && (
                                                    <span title={log.notes} style={{
                                                        fontSize: '0.68rem', fontWeight: 600, color: '#b45309',
                                                        background: '#fef3c7', borderRadius: '4px', padding: '1px 5px'
                                                    }}>Auto</span>
                                                )}
                                                {isManual && !isAutoClosed && (
                                                    <span title={log.notes} style={{
                                                        fontSize: '0.68rem', fontWeight: 600, color: '#4338ca',
                                                        background: '#eef2ff', borderRadius: '4px', padding: '1px 5px'
                                                    }}>Manual</span>
                                                )}
                                                {isLate && (
                                                    <span style={{
                                                        fontSize: '0.68rem',
                                                        fontWeight: 700,
                                                        color: '#991b1b',
                                                        background: '#fee2e2',
                                                        borderRadius: '4px',
                                                        padding: '1px 5px'
                                                    }}>
                                                        Late
                                                    </span>
                                                )}
                                            </div>
                                        </td>
                                        <td style={{ textAlign: 'center' }}>
                                            {numericId != null ? (
                                                <button
                                                    type="button"
                                                    className="hr-btn secondary sm"
                                                    onClick={() => toggleAttendanceAudit(numericId)}
                                                >
                                                    {auditPanelFor === numericId ? 'Hide' : 'History'}
                                                </button>
                                            ) : (
                                                <span style={{ color: '#cbd5e1', fontSize: '0.75rem' }}>—</span>
                                            )}
                                        </td>
                                    </tr>
                                    {auditPanelFor === numericId && numericId != null && (
                                        <tr>
                                            <td colSpan={6} style={{ background: '#f8fafc', padding: '0.75rem 1rem', fontSize: '0.8rem', borderBottom: '1px solid #e2e8f0' }}>
                                                {auditLoading && !auditCache[auditKey] ? (
                                                    <span style={{ color: '#64748b' }}>Loading audit…</span>
                                                ) : auditCache[auditKey] ? (
                                                    <div>
                                                        <div style={{ fontWeight: 700, marginBottom: '0.35rem' }}>Record</div>
                                                        <div style={{ color: '#475569', marginBottom: '0.5rem' }}>
                                                            Source: <code>{auditCache[auditKey].attendance?.source || '—'}</code>
                                                            {' · '}Status: <code>{auditCache[auditKey].attendance?.status || '—'}</code>
                                                            {auditCache[auditKey].attendance?.auto_closed ? ' · Auto-closed' : ''}
                                                        </div>
                                                        {auditCache[auditKey].attendance?.notes && (
                                                            <div style={{ color: '#64748b', marginBottom: '0.5rem' }}>Notes: {String(auditCache[auditKey].attendance.notes)}</div>
                                                        )}
                                                        <div style={{ fontWeight: 700, marginBottom: '0.25rem' }}>Approval history</div>
                                                        {(auditCache[auditKey].events || []).length === 0 ? (
                                                            <span style={{ color: '#94a3b8' }}>No approval events recorded for this row yet.</span>
                                                        ) : (
                                                            <ul style={{ margin: 0, paddingLeft: '1.1rem', color: '#334155' }}>
                                                                {auditCache[auditKey].events.map((ev: any) => (
                                                                    <li key={ev.id} style={{ marginBottom: '0.25rem' }}>
                                                                        <strong>{ev.action}</strong>
                                                                        {ev.actor_staff_id ? ` · by ${ev.actor_staff_id}` : ''}
                                                                        {' · '}{ev.created_at ? new Date(ev.created_at).toLocaleString() : ''}
                                                                        {ev.reason ? ` — ${ev.reason}` : ''}
                                                                    </li>
                                                                ))}
                                                            </ul>
                                                        )}
                                                    </div>
                                                ) : (
                                                    <span style={{ color: '#94a3b8' }}>No audit data.</span>
                                                )}
                                            </td>
                                        </tr>
                                    )}
                                    </Fragment>
                                );
                            })}
                            {pagedLogs.length === 0 && (
                                <tr>
                                    <td colSpan={6} style={{ textAlign: 'center', padding: '3rem 1.5rem', color: '#64748b' }}>
                                        <div style={{ fontWeight: 700, color: '#334155', marginBottom: '0.5rem' }}>No rows match your filters</div>
                                        <div style={{ fontSize: '0.875rem' }}>Try clearing the search box or setting status to &quot;All&quot;. Tap Refresh if you expect new data.</div>
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
                <div className="attendance-pagination-row">
                    <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
                        Page {page} of {totalPages}
                    </div>
                    <div style={{ display: 'flex', gap: '0.45rem' }}>
                        <button type="button" className="hr-btn secondary sm" onClick={() => setPage(1)} disabled={page === 1}>First</button>
                        <button type="button" className="hr-btn secondary sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>Prev</button>
                        <button type="button" className="hr-btn secondary sm" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}>Next</button>
                        <button type="button" className="hr-btn secondary sm" onClick={() => setPage(totalPages)} disabled={page === totalPages}>Last</button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ManualAttendanceView;