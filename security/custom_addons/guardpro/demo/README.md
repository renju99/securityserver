# GuardPro Demo Data Documentation

## Overview

This comprehensive demo data package showcases all features of the GuardPro Security Guard Management System. The demo data is designed to persist through module uninstall/reinstall cycles, making it perfect for client presentations and demonstrations.

## Demo Data Components

### 1. Core System Demo Data

#### Guards & Skills (`guard_demo_data.xml`)
- **10 Guard Profiles** with diverse skills and certifications
- **8 Guard Skills** (Armed Security, K9 Handler, First Aid, etc.)
- Guards with varying availability (full-time, part-time, on-call)
- Different status types (active, on_leave)
- Complete contact information and emergency contacts

**Featured Guards:**
- John Smith (GP-001) - Senior Guard with full qualifications
- Sarah Johnson (GP-002) - K9 Handler
- Michael Brown (GP-003) - Night Shift Specialist
- Emily Davis (GP-004) - Part-Time Guard
- And 6 more...

#### Client Sites (`client_demo_data.xml`)
- **NSHAMA** - Premium real estate client
- **2 Active Sites:**
  - NSHAMA Town Square (3 guards required)
  - NSHAMA The Springs (2 guards required)
- Complete geofencing configuration
- Site manager and emergency contact details
- Active contract information

#### eLearning Courses (`guard_elearning_demo_data.xml`)
- Pre-configured training courses
- Course enrollment data
- Completion tracking

### 2. Task Management Demo Data (`task_management_demo_data.xml`)

**10 Guard Tasks** covering all task types:
- **Patrol Tasks**: Morning perimeter patrol, night building inspection
- **Access Control**: Daily system checks
- **Safety Inspections**: Weekly equipment inspection
- **Equipment Checks**: Radio equipment verification
- **Visitor Screening**: Enhanced screening protocols
- **Emergency Drills**: Monthly fire evacuation drill
- **Maintenance Checks**: Pool area security
- **Incident Response**: Follow-up tasks

**Task Features Demonstrated:**
- Recurring tasks (daily, weekly, monthly)
- Task checklists with mandatory items
- Multiple priority levels
- Various task states (assigned, in_progress, completed)
- Links to incidents and shifts

### 3. Visitor Management Demo Data (`visitor_management_demo_data.xml`)

**Comprehensive visitor scenarios:**

- **Watchlist Entries (2)**: High and medium risk individuals
- **Pre-registered Visitors (2)**: Contractors and personal visitors with pre-approval
- **Checked-in Visitors (2)**: Active visitors including VIP guest
- **Checked-out History (2)**: Completed visits with full details
- **Vendor/Contractor (1)**: Long-term vendor with contract
- **Overstay Alert (1)**: Visitor exceeding expected duration
- **Job Applicant (1)**: Interview candidate
- **Denied Entry (1)**: Blacklisted attempt

**Features Showcased:**
- QR badge generation
- ID verification (Emirates ID, Passport, etc.)
- Pre-registration workflow
- VIP visitor handling
- Watchlist screening
- Escort requirements
- Vehicle tracking

### 4. Lost & Found Demo Data (`lost_found_demo_data.xml`)

**11 Lost Items** representing various categories:
- Mobile Phone (iPhone 14 Pro)
- Luxury Wallet (Louis Vuitton) - Claimed
- Car Keys (Mercedes Benz)
- MacBook Pro 16"
- Rolex Watch (High Value)
- Eyeglasses (Ray-Ban)
- Gold Bracelet (Cartier)
- Student Backpack
- Business Documents
- Child's Jacket
- Expired Umbrella (Disposed)

**Features Demonstrated:**
- Photo evidence capability
- Claim verification process
- High-value item handling
- Police report integration
- Legal holding periods
- Disposal tracking
- Confidential item management

### 5. Package Management Demo Data (`package_management_demo_data.xml`)

**10 Package Scenarios:**
- Standard Parcels (Aramex, Noon, DHL)
- Food Delivery (Talabat)
- Confidential Documents (Banking)
- Oversized Furniture (IKEA)
- Equipment Delivery (Gym)
- Medical Supplies (Refrigerated)
- Grocery Delivery (Perishable)
- Picked Up Package (History)
- Overdue Package (Alert)
- Unclaimed Package (35 days)

**Features Showcased:**
- Tracking number integration
- Signature requirements
- ID verification
- Storage location tracking
- Notification system
- Pickup verification
- Special handling (perishable, confidential, urgent)
- Overdue alerts

### 6. Key Management Demo Data (`key_management_demo_data.xml`)

**12 Keys in Registry:**
- Room Keys (Security Office)
- Gate Keys (Main Entrance, Pool)
- Vehicle Keys (Patrol Vehicle)
- Cabinet Keys (Security Equipment)
- Master Keys (Building Access)
- Office Keys (Server Room, Admin)
- Locker Keys
- Roof Access Keys

**Transaction Types:**
- Active Issuances (4)
- Completed Returns (3)
- Overdue Keys (1)
- Lost Keys (1) with replacement tracking
- Damaged Keys (1) with replacement cost

**Features Demonstrated:**
- Guard issuance tracking
- Contractor key management
- Security deposits
- Odometer tracking (vehicles)
- Duplicate key management
- Key replacement process
- Overdue alerts

### 7. Compliance Audit Demo Data (`compliance_audit_demo_data.xml`)

**9 Comprehensive Audits:**
- Site Security Audit (95% - Passed)
- Guard Performance Audit (88% - Passed)
- Failed Safety Audit (65%) with Corrective Actions
- Equipment Audit (In Progress)
- Scheduled Regulatory Audit
- Training Compliance Audit (92% - Passed)
- Operational Audit (85% - Passed)
- Quality Assurance Audit (90% - Passed)
- K9 Handler Performance Audit (94% - Passed)

**Corrective Actions:**
- Fire extinguisher replacement (Completed)
- Emergency exit sign repair (In Progress)
- First aid kit restocking (Completed)

**Features Demonstrated:**
- Scheduled vs. surprise audits
- Audit checklists
- Scoring system
- Pass/fail criteria
- Corrective action workflow
- Follow-up scheduling
- Multiple audit types

### 8. SLA Management Demo Data (`sla_management_demo_data.xml`)

**6 SLA Definitions:**
- Critical Incident Response (5 min response, 2 hrs resolution)
- High Priority Incident (15 min response, 4 hrs resolution)
- Security Patrol Completion (30 min response, 2 hrs completion)
- Visitor Processing (10 min processing time)
- Urgent Task Completion (30 min start, 4 hrs completion)
- Package Notification (15 min notification time)

**10+ Performance Records:**
- Met SLAs (7)
- Breached SLAs (2) with documented reasons
- Warning Status (1) - close to breach
- In Progress (1)

**Features Demonstrated:**
- Response time tracking
- Resolution time tracking
- Breach alerts
- Performance metrics
- Breach reason documentation
- Real-time SLA monitoring

### 9. Access Control Demo Data (`access_control_demo_data.xml`)

**7 Access Control Devices:**
- Main Entrance Door Lock (HID Global)
- Server Room Access (Suprema BioStation)
- Main Vehicle Gate (CAME)
- Service/Delivery Gate
- Parking Barrier (BFT)
- Lobby Turnstile (Boon Edam)
- Gym Door (Under Maintenance)

**12+ Access Events:**
- Access Granted (RFID, Mobile, Biometric, QR Code)
- Access Denied (Invalid credentials, Outside hours)
- Manual Override (Emergency)
- Scheduled Access
- Forced Entry Alert
- Tailgating Detection

**Features Demonstrated:**
- Multiple access methods
- Device health monitoring
- Remote control capability
- Biometric access
- Mobile app access
- Emergency override
- Alert system
- Event logging

### 10. Additional Demo Data

#### Shifts & Tours
- Active shifts in progress
- Completed shift history
- Tour logs with checkpoint scans

#### Incidents
- Various incident types and severities
- Investigation workflow
- Resolution tracking

#### Equipment
- Security equipment inventory
- Maintenance tracking
- Assignment records

#### Attendance
- Check-in/check-out records
- Time tracking
- Shift attendance

## Installation & Usage

### Installing Demo Data

1. **Fresh Installation:**
   ```bash
   # Install module with demo data enabled
   odoo-bin -d your_database -i guardpro --load-language=en_US
   ```

2. **Enable Demo Data on Existing Installation:**
   - Uninstall the module completely
   - Reinstall with demo data flag enabled
   - All demo data will be recreated

### Demo Data Persistence

All demo data files use `noupdate="1"` which means:
- ✅ Data persists through module upgrades
- ✅ Data can be manually modified without being overwritten
- ✅ Perfect for presentations and testing
- ⚠️ To reset demo data, you must uninstall and reinstall the module

### Best Practices for Presentations

1. **Preparation:**
   - Install module with demo data 24 hours before presentation
   - Review all demo scenarios
   - Customize site names to match client if needed
   - Adjust dates to be recent

2. **Key Demonstration Flows:**

   **Flow 1: Daily Operations**
   - Show active guards and shifts
   - Display task management dashboard
   - Review visitor check-ins
   - Check package deliveries
   - Monitor SLA performance

   **Flow 2: Security Incident Response**
   - Show incident reporting
   - Demonstrate SLA tracking
   - Review investigation workflow
   - Show compliance audit results

   **Flow 3: Access Control & Monitoring**
   - Display access control devices
   - Show real-time event logs
   - Demonstrate remote control
   - Review security alerts

   **Flow 4: Lost & Found / Package Management**
   - Show lost items with photos
   - Demonstrate claim process
   - Review package tracking
   - Show notification system

   **Flow 5: Compliance & Quality**
   - Review audit history
   - Show corrective actions
   - Display key management
   - Review SLA metrics

3. **Client-Specific Customization:**
   - Replace NSHAMA with client name
   - Adjust guard count to match client needs
   - Configure sites to match client locations
   - Set appropriate SLA targets

## Demo Data Statistics

- **Guards:** 10 active profiles
- **Sites:** 2 configured locations
- **Tasks:** 10+ various task types
- **Visitors:** 10+ visitor scenarios
- **Lost Items:** 11 items (including claimed/expired)
- **Packages:** 10+ package deliveries
- **Keys:** 12 keys with 10+ transactions
- **Audits:** 9 comprehensive audits
- **SLAs:** 6 definitions, 10+ performance records
- **Access Devices:** 7 devices with 12+ events
- **Incidents:** 3+ security incidents
- **Shifts:** Active and historical data

## Troubleshooting

### Demo Data Not Loading
- Ensure demo data flag is enabled during installation
- Check Odoo logs for XML parsing errors
- Verify all referenced fields exist in models

### Data Dependencies
Demo data loads in specific order:
1. Guards, Skills, Sites (Foundation)
2. Shifts, Equipment (Infrastructure)
3. Tasks, Visitors, Packages (Operations)
4. Keys, Audits, SLAs (Management)
5. Access Control (Integration)

### Modifying Demo Data
- Edit XML files before installation
- Use `noupdate="0"` to allow updates (not recommended for demos)
- Clear database and reinstall to reset all demo data

## Support

For issues or questions about demo data:
1. Check module logs for errors
2. Verify XML file syntax
3. Review model field definitions
4. Contact module administrator

---

**Last Updated:** October 2024
**Module Version:** 18.0.1.0.1
**Demo Data Version:** 2.0 (Complete Suite)

