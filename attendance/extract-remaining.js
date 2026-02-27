const fs = require('fs');

const path = 'frontend/src/HRDashboard.jsx';
let content = fs.readFileSync(path, 'utf8');

const mapping = [
    { name: 'LocationLogs', startStr: `) : activeTab === 'location_logs' ? (`, endStr: `) : activeTab === 'geo_fence_alerts' ? (` },
    { name: 'GeoFenceAlerts', startStr: `) : activeTab === 'geo_fence_alerts' ? (`, endStr: `) : activeTab === 'reports' ? (` },
    { name: 'ReportsTab', startStr: `) : activeTab === 'reports' ? (`, endStr: `) : activeTab === 'route_tracking' ? (` },
    { name: 'RouteTrackingTab', startStr: `) : activeTab === 'route_tracking' ? (`, endStr: `) : activeTab === 'idle_reporting' ? (` },
    { name: 'IdleReporting', startStr: `) : activeTab === 'idle_reporting' ? (`, endStr: `) : activeTab === 'access_roles' ? (` },
    { name: 'AccessRoles', startStr: `) : activeTab === 'access_roles' ? (`, endStr: `) : activeTab === 'biometrics' ? (` },
    { name: 'Biometrics', startStr: `) : activeTab === 'biometrics' ? (`, endStr: `) : (` }
];

for (let comp of mapping) {
    const startIndex = content.indexOf(comp.startStr);
    const endIndex = content.indexOf(comp.endStr);
    
    if (startIndex !== -1 && endIndex !== -1) {
        let jsxRaw = content.substring(startIndex + comp.startStr.length, endIndex).trim();
        
        let componentContent = `import React from 'react';\n\nexport default function ${comp.name}(props) {\n    return (\n        ${jsxRaw}\n    );\n}\n`;
        
        fs.writeFileSync(`frontend/src/components/${comp.name}.jsx`, componentContent);
        
        let replacement = `\n                    ) : activeTab === '${comp.name.toLowerCase().replace('tab', '')}' ? (\n                        <${comp.name} {...props} />\n                    `;
        
        // This is a rough automation, taking care to not mess up the HRDashboard in actual replacement.
    }
}
