import React, { useState, useEffect } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';
import { getBiometricPreset } from '../config/biometricDevicePresets';

interface BiometricsViewProps {
    onAddTerminal: () => void;
    onEditTerminal: (device: any) => void;
    onDelete: (id: number) => void;
}

const BiometricsView = ({ onAddTerminal, onEditTerminal, onDelete }: BiometricsViewProps) => {
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

    const getHealthClass = (status?: string) => {
        if (status === 'healthy') return 'health-healthy';
        if (status === 'stale') return 'health-stale';
        return 'health-offline';
    };

    /** `ip_address` column stores hostname (DynDNS) or numeric IP for ops display. */
    const formatNetworkLine = (device: { ip_address?: string; port?: string }) => {
        const host = (device.ip_address ?? '').trim();
        if (!host) return '—';
        const p = device.port;
        if (p !== undefined && p !== null && String(p).trim() !== '') return `${host}:${p}`;
        return host;
    };

    return (
        <div className="management-view">
            <div className="mgmt-header view-toolbar view-toolbar-spaced">
                <div>
                    <div>
                        <h2 className="view-heading-xl">Biometric Access</h2>
                        <p className="view-subheading">Monitor biometric terminal logs and manage devices</p>
                    </div>
                </div>
            </div>

            <div className="mgmt-tabs section-tabs">
                <button
                    className={`tab-btn ${subTab === 'logs' ? 'active' : ''}`}
                    onClick={() => setSubTab('logs')}
                >Access Logs</button>
                <button
                    className={`tab-btn ${subTab === 'devices' ? 'active' : ''}`}
                    onClick={() => setSubTab('devices')}
                >Managed Devices</button>
            </div>

            {subTab === 'logs' ? (
                <div className="logs-tab">
                    <div className="surface-filter">
                        <input
                            type="text"
                            placeholder="Filter by Staff ID..."
                            value={staffIdFilter}
                            onChange={(e) => setStaffIdFilter(e.target.value)}
                            className="surface-filter-input"
                        />
                        <button onClick={handleFetchLogs} className="hr-btn primary">Search</button>
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
                                                <img src={log.photo_url} alt="Log" className="table-image-sm" />
                                            ) : (
                                                <div className="table-avatar-sm">ID</div>
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
                    {biometricDevices.length > 0 ? (
                        <>
                            <p className="view-subheading" style={{ marginBottom: '1rem', maxWidth: '42rem' }}>
                                Register each terminal once with its type and serial or key so punches can be matched. If the
                                site has no static IP, store the device&apos;s <strong>DynDNS hostname</strong> and port for
                                reachability on the card below. ZKTeco ADMS push still uses the portal URLs from step 3 of the
                                wizard.
                            </p>
                            <div
                                className="device-actions-row"
                                style={{
                                    justifyContent: 'flex-start',
                                    gap: '1rem',
                                    flexWrap: 'wrap',
                                    alignItems: 'center',
                                }}
                            >
                                <button type="button" className="hr-btn primary" onClick={onAddTerminal}>
                                    Configure terminal
                                </button>
                                <span className="view-subheading" style={{ margin: 0, color: '#64748b', fontSize: '0.875rem' }}>
                                    Opens the 5-step wizard (starts at device type; includes connection test).
                                </span>
                            </div>
                            <div className="surface-grid">
                                {biometricDevices.map((device) => {
                                    const preset = getBiometricPreset(device.type);
                                    const keyLabel = preset.deviceKeyLabel || 'Device key';
                                    return (
                                        <div key={device.id} className="surface-card">
                                            <div className="device-card-head">
                                                <div>
                                                    <div className="device-title-row">
                                                        <h3 className="device-title">{device.name}</h3>
                                                        <span className={`status-chip ${device.is_active ? 'online' : 'offline'}`}>
                                                            {device.is_active ? 'Online' : 'Offline'}
                                                        </span>
                                                        <span className={`status-chip ${getHealthClass(device.health_status)}`}>
                                                            {device.health_status || 'unknown'}
                                                        </span>
                                                    </div>
                                                    <p className="device-address">{formatNetworkLine(device)}</p>
                                                    <p
                                                        className="device-last-seen"
                                                        style={{ fontFamily: 'ui-monospace, monospace', fontSize: '0.85rem' }}
                                                    >
                                                        {keyLabel}: {device.device_key || '—'}
                                                    </p>
                                                    <p className="device-last-seen">
                                                        Last seen:{' '}
                                                        {device.last_seen ? new Date(device.last_seen).toLocaleString() : 'Never'}
                                                    </p>
                                                </div>
                                                <div className="device-card-actions">
                                                    <button type="button" className="btn-icon" onClick={() => onEditTerminal(device)}>
                                                        Edit
                                                    </button>
                                                    <button type="button" className="btn-icon delete" onClick={() => onDelete(device.id)}>
                                                        Delete
                                                    </button>
                                                </div>
                                            </div>
                                            <div className="device-meta-grid">
                                                <div>
                                                    <span className="meta-label">Assigned Site</span>
                                                    <span className="meta-value">{device.site_name || 'Global'}</span>
                                                </div>
                                                <div>
                                                    <span className="meta-label">Device Type</span>
                                                    <span className="meta-value">{preset.label}</span>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </>
                    ) : (
                        <div
                            className="surface-card empty-state"
                            style={{ maxWidth: '32rem', margin: '0.5rem auto 0', padding: '2.5rem 2rem' }}
                        >
                            <div className="empty-state-icon" aria-hidden>
                                ⊡
                            </div>
                            <h3 className="empty-state-title">No terminals configured yet</h3>
                            <p className="empty-state-message" style={{ maxWidth: '28rem', margin: '0 auto 1.5rem' }}>
                                Use the wizard to choose your device family, enter its serial or key, and copy push URLs for
                                your installer. For sites without a static public IP, enter the terminal&apos;s DynDNS
                                hostname (and port) in step 3; use step 4 to run server-side connection tests before saving.
                            </p>
                            <button type="button" className="hr-btn primary" onClick={onAddTerminal}>
                                Configure terminal
                            </button>
                            <p className="view-subheading" style={{ margin: '1rem 0 0', fontSize: '0.8125rem', color: '#64748b' }}>
                                Starts at step 1 (device type); save on step 5 after optional tests.
                            </p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default BiometricsView;