-- Indexes for 10k-employee operational load.
-- Keep these aligned with backend/init.sql for fresh databases.

CREATE INDEX IF NOT EXISTS idx_employees_role_site_active
    ON employees (role_id, site_id, is_active);

CREATE INDEX IF NOT EXISTS idx_employees_site_active_staff
    ON employees (site_id, is_active, staff_id);

CREATE INDEX IF NOT EXISTS idx_attendance_employee_checkin_desc
    ON attendance (employee_id, check_in_time DESC);

CREATE INDEX IF NOT EXISTS idx_attendance_site_checkin_desc
    ON attendance (site_id, check_in_time DESC);

CREATE INDEX IF NOT EXISTS idx_attendance_open_employee
    ON attendance (employee_id, check_in_time DESC)
    WHERE check_out_time IS NULL;

CREATE INDEX IF NOT EXISTS idx_attendance_open_site
    ON attendance (site_id, check_in_time DESC)
    WHERE check_out_time IS NULL;

CREATE INDEX IF NOT EXISTS idx_attendance_status_checkin
    ON attendance (status, check_in_time DESC);

CREATE INDEX IF NOT EXISTS idx_live_logs_employee_time
    ON live_logs (employee_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_live_logs_time
    ON live_logs (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_geo_fence_alerts_employee_created
    ON geo_fence_alerts (employee_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_geo_fence_alerts_site_status_created
    ON geo_fence_alerts (site_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_biometric_devices_site_active
    ON biometric_devices (site_id, is_active);

CREATE INDEX IF NOT EXISTS idx_biometric_logs_device_timestamp
    ON biometric_logs (device_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_biometric_logs_staff_timestamp
    ON biometric_logs (staff_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_attendance_sync_outbox_status_retry
    ON attendance_sync_outbox (status, next_retry_at, id);

CREATE INDEX IF NOT EXISTS idx_attendance_sync_outbox_attendance
    ON attendance_sync_outbox (attendance_id, event_type);
