import React, { useEffect, useMemo, useState } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';
import { toDateInputValue } from '../utils/time';

const RosterPlanningView = () => {
    const { user } = useAuthStore();
    const { sites, shifts, employees } = useDataStore();
    const { showToast } = useUIStore();
    const token = user?.token;

    const today = toDateInputValue(new Date());
    const [mode, setMode] = useState<'fixed' | 'rotating'>('fixed');
    const [shiftId, setShiftId] = useState('');
    const [shiftSequence, setShiftSequence] = useState<(number | string)[]>([]);
    const [cycleDays, setCycleDays] = useState(1);
    const [templateName, setTemplateName] = useState('');
    const [siteId, setSiteId] = useState('');
    const [departmentName, setDepartmentName] = useState('');
    const [startDate, setStartDate] = useState(today);
    const [endDate, setEndDate] = useState(today);
    const [selectedEmployeeIds, setSelectedEmployeeIds] = useState<(number | string)[]>([]);
    const [templates, setTemplates] = useState<any[]>([]);
    const [assignments, setAssignments] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);

    const employeeOptions = useMemo(
        () => employees.map((e) => ({ id: e.id, label: `${e.staff_id} - ${[e.first_name, e.last_name].filter(Boolean).join(' ')}` })),
        [employees]
    );

    const fetchRosters = async () => {
        if (!token) return;
        try {
            const [tplRes, asnRes] = await Promise.all([
                fetch('/hr/rosters/templates', { headers: { Authorization: `Bearer ${token}` } }),
                fetch(`/hr/rosters/assignments?startDate=${startDate}&endDate=${endDate}`, { headers: { Authorization: `Bearer ${token}` } })
            ]);
            const tplData = await tplRes.json();
            const asnData = await asnRes.json();
            if (tplRes.ok) setTemplates(Array.isArray(tplData) ? tplData : []);
            if (asnRes.ok) setAssignments(Array.isArray(asnData) ? asnData : []);
        } catch (err) {
            console.error(err);
        }
    };

    useEffect(() => {
        fetchRosters();
    }, [token, startDate, endDate]);

    const applyRoster = async () => {
        if (!token) return;
        setLoading(true);
        try {
            const payload: any = {
                mode,
                startDate,
                endDate,
                siteId: siteId || null,
                departmentName: departmentName || null,
                employeeIds: selectedEmployeeIds
            };
            if (mode === 'fixed') {
                payload.shiftId = shiftId;
            } else {
                payload.name = templateName || `Rotation ${new Date().toISOString().slice(0, 10)}`;
                payload.shiftSequence = shiftSequence;
                payload.cycleDays = cycleDays;
            }

            const res = await fetch('/hr/rosters/apply', {
                method: 'POST',
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to apply roster');
            showToast(`Roster applied: ${data.assignmentsUpserted} assignments`, 'success');
            fetchRosters();
        } catch (err: any) {
            console.error(err);
            showToast(err.message || 'Failed to apply roster', 'error');
        } finally {
            setLoading(false);
        }
    };

    const toggleSequenceShift = (id: number) => {
        setShiftSequence((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
    };

    const toggleEmployee = (id: number) => {
        setSelectedEmployeeIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
    };

    return (
        <div className="management-view animate-fade-in">
            <div style={{ marginBottom: '1rem' }}>
                <h2 style={{ margin: 0 }}>Shift Planning</h2>
                <p style={{ margin: '4px 0 0', color: '#64748b' }}>Recurring rosters, rotating shifts, and bulk assignments</p>
            </div>

            <div className="card" style={{ marginBottom: '1rem' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
                    <select value={mode} onChange={(e) => setMode(e.target.value as any)} className="control-input">
                        <option value="fixed">Fixed Shift Bulk Assignment</option>
                        <option value="rotating">Rotating Shift Roster</option>
                    </select>
                    <select value={siteId} onChange={(e) => setSiteId(e.target.value)} className="control-input">
                        <option value="">All Sites</option>
                        {sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                    <input className="control-input" placeholder="Department (optional)" value={departmentName} onChange={(e) => setDepartmentName(e.target.value)} />
                    <input type="date" className="control-input" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                    <input type="date" className="control-input" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                </div>

                {mode === 'fixed' ? (
                    <div style={{ marginTop: '0.75rem' }}>
                        <select value={shiftId} onChange={(e) => setShiftId(e.target.value)} className="control-input">
                            <option value="">Select shift</option>
                            {shifts.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.start_time}-{s.end_time})</option>)}
                        </select>
                    </div>
                ) : (
                    <div style={{ marginTop: '0.75rem', display: 'grid', gap: '0.5rem' }}>
                        <input className="control-input" placeholder="Template name" value={templateName} onChange={(e) => setTemplateName(e.target.value)} />
                        <input type="number" className="control-input" min={1} max={31} value={cycleDays} onChange={(e) => setCycleDays(parseInt(e.target.value || '1', 10))} />
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                            {shifts.map((s) => (
                                <button
                                    key={s.id}
                                    type="button"
                                    className={`hr-btn ${shiftSequence.includes(s.id) ? 'primary' : 'secondary'}`}
                                    onClick={() => toggleSequenceShift(s.id)}
                                >
                                    {s.name}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                <div style={{ marginTop: '0.75rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.4rem', fontWeight: 600 }}>Optional employee selection</label>
                    <div style={{ maxHeight: '160px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '0.5rem' }}>
                        {employeeOptions.map((e) => (
                            <label key={e.id} style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.3rem' }}>
                                <input type="checkbox" checked={selectedEmployeeIds.includes(e.id)} onChange={() => toggleEmployee(e.id)} /> {e.label}
                            </label>
                        ))}
                    </div>
                </div>

                <div style={{ marginTop: '0.75rem' }}>
                    <button className="hr-btn primary" onClick={applyRoster} disabled={loading}>
                        {loading ? 'Applying...' : 'Apply Roster'}
                    </button>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="card">
                    <h3 style={{ marginTop: 0 }}>Roster Templates</h3>
                    <div style={{ maxHeight: '320px', overflowY: 'auto' }}>
                        {templates.map((t) => (
                            <div key={t.id} style={{ padding: '0.6rem', borderBottom: '1px solid #f1f5f9' }}>
                                <strong>{t.name}</strong>
                                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>{t.rotation_type} | {t.start_date} to {t.end_date || 'ongoing'}</div>
                            </div>
                        ))}
                        {templates.length === 0 && <div style={{ color: '#94a3b8' }}>No templates yet.</div>}
                    </div>
                </div>
                <div className="card">
                    <h3 style={{ marginTop: 0 }}>Assignments ({startDate} to {endDate})</h3>
                    <div style={{ maxHeight: '320px', overflowY: 'auto' }}>
                        {assignments.slice(0, 200).map((a) => (
                            <div key={a.id} style={{ padding: '0.6rem', borderBottom: '1px solid #f1f5f9' }}>
                                <strong>{a.staff_id}</strong> - {a.shift_name}
                                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>{a.work_date} | {a.site_name || 'Unassigned'}</div>
                            </div>
                        ))}
                        {assignments.length === 0 && <div style={{ color: '#94a3b8' }}>No assignments in range.</div>}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default RosterPlanningView;
