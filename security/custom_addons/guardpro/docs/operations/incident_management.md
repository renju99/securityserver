# Incident Management

Complete guide to reporting, tracking, and managing security incidents in GuardPro.

---

## Table of Contents
1. [Overview](#overview)
2. [Accessing Incident Management](#accessing-incident-management)
3. [Reporting a New Incident](#reporting-a-new-incident)
4. [Incident Classification](#incident-classification)
5. [Adding Evidence and Photos](#adding-evidence-and-photos)
6. [Updating Incident Status](#updating-incident-status)
7. [Escalating Incidents](#escalating-incidents)
8. [Viewing Incident Reports](#viewing-incident-reports)
9. [Common Workflows](#common-workflows)

---

## Overview

Incident Management allows you to:
- Report security incidents in real-time
- Track incident resolution progress
- Document evidence with photos and files
- Escalate critical incidents automatically
- Generate incident reports for clients
- Analyze incident trends and patterns

**Who Uses This:**
- Security Guards (report incidents)
- Supervisors (review and assign)
- Managers (oversee resolution)
- Clients (view incidents at their sites)

---

## Accessing Incident Management

### Navigation Steps:

**Method 1: From Main Menu**
1. Click **"GuardPro"** (top navigation)
2. Select **"Operations"**
3. Click **"Incident Reports"**

**Method 2: Quick Search**
- Press `Ctrl + K` (or `Cmd + K`)
- Type **"incidents"**
- Select **"Incident Reports"**

**Method 3: From Dashboard**
- Go to GuardPro Dashboard
- Click **"Incidents"** widget
- Shows recent incidents with quick filters

---

## Reporting a New Incident

### Step-by-Step Process:

#### Step 1: Open Incident Form

1. From Incident Reports list, click **"Create"** button
2. New incident report form opens

#### Step 2: Basic Incident Information

**Section: Incident Details**

| Field Name | Type | Mandatory | Description | Example |
|------------|------|-----------|-------------|---------|
| **Incident Number** | Auto | ✅ Auto-generated | Unique incident ID | INC-2025-0123 |
| **Site** | Selection | ✅ Yes | Location where incident occurred | "ABC Corporate HQ" |
| **Incident Date** | Date | ✅ Yes | Date of incident | "2025-10-29" |
| **Incident Time** | Time | ✅ Yes | Time incident occurred | "14:30" |
| **Reported By** | Selection | ✅ Auto | Guard who reported (current user) | Auto-filled |
| **Incident Type** | Selection | ✅ Yes | Category of incident | See classification below |
| **Severity** | Selection | ✅ Yes | Impact level | Low/Medium/High/Critical |

**How to Fill:**

1. **Site Selection:**
   - Click dropdown
   - System shows only sites you have access to
   - If reporting from shift, site is auto-filled
   - Can't change site once incident has updates

2. **Incident Date & Time:**
   - Default: Current date and time
   - Can adjust if reporting past incident
   - **Important:** Time must be accurate for log correlation
   - Format auto-adjusts to your timezone

3. **Incident Type Selection:**
   - Click dropdown to see categories
   - Each type has different required fields
   - Choose most specific type available

4. **Severity Level Guide:**

| Severity | When to Use | Response Time | Examples |
|----------|-------------|---------------|----------|
| **Low** | Minor issues, no immediate threat | 24-48 hours | Noise complaint, lost property |
| **Medium** | Requires attention, minor impact | 4-8 hours | Unauthorized parking, minor property damage |
| **High** | Significant concern, needs prompt action | 1-2 hours | Trespassing, suspicious activity |
| **Critical** | Immediate threat, emergency response | Immediate | Assault, fire, medical emergency |

**⚠️ Critical Incidents:**
- Automatically notify supervisor
- Create emergency task
- Send SMS alerts
- Log to audit trail

#### Step 3: Incident Location Details

**Section: Location Information**

| Field Name | Type | Mandatory | Description |
|------------|------|-----------|-------------|
| **Specific Location** | Text | ✅ Yes | Exact location within site |
| **Building/Area** | Selection | ❌ No | Building or zone identifier |
| **Floor/Level** | Text | ❌ No | Floor number or level |
| **Checkpoint** | Selection | ❌ No | Nearest checkpoint (if applicable) |
| **GPS Coordinates** | Auto | ❌ No | Auto-captured from mobile app |

**How to Fill:**

1. **Specific Location:**
   - Be as detailed as possible
   - Examples:
     - "Main entrance lobby, near security desk"
     - "Parking Lot B, near northwest corner"
     - "3rd floor, Room 305"
   - Helps responders locate quickly

2. **Using Mobile App:**
   - GPS coordinates captured automatically
   - Can attach photos showing location
   - Timestamp automatically recorded

**💡 Tips:**
- Include landmarks for easier identification
- Reference checkpoint numbers if near patrol route
- Add floor/level even if building has only ground floor

#### Step 4: Incident Description

**Section: Details and Description**

| Field Name | Type | Mandatory | Description | Character Limit |
|------------|------|-----------|-------------|-----------------|
| **Summary** | Text | ✅ Yes | Brief one-line description | 100 characters |
| **Detailed Description** | Text Area | ✅ Yes | Complete incident details | Unlimited |
| **Actions Taken** | Text Area | ✅ Yes | What you did in response | Unlimited |
| **Witnesses** | Text Area | ❌ No | Names and contacts of witnesses | Unlimited |
| **Police Notified** | Checkbox | ❌ No | If police were called | Yes/No |
| **Police Report Number** | Text | ❌ No | Official police report reference | - |

**How to Write Good Descriptions:**

**Summary (One Line):**
- Be concise but clear
- ❌ Bad: "Problem at site"
- ✅ Good: "Unauthorized vehicle attempted entry at main gate"

**Detailed Description (Use 5 W's):**
- **Who:** Who was involved?
- **What:** What happened exactly?
- **When:** Time sequence of events
- **Where:** Precise location
- **Why:** Suspected cause or motive (if known)

**Example Detailed Description:**
```
At approximately 14:30, I observed a white Toyota sedan (License: ABC-1234) 
attempting to enter through the main gate without proper authorization. 
The driver, a male approximately 35-40 years old wearing a blue shirt, 
claimed he had a delivery but could not provide a delivery order number.

I politely denied entry and requested he contact the recipient to arrange 
proper authorization. The driver became argumentative and attempted to 
drive around the barrier. I immediately activated the emergency alert and 
contacted my supervisor.

The vehicle left the premises at 14:35 heading northbound on Main Street. 
I observed the driver using a mobile phone while leaving.
```

**Actions Taken:**
- List everything you did in chronological order
- Include who you notified
- Mention any emergency procedures activated

**Example Actions Taken:**
```
1. Denied entry and requested proper authorization (14:30)
2. Activated emergency alert on mobile app (14:32)
3. Contacted Supervisor John Smith via radio (14:32)
4. Documented vehicle details and license plate (14:33)
5. Took photographs of vehicle (attached) (14:34)
6. Updated gate log with incident (14:36)
7. Completed this incident report (14:45)
```

#### Step 5: People Involved

**Section: Involved Parties**

Click **"Add Person"** to document each person involved:

| Field | Mandatory | Description |
|-------|-----------|-------------|
| **Role** | ✅ Yes | Suspect/Victim/Witness/Other |
| **Name** | ✅ Yes | Full name (if known) |
| **Description** | ❌ No | Physical description |
| **Contact Info** | ❌ No | Phone/email if available |
| **ID Verified** | ❌ No | If ID was checked |
| **ID Type & Number** | ❌ No | Type of ID and number |

**Physical Description Template:**
```
Gender: [Male/Female/Unknown]
Age: [Approximate age or range]
Height: [Approximate in ft/cm]
Build: [Slim/Average/Heavy]
Hair: [Color and length]
Clothing: [Description]
Distinguishing features: [Scars, tattoos, etc.]
```

**Example:**
```
Gender: Male
Age: 35-40 years
Height: Approximately 5'10" (178cm)
Build: Average
Hair: Dark brown, short
Clothing: Blue button-down shirt, dark jeans
Distinguishing features: Glasses, small scar on left cheek
Vehicle: White Toyota Sedan, License ABC-1234
```

#### Step 6: Add Evidence

**Section: Evidence and Attachments**

**Evidence Types:**
- 📷 Photos
- 🎥 Video footage
- 📄 Documents
- 🎤 Audio recordings
- 📊 CCTV footage references

**How to Add Photos:**

**Step A:** Click **"Add Photo"** button

**Step B:** Fill photo details:

| Field | Description |
|-------|-------------|
| **Photo File** | Upload image (JPG, PNG, HEIC) |
| **Caption** | Describe what photo shows |
| **Timestamp** | When photo was taken (auto-filled) |
| **Taken By** | Who captured photo (auto-filled) |

**Step C:** Click **"Upload"**

**📸 Photo Best Practices:**
- Take multiple angles
- Include wide shots for context
- Close-ups for details (damage, license plates, etc.)
- Ensure good lighting
- Don't delete original photos from device (backup)

**CCTV Footage:**
- Note camera numbers and time ranges
- Example: "Camera 3, 14:25-14:40, main entrance"
- Request footage download from control room
- Attach or reference in incident report

#### Step 7: Assign and Notify

**Section: Assignment and Notifications**

| Field | Type | Mandatory | Description |
|-------|------|-----------|-------------|
| **Assigned To** | Selection | ❌ No | Person responsible for follow-up |
| **Supervisor** | Selection | ✅ Auto | Your supervisor (auto-filled) |
| **Priority** | Selection | ✅ Auto | Based on severity (auto-calculated) |
| **Notify Client** | Checkbox | ❌ No | Send report to client contact |
| **Client Notification Method** | Selection | ❌ No | Email/SMS/Both |

**How Assignment Works:**

1. **For Low/Medium Severity:**
   - Assigned to your supervisor by default
   - Supervisor can reassign
   - Standard workflow applies

2. **For High Severity:**
   - Auto-assigned to supervisor
   - Supervisor notified immediately via SMS
   - Escalation timer starts (2 hours)

3. **For Critical Severity:**
   - Auto-assigned to operations manager
   - Immediate notifications sent:
     - Supervisor (SMS + Call)
     - Manager (SMS + Call)
     - On-call team (Alert)
   - Emergency protocol activated

**Client Notification:**
- Check **"Notify Client"** if:
  - Site requires immediate incident notification
  - Severity is High or Critical
  - Client property damaged
  - Client personnel involved
  
- ❌ Don't notify for:
  - Routine security checks
  - False alarms
  - Internal training incidents

#### Step 8: Review and Save

**Pre-Save Checklist:**

✅ All mandatory fields filled  
✅ Description is complete and clear  
✅ Actions taken documented  
✅ Evidence/photos attached  
✅ People involved documented  
✅ Severity accurately reflects situation  
✅ Location details are precise  

**Save Options:**

1. **"Save & Submit"** - Finalizes report, sends notifications
2. **"Save as Draft"** - Save progress, complete later
3. **"Save & New"** - Submit and create another incident
4. **"Discard"** - Cancel without saving

**What Happens After Submission:**

1. ✅ Incident number assigned (if not auto-generated)
2. ✅ Status set to **"Reported"**
3. 📧 Email sent to assigned person
4. 📱 SMS sent (if High/Critical severity)
5. 📊 Incident appears in dashboards
6. ⏱️ Resolution timer starts
7. 🔔 Mobile app notifications sent
8. 📝 Audit log entry created

---

## Incident Classification

### Types of Incidents

**Security Breaches:**
- Unauthorized access attempts
- Trespassing
- Tailgating (following authorized person)
- Badge violations
- Perimeter breaches

**Theft & Vandalism:**
- Property theft
- Vehicle theft/break-ins
- Vandalism
- Graffiti
- Equipment damage

**Safety Incidents:**
- Slips, trips, and falls
- Medical emergencies
- Fire/smoke detection
- Hazardous material spills
- Equipment malfunctions

**Behavioral Issues:**
- Disorderly conduct
- Verbal altercations
- Physical altercations
- Harassment
- Domestic disturbances
- Suspicious activity

**Access Control:**
- Lost/stolen badges
- Unauthorized entry attempts
- Door propped open violations
- Alarm activations
- Lock/key issues

**Emergency Events:**
- Fire
- Natural disasters
- Building evacuations
- Bomb threats
- Active shooter situations
- Medical emergencies

**Other:**
- Noise complaints
- Parking violations
- Lost and found
- Utility failures
- Weather-related issues

---

## Adding Evidence and Photos

### Mobile App Quick Photo Capture

**From Shift Screen:**

**Step 1:** While on shift, tap **"Report Incident"**

**Step 2:** Fill basic details

**Step 3:** Tap **"Add Photo"**

**Step 4:** Choose:
- **"Take Photo"** - Use camera now
- **"Choose from Gallery"** - Select existing photo

**Step 5:** Tap camera button, take photo

**Step 6:** Add caption, tap **"Use Photo"**

**Step 7:** Photo automatically uploaded with GPS and timestamp

**📱 Mobile Features:**
- Photos include metadata (GPS, timestamp)
- Can take multiple photos
- Works offline (syncs when online)
- Low/high quality options (data saving)

### Adding Video Evidence

**Step 1:** In incident form, click **"Add Video"**

**Step 2:** Upload video file or provide CCTV reference:

| Field | Description |
|-------|-------------|
| **Video Source** | CCTV/Mobile/Dashcam/Other |
| **Camera ID** | Camera number (if CCTV) |
| **Start Time** | When relevant footage starts |
| **End Time** | When relevant footage ends |
| **Description** | What video shows |
| **File** | Upload (if available) |

**💾 File Size Limits:**
- Photos: 10MB per file
- Videos: 100MB per file
- Total attachments: 500MB per incident

**🔒 Evidence Security:**
- All evidence encrypted
- Audit trail of who viewed
- Can't be deleted (only archived)
- Admissible for legal proceedings

---

## Updating Incident Status

### Status Workflow

```
Reported → Investigating → In Progress → Resolved → Closed
     ↓           ↓              ↓
   Draft    Escalated      On Hold
```

### Status Meanings

| Status | Description | Who Can Set | Next Steps |
|--------|-------------|-------------|------------|
| **Draft** | Not yet submitted | Reporter only | Complete and submit |
| **Reported** | Submitted, awaiting review | Auto-set on submit | Supervisor reviews |
| **Investigating** | Under investigation | Supervisor/Manager | Gather information |
| **In Progress** | Resolution underway | Assigned person | Complete actions |
| **On Hold** | Waiting for external factor | Anyone assigned | Resume when ready |
| **Escalated** | Escalated to higher level | Supervisor/Manager | Higher authority handles |
| **Resolved** | Issue resolved | Assigned person | Review for closure |
| **Closed** | Finalized, no further action | Manager only | Archived |

### How to Update Status

**Step 1:** Open the incident report

**Step 2:** Click **"Update Status"** button

**Step 3:** Fill status update form:

| Field | Mandatory | Description |
|-------|-----------|-------------|
| **New Status** | ✅ Yes | Select next status |
| **Update Notes** | ✅ Yes | Explain status change |
| **Estimated Resolution** | ❌ No | Expected resolution date |
| **Notify Reporter** | ❌ No | Send update to original reporter |

**Step 4:** Click **"Update"**

**Example Update Notes:**
```
Status: Investigating → In Progress

Notes: Reviewed CCTV footage. Identified suspect vehicle. 
Contacted local police department (Report #2025-1234). 
Detective assigned to case. Working with building management 
to enhance entry procedures. Expected completion: 2025-11-05.
```

---

## Escalating Incidents

### When to Escalate

Escalate incidents when:
- Severity increases after initial report
- Requires management decision
- Legal implications arise
- Media attention possible
- Cannot resolve within normal timeframe
- Client specifically requests escalation
- Safety risk increases

### How to Escalate

**Method 1: From Incident Form**

**Step 1:** Open incident

**Step 2:** Click **"Escalate"** button

**Step 3:** Select escalation reason:
- Increased severity
- Management decision needed
- Legal/compliance issue
- Client request
- Resource requirements
- Other (specify)

**Step 4:** Add escalation notes

**Step 5:** Select escalation target:
- Operations Manager
- Regional Manager
- Executive Team
- Legal Department
- External (Police/Fire)

**Step 6:** Click **"Confirm Escalation"**

**What Happens:**
1. Status changes to **"Escalated"**
2. Priority automatically increased
3. Notifications sent to escalation target
4. Original assignee remains informed
5. Escalation logged in audit trail
6. Client notified (if configured)

### Automatic Escalation

**System Auto-Escalates When:**
- Critical incident not acknowledged within 5 minutes
- High severity not assigned within 30 minutes
- Medium severity not resolved within 24 hours
- Incident resolution SLA exceeded
- Multiple related incidents at same site

**Escalation Notifications:**
- 📧 Email to manager
- 📱 SMS alert
- 📞 Phone call (for Critical)
- 🔔 Mobile app push notification
- 📊 Dashboard alert

---

## Viewing Incident Reports

### Generating Incident Report

**Step 1:** Open incident

**Step 2:** Click **"Action"** > **"Generate Report"**

**Step 3:** Select report format:
- **PDF** - Formal report with letterhead
- **Excel** - Data export for analysis
- **Summary** - One-page overview
- **Detailed** - Complete report with evidence

**Step 4:** Click **"Generate"**

**Report Includes:**
- Incident details
- Timeline of events
- People involved
- Evidence (photos embedded)
- Actions taken
- Status updates
- Resolution details

### Client Reports

**For Client-Facing Reports:**

**Step 1:** Open incident

**Step 2:** Click **"Generate Client Report"**

**Step 3:** Review report contents

**Step 4:** Choose delivery:
- **"Download PDF"** - Save locally
- **"Email to Client"** - Send directly
- **"Add to Client Portal"** - Post online

**Client Report Features:**
- Professional formatting
- Company branding
- Sanitized internal notes
- Appropriate language
- Actionable recommendations

---

## Common Workflows

### Workflow 1: Medical Emergency

**Step 1:** Call emergency services (911/local)

**Step 2:** Provide immediate assistance

**Step 3:** While waiting for ambulance:
- Open GuardPro mobile app
- Tap **"Report Incident"**
- Select **"Medical Emergency"**
- Set severity: **Critical**
- Location: Auto-captured
- Take photo of scene (if safe)

**Step 4:** When ambulance arrives:
- Note ambulance number
- Note EMT names
- Time of arrival
- Patient condition

**Step 5:** Complete incident report:
- Detailed description
- Actions taken
- Ambulance details
- Follow-up needed

**Step 6:** Notify:
- Supervisor (auto-notified)
- Site management
- Patient's emergency contact (if known)

### Workflow 2: Property Damage

**Step 1:** Secure the area

**Step 2:** Take photographs:
- Wide shot showing context
- Close-ups of damage
- Multiple angles
- Any evidence (broken glass, etc.)

**Step 3:** Create incident report:
- Type: **"Vandalism"** or **"Property Damage"**
- Severity: Based on damage extent
- Attach all photos
- Estimate damage cost (if possible)

**Step 4:** Document:
- What was damaged
- Estimated time of damage
- How discovered
- Any witnesses
- Possible suspects

**Step 5:** Preserve evidence:
- Don't clean up yet
- Cordon off area
- Log all evidence
- Wait for supervisor approval

**Step 6:** Follow up:
- File police report (if required)
- Contact insurance
- Document repairs needed
- Update incident when repairs complete

### Workflow 3: Suspicious Activity

**Step 1:** Observe from safe distance

**Step 2:** Note details:
- Person description
- Vehicle (if any)
- Activity/behavior
- Location
- Time

**Step 3:** If safe, take discreet photos/video

**Step 4:** Contact supervisor immediately

**Step 5:** Create incident report:
- Type: **"Suspicious Activity"**
- Detailed description
- Photos attached
- Person descriptions

**Step 6:** Continue monitoring (if safe)

**Step 7:** If activity escalates:
- Update incident status
- Increase severity
- Request backup
- Call police if necessary

---

## Need More Help?

- 📘 **See also:** [Shift Management](shift_management.md)
- 📘 **See also:** [Emergency Procedures](../operations/emergency_procedures.md)
- 📘 **See also:** [Mobile App Guide](../workflows/mobile_app.md)
- 📞 **Emergency:** Always call 911/local emergency first
- 📞 **Support:** Contact your supervisor or system administrator
