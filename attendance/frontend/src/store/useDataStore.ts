import { create } from 'zustand';
import {
    Employee, Site, Role, Shift, AttendanceLogEntry,
    GeoFenceAlert, BiometricDevice, BiometricLog
} from '../types';

type Setter<T> = T | ((prev: T) => T);

interface DataState {
    // Data States
    employees: Employee[];
    onlineEmployees: Record<string, any>;
    stats: { present: number; total: number };
    mgmtUsers: Employee[];
    mgmtStats: { total: number; page: number; totalPages: number };
    sites: Site[];
    roles: Role[];
    shifts: Shift[];
    attendanceLogs: AttendanceLogEntry[];
    geoFenceAlerts: GeoFenceAlert[];
    gfTotal: number;
    gfTotalPages: number;
    biometricDevices: BiometricDevice[];
    biometricLogs: BiometricLog[];
    allPermissions: { id: number; name: string; description?: string }[];

    // Location Logs State
    locationLogs: any[];
    locLogTotal: number;
    locLogTotalPages: number;
    locLogPage: number;
    locLogSearch: string;
    locLogStartDate: string;
    locLogEndDate: string;
    locLogLoading: boolean;
    locLogSelected: (number | string)[];
    locLogSelectAll: boolean;

    // Route Tracking State
    routeData: any;
    idleThreshold: number;

    // GeoFence Alerts Filter State
    gfPage: number;
    gfSearch: string;
    gfSiteFilter: string;
    gfStatusFilter: string;
    gfStartDate: string;
    gfEndDate: string;
    gfLoading: boolean;
    GF_LIMIT: number;

    // Loading States
    isMgmtLoading: boolean;
    isBiometricLoading: boolean;

    // Filter & UI States
    mgmtSubTab: 'staff' | 'sites' | 'shifts';
    mgmtPage: number;
    mgmtSearch: string;
    logSearch: string;
    selectedRoles: number[];
    selectedSites: (number | string)[];
    selectedShifts: (number | string)[];
    selectedUsers: (number | string)[];

    // Bulk Input States
    bulkShiftId: string;
    bulkSiteId: string;
    bulkDeptName: string;
    selectAll: boolean;
    showFilters: boolean;
    sortField: string;
    sortDirection: 'asc' | 'desc';

    // Actions
    fetchEmployees: (token: string) => Promise<void>;
    fetchRoles: (token: string) => Promise<void>;
    fetchSites: (token: string) => Promise<void>;
    fetchShifts: (token: string) => Promise<void>;
    fetchAlerts: (token: string, page?: number) => Promise<void>;
    fetchAttendance: (token: string) => Promise<void>;
    fetchPermissions: (token: string) => Promise<void>;
    fetchBiometricDevices: (token: string) => Promise<void>;
    fetchBiometricLogs: (token: string, staffId?: string, deviceId?: string) => Promise<void>;
    fetchManagementUsers: (token: string, page?: number, search?: string) => Promise<void>;
    fetchLocationLogs: (token: string, params: {
        page: number;
        limit: number;
        staffId?: string;
        startDate?: string;
        endDate?: string;
    }) => Promise<void>;

    // Setters
    setMgmtSubTab: (tab: 'staff' | 'sites' | 'shifts') => void;
    setMgmtPage: (page: Setter<number>) => void;
    setMgmtSearch: (search: string) => void;
    setLogSearch: (search: string) => void;
    setOnlineEmployees: (data: Setter<Record<string, any>>) => void;
    setAttendanceLogs: (data: Setter<AttendanceLogEntry[]>) => void;
    setGeoFenceAlerts: (data: Setter<GeoFenceAlert[]>) => void;
    setShifts: (data: Setter<Shift[]>) => void;
    setSelectedRoles: (roles: Setter<number[]>) => void;
    setSelectedSites: (sites: Setter<(number | string)[]>) => void;
    setSelectedShifts: (shifts: Setter<(number | string)[]>) => void;
    setSelectedUsers: (users: Setter<(number | string)[]>) => void;

    setBulkShiftId: (id: string) => void;
    setBulkSiteId: (id: string) => void;
    setBulkDeptName: (name: string) => void;
    setSelectAll: (val: Setter<boolean>) => void;
    setShowFilters: (val: boolean) => void;
    setSortField: (field: Setter<string>) => void;
    setSortDirection: (dir: Setter<'asc' | 'desc'>) => void;
    setMgmtUsers: (users: Setter<Employee[]>) => void;

    // Location Log Setters
    setLocationLogs: (logs: any[]) => void;
    setLocLogTotal: (total: number) => void;
    setLocLogTotalPages: (pages: number) => void;
    setLocLogPage: (page: Setter<number>) => void;
    setLocLogSearch: (search: string) => void;
    setLocLogStartDate: (date: string) => void;
    setLocLogEndDate: (date: string) => void;
    setLocLogLoading: (loading: boolean) => void;
    setLocLogSelected: (selected: Setter<(string | number)[]>) => void;
    setLocLogSelectAll: (val: boolean) => void;

    // Route Tracking Setters
    setRouteData: (data: any) => void;
    setIdleThreshold: (val: Setter<number>) => void;

    // GeoFence Setters
    setGfPage: (page: Setter<number>) => void;
    setGfSearch: (val: string) => void;
    setGfSiteFilter: (val: string) => void;
    setGfStatusFilter: (val: string) => void;
    setGfStartDate: (val: string) => void;
    setGfEndDate: (val: string) => void;
    setGfLoading: (val: boolean) => void;
    setGfTotal: (val: number) => void;
    setGfTotalPages: (val: number) => void;
}

export const useDataStore = create<DataState>((set, get) => ({
    // Data States
    employees: [],
    onlineEmployees: {},
    stats: { present: 0, total: 0 },
    mgmtUsers: [],
    mgmtStats: { total: 0, page: 1, totalPages: 1 },
    sites: [],
    roles: [],
    shifts: [],
    attendanceLogs: [],
    geoFenceAlerts: [],
    gfTotal: 0,
    gfTotalPages: 1,
    biometricDevices: [],
    biometricLogs: [],
    allPermissions: [],

    // Location Logs State
    locationLogs: [],
    locLogTotal: 0,
    locLogTotalPages: 1,
    locLogPage: 1,
    locLogSearch: '',
    locLogStartDate: '',
    locLogEndDate: '',
    locLogLoading: false,
    locLogSelected: [],
    locLogSelectAll: false,

    // Route Tracking State
    routeData: null,
    idleThreshold: 30,

    // GeoFence Alerts Filter State
    gfPage: 1,
    gfSearch: '',
    gfSiteFilter: '',
    gfStatusFilter: '',
    gfStartDate: '',
    gfEndDate: '',
    gfLoading: false,
    GF_LIMIT: 20,

    // Loading States
    isMgmtLoading: false,
    isBiometricLoading: false,

    // Filter & UI States
    mgmtSubTab: 'staff',
    mgmtPage: 1,
    mgmtSearch: '',
    logSearch: '',
    selectedRoles: [],
    selectedSites: [],
    selectedShifts: [],
    selectedUsers: [],

    bulkShiftId: '',
    bulkSiteId: '',
    bulkDeptName: '',
    selectAll: false,
    showFilters: false,
    sortField: 'staff_id',
    sortDirection: 'asc',

    // Fetches
    fetchEmployees: async (token) => {
        try {
            const res = await fetch('/api/hr/employees', { headers: { 'Authorization': `Bearer ${token}` } });
            if (!res.ok) return;
            const data = await res.json();
            if (Array.isArray(data)) {
                set((state) => ({ employees: data, stats: { ...state.stats, total: data.length } }));
            }
        } catch (err) {
            console.error('Error fetching employees:', err);
        }
    },

    fetchRoles: async (token) => {
        try {
            const res = await fetch('/api/hr/roles', { headers: { 'Authorization': `Bearer ${token}` } });
            if (!res.ok) return;
            const data = await res.json();
            if (Array.isArray(data)) set({ roles: data });
        } catch (err) { console.error('Error fetching roles:', err); }
    },

    fetchSites: async (token) => {
        try {
            const res = await fetch('/api/hr/sites', { headers: { 'Authorization': `Bearer ${token}` } });
            if (!res.ok) return;
            const data = await res.json();
            if (Array.isArray(data)) set({ sites: data });
        } catch (err) { console.error('Error fetching sites:', err); }
    },

    fetchShifts: async (token) => {
        try {
            const res = await fetch('/api/hr/shifts', { headers: { 'Authorization': `Bearer ${token}` } });
            if (!res.ok) return;
            const data = await res.json();
            if (Array.isArray(data)) set({ shifts: data });
        } catch (err) { console.error('Error fetching shifts:', err); }
    },

    fetchAlerts: async (token, page) => {
        const state = get();
        const currentPage = page || state.gfPage;
        set({ gfLoading: true });

        const params = new URLSearchParams({
            page: currentPage.toString(),
            limit: state.GF_LIMIT.toString(),
            ...(state.gfSearch && { staffId: state.gfSearch }),
            ...(state.gfSiteFilter && { siteId: state.gfSiteFilter }),
            ...(state.gfStatusFilter && { status: state.gfStatusFilter }),
            ...(state.gfStartDate && { startDate: state.gfStartDate }),
            ...(state.gfEndDate && { endDate: state.gfEndDate + 'T23:59:59' }),
        });

        try {
            const res = await fetch(`/api/hr/alerts?${params}`, { headers: { 'Authorization': `Bearer ${token}` } });
            const data = await res.json();
            if (Array.isArray(data)) {
                set({ geoFenceAlerts: data, gfLoading: false });
            } else if (data?.alerts) {
                set({
                    geoFenceAlerts: data.alerts,
                    gfTotal: data.total || 0,
                    gfTotalPages: data.totalPages || 1,
                    gfLoading: false
                });
            }
        } catch (err) {
            console.error('Error fetching alerts:', err);
            set({ gfLoading: false });
        }
    },

    fetchAttendance: async (token) => {
        try {
            const res = await fetch('/api/hr/attendance', { headers: { 'Authorization': `Bearer ${token}` } });
            const data = await res.json();
            if (Array.isArray(data)) set({ attendanceLogs: data });
        } catch (err) { console.error('Error fetching attendance:', err); }
    },

    fetchPermissions: async (token) => {
        try {
            const res = await fetch('/api/hr/permissions', { headers: { 'Authorization': `Bearer ${token}` } });
            if (!res.ok) return;
            const data = await res.json();
            if (Array.isArray(data)) set({ allPermissions: data });
        } catch (err) { console.error('Error fetching permissions:', err); }
    },

    fetchBiometricDevices: async (token) => {
        set({ isBiometricLoading: true });
        try {
            const res = await fetch('/api/hr/biometrics/devices', { headers: { 'Authorization': `Bearer ${token}` } });
            const data = await res.json();
            if (Array.isArray(data)) set({ biometricDevices: data });
        } catch (err) {
            console.error('Error fetching biometric devices:', err);
        } finally {
            set({ isBiometricLoading: false });
        }
    },

    fetchBiometricLogs: async (token, staffId = '', deviceId = '') => {
        set({ isBiometricLoading: true });
        const params = new URLSearchParams();
        if (staffId) params.set('staffId', staffId);
        if (deviceId) params.set('deviceId', deviceId);

        try {
            const res = await fetch(`/api/hr/biometrics/logs?${params}`, { headers: { 'Authorization': `Bearer ${token}` } });
            const data = await res.json();
            if (Array.isArray(data)) set({ biometricLogs: data });
        } catch (err) {
            console.error('Error fetching biometric logs:', err);
        } finally {
            set({ isBiometricLoading: false });
        }
    },

    fetchManagementUsers: async (token, page = 1, search = '') => {
        set({ isMgmtLoading: true });
        try {
            const res = await fetch(`/api/hr/users?page=${page}&search=${search}`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (!res.ok) return;
            const data = await res.json();
            if (data.users && Array.isArray(data.users)) {
                set({ mgmtUsers: data.users, mgmtStats: { total: data.total, page: data.page, totalPages: data.totalPages } });
            } else if (Array.isArray(data)) {
                set({ mgmtUsers: data });
            }
        } catch (err) {
            console.error('Error fetching management users:', err);
        } finally {
            set({ isMgmtLoading: false });
        }
    },

    fetchLocationLogs: async (token, params) => {
        set({ locLogLoading: true });
        const query = new URLSearchParams({
            page: params.page.toString(),
            limit: params.limit.toString()
        });
        if (params.staffId) query.set('staffId', params.staffId);
        if (params.startDate) query.set('startDate', params.startDate);
        if (params.endDate) query.set('endDate', params.endDate);

        try {
            const res = await fetch(`/api/hr/location-logs?${query}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            set({
                locationLogs: data.logs || [],
                locLogTotal: data.total || 0,
                locLogTotalPages: data.totalPages || 1,
                locLogSelected: [],
                locLogSelectAll: false
            });
        } catch (err) {
            console.error('Error fetching location logs:', err);
        } finally {
            set({ locLogLoading: false });
        }
    },

    // Setters
    setMgmtSubTab: (tab) => set({ mgmtSubTab: tab }),
    setMgmtPage: (val) => set((state) => ({ mgmtPage: typeof val === 'function' ? val(state.mgmtPage) : val })),
    setMgmtSearch: (search) => set({ mgmtSearch: search }),
    setLogSearch: (search) => set({ logSearch: search }),
    setOnlineEmployees: (val) => set((state) => ({ onlineEmployees: typeof val === 'function' ? val(state.onlineEmployees) : val })),
    setAttendanceLogs: (val) => set((state) => ({ attendanceLogs: typeof val === 'function' ? val(state.attendanceLogs) : val })),
    setGeoFenceAlerts: (val) => set((state) => ({ geoFenceAlerts: typeof val === 'function' ? val(state.geoFenceAlerts) : val })),
    setShifts: (val) => set((state) => ({ shifts: typeof val === 'function' ? val(state.shifts) : val })),
    setSelectedRoles: (val) => set((state) => ({ selectedRoles: typeof val === 'function' ? val(state.selectedRoles) : val })),
    setSelectedSites: (val) => set((state) => ({ selectedSites: typeof val === 'function' ? val(state.selectedSites) : val })),
    setSelectedShifts: (val) => set((state) => ({ selectedShifts: typeof val === 'function' ? val(state.selectedShifts) : val })),
    setSelectedUsers: (val) => set((state) => ({ selectedUsers: typeof val === 'function' ? val(state.selectedUsers) : val })),
    setBulkShiftId: (val) => set({ bulkShiftId: val }),
    setBulkSiteId: (val) => set({ bulkSiteId: val }),
    setBulkDeptName: (val) => set({ bulkDeptName: val }),
    setSelectAll: (val) => set((state) => ({ selectAll: typeof val === 'function' ? val(state.selectAll) : val })),
    setShowFilters: (showFilters) => set({ showFilters }),
    setSortField: (val) => set((state) => ({ sortField: typeof val === 'function' ? val(state.sortField) : val })),
    setSortDirection: (val) => set((state) => ({ sortDirection: typeof val === 'function' ? val(state.sortDirection) : val })),
    setMgmtUsers: (val) => set((state) => ({ mgmtUsers: typeof val === 'function' ? val(state.mgmtUsers) : val })),

    setLocationLogs: (logs) => set({ locationLogs: logs }),
    setLocLogTotal: (total) => set({ locLogTotal: total }),
    setLocLogTotalPages: (pages) => set({ locLogTotalPages: pages }),
    setLocLogPage: (val) => set((state) => ({ locLogPage: typeof val === 'function' ? val(state.locLogPage) : val })),
    setLocLogSearch: (search) => set({ locLogSearch: search }),
    setLocLogStartDate: (date) => set({ locLogStartDate: date }),
    setLocLogEndDate: (date) => set({ locLogEndDate: date }),
    setLocLogLoading: (loading) => set({ locLogLoading: loading }),
    setLocLogSelected: (val) => set((state) => ({ locLogSelected: typeof val === 'function' ? val(state.locLogSelected) : val })),
    setLocLogSelectAll: (val) => set({ locLogSelectAll: val }),

    setRouteData: (data) => set({ routeData: data }),
    setIdleThreshold: (val) => set((state) => ({ idleThreshold: typeof val === 'function' ? val(state.idleThreshold) : val })),

    setGfPage: (val) => set((state) => ({ gfPage: typeof val === 'function' ? val(state.gfPage) : val })),
    setGfSearch: (val) => set({ gfSearch: val }),
    setGfSiteFilter: (val) => set({ gfSiteFilter: val }),
    setGfStatusFilter: (val) => set({ gfStatusFilter: val }),
    setGfStartDate: (val) => set({ gfStartDate: val }),
    setGfEndDate: (val) => set({ gfEndDate: val }),
    setGfLoading: (val) => set({ gfLoading: val }),
    setGfTotal: (val) => set({ gfTotal: val }),
    setGfTotalPages: (val) => set({ gfTotalPages: val }),
}));
