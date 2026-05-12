# Odoo 18 — Berkeley Workforce (dedicated instance)

Isolated stack: own database (name must match `db_filter` in `config/odoo.conf`, e.g. `attendance` or `attendance_init`), own port (**8070** on host → 8069 in container), only addons in `./addons`.

## Start

```bash
cd /home/azureuser/odoo-attendance
docker compose up -d
```

Open `http://localhost:8070`, create a database whose name **starts with** `attendance` (see `db_filter` in `config/odoo.conf`), then install **Berkeley Workforce** (technical module name: `attendance_core`).

**Where to find it:** open the **Berkeley Workforce** app from the main Odoo apps menu (same level as **Employees** / **Attendances**). It is visible to **HR users**, **Attendance officers**, **HR managers**, and **Settings administrators** (`base.group_system`). Under that root, menus mirror the legacy HR app: **People & sites** (employees, work locations, **Vehicles (Fleet)** — requires **Fleet / User**), **Operations** (attendance log, biometrics, rosters, exports, geofence, location map, analysis), **Monitoring** (metrics, route & idle), **Time off**, **My punch (portal)**, and **Configuration** (job codes, policies, holidays). **Companies → Berkeley Workforce** holds Maps/Twilio-style company fields.

## Configuration

1. Set a strong `admin_passwd` in `config/odoo.conf`.
2. **Settings → Companies → [your company] → tab “Berkeley Workforce”:** paste the **Google Maps API key** (browser key; restrict by HTTP referrer to your Odoo URL). Twilio fields are stored there as well (SMS is not sent by this module).
3. Employees: set **Badge ID** (`barcode`) to the legacy `staff_id`.
4. **Work location**: open HR configuration work locations; set geofence fields (radius and/or polygon JSON) if you use geofence alerts.
5. Register **Berkeley Workforce → Configuration → Biometric devices** with a device key; devices call the HTTP API with header `X-Device-Key`, or ZKTeco terminals use `SN` as the same key for `/iclock/cdata`.

## ZKTeco iClock (push)

Devices call the same host paths as the legacy app (plain `OK` responses):

- `GET/POST /iclock/cdata` — ATTLOG body (tab-separated). Query `SN` must match **Biometric device → Device key**.
- Optional system parameter `attendance_core.zk_staff_prefix` — prefix for user id before matching `hr.employee.barcode`.

Other `/iclock/*` probe endpoints return `OK` (see legacy `zktecoIclock.js`).

## Biometric HTTP API

`POST /attendance_core/biometric/punch`

Headers: `X-Device-Key: <device device_key>`

JSON body example:

```json
{
  "staff_id": "EMP001",
  "direction": "in",
  "event_time": "2026-05-11T08:00:00"
}
```

`direction` is `in` or `out`. `event_time` is optional (defaults to now, UTC server time).

## Troubleshooting

### `RPC_ERROR` / **404** on `/mail/data` (Discuss / messaging init)

Odoo’s mail app calls `/mail/data` with `init_messaging`. For the **public** user, stock Odoo returns **404** if there is no Discuss guest cookie (`dgid`). That often happens when the **session** is missing or stale (tab left open, cleared cookies, or `web.base.url` not matching how you open the site, e.g. `http://127.0.0.1` vs `http://localhost`).

**Berkeley Workforce** includes a small patch that **skips** that messaging bootstrap instead of returning 404, so the web client can load; you should still **log in again** if you were meant to be an internal user. Set **Settings → Technical → Parameters → System Parameters**: `web.base.url` to the exact URL you use (including port, e.g. `http://localhost:8070`).

### **Vehicles (Fleet)** menu is missing

The entry **Berkeley Workforce → People & sites → Vehicles (Fleet)** is shown only to users in **Fleet / User** (`fleet.fleet_group_user`). Add that access right on the user (or a role group you use for HR) under **Settings → Users & Companies → Users**.

### Optional server packages (face match, S3)

Face descriptors and S3 uploads use **optional** Python libraries. See `addons/attendance_core/requirements-optional.txt` (`face_recognition`, `numpy`, `boto3`). Install in the same environment as Odoo (or the Docker image) only if you need those paths.

### Upgrade: “Field … does not exist in model `hr.work.location`” (or similar)

That means the server loaded **views** that reference Berkeley Workforce fields, but the **Python model extension** in `addons/attendance_core/models/` (especially `hr_work_location.py`) was not deployed or Odoo was not restarted before upgrading.

1. Copy the **entire** `attendance_core` addon directory onto the server (including all files under `models/`).
2. **Restart** the Odoo process (or `docker compose restart odoo`) so workers reload Python.
3. Run **Apps → Upgrade** on Berkeley Workforce again (or `odoo -u attendance_core --stop-after-init`).

## Documentation

- `doc/COMPARISON.md` — legacy Node `/attendance` app vs Berkeley Workforce: what is ported, what differs, and what is **out of scope** (face ML, Socket.IO dashboards, Odoo sync outbox, S3 exports, etc.).
- `doc/field_inventory.csv` — Phase 1 legacy → Odoo field mapping.
- `doc/PHASES.md` — phase completion notes.
