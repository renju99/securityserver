import React, { useState, useEffect, useMemo } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';
import { Employee } from '../types';

const ManualAttendanceView = () => {
    const { user } = useAuthStore();
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
    const [submitting, setSubmitting] = useState(false);
    const [formError, setFormError] = useState('');

    const token = user?.token;

    useEffect(() => {
        if (showPanel) {
            const now = new Date();
            now.setSeconds(0, 0);
            setDateTime(now.toISOString().slice(0, 16));
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

    const refreshLogs = async () => {
        if (!token) return;
        try {
            const res = await fetch('/api/hr/attendance', { headers: { 'Authorization': `Bearer ${token}` } });
            const data = await res.json();
            if (Array.isArray(data)) setAttendanceLogs(data);
        } catch (err) {
            console.error('Error refreshing logs:', err);
        }
    };

    const handleSubmit = async () => {
        setFormError('');
        if (!selectedEmployee) return setFormError('Please select an employee.');
        if (!dateTime) return setFormError('Please select a date and time.');

        setSubmitting(true);
        const endpoint = entryType === 'checkin'
            ? '/api/hr/attendance/manual-checkin'
            : '/api/hr/attendance/manual-checkout';

        const body = entryType === 'checkin'
            ? { staffId: selectedEmployee.staff_id, checkInTime: dateTime, siteId: siteId || undefined, notes }
            : { staffId: selectedEmployee.staff_id, checkOutTime: dateTime, notes };

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
                showToast(`✅ ${entryType === 'checkin' ? 'Check-in' : 'Check-out'} logged for ${selectedEmployee.staff_id}`, 'success');
                setShowPanel(false);
                setSelectedEmployee(null);
                setStaffSearch('');
                setNotes('');
                refreshLogs();
            }
        } catch {
            setFormError('Network error. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    const filteredLogs = useMemo(() => {
        return attendanceLogs.filter(log => {
            const name = `${log.first_name || ''} ${log.last_name || ''}`.toLowerCase();
            const sId = (log.staff_id || '').toLowerCase();
            return name.includes(logSearch.toLowerCase()) || sId.includes(logSearch.toLowerCase());
        });
    }, [attendanceLogs, logSearch]);

    const inputStyle: React.CSSProperties = {
        width: '100%', padding: '0.5rem 0.75rem', borderRadius: '7px',
        border: '1px solid #e2e8f0', fontSize: '0.875rem', boxSizing: 'border-box',
        outline: 'none', background: '#fff'
    };

    return (
        <div className="logs-container">
            <div className="logs-card">
                <div className="logs-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <h2>🕒 Live Attendance Logs</h2>
                        <div className="logs-search-wrapper">
                            <svg className="search-icon-svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="11" cy="11" r="8"></circle>
                                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                            </svg>
                            <input
                                type="text"
                                placeholder="Filter logs by Name or ID..."
                                className="logs-search-input"
                                value={logSearch}
                                onChange={e => setLogSearch(e.target.value)}
                            />
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.75rem' }}>
                        <button
                            className={showPanel ? 'hr-btn secondary' : 'hr-btn primary'}
                            onClick={() => setShowPanel(p => !p)}
                        >
                            ✏️ {showPanel ? 'Cancel' : 'Log Entry'}
                        </button>
                        <button className="hr-btn secondary" onClick={() => { refreshLogs(); showToast('Logs refreshed', 'info'); }}>
                            🔄 Refresh
                        </button>
                    </div>
                </div>

                {showPanel && (
                    <div style={{
                        margin: '0 0 1.25rem 0', padding: '1.25rem 1.5rem',
                        background: 'linear-gradient(135deg, #f8f6ff 0%, #fff 100%)',
                        border: '1.5px solid #c7bbff', borderRadius: '12px',
                        animation: 'slideDown 0.2s ease'
                    }}>
                        <div style={{ marginBottom: '1rem' }}>
                            <div style={{ fontWeight: 700, fontSize: '1rem', color: '#1e293b', marginBottom: '0.35rem' }}>
                                Manual Attendance Log
                            </div>
                            <p style={{ margin: 0, fontSize: '0.82rem', color: '#64748b' }}>
                                Log a check-in or check-out on behalf of an employee. All manual entries are audited.
                            </p>
                        </div>

                        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                            {(['checkin', 'checkout'] as const).map(type => (
                                <button
                                    key={type}
                                    className={`hr-btn sm ${entryType === type ? 'primary' : 'secondary'}`}
                                    onClick={() => setEntryType(type)}
                                >
                                    {type === 'checkin' ? '🟢 Check-In' : '🔴 Check-Out'}
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
                                ⚠ {formError}
                            </div>
                        )}

                        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
                            <button
                                className="hr-btn primary"
                                onClick={handleSubmit}
                                disabled={submitting}
                            >
                                {submitting ? 'Saving…' : `Save ${entryType === 'checkin' ? 'Check-In' : 'Check-Out'}`}
                            </button>
                            <button
                                className="hr-btn secondary"
                                onClick={() => { setShowPanel(false); setFormError(''); }}
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                )}

                <div className="logs-table-container">
                    <table className="mgmt-table">
                        <thead>
                            <tr>
                                <th>Staff Member</th>
                                <th>Check In</th>
                                <th>Check Out</th>
                                <th>Site Location</th>
                                <th style={{ textAlign: 'center' }}>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredLogs.map((log, i) => {
                                const hasCheckOut = !!log.check_out_time;
                                const checkIn = new Date(log.check_in_time);
                                const checkOut = hasCheckOut ? new Date(log.check_out_time!) : null;
                                const isManual = log.notes && log.notes.includes('Manually logged');
                                const isAutoClosed = !!log.auto_closed;

                                return (
                                    <tr key={log.id || i} className={log.is_live ? 'live-row' : ''}>
                                        <td>
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
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                                <span style={{ fontSize: '0.9rem' }}>📍</span>
                                                <span>{log.site_name || 'Generic Site'}</span>
                                            </div>
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
                                                    }}>📝 Auto</span>
                                                )}
                                                {isManual && !isAutoClosed && (
                                                    <span title={log.notes} style={{
                                                        fontSize: '0.68rem', fontWeight: 600, color: '#4338ca',
                                                        background: '#eef2ff', borderRadius: '4px', padding: '1px 5px'
                                                    }}>🖊 Manual</span>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                            {filteredLogs.length === 0 && (
                                <tr>
                                    <td colSpan={5} style={{ textAlign: 'center', padding: '4rem', color: '#94a3b8' }}>
                                        <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>📋</div>
                                        No recent attendance records found.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default ManualAttendanceView;