import React, { useState } from 'react';
import { generateIdleReportPDF } from '../utils/pdfReports';
import { batchReverseGeocode } from '../utils/geocoding';
import './RouteTrackingView.css'; // Reusing styles

const IdleReportingView = ({ user, employees, onMapUpdate, showToast, idleSpots, onIdleSpotsChange: setIdleSpots, googleMapsApiKey }) => {
    const toLocalISO = (date) => {
        const offset = date.getTimezoneOffset() * 60000;
        const localDate = new Date(date - offset);
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

    const [selectedStaff, setSelectedStaff] = useState('');
    const [startDateTime, setStartDateTime] = useState(getDefaultStartDateTime());
    const [endDateTime, setEndDateTime] = useState(getDefaultEndDateTime());
    const [idleThreshold, setIdleThreshold] = useState(30);
    const [isLoading, setIsLoading] = useState(false);
    const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);
    const [addresses, setAddresses] = useState({});
    const [localIdleSpots, setLocalIdleSpots] = useState([]);

    const handleFetchReport = async () => {
        if (!selectedStaff || !startDateTime || !endDateTime) {
            showToast('Please select staff and date/time range', 'error');
            return;
        }

        setIsLoading(true);
        const startUTC = new Date(startDateTime).toISOString();
        const endUTC = new Date(endDateTime).toISOString();

        try {
            const res = await fetch(
                `/api/hr/idle-report?staffId=${selectedStaff}&startDate=${startUTC}&endDate=${endUTC}&thresholdMins=${idleThreshold}`,
                { headers: { 'Authorization': `Bearer ${user.token}` } }
            );

            if (res.ok) {
                const data = await res.json();
                setLocalIdleSpots(data.idleSpots);
                setIdleSpots(data.idleSpots);

                if (data.idleSpots.length > 0) {
                    onMapUpdate({
                        lat: parseFloat(data.idleSpots[0].lat),
                        lng: parseFloat(data.idleSpots[0].lng)
                    }, 14);
                    showToast(`Found ${data.idleSpots.length} idle periods`, 'success');
                } else {
                    showToast('No idle periods found for this range', 'info');
                }
            } else {
                const errData = await res.json();
                showToast(errData.error || 'Failed to fetch report', 'error');
            }
        } catch (err) {
            showToast('Network error - please try again', 'error');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="route-tracking-view">
            <div className="filter-section">
                <h3>⏳ Idle Reporting</h3>
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

                <div className="filter-group">
                    <label>Idle Threshold (Minutes)</label>
                    <input
                        type="number"
                        min="5"
                        max="1440"
                        value={idleThreshold}
                        onChange={(e) => setIdleThreshold(parseInt(e.target.value) || 0)}
                        className="filter-input"
                        disabled={isLoading}
                    />
                    <small className="filter-hint">Min minutes stationary to flag</small>
                </div>

                <div className="filter-actions">
                    <button
                        onClick={handleFetchReport}
                        className="btn-primary"
                        disabled={isLoading}
                    >
                        {isLoading ? 'Searching...' : '🔍 Generate Report'}
                    </button>
                    <button
                        onClick={() => {
                            setLocalIdleSpots([]);
                            setIdleSpots([]);
                        }}
                        className="btn-secondary"
                        disabled={isLoading}
                    >
                        🗑️ Clear
                    </button>
                    {localIdleSpots.length > 0 && (
                        <button
                            onClick={async () => {
                                if (isGeneratingPDF) return;
                                setIsGeneratingPDF(true);
                                try {
                                    showToast('Processing addresses for report...', 'info');

                                    // Identify points to geocode (all idle spots)
                                    const pointsToGeocode = localIdleSpots.map(s => ({
                                        latitude: s.lat,
                                        longitude: s.lng
                                    }));

                                    const newAddresses = await batchReverseGeocode(pointsToGeocode, googleMapsApiKey);
                                    setAddresses(prev => ({ ...prev, ...newAddresses }));

                                    const emp = employees.find(e => e.staff_id === selectedStaff);
                                    const staffName = emp ? `${emp.first_name} ${emp.last_name}` : selectedStaff;

                                    const fileName = generateIdleReportPDF(
                                        localIdleSpots, selectedStaff, staffName,
                                        startDateTime, endDateTime, idleThreshold,
                                        newAddresses
                                    );
                                    showToast(`PDF downloaded: ${fileName}`, 'success');
                                } catch (err) {
                                    console.error('PDF Download Error:', err);
                                    showToast('Failed to generate PDF.', 'error');
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

            {localIdleSpots.length > 0 && (
                <div className="route-stats">
                    <div className="stat-card-route">
                        <div className="stat-icon">🛑</div>
                        <div className="stat-content">
                            <span className="stat-label">Idle Occurrences</span>
                            <span className="stat-value">{localIdleSpots.length}</span>
                        </div>
                    </div>
                </div>
            )}

            {localIdleSpots.length > 0 && (
                <div className="route-timeline">
                    {localIdleSpots.map((spot, index) => {
                        const addrKey = `${parseFloat(spot.lat).toFixed(5)},${parseFloat(spot.lng).toFixed(5)}`;
                        return (
                            <div key={index} className="timeline-item" onClick={() => onMapUpdate({ lat: spot.lat, lng: spot.lng }, 18)}>
                                <div className="timeline-icon">🛑</div>
                                <div className="timeline-content">
                                    <div className="timeline-title">{spot.duration}m Stationary</div>
                                    <div className="timeline-desc">
                                        {new Date(spot.startTime).toLocaleTimeString()} — {new Date(spot.endTime).toLocaleTimeString()}
                                    </div>
                                    {addresses[addrKey] && (
                                        <div className="timeline-address" style={{ fontSize: '0.75rem', marginTop: '4px', color: '#667eea' }}>
                                            📍 {addresses[addrKey]}
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

export default IdleReportingView;
