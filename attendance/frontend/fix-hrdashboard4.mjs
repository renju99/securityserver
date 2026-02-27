import fs from 'fs';

let content = fs.readFileSync('src/HRDashboard.tsx', 'utf-8');

// Replace const errors = {} with const errors: any = {}
content = content.replace(/const errors = \{\};/g, 'const errors: any = {};');

// Replace google.maps.event with window.google.maps.event 
// (or just use google if declare global worked? Wait, declare global interface Window has google. So we should change it to window.google)
content = content.replace(/if \(listener\) google\.maps/g, 'if (listener) window.google.maps');

fs.writeFileSync('src/HRDashboard.tsx', content);
