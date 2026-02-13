import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';

/**
 * Generate a detailed Route Tracking PDF report
 * @param {Object} routeData
 * @param {Object} addresses Map of coords to addresses (optional)
 */
export const generateRouteTrackingPDF = (routeData, addresses = {}) => {
    console.log('Starting Route Tracking PDF generation...', routeData);
    try {
        const doc = new jsPDF();

        if (typeof autoTable !== 'function') {
            console.error('autoTable is not a function. Import might be incorrect.');
            throw new Error('PDF Table plugin (autoTable) is not a function');
        }

        const pageWidth = doc.internal.pageSize.getWidth();
        const now = new Date();

        // ─── HEADER ───
        doc.setFillColor(102, 126, 234); // #667eea
        doc.rect(0, 0, pageWidth, 40, 'F');
        doc.setTextColor(255, 255, 255);
        doc.setFontSize(20);
        doc.setFont('helvetica', 'bold');
        doc.text('Detailed Route Tracking Report', 14, 18);
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.text(`Berkeley Workforce 360`, 14, 26);
        doc.text(`Generated: ${now.toLocaleString()}`, 14, 32);

        // ─── STAFF INFO ───
        let y = 50;
        doc.setTextColor(31, 41, 55);
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('Staff Information', 14, y);
        y += 8;

        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        const staffInfo = [
            ['Staff ID', routeData.employee.staffId],
            ['Name', `${routeData.employee.firstName} ${routeData.employee.lastName}`],
            ['Site', routeData.employee.siteName || 'N/A'],
        ];

        autoTable(doc, {
            startY: y,
            body: staffInfo,
            theme: 'plain',
            styles: { fontSize: 10, cellPadding: 3 },
            columnStyles: {
                0: { fontStyle: 'bold', cellWidth: 40, textColor: [107, 114, 128] },
                1: { textColor: [31, 41, 55] }
            },
            margin: { left: 14 }
        });

        // ─── ROUTE SUMMARY ───
        y = (doc.lastAutoTable?.finalY || y + 20) + 12;
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('Route Summary', 14, y);
        y += 8;

        const locations = routeData.locations;
        const totalPoints = routeData.totalPoints;

        // Calculate distance
        let totalDistance = 0;
        if (locations.length >= 2) {
            for (let i = 1; i < locations.length; i++) {
                const prev = locations[i - 1];
                const curr = locations[i];
                totalDistance += haversine(
                    parseFloat(prev.latitude), parseFloat(prev.longitude),
                    parseFloat(curr.latitude), parseFloat(curr.longitude)
                );
            }
        }
        const distKm = (totalDistance / 1000).toFixed(2);

        // Calculate duration
        let duration = 'N/A';
        if (locations.length >= 2) {
            const start = new Date(locations[0].timestamp);
            const end = new Date(locations[locations.length - 1].timestamp);
            const diffMs = end - start;
            const hours = Math.floor(diffMs / 3600000);
            const minutes = Math.floor((diffMs % 3600000) / 60000);
            duration = `${hours}h ${minutes}m`;
        }

        const summaryData = [
            ['Total Distance', `${distKm} km`],
            ['Duration', duration],
            ['Total Location Points', `${totalPoints}`],
            ['Sampled', routeData.sampled ? 'Yes (optimized for large dataset)' : 'No'],
            ['Start Location', locations.length > 0 ? (addresses[`${parseFloat(locations[0].latitude).toFixed(5)},${parseFloat(locations[0].longitude).toFixed(5)}`] || 'Available in breakdown') : 'N/A'],
            ['End Location', locations.length > 0 ? (addresses[`${parseFloat(locations[locations.length - 1].latitude).toFixed(5)},${parseFloat(locations[locations.length - 1].longitude).toFixed(5)}`] || 'Available in breakdown') : 'N/A'],
        ];

        autoTable(doc, {
            startY: y,
            body: summaryData,
            theme: 'striped',
            styles: { fontSize: 9, cellPadding: 4 },
            columnStyles: {
                0: { fontStyle: 'bold', cellWidth: 55, textColor: [107, 114, 128] },
                1: { textColor: [31, 41, 55] }
            },
            margin: { left: 14 },
            headStyles: { fillColor: [102, 126, 234] }
        });

        // ─── STOPS & PAUSES (NEW) ───
        const stops = detectStops(locations);
        if (stops.length > 0) {
            y = (doc.lastAutoTable?.finalY || y + 40) + 12;
            doc.setFontSize(14);
            doc.setFont('helvetica', 'bold');
            doc.text('Stationary Periods (> 5 mins)', 14, y);
            y += 4;

            const stopData = stops.map((s, idx) => [
                idx + 1,
                `${s.duration}m`,
                new Date(s.startTime).toLocaleTimeString(),
                new Date(s.endTime).toLocaleTimeString(),
                addresses[`${parseFloat(s.lat).toFixed(5)},${parseFloat(s.lng).toFixed(5)}`] || `${s.lat.toFixed(5)}, ${s.lng.toFixed(5)}`
            ]);

            autoTable(doc, {
                startY: y,
                head: [['#', 'Dur', 'From', 'To', 'Location Area']],
                body: stopData,
                theme: 'striped',
                styles: { fontSize: 8, cellPadding: 3 },
                headStyles: { fillColor: [107, 114, 128] },
                margin: { left: 14, right: 14 },
                columnStyles: {
                    0: { cellWidth: 8 },
                    1: { cellWidth: 15 },
                    2: { cellWidth: 25 },
                    3: { cellWidth: 25 },
                }
            });
        }

        // ─── DETAILED MOVEMENT BREAKDOWN (30-min) ───
        y = (doc.lastAutoTable?.finalY || y + 40) + 12;
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('Movement Detail (30-min intervals)', 14, y);
        y += 4;

        const breakdownPoints = getIntervalBreakdown(locations, 30);
        const detailTableData = breakdownPoints.map((point, index) => {
            const key = `${parseFloat(point.latitude).toFixed(5)},${parseFloat(point.longitude).toFixed(5)}`;
            return [
                index + 1,
                new Date(point.timestamp).toLocaleString(),
                addresses[key] || 'View on Map',
                `${parseFloat(point.latitude).toFixed(5)}, ${parseFloat(point.longitude).toFixed(5)}`
            ];
        });

        autoTable(doc, {
            startY: y,
            head: [['#', 'Time', 'Address / Area', 'GPS Coords']],
            body: detailTableData,
            theme: 'striped',
            styles: { fontSize: 8, cellPadding: 3 },
            headStyles: { fillColor: [102, 126, 234] },
            margin: { left: 14, right: 14 },
            columnStyles: {
                0: { cellWidth: 10 },
                1: { cellWidth: 40 },
                3: { cellWidth: 35, fontStyle: 'italic', textColor: [102, 126, 234] }
            },
            didDrawCell: (data) => {
                // Make GPS coords clickable
                if (data.section === 'body' && data.column.index === 3) {
                    const point = breakdownPoints[data.row.index];
                    const url = `https://www.google.com/maps?q=${point.latitude},${point.longitude}`;
                    doc.link(data.cell.x, data.cell.y, data.cell.width, data.cell.height, { url });
                }
            }
        });

        // ─── FOOTER ───
        const pageCount = doc.getNumberOfPages();
        for (let i = 1; i <= pageCount; i++) {
            doc.setPage(i);
            doc.setFontSize(8);
            doc.setTextColor(156, 163, 175);
            doc.text(
                `Page ${i} of ${pageCount} | Berkeley Workforce 360 - Detailed Route Report`,
                pageWidth / 2, doc.internal.pageSize.getHeight() - 10,
                { align: 'center' }
            );
        }

        const fileName = `Detailed_Route_${routeData.employee.staffId}_${formatDateForFilename(now)}.pdf`;
        doc.save(fileName);
        return fileName;
    } catch (error) {
        console.error('Route Tracking PDF error:', error);
        throw error;
    }
};


/**
 * Generate a detailed Idle Reporting PDF report
 */
export const generateIdleReportPDF = (idleSpots, staffId, staffName, startDate, endDate, threshold, addresses = {}) => {
    console.log('Starting Idle Report PDF generation...', { staffId, idleSpots });
    try {
        const doc = new jsPDF();

        if (typeof autoTable !== 'function') {
            console.error('autoTable is not a function. Import might be incorrect.');
            throw new Error('PDF Table plugin (autoTable) is not a function');
        }

        const pageWidth = doc.internal.pageSize.getWidth();
        const now = new Date();

        // ─── HEADER ───
        doc.setFillColor(118, 75, 162); // #764ba2
        doc.rect(0, 0, pageWidth, 40, 'F');
        doc.setTextColor(255, 255, 255);
        doc.setFontSize(20);
        doc.setFont('helvetica', 'bold');
        doc.text('Detailed Idle Time Report', 14, 18);
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.text(`Berkeley Workforce 360`, 14, 26);
        doc.text(`Generated: ${now.toLocaleString()}`, 14, 32);

        // ─── REPORT PARAMETERS ───
        let y = 50;
        doc.setTextColor(31, 41, 55);
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('Report Parameters', 14, y);
        y += 8;

        const paramData = [
            ['Staff ID', staffId],
            ['Staff Name', staffName],
            ['From', new Date(startDate).toLocaleString()],
            ['To', new Date(endDate).toLocaleString()],
            ['Idle Threshold', `${threshold} minutes`],
        ];

        autoTable(doc, {
            startY: y,
            body: paramData,
            theme: 'plain',
            styles: { fontSize: 10, cellPadding: 3 },
            columnStyles: {
                0: { fontStyle: 'bold', cellWidth: 40, textColor: [107, 114, 128] },
                1: { textColor: [31, 41, 55] }
            },
            margin: { left: 14 }
        });

        // ─── SUMMARY ───
        y = (doc.lastAutoTable?.finalY || y + 20) + 12;
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('Summary', 14, y);
        y += 8;

        const totalIdleMinutes = idleSpots.reduce((acc, s) => acc + s.duration, 0);
        const totalIdleHours = Math.floor(totalIdleMinutes / 60);
        const remainingMins = totalIdleMinutes % 60;

        const summaryData = [
            ['Total Idle Occurrences', `${idleSpots.length}`],
            ['Total Idle Time', `${totalIdleHours}h ${remainingMins}m (${totalIdleMinutes} minutes)`],
            ['Longest Idle Period', idleSpots.length > 0 ? `${Math.max(...idleSpots.map(s => s.duration))} minutes` : 'N/A'],
            ['Shortest Idle Period', idleSpots.length > 0 ? `${Math.min(...idleSpots.map(s => s.duration))} minutes` : 'N/A'],
        ];

        autoTable(doc, {
            startY: y,
            body: summaryData,
            theme: 'striped',
            styles: { fontSize: 10, cellPadding: 4 },
            columnStyles: {
                0: { fontStyle: 'bold', cellWidth: 55, textColor: [107, 114, 128] },
                1: { textColor: [31, 41, 55] }
            },
            margin: { left: 14 },
            headStyles: { fillColor: [118, 75, 162] }
        });

        // ─── DETAILED IDLE PERIODS ───
        y = (doc.lastAutoTable?.finalY || y + 40) + 12;
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('Detailed Idle Periods with Addresses', 14, y);
        y += 4;

        const idleTableData = idleSpots.map((spot, index) => {
            const key = `${parseFloat(spot.lat).toFixed(5)},${parseFloat(spot.lng).toFixed(5)}`;
            return [
                index + 1,
                `${spot.duration} min`,
                new Date(spot.startTime).toLocaleTimeString(),
                new Date(spot.endTime).toLocaleTimeString(),
                addresses[key] || 'Near Coordinates Below',
                `${parseFloat(spot.lat).toFixed(5)}, ${parseFloat(spot.lng).toFixed(5)}`
            ];
        });

        autoTable(doc, {
            startY: y,
            head: [['#', 'Dur', 'From', 'To', 'Address / Area', 'GPS Coords']],
            body: idleTableData,
            theme: 'striped',
            styles: { fontSize: 8, cellPadding: 3 },
            headStyles: { fillColor: [118, 75, 162] },
            margin: { left: 14, right: 14 },
            columnStyles: {
                0: { cellWidth: 8 },
                1: { cellWidth: 15 },
                2: { cellWidth: 20 },
                3: { cellWidth: 20 },
                5: { cellWidth: 35, fontStyle: 'italic', textColor: [118, 75, 162] }
            },
            didDrawCell: (data) => {
                // Make GPS coords clickable
                if (data.section === 'body' && data.column.index === 5) {
                    const spot = idleSpots[data.row.index];
                    const url = `https://www.google.com/maps?q=${spot.lat},${spot.lng}`;
                    doc.link(data.cell.x, data.cell.y, data.cell.width, data.cell.height, { url });
                }
            }
        });

        // ─── FOOTER ───
        const pageCount = doc.getNumberOfPages();
        for (let i = 1; i <= pageCount; i++) {
            doc.setPage(i);
            doc.setFontSize(8);
            doc.setTextColor(156, 163, 175);
            doc.text(
                `Page ${i} of ${pageCount} | Berkeley Workforce 360 - Detailed Idle Report`,
                pageWidth / 2, doc.internal.pageSize.getHeight() - 10,
                { align: 'center' }
            );
        }

        const fileName = `Detailed_Idle_${staffId}_${formatDateForFilename(now)}.pdf`;
        doc.save(fileName);
        return fileName;
    } catch (error) {
        console.error('Idle Report PDF error:', error);
        throw error;
    }
};


// ─── HELPERS ───

function haversine(lat1, lon1, lat2, lon2) {
    const R = 6371e3;
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(Δφ / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Get breakdown points at fixed intervals (e.g. 30 mins)
 */
function getIntervalBreakdown(locations, intervalMins = 60) {
    if (!locations || locations.length === 0) return [];

    const breakdown = [];
    let lastPointTime = 0;
    const intervalMs = intervalMins * 60 * 1000;

    locations.forEach((loc, idx) => {
        const time = new Date(loc.timestamp).getTime();
        // Always include first and last
        if (idx === 0 || idx === locations.length - 1 || (time - lastPointTime >= intervalMs)) {
            breakdown.push(loc);
            lastPointTime = time;
        }
    });

    return breakdown;
}

/**
 * Detect stationary periods (stops) longer than 5 mins
 */
function detectStops(locations, stopThresholdMins = 5) {
    if (!locations || locations.length < 2) return [];

    const stops = [];
    let currentStop = null;
    const distThreshold = 30; // 30 meters to consider "stationary" (GPS drift)

    for (let i = 1; i < locations.length; i++) {
        const prev = locations[i - 1];
        const curr = locations[i];
        const dist = haversine(prev.latitude, prev.longitude, curr.latitude, curr.longitude);

        if (dist < distThreshold) {
            if (!currentStop) {
                currentStop = {
                    startTime: prev.timestamp,
                    lat: prev.latitude,
                    lng: prev.longitude,
                    points: [prev, curr]
                };
            } else {
                currentStop.points.push(curr);
            }
        } else {
            if (currentStop) {
                const endTime = prev.timestamp;
                const duration = Math.round((new Date(endTime) - new Date(currentStop.startTime)) / 60000);
                if (duration >= stopThresholdMins) {
                    stops.push({
                        ...currentStop,
                        endTime,
                        duration
                    });
                }
                currentStop = null;
            }
        }
    }

    // Handle last stop if it finishes at the end
    if (currentStop) {
        const endTime = locations[locations.length - 1].timestamp;
        const duration = Math.round((new Date(endTime) - new Date(currentStop.startTime)) / 60000);
        if (duration >= stopThresholdMins) {
            stops.push({
                ...currentStop,
                endTime,
                duration
            });
        }
    }

    return stops;
}

function formatDateForFilename(date) {
    return `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}_${String(date.getHours()).padStart(2, '0')}${String(date.getMinutes()).padStart(2, '0')}`;
}
