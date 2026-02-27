import fs from 'fs';

const oldHR = fs.readFileSync('/tmp/old_hr.jsx', 'utf-8');

// Find GeofenceManager function
const startIdx = oldHR.indexOf('const GeofenceManager = ({ type, data, radius, center, onChange }) => {');
if (startIdx !== -1) {
    let endIdx = oldHR.indexOf('// ─── Location Logs View ──────────────────────────────────────────────────────', startIdx);
    if (endIdx === -1) {
        endIdx = oldHR.indexOf('export default HRDashboard;', startIdx);
    }
    let geofenceCode = oldHR.substring(startIdx, endIdx);

    // Clean up any trailing stuff
    geofenceCode = geofenceCode.trim();
    if (geofenceCode.endsWith('};')) {
        // ok
    }

    const finalCode =
        `// @ts-nocheck
import React, { useEffect, useState, useRef } from 'react';
import { useMap, useMapsLibrary } from '@vis.gl/react-google-maps';

` + geofenceCode + `\n\nexport default GeofenceManager;`;

    fs.writeFileSync('frontend/src/components/GeofenceManager.tsx', finalCode);
    console.log('Successfully extracted GeofenceManager.tsx');
} else {
    console.log('Could not find GeofenceManager in old_hr.jsx');
}
