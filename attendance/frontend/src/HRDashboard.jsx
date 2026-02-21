import React, { useEffect, useState, useRef, useCallback } from 'react';
import { io } from 'socket.io-client';
import { APIProvider, Map, Marker, InfoWindow, useMapsLibrary, useMap } from '@vis.gl/react-google-maps';
import Toast from './components/Toast';
import ConfirmDialog from './components/ConfirmDialog';
import { LoadingSpinner, TableSkeleton } from './components/LoadingSpinner';
import AnalyticsCard from './components/AnalyticsCard';
import FilterPanel from './components/FilterPanel';
import ReportsView from './components/ReportsView';
import RouteTrackingView, { RoutePolyline } from './components/RouteTrackingView';
import IdleReportingView from './components/IdleReportingView';
import { exportToCSV, formatDataForExport, formatSitesForExport } from './utils/exportUtils';
import './App.css';

// Socket connection
const socket = io('/', {
    path: '/socket.io/',
    autoConnect: false
});



const formatPermissionName = (name) => {
    return name
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
};

const getPermissionIcon = (name) => {
    if (name.includes('dashboard')) return '📊';
    if (name.includes('map')) return '🗺️';
    if (name.includes('staff') || name.includes('user')) return '👥';
    if (name.includes('site')) return '🏢';
    if (name.includes('report') || name.includes('export')) return '📥';
    if (name.includes('attendance')) return '🕒';
    return '🔒';
};

const HRDashboard = () => {
    const [employees, setEmployees] = useState([]);
    const [onlineEmployees, setOnlineEmployees] = useState({});
    const [stats, setStats] = useState({ present: 0, total: 0 });
    const [selectedId, setSelectedId] = useState(null);
    const [mapCenter, setMapCenter] = useState({ lat: 25.2048, lng: 55.2708 });
    const [zoom, setZoom] = useState(11);
    const [searchQuery, setSearchQuery] = useState('');
    const [user, setUser] = useState(JSON.parse(localStorage.getItem('hrUser')) || null);
    const [loginData, setLoginData] = useState({ staffId: '', password: '' });
    const [error, setError] = useState('');
    const [activeTab, setActiveTab] = useState('map'); // 'map', 'staff', or 'analytics'
    const [mgmtUsers, setMgmtUsers] = useState([]);
    const [mgmtStats, setMgmtStats] = useState({ total: 0, page: 1, totalPages: 1 });
    const [mgmtPage, setMgmtPage] = useState(1);
    const [mgmtSearch, setMgmtSearch] = useState('');
    const [sites, setSites] = useState([]);
    const [roles, setRoles] = useState([]);
    const [isMgmtLoading, setIsMgmtLoading] = useState(false);
    const [showUserModal, setShowUserModal] = useState(false);
    const [currentUser, setCurrentUser] = useState({ staffId: '', email: '', password: '', roleId: 4, siteId: '', departmentName: '', firstName: '', lastName: '' });
    const [mgmtSubTab, setMgmtSubTab] = useState('staff'); // 'staff', 'sites', or 'shifts'
    const [showSiteModal, setShowSiteModal] = useState(false);
    const [currentSite, setCurrentSite] = useState({
        name: '',
        location: '',
        latitude: '',
        longitude: '',
        radiusMeters: 100,
        geofenceType: 'CIRCLE',
        geofenceData: null,
        geofenceEnabled: true
    });
    const [shifts, setShifts] = useState([]);
    const [geoFenceAlerts, setGeoFenceAlerts] = useState([]);
    const [showShiftModal, setShowShiftModal] = useState(false);
    const [currentShift, setCurrentShift] = useState({ name: '', startTime: '', endTime: '' });
    const [attendanceLogs, setAttendanceLogs] = useState([]);
    const [selectedRole, setSelectedRole] = useState(null);
    const [allPermissions, setAllPermissions] = useState([]);
    const [isEditingPermissions, setIsEditingPermissions] = useState(false);
    const [tempPermissions, setTempPermissions] = useState([]);

    // Route Tracking
    const [routeData, setRouteData] = useState(null);
    const [idleThreshold, setIdleThreshold] = useState(30);
    const [idleSpots, setIdleSpots] = useState([]);

    // Toast notifications
    const [toasts, setToasts] = useState([]);
    const [confirmDialog, setConfirmDialog] = useState({ isOpen: false, title: '', message: '', onConfirm: null });
    const [validationErrors, setValidationErrors] = useState({});
    const [logSearch, setLogSearch] = useState(''); // Search for attendance logs
    const [isLoading, setIsLoading] = useState(false);

    // Location Logs state
    const [locationLogs, setLocationLogs] = useState([]);
    const [locLogSearch, setLocLogSearch] = useState('');
    const [locLogStartDate, setLocLogStartDate] = useState('');
    const [locLogEndDate, setLocLogEndDate] = useState('');
    const [locLogPage, setLocLogPage] = useState(1);
    const [locLogTotal, setLocLogTotal] = useState(0);
    const [locLogTotalPages, setLocLogTotalPages] = useState(1);
    const [locLogLoading, setLocLogLoading] = useState(false);
    const [locLogSelected, setLocLogSelected] = useState([]);
    const [locLogSelectAll, setLocLogSelectAll] = useState(false);
    const LOC_LOG_LIMIT = 100;
    const [socketStatus, setSocketStatus] = useState('connecting');
    const [lastHeartbeat, setLastHeartbeat] = useState(null);

    // Geo Fence Alerts tab state
    const [gfPage, setGfPage] = useState(1);
    const [gfTotal, setGfTotal] = useState(0);
    const [gfTotalPages, setGfTotalPages] = useState(1);
    const [gfLoading, setGfLoading] = useState(false);
    const [gfSearch, setGfSearch] = useState('');
    const [gfSiteFilter, setGfSiteFilter] = useState('');
    const [gfStatusFilter, setGfStatusFilter] = useState('');
    const [gfStartDate, setGfStartDate] = useState('');
    const [gfEndDate, setGfEndDate] = useState('');
    const GF_LIMIT = 50;

    // Filters
    const [selectedRoles, setSelectedRoles] = useState([]);
    const [selectedSites, setSelectedSites] = useState([]);
    const [showFilters, setShowFilters] = useState(false);

    // Bulk operations
    const [selectedUsers, setSelectedUsers] = useState([]);
    const [selectAll, setSelectAll] = useState(false);

    // Sorting
    const [sortField, setSortField] = useState('staff_id');
    const [sortDirection, setSortDirection] = useState('asc');

    // Analytics
    const [analyticsData, setAnalyticsData] = useState({
        totalUsers: 0,
        activeToday: 0,
        totalSites: 0,
        avgAttendance: 0
    });

    const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

    // Toast helper functions
    const showToast = useCallback((message, type = 'info') => {
        const id = Date.now();
        setToasts(prev => [...prev, { id, message, type }]);
    }, []);

    const removeToast = useCallback((id) => {
        setToasts(prev => prev.filter(toast => toast.id !== id));
    }, []);

    // Filter helper functions
    const applyFilters = useCallback((users) => {
        let filtered = [...users];

        // Apply role filter
        if (selectedRoles.length > 0) {
            filtered = filtered.filter(u => selectedRoles.includes(u.role_id));
        }

        // Apply site filter
        if (selectedSites.length > 0) {
            filtered = filtered.filter(u => {
                if (selectedSites.includes('global')) {
                    return !u.site_id || selectedSites.includes(u.site_id);
                }
                return selectedSites.includes(u.site_id);
            });
        }

        return filtered;
    }, [selectedRoles, selectedSites]);

    // Sort helper function
    const applySorting = useCallback((users) => {
        return [...users].sort((a, b) => {
            let aVal = a[sortField];
            let bVal = b[sortField];

            // Handle null/undefined
            if (aVal === null || aVal === undefined) aVal = '';
            if (bVal === null || bVal === undefined) bVal = '';

            // Convert to string for comparison
            aVal = String(aVal).toLowerCase();
            bVal = String(bVal).toLowerCase();

            if (sortDirection === 'asc') {
                return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
            } else {
                return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
            }
        });
    }, [sortField, sortDirection]);

    // Bulk operations
    const handleSelectAll = useCallback(() => {
        if (selectAll) {
            setSelectedUsers([]);
            setSelectAll(false);
        } else {
            setSelectedUsers(mgmtUsers.map(u => u.id));
            setSelectAll(true);
        }
    }, [selectAll, mgmtUsers]);

    const handleSelectUser = useCallback((userId) => {
        if (selectedUsers.includes(userId)) {
            setSelectedUsers(prev => prev.filter(id => id !== userId));
            setSelectAll(false);
        } else {
            setSelectedUsers(prev => [...prev, userId]);
        }
    }, [selectedUsers]);

    const handleBulkDelete = useCallback(() => {
        if (selectedUsers.length === 0) {
            showToast('No users selected', 'warning');
            return;
        }

        setConfirmDialog({
            isOpen: true,
            title: 'Delete Selected Users',
            message: `Are you sure you want to delete ${selectedUsers.length} user(s)? This action cannot be undone.`,
            confirmText: 'Delete',
            cancelText: 'Cancel',
            type: 'danger',
            onConfirm: async () => {
                setIsLoading(true);
                try {
                    const promises = selectedUsers.map(userId =>
                        fetch(`/api/hr/users/${userId}`, {
                            method: 'DELETE',
                            headers: { 'Authorization': `Bearer ${user.token}` }
                        })
                    );
                    await Promise.all(promises);
                    showToast(`Successfully deleted ${selectedUsers.length} user(s)`, 'success');
                    setSelectedUsers([]);
                    setSelectAll(false);
                    fetchManagementUsers();
                } catch (err) {
                    showToast('Failed to delete some users', 'error');
                } finally {
                    setIsLoading(false);
                }
            }
        });
    }, [selectedUsers, user, showToast]);

    const handleBulkExport = useCallback(() => {
        if (selectedUsers.length === 0) {
            showToast('No users selected', 'warning');
            return;
        }

        const selectedData = mgmtUsers.filter(u => selectedUsers.includes(u.id));
        const formattedData = formatDataForExport(selectedData);
        exportToCSV(formattedData, `selected_staff_${new Date().toISOString().split('T')[0]}.csv`);
        showToast(`Exported ${selectedUsers.length} user(s)`, 'success');
    }, [selectedUsers, mgmtUsers, showToast]);

    const clearFilters = useCallback(() => {
        setSelectedRoles([]);
        setSelectedSites([]);
        showToast('Filters cleared', 'info');
    }, [showToast]);

    useEffect(() => {
        if (!user) return;

        // Connect socket with auth
        if (user.token) {
            socket.auth = { token: user.token };
            if (!socket.connected) socket.connect();
        }

        // Join specific Socket room based on role
        if (user.role === 'HR Admin') {
            socket.emit('join_hr');
        } else if (user.role === 'Site Supervisor' && user.siteId) {
            socket.emit('join_site', user.siteId);
        }

        // Fetch initial data
        const headers = { 'Authorization': `Bearer ${user.token}` };

        const checkAuth = (res) => {
            if (res.status === 401 || res.status === 403) {
                console.warn('Authentication expired, logging out...');
                handleLogout();
                return false;
            }
            return true;
        };

        fetch('/api/hr/employees', { headers })
            .then(res => {
                if (!checkAuth(res)) return null;
                return res.json();
            })
            .then(data => {
                if (!data) return;
                if (Array.isArray(data)) {
                    setEmployees(data);
                    setStats(prev => ({ ...prev, total: data.length }));
                } else {
                    console.error('Expected array for employees but got:', data);
                    setEmployees([]);
                }
            })
            .catch(err => {
                console.error('Error fetching employees:', err);
                setEmployees([]);
            });

        if (user.role === 'HR Admin' || user.role === 'Site Supervisor') {
            fetch('/api/hr/roles', { headers }).then(res => res.json()).then(setRoles);
        }
        if (user.role === 'HR Admin') {
            fetch('/api/hr/sites', { headers }).then(res => res.json()).then(setSites);
            fetch('/api/hr/shifts', { headers }).then(res => res.json()).then(setShifts);
        }

        if (user.role === 'HR Admin' || user.role === 'Site Supervisor') {
            fetch('/api/hr/alerts?limit=50', { headers })
                .then(res => res.json())
                .then(data => {
                    if (Array.isArray(data)) {
                        setGeoFenceAlerts(data); // legacy fallback
                    } else if (data?.alerts) {
                        setGeoFenceAlerts(data.alerts);
                        setGfTotal(data.total || 0);
                        setGfTotalPages(data.totalPages || 1);
                    }
                });
        }

        fetch('/api/hr/attendance', { headers })
            .then(res => res.json())
            .then(data => {
                if (Array.isArray(data)) setAttendanceLogs(data);
            })
            .catch(console.error);

        // Socket listeners
        socket.on('connect', () => {
            setSocketStatus('connected');
            console.log('Socket connected to server');
        });

        socket.on('disconnect', (reason) => {
            setSocketStatus('disconnected');
            console.log('Socket disconnected:', reason);
        });

        socket.on('connect_error', (error) => {
            setSocketStatus('error');
            console.error('Socket connection error:', error);
        });

        // Add heartbeat/ping monitor if server sends any, otherwise use incoming data as proxy
        const updateHeartbeat = () => setLastHeartbeat(new Date().toLocaleTimeString());
        socket.on('employee_location', (data) => {
            console.log('Online update received:', data);
            if (!data || !data.employeeId || data.latitude === undefined || data.longitude === undefined) {
                console.warn('Malformed location data received:', data);
                return;
            }
            setOnlineEmployees(prev => ({
                ...prev,
                [data.employeeId]: {
                    ...data,
                    lastSeen: new Date().toLocaleTimeString()
                }
            }));
            updateHeartbeat();
        });

        socket.on('attendance_event', (data) => {
            console.log('Attendance event:', data);

            setAttendanceLogs(prev => {
                const logs = [...prev];
                // Check if this exact event is already processed (basic dedup)
                if (data.type === 'check_in') {
                    // Add new session
                    logs.unshift({
                        id: 'live-' + Date.now(),
                        staff_id: data.employeeId,
                        first_name: data.firstName,
                        last_name: data.lastName,
                        check_in_time: data.timestamp,
                        check_out_time: null,
                        site_name: data.siteName,
                        site_id: data.siteId,
                        is_live: true
                    });
                } else if (data.type === 'check_out') {
                    // Update active session
                    const idx = logs.findIndex(l => l.staff_id === data.employeeId && !l.check_out_time);
                    if (idx >= 0) {
                        logs[idx] = { ...logs[idx], check_out_time: data.timestamp };
                    }
                }
                return logs.slice(0, 100); // Keep max 100
            });
        });

        socket.on('geo_fence_alert', (data) => {
            console.warn('Geo Fence Alert:', data);
            showToast(`⚠️ Geo-Fence Alert: ${data.first_name || data.staff_id} is outside ${data.site_name || 'site'}!`, 'error');
            setGeoFenceAlerts(prev => [data, ...prev]);
        });

        return () => {
            socket.off('employee_location');
            socket.off('attendance_event');
            socket.off('geo_fence_alert');
        };
    }, [user]);

    useEffect(() => {
        if (activeTab === 'staff' && user?.role === 'HR Admin') {
            fetchManagementUsers();
        }
        if (activeTab === 'access_roles' && user?.role === 'HR Admin') {
            fetch('/api/hr/permissions', { headers: { 'Authorization': `Bearer ${user.token}` } })
                .then(res => res.json())
                .then(setAllPermissions)
                .catch(err => console.error('Error fetching permissions:', err));
        }
    }, [activeTab, mgmtPage, mgmtSearch]);

    useEffect(() => {
        if (activeTab !== 'map') return;

        if (selectedSites.length === 1) {
            const site = sites.find(s => s.id === selectedSites[0]);
            if (site && site.latitude && site.longitude) {
                setMapCenter({
                    lat: parseFloat(site.latitude),
                    lng: parseFloat(site.longitude)
                });
                setZoom(16);
            }
        }
    }, [selectedSites, sites, activeTab]);

    // Debounced search
    useEffect(() => {
        if (activeTab !== 'staff') return;

        const debounceTimer = setTimeout(() => {
            fetchManagementUsers();
        }, 300); // 300ms debounce

        return () => clearTimeout(debounceTimer);
    }, [mgmtSearch]);

    const fetchManagementUsers = () => {
        setIsMgmtLoading(true);
        fetch(`/api/hr/users?page=${mgmtPage}&search=${mgmtSearch}`, {
            headers: { 'Authorization': `Bearer ${user.token}` }
        })
            .then(res => res.json())
            .then(data => {
                if (data && Array.isArray(data.users)) {
                    setMgmtUsers(data.users);
                    setMgmtStats({ total: data.total, page: data.page, totalPages: data.totalPages });
                } else {
                    console.error('Expected users array in management response:', data);
                    setMgmtUsers([]);
                }
                setIsMgmtLoading(false);
            })
            .catch(err => {
                console.error('Error fetching management users:', err);
                setMgmtUsers([]);
                setIsMgmtLoading(false);
            });
    };

    const validateUser = (user) => {
        const errors = {};
        if (!user.staffId && !user.staff_id) errors.staffId = 'Staff ID is required';
        if (user.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(user.email)) {
            errors.email = 'Invalid email format';
        }
        if (!user.id && !user.password) errors.password = 'Password is required for new users';
        if (user.password && user.password.length < 6) errors.password = 'Password must be at least 6 characters';
        return errors;
    };

    const handleSaveUser = async (e) => {
        e.preventDefault();
        setValidationErrors({});

        const errors = validateUser(currentUser);
        if (Object.keys(errors).length > 0) {
            setValidationErrors(errors);
            showToast('Please fix validation errors', 'error');
            return;
        }

        const payload = {
            staffId: currentUser.staffId !== undefined ? currentUser.staffId : currentUser.staff_id,
            email: currentUser.email,
            password: currentUser.password,
            roleId: currentUser.roleId !== undefined ? currentUser.roleId : currentUser.role_id,
            siteId: currentUser.siteId !== undefined ? currentUser.siteId : currentUser.site_id,
            departmentName: currentUser.departmentName !== undefined ? currentUser.departmentName : currentUser.department_name,
            firstName: currentUser.firstName !== undefined ? currentUser.firstName : currentUser.first_name,
            lastName: currentUser.lastName !== undefined ? currentUser.lastName : currentUser.last_name,
            photoHelper: currentUser.photoHelper
        };

        setIsLoading(true);
        try {
            const res = await fetch('/api/hr/users', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${user.token}`
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                setShowUserModal(false);
                fetchManagementUsers();
                setCurrentUser({ staffId: '', email: '', password: '', roleId: 4, siteId: '', departmentName: '', firstName: '', lastName: '' });
                showToast(currentUser.id ? 'User updated successfully' : 'User created successfully', 'success');
            } else {
                const error = await res.json();
                showToast(error.error || 'Failed to save user', 'error');
            }
        } catch (err) {
            console.error('Error saving user:', err);
            showToast('Network error. Please try again.', 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const validateSite = (site) => {
        const errors = {};
        if (!site.name || site.name.trim().length === 0) errors.name = 'Site name is required';
        if (site.name && site.name.length < 3) errors.name = 'Site name must be at least 3 characters';
        return errors;
    };

    const handleSaveSite = async (e) => {
        e.preventDefault();
        setValidationErrors({});

        const errors = validateSite(currentSite);
        if (Object.keys(errors).length > 0) {
            setValidationErrors(errors);
            showToast('Please fix validation errors', 'error');
            return;
        }

        const method = currentSite.id ? 'PATCH' : 'POST';
        const url = currentSite.id ? `/api/hr/sites/${currentSite.id}` : '/api/hr/sites';

        setIsLoading(true);
        try {
            const res = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${user.token}`
                },
                body: JSON.stringify(currentSite)
            });

            if (res.ok) {
                setShowSiteModal(false);
                // Refresh sites list
                fetch('/api/hr/sites', { headers: { 'Authorization': `Bearer ${user.token}` } })
                    .then(res => res.json())
                    .then(setSites);
                setCurrentSite({
                    name: '',
                    location: '',
                    latitude: '',
                    longitude: '',
                    radiusMeters: 100,
                    geofenceType: 'CIRCLE',
                    geofenceData: null,
                    geofenceEnabled: true
                });
                showToast(currentSite.id ? 'Site updated successfully' : 'Site created successfully', 'success');
            } else {
                const error = await res.json();
                showToast(error.error || 'Failed to save site', 'error');
            }
        } catch (err) {
            console.error('Error saving site:', err);
            showToast('Network error. Please try again.', 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const handleFocusSite = (site) => {
        if (site.latitude && site.longitude) {
            setMapCenter({ lat: parseFloat(site.latitude), lng: parseFloat(site.longitude) });
            setZoom(16);
            setActiveTab('map');
            setSelectedSites([site.id]);
            showToast(`Focusing on ${site.name}`, 'info');
        } else {
            showToast('Geo location not set for this site', 'warning');
        }
    };

    const handleStartEditPermissions = () => {
        if (!selectedRole) return;
        // Default to empty array if no permissions
        const currentIds = (selectedRole.permissions || []).map(p => p.id).filter(id => id);
        setTempPermissions(currentIds);
        setIsEditingPermissions(true);
    };

    const handleTogglePermission = (permId) => {
        setTempPermissions(prev => {
            if (prev.includes(permId)) {
                return prev.filter(id => id !== permId);
            } else {
                return [...prev, permId];
            }
        });
    };

    const handleSavePermissions = async () => {
        if (!selectedRole) return;
        setIsLoading(true);
        try {
            const res = await fetch(`/api/hr/roles/${selectedRole.id}/permissions`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${user.token}`
                },
                body: JSON.stringify({ permissionIds: tempPermissions })
            });

            if (res.ok) {
                showToast('Permissions updated successfully', 'success');
                setIsEditingPermissions(false);
                // Refresh Roles
                fetch('/api/hr/roles', { headers: { 'Authorization': `Bearer ${user.token}` } })
                    .then(r => r.json())
                    .then(data => {
                        setRoles(data);
                        // Update selected role ref
                        const updatedRole = data.find(r => r.id === selectedRole.id);
                        if (updatedRole) setSelectedRole(updatedRole);
                    });
            } else {
                showToast('Failed to update permissions', 'error');
            }
        } catch (err) {
            console.error(err);
            showToast('Network error', 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const sidebarEmployees = [
        ...employees,
        ...Object.keys(onlineEmployees)
            .filter(id => !employees.some(e => e.staff_id === id))
            .map(id => ({
                id: `guest-${id}`,
                staff_id: id,
                isGuest: true,
                site_id: onlineEmployees[id].siteId,
                photo_url: onlineEmployees[id].photoUrl || onlineEmployees[id].photo_url,
                department_name: onlineEmployees[id].departmentName || onlineEmployees[id].department_name
            }))
    ].filter(emp => {
        const matchesSearch = emp.staff_id.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesSite = selectedSites.length === 0 || selectedSites.includes(emp.site_id || emp.siteId);
        return matchesSearch && matchesSite;
    });

    const handleLogin = async (e) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(loginData)
            });
            const data = await res.json();

            if (res.ok) {
                const userData = { ...data.user, token: data.token };
                localStorage.setItem('hrUser', JSON.stringify(userData));
                setUser(userData);
                showToast(`Welcome back, ${data.user.role}!`, 'success');
            } else {
                setError(data.error || 'Login failed');
                showToast(data.error || 'Invalid credentials', 'error');
            }
        } catch (err) {
            setError('Connection error');
            showToast('Unable to connect to server', 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const handleLogout = () => {
        localStorage.removeItem('hrUser');
        setUser(null);
        window.location.reload();
    };

    const handleSelectEmployee = (empId) => {
        if (onlineEmployees[empId]) {
            setMapCenter({
                lat: onlineEmployees[empId].latitude,
                lng: onlineEmployees[empId].longitude
            });
            setZoom(15);
            setSelectedId(empId);
        }
    };

    if (!user) {
        return (
            <div className="setup-screen hr-login">
                <div className="setup-card">
                    <div className="berkeley-logo-small">Berkeley Workforce 360</div>
                    <h2>Dashboard Login</h2>
                    <p>Enter your management credentials.</p>
                    <form onSubmit={handleLogin}>
                        {error && <div className="error-box">{error}</div>}
                        <input
                            type="text"
                            placeholder="Staff ID"
                            value={loginData.staffId}
                            onChange={(e) => setLoginData({ ...loginData, staffId: e.target.value })}
                            required
                            className="setup-input"
                        />
                        <input
                            type="password"
                            placeholder="Password"
                            value={loginData.password}
                            onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                            required
                            className="setup-input"
                        />
                        <button type="submit" className="btn-primary">Sign In</button>
                    </form>
                </div>
            </div>
        );
    }

    return (
        <div className="hr-dashboard">
            <APIProvider apiKey={GOOGLE_MAPS_API_KEY} libraries={['places', 'drawing', 'geometry']}>
                <header className="dashboard-header">
                    {/* Brand */}
                    <div className="header-left">
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
                            <span className="header-brand-title">Berkeley Workforce 360</span>
                            <span className="header-brand-sub">
                                {user.role}{user.siteName ? ` · ${user.siteName}` : (user.siteId ? ` · Site #${user.siteId}` : ' · Global')}
                            </span>
                        </div>
                    </div>

                    {/* Stats + Nav + Logout */}
                    <div className="header-stats">
                        <div className="stat-card">
                            <span className="stat-label">Total Staff</span>
                            <span className="stat-value">{stats.total}</span>
                        </div>
                        <div className="stat-card">
                            <span className="stat-label">Online Now</span>
                            <span className="stat-value text-success">{Object.keys(onlineEmployees).length}</span>
                        </div>
                        <div className="stat-card socket-status-card">
                            <span className="stat-label">Live Stream</span>
                            <span className={`stat-value socket-${socketStatus}`}>
                                {socketStatus === 'connected' ? '● Live' : '○ Off'}
                            </span>
                            {lastHeartbeat && <small className="last-heartbeat">{lastHeartbeat}</small>}
                        </div>
                    </div>

                    {/* Navigation */}
                    <div className="tab-switcher">
                        <button
                            className={`tab-btn ${activeTab === 'map' ? 'active' : ''}`}
                            onClick={() => setActiveTab('map')}
                        >
                            Live Map
                        </button>
                        {user.role === 'HR Admin' && (
                            <button
                                className={`tab-btn ${activeTab === 'staff' ? 'active' : ''}`}
                                onClick={() => setActiveTab('staff')}
                            >
                                Staff
                            </button>
                        )}
                        {user.role === 'HR Admin' && (
                            <button
                                className={`tab-btn ${activeTab === 'analytics' ? 'active' : ''}`}
                                onClick={() => setActiveTab('analytics')}
                            >
                                Analytics
                            </button>
                        )}
                        {(user.role === 'HR Admin' || user.role === 'Site Supervisor') && (
                            <button
                                className={`tab-btn ${activeTab === 'attendance' ? 'active' : ''}`}
                                onClick={() => setActiveTab('attendance')}
                            >
                                Attendance
                            </button>
                        )}
                        {(user.role === 'HR Admin' || user.role === 'Site Supervisor') && (
                            <button
                                className={`tab-btn ${activeTab === 'reports' ? 'active' : ''}`}
                                onClick={() => setActiveTab('reports')}
                            >
                                Reports
                            </button>
                        )}
                        {(user.role === 'HR Admin' || user.role === 'Site Supervisor') && (
                            <button
                                className={`tab-btn ${activeTab === 'route_tracking' ? 'active' : ''}`}
                                onClick={() => setActiveTab('route_tracking')}
                            >
                                Routes
                            </button>
                        )}
                        {(user.role === 'HR Admin' || user.role === 'Site Supervisor') && (
                            <button
                                className={`tab-btn ${activeTab === 'idle_reporting' ? 'active' : ''}`}
                                onClick={() => setActiveTab('idle_reporting')}
                            >
                                Idle
                            </button>
                        )}
                        {(user.role === 'HR Admin' || user.role === 'Site Supervisor') && (
                            <button
                                className={`tab-btn ${activeTab === 'location_logs' ? 'active' : ''}`}
                                onClick={() => setActiveTab('location_logs')}
                            >
                                Loc. Logs
                            </button>
                        )}
                        {(user.role === 'HR Admin' || user.role === 'Site Supervisor') && (
                            <button
                                className={`tab-btn ${activeTab === 'geo_fence_alerts' ? 'active' : ''}`}
                                onClick={() => setActiveTab('geo_fence_alerts')}
                            >
                                ⚠ Geo Alerts{geoFenceAlerts.length > 0 ? ` (${gfTotal || geoFenceAlerts.length})` : ''}
                            </button>
                        )}
                        {(user.role === 'HR Admin') && (
                            <button
                                className={`tab-btn ${activeTab === 'access_roles' ? 'active' : ''}`}
                                onClick={() => setActiveTab('access_roles')}
                            >
                                Access
                            </button>
                        )}
                    </div>

                    <button onClick={handleLogout} className="btn-logout">Logout</button>
                </header>

                <div className="dashboard-layout">
                    {activeTab === 'map' ? (
                        <>
                            <aside className="sidebar">
                                <div className="sidebar-header">
                                    <h3>Employees</h3>
                                    <div className="search-container">
                                        <select
                                            className="sidebar-search"
                                            style={{ marginBottom: '0.5rem' }}
                                            value={selectedSites[0] || ''}
                                            onChange={(e) => setSelectedSites(e.target.value ? [parseInt(e.target.value)] : [])}
                                        >
                                            <option value="">All Sites</option>
                                            {sites.map(s => (
                                                <option key={s.id} value={s.id}>{s.name}</option>
                                            ))}
                                        </select>
                                        <input
                                            type="text"
                                            placeholder="Search Staff ID..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="sidebar-search"
                                        />
                                    </div>
                                </div>
                                <div className="employee-list">
                                    {sidebarEmployees.map(emp => (
                                        <div
                                            key={emp.id}
                                            className={`list-item ${onlineEmployees[emp.staff_id] ? 'online' : 'offline'} ${selectedId === emp.staff_id ? 'selected' : ''}`}
                                            onClick={() => handleSelectEmployee(emp.staff_id)}
                                        >
                                            <div className="item-main">
                                                <div className="name-box" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                    {emp.photo_url ? (
                                                        <img src={emp.photo_url} alt="" style={{ width: '32px', height: '32px', borderRadius: '50%', objectFit: 'cover' }} />
                                                    ) : (
                                                        <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px', color: '#64748b' }}>
                                                            {(emp.first_name || emp.staff_id || '?').charAt(0).toUpperCase()}
                                                        </div>
                                                    )}
                                                    <div>
                                                        <div className="staff-name">{emp.staff_id}</div>
                                                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{emp.department_name}</div>
                                                    </div>
                                                    {emp.isGuest && <span className="guest-badge">Guest</span>}
                                                </div>
                                                <span className="status-indicator"></span>
                                            </div>
                                            {onlineEmployees[emp.staff_id] && (
                                                <div className="item-meta">
                                                    Last update: {onlineEmployees[emp.staff_id].lastSeen}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                                <div className="alerts-sub-header" style={{
                                    marginTop: '1rem',
                                    padding: '0.5rem 1rem', fontSize: '0.8rem', fontWeight: 600,
                                    color: '#ef4444', background: '#fee2e2', display: 'flex', alignItems: 'center', justifyContent: 'space-between'
                                }}>
                                    <span>Geo Fence Alerts ({geoFenceAlerts.length})</span>
                                </div>
                                {geoFenceAlerts.length > 0 && (
                                    <div className="alerts-list" style={{ maxHeight: '150px', overflowY: 'auto', background: '#fff5f5' }}>
                                        {geoFenceAlerts.map(alert => (
                                            <div key={alert.id} className="alert-item" style={{
                                                padding: '0.5rem 1rem', borderBottom: '1px solid #fecaca', fontSize: '0.8rem'
                                            }}>
                                                <div style={{ fontWeight: 600, color: '#b91c1c' }}>{alert.first_name || alert.staff_id}</div>
                                                <div style={{ color: '#ef4444' }}>{alert.message}</div>
                                                <div style={{ fontSize: '0.7rem', color: '#991b1b', marginTop: '2px' }}>
                                                    {new Date(alert.created_at).toLocaleTimeString()}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </aside>

                            <main className="map-container">
                                <Map
                                    center={mapCenter}
                                    zoom={zoom}
                                    onCenterChanged={(ev) => setMapCenter(ev.detail.center)}
                                    onZoomChanged={(ev) => setZoom(ev.detail.zoom)}
                                    gestureHandling={'greedy'}
                                    disableDefaultUI={false}
                                    className="google-map"
                                >
                                    {/* Site Marker if active */}
                                    {selectedSites.length === 1 && sites.find(s => s.id === selectedSites[0])?.latitude && (
                                        <Marker
                                            position={{
                                                lat: parseFloat(sites.find(s => s.id === selectedSites[0]).latitude),
                                                lng: parseFloat(sites.find(s => s.id === selectedSites[0]).longitude)
                                            }}
                                            label={{ text: "📍 Site Location", className: 'site-label' }}
                                        />
                                    )}

                                    {Object.values(onlineEmployees)
                                        .filter(loc => {
                                            const matchesSearch = loc.employeeId.toLowerCase().includes(searchQuery.toLowerCase());

                                            // Apply site filter
                                            let matchesSite = true;
                                            if (selectedSites.length > 0) {
                                                matchesSite = selectedSites.includes(loc.siteId);
                                            }

                                            return matchesSearch && matchesSite;
                                        })
                                        .map((loc, idx) => (
                                            <React.Fragment key={loc.employeeId}>
                                                <Marker
                                                    position={{ lat: loc.latitude, lng: loc.longitude }}
                                                    onClick={() => setSelectedId(loc.employeeId)}
                                                />
                                                {selectedId === loc.employeeId && (
                                                    <InfoWindow
                                                        position={{ lat: loc.latitude, lng: loc.longitude }}
                                                        onCloseClick={() => setSelectedId(null)}
                                                    >
                                                        <div className="map-popup">
                                                            {(loc.photoUrl || loc.photo_url) && (
                                                                <img src={loc.photoUrl || loc.photo_url} alt="Staff" style={{ width: '40px', height: '40px', borderRadius: '50%', objectFit: 'cover', marginBottom: '8px' }} />
                                                            )}
                                                            <strong>{loc.departmentName || loc.department_name || 'Staff'}</strong>
                                                            <div style={{ fontSize: '0.9rem', color: '#555' }}>ID: {loc.employeeId}</div>
                                                            <p style={{ margin: '4px 0', fontSize: '0.8rem' }}>Last seen: {loc.lastSeen}</p>
                                                            <small>
                                                                {typeof loc.latitude === 'number' ? loc.latitude.toFixed(5) : loc.latitude},
                                                                {typeof loc.longitude === 'number' ? loc.longitude.toFixed(5) : loc.longitude}
                                                            </small>
                                                        </div>
                                                    </InfoWindow>
                                                )}
                                            </React.Fragment>
                                        ))}
                                </Map>
                            </main>
                        </>
                    ) : activeTab === 'staff' ? (
                        <div className="management-view">
                            <div className="mgmt-subtabs">
                                <button
                                    className={`subtab-btn ${mgmtSubTab === 'staff' ? 'active' : ''}`}
                                    onClick={() => setMgmtSubTab('staff')}
                                >
                                    Staff Directory
                                </button>
                                <button
                                    className={`subtab-btn ${mgmtSubTab === 'sites' ? 'active' : ''}`}
                                    onClick={() => setMgmtSubTab('sites')}
                                >
                                    Site Locations
                                </button>
                                <button
                                    className={`subtab-btn ${mgmtSubTab === 'shifts' ? 'active' : ''}`}
                                    onClick={() => setMgmtSubTab('shifts')}
                                >
                                    Shift Schedules
                                </button>
                            </div>

                            {mgmtSubTab === 'staff' ? (
                                <>
                                    <div className="mgmt-header">
                                        <div className="mgmt-actions">
                                            <input
                                                type="text"
                                                placeholder="Search by ID or Email..."
                                                className="mgmt-search"
                                                value={mgmtSearch}
                                                onChange={(e) => { setMgmtSearch(e.target.value); setMgmtPage(1); }}
                                            />
                                            <button
                                                className="btn-primary"
                                                onClick={() => {
                                                    setCurrentUser({ staffId: '', email: '', password: '', roleId: 4, siteId: '', departmentName: 'Operations' });
                                                    setShowUserModal(true);
                                                }}>
                                                + Add New Staff
                                            </button>
                                            <button
                                                className="btn-secondary"
                                                onClick={() => {
                                                    const formattedData = formatDataForExport(mgmtUsers);
                                                    exportToCSV(formattedData, `staff_export_${new Date().toISOString().split('T')[0]}.csv`);
                                                    showToast('Staff data exported successfully', 'success');
                                                }}
                                            >
                                                📥 Export CSV
                                            </button>
                                            <button
                                                className={`btn-secondary ${showFilters ? 'active' : ''}`}
                                                onClick={() => setShowFilters(!showFilters)}
                                                style={{ background: showFilters ? '#2563eb' : '', color: showFilters ? 'white' : '' }}
                                            >
                                                🔍 Filters {(selectedRoles.length + selectedSites.length) > 0 && `(${selectedRoles.length + selectedSites.length})`}
                                            </button>
                                        </div>
                                    </div>

                                    {/* Bulk Actions Bar */}
                                    {selectedUsers.length > 0 && (
                                        <div style={{
                                            background: '#eff6ff',
                                            padding: '1rem',
                                            borderRadius: '0.5rem',
                                            marginBottom: '1rem',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'space-between',
                                            border: '1px solid #bfdbfe'
                                        }}>
                                            <div style={{ color: '#1e40af', fontWeight: '600' }}>
                                                {selectedUsers.length} user(s) selected
                                            </div>
                                            <div style={{ display: 'flex', gap: '0.75rem' }}>
                                                <button
                                                    className="btn-secondary"
                                                    onClick={handleBulkExport}
                                                >
                                                    📥 Export Selected
                                                </button>
                                                <button
                                                    className="btn-secondary"
                                                    onClick={handleBulkDelete}
                                                    style={{ background: '#fee2e2', color: '#991b1b', border: '1px solid #fecaca' }}
                                                >
                                                    🗑️ Delete Selected
                                                </button>
                                                <button
                                                    className="btn-secondary"
                                                    onClick={() => {
                                                        setSelectedUsers([]);
                                                        setSelectAll(false);
                                                    }}
                                                >
                                                    ✕ Clear Selection
                                                </button>
                                            </div>
                                        </div>
                                    )}

                                    {/* Filter Panel */}
                                    {showFilters && (
                                        <div style={{ marginBottom: '1rem' }}>
                                            <FilterPanel
                                                roles={roles}
                                                sites={sites}
                                                selectedRoles={selectedRoles}
                                                selectedSites={selectedSites}
                                                onRoleChange={setSelectedRoles}
                                                onSiteChange={setSelectedSites}
                                                onClear={clearFilters}
                                            />
                                        </div>
                                    )}

                                    <div className="mgmt-table-container">
                                        <table className="mgmt-table">
                                            <thead>
                                                <tr>
                                                    <th style={{ width: '40px' }}>
                                                        <input
                                                            type="checkbox"
                                                            checked={selectAll}
                                                            onChange={handleSelectAll}
                                                            style={{ cursor: 'pointer' }}
                                                        />
                                                    </th>
                                                    <th style={{ width: '60px' }}>Photo</th>
                                                    <th
                                                        onClick={() => {
                                                            if (sortField === 'staff_id') {
                                                                setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                                                            } else {
                                                                setSortField('staff_id');
                                                                setSortDirection('asc');
                                                            }
                                                        }}
                                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                                    >
                                                        Staff ID {sortField === 'staff_id' && (sortDirection === 'asc' ? '↑' : '↓')}
                                                    </th>
                                                    <th>Staff Name</th>
                                                    <th
                                                        onClick={() => {
                                                            if (sortField === 'email') {
                                                                setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                                                            } else {
                                                                setSortField('email');
                                                                setSortDirection('asc');
                                                            }
                                                        }}
                                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                                    >
                                                        Email {sortField === 'email' && (sortDirection === 'asc' ? '↑' : '↓')}
                                                    </th>
                                                    <th
                                                        onClick={() => {
                                                            if (sortField === 'role_name') {
                                                                setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                                                            } else {
                                                                setSortField('role_name');
                                                                setSortDirection('asc');
                                                            }
                                                        }}
                                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                                    >
                                                        Role {sortField === 'role_name' && (sortDirection === 'asc' ? '↑' : '↓')}
                                                    </th>
                                                    <th>Site</th>
                                                    <th
                                                        onClick={() => {
                                                            if (sortField === 'department_name') {
                                                                setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                                                            } else {
                                                                setSortField('department_name');
                                                                setSortDirection('asc');
                                                            }
                                                        }}
                                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                                    >
                                                        Department {sortField === 'department_name' && (sortDirection === 'asc' ? '↑' : '↓')}
                                                    </th>
                                                    <th>Actions</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {isMgmtLoading ? (
                                                    <tr>
                                                        <td colSpan="7" style={{ padding: 0, border: 'none' }}>
                                                            <LoadingSpinner size="medium" text="Loading staff..." />
                                                        </td>
                                                    </tr>
                                                ) : mgmtUsers.length === 0 ? (
                                                    <tr>
                                                        <td colSpan="7" style={{ padding: 0, border: 'none' }}>
                                                            <div className="empty-state">
                                                                <div className="empty-state-icon">👥</div>
                                                                <h3 className="empty-state-title">No Staff Found</h3>
                                                                <p className="empty-state-message">
                                                                    {mgmtSearch ? 'Try adjusting your search' : 'Get started by adding your first staff member'}
                                                                </p>
                                                            </div>
                                                        </td>
                                                    </tr>
                                                ) : (
                                                    applySorting(applyFilters(mgmtUsers)).map(u => (
                                                        <tr key={u.id} style={{ background: selectedUsers.includes(u.id) ? '#eff6ff' : '' }}>
                                                            <td>
                                                                <input
                                                                    type="checkbox"
                                                                    checked={selectedUsers.includes(u.id)}
                                                                    onChange={() => handleSelectUser(u.id)}
                                                                    style={{ cursor: 'pointer' }}
                                                                />
                                                            </td>
                                                            <td>
                                                                {u.photo_url ? (
                                                                    <img src={u.photo_url} alt="" style={{ width: '32px', height: '32px', borderRadius: '50%', objectFit: 'cover' }} />
                                                                ) : (
                                                                    <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', color: '#94a3b8' }}>
                                                                        NO IMG
                                                                    </div>
                                                                )}
                                                            </td>
                                                            <td><strong>{u.staff_id}</strong></td>
                                                            <td>{u.first_name || u.last_name ? `${u.first_name || ''} ${u.last_name || ''}`.trim() : '-'}</td>
                                                            <td>{u.email || '-'}</td>
                                                            <td><span className="role-tag">{u.role_name}</span></td>
                                                            <td>{u.site_name || 'Global'}</td>
                                                            <td>{u.department_name}</td>
                                                            <td>
                                                                <button className="btn-edit" onClick={() => {
                                                                    setCurrentUser({ ...u, password: '' });
                                                                    setShowUserModal(true);
                                                                    setValidationErrors({});
                                                                }}>Edit</button>
                                                            </td>
                                                        </tr>
                                                    ))
                                                )}
                                            </tbody>
                                        </table>
                                    </div>

                                    <div className="mgmt-pagination">
                                        <button disabled={mgmtPage === 1} onClick={() => setMgmtPage(p => p - 1)}>Previous</button>
                                        <span>Page {mgmtPage} of {mgmtStats.totalPages}</span>
                                        <button disabled={mgmtPage === mgmtStats.totalPages} onClick={() => setMgmtPage(p => p + 1)}>Next</button>
                                    </div>
                                </>
                            ) : (
                                <div className="site-management">
                                    <div className="mgmt-header">
                                        <div className="mgmt-actions">
                                            <button className="btn-primary" onClick={() => {
                                                setCurrentSite({
                                                    name: '',
                                                    location: '',
                                                    latitude: '',
                                                    longitude: '',
                                                    radiusMeters: 100,
                                                    geofenceType: 'CIRCLE',
                                                    geofenceData: null
                                                });
                                                setShowSiteModal(true);
                                            }}>
                                                + Add New Site
                                            </button>
                                        </div>
                                    </div>
                                    <div className="mgmt-table-container">
                                        <table className="mgmt-table">
                                            <thead>
                                                <tr>
                                                    <th>Site ID</th>
                                                    <th>Name</th>
                                                    <th>Location/Description</th>
                                                    <th>Actions</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {sites.map(s => (
                                                    <tr key={s.id}>
                                                        <td><strong>#{s.id}</strong></td>
                                                        <td>
                                                            <div><strong>{s.name}</strong></div>
                                                            {s.latitude && <small style={{ color: '#64748b' }}>{parseFloat(s.latitude).toFixed(4)}, {parseFloat(s.longitude).toFixed(4)}</small>}
                                                        </td>
                                                        <td>{s.location || '-'}</td>
                                                        <td>
                                                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                                                <button className="btn-edit" onClick={() => {
                                                                    setCurrentSite({
                                                                        ...s,
                                                                        radiusMeters: s.radius_meters || 100,
                                                                        geofenceType: s.geofence_type || 'CIRCLE',
                                                                        geofenceData: s.geofence_data,
                                                                        geofenceEnabled: s.geofence_enabled !== false
                                                                    });
                                                                    setShowSiteModal(true);
                                                                }}>Edit</button>
                                                                <button
                                                                    className="btn-secondary"
                                                                    style={{ padding: '0.4rem 0.8rem', fontSize: '0.75rem' }}
                                                                    onClick={() => handleFocusSite(s)}
                                                                >
                                                                    🌐 View on Map
                                                                </button>
                                                            </div>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}
                            {mgmtSubTab === 'shifts' && (
                                <div className="site-management">
                                    <div className="mgmt-header">
                                        <div className="mgmt-actions">
                                            <button className="btn-primary" onClick={() => {
                                                setCurrentShift({ name: '', startTime: '', endTime: '' });
                                                setShowShiftModal(true);
                                            }}>
                                                + Create New Shift
                                            </button>
                                        </div>
                                    </div>
                                    <div className="mgmt-table-container">
                                        <table className="mgmt-table">
                                            <thead>
                                                <tr>
                                                    <th>Shift Name</th>
                                                    <th>Start Time</th>
                                                    <th>End Time</th>
                                                    <th>Actions</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {shifts.map(s => (
                                                    <tr key={s.id}>
                                                        <td><strong>{s.name}</strong></td>
                                                        <td>{s.start_time}</td>
                                                        <td>{s.end_time}</td>
                                                        <td>
                                                            <button className="btn-edit" onClick={() => {
                                                                setCurrentShift({
                                                                    id: s.id,
                                                                    name: s.name,
                                                                    startTime: s.start_time,
                                                                    endTime: s.end_time
                                                                });
                                                                setShowShiftModal(true);
                                                            }}>Edit</button>
                                                        </td>
                                                    </tr>
                                                ))}
                                                {shifts.length === 0 && (
                                                    <tr><td colSpan="4" style={{ textAlign: 'center', padding: '2rem' }}>No shifts defined</td></tr>
                                                )}
                                            </tbody>
                                        </table>
                                    </div>

                                    {showShiftModal && (
                                        <div className="modal-overlay">
                                            <div className="modal-content">
                                                <h3>{currentShift.id ? 'Edit' : 'Create'} Shift Schedule</h3>
                                                <form onSubmit={async (e) => {
                                                    e.preventDefault();
                                                    try {
                                                        const url = currentShift.id ? `/api/hr/shifts/${currentShift.id}` : '/api/hr/shifts';
                                                        const method = currentShift.id ? 'PUT' : 'POST';

                                                        const res = await fetch(url, {
                                                            method: method,
                                                            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${user.token}` },
                                                            body: JSON.stringify(currentShift)
                                                        });

                                                        if (res.ok) {
                                                            setShowShiftModal(false);
                                                            fetch('/api/hr/shifts', { headers: { 'Authorization': `Bearer ${user.token}` } })
                                                                .then(r => r.json()).then(setShifts);
                                                            showToast(currentShift.id ? 'Shift updated' : 'Shift created', 'success');
                                                        } else {
                                                            showToast('Operation failed', 'error');
                                                        }
                                                    } catch (err) { showToast('Error saving shift', 'error'); }
                                                }}>
                                                    <div className="form-group">
                                                        <label>Shift Name</label>
                                                        <input required type="text" value={currentShift.name} onChange={e => setCurrentShift({ ...currentShift, name: e.target.value })} placeholder="e.g. Morning Shift" />
                                                    </div>
                                                    <div className="form-grid">
                                                        <div className="form-group">
                                                            <label>Start Time</label>
                                                            <input required type="time" value={currentShift.startTime} onChange={e => setCurrentShift({ ...currentShift, startTime: e.target.value })} />
                                                        </div>
                                                        <div className="form-group">
                                                            <label>End Time</label>
                                                            <input required type="time" value={currentShift.endTime} onChange={e => setCurrentShift({ ...currentShift, endTime: e.target.value })} />
                                                        </div>
                                                    </div>
                                                    <div className="modal-footer">
                                                        <button type="button" className="btn-secondary" onClick={() => setShowShiftModal(false)}>Cancel</button>
                                                        <button type="submit" className="btn-primary">{currentShift.id ? 'Save Changes' : 'Create Shift'}</button>
                                                    </div>
                                                </form>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ) : activeTab === 'analytics' ? (
                        <div className="management-view">
                            <div style={{ marginBottom: '2rem' }}>
                                <h2 style={{ margin: 0, color: '#1e293b', fontSize: '1.75rem' }}>Analytics Overview</h2>
                                <p style={{ margin: '0.5rem 0 0', color: '#64748b' }}>Comprehensive insights into your workforce and site operations</p>
                            </div>

                            {/* Analytics Cards Grid */}
                            <div className="analytics-modern-grid">
                                <div className="analytics-modern-card blue">
                                    <div className="card-icon">👥</div>
                                    <div className="card-content">
                                        <span className="card-label">Total Staff</span>
                                        <span className="card-value">{mgmtStats.total}</span>
                                        <span className="card-subtext">Registered Employees</span>
                                    </div>
                                    <div className="card-decoration"></div>
                                </div>

                                <div className="analytics-modern-card green">
                                    <div className="card-icon">⚡</div>
                                    <div className="card-content">
                                        <span className="card-label">Active Today</span>
                                        <span className="card-value">{Object.keys(onlineEmployees).length}</span>
                                        <span className="card-subtext">{Object.keys(onlineEmployees).length} Online Now</span>
                                    </div>
                                    <div className="card-decoration"></div>
                                </div>

                                <div className="analytics-modern-card orange">
                                    <div className="card-icon">📍</div>
                                    <div className="card-content">
                                        <span className="card-label">Total Sites</span>
                                        <span className="card-value">{sites.length}</span>
                                        <span className="card-subtext">Active Locations</span>
                                    </div>
                                    <div className="card-decoration"></div>
                                </div>

                                <div className="analytics-modern-card purple">
                                    <div className="card-icon">🏢</div>
                                    <div className="card-content">
                                        <span className="card-label">Departments</span>
                                        <span className="card-value">{new Set(mgmtUsers.map(u => u.department_name)).size}</span>
                                        <span className="card-subtext">Functional Groups</span>
                                    </div>
                                    <div className="card-decoration"></div>
                                </div>
                            </div>

                            <div className="analytics-detailed-sections">
                                {/* Role Distribution */}
                                <div className="distribution-card">
                                    <div className="dist-header">
                                        <h3>Workforce Composition</h3>
                                        <span>By Role</span>
                                    </div>
                                    <div className="dist-body">
                                        {roles.map(role => {
                                            const count = mgmtUsers.filter(u => u.role_name === role.name).length;
                                            const percentage = mgmtStats.total > 0 ? ((count / mgmtStats.total) * 100).toFixed(1) : 0;
                                            return (
                                                <div key={role.id} className="dist-row">
                                                    <div className="dist-info">
                                                        <span className="dist-name">{role.name}</span>
                                                        <span className="dist-count">{count}</span>
                                                    </div>
                                                    <div className="dist-progress-bg">
                                                        <div className="dist-progress-fill" style={{ width: `${percentage}%`, background: 'var(--primary-color)' }}></div>
                                                    </div>
                                                    <span className="dist-percent">{percentage}%</span>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>

                                {/* Site Distribution */}
                                <div className="distribution-card">
                                    <div className="dist-header">
                                        <h3>Site Allocation</h3>
                                        <span>By Location</span>
                                    </div>
                                    <div className="dist-body">
                                        {sites.slice(0, 5).map(site => {
                                            const count = mgmtUsers.filter(u => u.site_id === site.id).length;
                                            const percentage = mgmtStats.total > 0 ? ((count / mgmtStats.total) * 100).toFixed(1) : 0;
                                            return (
                                                <div key={site.id} className="dist-row">
                                                    <div className="dist-info">
                                                        <span className="dist-name">{site.name}</span>
                                                        <span className="dist-count">{count}</span>
                                                    </div>
                                                    <div className="dist-progress-bg">
                                                        <div className="dist-progress-fill" style={{ width: `${percentage}%`, background: '#f59e0b' }}></div>
                                                    </div>
                                                    <span className="dist-percent">{percentage}%</span>
                                                </div>
                                            );
                                        })}
                                        <div className="dist-row">
                                            <div className="dist-info">
                                                <span className="dist-name">Global / Others</span>
                                                <span className="dist-count">{mgmtUsers.filter(u => !u.site_id || !sites.slice(0, 5).find(s => s.id === u.site_id)).length}</span>
                                            </div>
                                            <div className="dist-progress-bg">
                                                <div className="dist-progress-fill" style={{ width: '0%', background: '#94a3b8' }}></div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Quick Actions */}
                            <div className="analytics-actions-bar">
                                <div className="actions-text">
                                    <h4>System Reports</h4>
                                    <p>Export latest dataset for offline analysis</p>
                                </div>
                                <div className="actions-buttons">
                                    <button
                                        className="modern-action-btn"
                                        onClick={() => {
                                            const formattedData = formatDataForExport(mgmtUsers);
                                            exportToCSV(formattedData, `staff_export_${new Date().toISOString().split('T')[0]}.csv`);
                                            showToast('Staff data exported successfully', 'success');
                                        }}
                                    >
                                        📥 Employees CSV
                                    </button>
                                    <button
                                        className="modern-action-btn secondary"
                                        onClick={() => {
                                            const formattedData = formatSitesForExport(sites);
                                            exportToCSV(formattedData, `sites_export_${new Date().toISOString().split('T')[0]}.csv`);
                                            showToast('Sites data exported successfully', 'success');
                                        }}
                                    >
                                        📥 Sites CSV
                                    </button>
                                </div>
                            </div>
                        </div>
                    ) : activeTab === 'attendance' ? (
                        <div className="logs-container">
                            <div className="logs-card">
                                <div className="logs-header">
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                        <h2>🕒 Live Attendance Logs</h2>
                                        <div className="logs-search-wrapper">
                                            <svg className="search-icon-svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <circle cx="11" cy="11" r="8"></circle>
                                                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                                            </svg>
                                            <input
                                                type="text"
                                                placeholder="Filter logs by Name or ID..."
                                                className="logs-search-input"
                                                value={logSearch}
                                                onChange={(e) => setLogSearch(e.target.value)}
                                            />
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', gap: '1rem' }}>
                                        <button className="btn-secondary" onClick={() => {
                                            fetch('/api/hr/attendance', { headers: { 'Authorization': `Bearer ${user.token}` } })
                                                .then(res => res.json())
                                                .then(setAttendanceLogs);
                                            showToast('Logs refreshed', 'info');
                                        }}>
                                            🔄 Refresh Data
                                        </button>
                                    </div>
                                </div>
                                <div className="logs-table-container">
                                    <table className="mgmt-table">
                                        <thead>
                                            <tr>
                                                <th>Staff Member</th>
                                                <th>Check In</th>
                                                <th>Check Out</th>
                                                <th>Site Location</th>
                                                <th style={{ textAlign: 'center' }}>Status</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {attendanceLogs
                                                .filter(log => {
                                                    const name = `${log.first_name || ''} ${log.last_name || ''}`.toLowerCase();
                                                    const sId = (log.staff_id || '').toLowerCase();
                                                    const query = logSearch.toLowerCase();
                                                    return name.includes(query) || sId.includes(query);
                                                })
                                                .map((log, i) => {
                                                    const hasCheckOut = !!log.check_out_time;
                                                    const checkIn = new Date(log.check_in_time);
                                                    const checkOut = hasCheckOut ? new Date(log.check_out_time) : null;

                                                    return (
                                                        <tr key={log.id || i} className={log.is_live ? 'live-row' : ''}>
                                                            <td>
                                                                <div className="staff-info-cell">
                                                                    <div className="staff-avatar-mini">
                                                                        {(log.first_name || log.staff_id || '?')[0].toUpperCase()}
                                                                    </div>
                                                                    <div>
                                                                        <div style={{ fontWeight: 600, color: '#1e293b' }}>
                                                                            {log.first_name || log.last_name ? `${log.first_name || ''} ${log.last_name || ''}`.trim() : 'Unnamed Employee'}
                                                                        </div>
                                                                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{log.staff_id}</div>
                                                                    </div>
                                                                </div>
                                                            </td>
                                                            <td>
                                                                <div className="time-display">
                                                                    <span className="date">{checkIn.toLocaleDateString()}</span>
                                                                    <span className="time">{checkIn.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                                                </div>
                                                            </td>
                                                            <td>
                                                                {hasCheckOut ? (
                                                                    <div className="time-display">
                                                                        <span className="date">{checkOut.toLocaleDateString()}</span>
                                                                        <span className="time">{checkOut.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                                                    </div>
                                                                ) : (
                                                                    <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>--:--</span>
                                                                )}
                                                            </td>
                                                            <td>
                                                                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                                                    <span style={{ fontSize: '0.9rem' }}>📍</span>
                                                                    <span>{log.site_name || 'Generic Site'}</span>
                                                                </div>
                                                            </td>
                                                            <td style={{ textAlign: 'center' }}>
                                                                <span className={`status-badge-pill ${hasCheckOut ? 'completed' : 'active'}`}>
                                                                    {hasCheckOut ? 'Completed' : 'Active Now'}
                                                                </span>
                                                            </td>
                                                        </tr>
                                                    );
                                                })}
                                            {attendanceLogs.length === 0 && (
                                                <tr>
                                                    <td colSpan="5" style={{ textAlign: 'center', padding: '4rem', color: '#94a3b8' }}>
                                                        <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>📋</div>
                                                        No recent attendance records found.
                                                    </td>
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    ) : activeTab === 'location_logs' ? (
                        <LocationLogsView
                            user={user}
                            locationLogs={locationLogs}
                            setLocationLogs={setLocationLogs}
                            locLogSearch={locLogSearch}
                            setLocLogSearch={setLocLogSearch}
                            locLogStartDate={locLogStartDate}
                            setLocLogStartDate={setLocLogStartDate}
                            locLogEndDate={locLogEndDate}
                            setLocLogEndDate={setLocLogEndDate}
                            locLogPage={locLogPage}
                            setLocLogPage={setLocLogPage}
                            locLogTotal={locLogTotal}
                            setLocLogTotal={setLocLogTotal}
                            locLogTotalPages={locLogTotalPages}
                            setLocLogTotalPages={setLocLogTotalPages}
                            locLogLoading={locLogLoading}
                            setLocLogLoading={setLocLogLoading}
                            locLogSelected={locLogSelected}
                            setLocLogSelected={setLocLogSelected}
                            locLogSelectAll={locLogSelectAll}
                            setLocLogSelectAll={setLocLogSelectAll}
                            LOC_LOG_LIMIT={LOC_LOG_LIMIT}
                            showToast={showToast}
                            confirmDialog={confirmDialog}
                            setConfirmDialog={setConfirmDialog}
                        />
                    ) : activeTab === 'geo_fence_alerts' ? (
                        <GeoFenceAlertsView
                            user={user}
                            sites={sites}
                            geoFenceAlerts={geoFenceAlerts}
                            setGeoFenceAlerts={setGeoFenceAlerts}
                            gfPage={gfPage}
                            setGfPage={setGfPage}
                            gfTotal={gfTotal}
                            setGfTotal={setGfTotal}
                            gfTotalPages={gfTotalPages}
                            setGfTotalPages={setGfTotalPages}
                            gfLoading={gfLoading}
                            setGfLoading={setGfLoading}
                            gfSearch={gfSearch}
                            setGfSearch={setGfSearch}
                            gfSiteFilter={gfSiteFilter}
                            setGfSiteFilter={setGfSiteFilter}
                            gfStatusFilter={gfStatusFilter}
                            setGfStatusFilter={setGfStatusFilter}
                            gfStartDate={gfStartDate}
                            setGfStartDate={setGfStartDate}
                            gfEndDate={gfEndDate}
                            setGfEndDate={setGfEndDate}
                            GF_LIMIT={GF_LIMIT}
                            showToast={showToast}
                        />
                    ) : activeTab === 'reports' ? (
                        <div className="management-view">
                            <ReportsView
                                user={user}
                                sites={sites}
                                roles={roles}
                                showToast={showToast}
                            />
                        </div>
                    ) : activeTab === 'route_tracking' ? (
                        <>
                            <aside className="sidebar">
                                <RouteTrackingView
                                    user={user}
                                    employees={employees}
                                    onMapUpdate={(center, zoom) => {
                                        setMapCenter(center);
                                        setZoom(zoom);
                                    }}
                                    routeData={routeData}
                                    onRouteDataChange={setRouteData}
                                    idleThreshold={idleThreshold}
                                    setIdleThreshold={setIdleThreshold}
                                    showToast={showToast}
                                    googleMapsApiKey={GOOGLE_MAPS_API_KEY}
                                />
                            </aside>
                            <main className="map-container">
                                <Map
                                    mapId="route-tracking-map"
                                    center={mapCenter}
                                    zoom={zoom}
                                    gestureHandling="greedy"
                                    disableDefaultUI={false}
                                    onCenterChanged={(e) => setMapCenter(e.detail.center)}
                                    onZoomChanged={(e) => setZoom(e.detail.zoom)}
                                >
                                    {/* Render route polyline if route data exists */}
                                    {routeData && <RoutePolyline routeData={routeData} idleThreshold={idleThreshold} />}

                                    {/* Render site markers */}
                                    {sites.map(site => {
                                        if (!site.latitude || !site.longitude) return null;
                                        return (
                                            <Marker
                                                key={`site-${site.id}`}
                                                position={{ lat: parseFloat(site.latitude), lng: parseFloat(site.longitude) }}
                                                icon={{
                                                    path: window.google.maps.SymbolPath.CIRCLE,
                                                    scale: 10,
                                                    fillColor: '#f59e0b',
                                                    fillOpacity: 0.6,
                                                    strokeColor: '#ffffff',
                                                    strokeWeight: 2
                                                }}
                                                title={site.name}
                                            />
                                        );
                                    })}
                                </Map>
                            </main>
                        </>
                    ) : activeTab === 'idle_reporting' ? (
                        <>
                            <aside className="sidebar">
                                <IdleReportingView
                                    user={user}
                                    employees={employees}
                                    onMapUpdate={(center, zoom) => {
                                        setMapCenter(center);
                                        setZoom(zoom);
                                    }}
                                    idleSpots={idleSpots}
                                    onIdleSpotsChange={setIdleSpots}
                                    showToast={showToast}
                                    googleMapsApiKey={GOOGLE_MAPS_API_KEY}
                                />
                            </aside>
                            <main className="map-container">
                                <Map
                                    mapId="idle-reporting-map"
                                    center={mapCenter}
                                    zoom={zoom}
                                    gestureHandling="greedy"
                                    disableDefaultUI={false}
                                    onCenterChanged={(e) => setMapCenter(e.detail.center)}
                                    onZoomChanged={(e) => setZoom(e.detail.zoom)}
                                >
                                    {/* Render Idle Spots Markers */}
                                    {idleSpots.map((spot, index) => (
                                        <Marker
                                            key={`idle-${index}`}
                                            position={{ lat: parseFloat(spot.lat), lng: parseFloat(spot.lng) }}
                                            icon={{
                                                path: window.google?.maps?.SymbolPath?.CIRCLE ?? 0,
                                                scale: 25,
                                                fillColor: '#f59e0b',
                                                fillOpacity: 0.3,
                                                strokeColor: '#f59e0b',
                                                strokeWeight: 2,
                                                strokeOpacity: 0.8
                                            }}
                                            zIndex={4500}
                                            title={`Stayed here for ${spot.duration} minutes\nFrom: ${new Date(spot.startTime).toLocaleTimeString()}\nTo: ${new Date(spot.endTime).toLocaleTimeString()}`}
                                        />
                                    ))}

                                    {/* Render site markers */}
                                    {sites.map(site => {
                                        if (!site.latitude || !site.longitude) return null;
                                        return (
                                            <Marker
                                                key={`site-${site.id}`}
                                                position={{ lat: parseFloat(site.latitude), lng: parseFloat(site.longitude) }}
                                                icon={{
                                                    path: window.google?.maps?.SymbolPath?.CIRCLE ?? 0,
                                                    scale: 10,
                                                    fillColor: '#f59e0b',
                                                    fillOpacity: 0.6,
                                                    strokeColor: '#ffffff',
                                                    strokeWeight: 2
                                                }}
                                                title={site.name}
                                            />
                                        );
                                    })}
                                </Map>
                            </main>
                        </>
                    ) : activeTab === 'access_roles' ? (
                        <div className="management-view">
                            <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '2rem', height: '100%', alignItems: 'start' }}>
                                {/* Roles List */}
                                <div className="card" style={{ padding: '0', overflow: 'hidden', height: 'calc(100vh - 140px)', display: 'flex', flexDirection: 'column' }}>
                                    <div style={{ padding: '1.5rem', borderBottom: '1px solid #e2e8f0' }}>
                                        <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#1e293b' }}>Access Roles</h3>
                                        <p style={{ margin: '0.5rem 0 0', color: '#64748b', fontSize: '0.875rem' }}>Select a role to view permissions</p>
                                    </div>
                                    <div className="role-list" style={{ overflowY: 'auto', flex: 1 }}>
                                        {roles.map(role => (
                                            <div
                                                key={role.id}
                                                className={`list-item ${selectedRole?.id === role.id ? 'selected' : ''}`}
                                                onClick={() => setSelectedRole(role)}
                                                style={{
                                                    padding: '1rem 1.5rem',
                                                    cursor: 'pointer',
                                                    borderBottom: '1px solid #f1f5f9',
                                                    background: selectedRole?.id === role.id ? '#eff6ff' : 'transparent',
                                                    borderLeft: selectedRole?.id === role.id ? '4px solid #2563eb' : '4px solid transparent'
                                                }}
                                            >
                                                <div style={{ fontWeight: '600', color: selectedRole?.id === role.id ? '#1e40af' : '#334155' }}>{role.name}</div>
                                                <div style={{ fontSize: '0.75rem', color: selectedRole?.id === role.id ? '#3b82f6' : '#94a3b8', marginTop: '4px' }}>
                                                    {role.permissions ? role.permissions.length : 0} permissions assigned
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Role Details */}
                                <div className="card" style={{ height: 'calc(100vh - 140px)', overflowY: 'auto' }}>
                                    {selectedRole ? (
                                        <>
                                            <div style={{ borderBottom: '1px solid #e2e8f0', paddingBottom: '1.5rem', marginBottom: '2rem' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                                        <h2 style={{ margin: 0, fontSize: '1.875rem', color: '#0f172a' }}>{selectedRole.name}</h2>
                                                        <span className="role-tag" style={{ fontSize: '0.875rem', padding: '0.25rem 0.75rem' }}>Active Role</span>
                                                    </div>
                                                    {!isEditingPermissions ? (
                                                        <button
                                                            className="btn-primary"
                                                            onClick={handleStartEditPermissions}
                                                            style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}
                                                        >
                                                            ✏️ Edit Permissions
                                                        </button>
                                                    ) : (
                                                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                                                            <button
                                                                className="btn-secondary"
                                                                onClick={() => setIsEditingPermissions(false)}
                                                                disabled={isLoading}
                                                            >
                                                                Cancel
                                                            </button>
                                                            <button
                                                                className="btn-primary"
                                                                onClick={handleSavePermissions}
                                                                disabled={isLoading}
                                                            >
                                                                {isLoading ? 'Saving...' : 'Save Changes'}
                                                            </button>
                                                        </div>
                                                    )}
                                                </div>
                                                <p style={{ color: '#64748b', margin: 0, fontSize: '1rem' }}>
                                                    This role grants access to the following screens and functionalities within the system.
                                                </p>
                                            </div>

                                            <div style={{ display: 'grid', gap: '2rem' }}>
                                                <div>
                                                    <h4 style={{
                                                        color: '#334155',
                                                        marginBottom: '1rem',
                                                        fontSize: '1.1rem',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '0.5rem'
                                                    }}>
                                                        <span style={{ fontSize: '1.25rem' }}>🔐</span> Available Screens & Permissions
                                                    </h4>

                                                    {isEditingPermissions ? (
                                                        <div className="permissions-edit-grid" style={{
                                                            display: 'grid',
                                                            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                                                            gap: '1rem'
                                                        }}>
                                                            {allPermissions.map(perm => {
                                                                const isChecked = tempPermissions.includes(perm.id);
                                                                return (
                                                                    <div
                                                                        key={perm.id}
                                                                        onClick={() => handleTogglePermission(perm.id)}
                                                                        style={{
                                                                            border: isChecked ? '1px solid #2563eb' : '1px solid #e2e8f0',
                                                                            background: isChecked ? '#eff6ff' : '#fff',
                                                                            borderRadius: '8px',
                                                                            padding: '1rem',
                                                                            cursor: 'pointer',
                                                                            display: 'flex',
                                                                            alignItems: 'flex-start',
                                                                            gap: '1rem',
                                                                            transition: 'all 0.2s'
                                                                        }}
                                                                    >
                                                                        <div style={{
                                                                            width: '20px',
                                                                            height: '20px',
                                                                            borderRadius: '4px',
                                                                            border: isChecked ? 'none' : '2px solid #cbd5e1',
                                                                            background: isChecked ? '#2563eb' : 'transparent',
                                                                            display: 'flex',
                                                                            alignItems: 'center',
                                                                            justifyContent: 'center',
                                                                            color: 'white',
                                                                            flexShrink: 0,
                                                                            marginTop: '2px'
                                                                        }}>
                                                                            {isChecked && '✓'}
                                                                        </div>
                                                                        <div>
                                                                            <div style={{ fontWeight: '600', color: '#1e293b', marginBottom: '0.25rem' }}>
                                                                                {formatPermissionName(perm.name)}
                                                                            </div>
                                                                            <div style={{ fontSize: '0.875rem', color: '#64748b' }}>
                                                                                {perm.description}
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                );
                                                            })}
                                                        </div>
                                                    ) : (
                                                        selectedRole.permissions && selectedRole.permissions.length > 0 ? (
                                                            <div className="permissions-grid" style={{
                                                                display: 'grid',
                                                                gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
                                                                gap: '1rem'
                                                            }}>
                                                                {selectedRole.permissions.map((perm, idx) => (
                                                                    <div key={idx} style={{
                                                                        background: '#fff',
                                                                        padding: '1.25rem',
                                                                        borderRadius: '12px',
                                                                        border: '1px solid #e2e8f0',
                                                                        boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                                                                        transition: 'transform 0.2s',
                                                                        cursor: 'default'
                                                                    }}>
                                                                        <div style={{
                                                                            width: '32px',
                                                                            height: '32px',
                                                                            borderRadius: '8px',
                                                                            background: '#eff6ff',
                                                                            color: '#2563eb',
                                                                            display: 'flex',
                                                                            alignItems: 'center',
                                                                            justifyContent: 'center',
                                                                            marginBottom: '1rem',
                                                                            fontSize: '1.25rem'
                                                                        }}>
                                                                            {getPermissionIcon(perm.name)}
                                                                        </div>
                                                                        <div style={{ fontWeight: '600', color: '#1e293b', marginBottom: '0.5rem' }}>
                                                                            {formatPermissionName(perm.name)}
                                                                        </div>
                                                                        <div style={{ fontSize: '0.875rem', color: '#64748b', lineHeight: '1.5' }}>
                                                                            {perm.description || 'Access granted to this feature.'}
                                                                        </div>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        ) : (
                                                            <div style={{
                                                                padding: '3rem',
                                                                textAlign: 'center',
                                                                color: '#64748b',
                                                                background: '#f8fafc',
                                                                borderRadius: '12px',
                                                                border: '2px dashed #e2e8f0'
                                                            }}>
                                                                <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>🚫</div>
                                                                <h3 style={{ margin: '0 0 0.5rem 0', color: '#475569' }}>No Permissions Assigned</h3>
                                                                <p style={{ margin: 0 }}>This role currently has no specific access permissions configured.</p>
                                                            </div>
                                                        )
                                                    )}
                                                </div>
                                            </div>
                                        </>
                                    ) : (
                                        <div style={{
                                            display: 'flex',
                                            flexDirection: 'column',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            height: '100%',
                                            color: '#94a3b8',
                                            background: '#f8fafc',
                                            borderRadius: '0 12px 12px 0'
                                        }}>
                                            <div style={{ fontSize: '4rem', marginBottom: '1.5rem', opacity: 0.5 }}>👈</div>
                                            <h3 style={{ margin: '0 0 0.5rem 0', color: '#475569' }}>Select a Role</h3>
                                            <p style={{ margin: 0 }}>Choose a role from the list to view its access details.</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ) : null}
                </div>

                {
                    showUserModal && (
                        <div className="modal-overlay">
                            <div className="modal-content">
                                <h3>{currentUser.id ? 'Edit' : 'Add'} Staff Member</h3>
                                <form onSubmit={handleSaveUser}>
                                    <div className="form-grid">
                                        <div className="form-group">
                                            <label>First Name</label>
                                            <input
                                                type="text"
                                                value={currentUser.firstName !== undefined ? currentUser.firstName : (currentUser.first_name || '')}
                                                onChange={(e) => setCurrentUser({ ...currentUser, firstName: e.target.value })}
                                                placeholder="e.g. John"
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>Last Name</label>
                                            <input
                                                type="text"
                                                value={currentUser.lastName !== undefined ? currentUser.lastName : (currentUser.last_name || '')}
                                                onChange={(e) => setCurrentUser({ ...currentUser, lastName: e.target.value })}
                                                placeholder="e.g. Doe"
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>Staff ID</label>
                                            <input
                                                type="text"
                                                value={currentUser.staff_id || currentUser.staffId}
                                                onChange={(e) => setCurrentUser({ ...currentUser, staffId: e.target.value })}
                                                required
                                                disabled={!!currentUser.id}
                                                className={validationErrors.staffId ? 'input-error' : ''}
                                            />
                                            {validationErrors.staffId && (
                                                <span className="error-message">{validationErrors.staffId}</span>
                                            )}
                                        </div>
                                        <div className="form-group">
                                            <label>Email</label>
                                            <input
                                                type="email"
                                                value={currentUser.email}
                                                onChange={(e) => setCurrentUser({ ...currentUser, email: e.target.value })}
                                                className={validationErrors.email ? 'input-error' : ''}
                                            />
                                            {validationErrors.email && (
                                                <span className="error-message">{validationErrors.email}</span>
                                            )}
                                        </div>
                                        <div className="form-group">
                                            <label>Password {currentUser.id && '(Leave blank to keep current)'}</label>
                                            <input
                                                type="password"
                                                value={currentUser.password}
                                                onChange={(e) => setCurrentUser({ ...currentUser, password: e.target.value })}
                                                required={!currentUser.id}
                                                className={validationErrors.password ? 'input-error' : ''}
                                            />
                                            {validationErrors.password && (
                                                <span className="error-message">{validationErrors.password}</span>
                                            )}
                                        </div>
                                        <div className="form-group">
                                            <label>Role</label>
                                            <select
                                                value={currentUser.role_id || currentUser.roleId}
                                                onChange={(e) => setCurrentUser({ ...currentUser, roleId: e.target.value })}
                                            >
                                                {roles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                                            </select>
                                        </div>
                                        <div className="form-group">
                                            <label>Site Assignment</label>
                                            <select
                                                value={currentUser.site_id || currentUser.siteId}
                                                onChange={(e) => setCurrentUser({ ...currentUser, siteId: e.target.value })}
                                            >
                                                <option value="">Global / All Sites</option>
                                                {sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                                            </select>
                                        </div>
                                        <div className="form-group">
                                            <label>Department</label>
                                            <input
                                                type="text"
                                                value={currentUser.department_name || currentUser.departmentName}
                                                onChange={(e) => setCurrentUser({ ...currentUser, departmentName: e.target.value })}
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>Shift Schedule</label>
                                            <select
                                                value={currentUser.shift_id || currentUser.shiftId || ''}
                                                onChange={(e) => setCurrentUser({ ...currentUser, shiftId: e.target.value })}
                                            >
                                                <option value="">No Shift Assigned</option>
                                                {shifts.map(s => <option key={s.id} value={s.id}>{s.name} ({s.start_time} - {s.end_time})</option>)}
                                            </select>
                                        </div>
                                        <div className="form-group">
                                            <label>Photo</label>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                                {(currentUser.photo_url || currentUser.photoUrl) && !currentUser.photoHelper && (
                                                    <img src={currentUser.photo_url || currentUser.photoUrl} alt="Current" style={{ width: '40px', height: '40px', borderRadius: '50%', objectFit: 'cover' }} />
                                                )}
                                                {currentUser.photoHelper && (
                                                    <img src={currentUser.photoHelper} alt="Preview" style={{ width: '40px', height: '40px', borderRadius: '50%', objectFit: 'cover' }} />
                                                )}
                                                <input
                                                    type="file"
                                                    accept="image/*"
                                                    onChange={(e) => {
                                                        const file = e.target.files[0];
                                                        if (file) {
                                                            const reader = new FileReader();
                                                            reader.onloadend = () => {
                                                                setCurrentUser({ ...currentUser, photoHelper: reader.result });
                                                            };
                                                            reader.readAsDataURL(file);
                                                        }
                                                    }}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                    <div className="modal-footer">
                                        <button type="button" className="btn-secondary" onClick={() => setShowUserModal(false)}>Cancel</button>
                                        <button type="submit" className="btn-primary" disabled={isLoading}>
                                            {isLoading ? 'Saving...' : 'Save Changes'}
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    )
                }

                {
                    showSiteModal && (
                        <div className="modal-overlay">
                            <div className="modal-content">
                                <h3>{currentSite.id ? 'Edit' : 'Add'} Site Location</h3>
                                <form onSubmit={handleSaveSite}>
                                    <div className="form-grid" style={{ gridTemplateColumns: '1fr' }}>
                                        <div className="form-group">
                                            <label>Site Name</label>
                                            <input
                                                type="text"
                                                value={currentSite.name}
                                                onChange={(e) => setCurrentSite({ ...currentSite, name: e.target.value })}
                                                required
                                                placeholder="e.g. Dubai South Hub"
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>Location/Description</label>
                                            <input
                                                type="text"
                                                value={currentSite.location}
                                                onChange={(e) => setCurrentSite({ ...currentSite, location: e.target.value })}
                                                placeholder="Address or area description"
                                            />
                                        </div>
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
                                            <div className="form-group">
                                                <label>Latitude</label>
                                                <input
                                                    type="number"
                                                    step="any"
                                                    value={currentSite.latitude}
                                                    onChange={(e) => setCurrentSite({ ...currentSite, latitude: e.target.value })}
                                                    placeholder="e.g. 25.2048"
                                                />
                                            </div>
                                            <div className="form-group">
                                                <label>Longitude</label>
                                                <input
                                                    type="number"
                                                    step="any"
                                                    value={currentSite.longitude}
                                                    onChange={(e) => setCurrentSite({ ...currentSite, longitude: e.target.value })}
                                                    placeholder="e.g. 55.2708"
                                                />
                                            </div>
                                            <div className="form-group">
                                                <label>Radius (Meters)</label>
                                                <input
                                                    type="number"
                                                    value={currentSite.radiusMeters || 100}
                                                    onChange={(e) => setCurrentSite({ ...currentSite, radiusMeters: parseInt(e.target.value) })}
                                                    placeholder="100"
                                                />
                                            </div>
                                        </div>

                                        <div className="location-picker-section" style={{ marginTop: '1rem', borderTop: '1px solid #eee', paddingTop: '1rem' }}>
                                            <PlaceAutocomplete onPlaceSelect={(place) => {
                                                if (place.geometry && place.geometry.location) {
                                                    const lat = place.geometry.location.lat();
                                                    const lng = place.geometry.location.lng();
                                                    setCurrentSite(prev => ({
                                                        ...prev,
                                                        latitude: lat,
                                                        longitude: lng,
                                                        location: place.formatted_address || prev.location
                                                    }));
                                                    // Also move map view to the selected place
                                                    setMapCenter({ lat: parseFloat(lat), lng: parseFloat(lng) });
                                                    setZoom(16);
                                                }
                                            }} />

                                            <div style={{ height: '300px', width: '100%', borderRadius: '8px', overflow: 'hidden', marginTop: '10px', position: 'relative' }}>
                                                <Map
                                                    center={{
                                                        lat: parseFloat(currentSite.latitude) || 25.2048,
                                                        lng: parseFloat(currentSite.longitude) || 55.2708
                                                    }}
                                                    zoom={currentSite.latitude ? 16 : 11}
                                                    onClick={(e) => {
                                                        if (currentSite.geofenceType !== 'POLYGON') {
                                                            setCurrentSite({
                                                                ...currentSite,
                                                                latitude: e.detail.latLng.lat.toString(),
                                                                longitude: e.detail.latLng.lng.toString()
                                                            });
                                                        }
                                                    }}
                                                    gestureHandling={'greedy'}
                                                    disableDefaultUI={false}
                                                    zoomControl={true}
                                                    mapId="site-map"
                                                >
                                                    <GeofenceManager
                                                        type={currentSite.geofenceType || 'CIRCLE'}
                                                        data={currentSite.geofenceData}
                                                        radius={currentSite.radiusMeters || 100}
                                                        center={{ lat: parseFloat(currentSite.latitude), lng: parseFloat(currentSite.longitude) }}
                                                        onChange={(newGeofence) => {
                                                            setCurrentSite(prev => ({
                                                                ...prev,
                                                                ...newGeofence
                                                            }));
                                                        }}
                                                    />
                                                    {currentSite.latitude && currentSite.longitude && currentSite.geofenceType !== 'POLYGON' && (
                                                        <Marker position={{
                                                            lat: parseFloat(currentSite.latitude),
                                                            lng: parseFloat(currentSite.longitude)
                                                        }} />
                                                    )}
                                                </Map>
                                            </div>
                                            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem', alignItems: 'center' }}>
                                                <label style={{ fontWeight: 600 }}>Geofence Check:</label>
                                                <button type="button"
                                                    onClick={() => setCurrentSite({ ...currentSite, geofenceType: 'CIRCLE' })}
                                                    className={(!currentSite.geofenceType || currentSite.geofenceType === 'CIRCLE') ? 'btn-primary' : 'btn-secondary'}
                                                    style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                                                >
                                                    Standard Radius (Circle)
                                                </button>
                                                <button type="button"
                                                    onClick={() => setCurrentSite({ ...currentSite, geofenceType: 'POLYGON' })}
                                                    className={currentSite.geofenceType === 'POLYGON' ? 'btn-primary' : 'btn-secondary'}
                                                    style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                                                >
                                                    Custom Area (Polygon)
                                                </button>
                                            </div>
                                            <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '5px' }}>
                                                {currentSite.geofenceType === 'POLYGON'
                                                    ? "Use the drawing tools on the map (top center) to draw the site boundary. Requires at least 3 points."
                                                    : "Click on the map to set center. Enter radius above or drag the circle edge (if visible) to adjust."}
                                            </p>
                                        </div>

                                        <div style={{ padding: '1rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0', marginTop: '1rem' }}>
                                            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontWeight: 600 }}>
                                                <input
                                                    type="checkbox"
                                                    checked={currentSite.geofenceEnabled !== false}
                                                    onChange={(e) => setCurrentSite({ ...currentSite, geofenceEnabled: e.target.checked })}
                                                    style={{ width: '20px', height: '20px' }}
                                                />
                                                Enforce Geofencing for this site
                                            </label>
                                            <p style={{ fontSize: '0.75rem', color: '#64748b', marginLeft: '30px', marginTop: '4px' }}>
                                                If disabled, staff assigned to this site will not trigger alerts even if they are outside the perimeter.
                                            </p>
                                        </div>
                                    </div>
                                    <div className="modal-footer">
                                        <button type="button" className="btn-secondary" onClick={() => setShowSiteModal(false)}>Cancel</button>
                                        <button type="submit" className="btn-primary">Save Site</button>
                                    </div>
                                </form>
                            </div>
                        </div >
                    )
                }

                {/* Toast Notifications */}
                <div className="toast-container">
                    {toasts.map(toast => (
                        <Toast
                            key={toast.id}
                            message={toast.message}
                            type={toast.type}
                            onClose={() => removeToast(toast.id)}
                        />
                    ))}
                </div>

                {/* Confirmation Dialog */}
                <ConfirmDialog
                    isOpen={confirmDialog.isOpen}
                    title={confirmDialog.title}
                    message={confirmDialog.message}
                    confirmText={confirmDialog.confirmText}
                    cancelText={confirmDialog.cancelText}
                    type={confirmDialog.type}
                    onConfirm={() => {
                        confirmDialog.onConfirm?.();
                        setConfirmDialog({ isOpen: false });
                    }}
                    onCancel={() => setConfirmDialog({ isOpen: false })}
                />
            </APIProvider >
        </div >
    );
};

// Helper component for Place Search
const PlaceAutocomplete = ({ onPlaceSelect }) => {
    const inputRef = useRef(null);
    const places = useMapsLibrary('places');
    const onPlaceSelectRef = useRef(onPlaceSelect);

    // Keep the ref updated with the latest callback
    useEffect(() => {
        onPlaceSelectRef.current = onPlaceSelect;
    }, [onPlaceSelect]);

    useEffect(() => {
        if (!places || !inputRef.current) return;

        const options = {
            fields: ['geometry', 'name', 'formatted_address'],
            componentRestrictions: { country: 'ae' } // Biased to UAE
        };

        const autocomplete = new places.Autocomplete(inputRef.current, options);

        const handlePlaceChanged = () => {
            const place = autocomplete.getPlace();
            if (place.geometry) {
                onPlaceSelectRef.current(place);
                // Clear the search box after selection to make it ready for next search
                if (inputRef.current) inputRef.current.value = '';
            }
        };

        const listener = autocomplete.addListener('place_changed', handlePlaceChanged);

        return () => {
            if (listener) google.maps.event.removeListener(listener);
        };
    }, [places]);

    return (
        <div className="form-group">
            <label>Search and Link Map Location</label>
            <input
                ref={inputRef}
                placeholder="Search for a building, street, or area..."
                className="setup-input"
                style={{
                    width: '100%',
                    border: '2px solid #3b82f6',
                    padding: '0.75rem',
                    borderRadius: '0.5rem'
                }}
            />
        </div>
    );
};

const GeofenceManager = ({ type, data, radius, center, onChange }) => {
    const map = useMap();
    const drawing = useMapsLibrary('drawing');
    const [manager, setManager] = useState(null);
    const overlayRef = useRef(null);

    // Initial Setup of Drawing Manager
    useEffect(() => {
        if (!map || !drawing) return;

        const dm = new drawing.DrawingManager({
            drawingControl: true,
            drawingControlOptions: {
                position: google.maps.ControlPosition.TOP_CENTER,
                drawingModes: [
                    google.maps.drawing.OverlayType.POLYGON,
                    google.maps.drawing.OverlayType.RECTANGLE
                ],
            },
            polygonOptions: {
                fillColor: '#3b82f6',
                fillOpacity: 0.2,
                strokeWeight: 2,
                strokeColor: '#2563eb',
                editable: true,
                draggable: true,
                zIndex: 1
            },
            rectangleOptions: {
                fillColor: '#3b82f6',
                fillOpacity: 0.2,
                strokeWeight: 2,
                strokeColor: '#2563eb',
                editable: false, // simpler for now
                draggable: true,
                zIndex: 1
            }
        });

        dm.setMap(map);
        setManager(dm);

        const listener = google.maps.event.addListener(dm, 'overlaycomplete', (e) => {
            // Clear previous overlay
            if (overlayRef.current) {
                overlayRef.current.setMap(null);
            }

            const newOverlay = e.overlay;
            overlayRef.current = newOverlay;

            // Switch to Polygon mode logic
            handlePolygonUpdate(newOverlay, e.type);

            // Add listeners for future edits
            if (e.type === 'polygon') {
                const path = newOverlay.getPath();
                google.maps.event.addListener(path, 'set_at', () => handlePolygonUpdate(newOverlay, 'polygon'));
                google.maps.event.addListener(path, 'insert_at', () => handlePolygonUpdate(newOverlay, 'polygon'));
            }
        });

        return () => {
            if (dm) dm.setMap(null);
            google.maps.event.removeListener(listener);
        };
    }, [map, drawing]);

    const handlePolygonUpdate = (overlay, type) => {
        let coords = [];
        if (type === 'rectangle') {
            const bounds = overlay.getBounds();
            const ne = bounds.getNorthEast();
            const sw = bounds.getSouthWest();
            coords = [
                { lat: ne.lat(), lng: sw.lng() },
                { lat: ne.lat(), lng: ne.lng() },
                { lat: sw.lat(), lng: ne.lng() },
                { lat: sw.lat(), lng: sw.lng() }
            ];
        } else {
            const path = overlay.getPath();
            path.forEach((latLng) => {
                coords.push({ lat: latLng.lat(), lng: latLng.lng() });
            });
        }

        onChange({
            geofenceType: 'POLYGON',
            geofenceData: coords
        });
    };

    // Effect to render initial/external state
    useEffect(() => {
        if (!map) return;

        // Cleanup previous
        if (overlayRef.current) {
            overlayRef.current.setMap(null);
            overlayRef.current = null;
        }

        if (type === 'CIRCLE' && center && center.lat) {
            const circle = new google.maps.Circle({
                map,
                center: center,
                radius: radius,
                fillColor: '#10b981',
                fillOpacity: 0.2,
                strokeColor: '#059669',
                strokeWeight: 2,
            });
            overlayRef.current = circle;
        } else if (type === 'POLYGON' && Array.isArray(data) && data.length > 0) {
            const polygon = new google.maps.Polygon({
                map,
                paths: data,
                fillColor: '#3b82f6',
                fillOpacity: 0.2,
                strokeColor: '#2563eb',
                strokeWeight: 2,
                editable: false,
            });
            overlayRef.current = polygon;
        }
    }, [map, type, data, radius, center]); // Re-render if external source changes

    // Update Drawing Mode based on type
    useEffect(() => {
        if (manager) {
            if (type === 'POLYGON') {
                manager.setDrawingMode(google.maps.drawing.OverlayType.POLYGON);
                manager.setOptions({ drawingControl: true });
            } else {
                manager.setDrawingMode(null); // Disable drawing
                manager.setOptions({ drawingControl: false });
            }
        }
    }, [manager, type]);

    return null;
};

// ─── Location Logs View ──────────────────────────────────────────────────────
const LocationLogsView = ({
    user, locationLogs, setLocationLogs,
    locLogSearch, setLocLogSearch,
    locLogStartDate, setLocLogStartDate,
    locLogEndDate, setLocLogEndDate,
    locLogPage, setLocLogPage,
    locLogTotal, setLocLogTotal,
    locLogTotalPages, setLocLogTotalPages,
    locLogLoading, setLocLogLoading,
    locLogSelected, setLocLogSelected,
    locLogSelectAll, setLocLogSelectAll,
    LOC_LOG_LIMIT, showToast,
    confirmDialog, setConfirmDialog
}) => {
    const [pendingSearch, setPendingSearch] = useState(locLogSearch);
    const [pendingStart, setPendingStart] = useState(locLogStartDate);
    const [pendingEnd, setPendingEnd] = useState(locLogEndDate);
    const [copied, setCopied] = useState(null);

    const fetchLogs = React.useCallback((search, start, end, page) => {
        setLocLogLoading(true);
        const params = new URLSearchParams({ page, limit: LOC_LOG_LIMIT });
        if (search) params.set('staffId', search);
        if (start) params.set('startDate', start);
        if (end) params.set('endDate', end);

        fetch(`/api/hr/location-logs?${params}`, {
            headers: { 'Authorization': `Bearer ${user.token}` }
        })
            .then(r => r.json())
            .then(data => {
                setLocationLogs(data.logs || []);
                setLocLogTotal(data.total || 0);
                setLocLogTotalPages(data.totalPages || 1);
                setLocLogSelected([]);
                setLocLogSelectAll(false);
            })
            .catch(() => showToast('Failed to load location logs', 'error'))
            .finally(() => setLocLogLoading(false));
    }, [user.token]);

    // Load on mount
    React.useEffect(() => {
        fetchLogs(locLogSearch, locLogStartDate, locLogEndDate, locLogPage);
    }, [locLogPage]);

    const handleApply = () => {
        setLocLogSearch(pendingSearch);
        setLocLogStartDate(pendingStart);
        setLocLogEndDate(pendingEnd);
        setLocLogPage(1);
        fetchLogs(pendingSearch, pendingStart, pendingEnd, 1);
    };

    const handleReset = () => {
        setPendingSearch(''); setLocLogSearch('');
        setPendingStart(''); setLocLogStartDate('');
        setPendingEnd(''); setLocLogEndDate('');
        setLocLogPage(1);
        fetchLogs('', '', '', 1);
    };

    const handleSelectAll = () => {
        if (locLogSelectAll) {
            setLocLogSelected([]);
            setLocLogSelectAll(false);
        } else {
            setLocLogSelected(locationLogs.map(l => l.id));
            setLocLogSelectAll(true);
        }
    };

    const handleSelectRow = (id) => {
        setLocLogSelected(prev =>
            prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
        );
        setLocLogSelectAll(false);
    };

    const handleDeleteSingle = (id) => {
        setConfirmDialog({
            isOpen: true,
            title: 'Delete Log Entry',
            message: 'Are you sure you want to delete this coordinate log? This cannot be undone.',
            confirmText: 'Delete',
            type: 'danger',
            onConfirm: async () => {
                try {
                    const res = await fetch(`/api/hr/location-logs/${id}`, {
                        method: 'DELETE',
                        headers: { 'Authorization': `Bearer ${user.token}` }
                    });
                    if (res.ok) {
                        showToast('Log entry deleted', 'success');
                        fetchLogs(locLogSearch, locLogStartDate, locLogEndDate, locLogPage);
                    } else {
                        showToast('Failed to delete log', 'error');
                    }
                } catch {
                    showToast('Network error', 'error');
                }
            }
        });
    };

    const handleBulkDelete = () => {
        if (locLogSelected.length === 0) { showToast('No rows selected', 'warning'); return; }
        setConfirmDialog({
            isOpen: true,
            title: `Delete ${locLogSelected.length} Log(s)`,
            message: `This will permanently delete ${locLogSelected.length} coordinate log entry(ies). Are you sure?`,
            confirmText: 'Delete All',
            type: 'danger',
            onConfirm: async () => {
                try {
                    const res = await fetch('/api/hr/location-logs', {
                        method: 'DELETE',
                        headers: {
                            'Authorization': `Bearer ${user.token}`,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ ids: locLogSelected })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        showToast(data.message, 'success');
                        fetchLogs(locLogSearch, locLogStartDate, locLogEndDate, locLogPage);
                    } else {
                        showToast(data.error || 'Failed to delete', 'error');
                    }
                } catch {
                    showToast('Network error', 'error');
                }
            }
        });
    };

    const handleCopyCoords = (lat, lng, id) => {
        navigator.clipboard.writeText(`${lat}, ${lng}`).then(() => {
            setCopied(id);
            setTimeout(() => setCopied(null), 1500);
        });
    };

    const fmt = (ts) => {
        if (!ts) return '—';
        const d = new Date(ts);
        return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
    };

    return (
        <div className="logs-container" style={{ padding: '1.5rem' }}>
            {/* ── Header ── */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div>
                    <h2 style={{ margin: 0, fontSize: '1.5rem', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        📍 Staff Coordinate Logs
                    </h2>
                    <p style={{ margin: '0.2rem 0 0', color: '#64748b', fontSize: '0.875rem' }}>
                        {locLogTotal.toLocaleString()} total pings recorded
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                    {locLogSelected.length > 0 && user.role === 'HR Admin' && (
                        <button
                            onClick={handleBulkDelete}
                            style={{
                                display: 'flex', alignItems: 'center', gap: '0.4rem',
                                padding: '0.5rem 1rem', borderRadius: '8px', border: 'none',
                                background: '#ef4444', color: '#fff', fontWeight: 600,
                                cursor: 'pointer', fontSize: '0.875rem'
                            }}
                        >
                            🗑️ Delete Selected ({locLogSelected.length})
                        </button>
                    )}
                    <button
                        onClick={() => fetchLogs(locLogSearch, locLogStartDate, locLogEndDate, locLogPage)}
                        className="btn-secondary"
                        style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}
                        disabled={locLogLoading}
                    >
                        {locLogLoading ? '⏳ Loading…' : '🔄 Refresh'}
                    </button>
                </div>
            </div>

            {/* ── Filters ── */}
            <div style={{
                background: '#f8fafc', borderRadius: '12px', border: '1px solid #e2e8f0',
                padding: '1rem 1.25rem', marginBottom: '1.25rem',
                display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end'
            }}>
                {/* Staff search */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '1 1 180px' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>Staff ID / Name</label>
                    <input
                        type="text"
                        placeholder="e.g. ST001"
                        value={pendingSearch}
                        onChange={e => setPendingSearch(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleApply()}
                        style={{
                            padding: '0.5rem 0.75rem', borderRadius: '8px',
                            border: '1px solid #cbd5e1', fontSize: '0.875rem',
                            outline: 'none', background: '#fff'
                        }}
                    />
                </div>

                {/* Start date */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '1 1 160px' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>Date From</label>
                    <input
                        type="datetime-local"
                        value={pendingStart}
                        onChange={e => setPendingStart(e.target.value)}
                        style={{
                            padding: '0.5rem 0.75rem', borderRadius: '8px',
                            border: '1px solid #cbd5e1', fontSize: '0.875rem',
                            outline: 'none', background: '#fff'
                        }}
                    />
                </div>

                {/* End date */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '1 1 160px' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>Date To</label>
                    <input
                        type="datetime-local"
                        value={pendingEnd}
                        onChange={e => setPendingEnd(e.target.value)}
                        style={{
                            padding: '0.5rem 0.75rem', borderRadius: '8px',
                            border: '1px solid #cbd5e1', fontSize: '0.875rem',
                            outline: 'none', background: '#fff'
                        }}
                    />
                </div>

                {/* Buttons */}
                <div style={{ display: 'flex', gap: '0.5rem', paddingBottom: '1px' }}>
                    <button
                        onClick={handleApply}
                        style={{
                            padding: '0.5rem 1.25rem', borderRadius: '8px', border: 'none',
                            background: '#2563eb', color: '#fff', fontWeight: 600,
                            cursor: 'pointer', fontSize: '0.875rem'
                        }}
                    >
                        Apply
                    </button>
                    <button
                        onClick={handleReset}
                        style={{
                            padding: '0.5rem 1rem', borderRadius: '8px',
                            border: '1px solid #cbd5e1', background: '#fff',
                            color: '#475569', fontWeight: 600,
                            cursor: 'pointer', fontSize: '0.875rem'
                        }}
                    >
                        Reset
                    </button>
                </div>
            </div>

            {/* ── Table ── */}
            <div style={{
                background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0',
                overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.06)'
            }}>
                {locLogLoading ? (
                    <div style={{ padding: '4rem', textAlign: 'center', color: '#94a3b8' }}>
                        <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>⏳</div>
                        Loading coordinate logs…
                    </div>
                ) : locationLogs.length === 0 ? (
                    <div style={{ padding: '4rem', textAlign: 'center', color: '#94a3b8' }}>
                        <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>📭</div>
                        <div style={{ fontWeight: 600, color: '#475569' }}>No logs found</div>
                        <div style={{ fontSize: '0.875rem', marginTop: '0.25rem' }}>Try adjusting the filters above</div>
                    </div>
                ) : (
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                            <thead>
                                <tr style={{ background: '#f1f5f9', borderBottom: '1px solid #e2e8f0' }}>
                                    {user.role === 'HR Admin' && (
                                        <th style={{ padding: '0.75rem 1rem', textAlign: 'center', width: '40px' }}>
                                            <input
                                                type="checkbox"
                                                checked={locLogSelectAll}
                                                onChange={handleSelectAll}
                                                style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                                            />
                                        </th>
                                    )}
                                    <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: '#334155' }}>#</th>
                                    <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: '#334155' }}>Staff Member</th>
                                    <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: '#334155' }}>Latitude</th>
                                    <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: '#334155' }}>Longitude</th>
                                    <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: '#334155' }}>Timestamp</th>
                                    {user.role === 'HR Admin' && (
                                        <th style={{ padding: '0.75rem 1rem', textAlign: 'center', fontWeight: 700, color: '#334155' }}>Action</th>
                                    )}
                                </tr>
                            </thead>
                            <tbody>
                                {locationLogs.map((log, idx) => {
                                    const isSelected = locLogSelected.includes(log.id);
                                    const rowNum = (locLogPage - 1) * LOC_LOG_LIMIT + idx + 1;
                                    return (
                                        <tr
                                            key={log.id}
                                            style={{
                                                borderBottom: '1px solid #f1f5f9',
                                                background: isSelected ? '#eff6ff' : (idx % 2 === 0 ? '#fff' : '#fafafa'),
                                                transition: 'background 0.15s'
                                            }}
                                        >
                                            {user.role === 'HR Admin' && (
                                                <td style={{ padding: '0.65rem 1rem', textAlign: 'center' }}>
                                                    <input
                                                        type="checkbox"
                                                        checked={isSelected}
                                                        onChange={() => handleSelectRow(log.id)}
                                                        style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                                                    />
                                                </td>
                                            )}
                                            <td style={{ padding: '0.65rem 1rem', color: '#94a3b8', fontVariantNumeric: 'tabular-nums' }}>{rowNum}</td>
                                            <td style={{ padding: '0.65rem 1rem' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                    <div style={{
                                                        width: '30px', height: '30px', borderRadius: '50%',
                                                        background: 'linear-gradient(135deg,#3b82f6,#2563eb)',
                                                        color: '#fff', display: 'flex', alignItems: 'center',
                                                        justifyContent: 'center', fontWeight: 700, fontSize: '0.75rem',
                                                        flexShrink: 0
                                                    }}>
                                                        {(log.first_name || log.staff_id || '?')[0].toUpperCase()}
                                                    </div>
                                                    <div>
                                                        <div style={{ fontWeight: 600, color: '#1e293b' }}>
                                                            {log.first_name || log.last_name
                                                                ? `${log.first_name || ''} ${log.last_name || ''}`.trim()
                                                                : 'Unnamed'}
                                                        </div>
                                                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{log.staff_id}</div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td style={{ padding: '0.65rem 1rem', fontFamily: 'monospace', color: '#0f172a' }}>
                                                {parseFloat(log.latitude).toFixed(6)}
                                            </td>
                                            <td style={{ padding: '0.65rem 1rem', fontFamily: 'monospace', color: '#0f172a' }}>
                                                {parseFloat(log.longitude).toFixed(6)}
                                            </td>
                                            <td style={{ padding: '0.65rem 1rem' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                    <button
                                                        onClick={() => handleCopyCoords(
                                                            parseFloat(log.latitude).toFixed(6),
                                                            parseFloat(log.longitude).toFixed(6),
                                                            log.id
                                                        )}
                                                        title="Copy coordinates"
                                                        style={{
                                                            background: 'none', border: 'none', cursor: 'pointer',
                                                            padding: '2px 4px', borderRadius: '4px',
                                                            color: copied === log.id ? '#10b981' : '#94a3b8',
                                                            fontSize: '0.85rem', flexShrink: 0
                                                        }}
                                                    >
                                                        {copied === log.id ? '✓' : '⎘'}
                                                    </button>
                                                    <span style={{ color: '#475569' }}>{fmt(log.timestamp)}</span>
                                                </div>
                                            </td>
                                            {user.role === 'HR Admin' && (
                                                <td style={{ padding: '0.65rem 1rem', textAlign: 'center' }}>
                                                    <button
                                                        onClick={() => handleDeleteSingle(log.id)}
                                                        title="Delete this log"
                                                        style={{
                                                            background: 'none', border: '1px solid #fca5a5',
                                                            borderRadius: '6px', padding: '4px 10px',
                                                            color: '#ef4444', cursor: 'pointer',
                                                            fontSize: '0.8rem', fontWeight: 600,
                                                            transition: 'all 0.15s'
                                                        }}
                                                        onMouseEnter={e => {
                                                            e.currentTarget.style.background = '#fef2f2';
                                                        }}
                                                        onMouseLeave={e => {
                                                            e.currentTarget.style.background = 'none';
                                                        }}
                                                    >
                                                        🗑 Delete
                                                    </button>
                                                </td>
                                            )}
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* ── Pagination ── */}
            {locLogTotalPages > 1 && (
                <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    marginTop: '1rem', flexWrap: 'wrap', gap: '0.5rem'
                }}>
                    <span style={{ fontSize: '0.875rem', color: '#64748b' }}>
                        Showing {((locLogPage - 1) * LOC_LOG_LIMIT) + 1}–{Math.min(locLogPage * LOC_LOG_LIMIT, locLogTotal)} of {locLogTotal.toLocaleString()} entries
                    </span>
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <button
                            disabled={locLogPage <= 1}
                            onClick={() => setLocLogPage(p => p - 1)}
                            style={{
                                padding: '0.4rem 0.9rem', borderRadius: '6px',
                                border: '1px solid #e2e8f0', background: locLogPage <= 1 ? '#f1f5f9' : '#fff',
                                color: locLogPage <= 1 ? '#94a3b8' : '#334155',
                                cursor: locLogPage <= 1 ? 'not-allowed' : 'pointer',
                                fontWeight: 600, fontSize: '0.875rem'
                            }}
                        >
                            ‹ Prev
                        </button>
                        {Array.from({ length: Math.min(7, locLogTotalPages) }, (_, i) => {
                            let pg;
                            if (locLogTotalPages <= 7) {
                                pg = i + 1;
                            } else if (locLogPage <= 4) {
                                pg = i + 1;
                            } else if (locLogPage >= locLogTotalPages - 3) {
                                pg = locLogTotalPages - 6 + i;
                            } else {
                                pg = locLogPage - 3 + i;
                            }
                            return (
                                <button
                                    key={pg}
                                    onClick={() => setLocLogPage(pg)}
                                    style={{
                                        padding: '0.4rem 0.75rem', borderRadius: '6px',
                                        border: `1px solid ${pg === locLogPage ? '#2563eb' : '#e2e8f0'}`,
                                        background: pg === locLogPage ? '#2563eb' : '#fff',
                                        color: pg === locLogPage ? '#fff' : '#334155',
                                        cursor: 'pointer', fontWeight: pg === locLogPage ? 700 : 500,
                                        fontSize: '0.875rem'
                                    }}
                                >
                                    {pg}
                                </button>
                            );
                        })}
                        <button
                            disabled={locLogPage >= locLogTotalPages}
                            onClick={() => setLocLogPage(p => p + 1)}
                            style={{
                                padding: '0.4rem 0.9rem', borderRadius: '6px',
                                border: '1px solid #e2e8f0', background: locLogPage >= locLogTotalPages ? '#f1f5f9' : '#fff',
                                color: locLogPage >= locLogTotalPages ? '#94a3b8' : '#334155',
                                cursor: locLogPage >= locLogTotalPages ? 'not-allowed' : 'pointer',
                                fontWeight: 600, fontSize: '0.875rem'
                            }}
                        >
                            Next ›
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

// ── Geo Fence Alerts View ──────────────────────────────────────────────────
const GeoFenceAlertsView = ({
    user, sites,
    geoFenceAlerts, setGeoFenceAlerts,
    gfPage, setGfPage,
    gfTotal, setGfTotal,
    gfTotalPages, setGfTotalPages,
    gfLoading, setGfLoading,
    gfSearch, setGfSearch,
    gfSiteFilter, setGfSiteFilter,
    gfStatusFilter, setGfStatusFilter,
    gfStartDate, setGfStartDate,
    gfEndDate, setGfEndDate,
    GF_LIMIT, showToast
}) => {
    const headers = { Authorization: `Bearer ${localStorage.getItem('hr_token')}` };

    const fetchAlerts = React.useCallback((page = 1) => {
        setGfLoading(true);
        const params = new URLSearchParams({
            page,
            limit: GF_LIMIT,
            ...(gfSearch && { staffId: gfSearch }),
            ...(gfSiteFilter && { siteId: gfSiteFilter }),
            ...(gfStatusFilter && { status: gfStatusFilter }),
            ...(gfStartDate && { startDate: gfStartDate }),
            ...(gfEndDate && { endDate: gfEndDate + 'T23:59:59' }),
        });
        fetch(`/api/hr/alerts?${params}`, { headers })
            .then(r => r.json())
            .then(data => {
                if (data?.alerts) {
                    setGeoFenceAlerts(data.alerts);
                    setGfTotal(data.total || 0);
                    setGfTotalPages(data.totalPages || 1);
                }
            })
            .catch(() => showToast('Failed to load alerts', 'error'))
            .finally(() => setGfLoading(false));
    }, [gfSearch, gfSiteFilter, gfStatusFilter, gfStartDate, gfEndDate, gfPage]);

    React.useEffect(() => {
        fetchAlerts(gfPage);
    }, [gfPage]);

    const handleSearch = () => {
        setGfPage(1);
        fetchAlerts(1);
    };

    const handleResolve = async (alertId) => {
        try {
            const res = await fetch(`/api/hr/alerts/${alertId}/resolve`, {
                method: 'PATCH',
                headers
            });
            if (!res.ok) throw new Error();
            showToast('Alert marked as resolved', 'success');
            fetchAlerts(gfPage);
        } catch {
            showToast('Failed to resolve alert', 'error');
        }
    };

    const unresolvedCount = geoFenceAlerts.filter(a => a.status === 'active').length;

    const formatDateTime = (ts) => {
        if (!ts) return '—';
        const d = new Date(ts);
        return d.toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    };

    return (
        <div className="management-view" style={{ padding: '1.5rem' }}>
            {/* Header */}
            <div style={{ marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
                    <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700, color: '#1e293b' }}>Geo Fence Alerts</h2>
                    {unresolvedCount > 0 && (
                        <span style={{
                            background: '#FF5E89', color: '#fff', borderRadius: '999px',
                            padding: '0.15rem 0.6rem', fontSize: '0.75rem', fontWeight: 700
                        }}>{unresolvedCount} active</span>
                    )}
                </div>
                <p style={{ margin: 0, color: '#64748b', fontSize: '0.875rem' }}>
                    Staff detected outside their assigned site geofence. {gfTotal > 0 ? `${gfTotal} total alerts.` : ''}
                </p>
            </div>

            {/* Filters */}
            <div style={{
                display: 'flex', flexWrap: 'wrap', gap: '0.75rem',
                background: '#fff', border: '1px solid #e2e8f0',
                borderRadius: '10px', padding: '1rem', marginBottom: '1.25rem'
            }}>
                <input
                    placeholder="Search by Staff ID…"
                    value={gfSearch}
                    onChange={e => setGfSearch(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSearch()}
                    style={{
                        flex: '1 1 160px', padding: '0.5rem 0.75rem', borderRadius: '7px',
                        border: '1px solid #e2e8f0', fontSize: '0.875rem', minWidth: '160px'
                    }}
                />
                {user.role === 'HR Admin' && (
                    <select
                        value={gfSiteFilter}
                        onChange={e => setGfSiteFilter(e.target.value)}
                        style={{
                            flex: '1 1 160px', padding: '0.5rem 0.75rem', borderRadius: '7px',
                            border: '1px solid #e2e8f0', fontSize: '0.875rem', background: '#fff'
                        }}
                    >
                        <option value="">All Sites</option>
                        {sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                )}
                <select
                    value={gfStatusFilter}
                    onChange={e => setGfStatusFilter(e.target.value)}
                    style={{
                        flex: '1 1 130px', padding: '0.5rem 0.75rem', borderRadius: '7px',
                        border: '1px solid #e2e8f0', fontSize: '0.875rem', background: '#fff'
                    }}
                >
                    <option value="">All Statuses</option>
                    <option value="active">Active</option>
                    <option value="resolved">Resolved</option>
                </select>
                <input
                    type="date"
                    value={gfStartDate}
                    onChange={e => setGfStartDate(e.target.value)}
                    style={{
                        flex: '1 1 140px', padding: '0.5rem 0.75rem', borderRadius: '7px',
                        border: '1px solid #e2e8f0', fontSize: '0.875rem'
                    }}
                />
                <input
                    type="date"
                    value={gfEndDate}
                    onChange={e => setGfEndDate(e.target.value)}
                    style={{
                        flex: '1 1 140px', padding: '0.5rem 0.75rem', borderRadius: '7px',
                        border: '1px solid #e2e8f0', fontSize: '0.875rem'
                    }}
                />
                <button
                    onClick={handleSearch}
                    style={{
                        padding: '0.5rem 1.25rem', background: '#6347FE', color: '#fff',
                        border: 'none', borderRadius: '7px', fontWeight: 600,
                        fontSize: '0.875rem', cursor: 'pointer'
                    }}
                >
                    Search
                </button>
                <button
                    onClick={() => {
                        setGfSearch(''); setGfSiteFilter(''); setGfStatusFilter('');
                        setGfStartDate(''); setGfEndDate('');
                        setTimeout(() => { setGfPage(1); fetchAlerts(1); }, 0);
                    }}
                    style={{
                        padding: '0.5rem 1rem', background: '#f1f5f9', color: '#475569',
                        border: '1px solid #e2e8f0', borderRadius: '7px', fontWeight: 600,
                        fontSize: '0.875rem', cursor: 'pointer'
                    }}
                >
                    Clear
                </button>
            </div>

            {/* Table */}
            <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                {gfLoading ? (
                    <div style={{ padding: '3rem', textAlign: 'center', color: '#94a3b8' }}>Loading alerts…</div>
                ) : geoFenceAlerts.length === 0 ? (
                    <div style={{ padding: '3rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>✅</div>
                        <div style={{ fontWeight: 600, color: '#334155' }}>No geo-fence alerts</div>
                        <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginTop: '0.25rem' }}>
                            All staff are within their assigned sites.
                        </div>
                    </div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                                {['Staff', 'Site', 'Coordinates', 'Message', 'Time', 'Status', 'Action'].map(h => (
                                    <th key={h} style={{
                                        padding: '0.75rem 1rem', textAlign: 'left',
                                        fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.06em',
                                        textTransform: 'uppercase', color: '#64748b'
                                    }}>{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {geoFenceAlerts.map((alert, idx) => (
                                <tr
                                    key={alert.id}
                                    style={{
                                        borderBottom: '1px solid #f1f5f9',
                                        background: alert.status === 'resolved' ? '#fafafa' : '#fff',
                                        transition: 'background 0.15s'
                                    }}
                                >
                                    <td style={{ padding: '0.85rem 1rem' }}>
                                        <div style={{ fontWeight: 600, color: '#1e293b', fontSize: '0.875rem' }}>
                                            {alert.staff_id}
                                        </div>
                                        {(alert.first_name || alert.last_name) && (
                                            <div style={{ color: '#64748b', fontSize: '0.78rem' }}>
                                                {[alert.first_name, alert.last_name].filter(Boolean).join(' ')}
                                            </div>
                                        )}
                                    </td>
                                    <td style={{ padding: '0.85rem 1rem', color: '#334155', fontSize: '0.875rem' }}>
                                        {alert.site_name || '—'}
                                    </td>
                                    <td style={{ padding: '0.85rem 1rem', color: '#64748b', fontSize: '0.78rem', fontFamily: 'monospace' }}>
                                        {alert.latitude && alert.longitude
                                            ? `${parseFloat(alert.latitude).toFixed(5)}, ${parseFloat(alert.longitude).toFixed(5)}`
                                            : '—'}
                                    </td>
                                    <td style={{ padding: '0.85rem 1rem', color: '#475569', fontSize: '0.82rem', maxWidth: '280px' }}>
                                        {alert.message}
                                    </td>
                                    <td style={{ padding: '0.85rem 1rem', color: '#64748b', fontSize: '0.82rem', whiteSpace: 'nowrap' }}>
                                        {formatDateTime(alert.created_at)}
                                    </td>
                                    <td style={{ padding: '0.85rem 1rem' }}>
                                        <span style={{
                                            display: 'inline-block', padding: '0.2rem 0.6rem',
                                            borderRadius: '999px', fontSize: '0.72rem', fontWeight: 700,
                                            background: alert.status === 'resolved' ? '#dcfce7' : '#fee2e2',
                                            color: alert.status === 'resolved' ? '#16a34a' : '#dc2626'
                                        }}>
                                            {alert.status === 'resolved' ? 'Resolved' : 'Active'}
                                        </span>
                                    </td>
                                    <td style={{ padding: '0.85rem 1rem' }}>
                                        {alert.status !== 'resolved' && (
                                            <button
                                                onClick={() => handleResolve(alert.id)}
                                                style={{
                                                    padding: '0.3rem 0.8rem', fontSize: '0.78rem', fontWeight: 600,
                                                    background: '#f0fdf4', color: '#16a34a',
                                                    border: '1px solid #bbf7d0', borderRadius: '6px', cursor: 'pointer'
                                                }}
                                            >
                                                Resolve
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Pagination */}
            {gfTotalPages > 1 && (
                <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    marginTop: '1rem', flexWrap: 'wrap', gap: '0.5rem'
                }}>
                    <span style={{ fontSize: '0.875rem', color: '#64748b' }}>
                        Showing {((gfPage - 1) * GF_LIMIT) + 1}–{Math.min(gfPage * GF_LIMIT, gfTotal)} of {gfTotal.toLocaleString()} alerts
                    </span>
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <button
                            disabled={gfPage <= 1}
                            onClick={() => setGfPage(p => p - 1)}
                            style={{
                                padding: '0.4rem 0.9rem', borderRadius: '6px',
                                border: '1px solid #e2e8f0',
                                background: gfPage <= 1 ? '#f1f5f9' : '#fff',
                                color: gfPage <= 1 ? '#94a3b8' : '#334155',
                                cursor: gfPage <= 1 ? 'not-allowed' : 'pointer',
                                fontWeight: 600, fontSize: '0.875rem'
                            }}
                        >‹ Prev</button>
                        <span style={{
                            padding: '0.4rem 0.75rem', borderRadius: '6px',
                            background: '#6347FE', color: '#fff', fontWeight: 700, fontSize: '0.875rem'
                        }}>
                            {gfPage} / {gfTotalPages}
                        </span>
                        <button
                            disabled={gfPage >= gfTotalPages}
                            onClick={() => setGfPage(p => p + 1)}
                            style={{
                                padding: '0.4rem 0.9rem', borderRadius: '6px',
                                border: '1px solid #e2e8f0',
                                background: gfPage >= gfTotalPages ? '#f1f5f9' : '#fff',
                                color: gfPage >= gfTotalPages ? '#94a3b8' : '#334155',
                                cursor: gfPage >= gfTotalPages ? 'not-allowed' : 'pointer',
                                fontWeight: 600, fontSize: '0.875rem'
                            }}
                        >Next ›</button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default HRDashboard;

