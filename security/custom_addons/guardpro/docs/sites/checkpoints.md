# Checkpoint Management

Complete guide to setting up and managing patrol checkpoints in GuardPro.

---

## Table of Contents
1. [Overview](#overview)
2. [Creating Checkpoints](#creating-checkpoints)
3. [QR Code & NFC Tag Setup](#qr-code--nfc-tag-setup)
4. [Checkpoint Schedules](#checkpoint-schedules)
5. [Scanning Checkpoints](#scanning-checkpoints)
6. [Viewing Checkpoint History](#viewing-checkpoint-history)
7. [Checkpoint Reports](#checkpoint-reports)

---

## Overview

Checkpoint Management allows you to:
- Create patrol checkpoint locations
- Assign QR codes or NFC tags
- Set expected scan frequencies
- Track checkpoint compliance
- Monitor patrol routes
- Generate checkpoint reports

**Benefits:**
- Proof of guard presence
- Accountability tracking
- Patrol route verification
- Compliance monitoring
- Client reporting

---

## Creating Checkpoints

### Step-by-Step Process:

#### Step 1: Navigate to Checkpoints

**Navigation:**
- GuardPro > Site Management > Checkpoints
- Or: Press `Ctrl + K`, type "checkpoints"

#### Step 2: Create New Checkpoint

Click **"Create"** button

#### Step 3: Basic Information

| Field | Mandatory | Description | Example |
|-------|-----------|-------------|---------|
| **Checkpoint Name** | ✅ Yes | Descriptive name | "Main Entrance Checkpoint" |
| **Checkpoint ID** | ✅ Yes | Unique identifier | "CHK-001" |
| **Site** | ✅ Yes | Location site | "ABC Corporate HQ" |
| **Building/Area** | ❌ No | Specific building | "Building A" |
| **Floor** | ❌ No | Floor level | "Ground Floor" |
| **Location Description** | ✅ Yes | Detailed location | "Near security desk" |

**How to Fill:**

1. **Checkpoint Name:**
   - Use clear, recognizable names
   - Include location reference
   - Examples:
     - "Main Entrance - North Door"
     - "Parking Lot B - Northwest Corner"
     - "Rooftop Access Point"

2. **Checkpoint ID:**
   - System can auto-generate
   - Or use your numbering system
   - Format: CHK-XXX or site-specific
   - Must be unique across all sites

3. **Location Description:**
   - Be very specific
   - Include landmarks
   - Example: "Located next to the fire alarm panel, 10 feet from the main security desk, under emergency exit sign"

#### Step 4: Checkpoint Type

| Field | Mandatory | Description |
|-------|-----------|-------------|
| **Checkpoint Type** | ✅ Yes | Type of checkpoint |
| **Scan Method** | ✅ Yes | How guards scan |
| **GPS Verification** | ❌ No | Require GPS match |
| **Photo Required** | ❌ No | Require photo proof |

**Checkpoint Types:**
- **Routine Patrol** - Regular patrol points
- **Critical Asset** - High-value areas
- **Emergency Exit** - Fire exit checks
- **Equipment Check** - Equipment inspection
- **Perimeter** - Building perimeter
- **Entrance/Exit** - Access points
- **Restricted Area** - Limited access zones

**Scan Methods:**
- **QR Code** - Scan QR code sticker
- **NFC Tag** - Tap NFC tag
- **GPS Location** - GPS coordinates only
- **Manual Entry** - Enter checkpoint ID

#### Step 5: Scan Requirements

| Field | Mandatory | Description |
|-------|-----------|-------------|
| **Scan Frequency** | ✅ Yes | How often to scan |
| **Time Window** | ❌ No | Acceptable scan time range |
| **Minimum Scans Per Shift** | ❌ No | Required scans |
| **Order Required** | ❌ No | Must scan in sequence |

**Scan Frequency Options:**
- **Every 15 minutes**
- **Every 30 minutes**
- **Every hour**
- **Every 2 hours**
- **Once per shift**
- **Twice per shift**
- **Custom** (specify)

**Example Configuration:**
```
Checkpoint: "Server Room Entrance"
Type: Critical Asset
Scan Frequency: Every 2 hours
Minimum Scans: 4 per 8-hour shift
Photo Required: Yes
GPS Verification: Yes
Order Required: No
```

#### Step 6: GPS Location (Optional but Recommended)

| Field | Description |
|-------|-------------|
| **Latitude** | GPS latitude coordinate |
| **Longitude** | GPS longitude coordinate |
| **GPS Accuracy Radius** | Allowed distance variance (meters) |

**How to Set GPS:**

**Method 1: Mobile App (Recommended)**
1. Guard goes to physical location
2. Opens GuardPro mobile app
3. App captures GPS automatically
4. Saves to checkpoint

**Method 2: Manual Entry**
1. Use Google Maps to find location
2. Right-click on exact spot
3. Copy coordinates
4. Paste into checkpoint form

**Method 3: Map Picker**
1. Click **"Pick from Map"** button
2. System shows site map
3. Click on checkpoint location
4. Coordinates captured

**GPS Accuracy Radius:**
- **5 meters** - Very precise (indoor)
- **10 meters** - Standard (building)
- **25 meters** - Flexible (outdoor)
- **50 meters** - Very flexible (large areas)

#### Step 7: Instructions and Notes

| Field | Mandatory | Description |
|-------|-----------|-------------|
| **Guard Instructions** | ❌ No | What guard should check |
| **Special Requirements** | ❌ No | Any special actions needed |
| **Safety Notes** | ❌ No | Safety considerations |
| **Access Requirements** | ❌ No | Keys/codes needed |

**Example Instructions:**
```
Guard Instructions:
- Check all doors are locked
- Verify alarm panel shows "Armed"
- Look for any signs of tampering
- Ensure emergency lights are functioning
- Report any unusual sounds or smells

Special Requirements:
- Access code: 1234# (changes monthly)
- Use north stairwell only
- Wear hard hat in this area

Safety Notes:
- Watch for wet floor during cleaning hours (6-7 PM)
- Heavy machinery operating nearby
- Poor lighting - use flashlight
```

#### Step 8: Save and Generate Code

**Click "Save"**

**System Actions:**
1. ✅ Checkpoint created
2. 🔢 Unique QR code generated automatically
3. 📍 GPS coordinates saved (if provided)
4. 🔔 Ready for deployment

---

## QR Code & NFC Tag Setup

### QR Code Generation

**Automatic Generation:**
- QR code created when checkpoint is saved
- Contains encrypted checkpoint ID
- Unique to each checkpoint
- Cannot be duplicated

**Downloading QR Code:**

**Step 1:** Open checkpoint record

**Step 2:** Click **"Download QR Code"** button

**Step 3:** Choose format:
- **PDF** - For printing (recommended)
- **PNG** - High resolution image
- **SVG** - Vector format (scalable)

**Step 4:** Select size:
- **Small** - 2x2 inches
- **Medium** - 4x4 inches (recommended)
- **Large** - 6x6 inches

**Step 5:** Click **"Download"**

### Printing QR Codes

**Best Practices:**

1. **Use Durable Material:**
   - Laminated paper
   - Plastic stickers
   - Metal tags
   - Weather-resistant labels

2. **Size Guidelines:**
   - Minimum: 2x2 inches
   - Recommended: 4x4 inches
   - For distant scanning: 6x6 inches

3. **Placement:**
   - Eye-level height (5-6 feet)
   - Well-lit area
   - Protected from weather
   - Easy guard access
   - Not obstructed

4. **Protection:**
   - Use plastic sleeve
   - Laminate thoroughly
   - Consider weatherproof housing
   - Regular inspection for damage

### NFC Tag Setup

**NFC Tag Requirements:**
- **Type:** NTAG213/215/216
- **Memory:** Minimum 144 bytes
- **Frequency:** 13.56 MHz
- **Format:** NFC Forum Type 2

**Programming NFC Tags:**

**Step 1:** Order blank NFC tags

**Step 2:** Download GuardPro NFC Writer app

**Step 3:** Open checkpoint in system

**Step 4:** Click **"Program NFC Tag"**

**Step 5:** Hold NFC tag to phone

**Step 6:** App writes checkpoint data

**Step 7:** Test scan to verify

**NFC Tag Placement:**
- Same location as QR code
- Mount on flat surface
- Away from metal interference
- Test scan range
- Mark with small indicator sticker

**💡 Tip:** Use both QR and NFC for redundancy

---

## Checkpoint Schedules

### Creating Checkpoint Patrol Routes

**Step 1:** GuardPro > Patrol Routes

**Step 2:** Click **"Create Route"**

**Step 3:** Add checkpoints to route:

| Field | Description |
|-------|-------------|
| **Route Name** | "Building A Evening Patrol" |
| **Checkpoints** | Select multiple checkpoints |
| **Sequence** | Order of scanning |
| **Time Allowance** | Time between checkpoints |

**Step 4:** Set schedule:
- Which shifts require this route
- How many times per shift
- Start/end times

**Example Route:**
```
Route: "Perimeter Security Check"
Frequency: Every 2 hours
Checkpoints (in order):
1. Main Entrance (0 min)
2. East Parking Lot (5 min)
3. Loading Dock (10 min)
4. South Perimeter (15 min)
5. West Entrance (20 min)
6. Back to Main Entrance (25 min)

Total Route Time: 25 minutes
Guard has: 30 minutes to complete
```

---

## Scanning Checkpoints

### Mobile App Scanning

**QR Code Scan:**

**Step 1:** Open GuardPro mobile app

**Step 2:** Tap **"Scan Checkpoint"**

**Step 3:** Point camera at QR code

**Step 4:** System auto-scans

**Step 5:** Confirmation shows:
- ✅ Checkpoint name
- ⏰ Scan time
- 📍 GPS location (if required)
- ✅ "Scan successful"

**Step 6:** Optional actions:
- Add notes
- Take photo
- Report issue

**NFC Scan:**

**Step 1:** Open app

**Step 2:** Tap **"Scan Checkpoint"**

**Step 3:** Tap phone to NFC tag

**Step 4:** Instant confirmation

**💡 NFC is faster:** 1-2 seconds vs 5-10 seconds for QR

### Offline Scanning

**Mobile app works offline:**
- Scans stored locally
- Syncs when connection restored
- No internet required
- Up to 1000 scans stored

**Offline indicator:**
- 🔴 Red icon shows offline mode
- Scans queued for upload
- Auto-syncs when online

---

## Viewing Checkpoint History

### Checkpoint Scan Log

**Navigation:**
- Open checkpoint record
- Click **"Scan History"** tab

**View Shows:**
- All scans for this checkpoint
- Date and time
- Guard who scanned
- Scan method used
- GPS coordinates
- Any photos taken
- Notes added

**Filters:**
- By date range
- By guard
- By shift
- Missed scans only
- Late scans only

### Missed Checkpoint Alerts

**System automatically flags:**
- ⚠️ Checkpoint not scanned on schedule
- ⏰ Scan outside time window
- 📍 GPS coordinates don't match
- ❌ Required photo missing

**Alert Actions:**
1. Supervisor notified
2. Guard receives reminder
3. Logged in compliance report
4. Can add explanation

---

## Checkpoint Reports

### Available Reports

**1. Checkpoint Compliance Report**
- Percentage of checkpoints scanned
- On-time vs late scans
- Missed checkpoints
- By site, shift, or guard

**2. Patrol Route Completion**
- Routes completed
- Average completion time
- Sequence compliance
- Gaps in coverage

**3. Checkpoint Activity Summary**
- Total scans per checkpoint
- Busiest checkpoints
- Least scanned checkpoints
- Trend analysis

**4. Guard Performance by Checkpoints**
- Individual guard compliance
- Most/least compliant guards
- Response time to reminders

### Generating Reports

**Step 1:** GuardPro > Reports > Checkpoint Reports

**Step 2:** Select report type

**Step 3:** Set parameters:
- Date range
- Sites
- Guards
- Checkpoints

**Step 4:** Click **"Generate"**

**Step 5:** View, download, or email

**Export Formats:**
- PDF (formatted report)
- Excel (data analysis)
- CSV (raw data)

---

## Troubleshooting

### QR Code Won't Scan

**Solutions:**
1. Clean camera lens
2. Ensure good lighting
3. Hold steady, 6-12 inches away
4. Check QR code not damaged
5. Try manual entry as backup

### GPS Not Matching

**Solutions:**
1. Wait for GPS to acquire (30 seconds)
2. Move away from buildings (better signal)
3. Check GPS is enabled on phone
4. Increase accuracy radius in settings
5. Use WiFi positioning indoors

### NFC Not Working

**Solutions:**
1. Ensure NFC enabled on phone
2. Remove phone case (metal interference)
3. Hold phone flat against tag
4. Try different position on tag
5. Verify tag is programmed correctly

---

## Best Practices

### Checkpoint Placement

✅ **Do:**
- Place at strategic security points
- Include high-value areas
- Cover all entry/exit points
- Balance quantity vs quality
- Consider guard walking distance

❌ **Don't:**
- Overload guards with too many
- Place in inaccessible locations
- Forget weather protection
- Ignore lighting conditions
- Place too close together

### Maintenance

**Monthly Tasks:**
- Inspect all QR codes for damage
- Test NFC tags
- Verify GPS coordinates
- Update instructions as needed
- Replace damaged tags

**Quarterly Tasks:**
- Review checkpoint effectiveness
- Optimize patrol routes
- Update schedules
- Guard feedback review
- Client requirements check

---

## Need More Help?

- 📘 **See also:** [Patrol Routes](patrols.md)
- 📘 **See also:** [Site Setup](site_setup.md)
- 📘 **See also:** [Mobile App Guide](../workflows/mobile_app.md)
- 📞 **Support:** Contact your system administrator

