import React, { useEffect, useMemo, useState } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';
import { EmployeeLeave, PublicHoliday } from '../types';
import { toDateInputValue } from '../utils/time';

const cardStyle: React.CSSProperties = {
    background: '#fff',
    border: '1px solid #e2e8f0',
    borderRadius: '16px',
    padding: '1.25rem',
    boxShadow: '0 1px 3px rgba(15, 23, 42, 0.05)'
};

const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '0.65rem 0.8rem',
    border: '1px solid #cbd5e1',
    borderRadius: '10px',
    fontSize: '0.9rem',
    boxSizing: 'border-box',
    background: '#fff'
};

const statusColors: Record<string, { bg: string; color: string }> = {
    approved: { bg: '#dcfce7', color: '#166534' },
    pending: { bg: '#fef3c7', color: '#92400e' },
    rejected: { bg: '#fee2e2', color: '#b91c1c' }
};

const LeaveCalendarView = () => {
    const user = useAuthStore((state) => state.user);
    const employees = useDataStore((state) => state.employees);
    const sites = useDataStore((state) => state.sites);
    const showToast = useUIStore((state) => state.showToast);

    const parseJsonSafe = async (res: Response) => {
        const text = await res.text();
        if (!text) return null;
        try {
            return JSON.parse(text);
        } catch {
            throw new Error(res.ok ? 'Invalid server response' : `Request failed (${res.status})`);
        }
    };

    const normalizeLeaveStatus = (raw: unknown): EmployeeLeave['status'] => {
        const s = String(raw || '').toLowerCase().trim();
        if (s === 'approved' || s === 'pending' || s === 'rejected') return s;
        return 'pending';
    };

    const now = new Date();
    const defaultStart = toDateInputValue(new Date(now.getFullYear(), now.getMonth(), 1));
    const defaultEnd = toDateInputValue(new Date(now.getFullYear(), now.getMonth() + 1, 0));

    const [startDate, setStartDate] = useState(defaultStart);
    const [endDate, setEndDate] = useState(defaultEnd);
    const [loading, setLoading] = useState(false);
    const [holidays, setHolidays] = useState<PublicHoliday[]>([]);
    const [leaves, setLeaves] = useState<EmployeeLeave[]>([]);

    const [holidayForm, setHolidayForm] = useState({
        name: '',
        startDate: defaultStart,
        endDate: defaultStart,
        siteId: ''
    });
    const [leaveForm, setLeaveForm] = useState({
        employeeId: '',
        leaveType: 'Annual Leave',
        startDate: defaultStart,
        endDate: defaultStart,
        status: 'approved',
        notes: ''
    });

    const token = user?.token;
    const isAdmin = user?.role === 'HR Admin';
    const financeReadOnly = user?.role === 'Payroll' || user?.role === 'Finance';
    const canSubmitLeave = (user?.role === 'HR Admin' || user?.role === 'Site Supervisor') && !financeReadOnly;

    const employeeOptions = useMemo(() => {
        const list = Array.isArray(employees) ? employees : [];
        return [...list]
            .filter((e) => e && e.id != null && e.staff_id != null)
            .sort((a, b) => String(a.staff_id).localeCompare(String(b.staff_id)));
    }, [employees]);

    const siteOptions = useMemo(() => (Array.isArray(sites) ? sites : []), [sites]);

    const refreshCalendar = async () => {
        if (!token) return;
        setLoading(true);
        const query = new URLSearchParams({
            ...(startDate && { startDate }),
            ...(endDate && { endDate })
        });

        try {
            const [holidaysRes, leavesRes] = await Promise.all([
                fetch(`/hr/calendar/holidays?${query}`, {
                    headers: { Authorization: `Bearer ${token}` }
                }),
                fetch(`/hr/calendar/leaves?${query}`, {
                    headers: { Authorization: `Bearer ${token}` }
                })
            ]);

            const holidaysData = await parseJsonSafe(holidaysRes);
            const leavesData = await parseJsonSafe(leavesRes);

            if (!holidaysRes.ok) {
                const msg =
                    holidaysData && typeof holidaysData === 'object' && 'error' in holidaysData
                        ? String((holidaysData as { error?: string }).error)
                        : '';
                throw new Error(msg || 'Failed to load holidays');
            }
            if (!leavesRes.ok) {
                const msg =
                    leavesData && typeof leavesData === 'object' && 'error' in leavesData
                        ? String((leavesData as { error?: string }).error)
                        : '';
                throw new Error(msg || 'Failed to load leave records');
            }

            setHolidays(Array.isArray(holidaysData) ? holidaysData : []);
            setLeaves(Array.isArray(leavesData) ? leavesData : []);
        } catch (err: any) {
            console.error(err);
            showToast(err.message || 'Failed to load leave calendar', 'error');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        refreshCalendar();
    }, [token, startDate, endDate]);

    const handleHolidaySubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!token) return;

        try {
            const res = await fetch('/hr/calendar/holidays', {
                method: 'POST',
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    ...holidayForm,
                    siteId: holidayForm.siteId || null
                })
            });
            const data = await parseJsonSafe(res);
            if (!res.ok) throw new Error((data && (data as any).error) || 'Failed to add holiday');

            setHolidayForm({
                name: '',
                startDate,
                endDate: startDate,
                siteId: ''
            });
            showToast('Holiday added', 'success');
            refreshCalendar();
        } catch (err: any) {
            console.error(err);
            showToast(err.message || 'Failed to add holiday', 'error');
        }
    };

    const handleLeaveSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!token) return;

        try {
            const res = await fetch('/hr/calendar/leaves', {
                method: 'POST',
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    ...leaveForm,
                    employeeId: leaveForm.employeeId || null
                })
            });
            const data = await parseJsonSafe(res);
            if (!res.ok) throw new Error((data && (data as any).error) || 'Failed to add leave');

            setLeaveForm({
                employeeId: '',
                leaveType: 'Annual Leave',
                startDate,
                endDate: startDate,
                status: 'approved',
                notes: ''
            });
            showToast('Leave saved', 'success');
            refreshCalendar();
        } catch (err: any) {
            console.error(err);
            showToast(err.message || 'Failed to save leave', 'error');
        }
    };

    const updateLeaveStatus = async (leaveId: number, status: EmployeeLeave['status']) => {
        if (!token) return;
        try {
            const res = await fetch(`/hr/calendar/leaves/${leaveId}`, {
                method: 'PATCH',
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status })
            });
            const data = await parseJsonSafe(res);
            if (!res.ok) throw new Error((data && (data as any).error) || 'Failed to update leave');
            showToast('Leave updated', 'success');
            refreshCalendar();
        } catch (err: any) {
            console.error(err);
            showToast(err.message || 'Failed to update leave', 'error');
        }
    };

    const deleteHoliday = async (holidayId: number) => {
        if (!token) return;
        try {
            const res = await fetch(`/hr/calendar/holidays/${holidayId}`, {
                method: 'DELETE',
                headers: { Authorization: `Bearer ${token}` }
            });
            const data = await parseJsonSafe(res);
            if (!res.ok) throw new Error((data && (data as any).error) || 'Failed to delete holiday');
            showToast('Holiday deleted', 'success');
            refreshCalendar();
        } catch (err: any) {
            console.error(err);
            showToast(err.message || 'Failed to delete holiday', 'error');
        }
    };

    const deleteLeave = async (leaveId: number) => {
        if (!token) return;
        try {
            const res = await fetch(`/hr/calendar/leaves/${leaveId}`, {
                method: 'DELETE',
                headers: { Authorization: `Bearer ${token}` }
            });
            const data = await parseJsonSafe(res);
            if (!res.ok) throw new Error((data && (data as any).error) || 'Failed to delete leave');
            showToast('Leave removed', 'success');
            refreshCalendar();
        } catch (err: any) {
            console.error(err);
            showToast(err.message || 'Failed to delete leave', 'error');
        }
    };

    return (
        <div className="management-view animate-fade-in" style={{ display: 'grid', gap: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                <div>
                    <h2 style={{ margin: 0, color: '#0f172a', fontSize: '1.75rem' }}>Leave & Holiday Calendar</h2>
                    <p style={{ margin: '0.5rem 0 0', color: '#64748b' }}>
                        Approved leave and public holidays are excluded from absence counts in reports.
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={inputStyle} />
                    <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={inputStyle} />
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
                <div style={cardStyle}>
                    <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Public Holidays</div>
                    <div style={{ marginTop: '0.35rem', fontSize: '1.8rem', fontWeight: 800, color: '#0f172a' }}>{holidays.length}</div>
                </div>
                <div style={cardStyle}>
                    <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Approved Leave</div>
                    <div style={{ marginTop: '0.35rem', fontSize: '1.8rem', fontWeight: 800, color: '#0f172a' }}>
                        {leaves.filter((leave) => leave.status === 'approved').length}
                    </div>
                </div>
                <div style={cardStyle}>
                    <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Pending Leave</div>
                    <div style={{ marginTop: '0.35rem', fontSize: '1.8rem', fontWeight: 800, color: '#0f172a' }}>
                        {leaves.filter((leave) => leave.status === 'pending').length}
                    </div>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem' }}>
                {isAdmin && (
                    <form onSubmit={handleHolidaySubmit} style={cardStyle}>
                        <h3 style={{ marginTop: 0, color: '#0f172a' }}>Add Public Holiday</h3>
                        <div style={{ display: 'grid', gap: '0.85rem' }}>
                            <input
                                style={inputStyle}
                                placeholder="Holiday name"
                                value={holidayForm.name}
                                onChange={(e) => setHolidayForm((prev) => ({ ...prev, name: e.target.value }))}
                                required
                            />
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                                <input
                                    type="date"
                                    style={inputStyle}
                                    value={holidayForm.startDate}
                                    onChange={(e) => setHolidayForm((prev) => ({ ...prev, startDate: e.target.value }))}
                                    required
                                />
                                <input
                                    type="date"
                                    style={inputStyle}
                                    value={holidayForm.endDate}
                                    onChange={(e) => setHolidayForm((prev) => ({ ...prev, endDate: e.target.value }))}
                                    required
                                />
                            </div>
                            <select
                                style={inputStyle}
                                value={holidayForm.siteId}
                                onChange={(e) => setHolidayForm((prev) => ({ ...prev, siteId: e.target.value }))}
                            >
                                <option value="">Global holiday</option>
                                {siteOptions.map((site) => (
                                    <option key={site.id} value={site.id}>{site.name}</option>
                                ))}
                            </select>
                            <button className="hr-btn primary" type="submit">Save Holiday</button>
                        </div>
                    </form>
                )}

                {canSubmitLeave ? (
                <form onSubmit={handleLeaveSubmit} style={cardStyle}>
                    <h3 style={{ marginTop: 0, color: '#0f172a' }}>Add Leave Record</h3>
                    <div style={{ display: 'grid', gap: '0.85rem' }}>
                        <select
                            style={inputStyle}
                            value={leaveForm.employeeId}
                            onChange={(e) => setLeaveForm((prev) => ({ ...prev, employeeId: e.target.value }))}
                            required
                        >
                            <option value="">Select employee</option>
                            {employeeOptions.map((employee) => (
                                <option key={employee.id} value={employee.id}>
                                    {employee.staff_id} - {[employee.first_name, employee.last_name].filter(Boolean).join(' ') || 'Unnamed'}
                                </option>
                            ))}
                        </select>
                        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: '0.75rem' }}>
                            <input
                                style={inputStyle}
                                placeholder="Leave type"
                                value={leaveForm.leaveType}
                                onChange={(e) => setLeaveForm((prev) => ({ ...prev, leaveType: e.target.value }))}
                                required
                            />
                            <select
                                style={inputStyle}
                                value={leaveForm.status}
                                onChange={(e) => setLeaveForm((prev) => ({ ...prev, status: e.target.value as EmployeeLeave['status'] }))}
                            >
                                <option value="approved">Approved</option>
                                <option value="pending">Pending</option>
                                <option value="rejected">Rejected</option>
                            </select>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                            <input
                                type="date"
                                style={inputStyle}
                                value={leaveForm.startDate}
                                onChange={(e) => setLeaveForm((prev) => ({ ...prev, startDate: e.target.value }))}
                                required
                            />
                            <input
                                type="date"
                                style={inputStyle}
                                value={leaveForm.endDate}
                                onChange={(e) => setLeaveForm((prev) => ({ ...prev, endDate: e.target.value }))}
                                required
                            />
                        </div>
                        <textarea
                            style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }}
                            placeholder="Notes (optional)"
                            value={leaveForm.notes}
                            onChange={(e) => setLeaveForm((prev) => ({ ...prev, notes: e.target.value }))}
                        />
                        <button className="hr-btn primary" type="submit">Save Leave</button>
                    </div>
                </form>
                ) : financeReadOnly ? (
                    <div style={{ ...cardStyle, color: '#64748b', fontSize: '0.9rem' }}>
                        <h3 style={{ marginTop: 0, color: '#0f172a' }}>Leave records</h3>
                        <p style={{ margin: 0 }}>You have read-only access. HR or site supervisors manage leave entries.</p>
                    </div>
                ) : null}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1rem' }}>
                <div style={cardStyle}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                        <h3 style={{ margin: 0, color: '#0f172a' }}>Holiday List</h3>
                        {loading && <span style={{ color: '#64748b', fontSize: '0.85rem' }}>Loading...</span>}
                    </div>
                    <div style={{ display: 'grid', gap: '0.75rem' }}>
                        {holidays.length === 0 && (
                            <div style={{ color: '#94a3b8', fontSize: '0.9rem' }}>No holidays in this range.</div>
                        )}
                        {holidays.map((holiday) => (
                            <div key={holiday.id} style={{ padding: '0.9rem', border: '1px solid #e2e8f0', borderRadius: '12px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem' }}>
                                    <div>
                                        <div style={{ fontWeight: 700, color: '#0f172a' }}>{holiday.name}</div>
                                        <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '0.25rem' }}>
                                            {holiday.start_date} to {holiday.end_date}
                                        </div>
                                        <div style={{ fontSize: '0.8rem', color: '#475569', marginTop: '0.35rem' }}>
                                            {holiday.site_name || 'Global'}
                                        </div>
                                    </div>
                                    {isAdmin && (
                                        <button className="hr-btn secondary" type="button" onClick={() => deleteHoliday(holiday.id)}>
                                            Delete
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                <div style={cardStyle}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                        <h3 style={{ margin: 0, color: '#0f172a' }}>Leave Records</h3>
                        {loading && <span style={{ color: '#64748b', fontSize: '0.85rem' }}>Loading...</span>}
                    </div>
                    <div style={{ display: 'grid', gap: '0.75rem' }}>
                        {leaves.length === 0 && (
                            <div style={{ color: '#94a3b8', fontSize: '0.9rem' }}>No leave records in this range.</div>
                        )}
                        {leaves.map((leave) => {
                            const st = normalizeLeaveStatus(leave.status);
                            const colors = statusColors[st] || statusColors.pending;
                            return (
                                <div key={leave.id} style={{ padding: '0.9rem', border: '1px solid #e2e8f0', borderRadius: '12px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', alignItems: 'flex-start' }}>
                                        <div>
                                            <div style={{ fontWeight: 700, color: '#0f172a' }}>
                                                {leave.staff_id} - {[leave.first_name, leave.last_name].filter(Boolean).join(' ') || 'Unnamed'}
                                            </div>
                                            <div style={{ fontSize: '0.85rem', color: '#475569', marginTop: '0.25rem' }}>
                                                {leave.leave_type} | {leave.start_date} to {leave.end_date}
                                            </div>
                                            <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.35rem' }}>
                                                {leave.site_name || 'No site'}{leave.notes ? ` | ${leave.notes}` : ''}
                                            </div>
                                        </div>
                                        <div style={{ display: 'grid', gap: '0.5rem', justifyItems: 'end' }}>
                                            {financeReadOnly ? (
                                                <span style={{
                                                    ...inputStyle,
                                                    minWidth: '120px',
                                                    display: 'inline-block',
                                                    textAlign: 'center',
                                                    background: colors.bg,
                                                    color: colors.color,
                                                    fontWeight: 700
                                                }}>{st}</span>
                                            ) : (
                                                <select
                                                    style={{ ...inputStyle, minWidth: '120px', background: colors.bg, color: colors.color, fontWeight: 700 }}
                                                    value={st}
                                                    onChange={(e) => updateLeaveStatus(leave.id, e.target.value as EmployeeLeave['status'])}
                                                >
                                                    <option value="approved">Approved</option>
                                                    <option value="pending">Pending</option>
                                                    <option value="rejected">Rejected</option>
                                                </select>
                                            )}
                                            {!financeReadOnly && (
                                                <button className="hr-btn secondary" type="button" onClick={() => deleteLeave(leave.id)}>
                                                    Delete
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LeaveCalendarView;
