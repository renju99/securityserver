const fs = require('fs');

const path = 'frontend/src/HRDashboard.jsx';
let content = fs.readFileSync(path, 'utf8');

const mapping = [
    {
        name: 'LocationLogs',
        startStr: `                    ) : activeTab === 'location_logs' ? (`,
        endStr: `                    ) : activeTab === 'geo_fence_alerts' ? (`
    },
    {
        name: 'GeoFenceAlerts',
        startStr: `                    ) : activeTab === 'geo_fence_alerts' ? (`,
        endStr: `                    ) : activeTab === 'reports' ? (`
    },
    {
        name: 'ReportsView',
        startStr: `                    ) : activeTab === 'reports' ? (`,
        endStr: `                    ) : activeTab === 'route_tracking' ? (`
    },
    {
        name: 'RouteTrackingView',
        startStr: `                    ) : activeTab === 'route_tracking' ? (`,
        endStr: `                    ) : activeTab === 'idle_reporting' ? (`
    },
    {
        name: 'IdleReporting',
        startStr: `                    ) : activeTab === 'idle_reporting' ? (`,
        endStr: `                    ) : activeTab === 'access_roles' ? (`
    },
    {
        name: 'AccessRoles',
        startStr: `                    ) : activeTab === 'access_roles' ? (`,
        endStr: `                    ) : activeTab === 'biometrics' ? (`
    },
    {
        name: 'Biometrics',
        startStr: `                    ) : activeTab === 'biometrics' ? (`,
        endStr: `                    ) : (`
    }
];

let finalContent = content;

// Generate components
for (let comp of mapping) {
    const startIndex = finalContent.indexOf(comp.startStr);
    const endIndex = finalContent.indexOf(comp.endStr);

    if (startIndex !== -1 && endIndex !== -1) {
        let jsxRaw = finalContent.substring(startIndex + comp.startStr.length, endIndex).trim();

        let componentContent = `
import React from 'react';

export default function ${comp.name}(props) {
    return (
        ${jsxRaw}
    );
}
`;
        fs.writeFileSync(\`frontend/src/components/\${comp.name}.jsx\`, componentContent.trim());
        
        // Define replacement JSX and patch content
        const replacement = \`                    ) : activeTab === '\${comp.startStr.split("===")[1].split("'")[1]}' ? (
                        <\${comp.name} {...props} />
\`;
        finalContent = finalContent.substring(0, startIndex) + replacement + finalContent.substring(endIndex);

        if (!finalContent.includes(\`import \${comp.name} from\`)) {
            finalContent = \`import \${comp.name} from './components/\${comp.name}';\\n\` + finalContent;
        }
        console.log(\`Extracted \${comp.name}\`);
    } else {
        console.log(\`Could not find \${comp.name}\`);
    }
}

// Write the modified Dashboard back
fs.writeFileSync(path, finalContent);
console.log('Complete');
