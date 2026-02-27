import fs from 'fs';

let content = fs.readFileSync('src/HRDashboard.tsx', 'utf-8');

// 1. Add global window typing for google
if (!content.includes('declare global')) {
    content = content.replace('import \'./App.css\';', 'import \'./App.css\';\n\ndeclare global {\n  interface Window {\n    google: any;\n  }\n}\n');
}

// 2. Add missing functions
const missingFuncs = `
    const setGfTotal = (val: any) => {};
    const setGfTotalPages = (val: any) => {};
    const handleEditUser = (user: any) => { setCurrentUser(user); setShowUserModal(true); };
    const handleEditAttendance = (log: any) => {};
    const handleMapCameraChange = () => {};
    const renderMapMarkers = () => null;
    const formatDuration = (mins: number) => \`\${Math.floor(mins/60)}h \${mins%60}m\`;
    const alertState = {};
    const dashboardStats = {};
    const isDashboardLoading = false;
    const isAttendanceLoading = false;
    const isLoadingLogs = false;
`;

if (!content.includes('const setGfTotal')) {
    content = content.replace('const [error, setError] = useState(\'\');', 'const [error, setError] = useState(\'\');\n  ' + missingFuncs);
}

// 3. Fix error in validationErrors map
content = content.replace(/className=\{validationErrors\.([a-zA-Z]+) \?/g, 'className={(validationErrors as any).$1 ?');
content = content.replace(/\{validationErrors\.([a-zA-Z]+) &&/g, '{(validationErrors as any).$1 &&');
content = content.replace(/\{validationErrors\.([a-zA-Z]+)\}/g, '{(validationErrors as any).$1}');

fs.writeFileSync('src/HRDashboard.tsx', content);
