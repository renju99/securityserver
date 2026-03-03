import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Modal from './Modal';
import { roleLabel } from '../../utils/roles';
import { Clock, Plus, Trash2, Edit2, FileSpreadsheet } from 'lucide-react';

const Schedules = () => {
    const [schedules, setSchedules] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [washrooms, setWashrooms] = useState([]);
    const [staff, setStaff] = useState([]);
    const [checklistTypes, setChecklistTypes] = useState([]);
    const [saving, setSaving] = useState(false);
    const [editItem, setEditItem] = useState(null);
    const [form, setForm] = useState({
        washroom_id: '',
        employee_id: '',
        start_time: '08:00',
        end_time: '',
        interval_value: 2,
        interval_unit: 'hours',
        checklist_type: 'daily_moderate',
    });

    const authHeader = { Authorization: `Bearer ${localStorage.getItem('token')}` };

    useEffect(() => { fetchAll(); }, []);

    const fetchAll = async () => {
        try {
            const [schRes, washRes, staffRes, typeRes] = await Promise.all([
                axios.get('/api/schedules', { headers: authHeader }),
                axios.get('/api/washrooms', { headers: authHeader }),
                axios.get('/api/staff', { headers: authHeader }),
                axios.get('/api/checklist-types', { headers: authHeader }),
            ]);
            setSchedules(schRes.data);
            setWashrooms(washRes.data);
            setStaff(staffRes.data);
            setChecklistTypes(typeRes.data);
        } catch (error) {
            console.error('Error fetching data:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Delete this schedule?')) return;
        try {
            await axios.delete(`/api/schedules/${id}`, { headers: authHeader });
            setSchedules(prev => prev.filter(s => s.id !== id));
        } catch (error) {
            alert('Delete failed: ' + (error.response?.data?.error || error.message));
        }
    };

    const handleToggleActive = async (item) => {
        try {
            const updated = await axios.put(`/api/schedules/${item.id}`, {
                ...item,
                active: !item.active
            }, { headers: authHeader });
            setSchedules(prev => prev.map(s => s.id === item.id ? { ...s, active: !s.active } : s));
        } catch (error) {
            alert('Update failed');
        }
    };

    const openEdit = (item) => {
        setEditItem(item);
        setForm({
            washroom_id: item.washroom_id,
            employee_id: item.employee_id || '',
            start_time: item.start_time?.slice(0, 5) || '08:00',
            end_time: item.end_time?.slice(0, 5) || '',
            interval_value: item.interval_value ?? 2,
            interval_unit: item.interval_unit || 'hours',
            checklist_type: item.checklist_type || 'daily_moderate',
        });
        setShowModal(true);
    };

    const handleSave = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            if (editItem) {
                await axios.put(`/api/schedules/${editItem.id}`, { ...form, active: editItem.active }, { headers: authHeader });
            } else {
                await axios.post('/api/schedules', form, { headers: authHeader });
            }
            setShowModal(false);
            setEditItem(null);
            setForm({ washroom_id: '', employee_id: '', start_time: '08:00', end_time: '', interval_value: 2, interval_unit: 'hours', checklist_type: 'daily_moderate' });
            fetchAll();
        } catch (error) {
            alert('Save failed: ' + (error.response?.data?.error || error.message));
        } finally {
            setSaving(false);
        }
    };

    const handleImportExcel = () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.xlsx,.xls,.csv';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('file', file);
            try {
                const res = await axios.post('/api/import/schedules', formData, {
                    headers: { ...authHeader, 'Content-Type': 'multipart/form-data' }
                });
                alert(`${res.data.message}`);
                fetchAll();
            } catch (error) {
                alert('Import failed: ' + (error.response?.data?.error || error.message));
            }
        };
        input.click();
    };

    const inputStyle = {
        width: '100%', padding: '0.6rem 0.8rem', borderRadius: '8px',
        background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)',
        color: 'white', fontSize: '0.9rem', boxSizing: 'border-box'
    };
    const labelStyle = { fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem', display: 'block' };

    return (
        <div className="fade-in">
            <header className="content-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <h1>Cleaning Schedules</h1>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button className="btn btn-secondary" onClick={handleImportExcel} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <FileSpreadsheet size={16} /> Import Excel
                    </button>
                    <button className="btn btn-primary" onClick={() => { setEditItem(null); setForm({ washroom_id: '', employee_id: '', start_time: '08:00', end_time: '', interval_value: 2, interval_unit: 'hours', checklist_type: 'daily_moderate' }); setShowModal(true); }} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Plus size={16} /> New Schedule
                    </button>
                </div>
            </header>

            {/* Table */}
            <div className="card glass shadow" style={{ padding: '0', overflowX: 'auto' }}>
                {loading ? (
                    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading schedules...</div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ background: 'rgba(255,255,255,0.05)' }}>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)', fontWeight: '600' }}>Location</th>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)', fontWeight: '600' }}>Start Time</th>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)', fontWeight: '600' }}>Interval</th>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)', fontWeight: '600' }}>Assigned To</th>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)', fontWeight: '600' }}>Status</th>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)', fontWeight: '600' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {schedules.map(item => (
                                <tr key={item.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', transition: 'background 0.2s' }}
                                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                                >
                                    <td style={{ padding: '1rem' }}>
                                        <div style={{ fontWeight: '600' }}>{item.washroom_name || 'All Washrooms'}</div>
                                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{item.project_name || '—'}</div>
                                    </td>
                                    <td style={{ padding: '1rem' }}>
                                        <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                            <Clock size={14} style={{ color: 'var(--primary)' }} />
                                            {item.start_time?.slice(0, 5)}
                                        </span>
                                    </td>
                                    <td style={{ padding: '1rem' }}>Every {item.interval_value} {item.interval_unit}</td>
                                    <td style={{ padding: '1rem' }}>
                                        {item.employee_name ? (
                                            <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                <div style={{ width: '28px', height: '28px', borderRadius: '50%', background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '0.75rem', color: 'white' }}>
                                                    {item.employee_name[0]}
                                                </div>
                                                {item.employee_name}
                                            </span>
                                        ) : (
                                            <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Unassigned</span>
                                        )}
                                    </td>
                                    <td style={{ padding: '1rem' }}>
                                        <button onClick={() => handleToggleActive(item)} style={{ cursor: 'pointer', border: 'none', background: item.active ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)', color: item.active ? 'var(--success)' : 'var(--danger)', padding: '3px 10px', borderRadius: '20px', fontSize: '0.75rem', fontWeight: '600' }}>
                                            {item.active ? '● Running' : '○ Paused'}
                                        </button>
                                    </td>
                                    <td style={{ padding: '1rem' }}>
                                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                                            <button type="button" className="btn btn-secondary" style={{ padding: '0.4rem 0.6rem' }} title="Edit" onClick={() => openEdit(item)}><Edit2 size={13} /></button>
                                            <button onClick={() => handleDelete(item.id)} className="btn btn-secondary" style={{ padding: '0.4rem 0.6rem', color: 'var(--danger)' }} title="Delete"><Trash2 size={13} /></button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
                {schedules.length === 0 && !loading && (
                    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                        No schedules yet. Click <strong>New Schedule</strong> or import from Excel.
                    </div>
                )}
            </div>

            <Modal
                show={showModal}
                onClose={() => { setShowModal(false); setEditItem(null); }}
                title={editItem ? 'Edit Schedule' : 'New Cleaning Schedule'}
                maxWidth={500}
            >
                <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div>
                        <label style={labelStyle}>Washroom *</label>
                        <select style={inputStyle} required value={form.washroom_id} onChange={e => setForm(f => ({ ...f, washroom_id: e.target.value }))}>
                            <option value="">Select washroom...</option>
                            {washrooms.map(w => (
                                <option key={w.id} value={w.id}>{w.name} {w.project_name ? `(${w.project_name})` : ''}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label style={labelStyle}>Assign To (Staff)</label>
                        <select style={inputStyle} value={form.employee_id} onChange={e => setForm(f => ({ ...f, employee_id: e.target.value }))}>
                            <option value="">Any available cleaner</option>
                            {staff.map(s => (
                                <option key={s.id} value={s.id}>{s.name} ({roleLabel(s.role)})</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label style={labelStyle}>Checklist Type *</label>
                        <select style={inputStyle} required value={form.checklist_type} onChange={e => setForm(f => ({ ...f, checklist_type: e.target.value }))}>
                            {checklistTypes.map(t => (
                                <option key={t.value} value={t.value}>{t.label}</option>
                            ))}
                        </select>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div>
                            <label style={labelStyle}>Start Time *</label>
                            <input type="time" style={inputStyle} required value={form.start_time} onChange={e => setForm(f => ({ ...f, start_time: e.target.value }))} />
                        </div>
                        <div>
                            <label style={labelStyle}>End Time (optional)</label>
                            <input type="time" style={inputStyle} value={form.end_time} onChange={e => setForm(f => ({ ...f, end_time: e.target.value }))} />
                        </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div>
                            <label style={labelStyle}>Every *</label>
                            <input type="number" min="1" max="24" style={inputStyle} required value={form.interval_value} onChange={e => setForm(f => ({ ...f, interval_value: e.target.value }))} />
                        </div>
                        <div>
                            <label style={labelStyle}>Unit *</label>
                            <select style={inputStyle} value={form.interval_unit} onChange={e => setForm(f => ({ ...f, interval_unit: e.target.value }))}>
                                <option value="hours">Hours</option>
                                <option value="days">Days</option>
                                <option value="weeks">Weeks</option>
                            </select>
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                        <button type="button" className="btn btn-secondary" onClick={() => { setShowModal(false); setEditItem(null); }} style={{ flex: 1 }}>Cancel</button>
                        <button type="submit" className="btn btn-primary" disabled={saving} style={{ flex: 2 }}>
                            {saving ? 'Saving...' : editItem ? 'Save Changes' : 'Create Schedule'}
                        </button>
                    </div>
                </form>
            </Modal>
        </div>
    );
};

export default Schedules;
