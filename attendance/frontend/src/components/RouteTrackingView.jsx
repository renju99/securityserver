import React, { useState, useEffect } from 'react';
import { Marker, useMap, useMapsLibrary } from '@vis.gl/react-google-maps';
import { generateRouteTrackingPDF } from '../utils/pdfReports';
import { batchReverseGeocode } from '../utils/geocoding';
import './RouteTrackingView.css';

const RouteTrackingView = ({ user, employees, onMapUpdate, showToast, routeData, onRouteDataChange: setRouteData, googleMapsApiKey }) => {
    // Helper to get local ISO string (YYYY-MM-DDTHH:mm) for datetime-local input
    const toLocalISO = (date) => {
        const offset = date.getTimezoneOffset() * 60000;
        const localDate = new Date(date - offset);
        return localDate.toISOString().slice(0, 16);
    };

    // Get default date/time values (today)
    const getDefaultStartDateTime = () => {
        const now = new Date();
        now.setHours(0, 0, 0, 0);
        return toLocalISO(now);
    };

    const getDefaultEndDateTime = () => {
        const now = new Date();
        return toLocalISO(now);
    };

    const [selectedStaff, setSelectedStaff] = useState('');
    const [startDateTime, setStartDateTime] = useState(getDefaultStartDateTime());
    const [endDateTime, setEndDateTime] = useState(getDefaultEndDateTime());
    const [isLoading, setIsLoading] = useState(false);
    const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);
    const [addresses, setAddresses] = useState({});

    const handleFetchRoute = async () => {
        if (!selectedStaff || !startDateTime || !endDateTime) {
            showToast('Please select staff and date/time range', 'warning');
            return;
        }

        setIsLoading(true);

        // Convert local datetime strings to UTC ISO strings for the API
        const startUTC = new Date(startDateTime).toISOString();
        const endUTC = new Date(endDateTime).toISOString();

        try {
            const res = await fetch(
                `/api/hr/route-tracking?staffId=${encodeURIComponent(selectedStaff)}&startDate=${encodeURIComponent(startUTC)}&endDate=${encodeURIComponent(endUTC)}`,
                { headers: { 'Authorization': `Bearer ${user.token}` } }
            );

            if (res.ok) {
                const data = await res.json();
                setRouteData(data);

                if (data.locations.length === 0) {
                    showToast('No location data found for this time period', 'info');
                } else {
                    showToast(`Route loaded: ${data.totalPoints} location points`, 'success');

                    // Update map center to first location
                    if (data.locations.length > 0) {
                        onMapUpdate({
                            lat: parseFloat(data.locations[0].latitude),
                            lng: parseFloat(data.locations[0].longitude)
                        }, 13);
                    }
                }
            } else {
                const errData = await res.json();
                showToast(errData.error || 'Failed to fetch route', 'error');
            }
        } catch (err) {
            console.error('Route tracking debug info:', {
                error: err.message,
                stack: err.stack,
                staffId: selectedStaff,
                start: startDateTime,
                end: endDateTime
            });
            showToast(`Error: ${err.message || 'Network issue'}. Please try again.`, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const handleClearRoute = () => {
        setRouteData(null);
        setSelectedStaff('');
        setStartDateTime(getDefaultStartDateTime());
        setEndDateTime(getDefaultEndDateTime());
        showToast('Route cleared', 'info');
    };

    const calculateDistance = (lat1, lon1, lat2, lon2) => {
        const R = 6371e3; // metres
        const φ1 = lat1 * Math.PI / 180;
        const φ2 = lat2 * Math.PI / 180;
        const Δφ = (lat2 - lat1) * Math.PI / 180;
        const Δλ = (lon2 - lon1) * Math.PI / 180;

        const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return R * c;
    };

    const getTotalDistance = () => {
        if (!routeData || routeData.locations.length < 2) return 0;

        let total = 0;
        for (let i = 1; i < routeData.locations.length; i++) {
            const prev = routeData.locations[i - 1];
            const curr = routeData.locations[i];
            total += calculateDistance(
                parseFloat(prev.latitude),
                parseFloat(prev.longitude),
                parseFloat(curr.latitude),
                parseFloat(curr.longitude)
            );
        }
        return (total / 1000).toFixed(2); // Convert to km
    };

    const getDuration = () => {
        if (!routeData || routeData.locations.length < 2) return '0h 0m';

        const start = new Date(routeData.locations[0].timestamp);
        const end = new Date(routeData.locations[routeData.locations.length - 1].timestamp);
        const diffMs = end - start;
        const hours = Math.floor(diffMs / 3600000);
        const minutes = Math.floor((diffMs % 3600000) / 60000);
        return `${hours}h ${minutes}m`;
    };

    return (
        <div className="route-tracking-view">
            <div className="filter-section">
                <h3>🗺️ Route Tracking</h3>
                <p className="filter-description">Track staff movement by selecting a staff member and date range</p>

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
                    <input
                        type="datetime-local"
                        value={startDateTime}
                        onChange={(e) => setStartDateTime(e.target.value)}
                        className="filter-input"
                        disabled={isLoading}
                    />
                </div>

                <div className="filter-group">
                    <label>To Date/Time</label>
                    <input
                        type="datetime-local"
                        value={endDateTime}
                        onChange={(e) => setEndDateTime(e.target.value)}
                        className="filter-input"
                        disabled={isLoading}
                    />
                </div>

                <div className="filter-actions">
                    <button
                        onClick={handleFetchRoute}
                        className="btn-primary"
                        disabled={isLoading || !selectedStaff || !startDateTime || !endDateTime}
                    >
                        {isLoading ? '⏳ Loading...' : '📍 Track Route'}
                    </button>
                    {routeData && (
                        <button
                            onClick={handleClearRoute}
                            className="btn-secondary"
                            disabled={isLoading}
                        >
                            🗑️ Clear
                        </button>
                    )}
                    {routeData && routeData.locations.length > 0 && (
                        <button
                            onClick={async () => {
                                if (isGeneratingPDF) return;
                                setIsGeneratingPDF(true);
                                try {
                                    showToast('Processing addresses for detailed report...', 'info');

                                    // 1. Identify which points need geocoding
                                    const locations = routeData.locations;
                                    const start = locations[0];
                                    const end = locations[locations.length - 1];

                                    // Get 30-min interval breakdown
                                    const intervalMs = 30 * 60 * 1000;
                                    const pointsToGeocode = [start, end];
                                    let lastTime = new Date(start.timestamp).getTime();

                                    locations.forEach(loc => {
                                        const time = new Date(loc.timestamp).getTime();
                                        if (time - lastTime >= intervalMs) {
                                            pointsToGeocode.push(loc);
                                            lastTime = time;
                                        }
                                    });

                                    // 2. Batch reverse geocode them
                                    const newAddresses = await batchReverseGeocode(pointsToGeocode, googleMapsApiKey);
                                    setAddresses(prev => ({ ...prev, ...newAddresses }));

                                    // 3. Generate PDF with addresses
                                    const fileName = generateRouteTrackingPDF(routeData, newAddresses);
                                    showToast(`PDF downloaded: ${fileName}`, 'success');
                                } catch (err) {
                                    console.error('PDF Download Error:', err);
                                    showToast('Failed to generate PDF. Check console for details.', 'error');
                                } finally {
                                    setIsGeneratingPDF(false);
                                }
                            }}
                            className="btn-download"
                            disabled={isGeneratingPDF}
                        >
                            {isGeneratingPDF ? '⏳ Processing...' : '📄 Detailed PDF Report'}
                        </button>
                    )}
                </div>
            </div>

            {routeData && routeData.locations.length > 0 && (
                <>
                    <div className="route-stats">
                        <div className="stat-card-route">
                            <span className="rt-stat-icon">👤</span>
                            <div className="stat-content">
                                <span className="rt-stat-label">Staff Member</span>
                                <span className="rt-stat-value">{(routeData.employee.firstName || routeData.employee.lastName) ? `${routeData.employee.firstName || ''} ${routeData.employee.lastName || ''}`.trim() : 'Unnamed Staff'}</span>
                                <span className="rt-stat-subtext">{routeData.employee.staffId}</span>
                            </div>
                        </div>

                        <div className="stat-card-route">
                            <span className="rt-stat-icon">📏</span>
                            <div className="stat-content">
                                <span className="rt-stat-label">Total Distance</span>
                                <span className="rt-stat-value">{getTotalDistance()} km</span>
                            </div>
                        </div>

                        <div className="stat-card-route">
                            <span className="rt-stat-icon">⏱️</span>
                            <div className="stat-content">
                                <span className="rt-stat-label">Duration</span>
                                <span className="rt-stat-value">{getDuration()}</span>
                            </div>
                        </div>

                        <div className="stat-card-route">
                            <span className="rt-stat-icon">📍</span>
                            <div className="stat-content">
                                <span className="rt-stat-label">Location Points</span>
                                <span className="rt-stat-value">{routeData.totalPoints}</span>
                            </div>
                        </div>

                        {routeData.employee.siteName && (
                            <div className="stat-card-route">
                                <span className="rt-stat-icon">🏢</span>
                                <div className="stat-content">
                                    <span className="rt-stat-label">Assigned Site</span>
                                    <span className="rt-stat-value">{routeData.employee.siteName}</span>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="route-timeline">
                        <div className="timeline-item">
                            <span className="timeline-icon start">🟢</span>
                            <div className="timeline-content">
                                <span className="timeline-label">From</span>
                                <span className="timeline-time">
                                    {new Date(routeData.locations[0].timestamp).toLocaleString()}
                                </span>
                                {addresses[`${parseFloat(routeData.locations[0].latitude).toFixed(5)},${parseFloat(routeData.locations[0].longitude).toFixed(5)}`] && (
                                    <div className="timeline-address" style={{ fontSize: '0.75rem', marginTop: '4px', color: '#6366f1' }}>
                                        📍 {addresses[`${parseFloat(routeData.locations[0].latitude).toFixed(5)},${parseFloat(routeData.locations[0].longitude).toFixed(5)}`]}
                                    </div>
                                )}
                            </div>
                        </div>
                        <div className="timeline-item">
                            <span className="timeline-icon end">🔴</span>
                            <div className="timeline-content">
                                <span className="timeline-label">To</span>
                                <span className="timeline-time">
                                    {new Date(routeData.locations[routeData.locations.length - 1].timestamp).toLocaleString()}
                                </span>
                                {addresses[`${parseFloat(routeData.locations[routeData.locations.length - 1].latitude).toFixed(5)},${parseFloat(routeData.locations[routeData.locations.length - 1].longitude).toFixed(5)}`] && (
                                    <div className="timeline-address" style={{ fontSize: '0.75rem', marginTop: '4px', color: '#6366f1' }}>
                                        📍 {addresses[`${parseFloat(routeData.locations[routeData.locations.length - 1].latitude).toFixed(5)},${parseFloat(routeData.locations[routeData.locations.length - 1].longitude).toFixed(5)}`]}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

// Export the polyline rendering component separately for use in the map
export const RoutePolyline = ({ routeData, idleThreshold = 30 }) => {
    const map = useMap();
    const mapsLib = useMapsLibrary('maps');

    useEffect(() => {
        if (!map || !mapsLib || !routeData || !routeData.locations || routeData.locations.length < 2) {
            return;
        }

        const rawPath = routeData.locations.map(loc => ({
            lat: parseFloat(loc.latitude),
            lng: parseFloat(loc.longitude)
        })).filter(p => !isNaN(p.lat) && !isNaN(p.lng));

        if (rawPath.length < 2) return;

        // Thin out the path for the polyline if it's very large (performance)
        // Keep up to 5000 points for a detailed line
        const thinFactor = Math.ceil(rawPath.length / 5000);
        const path = thinFactor > 1
            ? rawPath.filter((_, i) => i % thinFactor === 0 || i === rawPath.length - 1)
            : rawPath;

        // Create polyline using the maps library
        const polyline = new mapsLib.Polyline({
            path: path,
            geodesic: true,
            strokeColor: '#3b82f6', // Bright Blue
            strokeOpacity: 0.9,
            strokeWeight: 6,
            map: map,
            zIndex: 4000
        });

        // Cleanup
        return () => polyline.setMap(null);
    }, [map, mapsLib, routeData]);

    if (!routeData || !routeData.locations || routeData.locations.length === 0 || !mapsLib) return null;

    const rawPath = routeData.locations.map(loc => ({
        lat: parseFloat(loc.latitude),
        lng: parseFloat(loc.longitude),
        timestamp: loc.timestamp
    })).filter(p => !isNaN(p.lat) && !isNaN(p.lng));

    if (rawPath.length === 0) return null;

    const startPoint = rawPath[0];
    const endPoint = rawPath[rawPath.length - 1];

    // Helper to calculate distance for detection
    const getDist = (p1, p2) => {
        const R = 6371e3;
        const φ1 = p1.lat * Math.PI / 180;
        const φ2 = p2.lat * Math.PI / 180;
        const Δφ = (p2.lat - p1.lat) * Math.PI / 180;
        const Δλ = (p2.lng - p1.lng) * Math.PI / 180;
        const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    };

    // Idle Spots Detection Logic
    const getIdleSpots = () => {
        const spots = [];
        if (rawPath.length < 2) return spots;

        let currentGroup = [rawPath[0]];
        const thresholdMs = idleThreshold * 60 * 1000;

        for (let i = 1; i < rawPath.length; i++) {
            const lastPoint = currentGroup[currentGroup.length - 1];
            const currentPoint = rawPath[i];

            // Distance check (30m radius)
            const dist = getDist(currentGroup[0], currentPoint);

            if (dist < 30) {
                currentGroup.push(currentPoint);
            } else {
                // Check duration of previous group
                const startTime = new Date(currentGroup[0].timestamp);
                const endTime = new Date(currentGroup[currentGroup.length - 1].timestamp);
                const duration = endTime - startTime;

                if (duration >= thresholdMs) {
                    spots.push({
                        lat: currentGroup[0].lat,
                        lng: currentGroup[0].lng,
                        duration: Math.round(duration / 60000),
                        startTime: currentGroup[0].timestamp,
                        endTime: currentGroup[currentGroup.length - 1].timestamp
                    });
                }
                currentGroup = [currentPoint];
            }
        }

        // Check last group
        const startTime = new Date(currentGroup[0].timestamp);
        const endTime = new Date(currentGroup[currentGroup.length - 1].timestamp);
        const duration = endTime - startTime;
        if (duration >= thresholdMs) {
            spots.push({
                lat: currentGroup[0].lat,
                lng: currentGroup[0].lng,
                duration: Math.round(duration / 60000),
                startTime: currentGroup[0].timestamp,
                endTime: currentGroup[currentGroup.length - 1].timestamp
            });
        }

        return spots;
    };

    const idleSpots = getIdleSpots();

    // Hourly Points Sampling for breadcrumbs (excluding idle spots to avoid clutter)
    const getHourlyPoints = () => {
        const hourly = [];
        const seenHours = new Set();

        rawPath.forEach(point => {
            const date = new Date(point.timestamp);
            const hourKey = `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}-${date.getHours()}`;

            if (!seenHours.has(hourKey)) {
                seenHours.add(hourKey);
                hourly.push(point);
            }
        });

        return hourly;
    };

    const breadcrumbs = getHourlyPoints();
    const circleSymbol = mapsLib?.SymbolPath?.CIRCLE ?? 0;

    return (
        <>
            {/* Idle Spots Markers */}
            {idleSpots.map((spot, index) => (
                <Marker
                    key={`idle-${index}`}
                    position={{ lat: spot.lat, lng: spot.lng }}
                    icon={{
                        path: circleSymbol,
                        scale: 25,
                        fillColor: '#f59e0b', // Amber/Orange
                        fillOpacity: 0.3,
                        strokeColor: '#f59e0b',
                        strokeWeight: 2,
                        strokeOpacity: 0.8
                    }}
                    zIndex={4500}
                    title={`Stayed here for ${spot.duration} minutes\nFrom: ${new Date(spot.startTime).toLocaleTimeString()}\nTo: ${new Date(spot.endTime).toLocaleTimeString()}`}
                />
            ))}

            {/* Markers for Hourly Points (breadcrumbs) */}
            {breadcrumbs.map((loc, index) => (
                <Marker
                    key={`hourly-${index}`}
                    position={loc}
                    icon={{
                        path: circleSymbol,
                        scale: 6,
                        fillColor: '#6366f1',
                        fillOpacity: 0.8,
                        strokeColor: '#ffffff',
                        strokeWeight: 1.5
                    }}
                    zIndex={3005 + index}
                    title={`Time: ${new Date(loc.timestamp).toLocaleString()}`}
                />
            ))}

            {/* Start and End Markers */}
            {startPoint && (
                <Marker
                    key="start-marker"
                    position={startPoint}
                    label={{
                        text: "START",
                        color: "#ffffff",
                        fontWeight: "bold",
                        fontSize: "12px"
                    }}
                    icon={{
                        path: circleSymbol,
                        scale: 18,
                        fillColor: '#10b981',
                        fillOpacity: 1,
                        strokeColor: '#ffffff',
                        strokeWeight: 2
                    }}
                    zIndex={5000}
                />
            )}
            {endPoint && (
                <Marker
                    key="end-marker"
                    position={endPoint}
                    label={{
                        text: "END",
                        color: "#ffffff",
                        fontWeight: "bold",
                        fontSize: "12px"
                    }}
                    icon={{
                        path: circleSymbol,
                        scale: 18,
                        fillColor: '#ef4444',
                        fillOpacity: 1,
                        strokeColor: '#ffffff',
                        strokeWeight: 2
                    }}
                    zIndex={5000}
                />
            )}
        </>
    );
};

export default RouteTrackingView;
