import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import AttendanceLog from './components/AttendanceLog';
import StaffManager from './components/StaffManager';
import GeoFenceAlertsView from './components/GeoFenceAlertsView';
import ReportsView from './components/ReportsView';
import ScheduledReportsConfigView from './components/ScheduledReportsConfigView';
import OdooIntegrationView from './components/OdooIntegrationView';
import LeaveCalendarView from './components/LeaveCalendarView';
import MetricsDashboardView from './components/MetricsDashboardView';
import RouteTrackingView from './components/RouteTrackingView';
import IdleReportingView from './components/IdleReportingView';
import RosterPlanningView from './components/RosterPlanningView';
import LocationLogsView from './components/LocationLogsView';
import OrganizationsSettingsView from './components/OrganizationsSettingsView';
import EmailMessagingSettingsView from './components/EmailMessagingSettingsView';
import { useAuthStore } from './store/useAuthStore';
import { useDataStore } from './store/useDataStore';
import { useUIStore } from './store/useUIStore';
import { io } from 'socket.io-client';
import Toast from './components/Toast';
import ConfirmDialog from './components/ConfirmDialog';
import ErrorBoundary from './components/ErrorBoundary';
import { Employee, Site, Role } from './types';
import { exportToCSV, formatDataForExport } from './utils/exportUtils';
import './App.css';

const resolveSocketBaseUrl = (): string => {
    const fromEnv = import.meta.env.VITE_SOCKET_BASE_URL?.trim();
    if (fromEnv) return fromEnv.replace(/\/$/, '');
    if (typeof window !== 'undefined' && window.location?.origin) {
        return window.location.origin;
    }
    return '/';
};

const socket = io(resolveSocketBaseUrl(), {
    path: '/socket.io/',
    autoConnect: false,
    transports: ['polling', 'websocket'],
});

const BRANDING = {
    appTitle: 'Workforce Attendance',
    portalTitle: 'Attendance',
    portalSubtitle: 'HR',
};

const WEB_APP_VERSION = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : 'dev';

type AccessibleOrg = { id: number; slug: string; name: string };

function buildNavTabs(role: string | undefined) {
    const tabs: { key: string; label: string; group: string }[] = [
        { key: 'attendance', label: 'Attendance log', group: 'Main' },
    ];
    if (role === 'HR Admin') {
        tabs.push({ key: 'staff', label: 'Staff & locations', group: 'Main' });
        tabs.push({ key: 'alerts', label: 'Geo alerts', group: 'Operations' });
        tabs.push({ key: 'reports', label: 'Reports', group: 'Operations' });
        tabs.push({ key: 'schedules', label: 'Report schedules', group: 'Operations' });
        tabs.push({ key: 'rosters', label: 'Roster planning', group: 'Operations' });
        tabs.push({ key: 'calendar', label: 'Leave calendar', group: 'Operations' });
        tabs.push({ key: 'locationLogs', label: 'Location logs', group: 'Monitoring' });
        tabs.push({ key: 'routeTracking', label: 'Route tracking', group: 'Monitoring' });
        tabs.push({ key: 'idle', label: 'Idle reporting', group: 'Monitoring' });
        tabs.push({ key: 'metrics', label: 'Metrics', group: 'Monitoring' });
        tabs.push({ key: 'odoo', label: 'Odoo integration', group: 'Integrations' });
        tabs.push({ key: 'emailSettings', label: 'Email settings', group: 'Settings' });
        tabs.push({ key: 'organizations', label: 'Organizations', group: 'Settings' });
    } else if (role === 'Site Supervisor') {
        tabs.push({ key: 'alerts', label: 'Geo alerts', group: 'Operations' });
        tabs.push({ key: 'reports', label: 'Reports', group: 'Operations' });
        tabs.push({ key: 'rosters', label: 'Roster planning', group: 'Operations' });
        tabs.push({ key: 'calendar', label: 'Leave calendar', group: 'Operations' });
        tabs.push({ key: 'locationLogs', label: 'Location logs', group: 'Monitoring' });
        tabs.push({ key: 'routeTracking', label: 'Route tracking', group: 'Monitoring' });
        tabs.push({ key: 'idle', label: 'Idle reporting', group: 'Monitoring' });
    } else if (role === 'Payroll' || role === 'Finance') {
        tabs.push({ key: 'reports', label: 'Reports', group: 'Main' });
        tabs.push({ key: 'schedules', label: 'Report schedules', group: 'Main' });
        tabs.push({ key: 'calendar', label: 'Leave calendar', group: 'Main' });
    }
    return tabs;
}

const defaultDashboardTab = () => 'attendance';

const HRDashboard = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const environmentLabel = import.meta.env.PROD ? 'Production' : 'Staging';
    const tabInitRef = useRef(false);
    const user = useAuthStore((state) => state.user);
    const [accessibleOrgs, setAccessibleOrgs] = useState<AccessibleOrg[]>([]);
    const [orgSwitchLoading, setOrgSwitchLoading] = useState(false);

    const login = useAuthStore((state) => state.login);
    const logout = useAuthStore((state) => state.logout);
    const refreshAccessToken = useAuthStore((state) => state.refreshAccessToken);

    const employees = useDataStore((state) => state.employees);
    const stats = useDataStore((state) => state.stats);
    const mgmtUsers = useDataStore((state) => state.mgmtUsers);
    const sites = useDataStore((state) => state.sites);
    const roles = useDataStore((state) => state.roles);
    const shifts = useDataStore((state) => state.shifts);
    const fetchEmployees = useDataStore((state) => state.fetchEmployees);
    const fetchRoles = useDataStore((state) => state.fetchRoles);
    const fetchSites = useDataStore((state) => state.fetchSites);
    const fetchShifts = useDataStore((state) => state.fetchShifts);
    const fetchAttendance = useDataStore((state) => state.fetchAttendance);
    const fetchManagementUsers = useDataStore((state) => state.fetchManagementUsers);
    const setOnlineEmployees = useDataStore((state) => state.setOnlineEmployees);
    const setAttendanceLogs = useDataStore((state) => state.setAttendanceLogs);
    const setShifts = useDataStore((state) => state.setShifts);

    const mgmtPage = useDataStore((state) => state.mgmtPage);
    const mgmtSearch = useDataStore((state) => state.mgmtSearch);

    const toasts = useUIStore((state) => state.toasts);
    const confirmDialog = useUIStore((state) => state.confirmDialog);
    const showToast = useUIStore((state) => state.showToast);
    const removeToast = useUIStore((state) => state.removeToast);
    const openConfirm = useUIStore((state) => state.openConfirm);
    const closeConfirm = useUIStore((state) => state.closeConfirm);

    const [loginData, setLoginData] = useState(() => ({
        staffId: '',
        password: '',
        organizationSlug: (typeof localStorage !== 'undefined' && localStorage.getItem('hrOrganizationSlug')) || 'default',
    }));
    const [error, setError] = useState('');

    const [activeTab, setActiveTab] = useState('attendance');
    const [showUserModal, setShowUserModal] = useState(false);
    const [currentUser, setCurrentUser] = useState<any>({
        staffId: '',
        email: '',
        password: '',
        roleId: 4,
        siteId: '',
        departmentName: '',
        firstName: '',
        lastName: '',
    });
    const [showSiteModal, setShowSiteModal] = useState(false);
    const [currentSite, setCurrentSite] = useState<any>({
        name: '',
        location: '',
        latitude: '',
        longitude: '',
        radiusMeters: 100,
        geofenceType: 'CIRCLE',
        geofenceData: null,
        geofenceEnabled: true,
    });
    const [showShiftModal, setShowShiftModal] = useState(false);
    const [currentShift, setCurrentShift] = useState<any>({ name: '', startTime: '', endTime: '' });

    const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
    const [isLoading, setIsLoading] = useState(false);
    const [socketStatus, setSocketStatus] = useState('connecting');
    const [socketErrorDetail, setSocketErrorDetail] = useState<string | null>(null);
    const [checkedInSummary, setCheckedInSummary] = useState<any>({ totalCheckedIn: 0, lateCount: 0, perSiteCounts: {}, records: [] });

    const selectedUsers = useDataStore((state) => state.selectedUsers);
    const setSelectedUsers = useDataStore((state) => state.setSelectedUsers);
    const selectAll = useDataStore((state) => state.selectAll);
    const setSelectAll = useDataStore((state) => state.setSelectAll);

    useEffect(() => {
        if (!user?.token) {
            setAccessibleOrgs([]);
            return;
        }
        let cancelled = false;
        void fetch('/auth/accessible-organizations', {
            headers: { Authorization: `Bearer ${user.token}` },
            credentials: 'same-origin',
        })
            .then((r) => r.json())
            .then((d: { organizations?: AccessibleOrg[] }) => {
                if (!cancelled) setAccessibleOrgs(Array.isArray(d.organizations) ? d.organizations : []);
            })
            .catch(() => {
                if (!cancelled) setAccessibleOrgs([]);
            });
        return () => {
            cancelled = true;
        };
    }, [user?.token, user?.organizationId]);

    const handleOrganizationSwitch = async (nextOrgId: number) => {
        const curId = Number((user as { organizationId?: number })?.organizationId);
        if (!user?.token || !Number.isFinite(nextOrgId) || nextOrgId === curId) return;
        setOrgSwitchLoading(true);
        try {
            const res = await fetch('/auth/switch-organization', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { Authorization: `Bearer ${user.token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ organizationId: nextOrgId }),
            });
            const data = (await res.json()) as { error?: string; user?: Record<string, unknown>; token?: string };
            if (!res.ok) throw new Error(data.error || 'Could not switch organization');
            const u = data.user || {};
            const slug = String(u.organizationSlug || 'default').trim().toLowerCase() || 'default';
            try {
                localStorage.setItem('hrOrganizationSlug', slug);
            } catch {
                /* ignore */
            }
            setOnlineEmployees({});
            setAttendanceLogs([]);
            setShifts([]);
            tabInitRef.current = false;
            login({ ...u, token: data.token } as Parameters<typeof login>[0]);
            showToast(`Organization: ${String(u.organizationName || slug)}`, 'success');
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Switch failed', 'error');
        } finally {
            setOrgSwitchLoading(false);
        }
    };

    const handleBulkDelete = useCallback(() => {
        if (selectedUsers.length === 0) {
            showToast('No users selected', 'warning');
            return;
        }
        openConfirm({
            title: 'Delete Selected Staff?',
            message: `Delete ${selectedUsers.length} staff member(s)? This removes their attendance records.`,
            confirmText: 'Delete All',
            cancelText: 'Cancel',
            type: 'danger',
            onConfirm: async () => {
                setIsLoading(true);
                try {
                    await Promise.all(
                        selectedUsers.map((userId) =>
                            fetch(`/hr/users/${userId}`, {
                                method: 'DELETE',
                                headers: { Authorization: `Bearer ${user.token}` },
                            })
                        )
                    );
                    showToast(`Deleted ${selectedUsers.length} user(s)`, 'success');
                    setSelectedUsers([]);
                    setSelectAll(false);
                    fetchManagementUsers(user?.token || '', mgmtPage, mgmtSearch);
                } catch {
                    showToast('Failed to delete some users', 'error');
                } finally {
                    setIsLoading(false);
                }
            },
        });
    }, [selectedUsers, user, showToast, openConfirm, fetchManagementUsers, mgmtPage, mgmtSearch, setSelectedUsers, setSelectAll]);

    const handleBulkArchive = useCallback(() => {
        if (selectedUsers.length === 0) {
            showToast('No users selected', 'warning');
            return;
        }
        openConfirm({
            title: 'Archive Selected Staff?',
            message: `Archive ${selectedUsers.length} staff member(s)?`,
            confirmText: 'Archive All',
            cancelText: 'Cancel',
            type: 'warning',
            onConfirm: async () => {
                setIsLoading(true);
                try {
                    const res = await fetch(`/hr/users/bulk-update`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${user.token}` },
                        body: JSON.stringify({ userIds: selectedUsers, isActive: false }),
                    });
                    if (res.ok) {
                        showToast(`Archived ${selectedUsers.length} user(s)`, 'success');
                        setSelectedUsers([]);
                        setSelectAll(false);
                        fetchManagementUsers(user?.token || '', mgmtPage, mgmtSearch);
                    } else throw new Error('Failed');
                } catch {
                    showToast('Failed to archive', 'error');
                } finally {
                    setIsLoading(false);
                }
            },
        });
    }, [selectedUsers, user, showToast, openConfirm, fetchManagementUsers, mgmtPage, mgmtSearch, setSelectedUsers, setSelectAll]);

    const handleBulkExport = useCallback(() => {
        if (selectedUsers.length === 0) {
            showToast('No users selected', 'warning');
            return;
        }
        const selectedData = mgmtUsers.filter((u) => selectedUsers.includes(u.id));
        exportToCSV(formatDataForExport(selectedData), `staff_${new Date().toISOString().split('T')[0]}.csv`);
        showToast(`Exported ${selectedUsers.length} user(s)`, 'success');
    }, [selectedUsers, mgmtUsers, showToast]);

    useEffect(() => {
        if (!user) return;
        let cancelled = false;

        const applySocketAuth = (token: string) => {
            socket.auth = { token };
            setSocketStatus('connecting');
            if (socket.connected) socket.disconnect();
            socket.connect();
        };

        const attachSocketHandlers = () => {
            socket.off('connect');
            socket.off('disconnect');
            socket.off('connect_error');
            socket.off('attendance_event');

            socket.on('connect', () => {
                setSocketStatus('connected');
                setSocketErrorDetail(null);
                const sessionUser = useAuthStore.getState().user;
                if (sessionUser?.role === 'HR Admin') {
                    socket.emit('join_hr');
                } else if (sessionUser?.role === 'Site Supervisor' && sessionUser.siteId) {
                    socket.emit('join_site', sessionUser.siteId);
                }
            });

            socket.on('disconnect', (reason: string) => {
                setSocketStatus('disconnected');
                console.log('Socket disconnected:', reason);
            });

            socket.on('connect_error', (err: Error & { data?: unknown }) => {
                setSocketStatus('error');
                const msg = err?.message || String(err);
                setSocketErrorDetail(msg);
            });

            socket.on('attendance_event', (data: any) => {
                setAttendanceLogs((prev) => {
                    const logs = [...prev];
                    if (data.type === 'check_in') {
                        logs.unshift({
                            id: 'live-' + Date.now(),
                            staff_id: data.employeeId,
                            first_name: data.firstName,
                            last_name: data.lastName,
                            check_in_time: data.timestamp,
                            check_out_time: null,
                            site_name: data.siteName,
                            site_id: data.siteId,
                            is_live: true,
                        });
                    } else if (data.type === 'check_out') {
                        const idx = logs.findIndex((l) => l.staff_id === data.employeeId && !l.check_out_time);
                        if (idx >= 0) {
                            logs[idx] = { ...logs[idx], check_out_time: data.timestamp };
                        }
                    }
                    return logs.slice(0, 100);
                });
            });
        };

        const loadDashboardData = async () => {
            const refreshed = await refreshAccessToken();
            if (cancelled) return;

            let sessionUser = useAuthStore.getState().user;
            if (!sessionUser?.token) {
                logout();
                return;
            }

            if (!refreshed) {
                try {
                    const probe = await fetch('/hr/employees', {
                        headers: { Authorization: `Bearer ${sessionUser.token}` },
                        credentials: 'same-origin',
                    });
                    if (cancelled) return;
                    if (probe.status === 401 || probe.status === 403) {
                        logout();
                        return;
                    }
                } catch {
                    if (cancelled) return;
                }
            }

            sessionUser = useAuthStore.getState().user;
            if (cancelled || !sessionUser?.token) return;

            attachSocketHandlers();
            if (sessionUser.token) {
                socket.auth = { token: sessionUser.token };
                setSocketStatus(socket.connected ? 'connected' : 'connecting');
                if (!socket.connected) socket.connect();
            }

            fetchEmployees(sessionUser.token);
            fetchAttendance(sessionUser.token);

            if (sessionUser.role === 'HR Admin') {
                fetchRoles(sessionUser.token);
                fetchSites(sessionUser.token);
                fetchShifts(sessionUser.token);
            } else if (sessionUser.role === 'Site Supervisor') {
                fetchSites(sessionUser.token);
            } else if (sessionUser.role === 'Payroll' || sessionUser.role === 'Finance') {
                fetchSites(sessionUser.token);
                fetchShifts(sessionUser.token);
            }
        };

        void loadDashboardData();

        const ACCESS_REFRESH_MS = 8 * 60 * 1000;
        const refreshInterval = setInterval(async () => {
            const ok = await refreshAccessToken();
            if (cancelled || !ok) return;
            const t = useAuthStore.getState().user?.token;
            if (t) applySocketAuth(t);
        }, ACCESS_REFRESH_MS);

        return () => {
            cancelled = true;
            clearInterval(refreshInterval);
            socket.off('connect');
            socket.off('disconnect');
            socket.off('connect_error');
            socket.off('attendance_event');
        };
    }, [
        user?.token,
        user?.role,
        user?.siteId,
        user?.organizationId,
        refreshAccessToken,
        logout,
        fetchEmployees,
        fetchRoles,
        fetchSites,
        fetchShifts,
        fetchAttendance,
        setAttendanceLogs,
        setOnlineEmployees,
        setShifts,
    ]);

    useEffect(() => {
        if (!user?.token || !(user.role === 'HR Admin' || user.role === 'Site Supervisor')) return;
        let mounted = true;
        let timer: ReturnType<typeof setInterval> | null = null;
        const fetchSummary = async () => {
            try {
                const res = await fetch('/hr/attendance/current-summary', {
                    headers: { Authorization: `Bearer ${user.token}` },
                });
                const data = await res.json();
                if (res.ok && mounted) setCheckedInSummary(data);
            } catch (err) {
                console.error('current-summary:', err);
            }
        };
        void fetchSummary();
        timer = setInterval(fetchSummary, 30000);
        return () => {
            mounted = false;
            if (timer) clearInterval(timer);
        };
    }, [user?.token, user?.role]);

    useEffect(() => {
        if (activeTab === 'staff' && user?.role === 'HR Admin') {
            fetchManagementUsers(user.token, mgmtPage, mgmtSearch);
        }
    }, [activeTab, mgmtPage, mgmtSearch, user, fetchManagementUsers]);

    useEffect(() => {
        if (activeTab !== 'staff') return;
        const debounceTimer = setTimeout(() => {
            if (user?.token) fetchManagementUsers(user.token, mgmtPage, mgmtSearch);
        }, 300);
        return () => clearTimeout(debounceTimer);
    }, [mgmtSearch, activeTab, fetchManagementUsers, mgmtPage, user]);

    const navTabs = useMemo(() => buildNavTabs(user?.role), [user?.role]);
    const navTabGroups = useMemo(() => {
        return navTabs.reduce<Record<string, { key: string; label: string; group: string }[]>>((acc, tab) => {
            if (!acc[tab.group]) acc[tab.group] = [];
            acc[tab.group].push(tab);
            return acc;
        }, {});
    }, [navTabs]);

    useEffect(() => {
        if (!user?.staffId || !user?.token || !user?.role) return;
        if (tabInitRef.current) return;
        tabInitRef.current = true;
        const allowed = new Set(navTabs.map((t) => t.key));
        const fromUrl = searchParams.get('tab');
        const orgSlug = String((user as { organizationSlug?: string }).organizationSlug || 'default');
        const storageKey = `hrDashboardLastTab:${orgSlug}:${user.staffId}`;
        const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(storageKey) : null;
        if (fromUrl && allowed.has(fromUrl)) setActiveTab(fromUrl);
        else if (saved && allowed.has(saved)) setActiveTab(saved);
        else setActiveTab(defaultDashboardTab());
    }, [user?.staffId, user?.role, user?.token, navTabs, searchParams, (user as { organizationSlug?: string })?.organizationSlug]);

    useEffect(() => {
        if (!user?.staffId || !user?.token || !user?.role) return;
        if (!tabInitRef.current) return;
        const allowed = new Set(navTabs.map((t) => t.key));
        const fromUrl = searchParams.get('tab');
        if (!fromUrl || !allowed.has(fromUrl)) return;
        setActiveTab(fromUrl);
    }, [searchParams, navTabs, user?.staffId, user?.token, user?.role]);

    useEffect(() => {
        if (!user?.staffId || !user?.role) return;
        const allowed = new Set(navTabs.map((t) => t.key));
        if (!allowed.has(activeTab)) return;
        setSearchParams(
            (prev) => {
                if (prev.get('tab') === activeTab) return prev;
                const next = new URLSearchParams(prev);
                next.set('tab', activeTab);
                return next;
            },
            { replace: true }
        );
    }, [activeTab, user?.staffId, user?.role, navTabs, setSearchParams]);

    useEffect(() => {
        if (!user?.token) tabInitRef.current = false;
    }, [user?.token]);

    useEffect(() => {
        if (!user?.staffId || !user?.role) return;
        const orgSlug = String((user as { organizationSlug?: string }).organizationSlug || 'default');
        const storageKey = `hrDashboardLastTab:${orgSlug}:${user.staffId}`;
        if (typeof localStorage !== 'undefined') localStorage.setItem(storageKey, activeTab);
    }, [activeTab, user?.staffId, user?.role, (user as { organizationSlug?: string })?.organizationSlug]);

    useEffect(() => {
        if (!navTabs.some((tab) => tab.key === activeTab)) {
            setActiveTab(defaultDashboardTab());
        }
    }, [activeTab, navTabs]);

    const handleFocusSite = (site: Site) => {
        if (site.latitude && site.longitude) {
            showToast(`${site.name}: ${site.latitude}, ${site.longitude}`, 'info');
        } else {
            showToast('No coordinates set for this site', 'warning');
        }
    };

    const validateUser = (u: any) => {
        const errors: Record<string, string> = {};
        if (!u.staffId && !u.staff_id) errors.staffId = 'Staff ID is required';
        if (u.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(u.email)) {
            errors.email = 'Invalid email format';
        }
        if (!u.id && !u.password) errors.password = 'Password is required for new users';
        if (u.password && u.password.length < 6) errors.password = 'Password must be at least 6 characters';
        return errors;
    };

    const handleSaveUser = async (e: React.FormEvent) => {
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
        };
        setIsLoading(true);
        try {
            const res = await fetch('/hr/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${user.token}` },
                body: JSON.stringify(payload),
            });
            if (res.ok) {
                setShowUserModal(false);
                fetchManagementUsers(user?.token || '', mgmtPage, mgmtSearch);
                setCurrentUser({
                    staffId: '',
                    email: '',
                    password: '',
                    roleId: 4,
                    siteId: '',
                    departmentName: '',
                    firstName: '',
                    lastName: '',
                });
                showToast('Staff saved', 'success');
            } else {
                const errBody = await res.json();
                showToast(errBody.error || 'Failed to save user', 'error');
            }
        } catch {
            showToast('Network error', 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const validateSite = (site: any) => {
        const errors: Record<string, string> = {};
        if (!site.name || site.name.trim().length === 0) errors.name = 'Site name is required';
        if (site.name && site.name.length < 3) errors.name = 'Site name must be at least 3 characters';
        return errors;
    };

    const handleSaveSite = async (e: React.FormEvent) => {
        e.preventDefault();
        setValidationErrors({});
        const errors = validateSite(currentSite);
        if (Object.keys(errors).length > 0) {
            setValidationErrors(errors);
            showToast('Please fix validation errors', 'error');
            return;
        }
        const method = currentSite.id ? 'PATCH' : 'POST';
        const url = currentSite.id ? `/hr/sites/${currentSite.id}` : '/hr/sites';
        setIsLoading(true);
        try {
            const res = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${user.token}` },
                body: JSON.stringify(currentSite),
            });
            if (res.ok) {
                setShowSiteModal(false);
                fetch('/hr/sites', { headers: { Authorization: `Bearer ${user.token}` } })
                    .then((r) => r.json())
                    .then(() => fetchSites(user.token));
                setCurrentSite({
                    name: '',
                    location: '',
                    latitude: '',
                    longitude: '',
                    radiusMeters: 100,
                    geofenceType: 'CIRCLE',
                    geofenceData: null,
                    geofenceEnabled: true,
                });
                showToast(currentSite.id ? 'Site updated' : 'Site created', 'success');
            } else {
                const errBody = await res.json();
                showToast(errBody.error || 'Failed to save site', 'error');
            }
        } catch {
            showToast('Network error', 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);
        try {
            const organizationSlug = String(loginData.organizationSlug || 'default').trim().toLowerCase() || 'default';
            const res = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    staffId: loginData.staffId.trim(),
                    password: loginData.password,
                    organizationSlug,
                }),
            });
            const data = await res.json();
            if (res.ok) {
                const slug = organizationSlug;
                try {
                    localStorage.setItem('hrOrganizationSlug', slug);
                } catch {
                    /* ignore */
                }
                login({ ...data.user, token: data.token } as Parameters<typeof login>[0]);
                showToast(`Welcome back, ${String(data.user?.role || 'user')}!`, 'success');
            } else {
                setError(data.error || 'Login failed');
                showToast(data.error || 'Invalid credentials', 'error');
            }
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Request failed';
            setError('Connection error');
            showToast(`Unable to reach the server (${msg}).`, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const handleLogout = () => {
        logout();
    };

    if (!user) {
        return (
            <div className="setup-screen hr-login">
                <div className="setup-card">
                    <div className="berkeley-logo-small" style={{ marginBottom: '1rem' }}>
                        <img src="/berkeley-logo.png" alt="" style={{ height: '30px', width: 'auto', objectFit: 'contain' }} />
                    </div>
                    <h2>HR dashboard</h2>
                    <p className="field-hint" style={{ marginTop: 0, color: 'var(--gray-600)' }}>
                        Sign in with your staff account. Use the same organization code your team uses for the mobile app (often <strong>default</strong>).
                    </p>
                    <form onSubmit={handleLogin} noValidate>
                        {error && (
                            <div className="error-banner" role="alert" style={{ marginBottom: '1rem' }}>
                                {error}
                            </div>
                        )}
                        <div className="form-group">
                            <label htmlFor="hr-staff-id" className="field-label">Staff ID</label>
                            <input
                                id="hr-staff-id"
                                type="text"
                                placeholder="Your staff ID"
                                value={loginData.staffId}
                                onChange={(e) => setLoginData({ ...loginData, staffId: e.target.value })}
                                required
                                className="setup-input"
                                autoComplete="username"
                                disabled={isLoading}
                            />
                        </div>
                        <div className="form-group">
                            <label htmlFor="hr-org-slug" className="field-label">Organization</label>
                            <p className="field-hint" style={{ marginTop: 0 }}>Short code for your company (e.g. <code style={{ fontSize: '0.85em' }}>default</code>).</p>
                            <input
                                id="hr-org-slug"
                                type="text"
                                placeholder="default"
                                value={loginData.organizationSlug}
                                onChange={(e) =>
                                    setLoginData({
                                        ...loginData,
                                        organizationSlug: (e.target.value || 'default').trim().toLowerCase(),
                                    })
                                }
                                className="setup-input"
                                autoComplete="organization"
                                disabled={isLoading}
                            />
                        </div>
                        <div className="form-group">
                            <label htmlFor="hr-password" className="field-label">Password</label>
                            <input
                                id="hr-password"
                                type="password"
                                placeholder="Password"
                                value={loginData.password}
                                onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                                required
                                className="setup-input"
                                autoComplete="current-password"
                                disabled={isLoading}
                            />
                        </div>
                        <button type="submit" className="btn-primary" disabled={isLoading} aria-busy={isLoading}>
                            {isLoading ? 'Signing in…' : 'Sign in'}
                        </button>
                    </form>
                </div>
            </div>
        );
    }

    return (
        <div className="hr-dashboard">
            <header className="dashboard-topbar">
                <div className="topbar-left">
                    <div className="topbar-title-row">
                        <img src="/berkeley-logo.png" alt="Berkeley" className="topbar-logo" />
                        <div className="topbar-title">{BRANDING.appTitle}</div>
                    </div>
                    <div className="topbar-subtitle">
                        {user.role}
                        {user.siteName ? ` · ${user.siteName}` : user.siteId ? ` · Site #${user.siteId}` : ''}
                    </div>
                </div>
                <div className="topbar-right">
                    {accessibleOrgs.length > 1 ? (
                        <label className="env-pill" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', margin: 0 }}>
                            <span style={{ whiteSpace: 'nowrap' }}>Organization</span>
                            <select
                                className="control-input"
                                style={{ minWidth: '10rem', maxWidth: '14rem', padding: '0.2rem 0.35rem', fontSize: '0.8rem' }}
                                value={Number((user as { organizationId?: number }).organizationId) || ''}
                                disabled={orgSwitchLoading}
                                onChange={(e) => {
                                    const v = Number(e.target.value);
                                    if (Number.isFinite(v)) void handleOrganizationSwitch(v);
                                }}
                            >
                                {accessibleOrgs.map((o) => (
                                    <option key={o.id} value={o.id}>
                                        {o.name || o.slug}
                                    </option>
                                ))}
                            </select>
                        </label>
                    ) : (
                        <span className="env-pill">Org: {user.organizationSlug || 'default'}</span>
                    )}
                    <span className="env-pill">v{WEB_APP_VERSION}</span>
                    <span className="env-pill">{environmentLabel}</span>
                    <span
                        className={`live-pill ${socketStatus === 'connected' ? 'online' : socketStatus === 'connecting' ? 'connecting' : 'offline'}`}
                        title={socketErrorDetail || (socketStatus === 'connected' ? 'Live updates for new check-ins' : undefined)}
                    >
                        {socketStatus === 'connected' ? 'Live' : socketStatus === 'connecting' ? 'Connecting' : 'Offline'}
                    </span>
                    <button type="button" onClick={handleLogout} className="btn-logout">
                        Logout
                    </button>
                </div>
            </header>

            <div className="dashboard-shell">
                <aside className="dashboard-nav">
                    <div className="dashboard-nav-brand">
                        <img src="/berkeley-logo.png" alt="" className="dashboard-nav-logo-image" />
                        <div>
                            <div className="dashboard-nav-logo-title">{BRANDING.portalTitle}</div>
                            <div className="dashboard-nav-logo-sub">{BRANDING.portalSubtitle}</div>
                        </div>
                    </div>
                    {Object.entries(navTabGroups).map(([groupName, tabs]) => (
                        <div className="dashboard-nav-group" key={groupName}>
                            <div className="dashboard-nav-header">{groupName}</div>
                            <div className="dashboard-nav-list">
                                {tabs.map((tab) => (
                                    <button
                                        key={tab.key}
                                        type="button"
                                        className={`dashboard-nav-item ${activeTab === tab.key ? 'active' : ''}`}
                                        onClick={() => setActiveTab(tab.key)}
                                        aria-current={activeTab === tab.key ? 'page' : undefined}
                                    >
                                        <span>{tab.label}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    ))}
                </aside>

                <main className="dashboard-main">
                    {(user.role === 'Payroll' || user.role === 'Finance') && (
                        <div
                            className="employee-alert employee-alert--info"
                            style={{ margin: '0 0 1rem', fontSize: '0.875rem' }}
                            role="status"
                        >
                            You are in a <strong>read-focused</strong> role: view attendance and export as needed. To change records, ask an HR Admin or site supervisor.
                        </div>
                    )}
                    <div className="kpi-strip">
                        <div className="kpi-strip-card blue" title="People in the directory for this organization">
                            <div className="kpi-strip-value">{stats.total || employees.length}</div>
                            <div className="kpi-strip-label">Employees</div>
                        </div>
                        <div className="kpi-strip-card green" title="Currently checked in (open attendance)">
                            <div className="kpi-strip-value">{checkedInSummary.totalCheckedIn || 0}</div>
                            <div className="kpi-strip-label">Checked in</div>
                        </div>
                        <div className="kpi-strip-card amber" title="Checked in at or before shift threshold">
                            <div className="kpi-strip-value">
                                {Math.max((checkedInSummary.totalCheckedIn || 0) - (checkedInSummary.lateCount || 0), 0)}
                            </div>
                            <div className="kpi-strip-label">On time</div>
                        </div>
                        <div className="kpi-strip-card red" title="Checked in after late threshold">
                            <div className="kpi-strip-value">{checkedInSummary.lateCount || 0}</div>
                            <div className="kpi-strip-label">Late</div>
                        </div>
                    </div>

                    <div className="dashboard-layout">
                        <ErrorBoundary label={activeTab}>
                            {activeTab === 'staff' ? (
                                <StaffManager
                                    onEditUser={(u: Employee) => {
                                        setCurrentUser(u);
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
                            ) : activeTab === 'alerts' ? (
                                <GeoFenceAlertsView />
                            ) : activeTab === 'reports' ? (
                                <ReportsView onOpenReportSchedules={() => setActiveTab('schedules')} />
                            ) : activeTab === 'schedules' ? (
                                <ScheduledReportsConfigView />
                            ) : activeTab === 'odoo' ? (
                                <OdooIntegrationView />
                            ) : activeTab === 'calendar' ? (
                                <LeaveCalendarView />
                            ) : activeTab === 'metrics' ? (
                                <MetricsDashboardView />
                            ) : activeTab === 'routeTracking' ? (
                                <RouteTrackingView />
                            ) : activeTab === 'idle' ? (
                                <IdleReportingView />
                            ) : activeTab === 'rosters' ? (
                                <RosterPlanningView />
                            ) : activeTab === 'locationLogs' ? (
                                <LocationLogsView />
                            ) : activeTab === 'organizations' ? (
                                <OrganizationsSettingsView />
                            ) : activeTab === 'emailSettings' ? (
                                <EmailMessagingSettingsView />
                            ) : (
                                <AttendanceLog />
                            )}
                        </ErrorBoundary>
                    </div>
                </main>
            </div>

            {showUserModal && (
                <div className="modal-overlay" role="presentation">
                    <div
                        className="modal-content"
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="hr-staff-modal-title"
                    >
                        <h3 id="hr-staff-modal-title">{currentUser.id ? 'Edit team member' : 'Add team member'}</h3>
                        <form onSubmit={handleSaveUser}>
                            <div className="form-grid">
                                <div className="form-group">
                                    <label>First Name</label>
                                    <input
                                        type="text"
                                        value={currentUser.firstName !== undefined ? currentUser.firstName : currentUser.first_name || ''}
                                        onChange={(e) => setCurrentUser({ ...currentUser, firstName: e.target.value })}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Last Name</label>
                                    <input
                                        type="text"
                                        value={currentUser.lastName !== undefined ? currentUser.lastName : currentUser.last_name || ''}
                                        onChange={(e) => setCurrentUser({ ...currentUser, lastName: e.target.value })}
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
                                    {validationErrors.staffId && <span className="error-message">{validationErrors.staffId}</span>}
                                </div>
                                <div className="form-group">
                                    <label>Email</label>
                                    <input
                                        type="email"
                                        value={currentUser.email || ''}
                                        onChange={(e) => setCurrentUser({ ...currentUser, email: e.target.value })}
                                        className={validationErrors.email ? 'input-error' : ''}
                                    />
                                    {validationErrors.email && <span className="error-message">{validationErrors.email}</span>}
                                </div>
                                <div className="form-group">
                                    <label>Password {currentUser.id && '(blank = unchanged)'}</label>
                                    <input
                                        type="password"
                                        value={currentUser.password || ''}
                                        onChange={(e) => setCurrentUser({ ...currentUser, password: e.target.value })}
                                        required={!currentUser.id}
                                        className={validationErrors.password ? 'input-error' : ''}
                                    />
                                    {validationErrors.password && <span className="error-message">{validationErrors.password}</span>}
                                </div>
                                <div className="form-group">
                                    <label htmlFor="hr-modal-role">Role</label>
                                    <select
                                        id="hr-modal-role"
                                        value={String(currentUser.role_id ?? currentUser.roleId ?? '')}
                                        onChange={(e) => setCurrentUser({ ...currentUser, roleId: e.target.value })}
                                    >
                                        {roles.map((r: Role) => (
                                            <option key={r.id} value={r.id}>
                                                {r.name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>Department</label>
                                    <input
                                        type="text"
                                        value={currentUser.department_name || currentUser.departmentName || ''}
                                        onChange={(e) => setCurrentUser({ ...currentUser, departmentName: e.target.value })}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Site</label>
                                    <select
                                        value={currentUser.site_id || currentUser.siteId || ''}
                                        onChange={(e) => setCurrentUser({ ...currentUser, siteId: e.target.value })}
                                    >
                                        <option value="">All sites</option>
                                        {sites.map((s: Site) => (
                                            <option key={s.id} value={s.id}>
                                                {s.name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>Shift</label>
                                    <select
                                        value={currentUser.shift_id || currentUser.shiftId || ''}
                                        onChange={(e) => setCurrentUser({ ...currentUser, shiftId: e.target.value })}
                                    >
                                        <option value="">None</option>
                                        {shifts.map((s) => (
                                            <option key={s.id} value={s.id}>
                                                {s.name} ({s.start_time} - {s.end_time})
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                            <div className="modal-footer">
                                <button type="button" className="btn-secondary" onClick={() => setShowUserModal(false)}>
                                    Cancel
                                </button>
                                <button type="submit" className="btn-primary" disabled={isLoading}>
                                    {isLoading ? 'Saving…' : 'Save'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {showSiteModal && (
                <div className="modal-overlay" role="presentation">
                    <div
                        className="modal-content modal-content-lg"
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="hr-site-modal-title"
                    >
                        <h3 id="hr-site-modal-title">{currentSite.id ? 'Edit work site' : 'Add work site'}</h3>
                        <p style={{ margin: '0 0 1rem', fontSize: '0.85rem', color: 'var(--gray-600)' }}>
                            Sites are used for assignments and location rules. Coordinates and radius support map and geofence checks where enabled.
                        </p>
                        <form onSubmit={handleSaveSite}>
                            <div className="form-group">
                                <label htmlFor="hr-site-name">Site name</label>
                                <input
                                    id="hr-site-name"
                                    type="text"
                                    value={currentSite.name}
                                    onChange={(e) => setCurrentSite({ ...currentSite, name: e.target.value })}
                                    required
                                />
                                {validationErrors.name && <span className="error-message">{validationErrors.name}</span>}
                            </div>
                            <div className="form-group">
                                <label htmlFor="hr-site-desc">Description or address</label>
                                <input
                                    id="hr-site-desc"
                                    type="text"
                                    value={currentSite.location}
                                    onChange={(e) => setCurrentSite({ ...currentSite, location: e.target.value })}
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
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Longitude</label>
                                    <input
                                        type="number"
                                        step="any"
                                        value={currentSite.longitude}
                                        onChange={(e) => setCurrentSite({ ...currentSite, longitude: e.target.value })}
                                    />
                                </div>
                            </div>
                            <div className="form-group">
                                <label htmlFor="hr-site-radius">Radius (meters)</label>
                                <p className="field-hint" style={{ marginTop: 0 }}>Distance from the center point used when geofencing is on.</p>
                                <input
                                    id="hr-site-radius"
                                    type="number"
                                    min={1}
                                    value={currentSite.radiusMeters || 100}
                                    onChange={(e) => setCurrentSite({ ...currentSite, radiusMeters: parseInt(e.target.value, 10) })}
                                />
                            </div>
                            <div className="form-group">
                                <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <input
                                        type="checkbox"
                                        checked={currentSite.geofenceEnabled !== false}
                                        onChange={(e) => setCurrentSite({ ...currentSite, geofenceEnabled: e.target.checked })}
                                    />
                                    Enforce geofence for this site
                                </label>
                                <p className="field-hint" style={{ marginBottom: 0 }}>When off, location rules may not apply for this site.</p>
                            </div>
                            <div className="modal-footer">
                                <button type="button" className="btn-secondary" onClick={() => setShowSiteModal(false)}>
                                    Cancel
                                </button>
                                <button type="submit" className="btn-primary">
                                    Save
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            <div className="toast-container">
                {toasts.map((toast) => (
                    <Toast key={toast.id} message={toast.message} type={toast.type} onClose={() => removeToast(toast.id)} />
                ))}
            </div>

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
        </div>
    );
};

export default HRDashboard;
