# -*- coding: utf-8 -*-
"""Guard Attendance Model - Time Tracking."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class GuardAttendance(models.Model):
    """Guard Time & Attendance Tracking."""

    _name = 'guard.attendance'
    _description = 'Guard Attendance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'checkin_time desc'

    # Basic Information
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        tracking=True,
        index=True,
        ondelete='cascade'
    )
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True,
        tracking=True,
        index=True,
        ondelete='cascade'
    )
    shift_id = fields.Many2one(
        'guard.shift',
        string='Shift',
        tracking=True,
        ondelete='cascade'
    )
    
    # Shift Start
    checkin_time = fields.Datetime(
        string='Shift Start Time',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True
    )
    checkin_latitude = fields.Float(
        string='Shift Start Latitude',
        digits=(10, 7)
    )
    checkin_longitude = fields.Float(
        string='Shift Start Longitude',
        digits=(10, 7)
    )
    checkin_method = fields.Selection([
        ('manual', 'Manual'),
        ('mobile_app', 'Mobile App'),
        ('nfc', 'NFC'),
        ('qr', 'QR Code'),
        ('gps', 'GPS'),
        ('biometric', 'Biometric'),
        ('biometric_fingerprint', 'Biometric - Fingerprint'),
        ('biometric_facial', 'Biometric - Facial'),
    ], string='Shift Start Method', default='mobile_app')
    checkin_device = fields.Char(
        string='Shift Start Device'
    )
    
    # Shift End
    checkout_time = fields.Datetime(
        string='Shift End Time',
        tracking=True
    )
    checkout_latitude = fields.Float(
        string='Shift End Latitude',
        digits=(10, 7)
    )
    checkout_longitude = fields.Float(
        string='Shift End Longitude',
        digits=(10, 7)
    )
    checkout_method = fields.Selection([
        ('manual', 'Manual'),
        ('mobile_app', 'Mobile App'),
        ('nfc', 'NFC'),
        ('qr', 'QR Code'),
        ('gps', 'GPS'),
        ('biometric', 'Biometric'),
        ('biometric_fingerprint', 'Biometric - Fingerprint'),
        ('biometric_facial', 'Biometric - Facial'),
    ], string='Shift End Method', default='mobile_app')
    checkout_device = fields.Char(
        string='Shift End Device'
    )
    
    # Duration
    hours_worked = fields.Float(
        string='Hours Worked',
        compute='_compute_hours_worked',
        store=True,
        digits=(10, 2)
    )
    
    # Break Time
    break_hours = fields.Float(
        string='Break Hours',
        default=0.0,
        digits=(10, 2)
    )
    net_hours = fields.Float(
        string='Net Hours',
        compute='_compute_net_hours',
        store=True,
        digits=(10, 2)
    )
    
    # Status
    status = fields.Selection([
        ('checked_in', 'Shift Started'),
        ('on_break', 'On Break'),
        ('checked_out', 'Shift Ended'),
        ('incomplete', 'Incomplete')
    ], string='Status', compute='_compute_status', store=True)
    
    # Verification
    checkin_verified = fields.Boolean(
        string='Shift Start Verified',
        default=False,
        help='GPS location verified within geofence'
    )
    checkout_verified = fields.Boolean(
        string='Shift End Verified',
        default=False,
        help='GPS location verified within geofence'
    )
    
    # Biometric verification
    checkin_biometric_verified = fields.Boolean(
        string='Biometric Verified (Check-in)',
        default=False,
        help='Biometric verification completed for check-in'
    )
    checkout_biometric_verified = fields.Boolean(
        string='Biometric Verified (Check-out)',
        default=False,
        help='Biometric verification completed for check-out'
    )
    biometric_verification_id = fields.Many2one(
        'guard.biometric.verification',
        string='Biometric Verification',
        help='Related biometric verification record'
    )
    
    # Late/Early
    is_late = fields.Boolean(
        string='Late Shift Start',
        compute='_compute_late_early',
        store=True
    )
    is_early_checkout = fields.Boolean(
        string='Early Shift End',
        compute='_compute_late_early',
        store=True
    )
    late_minutes = fields.Integer(
        string='Minutes Late',
        compute='_compute_late_early',
        store=True
    )
    
    # Overtime
    overtime_hours = fields.Float(
        string='Overtime Hours',
        compute='_compute_overtime',
        store=True,
        digits=(10, 2)
    )
    
    # Notes
    checkin_notes = fields.Text(
        string='Shift Start Notes'
    )
    checkout_notes = fields.Text(
        string='Shift End Notes'
    )
    supervisor_notes = fields.Text(
        string='Supervisor Notes'
    )
    
    # Approval
    approved = fields.Boolean(
        string='Approved',
        default=False,
        tracking=True
    )
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By'
    )
    approval_datetime = fields.Datetime(
        string='Approval Date/Time'
    )

    @api.depends('checkin_time', 'checkout_time')
    def _compute_hours_worked(self):
        """Calculate total hours worked."""
        for record in self:
            if record.checkin_time and record.checkout_time:
                delta = record.checkout_time - record.checkin_time
                record.hours_worked = delta.total_seconds() / 3600.0
            else:
                record.hours_worked = 0.0

    @api.depends('hours_worked', 'break_hours')
    def _compute_net_hours(self):
        """Calculate net hours (worked - breaks)."""
        for record in self:
            record.net_hours = record.hours_worked - record.break_hours

    @api.depends('checkin_time', 'checkout_time')
    def _compute_status(self):
        """Determine attendance status."""
        for record in self:
            if not record.checkin_time:
                record.status = 'incomplete'
            elif record.checkout_time:
                record.status = 'checked_out'
            else:
                record.status = 'checked_in'

    @api.depends('checkin_time', 'checkout_time', 'shift_id')
    def _compute_late_early(self):
        """Check for late shift start or early shift end."""
        for record in self:
            if record.shift_id:
                # Shift start late
                if record.checkin_time > record.shift_id.start_datetime:
                    record.is_late = True
                    delta = record.checkin_time - record.shift_id.start_datetime
                    record.late_minutes = int(delta.total_seconds() / 60)
                else:
                    record.is_late = False
                    record.late_minutes = 0
                
                # Shift end early
                if (record.checkout_time and
                        record.checkout_time < record.shift_id.end_datetime):
                    record.is_early_checkout = True
                else:
                    record.is_early_checkout = False
            else:
                record.is_late = False
                record.is_early_checkout = False
                record.late_minutes = 0

    @api.depends('hours_worked', 'shift_id')
    def _compute_overtime(self):
        """Calculate overtime hours."""
        for record in self:
            if record.shift_id and record.hours_worked > record.shift_id.duration:
                record.overtime_hours = record.hours_worked - record.shift_id.duration
            else:
                record.overtime_hours = 0.0

    @api.constrains('checkin_time', 'checkout_time')
    def _check_times(self):
        """Validate shift start and end times."""
        for record in self:
            if record.checkout_time and record.checkout_time <= record.checkin_time:
                raise ValidationError(_(
                    'Shift end time must be after shift start time!'
                ))

    def action_approve(self):
        """Approve attendance record."""
        self.write({
            'approved': True,
            'approved_by': self.env.user.id,
            'approval_datetime': fields.Datetime.now()
        })

    def action_checkout_now(self, latitude=None, longitude=None):
        """End shift for the guard now."""
        self.ensure_one()
        
        if self.checkout_time:
            raise ValidationError(_('Shift has already ended!'))
        
        self.write({
            'checkout_time': fields.Datetime.now(),
            'checkout_latitude': latitude,
            'checkout_longitude': longitude,
            'checkout_method': 'mobile_app'
        })
        
        # Verify GPS if site has geofencing
        if self.site_id.geofence_enabled and latitude and longitude:
            self.checkout_verified = self.site_id.check_guard_in_geofence(
                latitude, longitude
            )

    @api.model_create_multi
    def create(self, vals_list):
        """Verify GPS on shift start."""
        records = super().create(vals_list)
        
        # Verify shift start location for each record
        for record in records:
            if (record.site_id.geofence_enabled and
                    record.checkin_latitude and record.checkin_longitude):
                record.checkin_verified = record.site_id.check_guard_in_geofence(
                    record.checkin_latitude,
                    record.checkin_longitude
                )
        
        return records
    
    def init(self):
        """Create database indexes for performance optimization."""
        # Composite index for common queries (guard + site + date)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS guard_attendance_guard_site_date_idx
            ON guard_attendance (guard_id, site_id, checkin_time DESC);
        """)
        
        # Index for status filtering
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS guard_attendance_status_idx
            ON guard_attendance (status) WHERE status IN ('checked_in', 'on_break');
        """)
        
        # Index for date range queries
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS guard_attendance_date_range_idx
            ON guard_attendance (checkin_time, checkout_time);
        """)

