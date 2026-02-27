const fs = require('fs');
const filepath = 'frontend/src/HRDashboard.jsx';
let content = fs.readFileSync(filepath, 'utf8');

const startStr = 'const GeofenceManager = ({ type, data, radius, center, onChange }) => {';
const startIndex = content.indexOf(startStr);

if (startIndex !== -1) {
    // We just want to remove everything from GeofenceManager definition down to the end of the file, keeping ONLY `export default HRDashboard;`
    content = content.substring(0, startIndex).trim() + '\n\nexport default HRDashboard;\n';
    fs.writeFileSync(filepath, content);
    console.log('Removed GeofenceManager');
} else {
    console.log('GeofenceManager not found');
}
