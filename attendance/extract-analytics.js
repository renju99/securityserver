const fs = require('fs');

const path = 'frontend/src/HRDashboard.jsx';
let content = fs.readFileSync(path, 'utf8');

const startStr = `) : activeTab === 'analytics' ? (`
const endStr = `) : activeTab === 'attendance' ? (`

const startIndex = content.indexOf(startStr);
const endIndex = content.indexOf(endStr);

if (startIndex === -1 || endIndex === -1) {
    console.log("Could not find boundaries");
    process.exit(1);
}

const jsxRaw = content.substring(startIndex + startStr.length, endIndex).trim();

const props = `
    mgmtStats, onlineEmployees, dashboardStats, alertState, formatDuration,
    exportToCSV, formatDataForExport, showToast, isDashboardLoading
`;

const componentContent = `
import React from 'react';
import AnalyticsCard from './AnalyticsCard';
import { LoadingSpinner } from './LoadingSpinner';

export default function AnalyticsDashboard({ 
    ${props}
}) {
    return (
        ${jsxRaw}
    );
}
`;

fs.writeFileSync('frontend/src/components/AnalyticsDashboard.jsx', componentContent.trim());

const replacement = `
                    ) : activeTab === 'analytics' ? (
                        <AnalyticsDashboard 
                            {...{
                                mgmtStats, onlineEmployees, dashboardStats, alertState, formatDuration,
                                exportToCSV, formatDataForExport, showToast, isDashboardLoading
                            }}
                        />
                    `;

const newContent = content.substring(0, startIndex) + replacement + content.substring(endIndex);

let finalContent = newContent;
if (!finalContent.includes('import AnalyticsDashboard from')) {
    finalContent = finalContent.replace("import React, { useEffect", "import React, { useEffect\nimport AnalyticsDashboard from './components/AnalyticsDashboard';");
}

fs.writeFileSync(path, finalContent);
console.log("Extracted AnalyticsDashboard!");
