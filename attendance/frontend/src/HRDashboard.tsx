import ManualAttendanceView from './components/ManualAttendanceView';
import BiometricsView from './components/BiometricsView';
import GeoFenceAlertsView from './components/GeoFenceAlertsView';
import LocationLogsView from './components/LocationLogsView';
import React, { useEffect, useState, useRef, useCallback } from 'react';
import AttendanceLog from './components/AttendanceLog';
import AnalyticsDashboard from './components/AnalyticsDashboard';
import StaffManager from './components/StaffManager';
import VehiclesManager from './components/VehiclesManager';
import MapDashboard from './components/MapDashboard';
import { useAuthStore } from './store/useAuthStore';
import { useDataStore } from './store/useDataStore';
import { useMapStore } from './store/useMapStore';
import { useUIStore } from './store/useUIStore';
import { io } from 'socket.io-client';
import { APIProvider, Map, Marker, InfoWindow, useMapsLibrary, useMap } from '@vis.gl/react-google-maps';
import Toast from './components/Toast';
import ConfirmDialog from './components/ConfirmDialog';
import { LoadingSpinner, TableSkeleton } from './components/LoadingSpinner';
import AnalyticsCard from './components/AnalyticsCard';
import FilterPanel from './components/FilterPanel';
import ReportsView from './components/ReportsView';
import ErrorBoundary from './components/ErrorBoundary';
import GeofenceManager from './components/GeofenceManager';
import RouteTrackingView, { RoutePolyline } from './components/RouteTrackingView';
import IdleReportingView from './components/IdleReportingView';
import { exportToCSV, formatDataForExport, formatSitesForExport } from './utils/exportUtils';
import { Employee, Site, Role, Shift, AttendanceLogEntry, GeoFenceAlert, BiometricDevice, BiometricLog } from './types';
import './App.css';

declare global {
    interface Window {
        google: any;
    }
}


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
    const user = useAuthStore(state => state.user);
    const login = useAuthStore(state => state.login);
    const logout = useAuthStore(state => state.logout);

    const employees = useDataStore(state => state.employees);
    const onlineEmployees = useDataStore(state => state.onlineEmployees);
    const stats = useDataStore(state => state.stats);
    const mgmtUsers = useDataStore(state => state.mgmtUsers);
    const mgmtStats = useDataStore(state => state.mgmtStats);
    const sites = useDataStore(state => state.sites);
    const roles = useDataStore(state => state.roles);
    const shifts = useDataStore(state => state.shifts);
    const attendanceLogs = useDataStore(state => state.attendanceLogs);
    const geoFenceAlerts = useDataStore(state => state.geoFenceAlerts);
    const biometricDevices = useDataStore(state => state.biometricDevices);
    const biometricLogs = useDataStore(state => state.biometricLogs);
    const allPermissions = useDataStore(state => state.allPermissions);
    const isMgmtLoading = useDataStore(state => state.isMgmtLoading);
    const isBiometricLoading = useDataStore(state => state.isBiometricLoading);
    const fetchEmployees = useDataStore(state => state.fetchEmployees);
    const fetchRoles = useDataStore(state => state.fetchRoles);
    const fetchSites = useDataStore(state => state.fetchSites);
    const fetchShifts = useDataStore(state => state.fetchShifts);
    const fetchAlerts = useDataStore(state => state.fetchAlerts);
    const fetchAttendance = useDataStore(state => state.fetchAttendance);
    const fetchPermissions = useDataStore(state => state.fetchPermissions);
    const fetchBiometricDevices = useDataStore(state => state.fetchBiometricDevices);
    const fetchBiometricLogs = useDataStore(state => state.fetchBiometricLogs);
    const fetchManagementUsers = useDataStore(state => state.fetchManagementUsers);
    const setOnlineEmployees = useDataStore(state => state.setOnlineEmployees);
    const setAttendanceLogs = useDataStore(state => state.setAttendanceLogs);
    const setGeoFenceAlerts = useDataStore(state => state.setGeoFenceAlerts);
    const setShifts = useDataStore(state => state.setShifts);
    const selectedRoles = useDataStore(state => state.selectedRoles);
    const setSelectedRoles = useDataStore(state => state.setSelectedRoles);
    const selectedSites = useDataStore(state => state.selectedSites);
    const setSelectedSites = useDataStore(state => state.setSelectedSites);
    const selectedUsers = useDataStore(state => state.selectedUsers);
    const setSelectedUsers = useDataStore(state => state.setSelectedUsers);
    const selectAll = useDataStore(state => state.selectAll);
    const setSelectAll = useDataStore(state => state.setSelectAll);
    const sortField = useDataStore(state => state.sortField);
    const setSortField = useDataStore(state => state.setSortField);
    const sortDirection = useDataStore(state => state.sortDirection);
    const setSortDirection = useDataStore(state => state.setSortDirection);
    const mgmtPage = useDataStore(state => state.mgmtPage);
    const setMgmtPage = useDataStore(state => state.setMgmtPage);
    const mgmtSearch = useDataStore(state => state.mgmtSearch);
    const setMgmtSearch = useDataStore(state => state.setMgmtSearch);
    const mgmtSubTab = useDataStore(state => state.mgmtSubTab);
    const setMgmtSubTab = useDataStore(state => state.setMgmtSubTab);
    const showFilters = useDataStore(state => state.showFilters);
    const setShowFilters = useDataStore(state => state.setShowFilters);
    const routeData = useDataStore(state => state.routeData);
    const idleThreshold = useDataStore(state => state.idleThreshold);

    const gfPage = useDataStore(state => state.gfPage);
    const setGfPage = useDataStore(state => state.setGfPage);
    const gfTotal = useDataStore(state => state.gfTotal);
    const gfTotalPages = useDataStore(state => state.gfTotalPages);
    const gfLoading = useDataStore(state => state.gfLoading);
    const gfSearch = useDataStore(state => state.gfSearch);
    const setGfSearch = useDataStore(state => state.setGfSearch);
    const gfSiteFilter = useDataStore(state => state.gfSiteFilter);
    const setGfSiteFilter = useDataStore(state => state.setGfSiteFilter);
    const gfStatusFilter = useDataStore(state => state.gfStatusFilter);
    const setGfStatusFilter = useDataStore(state => state.setGfStatusFilter);
    const gfStartDate = useDataStore(state => state.gfStartDate);
    const setGfStartDate = useDataStore(state => state.setGfStartDate);
    const gfEndDate = useDataStore(state => state.gfEndDate);
    const setGfEndDate = useDataStore(state => state.setGfEndDate);
    const GF_LIMIT = useDataStore(state => state.GF_LIMIT);

    const locationLogs = useDataStore(state => state.locationLogs);
    const locLogTotal = useDataStore(state => state.locLogTotal);
    const locLogTotalPages = useDataStore(state => state.locLogTotalPages);
    const locLogPage = useDataStore(state => state.locLogPage);
    const setLocLogPage = useDataStore(state => state.setLocLogPage);
    const locLogSearch = useDataStore(state => state.locLogSearch);
    const setLocLogSearch = useDataStore(state => state.setLocLogSearch);
    const locLogStartDate = useDataStore(state => state.locLogStartDate);
    const setLocLogStartDate = useDataStore(state => state.setLocLogStartDate);
    const locLogEndDate = useDataStore(state => state.locLogEndDate);
    const setLocLogEndDate = useDataStore(state => state.setLocLogEndDate);
    const locLogLoading = useDataStore(state => state.locLogLoading);
    const fetchLocationLogs = useDataStore(state => state.fetchLocationLogs);
    const setLocLogSelected = useDataStore(state => state.setLocLogSelected);
    const locLogSelected = useDataStore(state => state.locLogSelected);
    const locLogSelectAll = useDataStore(state => state.locLogSelectAll);
    const setLocLogSelectAll = useDataStore(state => state.setLocLogSelectAll);

    const toasts = useUIStore(state => state.toasts);
    const confirmDialog = useUIStore(state => state.confirmDialog);
    const showToast = useUIStore(state => state.showToast);
    const removeToast = useUIStore(state => state.removeToast);
    const openConfirm = useUIStore(state => state.openConfirm);
    const closeConfirm = useUIStore(state => state.closeConfirm);

    const searchQuery = useMapStore(state => state.searchQuery);
    const selectedId = useMapStore(state => state.selectedId);
    const mapCenter = useMapStore(state => state.mapCenter);
    const zoom = useMapStore(state => state.zoom);
    const setSearchQuery = useMapStore(state => state.setSearchQuery);
    const setSelectedId = useMapStore(state => state.setSelectedId);
    const setMapCenter = useMapStore(state => state.setMapCenter);
    const setZoom = useMapStore(state => state.setZoom);
    const [loginData, setLoginData] = useState<any>({ staffId: '', password: '' });
    const [error, setError] = useState('');

    const [activeTab, setActiveTab] = useState('map'); // 'map', 'staff', 'reports', etc.
    const [showUserModal, setShowUserModal] = useState(false);
    const [currentUser, setCurrentUser] = useState<any>({ staffId: '', email: '', password: '', roleId: 4, siteId: '', departmentName: '', firstName: '', lastName: '' });
    const [showSiteModal, setShowSiteModal] = useState(false);
    const [currentSite, setCurrentSite] = useState<any>({
        name: '',
        location: '',
        latitude: '',
        longitude: '',
        radiusMeters: 100,
        geofenceType: 'CIRCLE',
        geofenceData: null,
        geofenceEnabled: true
    });
    const [showShiftModal, setShowShiftModal] = useState(false);
    const [currentShift, setCurrentShift] = useState<any>({ name: '', startTime: '', endTime: '' });
    const [selectedRole, setSelectedRole] = useState<Role | null>(null);
    const [isEditingPermissions, setIsEditingPermissions] = useState(false);
    const [tempPermissions, setTempPermissions] = useState<number[]>([]);

    const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
    const [isLoading, setIsLoading] = useState(false);
    const [socketStatus, setSocketStatus] = useState('connecting');
    const [lastHeartbeat, setLastHeartbeat] = useState<string | null>(null);

    // Biometrics state
    const [showBiometricModal, setShowBiometricModal] = useState(false);
    const [currentBiometricDevice, setCurrentBiometricDevice] = useState<any>({ name: '', deviceKey: '', siteId: '', type: 'RA08', ipAddress: '', port: '' });

    const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

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
                if (selectedSites.includes(-1 as any)) {
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

        openConfirm({
            title: 'Delete Selected Staff?',
            message: `Are you sure you want to delete ${selectedUsers.length} staff member(s)? This will also remove their attendance and location records.`,
            confirmText: 'Delete All',
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
                    fetchManagementUsers(user?.token || '', mgmtPage, mgmtSearch);
                } catch (err) {
                    showToast('Failed to delete some users', 'error');
                } finally {
                    setIsLoading(false);
                }
            }
        });
    }, [selectedUsers, user, showToast, openConfirm, fetchManagementUsers, mgmtPage, mgmtSearch]);

    const handleBulkArchive = useCallback(() => {
        if (selectedUsers.length === 0) {
            showToast('No users selected', 'warning');
            return;
        }

        openConfirm({
            title: 'Archive Selected Staff?',
            message: `Are you sure you want to archive ${selectedUsers.length} staff member(s)? They will be hidden but their history will be preserved.`,
            confirmText: 'Archive All',
            cancelText: 'Cancel',
            type: 'warning',
            onConfirm: async () => {
                setIsLoading(true);
                try {
                    const res = await fetch(`/api/hr/users/bulk-update`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${user.token}` },
                        body: JSON.stringify({ userIds: selectedUsers, isActive: false })
                    });

                    if (res.ok) {
                        showToast(`Successfully archived ${selectedUsers.length} user(s)`, 'success');
                        setSelectedUsers([]);
                        setSelectAll(false);
                        fetchManagementUsers(user?.token || '', mgmtPage, mgmtSearch);
                    } else {
                        throw new Error('Failed');
                    }
                } catch (err) {
                    showToast('Failed to archive some users', 'error');
                } finally {
                    setIsLoading(false);
                }
            }
        });
    }, [selectedUsers, user, showToast, openConfirm, fetchManagementUsers, mgmtPage, mgmtSearch]);

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
    }, [showToast, setSelectedRoles, setSelectedSites]);

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
                logout();
                return false;
            }
            return true;
        };

        fetchEmployees(user.token);

        if (user.role === 'HR Admin' || user.role === 'Site Supervisor') {
            fetchRoles(user.token);
            fetchAlerts(user.token);
        }
        if (user.role === 'HR Admin') {
            fetchSites(user.token);
            fetchShifts(user.token);
        }

        fetchAttendance(user.token);

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

        socket.on('auto_checkout', (data) => {
            console.warn('[AUTO-CHECKOUT] Event received:', data);
            showToast(
                `🕐 Auto Check-Out: ${data.name || data.staffId} was automatically checked out. ${data.reason}`,
                'warning'
            );
        });

        return () => {
            socket.off('connect');
            socket.off('disconnect');
            socket.off('connect_error');
            socket.off('employee_location');
            socket.off('attendance_event');
            socket.off('geo_fence_alert');
            socket.off('auto_checkout');
        };
    }, [user?.token, user?.role, user?.siteId]); // Only re-run when user identity changes

    useEffect(() => {
        if (activeTab === 'staff' && user?.role === 'HR Admin') {
            fetchManagementUsers(user.token, mgmtPage, mgmtSearch);
        }
        if (activeTab === 'access_roles' && user?.role === 'HR Admin') {
            fetchPermissions(user.token);
        }
    }, [activeTab, mgmtPage, mgmtSearch, user, fetchManagementUsers, fetchPermissions]);

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
    }, [selectedSites, sites, activeTab, setMapCenter, setZoom]);


    const handleSaveBiometricDevice = async (e) => {
        if (e) e.preventDefault();
        const method = currentBiometricDevice.id ? 'PATCH' : 'POST';
        const url = currentBiometricDevice.id
            ? `/api/hr/biometrics/devices/${currentBiometricDevice.id}`
            : '/api/hr/biometrics/devices';

        // Prepare payload, ensuring siteId is handled correctly (null if empty)
        const payload = {
            ...currentBiometricDevice,
            siteId: currentBiometricDevice.siteId || null
        };

        try {
            const res = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${user.token}`
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                setShowBiometricModal(false);
                fetchBiometricDevices(user.token);
                showToast(currentBiometricDevice.id ? 'Device updated' : 'Device registered', 'success');
            } else {
                const error = await res.json();
                showToast(error.error || 'Failed to save device', 'error');
            }
        } catch (err) {
            showToast('Network error', 'error');
        }
    };

    const handleDeleteBiometricDevice = async (id: number) => {
        openConfirm({
            title: 'Delete Device?',
            message: 'Are you sure you want to remove this biometric terminal? This will not delete associated logs.',
            confirmText: 'Delete',
            type: 'danger',
            onConfirm: async () => {
                try {
                    const res = await fetch(`/api/hr/biometrics/devices/${id}`, {
                        method: 'DELETE',
                        headers: { 'Authorization': `Bearer ${user.token}` }
                    });
                    if (res.ok) {
                        fetchBiometricDevices(user.token);
                        showToast('Device removed', 'success');
                    } else {
                        showToast('Failed to delete device', 'error');
                    }
                } catch {
                    showToast('Network error', 'error');
                }
            }
        });
    };

    useEffect(() => {
        if (activeTab === 'biometrics' && (user?.role === 'HR Admin' || user?.role === 'Site Supervisor')) {
            fetchBiometricDevices(user.token);
            fetchBiometricLogs(user.token);
        }
    }, [activeTab, fetchBiometricDevices, fetchBiometricLogs, user]);

    // Debounced search
    useEffect(() => {
        if (activeTab !== 'staff') return;

        const debounceTimer = setTimeout(() => {
            fetchManagementUsers(user.token, mgmtPage, mgmtSearch);
        }, 300); // 300ms debounce

        return () => clearTimeout(debounceTimer);
    }, [mgmtSearch, activeTab, fetchManagementUsers, mgmtPage, user]);

    const validateUser = (user) => {
        const errors: any = {};
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
            shiftId: currentUser.shiftId !== undefined ? currentUser.shiftId : currentUser.shift_id,
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
                fetchManagementUsers(user?.token || '', mgmtPage, mgmtSearch);
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
        const errors: any = {};
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
                    .then(() => fetchSites(user.token));
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
                        fetchRoles(user.token);
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
        const matchesSite = selectedSites.length === 0 || selectedSites.includes((emp as any).site_id || (emp as any).siteId);
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
                login(userData);
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
        logout();
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
                                Staff & Sites
                            </button>
                        )}
                        {user.role === 'HR Admin' && (
                            <button className={`tab-btn ${activeTab === 'vehicles' ? 'active' : ''}`} onClick={() => setActiveTab('vehicles')}>Vehicles</button>
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
                        {(user.role === 'HR Admin' || user.role === 'Site Supervisor') && (
                            <button
                                className={`tab-btn ${activeTab === 'biometrics' ? 'active' : ''}`}
                                onClick={() => setActiveTab('biometrics')}
                            >
                                Biometrics
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
                    <ErrorBoundary label={activeTab}>
                        {activeTab === 'map' ? (
                        <MapDashboard />
                    ) : activeTab === 'staff' ? (
                        <StaffManager
                            onEditUser={(user) => {
                                setCurrentUser(user);
                                setShowUserModal(true);
                                setValidationErrors({});
                            }}
                            setCurrentUser={setCurrentUser}
                            setShowUserModal={setShowUserModal}
                            handleBulkExport={handleBulkExport}
                            handleBulkArchive={handleBulkArchive}
                            handleBulkDelete={handleBulkDelete}
                            handleFocusSite={handleFocusSite}
                            setCurrentSite={setCurrentSite}
                            setShowSiteModal={setShowSiteModal}
                            setCurrentShift={setCurrentShift}
                            setShowShiftModal={setShowShiftModal}
                            currentShift={currentShift}
                            setValidationErrors={setValidationErrors}
                            showShiftModal={showShiftModal}
                        />
                    ) : activeTab === 'vehicles' ? (
                        <VehiclesManager
                            onEditUser={(u) => {
                                setCurrentUser({
                                    id: u.id,
                                    staffId: u.staff_id,
                                    email: u.email,
                                    roleId: u.role_id,
                                    siteId: u.site_id,
                                    departmentName: u.department_name,
                                    firstName: u.first_name,
                                    lastName: u.last_name
                                });
                                setShowUserModal(true);
                            }}
                            setCurrentUser={setCurrentUser}
                            setShowUserModal={setShowUserModal}
                            handleBulkExport={handleBulkExport}
                            handleBulkArchive={handleBulkArchive}
                            handleBulkDelete={handleBulkDelete}
                            handleFocusSite={handleFocusSite}
                            setCurrentSite={setCurrentSite}
                            setShowSiteModal={setShowSiteModal}
                            setCurrentShift={setCurrentShift}
                            setShowShiftModal={setShowShiftModal}
                            currentShift={currentShift}
                            setValidationErrors={setValidationErrors}
                            showShiftModal={showShiftModal}
                        />
                    ) : activeTab === 'reports' ? (
                        <ReportsView />
                    ) : activeTab === 'attendance' ? (
                        <AttendanceLog />
                    ) : activeTab === 'geo_fence_alerts' ? (
                        <GeoFenceAlertsView />
                    ) : activeTab === 'location_logs' ? (
                        <LocationLogsView />
                    ) : activeTab === 'analytics' ? (
                        <AnalyticsDashboard />
                    ) : activeTab === 'route_tracking' ? (
                        <RouteTrackingView />
                    ) : activeTab === 'idle_reporting' ? (
                        <IdleReportingView />
                    ) : activeTab === 'biometrics' ? (
                        <BiometricsView
                            setShowModal={setShowBiometricModal}
                            setCurrentDevice={setCurrentBiometricDevice}
                            onDelete={handleDeleteBiometricDevice}
                        />
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
                    ) : activeTab === 'biometrics' ? (
                        <BiometricsView
                            setShowModal={setShowBiometricModal}
                            setCurrentDevice={setCurrentBiometricDevice}
                            onDelete={handleDeleteBiometricDevice}
                        />
                    ) : null
                        }
                    </ErrorBoundary>
                </div >

                {
                    showUserModal && (
                        <div className="modal-overlay">
                            <div className="modal-content">
                                <h3>{currentUser.id ? 'Edit' : 'Add'} {activeTab === 'vehicles' ? 'Vehicle' : 'Staff Member'}</h3>
                                <form onSubmit={handleSaveUser}>
                                    <div className="form-grid">
                                        <div className="form-group">
                                            <label>{activeTab === 'vehicles' ? 'Vehicle Make (e.g. Toyota)' : 'First Name'}</label>
                                            <input
                                                type="text"
                                                value={currentUser.firstName !== undefined ? currentUser.firstName : (currentUser.first_name || '')}
                                                onChange={(e) => setCurrentUser({ ...currentUser, firstName: e.target.value })}
                                                placeholder={activeTab === 'vehicles' ? "Make" : "e.g. John"}
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>{activeTab === 'vehicles' ? 'Vehicle Model (e.g. Hilux)' : 'Last Name'}</label>
                                            <input
                                                type="text"
                                                value={currentUser.lastName !== undefined ? currentUser.lastName : (currentUser.last_name || '')}
                                                onChange={(e) => setCurrentUser({ ...currentUser, lastName: e.target.value })}
                                                placeholder={activeTab === 'vehicles' ? "Model" : "e.g. Doe"}
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>{activeTab === 'vehicles' ? 'Plate Number (Tracking ID)' : 'Staff ID'}</label>
                                            <input
                                                type="text"
                                                value={currentUser.staff_id || currentUser.staffId}
                                                onChange={(e) => setCurrentUser({ ...currentUser, staffId: e.target.value })}
                                                required
                                                disabled={!!currentUser.id}
                                                className={(validationErrors as any).staffId ? 'input-error' : ''}
                                            />
                                            {(validationErrors as any).staffId && (
                                                <span className="error-message">{(validationErrors as any).staffId}</span>
                                            )}
                                        </div>
                                        <div className="form-group">
                                            <label>Email</label>
                                            <input
                                                type="email"
                                                value={currentUser.email}
                                                onChange={(e) => setCurrentUser({ ...currentUser, email: e.target.value })}
                                                className={(validationErrors as any).email ? 'input-error' : ''}
                                            />
                                            {(validationErrors as any).email && (
                                                <span className="error-message">{(validationErrors as any).email}</span>
                                            )}
                                        </div>
                                        <div className="form-group">
                                            <label>Password {currentUser.id && '(Leave blank to keep current)'}</label>
                                            <input
                                                type="password"
                                                value={currentUser.password}
                                                onChange={(e) => setCurrentUser({ ...currentUser, password: e.target.value })}
                                                required={!currentUser.id}
                                                className={(validationErrors as any).password ? 'input-error' : ''}
                                            />
                                            {(validationErrors as any).password && (
                                                <span className="error-message">{(validationErrors as any).password}</span>
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
                                        <div className="form-group" style={{ display: activeTab === 'vehicles' ? 'none' : 'block' }}>
                                            <label>Department</label>
                                            <input
                                                type="text"
                                                value={currentUser.department_name || currentUser.departmentName || ''}
                                                onChange={(e) => setCurrentUser({ ...currentUser, departmentName: e.target.value })}
                                            />
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
                            <div className="modal-content modal-content-lg">
                                <h3>{currentSite.id ? 'Edit' : 'Add'} Site Location</h3>
                                <form onSubmit={handleSaveSite}>
                                    <div className="geofence-form-layout">
                                        <div className="left-panel">
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
                                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
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
                                            </div>
                                            <div className="form-group" style={{ marginTop: '1rem' }}>
                                                <label>Radius (Meters)</label>
                                                <input
                                                    type="number"
                                                    value={currentSite.radiusMeters || 100}
                                                    onChange={(e) => setCurrentSite({ ...currentSite, radiusMeters: parseInt(e.target.value) })}
                                                    placeholder="100"
                                                />
                                            </div>

                                            <div style={{ padding: '1rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0', marginTop: '1.5rem' }}>
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

                                        <div className="location-picker-section">
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

                                            <div style={{ height: '400px', width: '100%', borderRadius: '8px', overflow: 'hidden', marginTop: '10px', position: 'relative' }}>
                                                <Map
                                                    style={{ width: '100%', height: '100%' }}
                                                    zoomControl={true}
                                                    mapTypeControl={false}
                                                    gestureHandling="greedy"
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
                                                    disableDefaultUI={false}
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
                                            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
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

                                    </div>
                                    <div className="modal-footer">
                                        <button type="button" className="btn-secondary" onClick={() => setShowSiteModal(false)}>Cancel</button>
                                        <button type="submit" className="btn-primary">Save Site</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    )
                }

                {
                    showBiometricModal && (
                        <div className="modal-overlay">
                            <div className="modal-content">
                                <h3>{currentBiometricDevice.id ? 'Edit' : 'Add'} Biometric Terminal</h3>
                                <form onSubmit={handleSaveBiometricDevice}>
                                    <div className="form-grid" style={{ gridTemplateColumns: '1fr' }}>
                                        <div className="form-group">
                                            <label>Device Name *</label>
                                            <input
                                                type="text"
                                                value={currentBiometricDevice.name}
                                                onChange={(e) => setCurrentBiometricDevice({ ...currentBiometricDevice, name: e.target.value })}
                                                required
                                                placeholder="e.g. Main Entrance RA08"
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>Device Key / Serial Number *</label>
                                            <input
                                                type="text"
                                                value={currentBiometricDevice.deviceKey !== undefined ? currentBiometricDevice.deviceKey : (currentBiometricDevice.device_key || '')}
                                                onChange={(e) => setCurrentBiometricDevice({ ...currentBiometricDevice, deviceKey: e.target.value })}
                                                required
                                                placeholder="e.g. RA08-01234567"
                                                disabled={!!currentBiometricDevice.id}
                                            />
                                            <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '4px' }}>
                                                Unique identifier sent by the device hardware.
                                            </p>
                                        </div>
                                        <div style={{ display: 'grid', gridTemplateColumns: '7fr 3fr', gap: '1rem' }}>
                                            <div className="form-group">
                                                <label>IP Address / Hostname</label>
                                                <input
                                                    type="text"
                                                    value={currentBiometricDevice.ipAddress !== undefined ? currentBiometricDevice.ipAddress : (currentBiometricDevice.ip_address || '')}
                                                    onChange={(e) => setCurrentBiometricDevice({ ...currentBiometricDevice, ipAddress: e.target.value })}
                                                    placeholder="e.g. head-office.dynalias.com"
                                                />
                                            </div>
                                            <div className="form-group">
                                                <label>Port</label>
                                                <input
                                                    type="number"
                                                    value={currentBiometricDevice.port !== undefined ? currentBiometricDevice.port : (currentBiometricDevice.port || '')}
                                                    onChange={(e) => setCurrentBiometricDevice({ ...currentBiometricDevice, port: parseInt(e.target.value) || '' })}
                                                    placeholder="8092"
                                                />
                                            </div>
                                        </div>
                                        <div className="form-group">
                                            <label>Assigned Site</label>
                                            <select
                                                value={currentBiometricDevice.siteId !== undefined ? currentBiometricDevice.siteId : (currentBiometricDevice.site_id || '')}
                                                onChange={(e) => setCurrentBiometricDevice({ ...currentBiometricDevice, siteId: e.target.value })}
                                            >
                                                <option value="">Global / Unassigned</option>
                                                {sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                                            </select>
                                        </div>
                                        <div className="form-group">
                                            <label>Terminal Type</label>
                                            <select
                                                value={currentBiometricDevice.type || 'RA08'}
                                                onChange={(e) => setCurrentBiometricDevice({ ...currentBiometricDevice, type: e.target.value })}
                                            >
                                                <option value="RA08">RA08 (AIBOX)</option>
                                                <option value="Generic">Generic Biometric</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div className="modal-footer">
                                        <button type="button" className="btn-secondary" onClick={() => setShowBiometricModal(false)}>Cancel</button>
                                        <button type="submit" className="btn-primary" disabled={isBiometricLoading}>
                                            {isBiometricLoading ? 'Saving...' : 'Save Device'}
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
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
                        closeConfirm();
                    }}
                    onCancel={closeConfirm}
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
            if (listener) window.google.maps.event.removeListener(listener);
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

export default HRDashboard;
