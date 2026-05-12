# Legacy `attendance` app vs Odoo **Berkeley Workforce**

Technical addon folder / module name remains **`attendance_core`** (for upgrades and API paths such as `/attendance_core/biometric/punch`).

| Feature area | Legacy (`/attendance`) | Odoo 18 (Berkeley Workforce `attendance_core` 18.0.3+) | Notes |
|--------------|------------------------|-------------------------------------|-------|
| Core punches | `attendance` table | `hr.attendance` + `check_work_location_id`, review fields | Native GPS/modes |
| Staff ID | `staff_id` | `hr.employee.barcode` | |
| Sites / geofence | `sites` + PostGIS | `hr.work.location` + radius + optional polygon JSON | No PostGIS; polygon in JSON |
| NFC token | site field | `attendance_nfc_payload` on work location | |
| Job codes | `job_codes` | `attendance.job.code` + `attendance_job_code_id` on `hr.attendance` | Avoids `job_id` name clashes in the web client |
| Policies | `attendance_policy_rules` | `attendance.policy.rule` | Links work location + optional `resource.calendar` |
| Pending approval | `status=pending` | `review_status` + chatter | Approve/reject wizards |
| Manual bulk checkout | API | Wizard `attendance.bulk.checkout.wizard` | |
| Biometric devices/logs | RA08 + generic API | `attendance.biometric.device/event` + JSON punch | |
| ZKTeco iClock | `/iclock/cdata` ATTLOG | Same routes under Odoo `auth=public` | Device `device_key` = terminal SN |
| Geo alerts | `geo_fence_alerts` | `attendance.geofence.alert` | |
| Location trail | `live_logs` + socket batch | `attendance.location.log` + map client action | No high-freq socket; HR can import or future API |
| Route / idle analytics | SQL endpoints | `attendance.daily.mobility` + pivot/list; cron rebuild from location logs | Idle gap configurable (`attendance_core.idle_gap_minutes`) |
| Rosters | `roster_templates` + apply | `attendance.roster.template` / `.line` / `attendance.roster.assignment` | Calendar on assignments |
| Public holidays | `public_holidays` | `attendance.public.holiday` | Optional `hr_holidays` for real leave workflows |
| Leave calendar | custom API | **Time Off** menu → Odoo `hr.leave` (requires `hr_holidays`) | Berkeley Workforce menu links to standard calendar |
| Report presets | `report_presets` | `attendance.report.preset` + “Open attendances” | Domain stored as JSON |
| Attendance reporting UI | legacy SQL | Core graph/pivot + **Berkeley Workforce** dimensions (work location, job code, break minutes); list is stock | Custom search fields omitted (Owl/search field map); use pivot rows or filters on standard fields |
| Scheduled exports | advanced scheduler + S3/email | `attendance.scheduled.export` + cron CSV email + **optional S3** (`boto3`, company keys) | Email always; S3 if configured |
| HR metrics / cleanup | admin endpoints | `attendance.metrics.snapshot` (hourly cron) + **retention cleanup** (location logs, processed biometric events, old snapshots) | Company retention days on Berkeley Workforce tab |
| Real-time HR dashboard | Socket.IO | **Odoo bus**: `simple_notification` + channel **`bw_attendance_hr_live`** + **Monitoring → Live HR attendance** | Disable with context `berkeley_workforce_disable_bus` |
| Employee PWA / offline | React + queue | **Portal** `/my/berkeley_workforce` + `localStorage` queue + sync endpoint | Lightweight; not a full installable PWA |
| Face enrollment / kiosk ML | face-api + descriptors | **face_recognition** (optional) + stored 128-d descriptor + `/attendance_core/face/enroll` & `/verify` (auth=user) | See `requirements-optional.txt` |
| Odoo sync outbox | multi-instance JSON-RPC | **Odoo → Odoo sync** menu: target instances, employee routing, **replication queue** + cron (XML-RPC `hr.attendance`) | Company flag **Replicate attendances to another Odoo** |
| Multi-org | `organizations` | `res.company` + **Settings → Berkeley Workforce** migration notes (replaces JWT org switcher) | |
| Vehicles / fleet | vehicle “users” + plate/make/model on employees | **Fleet** (`fleet.vehicle`); **People & sites → Vehicles (Fleet)**; **hr_fleet** links employees (mobility card, car stat button for fleet managers) | Users need **Fleet / User** (`fleet.fleet_group_user`) to open this menu; driver is a **partner** on the vehicle |
| Email / Twilio | custom settings | Odoo Mail + **Twilio fields** on **company → Berkeley Workforce** tab (storage only; no SMS send) | Per `res.company`; legacy `ir.config_parameter` migration on upgrade |
| Google Maps | frontend env | **Companies → Berkeley Workforce** + location log **map** client action | API key on `res.company` |
| **Menu visibility** | legacy HR app | **Berkeley Workforce** app (top-level, like **Employees**) for **HR users**, **Attendance officers**, **HR managers**, or **Settings administrators** (`base.group_system`); **Configuration** and **Bulk check-out** unchanged | Root menu no longer nested under **Human Resources** |

## Legacy HR dashboard → Berkeley Workforce app (where to click)

Open the **Berkeley Workforce** app from the Odoo home screen (top-level, next to **Employees**). Then:

| Legacy tab (`/attendance` HR UI) | Berkeley Workforce (Odoo) |
|----------------------------------|---------------------------|
| Attendance log | **Operations → Attendance log** (stock `hr.attendance`) |
| Staff & locations | **People & sites → Employees**, **Work locations** |
| Vehicles | **People & sites → Vehicles (Fleet)** (needs **Fleet / User** group) |
| Geo alerts | **Operations → Geofence alerts** |
| Reports | **Operations → Report presets** + **Attendance analysis** |
| Report schedules | **Operations → Scheduled exports** |
| Roster planning | **Operations → Roster templates** / **Roster assignments** |
| Leave calendar | **Time off** (needs **Time Off** user rights) |
| Location logs / Route / Idle / Metrics | **Operations** (logs, map) / **Monitoring** (HR metrics, Route & idle) |
| Biometrics | **Operations → Biometrics** |
| Odoo integration | **Odoo → Odoo sync** (target instance, routing, queue) + **Settings → Berkeley Workforce** (legacy JWT / org notes) |
| Email settings / Organizations | **Settings → Companies → [company] → Berkeley Workforce** tab; multi-company uses **Companies** |
| Employee PWA / kiosk | **My punch (portal)** menu + standard **Attendances** kiosk / portal templates |

## Not ported as identical legacy behaviour

- **Browser face-api bundle** in the same shape as the old React kiosk (server-side **face_recognition** / dlib path instead).
- **Socket.IO protocol** and third-party dashboards (Odoo **bus** + **Live HR attendance** client action instead).
- **Legacy JWT org-switcher API** (use **Companies** + **Users**; see **Settings → Berkeley Workforce** app block).

If you need stricter parity (e.g. custom kiosk SPA), plan it as a separate front-end project calling the JSON routes.
