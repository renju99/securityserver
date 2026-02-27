import fs from 'fs';

let content = fs.readFileSync('src/HRDashboard.tsx', 'utf-8');

// Replace setSites
content = content.replace('then(setSites);', 'then(() => fetchSites(user.token));');
// Replace setRoles
content = content.replace('setRoles(data);', 'fetchRoles(user.token);');

// Import GeofenceManager
if (!content.includes('import GeofenceManager')) {
    content = content.replace('import RouteTrackingView', 'import GeofenceManager from \'./components/GeofenceManager\';\nimport RouteTrackingView');
}

fs.writeFileSync('src/HRDashboard.tsx', content);
