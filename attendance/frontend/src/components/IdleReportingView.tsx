import React, { useState, useEffect } from 'react';
import { Map, Marker, useMap, useMapsLibrary } from '@vis.gl/react-google-maps';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';
import { useMapStore } from '../store/useMapStore';
import { silverMapStyle } from '../utils/mapStyles';
import { generateIdleReportPDF } from '../utils/pdfReports';
import { batchReverseGeocode } from '../utils/geocoding';
import './RouteTrackingView.css';

const toLocalISO = (date: Date) => {
    const offset = date.getTimezoneOffset() * 60000;
    const localDate = new Date(date.getTime() - offset);
    return localDate.toISOString().slice(0, 16);
};

const getDefaultStartDateTime = () => {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    return toLocalISO(now);
};

const getDefaultEndDateTime = () => {
    const now = new Date();
    return toLocalISO(now);
};

export const MapUpdater = ({ center, zoom }: { center: { lat: number, lng: number }, zoom: number }) => {
    const map = useMap();
    useEffect(() => {
        if (!map) return;
        map.panTo(center);
        map.setZoom(zoom);
    }, [map, center, zoom]);
    return null;
};

const IdleReportingView = () => {
    const { user } = useAuthStore();
    const { employees } = useDataStore();
    const { mapCenter, zoom, setMapCenter, setZoom } = useMapStore();
    const { showToast } = useUIStore();

    const [selectedStaff, setSelectedStaff] = useState('');
    const [startDateTime, setStartDateTime] = useState(getDefaultStartDateTime());
    const [endDateTime, setEndDateTime] = useState(getDefaultEndDateTime());
    const [idleThreshold, setIdleThreshold] = useState(30);
    const [isLoading, setIsLoading] = useState(false);
    const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);
    const [addresses, setAddresses] = useState<Record<string, string>>({});
    const [localIdleSpots, setLocalIdleSpots] = useState<any[]>([]);

    const googleMapsApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

    const handleFetchReport = async () => {
        if (!selectedStaff || !startDateTime || !endDateTime || !user?.token) {
            showToast('Please select staff and date/time range', 'error');
            return;
        }

        setIsLoading(true);
        const startUTC = new Date(startDateTime).toISOString();
        const endUTC = new Date(endDateTime).toISOString();

        try {
            const res = await fetch(
                `/hr/idle-report?staffId=${selectedStaff}&startDate=${startUTC}&endDate=${endUTC}&thresholdMins=${idleThreshold}`,
                { headers: { 'Authorization': `Bearer ${user.token}` } }
            );

            if (res.ok) {
                const data = await res.json();
                setLocalIdleSpots(data.idleSpots);

                if (data.idleSpots.length > 0) {
                    setMapCenter({
                        lat: parseFloat(data.idleSpots[0].lat),
                        lng: parseFloat(data.idleSpots[0].lng)
                    });
                    setZoom(14);
                    showToast(`Found ${data.idleSpots.length} idle periods`, 'success');
                } else {
                    showToast('No idle periods found for this range', 'info');
                }
            } else {
                const errData = await res.json();
                showToast(errData.error || 'Failed to fetch report', 'error');
            }
        } catch (err) {
            showToast('Network error', 'error');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <>
            <div className="route-tracking-view sidebar animate-fade-in" style={{ width: '320px', minWidth: '320px', display: 'flex', flexDirection: 'column', padding: '1.2rem', gap: '1.2rem' }}>
                <div className="filter-section">
                    <h3>Idle Reporting</h3>
                    <p className="filter-description">Identify where staff stayed stationary for long periods</p>

                    <div className="filter-group">
                        <label>Staff Member</label>
                        <select
                            value={selectedStaff}
                            onChange={(e) => setSelectedStaff(e.target.value)}
                            className="filter-select"
                            disabled={isLoading}
                        >
                            <option value="">Select Staff...</option>
                            {employees.map(emp => (
                                <option key={emp.staff_id} value={emp.staff_id}>
                                    {emp.staff_id} - {emp.first_name} {emp.last_name}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="filter-group">
                        <label>From Date/Time</label>
                        <input type="datetime-local" value={startDateTime} onChange={(e) => setStartDateTime(e.target.value)} className="filter-input" disabled={isLoading} />
                    </div>

                    <div className="filter-group">
                        <label>To Date/Time</label>
                        <input type="datetime-local" value={endDateTime} onChange={(e) => setEndDateTime(e.target.value)} className="filter-input" disabled={isLoading} />
                    </div>

                    <div className="filter-group">
                        <label>Threshold (Minutes)</label>
                        <input type="number" min="5" max="1440" value={idleThreshold} onChange={(e) => setIdleThreshold(parseInt(e.target.value) || 0)} className="filter-input" disabled={isLoading} />
                        <small className="filter-hint">Min minutes stationary to flag</small>
                    </div>

                    <div className="filter-actions">
                        <button onClick={handleFetchReport} className="hr-btn primary" disabled={isLoading}>{isLoading ? 'Searching...' : 'Generate Report'}</button>
                        <button onClick={() => setLocalIdleSpots([])} className="hr-btn secondary" disabled={isLoading}>Clear</button>
                        {localIdleSpots.length > 0 && (
                            <button
                                onClick={async () => {
                                    if (isGeneratingPDF) return;
                                    setIsGeneratingPDF(true);
                                    try {
                                        showToast('Processing addresses...', 'info');
                                        const pointsToGeocode = localIdleSpots.map(s => ({
                                            latitude: s.lat,
                                            longitude: s.lng
                                        }));
                                        const newAddresses = await batchReverseGeocode(pointsToGeocode, googleMapsApiKey);
                                        setAddresses(prev => ({ ...prev, ...newAddresses }));
                                        const emp = employees.find(e => e.staff_id === selectedStaff);
                                        const staffName = emp ? `${emp.first_name} ${emp.last_name} ` : selectedStaff;
                                        generateIdleReportPDF(localIdleSpots, selectedStaff, staffName, startDateTime, endDateTime, idleThreshold, newAddresses);
                                        showToast('Report generated', 'success');
                                    } catch (err) {
                                        console.error(err); showToast('Failed to generate PDF', 'error');
                                    } finally { setIsGeneratingPDF(false); }
                                }}
                                className="btn-download" disabled={isGeneratingPDF}
                            >
                                {isGeneratingPDF ? 'Processing...' : 'Detailed PDF Report'}
                            </button>
                        )}
                    </div>
                </div >

                {
                    localIdleSpots.length > 0 && (
                        <div className="route-stats">
                            <div className="stat-card-route">
                                <span className="rt-stat-icon">ID</span>
                                <div className="stat-content">
                                    <span className="rt-stat-label">Staff Member</span>
                                    <span className="rt-stat-value">{employees.find(e => e.staff_id === selectedStaff)?.first_name || selectedStaff}</span>
                                    <span className="rt-stat-subtext">{selectedStaff}</span>
                                </div>
                            </div>
                            <div className="stat-card-route">
                                <div className="rt-stat-icon">ST</div>
                                <div className="stat-content"><span className="rt-stat-label">Idle Occurrences</span><span className="rt-stat-value">{localIdleSpots.length} Total</span></div>
                            </div>
                        </div>
                    )
                }

                {
                    localIdleSpots.length > 0 && (
                        <div className="route-timeline">
                            {localIdleSpots.map((spot, index) => {
                                const addrKey = `${parseFloat(spot.lat).toFixed(5)},${parseFloat(spot.lng).toFixed(5)} `;
                                return (
                                    <div key={index} className="timeline-item" onClick={() => {
                                        setMapCenter({ lat: spot.lat, lng: spot.lng });
                                        setZoom(18);
                                    }}>
                                        <div className="timeline-icon">ST</div>
                                        <div className="timeline-content">
                                            <div className="timeline-title">{spot.duration}m Stationary</div>
                                            <div className="timeline-desc">{new Date(spot.startTime).toLocaleTimeString()} — {new Date(spot.endTime).toLocaleTimeString()}</div>
                                            {addresses[addrKey] && <div className="timeline-address" style={{ fontSize: '0.75rem', marginTop: '4px', color: '#667eea' }}>{addresses[addrKey]}</div>}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )
                }
            </div >
            <main className="map-container animate-fade-in">
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
                    <IdleHotSpots spots={localIdleSpots} />
                </Map>
            </main>
        </>
    );
};

export const IdleHotSpots = ({ spots }: { spots: any[] }) => {
    const map = useMap();
    const mapsLib = useMapsLibrary('maps');

    if (!spots || spots.length === 0 || !mapsLib) return null;
    const circleSymbol = (mapsLib as any)?.SymbolPath?.CIRCLE ?? 0;

    return (
        <>
            {spots.map((spot, i) => {
                const lat = parseFloat(spot.lat);
                const lng = parseFloat(spot.lng);
                if (isNaN(lat) || isNaN(lng)) return null;

                const intensity = Math.min(spot.duration / 60, 1);
                const scale = 15 + (intensity * 10);

                return (
                    <React.Fragment key={`spot-${i}`}>
                        {/* Bloom Marker */}
                        <Marker
                            position={{ lat, lng }}
                            icon={{
                                path: circleSymbol,
                                scale: scale,
                                fillColor: '#fb923c',
                                fillOpacity: 0.35 + (intensity * 0.2),
                                strokeColor: '#f97316',
                                strokeOpacity: 0.6,
                                strokeWeight: 2
                            }}
                            zIndex={3000}
                        />
                        {/* Core and Label Marker */}
                        <Marker
                            position={{ lat, lng }}
                            icon={{
                                path: circleSymbol,
                                scale: scale * 0.4,
                                fillColor: '#ef4444',
                                fillOpacity: 0.8,
                                strokeColor: '#ef4444',
                                strokeWeight: 0
                            }}
                            label={{
                                text: `${spot.duration} m`,
                                color: 'white',
                                fontWeight: 'bold',
                                fontSize: '11px',
                                className: 'hot-spot-label'
                            }}
                            zIndex={3001}
                            title={`${spot.duration}m stationary`}
                        />
                    </React.Fragment>
                );
            })}
        </>
    );
};

export default IdleReportingView;
