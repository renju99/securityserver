# -*- coding: utf-8 -*-
"""Guard Extensions for HR Attendance.

This module extends Odoo's built-in hr.attendance to add guard-specific features:
- Site assignment for each attendance record
- Shift type tracking
- GPS coordinates for mobile check-in/out
- Integration with guard profiles
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class HrAttendanceGuard(models.Model):
    """Extend HR Attendance with guard-specific fields."""
    
    _inherit = 'hr.attendance'
    
    # Guard-specific fields
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard Profile',
        compute='_compute_guard_id',
        store=True,
        index=True,
        help='Linked guard profile based on employee'
    )
    
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=False,
        tracking=True,
        index=True,
        help='The site where guard is checking in/out'
    )
    
    shift_type = fields.Selection([
        ('day', 'Day Shift'),
        ('night', 'Night Shift'),
        ('swing', 'Swing Shift'),
        ('overtime', 'Overtime')
    ], string='Shift Type', tracking=True)
    
    planned_shift_id = fields.Many2one(
        'guard.shift.plan',
        string='Planned Shift',
        help='Reference to the planned shift schedule',
        ondelete='set null'
    )
    
    # GPS Tracking
    checkin_latitude = fields.Float(
        string='Check-in Latitude',
        digits=(10, 7),
        help='GPS latitude at check-in'
    )
    checkin_longitude = fields.Float(
        string='Check-in Longitude',
        digits=(10, 7),
        help='GPS longitude at check-in'
    )
    checkout_latitude = fields.Float(
        string='Check-out Latitude',
        digits=(10, 7),
        help='GPS latitude at check-out'
    )
    checkout_longitude = fields.Float(
        string='Check-out Longitude',
        digits=(10, 7),
        help='GPS longitude at check-out'
    )
    
    # Status tracking
    attendance_status = fields.Selection([
        ('on_time', 'On Time'),
        ('late', 'Late'),
        ('early', 'Early Departure'),
        ('no_show', 'No Show')
    ], string='Attendance Status', compute='_compute_attendance_status', store=True)
    
    # Related incidents and tours during this attendance
    incident_ids = fields.One2many(
        'incident.report',
        'attendance_id',
        string='Incidents During Shift',
        help='Incidents reported during this attendance period'
    )
    incident_count = fields.Integer(
        string='Incidents',
        compute='_compute_incident_count',
        store=True
    )
    
    tour_log_ids = fields.One2many(
        'tour.log',
        'attendance_id',
        string='Tours Completed',
        help='Security tours completed during this attendance'
    )
    tour_count = fields.Integer(
        string='Tours',
        compute='_compute_tour_count',
        store=True
    )
    
    # Notes
    checkin_notes = fields.Text(
        string='Check-in Notes',
        help='Notes recorded at check-in'
    )
    checkout_notes = fields.Text(
        string='Check-out Notes',
        help='Notes recorded at check-out'
    )
    
    @api.depends('employee_id')
    def _compute_guard_id(self):
        """Link to guard profile based on employee."""
        for record in self:
            if record.employee_id:
                guard = self.env['guard.profile'].search([
                    ('employee_id', '=', record.employee_id.id)
                ], limit=1)
                record.guard_id = guard.id if guard else False
            else:
                record.guard_id = False
    
    @api.depends('planned_shift_id', 'check_in', 'check_out')
    def _compute_attendance_status(self):
        """Determine attendance status based on planned shift."""
        for record in self:
            if not record.planned_shift_id:
                record.attendance_status = False
                continue
            
            planned_start = record.planned_shift_id.start_datetime
            planned_end = record.planned_shift_id.end_datetime
            
            # Check if late (more than 15 minutes after start)
            if record.check_in and planned_start:
                from datetime import timedelta
                grace_period = timedelta(minutes=15)
                if record.check_in > (planned_start + grace_period):
                    record.attendance_status = 'late'
                    continue
            
            # Check if early departure (more than 15 minutes before end)
            if record.check_out and planned_end:
                from datetime import timedelta
                grace_period = timedelta(minutes=15)
                if record.check_out < (planned_end - grace_period):
                    record.attendance_status = 'early'
                    continue
            
            # Otherwise on time
            if record.check_in:
                record.attendance_status = 'on_time'
            else:
                record.attendance_status = False
    
    @api.depends('incident_ids')
    def _compute_incident_count(self):
        """Count incidents during attendance."""
        for record in self:
            record.incident_count = len(record.incident_ids)
    
    @api.depends('tour_log_ids')
    def _compute_tour_count(self):
        """Count tours completed during attendance."""
        for record in self:
            record.tour_count = len(record.tour_log_ids)
    
    @api.constrains('checkin_latitude', 'checkin_longitude', 'site_id')
    def _check_geofence_checkin(self):
        """Validate check-in is within site geofence if enabled."""
        for record in self:
            if record.site_id and record.site_id.geofence_enabled:
                if record.checkin_latitude and record.checkin_longitude:
                    if not record.site_id.check_guard_in_geofence(
                        record.checkin_latitude,
                        record.checkin_longitude
                    ):
                        # Log warning but don't block (supervisor can approve)
                        _logger.warning(
                            'Check-in outside geofence: Guard %s at site %s',
                            record.employee_id.name,
                            record.site_id.name
                        )
                        # Create activity for supervisor
                        record.activity_schedule(
                            'mail.mail_activity_data_warning',
                            summary=_('Check-in Outside Geofence'),
                            note=_(
                                'Guard %s checked in outside the geofence for site %s. '
                                'Please verify and approve.'
                            ) % (record.employee_id.name, record.site_id.name),
                            user_id=(
                                record.site_id.manager_id.user_ids[:1].id
                                if record.site_id.manager_id and record.site_id.manager_id.user_ids
                                else self.env.user.id
                            )
                        )
    
    def action_view_incidents(self):
        """Open incidents from this attendance."""
        self.ensure_one()
        return {
            'name': _('Incidents - %s') % self.employee_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'incident.report',
            'view_mode': 'list,form',
            'domain': [('attendance_id', '=', self.id)],
            'context': {'default_attendance_id': self.id}
        }
    
    def action_view_tours(self):
        """Open tour logs from this attendance."""
        self.ensure_one()
        return {
            'name': _('Tours - %s') % self.employee_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'tour.log',
            'view_mode': 'list,form',
            'domain': [('attendance_id', '=', self.id)],
            'context': {'default_attendance_id': self.id}
        }
    
    @api.model
    def mobile_checkin(self, employee_id, site_id, latitude=None, longitude=None, notes=None):
        """
        Mobile app check-in endpoint.
        
        Args:
            employee_id: HR employee ID
            site_id: Client site ID
            latitude: GPS latitude
            longitude: GPS longitude
            notes: Optional check-in notes
            
        Returns:
            dict: Success status and attendance record ID
        """
        employee = self.env['hr.employee'].browse(employee_id)
        site = self.env['client.site'].browse(site_id)
        
        if not employee.exists():
            raise ValidationError(_('Employee not found!'))
        
        if not site.exists():
            raise ValidationError(_('Site not found!'))
        
        # Check for existing open attendance
        existing = self.search([
            ('employee_id', '=', employee_id),
            ('check_out', '=', False)
        ], limit=1)
        
        if existing:
            raise ValidationError(_(
                'You are already checked in! Please check out first before checking in again.'
            ))
        
        # Verify geofence if enabled
        if site.geofence_enabled and latitude and longitude:
            if not site.check_guard_in_geofence(latitude, longitude):
                raise ValidationError(_('You are not within the site geofence!'))
        
        # Create attendance record
        attendance = self.create({
            'employee_id': employee_id,
            'check_in': fields.Datetime.now(),
            'site_id': site_id,
            'checkin_latitude': latitude,
            'checkin_longitude': longitude,
            'checkin_notes': notes
        })
        
        return {
            'success': True,
            'message': _('Shift started successfully!'),
            'attendance_id': attendance.id,
            'check_in': attendance.check_in
        }
    
    @api.model
    def mobile_checkout(self, employee_id, latitude=None, longitude=None, notes=None):
        """
        Mobile app check-out endpoint.
        
        Args:
            employee_id: HR employee ID
            latitude: GPS latitude
            longitude: GPS longitude
            notes: Optional check-out notes
            
        Returns:
            dict: Success status and hours worked
        """
        # Find open attendance
        attendance = self.search([
            ('employee_id', '=', employee_id),
            ('check_out', '=', False)
        ], limit=1)
        
        if not attendance:
            raise ValidationError(_(
                'No active shift found! Please start your shift first before ending it.'
            ))
        
        # Verify geofence if enabled for the site
        if attendance.site_id and attendance.site_id.geofence_enabled:
            if latitude and longitude:
                if not attendance.site_id.check_guard_in_geofence(latitude, longitude):
                    raise ValidationError(_('You are not within the site geofence!'))
        
        # Update attendance record
        attendance.write({
            'check_out': fields.Datetime.now(),
            'checkout_latitude': latitude,
            'checkout_longitude': longitude,
            'checkout_notes': notes
        })
        
        return {
            'success': True,
            'message': _('Shift ended successfully!'),
            'attendance_id': attendance.id,
            'hours_worked': attendance.worked_hours
        }


class HrEmployee(models.Model):
    """Extend HR Employee with guard-specific computed fields."""
    
    _inherit = 'hr.employee'
    
    is_guard = fields.Boolean(
        string='Is Security Guard',
        compute='_compute_is_guard',
        store=True,
        help='True if this employee has a guard profile'
    )
    
    guard_profile_id = fields.Many2one(
        'guard.profile',
        string='Guard Profile',
        compute='_compute_is_guard',
        store=True
    )
    
    @api.depends('name')
    def _compute_is_guard(self):
        """Check if employee has a guard profile."""
        for employee in self:
            guard = self.env['guard.profile'].search([
                ('employee_id', '=', employee.id)
            ], limit=1)
            employee.is_guard = bool(guard)
            employee.guard_profile_id = guard.id if guard else False

