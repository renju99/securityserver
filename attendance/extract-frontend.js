const fs = require('fs');

const path = 'frontend/src/HRDashboard.jsx';
let content = fs.readFileSync(path, 'utf8');

const mapStartStr = `{activeTab === 'map' ? (`;
const mapEndStr = `) : activeTab === 'staff' ? (`;

const startIndex = content.indexOf(mapStartStr);
const endIndex = content.indexOf(mapEndStr);

if (startIndex === -1 || endIndex === -1) {
    console.log("Could not find boundaries");
    process.exit(1);
}

// Extract the raw JSX representing the Map Dashboard (<> ... </>)
const mapJsxRaw = content.substring(startIndex + mapStartStr.length, endIndex).trim();
// Extract the imports we might need or just create a new file
console.log("Extracted JSX snippet, length:", mapJsxRaw.length);

const mapComponentProps = `
    user, sites, searchQuery, selectedSites, setSelectedSites, setSearchQuery, sidebarEmployees, 
    onlineEmployees, selectedId, handleSelectEmployee, mapCenter, handleMapCameraChange, 
    alertState, renderMapMarkers, showToast
`;

const mapComponentContent = `
import React, { useCallback, useState } from 'react';
import { Map, Marker, InfoWindow, AdvancedMarker } from '@vis.gl/react-google-maps';

export default function MapDashboard({ 
${mapComponentProps} 
}) {
    return (
        ${mapJsxRaw}
    );
}
`;

fs.mkdirSync('frontend/src/components', { recursive: true });
fs.writeFileSync('frontend/src/components/MapDashboard.jsx', mapComponentContent.trim());

// We must replace the old chunk with the `<MapDashboard />`
const replacement = `{activeTab === 'map' ? (
                        <MapDashboard 
                            user={user}
                            sites={sites}
                            searchQuery={searchQuery}
                            selectedSites={selectedSites}
                            setSelectedSites={setSelectedSites}
                            setSearchQuery={setSearchQuery}
                            sidebarEmployees={sidebarEmployees}
                            onlineEmployees={onlineEmployees}
                            selectedId={selectedId}
                            handleSelectEmployee={handleSelectEmployee}
                            mapCenter={mapCenter}
                            handleMapCameraChange={handleMapCameraChange}
                            alertState={alertState}
                            renderMapMarkers={renderMapMarkers}
                            showToast={showToast}
                        />
                    `;

const newContent = content.substring(0, startIndex) + replacement + content.substring(endIndex);

// inject import at top if it isn't there
let finalContent = newContent;
if (!finalContent.includes('import MapDashboard from')) {
    finalContent = finalContent.replace("import React,", "import React,\nimport MapDashboard from './components/MapDashboard';");
}

fs.writeFileSync(path, finalContent);
console.log("Replaced and saved!");
