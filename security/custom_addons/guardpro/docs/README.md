# Sentry — Security operations on Odoo 18

Sentry brings guard scheduling, patrol proof, incidents, visitors, and client reporting into **Odoo 18 Community**. Supervisors, control room staff, and guards share one system; clients can use the portal where you enable it.

**Version:** 18.0.1.1.17 · See also [Documentation index](INDEX.md) and [Get started](GETTING_STARTED.md).

---

## What you get

### Field and mobile

- Responsive **mobile web** for guards (bookmark or add to home screen; flows are Odoo-native routes).  
- GPS-related features where enabled: location history, geofence alerts, checkpoint scans (QR/NFC/manual, per configuration).  
- Patrol **tours**, **checkpoints**, route helpers, and **tour logs** for audit evidence.  

### Control room

- **Shifts**, templates, swaps, and attendance aligned with your setup.  
- **Incidents** with investigation, escalation, and SLA links where configured.  
- **Visitors**, packages, keys, lost-and-found, and related workflows.  
- **Emergency broadcast** and internal messaging features where installed and permitted.  
- **Dashboards and reports** (PDF/Excel depending on configuration).  

### Compliance

- Audits, **daily activity reports**, SLA definitions and performance tracking.  
- Knowledge / SOP content and eLearning when **website_slides** and your data packs are present.  

### Automation and integration

- Scheduled actions for reminders, DAR, SLAs, credentials, and more.  
- APIs and webhooks for integrations (see `docs/api/`).  

---

## Product scope notes

This README describes the **current** product, not every line of experimental or optional code in the repository.

- **CCTV:** Site camera records may exist; **live viewing is not exposed** in the default UI.  
- **Biometric:** Default browser bundles do not include in-capture biometric scripts; verification may still be used via API/devices per your deployment.  
- **Optional modules:** `hr_attendance` and `maintenance` extend attendance and equipment when installed.  

---

## Who it is for

- Contract security providers and in-house security teams  
- Property and facilities teams that need patrol and incident discipline  
- Anyone who has outgrown spreadsheets for SLA and audit evidence  

---

## Quick setup

| Step | Topic | Link |
|------|--------|------|
| 1 | First patrol loop (guided) | [Get started](GETTING_STARTED.md) |
| 2 | Install the module | [Installation](user-guide/02-installation.md) |
| 3 | Configure groups and settings | [Configuration](user-guide/03-configuration.md) |
| 4 | Add guards and a site | [Guard profiles](guards/profile_management.md) · [Site setup](sites/site_setup.md) |
| 5 | First shift | [Shift management](operations/shift_management.md) |

---

## Technical notes

- **Odoo:** 18 Community  
- **Python:** 3.10+  
- **PostgreSQL:** 13+  
- **Python deps:** `markdown` (in-app docs), plus packages listed in `requirements.txt` / manifest for optional features  

Core dependencies include: `base`, `web`, `website`, `hr`, `project`, `contacts`, `mail`, `portal`, `auth_signup`, `website_slides`.

---

## License

LGPL-3 — see the module root for the full license text.

---

## More

- [Full index](INDEX.md)  
- [Quick reference](QUICK_REFERENCE.md)  
- [Developer guide](developer-guide/01-architecture.md)  
