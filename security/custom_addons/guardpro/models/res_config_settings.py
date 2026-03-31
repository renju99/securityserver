# -*- coding: utf-8 -*-
"""GuardPro Configuration Settings."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    """GuardPro system configuration settings."""
    
    _inherit = 'res.config.settings'

    # ====================================================
    # GOOGLE MAPS INTEGRATION
    # ====================================================
    
    google_maps_api_key = fields.Char(
        string='Google Maps API Key',
        config_parameter='guardpro.google_maps_api_key',
        help='API key for Google Maps integration. '
             'Required for real-time location tracking and mapping features.'
    )
    
    # ====================================================
    # GPS TRACKING SETTINGS
    # ====================================================
    
    gps_update_interval = fields.Integer(
        string='GPS Update Interval (seconds)',
        default=30,
        config_parameter='guardpro.gps_update_interval',
        help='How often the mobile app should update GPS location. '
             'Lower values = more accurate but use more battery. '
             'Recommended: 30-60 seconds.'
    )
    
    gps_accuracy_threshold = fields.Float(
        string='GPS Accuracy Threshold (meters)',
        default=50.0,
        config_parameter='guardpro.gps_accuracy_threshold',
        help='Minimum GPS accuracy required for location updates. '
             'Updates with lower accuracy will be ignored.'
    )
    
    # ====================================================
    # DATA RETENTION POLICIES
    # ====================================================
    
    location_history_retention = fields.Integer(
        string='Location History Retention (days)',
        default=90,
        config_parameter='guardpro.location_history_retention',
        help='How long to keep location history records before automatic deletion. '
             'Recommended: 90-180 days for compliance and performance.'
    )
    
    shift_records_retention = fields.Integer(
        string='Shift Records Retention (days)',
        default=730,  # 2 years
        config_parameter='guardpro.shift_records_retention',
        help='How long to keep completed shift records. '
             'Recommended: 2-7 years for compliance.'
    )
    
    incident_records_retention = fields.Integer(
        string='Incident Records Retention (days)',
        default=2555,  # 7 years
        config_parameter='guardpro.incident_records_retention',
        help='How long to keep incident records. '
             'Recommended: 7 years for legal compliance.'
    )
    
    # ====================================================
    # NOTIFICATION SETTINGS
    # ====================================================
    
    shift_reminder_minutes = fields.Integer(
        string='Shift Reminder (minutes before start)',
        default=30,
        config_parameter='guardpro.shift_reminder_minutes',
        help='Send shift reminder notifications this many minutes before shift starts. '
             'Recommended: 30-60 minutes.'
    )
    
    critical_incident_escalation = fields.Integer(
        string='Critical Incident Escalation (minutes)',
        default=30,
        config_parameter='guardpro.critical_incident_escalation',
        help='Automatically escalate critical incidents if not responded to within this time. '
             'Recommended: 15-30 minutes.'
    )
    
    missed_checkin_grace_period = fields.Integer(
        string='Missed Check-in Grace Period (minutes)',
        default=15,
        config_parameter='guardpro.missed_checkin_grace_period',
        help='Grace period before alerting supervisors about missed check-ins. '
             'Recommended: 10-15 minutes.'
    )

    mail_mail_retention_days = fields.Integer(
        string='Email queue log retention (days)',
        default=365,
        config_parameter='guardpro.mail_mail_retention_days',
        help='How long to keep mail.mail rows (outgoing/sent/exception queue) before the daily job '
             'removes them. Chatter messages on documents (mail.message) are not deleted.'
    )
    
    # ====================================================
    # GEOFENCING SETTINGS
    # ====================================================
    
    geofence_default_radius = fields.Float(
        string='Default Geofence Radius (meters)',
        default=100.0,
        config_parameter='guardpro.default_geofence_radius',
        help='Default radius for circular geofences when creating new sites. '
             'Can be customized per site. '
             'Recommended: 50-200 meters depending on site size.'
    )
    
    geofence_check_interval = fields.Integer(
        string='Geofence Check Interval (seconds)',
        default=60,
        config_parameter='guardpro.geofence_check_interval',
        help='How often to check if guards are within their assigned geofences. '
             'Recommended: 60-300 seconds.'
    )

    geofence_alert_interval_minutes = fields.Integer(
        string='Geofence Alert Interval (minutes)',
        default=15,
        config_parameter='guardpro.geofence_alert_interval_minutes',
        help='Minimum time between repeated geofence alerts for the same guard and site. '
             'Recommended: 15 minutes.'
    )
    
    # ====================================================
    # SECURITY SETTINGS
    # ====================================================
    
    enable_panic_button = fields.Boolean(
        string='Enable Panic Button',
        default=True,
        config_parameter='guardpro.enable_panic_button',
        help='Enable emergency panic button in mobile app.'
    )
    
    require_photo_on_checkin = fields.Boolean(
        string='Require Photo on Check-in',
        default=False,
        config_parameter='guardpro.require_photo_on_checkin',
        help='Require guards to take a photo when checking in to shifts.'
    )
    
    require_photo_on_checkout = fields.Boolean(
        string='Require Photo on Check-out',
        default=False,
        config_parameter='guardpro.require_photo_on_checkout',
        help='Require guards to take a photo when checking out of shifts.'
    )
    
    # ====================================================
    # PERFORMANCE SETTINGS
    # ====================================================
    
    max_location_points_per_shift = fields.Integer(
        string='Max Location Points per Shift',
        default=480,  # 8 hours * 60 minutes / 1 minute
        config_parameter='guardpro.max_location_points_per_shift',
        help='Maximum number of location points to store per shift. '
             'Prevents database bloat. '
             'Recommended: 300-500 points.'
    )
    
    enable_location_clustering = fields.Boolean(
        string='Enable Location Clustering',
        default=True,
        config_parameter='guardpro.enable_location_clustering',
        help='Cluster nearby location points for better map performance.'
    )
    
    # ====================================================
    # FEATURE FLAGS
    # ====================================================
    
    enable_nfc_scanning = fields.Boolean(
        string='Enable NFC Scanning',
        default=True,
        config_parameter='guardpro.enable_nfc_scanning',
        help='Enable NFC tag scanning for checkpoints (Android only).'
    )
    
    enable_qr_scanning = fields.Boolean(
        string='Enable QR Code Scanning',
        default=True,
        config_parameter='guardpro.enable_qr_scanning',
        help='Enable QR code scanning for checkpoints.'
    )
    
    enable_offline_mode = fields.Boolean(
        string='Enable Offline Mode',
        default=True,
        config_parameter='guardpro.enable_offline_mode',
        help='Enable offline capabilities in mobile app with automatic sync.'
    )
    
    # ====================================================
    # NEW MODULES SETTINGS
    # ====================================================
    
    # Lost & Found Settings
    lost_found_default_holding_period = fields.Integer(
        string='Lost & Found Holding Period (days)',
        default=90,
        config_parameter='guardpro.lost_found_holding_period',
        help='Default number of days to hold lost & found items before disposal. '
             'Recommended: 30-90 days based on local regulations.'
    )
    
    # Package Management Settings
    package_overdue_threshold = fields.Integer(
        string='Package Overdue Threshold (days)',
        default=7,
        config_parameter='guardpro.package_overdue_threshold',
        help='Number of days before a package is considered overdue for pickup. '
             'Recommended: 3-7 days.'
    )
    
    package_unclaimed_period = fields.Integer(
        string='Package Unclaimed Period (days)',
        default=30,
        config_parameter='guardpro.package_unclaimed_period',
        help='Days after which uncollected packages are marked as unclaimed. '
             'Recommended: 30 days.'
    )
    
    # Visitor Management Settings
    visitor_registration_expiry = fields.Integer(
        string='Visitor Pre-Registration Expiry (days)',
        default=7,
        config_parameter='guardpro.visitor_registration_expiry',
        help='Days after which unused pre-registrations expire. '
             'Recommended: 7 days.'
    )
    
    visitor_max_duration = fields.Float(
        string='Visitor Max Duration (hours)',
        default=12.0,
        config_parameter='guardpro.visitor_max_duration',
        help='Maximum expected visitor duration before overdue alert. '
             'Recommended: 8-12 hours.'
    )
    
    enable_visitor_qr_codes = fields.Boolean(
        string='Enable Visitor QR Codes',
        default=True,
        config_parameter='guardpro.enable_visitor_qr_codes',
        help='Generate QR codes for visitor badges.'
    )
    
    # Task Management Settings
    task_overdue_alert_hours = fields.Integer(
        string='Task Overdue Alert Interval (hours)',
        default=1,
        config_parameter='guardpro.task_overdue_alert_hours',
        help='How often to send overdue task alerts. '
             'Recommended: 1-4 hours.'
    )
    
    # Audit Settings
    audit_reminder_days = fields.Integer(
        string='Audit Reminder (days before due)',
        default=7,
        config_parameter='guardpro.audit_reminder_days',
        help='Send audit reminders this many days before scheduled date. '
             'Recommended: 7 days.'
    )
    
    # Daily Activity Report Settings
    dar_auto_generate = fields.Boolean(
        string='Auto-Generate Daily Reports',
        default=True,
        config_parameter='guardpro.dar_auto_generate',
        help='Automatically generate Daily Activity Reports for previous day.'
    )
    
    dar_auto_send_time = fields.Float(
        string='Auto-Send Time (24-hour format)',
        default=8.0,
        config_parameter='guardpro.dar_auto_send_time',
        help='Time to auto-send approved DARs to clients (e.g., 8.0 = 8:00 AM). '
             'Only applies if site has auto-send enabled.'
    )
    
    # SLA Settings
    sla_alert_threshold = fields.Float(
        string='SLA Alert Threshold (%)',
        default=90.0,
        config_parameter='guardpro.sla_alert_threshold',
        help='Alert if SLA performance drops below this percentage. '
             'Recommended: 85-95%.'
    )
    
    # ====================================================
    # PERFORMANCE MANAGEMENT SETTINGS
    # ====================================================
    
    performance_review_frequency = fields.Selection([
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
    ], string='Default Review Frequency',
       default='monthly',
       config_parameter='guardpro.performance_review_frequency',
       help='Default frequency for performance reviews.'
    )
    
    performance_auto_calculate = fields.Boolean(
        string='Auto-Calculate Performance Metrics',
        default=True,
        config_parameter='guardpro.performance_auto_calculate',
        help='Automatically calculate performance metrics at the end of each review period.'
    )
    
    performance_review_reminder_days = fields.Integer(
        string='Review Reminder (days before due)',
        default=3,
        config_parameter='guardpro.performance_review_reminder_days',
        help='Send reminder to complete pending reviews this many days before due date.'
    )
    
    performance_excellent_threshold = fields.Float(
        string='Excellent Performance Threshold',
        default=90.0,
        config_parameter='guardpro.performance_excellent_threshold',
        help='Minimum score for Excellent performance rating (0-100).'
    )
    
    performance_good_threshold = fields.Float(
        string='Good Performance Threshold',
        default=80.0,
        config_parameter='guardpro.performance_good_threshold',
        help='Minimum score for Good performance rating (0-100).'
    )
    
    performance_satisfactory_threshold = fields.Float(
        string='Satisfactory Performance Threshold',
        default=70.0,
        config_parameter='guardpro.performance_satisfactory_threshold',
        help='Minimum score for Satisfactory performance rating (0-100).'
    )
    
    performance_needs_improvement_threshold = fields.Float(
        string='Needs Improvement Threshold',
        default=60.0,
        config_parameter='guardpro.performance_needs_improvement_threshold',
        help='Minimum score for Needs Improvement rating. Below this is Unsatisfactory (0-100).'
    )
    
    performance_badge_enabled = fields.Boolean(
        string='Enable Performance Badges',
        default=True,
        config_parameter='guardpro.performance_badge_enabled',
        help='Enable automatic award of performance badges.'
    )
    
    performance_punctuality_weight = fields.Float(
        string='Punctuality Weight (%)',
        default=20.0,
        config_parameter='guardpro.performance_punctuality_weight',
        help='Weight of punctuality in overall performance score (0-100%).'
    )
    
    performance_tour_completion_weight = fields.Float(
        string='Tour Completion Weight (%)',
        default=25.0,
        config_parameter='guardpro.performance_tour_completion_weight',
        help='Weight of tour completion in overall performance score (0-100%).'
    )
    
    performance_incident_response_weight = fields.Float(
        string='Incident Response Weight (%)',
        default=20.0,
        config_parameter='guardpro.performance_incident_response_weight',
        help='Weight of incident response quality in overall performance score (0-100%).'
    )
    
    performance_client_satisfaction_weight = fields.Float(
        string='Client Satisfaction Weight (%)',
        default=20.0,
        config_parameter='guardpro.performance_client_satisfaction_weight',
        help='Weight of client satisfaction in overall performance score (0-100%).'
    )
    
    performance_shift_adherence_weight = fields.Float(
        string='Shift Adherence Weight (%)',
        default=15.0,
        config_parameter='guardpro.performance_shift_adherence_weight',
        help='Weight of shift adherence in overall performance score (0-100%).'
    )
    
    # ====================================================
    # VALIDATION
    # ====================================================
    
    @api.constrains('gps_update_interval')
    def _check_gps_interval(self):
        """Validate GPS update interval."""
        for record in self:
            if record.gps_update_interval < 10:
                raise ValidationError(_(
                    'GPS update interval must be at least 10 seconds to prevent battery drain.'
                ))
            if record.gps_update_interval > 300:
                raise ValidationError(_(
                    'GPS update interval should not exceed 5 minutes (300 seconds).'
                ))
    
    @api.constrains('location_history_retention')
    def _check_retention(self):
        """Validate retention periods."""
        for record in self:
            if record.location_history_retention < 7:
                raise ValidationError(_(
                    'Location history retention must be at least 7 days.'
                ))
    
    @api.constrains('shift_reminder_minutes')
    def _check_reminder_time(self):
        """Validate shift reminder time."""
        for record in self:
            if record.shift_reminder_minutes < 5:
                raise ValidationError(_(
                    'Shift reminder must be at least 5 minutes before start.'
                ))
            if record.shift_reminder_minutes > 480:  # 8 hours
                raise ValidationError(_(
                    'Shift reminder should not exceed 8 hours.'
                ))

    @api.constrains('geofence_alert_interval_minutes')
    def _check_geofence_alert_interval(self):
        """Validate geofence alert interval."""
        for record in self:
            if record.geofence_alert_interval_minutes < 1:
                raise ValidationError(_(
                    'Geofence alert interval must be at least 1 minute.'
                ))
            if record.geofence_alert_interval_minutes > 1440:
                raise ValidationError(_(
                    'Geofence alert interval should not exceed 24 hours (1440 minutes).'
                ))

    @api.constrains('mail_mail_retention_days')
    def _check_mail_mail_retention_days(self):
        """Validate mail.mail retention."""
        for record in self:
            if record.mail_mail_retention_days < 1:
                raise ValidationError(_(
                    'Email queue retention must be at least 1 day.'
                ))
            if record.mail_mail_retention_days > 3650:
                raise ValidationError(_(
                    'Email queue retention should not exceed 3650 days (10 years).'
                ))

