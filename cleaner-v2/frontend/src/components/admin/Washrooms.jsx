import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Plus, Edit2, Trash2, QrCode, Save, Copy } from 'lucide-react';
import Modal from './Modal';

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const inputStyle = { width: '100%', padding: '0.6rem 0.8rem', borderRadius: '8px', background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)', color: 'white', fontSize: '0.9rem', boxSizing: 'border-box' };
const labelStyle = { fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem', display: 'block' };

const Washrooms = () => {
    const [washrooms, setWashrooms] = useState([]);
    const [projects, setProjects] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editItem, setEditItem] = useState(null);
    const [saving, setSaving] = useState(false);
    const [form, setForm] = useState({ project_id: '', name: '', code: '', building: '', floor: '', room: '', lat: '', lng: '' });

    useEffect(() => { fetchAll(); }, []);

    const fetchAll = async () => {
        try {
            const [wRes, pRes] = await Promise.all([
                axios.get('/api/washrooms', { headers: authHeader() }),
                axios.get('/api/projects', { headers: authHeader() }),
            ]);
            setWashrooms(wRes.data);
            setProjects(pRes.data);
        } catch (err) {
            console.error('Error fetching washrooms:', err);
        } finally {
            setLoading(false);
        }
    };

    const openCreate = () => {
        setEditItem(null);
        setForm({ project_id: projects[0]?.id || '', name: '', code: '', building: '', floor: '', room: '', lat: '', lng: '' });
        setShowModal(true);
    };

    const openEdit = (item) => {
        setEditItem(item);
        setForm({ project_id: item.project_id, name: item.name, code: item.code || '', building: item.building || '', floor: item.floor || '', room: item.room || '', lat: item.lat || '', lng: item.lng || '' });
        setShowModal(true);
    };

    const handleSave = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            if (editItem) {
                await axios.put(`/api/washrooms/${editItem.id}`, form, { headers: authHeader() });
            } else {
                await axios.post('/api/washrooms', form, { headers: authHeader() });
            }
            setShowModal(false);
            fetchAll();
        } catch (err) {
            alert('Save failed: ' + (err.response?.data?.error || err.message));
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Remove this washroom?')) return;
        try {
            await axios.delete(`/api/washrooms/${id}`, { headers: authHeader() });
            setWashrooms(prev => prev.filter(w => w.id !== id));
        } catch (err) {
            alert('Delete failed: ' + (err.response?.data?.error || err.message));
        }
    };

    const copyToken = (token) => {
        navigator.clipboard.writeText(token);
    };

    return (
        <div className="fade-in">
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
                <h1>Washroom Management</h1>
                <button
                    className="btn btn-primary"
                    onClick={openCreate}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
                    title={projects.length === 0 ? 'Create a project first' : ''}
                    disabled={projects.length === 0}
                >
                    <Plus size={16} /> New Washroom
                </button>
            </header>

            <div className="card glass" style={{ padding: '0', overflowX: 'auto' }}>
                {loading ? (
                    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading...</div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ background: 'rgba(255,255,255,0.05)' }}>
                                {['Project', 'Washroom Name', 'Code / Room', 'QR Token', 'Status', 'Actions'].map(h => (
                                    <th key={h} style={{ textAlign: 'left', padding: '1rem 1.2rem', color: 'var(--text-muted)', fontWeight: '600', fontSize: '0.82rem', whiteSpace: 'nowrap' }}>{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {washrooms.map(item => (
                                <tr key={item.id}
                                    style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', transition: 'background 0.15s' }}
                                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                                >
                                    <td style={{ padding: '1rem 1.2rem', color: 'var(--text-muted)', fontSize: '0.88rem' }}>{item.project_name || '—'}</td>
                                    <td style={{ padding: '1rem 1.2rem', fontWeight: '600' }}>{item.name}</td>
                                    <td style={{ padding: '1rem 1.2rem' }}>
                                        <span style={{ color: 'var(--primary)', fontWeight: '700', fontSize: '0.85rem' }}>{item.code || item.room || '—'}</span>
                                        {item.floor && <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginLeft: '0.4rem' }}>Fl. {item.floor}</span>}
                                    </td>
                                    <td style={{ padding: '1rem 1.2rem' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', color: 'var(--text-muted)', fontFamily: 'monospace', background: 'rgba(255,255,255,0.04)', padding: '3px 8px', borderRadius: '6px', maxWidth: '140px', overflow: 'hidden' }}>
                                            <QrCode size={12} style={{ flexShrink: 0 }} />
                                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.qr_token}</span>
                                            <button onClick={() => copyToken(item.qr_token)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary)', padding: 0, flexShrink: 0 }}><Copy size={11} /></button>
                                        </div>
                                    </td>
                                    <td style={{ padding: '1rem 1.2rem' }}>
                                        <span style={{ background: 'rgba(34,197,94,0.15)', color: 'var(--success)', padding: '3px 10px', borderRadius: '20px', fontSize: '0.75rem', fontWeight: '600' }}>Active</span>
                                    </td>
                                    <td style={{ padding: '1rem 1.2rem' }}>
                                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                                            <button className="btn btn-secondary" style={{ padding: '0.4rem 0.7rem' }} onClick={() => openEdit(item)}><Edit2 size={13} /></button>
                                            <button className="btn btn-secondary" style={{ padding: '0.4rem 0.7rem', color: 'var(--danger)' }} onClick={() => handleDelete(item.id)}><Trash2 size={13} /></button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
                {washrooms.length === 0 && !loading && (
                    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>No washrooms found. Add one above.</div>
                )}
            </div>

            <Modal
                show={showModal}
                onClose={() => setShowModal(false)}
                title={editItem ? 'Edit Washroom' : 'New Washroom'}
                maxWidth={500}
            >
                <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div>
                        <label style={labelStyle}>Project *</label>
                        <select style={inputStyle} required value={form.project_id} onChange={e => setForm(f => ({ ...f, project_id: e.target.value }))}>
                            <option value="">Select project...</option>
                            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                        </select>
                    </div>
                    <div>
                        <label style={labelStyle}>Washroom Name *</label>
                        <input style={inputStyle} required placeholder="e.g. Male Washroom - Floor 2" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div>
                            <label style={labelStyle}>Code / Room No.</label>
                            <input style={inputStyle} placeholder="PPM-A1-0001" value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value }))} />
                        </div>
                        <div>
                            <label style={labelStyle}>Building</label>
                            <input style={inputStyle} placeholder="Block A" value={form.building} onChange={e => setForm(f => ({ ...f, building: e.target.value }))} />
                        </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div>
                            <label style={labelStyle}>Floor</label>
                            <input style={inputStyle} placeholder="1" value={form.floor} onChange={e => setForm(f => ({ ...f, floor: e.target.value }))} />
                        </div>
                        <div>
                            <label style={labelStyle}>Room</label>
                            <input style={inputStyle} placeholder="WR-101" value={form.room} onChange={e => setForm(f => ({ ...f, room: e.target.value }))} />
                        </div>
                    </div>
                    {!editItem && (
                        <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', background: 'rgba(99,102,241,0.08)', padding: '0.6rem', borderRadius: '8px' }}>
                            💡 A unique QR token will be auto-generated for this washroom.
                        </p>
                    )}
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                        <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)} style={{ flex: 1 }}>Cancel</button>
                        <button type="submit" className="btn btn-primary" disabled={saving} style={{ flex: 2, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem' }}>
                            <Save size={15} /> {saving ? 'Saving...' : editItem ? 'Save Changes' : 'Create Washroom'}
                        </button>
                    </div>
                </form>
            </Modal>
        </div>
    );
};

export default Washrooms;
