import React, { useMemo } from 'react';
import { Map, Marker, AdvancedMarker, Pin, InfoWindow, useMap } from '@vis.gl/react-google-maps';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useMapStore } from '../store/useMapStore';
import { silverMapStyle } from '../utils/mapStyles';
import { Employee, EmployeeLocation } from '../types';

export const MapUpdater = ({ center, zoom }: { center: { lat: number, lng: number }, zoom: number }) => {
    const map = useMap();
    React.useEffect(() => {
        if (!map) return;
        map.panTo(center);
        map.setZoom(zoom);
    }, [map, center, zoom]);
    return null;
};

export default function MapDashboard() {
    const { user } = useAuthStore();
    const {
        employees, sites, onlineEmployees, geoFenceAlerts,
        selectedSites, setSelectedSites
    } = useDataStore();

    const {
        searchQuery, setSearchQuery, selectedId, setSelectedId,
        mapCenter, setMapCenter, zoom, setZoom
    } = useMapStore();

    // Re-implementing sidebar logic from HRDashboard
    const sidebarEmployees = useMemo(() => {
        let filtered = employees.filter(emp => {
            const matchesSearch = emp.staff_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
                `${emp.first_name} ${emp.last_name} `.toLowerCase().includes(searchQuery.toLowerCase());

            let matchesSite = true;
            if (selectedSites.length > 0) {
                if (selectedSites.includes(-1 as any)) {
                    matchesSite = !emp.site_id || selectedSites.includes(emp.site_id);
                } else {
                    matchesSite = !!emp.site_id && selectedSites.includes(emp.site_id);
                }
            }
            return matchesSearch && matchesSite;
        });
        return filtered;
    }, [employees, searchQuery, selectedSites]);

    const handleSelectEmployee = (staffId: string) => {
        setSelectedId(staffId);
        const loc = onlineEmployees[staffId];
        if (loc) {
            setMapCenter({ lat: loc.latitude, lng: loc.longitude });
            setZoom(15);
        }
    };

    return (
        <>
            <aside className="sidebar">
                <div className="sidebar-header">
                    <h3>Employees</h3>
                    <div className="search-container">
                        <select
                            className="sidebar-search"
                            style={{ marginBottom: '0.5rem' }}
                            value={selectedSites[0] || ''}
                            onChange={(e) => setSelectedSites(e.target.value ? [parseInt(e.target.value)] : [])}
                        >
                            <option value="">All Sites</option>
                            {Array.isArray(sites) && sites.map(s => (
                                <option key={s.id} value={s.id}>{s.name}</option>
                            ))}
                        </select>
                        <input
                            type="text"
                            placeholder="Search Staff ID..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="sidebar-search"
                        />
                    </div>
                </div>
                <div className="employee-list">
                    {sidebarEmployees.map(emp => (
                        <div
                            key={emp.id}
                            className={`list - item ${onlineEmployees[emp.staff_id] ? 'online' : 'offline'} ${selectedId === emp.staff_id ? 'selected' : ''} `}
                            onClick={() => handleSelectEmployee(emp.staff_id)}
                        >
                            <div className="item-main">
                                <div className="name-box" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    {emp.photo_url ? (
                                        <img src={emp.photo_url} alt="" style={{ width: '32px', height: '32px', borderRadius: '50%', objectFit: 'cover' }} />
                                    ) : (
                                        <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px', color: '#64748b' }}>
                                            {(emp.first_name || emp.staff_id || '?').charAt(0).toUpperCase()}
                                        </div>
                                    )}
                                    <div>
                                        <div className="staff-name">{emp.staff_id}</div>
                                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{emp.department_name}</div>
                                    </div>
                                    {emp.isGuest && <span className="guest-badge">Guest</span>}
                                </div>
                                <span className="status-indicator"></span>
                            </div>
                            {onlineEmployees[emp.staff_id] && (
                                <div className="item-meta">
                                    Last update: {onlineEmployees[emp.staff_id].lastSeen}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
                <div className="alerts-sub-header" style={{
                    marginTop: '1rem',
                    padding: '0.5rem 1rem', fontSize: '0.8rem', fontWeight: 600,
                    color: '#ef4444', background: '#fee2e2', display: 'flex', alignItems: 'center', justifyContent: 'space-between'
                }}>
                    <span>Geo Fence Alerts ({geoFenceAlerts.length})</span>
                </div>
                {geoFenceAlerts.length > 0 && (
                    <div className="alerts-list" style={{ maxHeight: '150px', overflowY: 'auto', background: '#fff5f5' }}>
                        {geoFenceAlerts.map(alert => (
                            <div key={alert.id} className="alert-item" style={{
                                padding: '0.5rem 1rem', borderBottom: '1px solid #fecaca', fontSize: '0.8rem'
                            }}>
                                <div style={{ fontWeight: 600, color: '#b91c1c' }}>{alert.first_name || alert.staff_id}</div>
                                <div style={{ color: '#ef4444' }}>{alert.message}</div>
                                <div style={{ fontSize: '0.7rem', color: '#991b1b', marginTop: '2px' }}>
                                    {new Date(alert.created_at).toLocaleTimeString()}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </aside>

            <main className="map-container">
                <Map
                    defaultCenter={mapCenter}
                    defaultZoom={zoom}
                    gestureHandling={'greedy'}
                    disableDefaultUI={false}
                    zoomControl={true}
                    mapTypeControl={true}
                    streetViewControl={false}
                    fullscreenControl={true}
                    className="google-map"
                    styles={silverMapStyle}
                >
                    <MapUpdater center={mapCenter} zoom={zoom} />
                    {/* Site Marker if active */}
                    {selectedSites.length === 1 && sites.find(s => s.id === selectedSites[0])?.latitude && (
                        <Marker
                            position={{
                                lat: parseFloat(sites.find(s => s.id === (selectedSites[0] as number))!.latitude),
                                lng: parseFloat(sites.find(s => s.id === (selectedSites[0] as number))!.longitude)
                            }}
                            label={{ text: "📍 Site Location", className: 'site-label' }}
                        />
                    )}

                    {(Object.values(onlineEmployees) as EmployeeLocation[])
                        .filter(loc => {
                            const matchesSearch = loc.employeeId.toLowerCase().includes(searchQuery.toLowerCase());

                            // Apply site filter
                            let matchesSite = true;
                            if (selectedSites.length > 0) {
                                matchesSite = selectedSites.includes(loc.siteId as number);
                            }

                            return matchesSearch && matchesSite;
                        })
                        .map((loc) => {
                            const isVehicle = (loc as any).departmentName === 'Vehicle' || (loc as any).department_name === 'Vehicle';
                            const iconUrl = isVehicle
                                ? `data:image/svg+xml;charset=UTF-8,${encodeURIComponent('<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><circle cx="16" cy="16" r="14" fill="#6366f1" stroke="white" stroke-width="2"/><text x="16" y="21" font-size="14" text-anchor="middle">🚙</text></svg>')}`
                                : `data:image/svg+xml;charset=UTF-8,${encodeURIComponent('<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><circle cx="16" cy="16" r="14" fill="#10b981" stroke="white" stroke-width="2"/><text x="16" y="21" font-size="14" text-anchor="middle">🧑‍💼</text></svg>')}`;

                            return (
                                <React.Fragment key={loc.employeeId}>
                                    <Marker
                                        position={{ lat: loc.latitude, lng: loc.longitude }}
                                        onClick={() => setSelectedId(loc.employeeId)}
                                        icon={{ url: iconUrl, scaledSize: { width: 32, height: 32 } as any }}
                                    />
                                    {selectedId === loc.employeeId && (
                                        <InfoWindow
                                            position={{ lat: loc.latitude, lng: loc.longitude }}
                                            onCloseClick={() => setSelectedId(null)}
                                        >
                                            <div className="map-popup">
                                                {(loc.photoUrl || loc.photo_url) && (
                                                    <img src={loc.photoUrl || loc.photo_url} alt="Staff" style={{ width: '40px', height: '40px', borderRadius: '50%', objectFit: 'cover', marginBottom: '8px' }} />
                                                )}
                                                <strong>{loc.departmentName || loc.department_name || 'Staff'}</strong>
                                                <div style={{ fontSize: '0.9rem', color: '#555' }}>ID: {loc.employeeId}</div>
                                                <p style={{ margin: '4px 0', fontSize: '0.8rem' }}>Last seen: {loc.lastSeen}</p>
                                                <small>
                                                    {typeof loc.latitude === 'number' ? loc.latitude.toFixed(5) : loc.latitude},
                                                    {typeof loc.longitude === 'number' ? loc.longitude.toFixed(5) : loc.longitude}
                                                </small>
                                            </div>
                                        </InfoWindow>
                                    )}
                                </React.Fragment>
                            );
                        })}
                </Map>
            </main>
        </>
    );
}