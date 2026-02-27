export interface Employee {
    id: number;
    staff_id: string;
    first_name: string;
    last_name: string;
    department_name: string;
    role_name: string;
    role_id: number;
    site_id?: number | null;
    site_name?: string;
    shift_id?: number | null;
    shift_name?: string;
    isTrackingEnabled?: boolean;
    photo_url?: string;
    isGuest?: boolean;
    email?: string;
}

export interface Site {
    id: number;
    name: string;
    latitude: string;
    longitude: string;
    radius?: number;
    location?: string;
}

export interface Role {
    id: number;
    name: string;
    permissions?: { id: number; name: string; description?: string }[];
}

export interface Shift {
    id: number;
    name: string;
    start_time: string;
    end_time: string;
}

export interface AttendanceLogEntry {
    id: number | string;
    staff_id: string;
    first_name: string;
    last_name: string;
    check_in_time: string;
    check_out_time?: string;
    site_name?: string;
    site_id?: number | string;
    is_live?: boolean;
    notes?: string;
    auto_closed?: boolean;
}

export interface EmployeeLocation {
    employeeId: string;
    latitude: number;
    longitude: number;
    lastSeen: string;
    siteId?: number;
    departmentName?: string;
    department_name?: string;
    photoUrl?: string;
    photo_url?: string;
}

export interface GeoFenceAlert {
    id: number;
    staff_id: string;
    first_name: string;
    last_name?: string;
    site_name?: string;
    latitude?: string;
    longitude?: string;
    message: string;
    created_at: string;
    status: 'active' | 'resolved';
}

export interface BiometricDevice {
    id: number;
    name: string;
    device_key: string;
    ip_address?: string;
    port?: string;
    site_id?: number;
    site_name?: string;
    last_seen?: string;
    is_active: boolean;
    type: string;
}

export interface BiometricLog {
    id: number;
    staff_id: string;
    first_name: string;
    last_name: string;
    device_name: string;
    timestamp: string;
    photo_url?: string;
}
