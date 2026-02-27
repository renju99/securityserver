import React, { useState, useEffect } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';

interface BiometricsViewProps {
    setShowModal: (show: boolean) => void;
    setCurrentDevice: (device: any) => void;
    onDelete: (id: number) => void;
}

const BiometricsView = ({ setShowModal, setCurrentDevice, onDelete }: BiometricsViewProps) => {
    const { user } = useAuthStore();
    const {
        biometricDevices, biometricLogs, fetchBiometricLogs
    } = useDataStore();
    const { showToast } = useUIStore();

    const [subTab, setSubTab] = useState<'logs' | 'devices'>('logs');
    const [staffIdFilter, setStaffIdFilter] = useState('');
    const [deviceIdFilter, setDeviceIdFilter] = useState('');

    useEffect(() => {
        if (user?.token) {
            fetchBiometricLogs(user.token, staffIdFilter, deviceIdFilter);
        }
    }, [staffIdFilter, deviceIdFilter, user?.token, fetchBiometricLogs]);

    const handleFetchLogs = () => {
        if (user?.token) fetchBiometricLogs(user.token, staffIdFilter, deviceIdFilter);
    };

    return (
        <div className="management-view" style={{ padding: '1.5rem' }}>
            <div className="mgmt-header" style={{ marginBottom: '2rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <h2 style={{ fontSize: '1.875rem', fontWeight: 800, color: '#0f172a', margin: 0 }}>🤳 Biometric Access</h2>
                        <p style={{ color: '#64748b', marginTop: '0.5rem', fontSize: '1rem' }}>Monitor biometric terminal logs and manage devices</p>
                    </div>
                </div>
            </div>

            <div className="mgmt-tabs" style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '1rem' }}>
                <button
                    className={`tab-btn ${subTab === 'logs' ? 'active' : ''}`}
                    onClick={() => setSubTab('logs')}
                    style={{ background: subTab === 'logs' ? '#eff6ff' : 'transparent', border: 'none', color: subTab === 'logs' ? '#2563eb' : '#64748b', padding: '0.75rem 1.5rem', borderRadius: '10px', fontWeight: 600, cursor: 'pointer' }}
                >🕒 Access Logs</button>
                <button
                    className={`tab-btn ${subTab === 'devices' ? 'active' : ''}`}
                    onClick={() => setSubTab('devices')}
                    style={{ background: subTab === 'devices' ? '#eff6ff' : 'transparent', border: 'none', color: subTab === 'devices' ? '#2563eb' : '#64748b', padding: '0.75rem 1.5rem', borderRadius: '10px', fontWeight: 600, cursor: 'pointer' }}
                >📟 Managed Devices</button>
            </div>

            {subTab === 'logs' ? (
                <div className="logs-tab">
                    <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', background: '#f8fafc', padding: '1rem', borderRadius: '12px' }}>
                        <input
                            type="text"
                            placeholder="Filter by Staff ID..."
                            value={staffIdFilter}
                            onChange={(e) => setStaffIdFilter(e.target.value)}
                            style={{ padding: '0.625rem', borderRadius: '8px', border: '1px solid #cbd5e1', flex: 1 }}
                        />
                        <button onClick={handleFetchLogs} className="btn-primary" style={{ padding: '0.625rem 1.25rem', borderRadius: '8px', background: '#2563eb', color: 'white', border: 'none', fontWeight: 600, cursor: 'pointer' }}>Search</button>
                    </div>

                    <div className="mgmt-table-container">
                        <table className="mgmt-table">
                            <thead>
                                <tr>
                                    <th>Photo</th>
                                    <th>Staff ID</th>
                                    <th>Name</th>
                                    <th>Terminal</th>
                                    <th>Time</th>
                                </tr>
                            </thead>
                            <tbody>
                                {biometricLogs.map((log) => (
                                    <tr key={log.id}>
                                        <td>
                                            {log.photo_url ? (
                                                <img src={log.photo_url} alt="Log" style={{ width: '40px', height: '40px', borderRadius: '8px', objectFit: 'cover' }} />
                                            ) : (
                                                <div style={{ width: '40px', height: '40px', background: '#f1f5f9', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>👤</div>
                                            )}
                                        </td>
                                        <td><strong>{log.staff_id}</strong></td>
                                        <td>{log.first_name} {log.last_name}</td>
                                        <td>{log.device_name}</td>
                                        <td>{new Date(log.timestamp).toLocaleString()}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            ) : (
                <div className="devices-tab">
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1.5rem' }}>
                        <button
                            className="btn-primary"
                            onClick={() => setShowModal(true)}
                        >+ Add Terminal</button>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '1.5rem' }}>
                        {biometricDevices.map((device) => (
                            <div key={device.id} className="card" style={{ padding: '1.5rem' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                    <div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                            <h3 style={{ margin: 0 }}>{device.name}</h3>
                                            <span style={{ fontSize: '0.75rem', background: device.is_active ? '#dcfce7' : '#fee2e2', color: device.is_active ? '#15803d' : '#b91c1c', padding: '0.2rem 0.5rem', borderRadius: '12px', fontWeight: 600 }}>
                                                {device.is_active ? 'Online' : 'Offline'}
                                            </span>
                                        </div>
                                        <p style={{ color: '#64748b', fontSize: '0.875rem', marginTop: '0.5rem' }}>{device.ip_address}:{device.port}</p>
                                    </div>
                                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                                        <button className="btn-icon" onClick={() => setCurrentDevice(device)}>✏️</button>
                                        <button className="btn-icon delete" onClick={() => onDelete(device.id)}>🗑️</button>
                                    </div>
                                </div>
                                <div style={{ marginTop: '1rem', borderTop: '1px solid #f1f5f9', paddingTop: '1rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                                    <div>
                                        <span style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block' }}>Assigned Site</span>
                                        <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>{device.site_name || 'Global'}</span>
                                    </div>
                                    <div>
                                        <span style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block' }}>Device Type</span>
                                        <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>{device.type}</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default BiometricsView;