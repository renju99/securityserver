import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Plus, Edit2, Trash2, Mail, Calendar, Save } from 'lucide-react';
import Modal from './Modal';

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const inputStyle = { width: '100%', padding: '0.6rem 0.8rem', borderRadius: '8px', background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)', color: 'white', fontSize: '0.9rem', boxSizing: 'border-box' };
const labelStyle = { fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem', display: 'block' };

const ROLE_OPTIONS = [
    { value: 'cleaner', label: 'Cleaner', description: 'Check-in at locations, complete checklists', color: 'var(--primary)' },
    { value: 'supervisor', label: 'Supervisor', description: 'View reports and schedules, oversee cleaners', color: '#0ea5e9' },
    { value: 'manager', label: 'Manager', description: 'Manage schedules, staff, and reports', color: '#8b5cf6' },
    { value: 'admin', label: 'Full Admin', description: 'Full access: projects, locations, users, all settings', color: 'var(--success)' },
];

const roleLabel = (role) => ROLE_OPTIONS.find(r => r.value === role)?.label || role;

const Staff = () => {
    const [staffMembers, setStaffMembers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editMember, setEditMember] = useState(null);
    const [saving, setSaving] = useState(false);
    const [form, setForm] = useState({ name: '', email: '', role: 'cleaner', password: '' });

    const fetchStaff = async () => {
        try {
            const response = await axios.get('/api/staff', { headers: authHeader() });
            setStaffMembers(response.data);
        } catch (error) {
            console.error('Error fetching staff:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchStaff(); }, []);

    const openCreate = () => {
        setEditMember(null);
        setForm({ name: '', email: '', role: 'cleaner', password: '' });
        setShowModal(true);
    };

    const openEdit = (member) => {
        setEditMember(member);
        setForm({ name: member.name, email: member.email, role: member.role || 'cleaner', password: '' });
        setShowModal(true);
    };

    const handleSave = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            if (editMember) {
                const payload = { name: form.name, email: form.email, role: form.role };
                if (form.password) payload.password = form.password;
                await axios.put(`/api/staff/${editMember.id}`, payload, { headers: authHeader() });
            } else {
                await axios.post('/api/staff', form, { headers: authHeader() });
            }
            setShowModal(false);
            fetchStaff();
        } catch (err) {
            alert(err.response?.data?.error || 'Save failed');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Remove this staff member? They will no longer be able to log in.')) return;
        try {
            await axios.delete(`/api/staff/${id}`, { headers: authHeader() });
            setStaffMembers(prev => prev.filter(s => s.id !== id));
        } catch (err) {
            alert(err.response?.data?.error || 'Delete failed');
        }
    };

    return (
        <div className="fade-in">
            <header className="content-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
                <div>
                    <h1>Users</h1>
                    <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Create and manage user accounts and access rights</p>
                </div>
                <button className="btn btn-primary" onClick={openCreate} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Plus size={18} /> Create User
                </button>
            </header>

            <div className="grid-list" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem' }}>
                {staffMembers.map(member => (
                    <div key={member.id} className="card glass shadow" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                            <div className="avatar" style={{ width: '48px', height: '48px', borderRadius: '50%', background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold' }}>
                                {member.name?.charAt(0) || '?'}
                            </div>
                            <span className="status-tag on_time" style={{ height: 'fit-content', background: (ROLE_OPTIONS.find(r => r.value === member.role) || {}).color ? `${ROLE_OPTIONS.find(r => r.value === member.role).color}22` : 'rgba(99, 102, 241, 0.2)', color: (ROLE_OPTIONS.find(r => r.value === member.role) || {}).color || 'var(--primary)', padding: '2px 10px', borderRadius: '20px', fontSize: '0.75rem', fontWeight: '600' }}>{roleLabel(member.role)}</span>
                        </div>
                        <h3>{member.name}</h3>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Mail size={14} /> {member.email}
                        </p>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Calendar size={14} /> Joined {member.created_at ? new Date(member.created_at).toLocaleDateString() : '—'}
                        </p>
                        <div style={{ display: 'flex', gap: '1rem', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1rem', marginTop: '0.5rem' }}>
                            <button type="button" className="btn btn-secondary" style={{ flex: 1, fontSize: '0.85rem', padding: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem' }} onClick={() => openEdit(member)}><Edit2 size={14} /> Edit</button>
                            <button type="button" className="btn btn-secondary" style={{ flex: 1, fontSize: '0.85rem', padding: '0.5rem', color: 'var(--danger)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem' }} onClick={() => handleDelete(member.id)}><Trash2 size={14} /> Delete</button>
                        </div>
                    </div>
                ))}
            </div>
            {staffMembers.length === 0 && !loading && (
                <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                    No users yet. Click <strong>Create User</strong> to add one.
                </div>
            )}

            <Modal
                show={showModal}
                onClose={() => setShowModal(false)}
                title={editMember ? 'Edit User' : 'Create User'}
                maxWidth={480}
            >
                <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div>
                        <label style={labelStyle}>Name *</label>
                        <input style={inputStyle} required placeholder="Full name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
                    </div>
                    <div>
                        <label style={labelStyle}>Email *</label>
                        <input type="email" style={inputStyle} required placeholder="email@company.com" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
                    </div>
                    <div>
                        <label style={labelStyle}>Access rights</label>
                        <select style={inputStyle} value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
                            {ROLE_OPTIONS.map(opt => (
                                <option key={opt.value} value={opt.value}>{opt.label} — {opt.description}</option>
                            ))}
                        </select>
                        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                            {ROLE_OPTIONS.find(r => r.value === form.role)?.description}
                        </p>
                    </div>
                    <div>
                        <label style={labelStyle}>{editMember ? 'New password (leave blank to keep current)' : 'Password *'}</label>
                        <input type="password" style={inputStyle} placeholder={editMember ? '••••••••' : 'Min 8 characters'} value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required={!editMember} minLength={8} />
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                        <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)} style={{ flex: 1 }}>Cancel</button>
                        <button type="submit" className="btn btn-primary" disabled={saving} style={{ flex: 2, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem' }}><Save size={15} /> {saving ? 'Saving...' : editMember ? 'Save Changes' : 'Create'}</button>
                    </div>
                </form>
            </Modal>
        </div>
    );
};

export default Staff;
