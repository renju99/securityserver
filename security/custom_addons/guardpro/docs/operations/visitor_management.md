# Visitor Management

Complete guide to registering, tracking, and managing visitors in GuardPro.

---

## Table of Contents
1. [Overview](#overview)
2. [Pre-Registration vs Walk-in Visitors](#pre-registration-vs-walk-in-visitors)
3. [Registering a Walk-in Visitor](#registering-a-walk-in-visitor)
4. [Pre-Registering Expected Visitors](#pre-registering-expected-visitors)
5. [Check-in Process](#check-in-process)
6. [Check-out Process](#check-out-process)
7. [Visitor Badges](#visitor-badges)
8. [Contractor Management](#contractor-management)
9. [Visitor Reports](#visitor-reports)

---

## Overview

Visitor Management allows you to:
- Register and track all site visitors
- Issue and manage visitor badges
- Pre-register expected visitors
- Maintain visitor logs
- Track visitor check-in/check-out
- Monitor contractor access
- Generate visitor reports

---

## Pre-Registration vs Walk-in Visitors

### Pre-Registered Visitors
- **When:** Planned visits, meetings, deliveries
- **By Whom:** Host employee or admin
- **Benefits:**
  - Faster check-in (1-2 minutes)
  - Badge pre-printed
  - Host notified automatically
  - NDA/forms signed in advance

### Walk-in Visitors
- **When:** Unannounced arrivals
- **By Whom:** Security guard at entry
- **Process:**
  - Full registration required
  - Host must approve
  - Badge issued on-site
  - Takes 5-10 minutes

---

## Registering a Walk-in Visitor

### Step-by-Step Process:

#### Step 1: Open Visitor Registration

**Navigation:**
- GuardPro > Operations > Visitor Management
- Or: Press `Ctrl + K`, type "visitor"
- Click **"Register New Visitor"**

#### Step 2: Visitor Information

| Field | Mandatory | Description | Example |
|-------|-----------|-------------|---------|
| **First Name** | ✅ Yes | Visitor's first name | "John" |
| **Last Name** | ✅ Yes | Visitor's last name | "Smith" |
| **Company** | ❌ No | Visitor's organization | "ABC Delivery" |
| **Purpose of Visit** | ✅ Yes | Reason for visiting | Meeting/Delivery/Interview |
| **Host Name** | ✅ Yes | Person they're visiting | Select from employee list |
| **Phone Number** | ✅ Yes | Contact number | +1 (555) 123-4567 |
| **Email** | ❌ No | Email address | john.smith@company.com |
| **Vehicle Info** | ❌ No | If driving | License plate, make/model |

**How to Fill:**

1. **Name Entry:**
   - Use proper capitalization
   - Match ID document exactly
   - Ask visitor to spell if unclear

2. **Purpose of Visit Selection:**
   - **Meeting** - Business meeting with employee
   - **Delivery** - Delivering packages/goods
   - **Interview** - Job interview candidate
   - **Maintenance** - Repair/maintenance work
   - **Contractor** - Construction/service work
   - **Guest** - Personal guest of employee
   - **Other** - Specify in notes

3. **Host Selection:**
   - Start typing host name
   - Select from dropdown
   - System checks if host is:
     - ✅ Currently on-site
     - ❌ Out of office
     - ❌ On leave
   - If host unavailable, ask visitor to contact them

4. **Contact Information:**
   - Minimum: Phone number required
   - Email optional but recommended for:
     - Sending visitor instructions
     - Digital NDA signing
     - Follow-up communications

#### Step 3: ID Verification

| Field | Mandatory | Description |
|-------|-----------|-------------|
| **ID Type** | ✅ Yes | Type of identification |
| **ID Number** | ✅ Yes | ID document number |
| **ID Expiry Date** | ❌ No | When ID expires |
| **Photo Capture** | ✅ Yes | Visitor's photo |

**ID Types Accepted:**
- Government-issued ID
- Driver's License
- Passport
- State ID Card
- Military ID
- Work Permit

**ID Verification Steps:**

**Step A:** Ask visitor for ID

**Step B:** Verify ID:
- Check photo matches visitor
- Not expired
- Not damaged/altered
- Name matches stated name

**Step C:** Enter ID details:
- Select ID type
- Enter ID number exactly
- Note expiry (if visible)

**Step D:** Capture photo:
- Click **"Capture Photo"**
- Use webcam or mobile camera
- Ensure good lighting
- Face clearly visible
- Click when ready

**📸 Photo Requirements:**
- Face forward
- No sunglasses/hats
- Clear, well-lit
- Neutral expression
- Photo used for badge

#### Step 4: Access Authorization

| Field | Mandatory | Description |
|-------|-----------|-------------|
| **Access Level** | ✅ Yes | Where visitor can go |
| **Escort Required** | ✅ Yes | Must be accompanied |
| **Valid Until** | ✅ Yes | Access expiration |
| **Areas Allowed** | ❌ No | Specific zones |

**Access Levels:**
- **Lobby Only** - Reception area only
- **Ground Floor** - Ground floor common areas
- **Specific Floor/Area** - Named locations
- **Escorted Full Access** - Anywhere with escort
- **Contractor Access** - Work areas only

**Escort Requirements:**
- **Always Required:** Default for most visitors
- **Not Required:** Only for:
  - Regular contractors (pre-approved)
  - Frequent visitors with clearance
  - Certain delivery personnel

**Valid Until:**
- **Same Day Visit:** Set to end of business day
- **Multi-Day Contractor:** Set to project end date
- **Recurring Visitor:** Set to agreement end date

**💡 Best Practice:**
- Start with most restrictive access
- Host can request upgrade if needed
- Document any access exceptions

#### Step 5: Additional Requirements

**Section: Compliance & Safety**

| Field | Mandatory | Description |
|-------|-----------|-------------|
| **NDA Required** | Checkbox | Non-disclosure agreement |
| **Safety Briefing** | Checkbox | Safety orientation needed |
| **Background Check** | Checkbox | Check required (contractors) |
| **Special Instructions** | Text | Any special notes |

**When NDA Required:**
- Visiting restricted areas
- Access to confidential information
- Client-facing visits
- Competitor company representatives

**NDA Process:**
1. Check **"NDA Required"**
2. Print NDA form (auto-generated)
3. Have visitor read and sign
4. Scan or photograph signed NDA
5. Attach to visitor record

**Safety Briefing (5-10 minutes):**
- Emergency exits location
- Assembly point
- Emergency procedures
- Restricted areas
- Safety rules (hard hat zones, etc.)
- Check box once briefing complete

#### Step 6: Host Notification

**Automatic Actions:**
- 📧 Email sent to host: "Your visitor [Name] has arrived"
- 📱 SMS sent (if configured)
- 🔔 Mobile app notification
- 📞 Can click to call host directly

**Host Must:**
- Acknowledge visitor arrival
- Come to reception (if escort required)
- Or authorize unescorted entry (if allowed)

**Waiting for Host:**
- Ask visitor to wait in designated area
- Offer refreshments if available
- Expected wait time: 5-10 minutes
- If host doesn't respond in 15 minutes:
  - Call host's phone
  - Contact host's supervisor
  - Update visitor

#### Step 7: Issue Visitor Badge

**Badge Information:**
| Field | Auto-Filled | Description |
|-------|-------------|-------------|
| Badge Number | ✅ Yes | Unique badge ID |
| Visitor Name | ✅ Yes | From registration |
| Photo | ✅ Yes | Captured photo |
| Valid Date | ✅ Yes | Today's date |
| Host Name | ✅ Yes | Person visiting |
| Expiry Time | ✅ Yes | End of day/custom |

**Badge Issuance:**

**Step A:** Click **"Print Badge"**

**Step B:** Badge prints with:
- Visitor photo
- Name
- Company
- Host name
- Date
- Barcode (for tracking)

**Step C:** Affix badge to lanyard

**Step D:** Explain badge rules:
- Must be worn visibly at all times
- Return to reception on exit
- If lost, report immediately
- Don't share or loan

**Step E:** Hand badge to visitor

**Step F:** Click **"Badge Issued"** in system

**💡 Badge Colors (if using colored badges):**
- **Blue** - Standard visitor
- **Yellow** - Contractor
- **Red** - Requires escort
- **Green** - Multi-day access

#### Step 8: Complete Check-in

**Final Steps:**

1. **Save registration**: Click **"Save"**

2. **System records**:
   - Check-in time (automatic)
   - Guard who checked in
   - Badge issued
   - Photo captured
   - Host notified

3. **Give visitor**:
   - Badge with lanyard
   - Site map (if available)
   - WiFi access (if applicable)
   - Parking pass (if needed)

4. **Remind visitor**:
   - Where to go / wait for host
   - Check out on departure
   - Return badge
   - Parking time limits

---

## Pre-Registering Expected Visitors

### Creating Pre-Registration

**Who Can Pre-Register:**
- Employees (for their visitors)
- Receptionists
- HR department
- Security supervisors

**Step-by-Step:**

#### Step 1: Access Pre-Registration

- GuardPro > Visitor Management
- Click **"Pre-Register Visitor"**

#### Step 2: Schedule Visit

| Field | Mandatory | Description |
|-------|-----------|-------------|
| **Visitor Name** | ✅ Yes | Full name |
| **Company** | ❌ No | Organization |
| **Visit Date** | ✅ Yes | Expected arrival date |
| **Expected Time** | ✅ Yes | Approximate arrival |
| **Duration** | ❌ No | How long visit will last |
| **Host** | ✅ Yes | Person being visited |
| **Purpose** | ✅ Yes | Reason for visit |

#### Step 3: Contact & Access Details

- Phone number
- Email (for sending pre-visit instructions)
- Access level
- Escort requirements
- Special instructions

#### Step 4: Optional Pre-Checks

**Digital NDA:**
- Check **"Send NDA for e-signature"**
- Visitor receives email with DocuSign/similar
- Must sign before arrival
- System verifies signature

**Background Check (for contractors):**
- Request background check
- Set check requirements
- Check status tracked
- Must clear before access

**Parking Reservation:**
- Reserve parking spot
- Send spot number to visitor
- Block spot in parking system

#### Step 5: Send Confirmation

- Click **"Send Pre-Registration Email"**
- Visitor receives:
  - Visit confirmation
  - Date, time, location
  - Parking instructions
  - What to bring (ID, etc.)
  - COVID/health requirements (if any)
  - Map/directions

#### Step 6: Day of Visit

**When visitor arrives:**

**Step A:** Guard opens visitor registration

**Step B:** Search by name or scan confirmation code

**Step C:** Pre-filled form appears

**Step D:** Verify ID and capture photo only

**Step E:** Print badge (takes 30 seconds)

**Step F:** Check in complete

**Benefits:**
- ⚡ 2-minute check-in vs 10 minutes
- ✅ Host pre-notified
- 📋 Compliance docs pre-completed
- 🅿️ Parking pre-arranged

---

## Check-in Process

### Quick Check-in (Pre-Registered)

1. Search visitor by name
2. Verify ID
3. Capture photo
4. Print badge
5. Hand off to host

**Total Time:** ~2 minutes

### Full Check-in (Walk-in)

1. Gather visitor information
2. Verify ID
3. Capture photo
4. Enter all details
5. Contact host
6. Wait for approval
7. Print badge
8. Brief visitor on rules

**Total Time:** ~10 minutes

---

## Check-out Process

### Standard Check-out

**Step 1:** Visitor returns to reception

**Step 2:** Collect visitor badge

**Step 3:** Scan badge barcode or search by name

**Step 4:** Click **"Check Out"**

**Step 5:** System records:
- Check-out time
- Visit duration
- Badge returned
- Guard who processed

**Step 6:** Thank visitor

### Auto Check-out

**System automatically checks out:**
- At badge expiry time
- After 2 hours past expected departure
- If guard manually triggers "End of Day Checkout"

**For auto check-outs:**
- Badge marked as "Not Returned"
- Alert created
- Follow-up required
- Badge deactivated

---

## Visitor Badges

### Badge Management

**Active Badges:**
- Track all issued badges
- View in real-time who's on-site
- See badge status
- Location tracking (if system integrated)

**Lost/Stolen Badges:**

**If visitor reports lost badge:**

1. Create incident report
2. Deactivate badge in system
3. Issue replacement if needed
4. Mark original as "Lost"
5. Investigate if necessary

**Badge Not Returned:**

1. Contact visitor by phone/email
2. Request return via mail
3. After 30 days: Mark as lost
4. Add note to visitor record
5. May affect future visit approval

### Badge Inventory

**Daily Tasks:**
- Count badges at shift start/end
- Match count with system
- Report discrepancies
- Restock blank badges
- Clean/maintain badge printer

---

## Contractor Management

### Long-term Contractor Setup

**Step 1:** Create Contractor Profile

- GuardPro > Contractor Management
- Click **"New Contractor"**

| Field | Description |
|-------|-------------|
| **Company Name** | Contracting company |
| **Contact Person** | Primary contact |
| **Contract Start/End** | Project duration |
| **Site** | Work location |
| **Insurance Verified** | Proof on file |
| **Background Check** | Status |

**Step 2:** Add Individual Workers

- Click **"Add Worker"**
- Enter worker details
- Upload certifications
- Take photo
- Issue contractor badge

**Step 3:** Set Access Schedule

- Mon-Fri 7 AM - 5 PM (typical)
- Weekends (if approved)
- After hours (with authorization)
- Specific areas only

**Step 4:** Track Daily Access

- Contractors check in/out daily
- No need to issue new badge each day
- System tracks hours
- Alerts if late/no-show

---

## Visitor Reports

### Available Reports

**Daily Visitor Log:**
- All visitors for selected date
- Check-in/check-out times
- Purpose of visit
- Hosts
- Export to Excel/PDF

**Visitor Summary:**
- Total visitors per day/week/month
- Visitor trends
- Peak times
- Most frequent visitors

**Outstanding Visitors:**
- Currently on-site
- Not checked out
- Overdue check-out
- Real-time list

**Contractor Hours:**
- Hours worked
- By contractor/company
- For billing purposes
- Exportable for payroll

### Generating Reports

**Step 1:** GuardPro > Reports > Visitor Reports

**Step 2:** Select report type

**Step 3:** Set filters:
- Date range
- Site
- Visitor type
- Host
- Purpose

**Step 4:** Click **"Generate"**

**Step 5:** Choose format:
- View on screen
- Download PDF
- Export to Excel
- Email to recipients

---

## Need More Help?

- 📘 **See also:** [Access Control](access_control.md)
- 📘 **See also:** [Site Management](../sites/site_setup.md)
- 📞 **Support:** Contact your system administrator
