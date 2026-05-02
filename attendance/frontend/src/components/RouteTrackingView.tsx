import React, { useState, useEffect } from 'react';
import { Map, Marker, useMap, useMapsLibrary } from '@vis.gl/react-google-maps';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';
import { useMapStore } from '../store/useMapStore';
import { silverMapStyle } from '../utils/mapStyles';
import { generateRouteTrackingPDF } from '../utils/pdfReports';
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

const RouteTrackingView = () => {
    const { user } = useAuthStore();
    const { employees, routeData, setRouteData } = useDataStore();
    const { mapCenter, zoom, setMapCenter, setZoom } = useMapStore();
    const { showToast } = useUIStore();

    const [selectedStaff, setSelectedStaff] = useState('');
    const [startDateTime, setStartDateTime] = useState(getDefaultStartDateTime());
    const [endDateTime, setEndDateTime] = useState(getDefaultEndDateTime());
    const [isLoading, setIsLoading] = useState(false);
    const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);
    const [, setAddresses] = useState<Record<string, string>>({});

    const googleMapsApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

    const handleFetchRoute = async () => {
        if (!selectedStaff || !startDateTime || !endDateTime || !user?.token) {
            showToast('Please select staff and date/time range', 'warning');
            return;
        }

        setIsLoading(true);
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
                    showToast('No location data found', 'info');
                } else {
                    showToast(`Route loaded: ${data.totalPoints} points`, 'success');
                    setMapCenter({
                        lat: parseFloat(data.locations[0].latitude),
                        lng: parseFloat(data.locations[0].longitude)
                    });
                    setZoom(13);
                }
            } else {
                const errData = await res.json();
                showToast(errData.error || 'Failed to fetch route', 'error');
            }
        } catch (err: any) {
            showToast(`Error: ${err.message}`, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const handleClearRoute = () => {
        setRouteData(null);
        setSelectedStaff('');
        setStartDateTime(getDefaultStartDateTime());
        setEndDateTime(getDefaultEndDateTime());
    };

    const calculateDistance = (lat1: number, lon1: number, lat2: number, lon2: number) => {
        const R = 6371e3;
        const phi1 = lat1 * Math.PI / 180;
        const phi2 = lat2 * Math.PI / 180;
        const dphi = (lat2 - lat1) * Math.PI / 180;
        const dlambda = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dphi / 2) * Math.sin(dphi / 2) +
            Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlambda / 2) * Math.sin(dlambda / 2);
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    };

    const getTotalDistance = () => {
        if (!routeData || routeData.locations.length < 2) return 0;
        let total = 0;
        for (let i = 1; i < routeData.locations.length; i++) {
            total += calculateDistance(
                parseFloat(routeData.locations[i - 1].latitude),
                parseFloat(routeData.locations[i - 1].longitude),
                parseFloat(routeData.locations[i].latitude),
                parseFloat(routeData.locations[i].longitude)
            );
        }
        return (total / 1000).toFixed(2);
    };

    const getDuration = () => {
        if (!routeData || routeData.locations.length < 2) return '0h 0m';
        const start = new Date(routeData.locations[0].timestamp).getTime();
        const end = new Date(routeData.locations[routeData.locations.length - 1].timestamp).getTime();
        const diffMs = end - start;
        const hours = Math.floor(diffMs / 3600000);
        const minutes = Math.floor((diffMs % 3600000) / 60000);
        return `${hours}h ${minutes}m`;
    };

    return (
        <>
            <div className="route-tracking-view sidebar animate-fade-in" style={{ width: '320px', minWidth: '320px', display: 'flex', flexDirection: 'column', padding: '1.2rem', gap: '1.2rem' }}>
                <div className="filter-section">
                    <h3>Route Tracking</h3>
                    <div className="filter-group">
                        <label>Staff Member</label>
                        <select value={selectedStaff} onChange={(e) => setSelectedStaff(e.target.value)} className="filter-select" disabled={isLoading}>
                            <option value="">Select Staff...</option>
                            {employees.map(emp => (
                                <option key={emp.staff_id} value={emp.staff_id}>{emp.staff_id} - {emp.first_name} {emp.last_name}</option>
                            ))}
                        </select>
                    </div>
                    <div className="filter-group">
                        <label>From</label>
                        <input type="datetime-local" value={startDateTime} onChange={(e) => setStartDateTime(e.target.value)} className="filter-input" />
                    </div>
                    <div className="filter-group">
                        <label>To</label>
                        <input type="datetime-local" value={endDateTime} onChange={(e) => setEndDateTime(e.target.value)} className="filter-input" />
                    </div>
                    <div className="filter-actions">
                        <button onClick={handleFetchRoute} className="btn-primary" disabled={isLoading}>Track</button>
                        {routeData && <button onClick={handleClearRoute} className="btn-secondary">Clear</button>}
                        {routeData && (
                            <button
                                onClick={async () => {
                                    if (isGeneratingPDF) return;
                                    setIsGeneratingPDF(true);
                                    try {
                                        showToast('Geocoding...', 'info');
                                        const locations = routeData.locations;
                                        const points = [locations[0], locations[locations.length - 1]];
                                        const newAddresses = await batchReverseGeocode(points, googleMapsApiKey);
                                        setAddresses(newAddresses);
                                        generateRouteTrackingPDF(routeData, newAddresses);
                                        showToast('PDF Prepared', 'success');
                                    } catch (err) { console.error(err); } finally { setIsGeneratingPDF(false); }
                                }}
                                className="btn-download"
                            >PDF</button>
                        )}
                    </div>
                </div>
                {routeData && (
                    <div className="route-stats">
                        <div className="stat-card-route">
                            <strong>{getTotalDistance()} km</strong>
                            <span>Distance</span>
                        </div>
                        <div className="stat-card-route">
                            <strong>{getDuration()}</strong>
                            <span>Duration</span>
                        </div>
                    </div>
                )}
            </div>
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
                    {routeData && <RoutePolyline routeData={routeData} />}
                </Map>
            </main>
        </>
    );
};

export const RoutePolyline = ({ routeData, idleThreshold = 30 }: { routeData: any, idleThreshold?: number }) => {
    const map = useMap();
    const mapsLib = useMapsLibrary('maps');

    const [idleSpots, setIdleSpots] = useState<any[]>([]);

    useEffect(() => {
        if (!map || !mapsLib || !routeData || !routeData.locations || routeData.locations.length < 2) return;

        const rawPath = routeData.locations.map((loc: any) => ({
            lat: parseFloat(loc.latitude),
            lng: parseFloat(loc.longitude),
            timestamp: loc.timestamp
        })).filter((p: any) => !isNaN(p.lat) && !isNaN(p.lng));

        const polyline = new mapsLib.Polyline({
            path: rawPath,
            geodesic: true,
            strokeColor: '#3b82f6',
            strokeOpacity: 0.9,
            strokeWeight: 5,
            map,
            zIndex: 4000
        });

        const R = 6371e3;
        const getDist = (p1: any, p2: any) => {
            const phi1 = p1.lat * Math.PI / 180;
            const phi2 = p2.lat * Math.PI / 180;
            const dphi = (p2.lat - p1.lat) * Math.PI / 180;
            const dlambda = (p2.lng - p1.lng) * Math.PI / 180;
            const a = Math.sin(dphi / 2) * Math.sin(dphi / 2) + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlambda / 2) * Math.sin(dlambda / 2);
            return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        };

        const thresholdMs = idleThreshold * 60 * 1000;
        let group = [rawPath[0]];
        const spots = [];

        for (let i = 1; i < rawPath.length; i++) {
            if (getDist(group[0], rawPath[i]) < 40) { // Slight bump to 40m radius clustering
                group.push(rawPath[i]);
            } else {
                const durationMs = new Date(group[group.length - 1].timestamp).getTime() - new Date(group[0].timestamp).getTime();
                if (durationMs >= thresholdMs) {
                    spots.push({ lat: group[0].lat, lng: group[0].lng, duration: Math.round(durationMs / 60000) });
                }
                group = [rawPath[i]];
            }
        }
        setIdleSpots(spots);

        // Draw hot areas as overlapping glowing circles
        const circles = spots.map(spot => {
            const intensity = Math.min(spot.duration / 60, 1); // scales up to 1hr
            const radius = 25 + (intensity * 40); // 25m to 65m

            // Inner core
            const core = new mapsLib.Circle({
                map,
                center: { lat: spot.lat, lng: spot.lng },
                radius: radius * 0.4,
                strokeColor: '#ef4444',
                strokeWeight: 0,
                fillColor: '#ef4444',
                fillOpacity: 0.8,
                zIndex: 3001
            });

            // Outer heat bloom
            const bloom = new mapsLib.Circle({
                map,
                center: { lat: spot.lat, lng: spot.lng },
                radius: radius,
                strokeColor: '#f97316',
                strokeOpacity: 0.6,
                strokeWeight: 2,
                fillColor: '#fb923c',
                fillOpacity: 0.35 + (intensity * 0.2), // up to 0.55 opacity
                zIndex: 3000
            });

            return [core, bloom];
        }).flat();

        return () => {
            polyline.setMap(null);
            circles.forEach(c => c.setMap(null));
        };
    }, [map, mapsLib, routeData, idleThreshold]);

    if (!routeData || !routeData.locations || routeData.locations.length === 0 || !mapsLib) return null;

    const rawPath = routeData.locations.map((loc: any) => ({
        lat: parseFloat(loc.latitude),
        lng: parseFloat(loc.longitude)
    })).filter((p: any) => !isNaN(p.lat) && !isNaN(p.lng));

    const circleSymbol = (mapsLib as any)?.SymbolPath?.CIRCLE ?? 0;

    return (
        <>
            {idleSpots.map((spot, i) => (
                <Marker
                    key={`label-${i}`}
                    position={spot}
                    icon={{ path: circleSymbol, scale: 0 }} // invisible marker just for the label
                    label={{
                        text: `${spot.duration}m`,
                        color: 'white',
                        fontWeight: 'bold',
                        fontSize: '11px',
                        className: 'hot-spot-label'
                    }}
                    title={`${spot.duration}m stationary`}
                />
            ))}
            <Marker position={rawPath[0]} label={{ text: "START", color: "white", fontWeight: "bold", fontSize: "10px" }} icon={{ path: circleSymbol, scale: 14, fillColor: '#10b981', fillOpacity: 1, strokeColor: 'white', strokeWeight: 2 }} />
            <Marker position={rawPath[rawPath.length - 1]} label={{ text: "END", color: "white", fontWeight: "bold", fontSize: "10px" }} icon={{ path: circleSymbol, scale: 14, fillColor: '#ef4444', fillOpacity: 1, strokeColor: 'white', strokeWeight: 2 }} />
        </>
    );
};

export default RouteTrackingView;
