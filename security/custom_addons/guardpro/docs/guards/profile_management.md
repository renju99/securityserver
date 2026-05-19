# Guard Profile Management

Complete guide to creating and managing security guard profiles in GuardLink.

---

## Table of Contents
1. [Overview](#overview)
2. [Accessing Guard Profiles](#accessing-guard-profiles)
3. [Creating a New Guard Profile](#creating-a-new-guard-profile)
4. [Managing Guard Information](#managing-guard-information)
5. [Certifications and Training](#certifications-and-training)
6. [Guard Documents](#guard-documents)
7. [Setting Guard Availability](#setting-guard-availability)
8. [Common Tasks](#common-tasks)

---

## Overview

Guard Profile Management allows you to:
- Create and maintain guard personnel records
- Track certifications, licenses, and training
- Manage guard documents and credentials
- Set guard availability and preferences
- Monitor guard performance metrics
- Handle onboarding and offboarding

---

## Accessing Guard Profiles

### Navigation Steps:

**Step 1:** From GuardLink Main Menu
- Click **"GuardLink"** in the top navigation
- Select **"Guards"**
- Click **"Guard Profiles"**

**Alternative:** Use Quick Search
- Press `Ctrl + K` (or `Cmd + K` on Mac)
- Type **"guard profiles"**
- Press Enter

**You'll See:** List view showing all guards with:
- Photo
- Name
- Employee ID
- Status (Active/Inactive/On Leave)
- Current shift (if on duty)
- Performance rating

---

## Creating a New Guard Profile

### Step-by-Step Process:

#### Step 1: Open Creation Form

1. Click **"Create"** button (top-left, blue button)
2. New guard profile form opens

#### Step 2: Personal Information

**Section: Basic Information**

| Field Name | Type | Mandatory | Description | Example |
|------------|------|-----------|-------------|---------|
| **First Name** | Text | ✅ Yes | Guard's first name | "John" |
| **Last Name** | Text | ✅ Yes | Guard's last name | "Smith" |
| **Employee ID** | Text | ✅ Yes | Unique identification number | "GRD-2025-001" |
| **Date of Birth** | Date | ✅ Yes | Birth date (for age verification) | "1990-05-15" |
| **Gender** | Selection | ❌ No | Gender identification | Male/Female/Other |
| **Photo** | Image | ✅ Yes | Guard's photograph | Upload JPG/PNG |

**How to Fill:**

1. **First Name & Last Name:**
   - Type the guard's full legal name
   - Use proper capitalization
   - Example: "John" not "john" or "JOHN"

2. **Employee ID:**
   - System can auto-generate if you leave blank
   - Format: GRD-YYYY-NNN (e.g., GRD-2025-001)
   - Or use your company's format
   - Must be unique

3. **Date of Birth:**
   - Click calendar icon
   - Select date
   - **Important:** Guard must be 18+ years old
   - System will show error if under 18

4. **Photo Upload:**
   - Click **"Upload"** button
   - Select recent, clear photo
   - **Requirements:**
     - Face clearly visible
     - Professional appearance
     - JPG or PNG format
     - Max size: 5MB
     - Recommended: 400x400 pixels minimum

**💡 Tip:** Photo is used for ID card generation and mobile app profile

#### Step 3: Contact Information

**Section: Contact Details**

| Field Name | Type | Mandatory | Description | Format |
|------------|------|-----------|-------------|--------|
| **Mobile Phone** | Phone | ✅ Yes | Primary contact number | +1 (555) 123-4567 |
| **Email** | Email | ✅ Yes | Work email address | john.smith@company.com |
| **Alternative Phone** | Phone | ❌ No | Secondary contact | +1 (555) 987-6543 |
| **Emergency Contact** | Text | ✅ Yes | Emergency contact person | "Jane Smith (Wife)" |
| **Emergency Phone** | Phone | ✅ Yes | Emergency contact number | +1 (555) 111-2222 |

**How to Fill:**

1. **Mobile Phone:**
   - Enter primary contact number
   - Include country code (e.g., +1 for US)
   - **Important:** This number is used for:
     - SMS shift reminders
     - Emergency alerts
     - Mobile app verification
   - Format: System auto-formats as you type

2. **Email:**
   - Enter active email address
   - Guard will receive:
     - Shift schedules
     - System notifications
     - Portal access link
   - **Note:** Email must be unique (one per guard)

3. **Emergency Contact:**
   - Enter name and relationship
   - Format: "Name (Relationship)"
   - Example: "Sarah Johnson (Mother)"

**✅ Validation:**
- Mobile phone: System verifies format
- Email: System checks if already in use
- Emergency phone: Must be different from guard's phone

#### Step 4: Address Information

**Section: Residential Address**

| Field Name | Type | Mandatory | Description |
|------------|------|-----------|-------------|
| **Street Address** | Text | ✅ Yes | House/apartment number and street |
| **City** | Text | ✅ Yes | City name |
| **State/Province** | Text | ✅ Yes | State or province |
| **ZIP/Postal Code** | Text | ✅ Yes | Postal code |
| **Country** | Selection | ✅ Yes | Country |

**How to Fill:**
1. Enter complete address
2. System uses address for:
   - Shift distance calculations
   - Tax documentation
   - Official correspondence

#### Step 5: Employment Information

**Section: Employment Details**

| Field Name | Type | Mandatory | Description | Example |
|------------|------|-----------|-------------|---------|
| **Hire Date** | Date | ✅ Yes | Employment start date | "2025-01-15" |
| **Employment Status** | Selection | ✅ Yes | Current employment status | Full-time/Part-time/Contract |
| **Employment Type** | Selection | ✅ Yes | Guard type | Armed/Unarmed/Supervisor |
| **Department** | Selection | ❌ No | Assigned department | Operations/Mobile Patrol |
| **Supervisor** | Selection | ❌ No | Direct supervisor | Select from user list |
| **Hourly Rate** | Decimal | ✅ Yes | Pay rate per hour | 18.50 |

**How to Fill:**

1. **Hire Date:**
   - Select actual start date
   - Used for:
     - Seniority calculations
     - Benefits eligibility
     - Performance review scheduling

2. **Employment Status Options:**
   - **Full-time:** 40+ hours/week, benefits eligible
   - **Part-time:** Less than 40 hours/week
   - **Contract:** Fixed-term contractor
   - **Temporary:** Short-term assignment

3. **Employment Type Options:**
   - **Unarmed Guard:** Standard security officer
   - **Armed Guard:** Authorized to carry weapon (requires special certifications)
   - **Supervisor:** Team lead or shift supervisor
   - **Mobile Patrol:** Vehicle-based patrol officer

4. **Hourly Rate:**
   - Enter base hourly rate
   - System uses for:
     - Shift cost calculations
     - Payroll integration
     - Client billing

**🔒 Security Note:** Only managers with "Payroll Access" can view/edit hourly rate

#### Step 6: Skills and Certifications

**Section: Qualifications**

| Field Name | Type | Mandatory | Description |
|------------|------|-----------|-------------|
| **Certifications** | Multi-select | ✅ Yes (at least 1) | Valid certifications held |
| **Languages** | Multi-select | ❌ No | Languages spoken |
| **Special Skills** | Multi-select | ❌ No | Additional relevant skills |
| **Driving License** | Selection | ❌ No | Valid driver's license type |
| **License Number** | Text | ❌ No | Driver's license number |
| **License Expiry** | Date | ❌ No | License expiration date |

**How to Fill Certifications:**

**Step A:** Click **"Add Certification"** button

**Step B:** Fill certification details:

| Sub-field | Description |
|-----------|-------------|
| **Certification Type** | Select from list (e.g., Security Guard License, First Aid, CPR) |
| **Certificate Number** | Official certificate/license number |
| **Issue Date** | When certification was obtained |
| **Expiry Date** | When certification expires |
| **Issuing Authority** | Organization that issued certification |
| **Document** | Upload scanned copy of certificate |

**Step C:** Click **"Add"**

**Step D:** Repeat for all certifications

**Common Certifications:**
- ✅ Security Guard License (Usually mandatory)
- ⚕️ First Aid & CPR
- 🚔 Weapons Permit (for armed guards)
- 🔥 Fire Safety Training
- 🏥 AED Certification
- 🚗 Defensive Driving
- 📡 CCTV Operations

**⚠️ Important:**
- System tracks expiry dates
- Sends automatic renewal reminders 30 days before expiry
- Expired certifications shown in RED
- Cannot assign guards to shifts requiring expired certifications

#### Step 7: Background Check Information

**Section: Background Verification**

| Field Name | Type | Mandatory | Description |
|------------|------|-----------|-------------|
| **Background Check Status** | Selection | ✅ Yes | Verification status | Pending/Approved/Failed |
| **Background Check Date** | Date | ❌ No | When background check was completed |
| **Background Check Expiry** | Date | ❌ No | When recheck is required |
| **Drug Test Status** | Selection | ✅ Yes | Drug screening status | Pending/Pass/Fail |
| **Drug Test Date** | Date | ❌ No | Date of last drug test |
| **Next Drug Test Due** | Date | ❌ No | When next test is required |

**Status Options:**

**Background Check:**
- **Pending:** Check in progress, guard cannot be activated
- **Approved:** Passed, guard can work
- **Failed:** Did not pass, guard cannot be activated
- **Expired:** Needs renewal

**Drug Test:**
- **Pending:** Test not completed
- **Pass:** Passed drug screening
- **Fail:** Failed screening

**Process:**
1. Select **"Pending"** when first creating profile
2. Update to **"Approved"/"Pass"** once results received
3. Upload verification documents in **"Documents"** tab

#### Step 8: Review and Save

**Pre-Save Checklist:**

✅ All mandatory fields filled  
✅ Photo uploaded  
✅ Contact information verified  
✅ At least one certification added  
✅ Employment details complete  
✅ Background check status set  

**Save Options:**

1. **"Save"** - Save and stay on form
2. **"Save & Close"** - Save and return to list
3. **"Save & New"** - Save and create another guard

**What Happens Next:**

1. ✅ Profile created with status **"Inactive"** (until background checks complete)
2. 📧 Welcome email sent to guard's email with:
   - Portal access link
   - Username (their email)
   - Temporary password
3. 📱 SMS sent with mobile app download link
4. 📋 Tasks created in your task list:
   - Complete onboarding checklist
   - Schedule orientation
   - Issue uniform and equipment

---

## Managing Guard Information

### Activating a Guard

Once background checks are complete:

**Step 1:** Open guard profile

**Step 2:** Go to **"General"** tab

**Step 3:** Change **"Status"** field:
- From: **"Inactive"**
- To: **"Active"**

**Step 4:** Click **"Save"**

**What This Does:**
- Guard now visible in shift assignment dropdowns
- Guard can log into mobile app
- Guard receives activation notification
- Guard appears in available guards list

### Putting Guard on Leave

**Step 1:** Open guard profile

**Step 2:** Click **"Set On Leave"** button

**Step 3:** Fill leave details:
- **Leave Type:** Vacation/Sick/Personal/Maternity
- **Start Date:** When leave begins
- **End Date:** When guard returns
- **Reason:** Optional note

**Step 4:** Click **"Confirm"**

**Result:**
- Status changes to **"On Leave"**
- Guard removed from available guards list
- Existing shifts show **"Guard on Leave"** alert
- System suggests finding replacements

### Deactivating a Guard

When guard leaves company:

**Step 1:** Open guard profile

**Step 2:** Click **"Action"** > **"Deactivate"**

**Step 3:** Select reason:
- Resigned
- Terminated
- Retired
- Contract Ended

**Step 4:** Enter **"Last Working Day"**

**Step 5:** Click **"Confirm Deactivation"**

**Important Actions Before Deactivating:**
- ✅ Remove from all future shifts
- ✅ Collect all company property
- ✅ Complete exit interview
- ✅ Archive important documents
- ✅ Disable system access

---

## Certifications and Training

### Adding a New Certification

**Step 1:** Open guard profile

**Step 2:** Click **"Certifications"** tab

**Step 3:** Click **"Add Certification"**

**Step 4:** Fill details as described in Section "Step 6" above

**Step 5:** Upload certificate document

**Step 6:** Click **"Save"**

### Renewing Expiring Certifications

**System Alerts:**
- 🔔 30 days before expiry: **"Certification expiring soon"**
- 🔴 On expiry date: **"Certification expired"** (RED alert)
- ⛔ After expiry: Guard cannot be assigned to shifts requiring this certification

**Renewal Process:**

**Step 1:** Guard completes renewal training

**Step 2:** Update certification in profile:
- Open certification record
- Update **"Issue Date"** to new date
- Update **"Expiry Date"** to new expiry
- Update **"Certificate Number"** if changed
- Upload new certificate document

**Step 3:** Click **"Save"**

**Step 4:** System automatically:
- Clears expiry alerts
- Re-enables guard for relevant shifts
- Sends confirmation to guard

---

## Guard Documents

### Document Types

**Required Documents:**
- 📄 Government-issued ID
- 📄 Security Guard License
- 📄 Background Check Report
- 📄 Drug Test Results
- 📄 W-4 Tax Form (US) or equivalent

**Optional Documents:**
- 📄 Resume/CV
- 📄 References
- 📄 Vaccination Records
- 📄 Training Certificates
- 📄 Performance Reviews

### Uploading Documents

**Step 1:** Open guard profile

**Step 2:** Click **"Documents"** tab

**Step 3:** Click **"Upload Document"**

**Step 4:** Fill details:

| Field | Description |
|-------|-------------|
| **Document Type** | Select category |
| **Document Name** | Descriptive name |
| **Description** | Optional notes |
| **File** | Click to upload |
| **Expiry Date** | If document expires |

**Step 5:** Click **"Upload"**

**💡 Best Practices:**
- Use clear, descriptive names: "John_Smith_Guard_License_2025.pdf"
- Upload PDF format for important documents
- Add expiry dates to track renewals
- Regular review documents quarterly

---

## Setting Guard Availability

### Configuring Weekly Availability

**Step 1:** Open guard profile

**Step 2:** Click **"Availability"** tab

**Step 3:** You'll see weekly schedule grid:

```
        | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
Morning | ✅  | ✅  | ✅  | ✅  | ✅  | ❌  | ❌  |
Day     | ✅  | ✅  | ✅  | ✅  | ✅  | ❌  | ❌  |
Evening | ✅  | ✅  | ✅  | ✅  | ✅  | ❌  | ❌  |
Night   | ❌  | ❌  | ❌  | ❌  | ❌  | ❌  | ❌  |
```

**Step 4:** Click checkboxes to set availability

**Step 5:** Click **"Save Availability"**

### Setting Time-Off

**Step 1:** In **"Availability"** tab, click **"Add Time Off"**

**Step 2:** Enter:
- **Start Date:** First day off
- **End Date:** Last day off
- **Reason:** Optional
- **Type:** Vacation/Personal/Other

**Step 3:** Click **"Save"**

**Result:**
- Guard shows as **"Not Available"** for this period
- Cannot be assigned to shifts during time-off
- Appears on team calendar

---

## Common Tasks

### Task 1: Generate Guard ID Card

**Step 1:** Open guard profile

**Step 2:** Click **"Action"** > **"Generate ID Card"**

**Step 3:** Review ID card preview

**Step 4:** Click **"Print"** or **"Download PDF"**

**ID Card Includes:**
- Guard photo
- Name and Employee ID
- Company logo
- QR code (for mobile verification)
- Emergency contact number
- Expiry date

### Task 2: View Guard Performance

**Step 1:** Open guard profile

**Step 2:** Click **"Performance"** tab

**You'll See:**
- Overall performance rating (1-5 stars)
- Attendance rate (%)
- On-time rate (%)
- Incident reports filed
- Commendations received
- Warnings/disciplinary actions
- Client feedback scores

### Task 3: View Guard Shift History

**Step 1:** Open guard profile

**Step 2:** Click **"Shifts"** tab

**You'll See:**
- List of all past and future shifts
- Total hours worked this month
- Shift completion rate
- Filter by date range

### Task 4: Send Message to Guard

**Step 1:** Open guard profile

**Step 2:** Click **"Send Message"** button

**Step 3:** Compose message

**Step 4:** Choose delivery method:
- Email only
- SMS only
- Both Email and SMS
- Mobile app notification

**Step 5:** Click **"Send"**

---

## Need More Help?

- 📘 **See also:** [Shift Management](../operations/shift_management.md)
- 📘 **See also:** [Attendance Tracking](attendance.md)
- 📘 **See also:** [Training & Certifications](training.md)
- 📞 **Support:** Contact your system administrator

