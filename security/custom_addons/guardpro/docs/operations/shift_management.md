# Shift Management

Complete guide to creating, assigning, and managing guard shifts in GuardPro.

---

## Table of Contents
1. [Overview](#overview)
2. [Accessing Shift Management](#accessing-shift-management)
3. [Creating a New Shift](#creating-a-new-shift)
4. [Assigning Guards to Shifts](#assigning-guards-to-shifts)
5. [Managing Shift Templates](#managing-shift-templates)
6. [Shift Swaps and Changes](#shift-swaps-and-changes)
7. [Viewing Shift Calendar](#viewing-shift-calendar)
8. [Common Issues and Solutions](#common-issues-and-solutions)

---

## Overview

Shift Management allows you to:
- Create and schedule guard shifts
- Assign guards to specific sites and time slots
- Manage shift templates for recurring schedules
- Handle shift swaps and replacements
- Monitor shift coverage and attendance

---

## Accessing Shift Management

### Navigation Steps:

**Step 1:** Log in to GuardPro
- Open your web browser
- Go to your GuardPro URL (e.g., `https://your-company.odoo.com`)
- Enter your username and password
- Click **"Log in"**

**Step 2:** Navigate to Shift Management
- Click on **"GuardPro"** in the main menu (top navigation bar)
- Click on **"Operations"** in the dropdown menu
- Select **"Guard Shifts"**

**Alternative Navigation:**
- Use the search bar (press `Ctrl + K` or `Cmd + K`)
- Type **"shifts"** and select **"Guard Shifts"**

---

## Creating a New Shift

### Step-by-Step Process:

#### Step 1: Open the Shift Creation Form

1. From the Guard Shifts list view, click the **"Create"** button (blue button at top-left)
2. A new shift form will open

#### Step 2: Fill in Basic Information

**Section: Shift Details**

| Field Name | Type | Mandatory | Description | Example |
|------------|------|-----------|-------------|---------|
| **Site** | Selection | ✅ Yes | Select the client site for this shift | "ABC Corporate HQ" |
| **Shift Date** | Date | ✅ Yes | The date this shift occurs | "2025-10-30" |
| **Start Time** | Time | ✅ Yes | Shift start time | "09:00 AM" |
| **End Time** | Time | ✅ Yes | Shift end time | "05:00 PM" |
| **Shift Type** | Selection | ✅ Yes | Type of shift | Day/Night/Swing |

**How to Fill:**
1. Click on **"Site"** dropdown
2. Start typing the site name (e.g., "ABC")
3. Select the correct site from the filtered list
4. Click on **"Shift Date"** calendar icon
5. Select the date from the calendar
6. Enter **"Start Time"** using 24-hour or 12-hour format
7. Enter **"End Time"** (must be after start time)
8. Select **"Shift Type"** from dropdown

**💡 Tips:**
- The system calculates shift duration automatically
- For overnight shifts (e.g., 10 PM to 6 AM), the end time on the next day is automatically handled
- Red asterisk (*) indicates mandatory fields

#### Step 3: Assign Guards

**Section: Guard Assignment**

| Field Name | Type | Mandatory | Description | Example |
|------------|------|-----------|-------------|---------|
| **Primary Guard** | Selection | ✅ Yes | Main guard for this shift | "John Smith" |
| **Backup Guard** | Selection | ❌ No | Standby guard in case primary is unavailable | "Jane Doe" |
| **Number of Guards Required** | Number | ✅ Yes | How many guards needed for this shift | "2" |

**How to Fill:**
1. Click on **"Primary Guard"** dropdown
2. You'll see a list of available guards
3. The list shows:
   - Guard name
   - Current status (Available/On Shift/Off Duty)
   - Skill level
   - Certifications
4. Select the appropriate guard
5. Optionally, add a backup guard
6. Set the **"Number of Guards Required"**

**Smart Filters:**
- Click **"Show Available Only"** checkbox to see only guards available for this time slot
- Click **"Filter by Site Certification"** to see guards certified for the selected site

**⚠️ Warnings:**
- If you select a guard who already has a shift at that time, you'll see: **"Warning: Guard already scheduled"**
- If guard certifications don't match site requirements: **"Warning: Missing required certifications"**

#### Step 4: Define Shift Responsibilities

**Section: Tasks and Checkpoints**

| Field Name | Type | Mandatory | Description |
|------------|------|-----------|-------------|
| **Assigned Tasks** | Multi-select | ❌ No | Specific tasks for this shift |
| **Patrol Route** | Selection | ❌ No | Predefined patrol route |
| **Checkpoints** | Multi-select | ❌ No | Checkpoints to monitor |
| **Special Instructions** | Text | ❌ No | Additional instructions |

**How to Fill:**
1. Click **"Add a line"** under **"Assigned Tasks"**
2. Select from common tasks:
   - Access Control Monitoring
   - Patrol Rounds
   - Visitor Management
   - Incident Response
   - Equipment Inspection
3. For **"Patrol Route"**, select a predefined route or create new
4. Add relevant checkpoints from the list
5. Enter any special instructions in the text box

**Example Special Instructions:**
```
- Check fire alarm panel every 2 hours
- Report any suspicious vehicles in parking lot
- Main entrance code changes at midnight (code will be sent via SMS)
- Contact supervisor if temperature drops below 15°C
```

#### Step 5: Set Notifications and Reminders

**Section: Notifications**

| Field Name | Type | Mandatory | Description | Default |
|------------|------|-----------|-------------|---------|
| **Send Shift Reminder** | Checkbox | ❌ No | Send reminder to guard | ✅ Checked |
| **Reminder Time** | Selection | ❌ No | When to send reminder | 2 hours before |
| **Notify Supervisor** | Checkbox | ❌ No | Notify supervisor when shift starts | ❌ Unchecked |
| **Notify Client** | Checkbox | ❌ No | Notify client contact | ❌ Unchecked |

**How to Configure:**
1. Leave **"Send Shift Reminder"** checked (recommended)
2. Adjust **"Reminder Time"** if needed (options: 30 min, 1 hour, 2 hours, 4 hours, 24 hours before)
3. Check **"Notify Supervisor"** for high-priority shifts
4. Check **"Notify Client"** if client requested updates

#### Step 6: Review and Save

**Before Saving - Review Checklist:**

✅ Site selected and correct  
✅ Date and times are accurate  
✅ Primary guard assigned  
✅ Shift type is correct  
✅ Tasks and responsibilities defined  
✅ Special instructions added (if any)  

**Save Options:**

1. **"Save"** - Saves the shift and stays on the form
2. **"Save & New"** - Saves and opens a new shift form (useful for creating multiple shifts)
3. **"Save & Close"** - Saves and returns to the shift list
4. **"Discard"** - Cancels and doesn't save changes

**What Happens After Saving:**

1. ✅ Shift is created with status **"Scheduled"**
2. 📧 Automatic email sent to primary guard with shift details
3. 📱 SMS reminder scheduled (if enabled)
4. 📅 Shift appears on shift calendar
5. 🔔 Guard receives notification in mobile app
6. ⏰ System schedules automatic check-in reminder

---

## Assigning Guards to Shifts

### Using the Quick Assignment Wizard

If you need to assign multiple guards or fill multiple shifts quickly:

**Step 1:** Go to Guard Shifts list view

**Step 2:** Click **"Action"** dropdown (top menu)

**Step 3:** Select **"Bulk Assign Guards"**

**Step 4:** The Assignment Wizard opens:

| Field | Description |
|-------|-------------|
| **Date Range** | Select start and end dates for assignments |
| **Site** | Filter shifts by site |
| **Unassigned Only** | Show only shifts without guards |
| **Auto-Assign** | Let system assign based on availability and skills |

**Step 5:** Review proposed assignments

**Step 6:** Click **"Apply Assignments"**

---

## Managing Shift Templates

### What are Shift Templates?

Shift Templates are predefined shift configurations for recurring schedules (e.g., Monday-Friday 9-5 shift at Site A).

### Creating a Shift Template

**Step 1:** Navigate to **GuardPro > Configuration > Shift Templates**

**Step 2:** Click **"Create"**

**Step 3:** Fill in Template Information:

| Field | Mandatory | Description |
|-------|-----------|-------------|
| **Template Name** | ✅ Yes | Descriptive name (e.g., "Weekday Morning - Site A") |
| **Site** | ✅ Yes | Default site for this template |
| **Start Time** | ✅ Yes | Default start time |
| **End Time** | ✅ Yes | Default end time |
| **Shift Type** | ✅ Yes | Day/Night/Swing |
| **Days of Week** | ✅ Yes | Which days this template applies |
| **Number of Guards** | ✅ Yes | Default number of guards needed |
| **Default Tasks** | ❌ No | Standard tasks for this shift type |

**Step 4:** Click **"Save"**

### Using Templates to Create Shifts

**Step 1:** From Guard Shifts, click **"Create from Template"**

**Step 2:** Select your template

**Step 3:** Choose date range (e.g., "Next 30 days")

**Step 4:** Click **"Generate Shifts"**

**Result:** System creates all shifts based on template for the specified period

---

## Shift Swaps and Changes

### How Guards Request Shift Swaps

**Guard's Mobile App Process:**

1. Guard opens shift in mobile app
2. Taps **"Request Swap"**
3. Selects replacement guard or leaves open for volunteers
4. Adds reason for swap
5. Submits request

### Approving Shift Swaps (Manager)

**Step 1:** You'll receive notification: **"Shift swap request pending"**

**Step 2:** Navigate to **GuardPro > Operations > Shift Swaps**

**Step 3:** Open the swap request

**Step 4:** Review:
- Original guard's reason
- Replacement guard's qualifications
- Site certification status
- Both guards' recent performance ratings

**Step 5:** Decision Options:

**Approve:**
1. Click **"Approve Swap"** button
2. Both guards receive confirmation
3. Shift assignment automatically updates
4. Calendar reflects the change

**Reject:**
1. Click **"Reject"**
2. Enter rejection reason
3. Original guard receives notification
4. Original assignment remains

**Request Changes:**
1. Click **"Request Modification"**
2. Add comments (e.g., "Need supervisor approval first")
3. Guard can resubmit with modifications

---

## Viewing Shift Calendar

### Calendar View Navigation

**Step 1:** From Guard Shifts, click **"Calendar"** button (top right)

**Step 2:** Calendar View Options:

**View Types:**
- **Day** - Shows all shifts for one day
- **Week** - Shows 7-day week view
- **Month** - Shows full month overview

**Color Coding:**
- 🟢 **Green** - Fully staffed shifts
- 🟡 **Yellow** - Partially staffed (need more guards)
- 🔴 **Red** - Unstaffed shifts (urgent)
- 🔵 **Blue** - Completed shifts
- ⚪ **Gray** - Cancelled shifts

### Filtering Calendar

**Filter Options:**
- **By Site** - Show only specific site's shifts
- **By Guard** - Show shifts for specific guard
- **By Status** - Show only scheduled/in-progress/completed
- **By Shift Type** - Filter by day/night/swing shifts

**How to Apply Filters:**
1. Click **"Filters"** button
2. Select filter criteria
3. Click **"Apply"**
4. Clear filters by clicking **"Clear All"**

---

## Common Issues and Solutions

### Issue 1: Cannot Assign Guard to Shift

**Error Message:** "Guard not available for this time slot"

**Solutions:**
1. **Check Guard's Schedule**
   - Go to guard's profile
   - Click **"Schedule"** tab
   - Look for conflicting shifts
2. **Check Guard's Availability**
   - Guard might have marked time as unavailable
   - Go to **Guard Profile > Availability**
   - Adjust if needed
3. **Check Guard's Status**
   - Guard must be "Active" status
   - Go to **Guard Profile > General tab**
   - Verify **"Status"** field is "Active"

### Issue 2: Shift Reminder Not Sent

**Possible Causes:**
1. Guard's email/phone number not configured
   - **Solution:** Update guard's contact information in profile
2. Notification settings disabled
   - **Solution:** Go to **GuardPro > Configuration > Settings**
   - Enable **"Shift Reminders"**
3. Guard's notification preferences set to "None"
   - **Solution:** Guard updates preferences in mobile app or portal

### Issue 3: Cannot Delete a Shift

**Error Message:** "Cannot delete shift: Guard has checked in"

**Solution:**
- Shifts with attendance records cannot be deleted
- Instead, **"Cancel"** the shift:
  1. Open the shift
  2. Click **"Cancel Shift"** button
  3. Enter cancellation reason
  4. System marks shift as cancelled but preserves records

### Issue 4: Shift Times Showing Incorrectly

**Cause:** Timezone mismatch

**Solution:**
1. Go to **Settings > Users**
2. Open your user profile
3. Set correct **"Timezone"**
4. Refresh page
5. Times will display in your local timezone

---

## Best Practices

### ✅ Shift Scheduling Best Practices

1. **Schedule in Advance**
   - Create shifts at least 7 days in advance
   - Gives guards time to plan
   - Reduces last-minute issues

2. **Use Shift Templates**
   - Create templates for recurring schedules
   - Saves time and reduces errors
   - Ensures consistency

3. **Always Assign Backup Guards**
   - Helps cover unexpected absences
   - Reduces emergency situations
   - Improves coverage reliability

4. **Add Clear Special Instructions**
   - Include site-specific procedures
   - Note emergency contacts
   - Mention any special requirements

5. **Monitor Coverage**
   - Check calendar daily for unstaffed shifts
   - Address gaps immediately
   - Keep backup guard list updated

### ✅ Communication Best Practices

1. **Enable Shift Reminders**
   - Reduces no-shows
   - Guards appreciate the reminders
   - Recommended: 2 hours before shift

2. **Use Comments Feature**
   - Add shift notes for context
   - Guards can see and respond
   - Helps continuity between shifts

3. **Regular Status Updates**
   - Check shift status during the day
   - Address issues promptly
   - Maintain communication with guards on duty

---

## Quick Reference Commands

### Keyboard Shortcuts
- `Ctrl + K` / `Cmd + K` - Quick search
- `Alt + C` - Create new shift
- `Alt + S` - Save shift
- `F5` - Refresh shift list

### Status Meanings
- **Scheduled** - Shift created, waiting for start time
- **In Progress** - Guard has checked in, shift active
- **Completed** - Shift ended, guard checked out
- **Cancelled** - Shift cancelled, not counted in reports
- **No Show** - Guard didn't check in, requires follow-up

---

## Need More Help?

- 📘 **See also:** [Guard Profile Management](../guards/profile_management.md)
- 📘 **See also:** [Attendance Tracking](../guards/attendance.md)
- 📘 **See also:** [Site Management](../sites/site_setup.md)
- 📞 **Support:** Contact your system administrator
- 🎥 **Video Tutorials:** Available in GuardPro Help Center
