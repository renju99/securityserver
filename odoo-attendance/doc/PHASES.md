# Berkeley Workforce — completed phases (summary)

Odoo addon technical name: **`attendance_core`** (Apps label: **Berkeley Workforce**).

## Phase 1 — Field inventory

See `doc/field_inventory.csv` for legacy column → Odoo mapping and whether a custom field is justified.

## Phase 2 — Configuration (standard Odoo)

Use **Working Hours** (`resource.calendar`), **Attendances** app kiosk settings, and **employee** `work_location_id` / `barcode` before enabling custom rules. This deployment adds only the `attendance_core` addon path.

## Phase 3 — Thin extensions

- `hr.attendance`: optional per-punch work location, lightweight manual review fields; biometric events reference processed rows.
- `hr.work.location`: NFC payload + simple circle geofence fields for validation/alerting.

## Phase 4 — Biometrics

- Models: `attendance.biometric.device`, `attendance.biometric.event`.
- HTTP JSON endpoint (device key auth) + cron to process pending events into `hr.attendance`.

## Phase 5 — Monitoring & reports

- `attendance.geofence.alert` created when a check-in is outside the location radius (if configured).
- Pivot/graph on `hr.attendance` inherit core views: **punch work location**, **job / activity code** (`attendance_job_code_id`), **break minutes** as rows/measures. (Search bar extensions were removed: the web client’s search parser can omit custom fields from its field map and throw “Unknown field”.)
- **Berkeley Workforce — Attendance analysis** menu action opens graph/pivot/list/form (list is stock Odoo tree; job/break stay on the attendance form to avoid `attendance_list_view` client issues).
- **Settings → Companies → [company] → Berkeley Workforce** tab: Google Maps API key + Twilio fields (per company); migrated from legacy `ir.config_parameter` on upgrade.

## Run (separate instance)

See repository `README.md` in `odoo-attendance/`.

## Verification

Module **Berkeley Workforce** (`attendance_core`) was installed successfully against a throwaway database using Docker (`docker compose up -d db` then `createdb attendance_init` and `odoo -i attendance_core --stop-after-init`).
