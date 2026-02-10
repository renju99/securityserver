GuardPro - Enterprise Security Operations Suite
==================================================

Overview
--------

GuardPro centralizes guard field operations, compliance, and client reporting inside Odoo 18 Community Edition. The suite connects supervisors, control rooms, guards, and clients with real-time visibility, mobile-first workflows, and automated analytics.

Designed with security service providers and in-house facility teams in mind, GuardPro helps you win competitive tenders, protect service margins, and deliver branded transparency to every client account.

Highlights
----------

* Mobile-first guard experience with offline-ready PWA, live GPS tracking, and checkpoint verification (NFC, QR, geofencing)
* Incident, emergency, and compliance management with evidence capture, workflows, escalation ladders, and SLA tracking
* Centralized scheduling, attendance control, and guard credential lifecycle management with conflict detection
* 30+ operational modules covering tasks, visitors, packages, keys, tours, audits, daily activity reports, and more
* Client and guard portals with secure role-based access, dashboards, and self-service reporting
* 40% reduction in manual admin through automated workflows, smart schedules, and SLA alerts (based on customer rollouts)

Features
--------

Core Functionality
~~~~~~~~~~~~~~~~~~

* **Guard Profile Management**: Complete guard information, certifications, skills, and performance tracking
* **Client Site Management**: Site locations with geofencing (circular and polygon)
* **Security Tours**: Define patrol routes with checkpoints
* **Shift Scheduling**: Advanced scheduling with calendar view and drag-drop support
* **Real-time GPS Tracking**: Monitor guard locations with 30-second updates
* **Checkpoint Verification**: NFC tags, QR codes, and virtual GPS checkpoints
* **Incident Reporting**: Complete incident management with photos, videos, and workflows
* **Time & Attendance**: GPS-verified check-in/check-out with geofencing
* **Equipment Tracking**: Manage guard equipment and assets
* **Client User Access**: Internal user role for clients to view reports and incidents
* **Guard Portal Access**: Mobile portal for guards to view shifts, report incidents, and complete tours

New Modules (October 2025 - Complete SRS Compliance)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Task Management**: Digital duty assignments with checklists and templates
* **Visitor Management**: Pre-registration, QR badges, watchlist screening, contractor management
* **Lost & Found**: Property tracking with legal holding periods, photo evidence, claim verification
* **Package Management**: Delivery receipt tracking, pickup notifications, signature capture
* **Key Management**: Physical key tracking, issuance logs, overdue alerts, barcode integration
* **Audit & Compliance**: Customizable checklists, scoring, corrective actions, audit trails
* **Daily Activity Reports (DARs)**: Auto-generated reports with approval workflow and client email
* **SLA Management**: KPI tracking, automated calculations, breach alerts, performance dashboards

Mobile PWA Features
~~~~~~~~~~~~~~~~~~~

* **Progressive Web App**: Install on mobile devices (iOS/Android)
* **Offline Capability**: Works without internet connection with automatic sync
* **NFC Scanning**: Tap NFC tags for checkpoint verification
* **QR Code Scanning**: Camera-based QR code scanning
* **GPS Tracking**: Battery-optimized background location tracking
* **Panic Button**: Emergency alert system
* **Push Notifications**: Real-time alerts and updates
* **Dark Mode**: Automatic dark mode support

Enterprise Features
~~~~~~~~~~~~~~~~~~~

* **Geofencing**: Circular and polygon geofences with entry/exit alerts
* **Tour Logging**: Track tour completion and checkpoint scans
* **Performance Analytics**: Guard performance metrics and reports
* **Automated Reporting**: Schedule and generate custom reports
* **Multi-level Security**: Role-based access control with record rules
* **Audit Trails**: Complete activity logging

Installation
------------

1. Copy the ``guardpro`` folder to your Odoo addons directory::

   cp -r guardpro /path/to/odoo/custom_addons/

2. Update your Odoo configuration to include the custom addons path::

   addons_path = /path/to/odoo/addons,/path/to/odoo/custom_addons

3. Restart your Odoo server::

   odoo-bin -c /path/to/odoo.conf

4. Install Python dependencies (required for documentation viewer)::

   pip3 install -r guardpro/requirements.txt

   Or install manually::

   pip3 install markdown Pygments

5. In Odoo, go to **Apps > Update Apps List**

6. Search for "GuardPro" and click **Install**

Configuration
-------------

Initial Setup
~~~~~~~~~~~~~

Google Maps API Key (Required for Mapping)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Create a billing-enabled project in the `Google Cloud Console <https://console.cloud.google.com/apis/credentials>`_
2. Enable the **Maps JavaScript API** (and optional Places/Geocoding APIs if needed)
3. Generate a browser-restricted API key
4. In Odoo, go to **Settings > General Settings > GuardPro > Google Maps Integration**
5. Paste the key into the **Google Maps API Key** field and click **Save**

.. note::
   GuardPro never ships with a shared Google API key. Each customer must provide their own key so billing and usage stay under their Google Cloud account.

Create Guard Profiles
^^^^^^^^^^^^^^^^^^^^^

* Go to **Documentation > Resources > Guards**
* Create guard profiles linked to HR employees
* Add certifications, skills, and contact information

Setup Client Sites
^^^^^^^^^^^^^^^^^^

* Go to **Documentation > Resources > Sites**
* Create client sites with GPS coordinates
* Configure geofencing (circular or polygon)
* Add access instructions and emergency contacts

Define Security Tours
^^^^^^^^^^^^^^^^^^^^^

* Go to **Documentation > Operations > Tours**
* Create patrol routes
* Assign checkpoints to tours
* Set tour frequency and requirements

Create Checkpoints
^^^^^^^^^^^^^^^^^^

* Go to **Documentation > Resources > Checkpoints**
* Add checkpoints with NFC tags or QR codes
* Set GPS coordinates for virtual checkpoints
* Configure photo/note requirements

Schedule Shifts
^^^^^^^^^^^^^^^

* Go to **Documentation > Operations > Shifts**
* Use the calendar view to schedule shifts
* Assign guards to sites
* Set shift types and requirements

Usage
-----

For Guards (Mobile)
~~~~~~~~~~~~~~~~~~~

1. **Check-in to Shift**:
   * Open GuardPro mobile app
   * Tap "Check In" button
   * Confirm GPS location is within geofence

2. **Start Tour**:
   * Select assigned tour
   * Tap "Start Tour"
   * Scan checkpoints in order

3. **Scan Checkpoints**:
   * Tap "Scan" button
   * Hold phone near NFC tag or point at QR code
   * Add photos/notes if required

4. **Report Incident**:
   * Tap "Report Incident" button
   * Fill in incident details
   * Take photos and add location
   * Submit report

5. **Emergency Panic**:
   * Tap red "PANIC" button
   * Confirm emergency alert
   * Emergency notifications sent automatically

For Supervisors
~~~~~~~~~~~~~~~

1. **Monitor Active Shifts**:
   * View Dashboard for real-time status
   * Check guard locations on map
   * Review tour progress

2. **Review Incidents**:
   * Go to Incidents menu
   * Review submitted reports
   * Update status and add notes
   * Assign for investigation

3. **Approve Attendance**:
   * Go to Operations > Attendance
   * Review time records
   * Verify GPS check-in/out locations
   * Approve hours worked

For Managers
~~~~~~~~~~~~

1. **Scheduling**:
   * Use Shift Assignment Wizard for bulk scheduling
   * Manage guard availability
   * Handle shift swaps and replacements

2. **Reporting**:
   * Generate custom reports
   * Export data to Excel/PDF
   * Track KPIs and performance metrics

3. **Configuration**:
   * Manage user access and permissions
   * Configure incident categories
   * Setup guard skills and certifications

For Clients (Portal)
~~~~~~~~~~~~~~~~~~~~

1. **Access Portal**:
   * Visit ``/my/guardpro``
   * View your sites and coverage

2. **Review Incidents**:
   * View incidents at your sites
   * Track incident resolution status
   * Download incident reports

3. **Monitor Activity**:
   * See active shifts
   * View guard patrol logs
   * Access historical data

Security & Permissions
----------------------

User Groups
~~~~~~~~~~~

* **Guard User**: Portal user with mobile portal access (view shifts, report incidents, complete tours - own data only)
* **Client User**: Internal user with read-only access to own site data
* **Supervisor**: Internal user who can manage shifts, review incidents, approve attendance
* **Manager**: Internal user with full management access
* **Administrator**: Internal user with complete system access including configuration

Record Rules
~~~~~~~~~~~~

* Guards can only view their own shifts, attendance, and tours
* Clients can only view data for their sites
* Supervisors can view all operational data
* Managers have full access

Technical Details
-----------------

Dependencies
~~~~~~~~~~~~

* Odoo 18 Community Edition
* Python 3.10+
* PostgreSQL 13+

Browser Support (Mobile PWA)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Chrome/Edge 90+ (Android)
* Safari 14.5+ (iOS)
* Web NFC API (Android only)
* Camera API for QR scanning

API Endpoints
~~~~~~~~~~~~~

* ``/guardpro/api/shifts/today`` - Get today's shifts
* ``/guardpro/api/shift/checkin`` - Check in to shift
* ``/guardpro/api/shift/checkout`` - Check out from shift
* ``/guardpro/api/checkpoint/scan`` - Scan checkpoint
* ``/guardpro/api/tour/start`` - Start tour
* ``/guardpro/api/incident/create`` - Create incident
* ``/guardpro/api/incident/panic`` - Panic button
* ``/guardpro/api/location/update`` - Update GPS location

Data Models
~~~~~~~~~~~

* ``guard.profile`` - Guard information
* ``client.site`` - Client site locations
* ``security.tour`` - Patrol routes
* ``checkpoint`` - Verification points
* ``guard.shift`` - Shift schedules
* ``incident.report`` - Incident reports
* ``guard.attendance`` - Time tracking
* ``guardpro.equipment`` - Equipment tracking
* ``tour.log`` - Tour execution logs
* ``checkpoint.scan`` - Checkpoint scan records

Troubleshooting
---------------

GPS not working:
~~~~~~~~~~~~~~~~

* Ensure location permissions are granted
* Check device location services are enabled
* Verify HTTPS connection (required for Geolocation API)

NFC not scanning:
~~~~~~~~~~~~~~~~~

* NFC only supported on Android devices
* Ensure NFC is enabled in device settings
* Hold device close to tag (2-3 cm)

Offline sync issues:
~~~~~~~~~~~~~~~~~~~~

* Check internet connection
* Clear browser cache
* Re-sync manually from app settings

Geofence alerts not triggering:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Verify site coordinates are correct
* Check geofence radius is appropriate
* Ensure GPS accuracy is sufficient

Best Practices
--------------

1. **Regular Data Backup**: Backup database regularly
2. **Test Geofences**: Verify geofence boundaries before deployment
3. **NFC Tag Placement**: Place tags in protected, accessible locations
4. **Training**: Provide thorough training for all users
5. **Mobile Device Management**: Use compatible, updated devices

Support
-------

For issues, feature requests, or contributions, email ``mails4ranjith@gmail.com``.

License
-------

This module is licensed under LGPL-3.

Version
-------

**Current Version:** 18.0.1.0.8

**Last Updated:** November 2025

