import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { MapPin, Plus, Edit2, Trash2, Globe, Save } from 'lucide-react';
import Modal from './Modal';
import PlacesAutocompleteInput from '../common/PlacesAutocompleteInput';
import LocationMap from '../common/LocationMap';
import { PREDEFINED_LOCATIONS } from '../../config/locations';

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });
const inputStyle = { width: '100%', padding: '0.6rem 0.8rem', borderRadius: '8px', background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)', color: 'white', fontSize: '0.9rem', boxSizing: 'border-box' };
const labelStyle = { fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem', display: 'block' };

const Projects = () => {
    const [projects, setProjects] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editProject, setEditProject] = useState(null);
    const [saving, setSaving] = useState(false);
    const [form, setForm] = useState({ name: '', location: '', geofence_lat: '', geofence_lng: '', geofence_radius: 100, locationPreset: '' });

    useEffect(() => { fetchProjects(); }, []);

    const fetchProjects = async () => {
        try {
            const res = await axios.get('/api/projects', { headers: authHeader() });
            setProjects(res.data);
        } catch (err) {
            console.error('Error fetching projects:', err);
        } finally {
            setLoading(false);
        }
    };

    const openCreate = () => {
        setEditProject(null);
        setForm({ name: '', location: '', geofence_lat: '', geofence_lng: '', geofence_radius: 100, locationPreset: '' });
        setShowModal(true);
    };

    const openEdit = (project) => {
        setEditProject(project);
        setForm({
            name: project.name,
            location: project.location || '',
            geofence_lat: project.geofence_lat || '',
            geofence_lng: project.geofence_lng || '',
            geofence_radius: project.geofence_radius || 100,
            locationPreset: '',
        });
        setShowModal(true);
    };

    const handleSave = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            if (editProject) {
                await axios.put(`/api/projects/${editProject.id}`, form, { headers: authHeader() });
            } else {
                await axios.post('/api/projects', form, { headers: authHeader() });
            }
            setShowModal(false);
            fetchProjects();
        } catch (err) {
            alert('Save failed: ' + (err.response?.data?.error || err.message));
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Delete this project? All washrooms under it will also be deleted.')) return;
        try {
            await axios.delete(`/api/projects/${id}`, { headers: authHeader() });
            setProjects(prev => prev.filter(p => p.id !== id));
        } catch (err) {
            alert('Delete failed: ' + (err.response?.data?.error || err.message));
        }
    };

    return (
        <div className="fade-in">
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
                <h1>Project Management</h1>
                <button className="btn btn-primary" onClick={openCreate} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Plus size={16} /> New Project
                </button>
            </header>

            {loading ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading projects...</div>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem' }}>
                    {projects.map(project => (
                        <div key={project.id} className="card glass" style={{ position: 'relative' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                                <div style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--primary)', width: '44px', height: '44px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                    <Globe size={22} />
                                </div>
                                <span style={{ height: 'fit-content', background: 'rgba(34,197,94,0.2)', color: 'var(--success)', padding: '3px 10px', borderRadius: '20px', fontSize: '0.75rem', fontWeight: '600' }}>Active</span>
                            </div>
                            <h3 style={{ marginBottom: '0.4rem' }}>{project.name}</h3>
                            <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '1.5rem' }}>
                                <MapPin size={13} /> {project.location || 'No location set'}
                            </p>
                            <div style={{ display: 'flex', gap: '0.8rem', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '1rem' }}>
                                <button className="btn btn-secondary" style={{ flex: 1, fontSize: '0.85rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem' }} onClick={() => openEdit(project)}>
                                    <Edit2 size={13} /> Edit
                                </button>
                                <button className="btn btn-secondary" style={{ flex: 1, fontSize: '0.85rem', color: 'var(--danger)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem' }} onClick={() => handleDelete(project.id)}>
                                    <Trash2 size={13} /> Delete
                                </button>
                            </div>
                        </div>
                    ))}
                    {projects.length === 0 && (
                        <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: '4rem', color: 'var(--text-muted)' }}>
                            No projects yet. Click <strong>New Project</strong> to create one.
                        </div>
                    )}
                </div>
            )}

            <Modal
                show={showModal}
                onClose={() => setShowModal(false)}
                title={editProject ? 'Edit Project' : 'New Project'}
            >
                <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div>
                        <label style={labelStyle}>Project Name *</label>
                        <input style={inputStyle} required placeholder="e.g. Dubai Mall" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
                    </div>
                    <PlacesAutocompleteInput
                        label="Location / Address"
                        value={form.location}
                        onChange={value => setForm(f => ({ ...f, location: value }))}
                        onLocationSelected={({ address, lat, lng }) =>
                            setForm(f => ({
                                ...f,
                                location: address,
                                geofence_lat: lat,
                                geofence_lng: lng,
                            }))
                        }
                        labelStyle={labelStyle}
                        inputStyle={inputStyle}
                    />
                    {PREDEFINED_LOCATIONS.length > 0 && (
                        <div>
                            <label style={labelStyle}>Select from saved locations</label>
                            <select
                                style={inputStyle}
                                value={form.locationPreset || ''}
                                onChange={e => {
                                    const value = e.target.value;
                                    setForm(f => {
                                        if (!value) {
                                            const { locationPreset, ...rest } = f;
                                            return { ...rest, locationPreset: '' };
                                        }
                                        const preset = PREDEFINED_LOCATIONS.find(p => p.id === value);
                                        if (!preset) return f;
                                        return {
                                            ...f,
                                            locationPreset: value,
                                            name: f.name || preset.name,
                                            location: preset.address,
                                            geofence_lat: preset.lat,
                                            geofence_lng: preset.lng,
                                            geofence_radius: preset.radius ?? f.geofence_radius,
                                        };
                                    });
                                }}
                            >
                                <option value="">Custom (enter manually)</option>
                                {PREDEFINED_LOCATIONS.map(p => (
                                    <option key={p.id} value={p.id}>
                                        {p.name} — {p.address}
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div>
                            <label style={labelStyle}>Geofence Latitude</label>
                            <input type="number" step="any" style={inputStyle} placeholder="25.2048" value={form.geofence_lat} onChange={e => setForm(f => ({ ...f, geofence_lat: e.target.value }))} />
                        </div>
                        <div>
                            <label style={labelStyle}>Geofence Longitude</label>
                            <input type="number" step="any" style={inputStyle} placeholder="55.2708" value={form.geofence_lng} onChange={e => setForm(f => ({ ...f, geofence_lng: e.target.value }))} />
                        </div>
                    </div>
                    <div>
                        <label style={labelStyle}>Geofence Radius (meters)</label>
                        <input type="number" style={inputStyle} value={form.geofence_radius} onChange={e => setForm(f => ({ ...f, geofence_radius: e.target.value }))} />
                    </div>
                    <div>
                        <label style={labelStyle}>Location on map</label>
                        <LocationMap
                            lat={form.geofence_lat}
                            lng={form.geofence_lng}
                            address={form.location}
                            radiusMeters={form.geofence_radius}
                            height={220}
                        />
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                        <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)} style={{ flex: 1 }}>Cancel</button>
                        <button type="submit" className="btn btn-primary" disabled={saving} style={{ flex: 2, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem' }}>
                            <Save size={15} /> {saving ? 'Saving...' : editProject ? 'Save Changes' : 'Create Project'}
                        </button>
                    </div>
                </form>
            </Modal>
        </div>
    );
};

export default Projects;
