# GuardLink documentation

Welcome to the documentation for **GuardLink**, the security guard operations suite for Odoo 18. This hub is organized like a **guide**: short chapters, clear outcomes, and links into deeper topics.

**Module version:** 18.0.1.1.17 · **Last updated:** March 2026

---

## How to use this guide

| If you want to… | Start here |
|-----------------|------------|
| Go from zero to first patrol loop | [Get started — Chapter 1](GETTING_STARTED.md) |
| Install and turn the module on | [Installation](user-guide/02-installation.md) |
| Permissions, settings, go-live checklist | [Configuration](user-guide/03-configuration.md) |
| One-page cheat sheet | [Quick reference](QUICK_REFERENCE.md) |
| APIs and integrations | [Mobile API](api/mobile-api.md) · [REST API](api/rest-api.md) · [Webhooks](api/webhooks.md) |

Open the **in-app documentation** (from GuardLink, if your admin enabled it) for search and the same content in a reader-friendly layout.

---

## Product scope (current build)

Documentation matches **what ships today**, not a future roadmap.

- **Mobile:** Guards use the **web app** (responsive, installable from the browser on many devices). Older standalone PWA bundles are not used.  
- **CCTV:** Camera records can exist per site configuration; **live monitoring is not available** in the default web UI.  
- **Biometric:** In-browser biometric capture is **not** in the default asset bundle; attendance and verification depend on your configured process (manual, device, or integration).  
- **Optional Odoo apps:** `hr_attendance` and `maintenance` remain optional; some menus and automation appear only when those apps are installed.  

---

## Chapters at a glance

### Chapter 1 — Orientation

- [Get started — first site and patrol loop](GETTING_STARTED.md)  
- [Introduction](user-guide/01-introduction.md)  
- [Features overview](user-guide/04-features.md)  
- [Workflows](user-guide/05-workflows.md)  
- [Troubleshooting](user-guide/06-troubleshooting.md)  

### Chapter 2 — People and sites

- [Guard profiles](guards/profile_management.md)  
- [Attendance](guards/attendance.md)  
- [Performance](guards/performance.md)  
- [Training](guards/training.md)  
- [Site setup](sites/site_setup.md)  
- [Checkpoints](sites/checkpoints.md)  
- [Patrols](sites/patrols.md)  
- [Equipment](sites/equipment.md)  

### Chapter 3 — Daily operations

- [Shifts](operations/shift_management.md)  
- [Incidents](operations/incident_management.md)  
- [Visitors](operations/visitor_management.md)  
- [Access control](operations/access_control.md)  

### Chapter 4 — Compliance and reporting

- [Audits](compliance/audits.md)  
- [Daily activity reports](compliance/reports.md)  
- [SLA](compliance/sla.md)  

### Chapter 5 — Developers and integrations

- [Architecture](developer-guide/01-architecture.md)  
- [Models](developer-guide/02-models.md)  
- [Views](developer-guide/03-views.md)  
- [Business logic](developer-guide/04-business-logic.md)  
- [Security (access rules)](developer-guide/05-security.md)  
- [Customization](developer-guide/06-customization.md)  

---

### Client due diligence

- [Security, data protection & hosting overview](CLIENT_SECURITY_DATA_PROTECTION_HOSTING.md) — client-shareable assurance brief (access control, isolation, TLS hosting, privacy FAQ)

## Additional reference material

Specialized notes (deployment, testing, planning) live alongside this guide, for example:

- [SOP printable guide](SOP_PRINTABLE_GUIDE.md)  
- Printable and operational PDFs are generated from the app where templates are configured.  

Use the sidebar search in the **in-app documentation** viewer to find niche topics quickly.

---

## Support

- **Email:** support@guardlink.app  
- **Website:** [guardlink.app](https://guardlink.app/)  

---

[↑ Back to top](#guardlink-documentation)
