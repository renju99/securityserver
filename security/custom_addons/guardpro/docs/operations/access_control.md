# Access Control

Complete guide to managing site access control in GuardLink.

---

## Overview

Access Control Management helps you manage access cards, badges, permissions, door access rules, and monitor access logs for secure facility management.

---

## Access Card Management

### Issuing Access Cards

**Navigation:**
- GuardLink > Access Control > Access Cards
- Click **"Issue Card"**

### Card Information

| Field | Mandatory | Description |
|-------|-----------|-------------|
| **Card Number** | ✅ Yes | Unique card ID |
| **Cardholder** | ✅ Yes | Person assigned |
| **Card Type** | ✅ Yes | Employee/Visitor/Contractor/VIP |
| **Valid From** | ✅ Yes | Activation date |
| **Valid Until** | ✅ Yes | Expiration date |
| **Access Level** | ✅ Yes | Permissions granted |
| **PIN Code** | ❌ No | Optional PIN |

### Access Levels

**Pre-defined Levels:**
- **Level 1:** Public areas only
- **Level 2:** Office areas
- **Level 3:** Restricted areas
- **Level 4:** High security zones
- **Level 5:** Full access (management)

**Custom Levels:**
- Create site-specific levels
- Define exact door/area access
- Set time restrictions
- Configure escort requirements

---

## Door Access Rules

### Configuring Door Access

**For Each Door:**
- Which access levels permitted
- Time-based restrictions
- Require PIN/biometric
- Anti-passback enabled
- Alarm on unauthorized attempt

### Time-Based Access

**Schedule Examples:**
- **Business Hours:** Mon-Fri 8AM-6PM
- **24/7 Access:** No restrictions
- **Night Shift:** 6PM-6AM
- **Weekends Only:** Sat-Sun any time
- **After Hours:** 6PM-8AM + weekends

---

## Access Logs

### Viewing Access History

**Navigation:**
- GuardLink > Access Control > Access Logs

**Log Shows:**
- Date/time of access
- Door/location
- Cardholder name
- Access granted/denied
- Method (card/PIN/biometric)

### Access Violations

**Types of Violations:**
- Unauthorized access attempt
- Tailgating detected
- Door forced open
- Held open too long
- Card used outside permitted hours
- Multiple failed PIN attempts

**Violation Response:**
- Alert sent to security
- Incident automatically created
- Card temporarily suspended
- CCTV footage flagged
- Investigation initiated

---

## Visitor Access

### Temporary Access

**Process:**
1. Register visitor (see Visitor Management)
2. Issue temporary access card
3. Set expiration (typically same day)
4. Define allowed areas
5. Require escort if needed
6. Auto-deactivate at end of day

---

## Reports

**Available Reports:**
- Access activity by person
- Access by door/location
- Violations and attempts
- Time-based access patterns
- Card usage statistics
- Unauthorized access attempts

---

## Need More Help?

- 📘 **See also:** [Visitor Management](visitor_management.md)
- 📘 **See also:** [Site Setup](../sites/site_setup.md)
- 📘 **See also:** [Incident Management](incident_management.md)
