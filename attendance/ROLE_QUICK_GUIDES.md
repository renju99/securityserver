# Berkeley Workforce 360 - Role Quick Guides

Use this as a short training handout for daily operations.

## 1) HR Admin - Quick Guide

### Daily start (2 minutes)

1. Login to dashboard.
2. Check `Attendance`, `Geo Alerts`, and `Biometrics`.
3. Confirm no sync backlog in `Integrations`.

### Add/Update Staff

1. Open `Staff & Sites`.
2. Click add/edit user.
3. Set staff ID, role, site, shift.
4. Save and verify record in list.

### Face Enrollment

1. In `Staff & Sites`, open employee profile.
2. Start camera and capture face.
3. Confirm `face enrolled` status.

### Odoo Routing (critical)

1. Open `Integrations`.
2. Ensure active operational staff are routed to `dxb` or `auh`.
3. HR/vehicle/test records should stay excluded.

### End of day

1. Review `Reports` and exceptions.
2. Verify no unresolved attendance anomalies.

---

## 2) Site Supervisor - Quick Guide

### Daily start

1. Open `Live Map`.
2. Check `Attendance` active staff.
3. Review `Geo Alerts` and `Location Logs`.

### During shift

1. Track movement with `Route Tracking`.
2. Investigate idle flags in `Idle Reporting`.
3. Coordinate manual attendance corrections when required.

### End of shift

1. Confirm all expected staff checked out.
2. Escalate profile/role/site issues to HR Admin.

---

## 3) Employee - Quick Guide

### Login

1. Enter staff ID.
2. Use face login.
3. If needed, use PIN fallback.

### Attendance

1. Tap `Face Check-In` at shift start.
2. Tap `Face Check-Out` at shift end.
3. Keep camera clear and GPS enabled.

### If face fails

1. Improve lighting.
2. Face camera directly, blink slowly.
3. Retry, then contact HR if repeated failures.

---

## 4) Kiosk Operator / Site Kiosk - Quick Guide

### One-time setup

1. Open `/kiosk/{siteId}`.
2. Enter kiosk `deviceKey`.
3. Confirm camera is working.

### For each employee

1. Employee taps `Check-In` or `Check-Out`.
2. Kiosk scans face and identifies staff automatically.
3. Confirm success message and staff ID shown.

### If kiosk shows errors

1. Verify network.
2. Verify `deviceKey`.
3. Verify camera permissions.
4. Escalate to HR Admin for enrollment/routing issues.

---

## 5) IT/System Admin - Quick Guide

### Health checks

1. Confirm containers healthy (`api`, `web`, `db`, `redis`, listener).
2. Check `/healthz` success.
3. Confirm public URL returns `200`.

### Deployment

1. Pull latest code.
2. Run compose build/up with production env.
3. Verify smoke tests (login, attendance, kiosk, reports).

### Operations

1. Monitor logs and container health.
2. Monitor Odoo sync status.
3. Maintain secrets and backup/restore process.

---

## 6) Go-Live Daily Checklist (All Leads)

1. Public app reachable.
2. HR login works.
3. Employee face attendance works.
4. Kiosk check-in/check-out works.
5. No active sync failures.
6. Device health acceptable.
7. Alerts reviewed and acknowledged.

---

## 7) Escalation Path

- **Employee attendance issue** -> Site Supervisor -> HR Admin  
- **Face enrollment/routing issue** -> HR Admin  
- **System/network/deployment issue** -> IT Admin  
- **Odoo sync issue** -> HR Admin + IT Admin
