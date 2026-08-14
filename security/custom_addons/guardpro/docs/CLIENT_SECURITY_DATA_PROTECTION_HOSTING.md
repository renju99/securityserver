# GuardLink — Security, Data Protection & Hosting Overview

**Client Assurance Document**  
Version 1.0 · July 2026 · Client-shareable  
Platform: GuardLink on Odoo 18

---

## 1. Purpose

Clients often ask whether introducing a digital guard management platform is safe for their site data, personal information, and operational records. This document explains how GuardLink is designed and hosted so implementation can proceed with clear visibility into security controls, data isolation, and operational safeguards.

GuardLink is an enterprise security operations suite for guard tours, attendance, incidents, visitors, keys, compliance reporting, and client visibility. It is built on Odoo 18 Community Edition with role-based access, site-level data isolation, audit logging, and privacy tooling.

---

## 2. Executive summary

- **Encrypted in transit** — HTTPS with TLS 1.2 / 1.3 and HSTS.
- **Role-based access** — guards, supervisors, managers, administrators, reception, and client users receive only the permissions they need.
- **Site-level data isolation** — client users and field staff only see records for sites they are assigned to.
- **Auditability** — sensitive actions can be traced via audit logs and chatter history.
- **Privacy tooling** — export and anonymization workflows support personal-data requests (GDPR-style access / erasure processes).
- **Hardened hosting** — reverse-proxy TLS, security headers, database listing disabled, containerized app/DB separation.

**Bottom line:** Client operational data stays partitioned by site and role, travels over encrypted channels, and remains under the security provider’s administration—with portal access limited to what each client is authorized to see.

---

## 3. What data GuardLink processes

| Category | Examples | Typical purpose |
|----------|----------|-----------------|
| Operational | Sites, tours, checkpoints, shifts, DAR, SLA | Security delivery & reporting |
| Personnel | Guard profiles, credentials, training, attendance | Staffing & compliance |
| Incident & evidence | Incident reports, photos, investigations | Response & client notification |
| Access & visitors | Visitor logs, packages, key issue/return | Access control & custody |
| Location (optional) | GPS / geofence / checkpoint scans | Patrol verification |
| Client portal | Dashboards, feedback, shared reports | Client oversight |
| Technical / audit | Login context, audit trail entries | Accountability |

Location history can be sensitive. Export of location history is optional and off by default in privacy export tools.

---

## 4. Access control & data isolation

### 4.1 Role-based access control (RBAC)

| Role | Access principle |
|------|------------------|
| Administrator | Full system access for authorized provider staff only |
| Manager | Full operational control for assigned sites |
| Supervisor | Oversight for assigned sites (primarily read / limited write) |
| Guard (portal) | Own profile and assigned-site field workflows |
| Client user | Read-only visibility for assigned site(s) only |
| Reception | Front-desk workflows as configured |

### 4.2 Record-level (site) isolation

Non-admin users are limited to sites assigned on their user account:

- A client user for Site A cannot open Site B’s incidents, tours, attendance, CCTV, investigations, or reports.
- Guards, supervisors, managers, and reception only work within their assigned sites.
- Watchlist and visitor-host directories are scoped by site and auto-assigned on create (visitor site / user sites); empty stock is backfilled so entries are not left admin-only. Unassigned stock equipment is not shared across clients.
- Intentional company-wide emergency broadcasts (`broadcast_type = all`) remain visible to relevant field staff.
- REST API keys inherit the bound user’s assigned sites (administrators retain full access).
- Administrators retain cross-site access required to operate the security company.

### 4.3 Client portal boundary

Clients receive a dedicated portal with secure login. Portal users are provisioned by the security provider and scoped to the client’s sites—transparency without administrative or cross-client access.

**Do not assign GuardLink “Client User” to residents.** That group implies Odoo Internal User (backend). Residential tenants must use **Resident/Tenant User** (portal). “Client User” is only for B2B client-company staff who need backend site visibility.

---

## 5. Hosting & infrastructure posture

Typical production architecture (e.g. Berkeley UAE GuardLink):

- **Application:** GuardLink on Odoo 18, containerized and reverse-proxied
- **Database:** PostgreSQL on a private network (not exposed publicly)
- **Edge / TLS:** Nginx terminates HTTPS; HTTP redirects to HTTPS
- **Certificates:** Public TLS certificates with renewal processes
- **Transport:** TLS 1.2–1.3; HSTS; security headers (`X-Content-Type-Options`, `X-Frame-Options`, etc.)
- **Hardening:** `list_db = False`; `proxy_mode` behind the reverse proxy
- **Separation:** App and DB as isolated Docker services; only the proxy is public

### 5.1 Encryption

| Layer | Control |
|-------|---------|
| In transit | HTTPS / TLS 1.2–1.3 for web, portal, and API traffic |
| Passwords | Odoo secure password hashing (not reversible plaintext) |
| Biometric material (where used) | Application-level encryption (Fernet / PBKDF2) |
| At rest | Secured host volumes; disk encryption per infrastructure policy |

### 5.2 Availability & backups (provider-operated)

Recommended baseline:

- Automated database backups with tested restores
- Off-host / off-site backup copies
- Container restart policies and health monitoring
- Controlled change windows for upgrades
- Infrastructure access limited to authorized administrators

---

## 6. Application security controls

### Authentication & sessions

- Named user accounts (avoid shared generic client logins)
- Password authentication with Odoo session management
- Accounts can be deactivated without deleting operational history

### Authorization

- Model ACLs per security group
- Record rules for site-scoped visibility
- Menu / feature visibility by group
- API and portal routes inherit the same auth model

### Audit & accountability

- Dedicated audit log for tracked events
- Chatter on key records
- Incident investigation / escalation history
- Exportable compliance and daily activity reports

### Privacy & data subject rights

- **Data export** — guard personal and related operational data (JSON / XML / PDF)
- **Anonymization** — remove personal identifiers while retaining operational history where needed
- **Configurable scope** — location history optional in exports

These tools support GDPR-style processes and help align with UAE PDPL principles (purpose limitation, security, data subject rights). Final legal compliance remains with the contracting parties and their policies.

---

## 7. Common client questions (FAQ)

**Will other clients see our site data?**  
No. Client portal users and non-admin users are restricted by site assignment record rules.

**Is our data encrypted in transit?**  
Yes. HTTPS with TLS 1.2/1.3, HTTP→HTTPS redirect, and HSTS.

**Who owns / controls our data?**  
Records are held in the security provider’s GuardLink instance. Portal accounts provide authorized visibility. Contractual terms (DPA / service agreement) should define retention, export, and exit assistance.

**Can we get reports without full system access?**  
Yes. Client users are typically read-only for assigned sites; PDF/Excel reports cover incidents, DAR, attendance, site summaries, and compliance.

**What about guard personal data and biometrics?**  
Protected by role permissions. Where biometric features are used, sensitive material uses application-level encryption. Features are enabled only as configured.

**Does GuardLink sell or share our data?**  
Operated as the provider’s security operations system for contracted delivery and reporting. Subprocessors (email/SMS, hosting, maps) should be listed in the provider’s privacy / processing schedule.

**Where is the system hosted?**  
Controlled by the security provider. Berkeley UAE example: TLS-secured public endpoint at `https://security.berkeleyuae.com/`. On-premise or dedicated hosting can be discussed contractually.

**How are leavers handled?**  
Accounts can be deactivated immediately while preserving audit and operational history.

**Can we request deletion of personal data?**  
Yes—via the provider’s privacy process. Export and anonymization workflows support this.

**Is this a blind multi-tenant SaaS?**  
Deployments are provider-operated instances with internal site/role isolation. Clients do not browse unrelated sites.

---

## 8. Shared responsibility

| Security provider / operator | Client organization |
|------------------------------|---------------------|
| Host hardening, TLS, backups, patching, admin access | Nominate authorized portal users only |
| Correct site assignment & role provisioning | Protect credentials; report suspected misuse |
| Platform incident response | Define what may be shared via portal |
| Privacy requests & retention schedules | Raise data-subject / contractual requests in writing |
| Staff training & least privilege | Align site SOPs with digital workflows |

---

## 9. Go-live safeguards checklist

- [ ] HTTPS enforced; certificates valid
- [ ] Public database listing disabled; admin master password restricted
- [ ] Client users: least privilege + correct site assignments only
- [ ] Confirm which modules (GPS, biometrics, visitor PII) are required
- [ ] Agree retention for incidents, visitor logs, and personnel data
- [ ] Document backup frequency and last restore test
- [ ] Provide portal URL, support contact, escalation path
- [ ] Access review after first week live

---

## 10. Assurance statement

GuardLink is designed as a security-first operations platform: encrypted transport, role-based and site-scoped access, auditability, and privacy tooling are built in. When deployed on a hardened, provider-managed host with correct user provisioning, it is suitable for client site operations where confidentiality of site activity, incident records, and personnel data matters.

This document describes product and hosting controls. It is **not** a legal opinion, ISO 27001 / SOC 2 certificate, or substitute for a Data Processing Agreement. Formal certifications, penetration-test reports, or contractual DPAs can be provided separately upon request where available.

---

## 11. Contact

- Product: GuardLink — Enterprise Security Guard Management  
- Website: https://guardlink.app/  
- Example production portal (Berkeley UAE): https://security.berkeleyuae.com/  
- Support: via your GuardLink / Berkeley Security account manager  

For a live walkthrough, request a roles / site-isolation / audit-log / privacy-export demo.
