const fs = require('fs');

const index = fs.readFileSync('backend/index.js', 'utf8');
const lines = index.split('\n');

const startIndex = 548; // Line 549 is index 548
const endIndex = 1984; // Line 1985 is index 1984

const hrLines = lines.slice(startIndex, endIndex);

let hrContent = `const express = require('express');

module.exports = (pool, authenticateToken, authorizeRole, bcrypt, jwt, JWT_SECRET, getGeofenceAlerts, broadcastGeofenceAlert) => {
    const router = express.Router();

    // Helper to extract JWT if some functions need it
    
` + hrLines.join('\n').replace(/app\./g, 'router.') + `
    return router;
};
`;

fs.writeFileSync('backend/routes/hr.js', hrContent);

const newIndexLines = [
    ...lines.slice(0, startIndex),
    "const hrRoutes = require('./routes/hr');",
    "app.use('/', hrRoutes(pool, authenticateToken, authorizeRole, bcrypt, jwt, JWT_SECRET, getGeofenceAlerts, broadcastGeofenceAlert));",
    ...lines.slice(endIndex)
];

fs.writeFileSync('backend/index.js', newIndexLines.join('\n'));
console.log('Extraction complete');
