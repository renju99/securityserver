# Berkeley Workforce 360 - End User Operations Guide

This guide explains how each user role operates the system and how administrators configure it.

## 1. User Roles and Access

- **HR Admin**
  - Full access to staff, vehicles, attendance, reports, rosters, biometrics, integrations, metrics, and access roles.
- **Site Supervisor**
  - Operational access to map, attendance, leave calendar, rosters, reports, route tracking, location logs, geo alerts, and biometrics.
- **Employee**
  - Uses face/PIN login and attendance actions.
- **Kiosk Operator**
  - Uses kiosk screen for face-based check-in/check-out (1:N).
- **System/IT Admin**
  - Handles deployment, environment variables, backups, and monitoring.

## 2. Menu Order (Dashboard)

Menus are now arranged in operational sequence:

1. `Live Map`
2. `Attendance`
3. `Rosters`
4. `Leave Calendar`
5. `Staff & Sites` (HR Admin only)
6. `Vehicles` (HR Admin only)
7. `Reports`
8. `Analytics` (HR Admin only)
9. `Route Tracking`
10. `Idle Reporting`
11. `Location Logs`
12. `Geo Alerts`
13. `Biometrics`
14. `Integrations` (HR Admin only)
15. `Access Roles` (HR Admin only)
16. `Metrics` (HR Admin only)

## 3. HR Admin - Daily Operations

### 3.1 Staff and Site Setup

1. Open `Staff & Sites`.
2. Create/update employee profile:
   - first/last name
   - staff ID
   - role
   - site
   - shift
3. Save changes.

### 3.2 Face Enrollment (Employee)

1. Open `Staff & Sites`.
2. Edit employee and open face enrollment section.
3. Start camera, ensure good lighting.
4. Capture and save enrollment.
5. Confirm status shows `face enrolled`.

### 3.3 Mobile HR Enrollment

1. Open `/hr/enrollment` on HR mobile device.
2. Login with HR Admin credentials.
3. Search employee and select profile.
4. Capture face and save.

### 3.4 Attendance Review and Corrections

1. Open `Attendance`.
2. Review check-ins/check-outs.
3. Use manual check-in/check-out when needed.
4. Use bulk checkout for unresolved open sessions (if policy allows).

### 3.5 Reports and Exports

1. Open `Reports`.
2. Choose report type and date range.
3. Export CSV/PDF as needed.

### 3.6 Biometrics and Device Status

1. Open `Biometrics`.
2. Verify device heartbeat and health.
3. Investigate offline/stale devices.

### 3.7 Odoo Integrations

1. Open `Integrations`.
2. Configure Odoo instances (`dxb`, `auh`) and credentials.
3. Maintain `staff -> instance` routing.
4. Monitor sync status and retries.

## 4. Site Supervisor - Daily Operations

1. Open `Live Map` to track active employees.
2. Use `Attendance` for same-day operations.
3. Manage `Rosters` for shift assignment.
4. Monitor `Geo Alerts`, `Location Logs`, and `Route Tracking`.
5. Escalate employee master-data changes to HR Admin.

## 5. Employee - Login and Attendance

### 5.1 Face Login

1. Open employee login screen.
2. Enter staff ID and scan face.
3. If face fails, use PIN fallback (if enabled by HR).

### 5.2 Face Attendance (1:1)

1. Choose `Face Check-In` or `Face Check-Out`.
2. Ensure camera and GPS are enabled.
3. Complete scan and verify success message.

## 6. Kiosk Operator - Site Kiosk (1:N)

1. Open kiosk URL: `/kiosk/{siteId}`.
2. Enter kiosk `deviceKey` once (stored locally).
3. Employee taps `Check-In` or `Check-Out`.
4. Camera scans face and system identifies staff automatically.
5. Confirm success message with identified staff ID/name.

## 7. Odoo Routing Policy (Important)

- Operational employees must have an **active** route in `staff_odoo_routing`.
- HR Admin, vehicle profiles, and test/invalid profiles should be marked as **excluded** (`is_active=false`) with notes.
- System now skips Odoo queueing for staff without active route to avoid dead-letter noise.

## 8. System Configuration (IT Admin)

### 8.1 Required Environment Variables

- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET`
- `JWT_REFRESH_SECRET`
- `CORS_ORIGINS`
- `JWT_REFRESH_COOKIE_SECURE=true` (production)

### 8.2 Deploy/Update

1. Update code and env.
2. Rebuild and start:
   - `docker-compose --env-file .env.prod -f docker-compose.prod.yml up -d --build`
3. Verify:
   - containers healthy
   - `https://attendance.berkeleyuae.com` returns `200`
   - `/healthz` returns `{"ok":true}`

## 9. Go-Live Checklist

1. All containers healthy (`api`, `web`, `db`, `redis`, RA08 listener).
2. Public domain and TLS working.
3. HR can enroll employee faces.
4. Employee 1:1 attendance works.
5. Kiosk 1:N attendance works.
6. Odoo routing complete for operational staff.
7. Odoo outbox has no active failed backlog.
8. Backups and restore drill completed.
9. Monitoring and alerting enabled.

## 10. Troubleshooting

- **Face scan fails**
  - Improve lighting and face framing, clean camera lens, retry.
- **GPS/location error on attendance**
  - Enable location permissions and retry.
- **Kiosk unknown device**
  - Verify `deviceKey` and kiosk-device assignment in Integrations.
- **Odoo sync not happening**
  - Check active route, instance status, and outbox status.
- **502 from public domain**
  - Check reverse proxy upstream and container health.
