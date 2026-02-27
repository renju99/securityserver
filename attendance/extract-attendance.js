const fs = require('fs');

const path = 'frontend/src/HRDashboard.jsx';
let content = fs.readFileSync(path, 'utf8');

const startStr = `) : activeTab === 'attendance' ? (`
const endStr = `) : activeTab === 'location_logs' ? (`

const startIndex = content.indexOf(startStr);
const endIndex = content.indexOf(endStr);

if (startIndex === -1 || endIndex === -1) {
    console.log("Could not find boundaries");
    process.exit(1);
}

const jsxRaw = content.substring(startIndex + startStr.length, endIndex).trim();

const props = `
    attendanceLogs, isAttendanceLoading, applyFilters, formatDataForExport, exportToCSV,
    showToast, showFilters, setShowFilters, roles, sites, selectedRoles, selectedSites,
    setSelectedRoles, setSelectedSites, clearFilters, handleEditAttendance, isLoadingLogs, user
`;

const componentContent = `
import React from 'react';
import FilterPanel from './FilterPanel';
import { LoadingSpinner } from './LoadingSpinner';

export default function AttendanceLog({ 
    ${props}
}) {
    return (
        ${jsxRaw}
    );
}
`;

fs.writeFileSync('frontend/src/components/AttendanceLog.jsx', componentContent.trim());

const replacement = `
                    ) : activeTab === 'attendance' ? (
                        <AttendanceLog 
                            {...{
                                attendanceLogs, isAttendanceLoading, applyFilters, formatDataForExport, exportToCSV,
                                showToast, showFilters, setShowFilters, roles, sites, selectedRoles, selectedSites,
                                setSelectedRoles, setSelectedSites, clearFilters, handleEditAttendance, isLoadingLogs, user
                            }}
                        />
                    `;

const newContent = content.substring(0, startIndex) + replacement + content.substring(endIndex);

let finalContent = newContent;
if (!finalContent.includes('import AttendanceLog from')) {
    finalContent = finalContent.replace("import React, { useEffect", "import React, { useEffect\nimport AttendanceLog from './components/AttendanceLog';");
}


// Replace one bad import that was generated previously too
finalContent = finalContent.replace("import React, { useEffect\\nimport AnalyticsDashboard", "import React, { useEffect }\nimport AnalyticsDashboard");

fs.writeFileSync(path, finalContent);
console.log("Extracted AttendanceLog!");
