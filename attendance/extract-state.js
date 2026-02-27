const fs = require('fs');

const path = 'frontend/src/HRDashboard.jsx';
let content = fs.readFileSync(path, 'utf8');

// Inject the store import
if (!content.includes('import { useDataStore }')) {
    content = content.replace("import { useAuthStore } from './store/useAuthStore';", "import { useAuthStore } from './store/useAuthStore';\nimport { useDataStore } from './store/useDataStore';");
}

// Replace the block of useState declarations
const stateToRemove = [
    'const [employees, setEmployees] = useState([]);',
    'const [onlineEmployees, setOnlineEmployees] = useState({});',
    'const [stats, setStats] = useState({ present: 0, total: 0 });',
    'const [mgmtUsers, setMgmtUsers] = useState([]);',
    'const [mgmtStats, setMgmtStats] = useState({ total: 0, page: 1, totalPages: 1 });',
    'const [sites, setSites] = useState([]);',
    'const [roles, setRoles] = useState([]);',
    'const [isMgmtLoading, setIsMgmtLoading] = useState(false);',
    'const [shifts, setShifts] = useState([]);',
    'const [geoFenceAlerts, setGeoFenceAlerts] = useState([]);',
    'const [attendanceLogs, setAttendanceLogs] = useState([]);',
    'const [allPermissions, setAllPermissions] = useState([]);',
    'const [biometricDevices, setBiometricDevices] = useState([]);',
    'const [biometricLogs, setBiometricLogs] = useState([]);',
    'const [isBiometricLoading, setIsBiometricLoading] = useState(false);'
];

for (let stmt of stateToRemove) {
    content = content.replace(stmt, '');
}

// Add the Zustand hook
const zustandHook = `
    const { 
        employees, onlineEmployees, stats, mgmtUsers, mgmtStats, 
        sites, roles, shifts, attendanceLogs, geoFenceAlerts, gfTotal, gfTotalPages, 
        biometricDevices, biometricLogs, allPermissions, isMgmtLoading, isBiometricLoading,
        fetchEmployees, fetchRoles, fetchSites, fetchShifts, fetchAlerts, fetchAttendance,
        fetchPermissions, fetchBiometricDevices, fetchBiometricLogs, fetchManagementUsers,
        setOnlineEmployees, setAttendanceLogs, setGeoFenceAlerts
    } = useDataStore();
`;

content = content.replace('const HRDashboard = () => {\n', 'const HRDashboard = () => {\n' + zustandHook);

// Remove the `setGfTotal` and `setGfTotalPages` from useState
content = content.replace("const [gfTotal, setGfTotal] = useState(0);\n", "");
content = content.replace("const [gfTotalPages, setGfTotalPages] = useState(1);\n", "");

// The socket event `geo_fence_alert` uses `setGeoFenceAlerts`. 
// The `useDataStore.js` `setGeoFenceAlerts` does `set({ geoFenceAlerts: data })`
// So in HRDashboard, `setGeoFenceAlerts(prev => [data, ...prev])` needs to be replaced.
content = content.replace(
    /setGeoFenceAlerts\(prev => \[data, \.\.\.prev\]\);/g,
    "setGeoFenceAlerts([data, ...geoFenceAlerts]);"
);

// We'll replace the fetch block manually in the next step to not overcomplicate the script.

fs.writeFileSync(path, content);
console.log('State extracted');
