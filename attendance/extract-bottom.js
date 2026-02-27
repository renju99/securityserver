const fs = require('fs');
const filepath = 'frontend/src/HRDashboard.jsx';

let content = fs.readFileSync(filepath, 'utf8');

const blocks = [
    { start: '// ─── Location Logs View', end: '// ── Geo Fence Alerts View', target: 'LocationLogsView' },
    { start: '// ── Geo Fence Alerts View', end: '// ── Biometrics View', target: 'GeoFenceAlertsView' },
    { start: '// ── Biometrics View', end: '// ── Manual Attendance View', target: 'BiometricsView' },
    { start: '// ── Manual Attendance View', end: 'export default HRDashboard;', target: 'ManualAttendanceView' }
];

for (let b of blocks) {
    let sIdx = content.indexOf(b.start);
    let eIdx = content.indexOf(b.end);
    if (sIdx !== -1 && eIdx !== -1) {
        let blockContent = content.substring(sIdx, eIdx).trim();

        let fileContent = `
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { APIProvider, Map, Marker, InfoWindow, useMapsLibrary, useMap } from '@vis.gl/react-google-maps';
import { LoadingSpinner } from './LoadingSpinner';

${blockContent}

export default ${b.target};
`;
        fs.writeFileSync(`frontend/src/components/${b.target}.jsx`, fileContent.trim());

        content = content.substring(0, sIdx) + content.substring(eIdx);

        if (!content.includes(`import ${b.target} from`)) {
            content = `import ${b.target} from './components/${b.target}';\n` + content;
        }

        console.log("Extracted", b.target);
    }
}

// Extract GeofenceManager
let gmStart = content.indexOf('function GeofenceManager');
let gmEnd = content.indexOf('// ─── Location Logs View');
if (gmEnd === -1) gmEnd = content.indexOf('\nexport default HRDashboard');
if (gmStart !== -1) {
    let gmBlock = content.substring(gmStart, gmEnd).trim();
    let gmFile = `
import React, { useEffect, useRef } from 'react';
import { useMapsLibrary, useMap } from '@vis.gl/react-google-maps';

${gmBlock}

export default GeofenceManager;
`;
    fs.writeFileSync('frontend/src/components/GeofenceManager.jsx', gmFile.trim());
    content = content.substring(0, gmStart) + content.substring(gmEnd);
    if (!content.includes('import GeofenceManager from')) {
        content = "import GeofenceManager from './components/GeofenceManager';\n" + content;
    }
    console.log("Extracted GeofenceManager");
}


// Replace one bad import that was generated previously too
content = content.replace("import React, { useEffect\\nimport AnalyticsDashboard", "import React, { useEffect }\nimport AnalyticsDashboard");


fs.writeFileSync(filepath, content.trim() + '\\nexport default HRDashboard;\\n');

