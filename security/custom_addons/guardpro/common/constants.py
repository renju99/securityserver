# -*- coding: utf-8 -*-
"""GuardLink Module Constants.

This module contains all constants used throughout the GuardLink module.
Centralizing constants improves maintainability and makes configuration easier.
"""

# ============================================================================
# LOCATION & GPS CONSTANTS
# ============================================================================

# Location update retry configuration
LOCATION_UPDATE_MAX_RETRIES = 3
LOCATION_UPDATE_RETRY_DELAY = 0.1  # seconds
LOCATION_UPDATE_RETRY_BACKOFF = True  # Use exponential backoff

# GPS coordinate limits
GPS_LATITUDE_MIN = -90.0
GPS_LATITUDE_MAX = 90.0
GPS_LONGITUDE_MIN = -180.0
GPS_LONGITUDE_MAX = 180.0

# Earth's radius for distance calculations
EARTH_RADIUS_METERS = 6371000  # meters
EARTH_RADIUS_KM = 6371  # kilometers

# ============================================================================
# SHIFT & ATTENDANCE CONSTANTS
# ============================================================================

# Check-in grace period (minutes)
CHECKIN_GRACE_PERIOD_MINUTES = 15

# Missed check-in alert delay (minutes)
MISSED_CHECKIN_ALERT_DELAY = 15

# Shift reminder time before start (minutes)
SHIFT_REMINDER_MINUTES = 30

# Shift reminder window (minutes before/after)
SHIFT_REMINDER_WINDOW = 5

# ============================================================================
# INCIDENT & ALERT CONSTANTS
# ============================================================================

# Critical incident escalation time (minutes)
CRITICAL_INCIDENT_ESCALATION_MINUTES = 30

# Overdue tour check period (hours)
OVERDUE_TOUR_CHECK_HOURS = 24

# ============================================================================
# DATA RETENTION CONSTANTS
# ============================================================================

# Location history retention period (days)
LOCATION_HISTORY_RETENTION_DAYS = 90

# ============================================================================
# CERTIFICATION & LICENSE CONSTANTS
# ============================================================================

# License expiry warning periods (days)
LICENSE_EXPIRY_WARNING_DAYS = 30
LICENSE_EXPIRY_CRITICAL_DAYS = 7
LICENSE_EXPIRY_HIGH_DAYS = 14

# ============================================================================
# API & RATE LIMITING CONSTANTS
# ============================================================================

# API rate limits (requests per time window)
API_RATE_LIMIT_REQUESTS = 30
API_RATE_LIMIT_WINDOW = 60  # seconds

# API retry configuration
API_MAX_RETRIES = 3
API_RETRY_DELAY = 0.1  # seconds

# ============================================================================
# VALIDATION CONSTANTS
# ============================================================================

# Maximum file upload sizes (bytes)
MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB

# Maximum text field lengths
MAX_NOTES_LENGTH = 5000
MAX_DESCRIPTION_LENGTH = 10000

# ============================================================================
# NOTIFICATION CONSTANTS
# ============================================================================

# Notification priorities
NOTIFICATION_PRIORITY_LOW = '1'
NOTIFICATION_PRIORITY_NORMAL = '0'
NOTIFICATION_PRIORITY_HIGH = '2'
NOTIFICATION_PRIORITY_URGENT = '3'

# ============================================================================
# CRON JOB PRIORITIES
# ============================================================================

CRON_PRIORITY_CRITICAL = 1  # Highest priority
CRON_PRIORITY_HIGH = 5
CRON_PRIORITY_NORMAL = 10
CRON_PRIORITY_LOW = 15

# ============================================================================
# STATUS CONSTANTS
# ============================================================================

# Guard statuses
GUARD_STATUS_ACTIVE = 'active'
GUARD_STATUS_ON_LEAVE = 'on_leave'
GUARD_STATUS_SUSPENDED = 'suspended'
GUARD_STATUS_TERMINATED = 'terminated'

# Shift statuses
SHIFT_STATUS_SCHEDULED = 'scheduled'
SHIFT_STATUS_CONFIRMED = 'confirmed'
SHIFT_STATUS_IN_PROGRESS = 'in_progress'
SHIFT_STATUS_COMPLETED = 'completed'
SHIFT_STATUS_CANCELLED = 'cancelled'
SHIFT_STATUS_NO_SHOW = 'no_show'

# Incident severity levels
INCIDENT_SEVERITY_LOW = 'low'
INCIDENT_SEVERITY_MEDIUM = 'medium'
INCIDENT_SEVERITY_HIGH = 'high'
INCIDENT_SEVERITY_CRITICAL = 'critical'

# Tour statuses
TOUR_STATUS_IN_PROGRESS = 'in_progress'
TOUR_STATUS_COMPLETED = 'completed'
TOUR_STATUS_INCOMPLETE = 'incomplete'
TOUR_STATUS_CANCELLED = 'cancelled'

# ============================================================================
# COLOR CONSTANTS FOR UI
# ============================================================================

# Shift status colors (Odoo color palette index)
COLOR_SHIFT_SCHEDULED = 3    # Blue
COLOR_SHIFT_CONFIRMED = 7    # Green
COLOR_SHIFT_IN_PROGRESS = 9  # Orange
COLOR_SHIFT_COMPLETED = 10   # Green
COLOR_SHIFT_CANCELLED = 1    # Red
COLOR_SHIFT_NO_SHOW = 2      # Red

# Incident severity colors
COLOR_INCIDENT_LOW = 3       # Blue
COLOR_INCIDENT_MEDIUM = 9    # Orange
COLOR_INCIDENT_HIGH = 2      # Red
COLOR_INCIDENT_CRITICAL = 1  # Dark Red

# ============================================================================
# GEOFENCING CONSTANTS
# ============================================================================

# Default geofence radius (meters)
DEFAULT_GEOFENCE_RADIUS = 1000.0

# Geofence check tolerance (meters)
GEOFENCE_TOLERANCE = 10.0

# ============================================================================
# SYSTEM PARAMETER KEYS
# ============================================================================

# System parameter keys for configurable values
SYSPARAM_SHIFT_REMINDER_MINUTES = 'guardpro.shift_reminder_minutes'
SYSPARAM_CHECKIN_GRACE_PERIOD = 'guardpro.checkin_grace_period'
SYSPARAM_CRITICAL_INCIDENT_ESCALATION = 'guardpro.critical_incident_escalation'
SYSPARAM_LOCATION_HISTORY_RETENTION = 'guardpro.location_history_retention'
SYSPARAM_LICENSE_WARNING_DAYS = 'guardpro.license_warning_days'

# ============================================================================
# PACKAGE MANAGEMENT CONSTANTS
# ============================================================================

# Package lifecycle thresholds (days)
UNCLAIMED_THRESHOLD_DAYS = 30
OVERDUE_THRESHOLD_DAYS = 7

# Package type expected pickup periods (days)
PACKAGE_PICKUP_FOOD_DELIVERY = 0  # Same day
PACKAGE_PICKUP_MEDICAL = 1  # Next day
PACKAGE_PICKUP_PERISHABLE = 1  # Next day
PACKAGE_PICKUP_DOCUMENT = 3  # 3 days
PACKAGE_PICKUP_STANDARD = 7  # 1 week
PACKAGE_PICKUP_FURNITURE = 14  # 2 weeks

# Photo optimization thresholds (bytes)
PHOTO_OPTIMIZATION_THRESHOLD = 300 * 1024  # 300 KB
PACKAGE_PHOTO_MAX_DIMENSION = 1200  # pixels
DAMAGE_PHOTO_MAX_DIMENSION = 800  # pixels

# Notification settings
PACKAGE_NOTIFICATION_RETRY_DELAY = 300  # seconds (5 minutes)
PACKAGE_NOTIFICATION_MAX_RETRIES = 3

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_color_for_shift_status(status):
    """Get color index for shift status.
    
    Args:
        status (str): Shift status
        
    Returns:
        int: Color index for Odoo UI
    """
    color_map = {
        SHIFT_STATUS_SCHEDULED: COLOR_SHIFT_SCHEDULED,
        SHIFT_STATUS_CONFIRMED: COLOR_SHIFT_CONFIRMED,
        SHIFT_STATUS_IN_PROGRESS: COLOR_SHIFT_IN_PROGRESS,
        SHIFT_STATUS_COMPLETED: COLOR_SHIFT_COMPLETED,
        SHIFT_STATUS_CANCELLED: COLOR_SHIFT_CANCELLED,
        SHIFT_STATUS_NO_SHOW: COLOR_SHIFT_NO_SHOW,
    }
    return color_map.get(status, 0)


def get_color_for_incident_severity(severity):
    """Get color index for incident severity.
    
    Args:
        severity (str): Incident severity
        
    Returns:
        int: Color index for Odoo UI
    """
    color_map = {
        INCIDENT_SEVERITY_LOW: COLOR_INCIDENT_LOW,
        INCIDENT_SEVERITY_MEDIUM: COLOR_INCIDENT_MEDIUM,
        INCIDENT_SEVERITY_HIGH: COLOR_INCIDENT_HIGH,
        INCIDENT_SEVERITY_CRITICAL: COLOR_INCIDENT_CRITICAL,
    }
    return color_map.get(severity, 0)



