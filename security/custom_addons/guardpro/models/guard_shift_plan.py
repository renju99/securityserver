# -*- coding: utf-8 -*-
"""Simplified Guard Shift Planning.

This model handles PLANNING/SCHEDULING only.
Actual time tracking is done via hr.attendance.

This separation provides:
- Simple scheduling interface
- Drag-and-drop calendar planning
- No complex check-in/out logic (delegated to hr.attendance)
- Clean separation of concerns
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class GuardShiftPlan(models.Model):
    """Simplified guard shift planning/scheduling."""
    
    _name = 'guard.shift.plan'
    _description = 'Guard Shift Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_datetime desc'
    
    # Basic Information
    name = fields.Char(
        string='Shift Name',
        compute='_compute_name',
        store=True
    )
    
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        tracking=True,
        index=True,
        help='Employee assigned to this shift'
    )
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard Profile',
        compute='_compute_guard_id',
        store=True,
        help='Related guard profile'
    )
    
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True,
        tracking=True,
        index=True
    )
    
    # Timing
    start_datetime = fields.Datetime(
        string='Planned Start',
        required=True,
        tracking=True,
        index=True
    )
    
    end_datetime = fields.Datetime(
        string='Planned End',
        required=True,
        tracking=True
    )
    
    duration = fields.Float(
        string='Duration (hours)',
        compute='_compute_duration',
        store=True
    )
    
    # Shift Details
    shift_type = fields.Selection([
        ('day', 'Day Shift'),
        ('night', 'Night Shift'),
        ('swing', 'Swing Shift'),
        ('overtime', 'Overtime')
    ], string='Shift Type', default='day', required=True, tracking=True)
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)
    
    # Assignment Details
    post_location = fields.Char(
        string='Post Location',
        help='Specific location within the site'
    )
    
    tour_ids = fields.Many2many(
        'security.tour',
        string='Assigned Tours',
        help='Tours to be completed during this shift'
    )
    
    # Requirements
    special_requirements = fields.Text(
        string='Special Requirements',
        help='Any special equipment, training, or instructions'
    )
    
    instructions = fields.Html(
        string='Shift Instructions',
        help='Detailed instructions for this shift'
    )
    
    # Actual Attendance (from hr.attendance)
    attendance_ids = fields.One2many(
        'hr.attendance',
        'planned_shift_id',
        string='Actual Attendance',
        readonly=True,
        help='Actual check-in/out records from HR attendance'
    )
    
    attendance_count = fields.Integer(
        string='Attendance Records',
        compute='_compute_attendance_count',
        store=True
    )
    
    actual_hours = fields.Float(
        string='Actual Hours Worked',
        compute='_compute_actual_hours',
        help='Sum of actual hours from attendance records'
    )
    
    attendance_status = fields.Selection([
        ('pending', 'Pending'),
        ('checked_in', 'Checked In'),
        ('completed', 'Completed'),
        ('no_show', 'No Show')
    ], string='Attendance Status', compute='_compute_attendance_status', store=True)
    
    # Template reference (for recurring shifts)
    template_id = fields.Many2one(
        'guard.shift.template',
        string='Created from Template',
        readonly=True,
        ondelete='set null'
    )
    
    # Supervisor
    supervisor_id = fields.Many2one(
        'res.users',
        string='Supervisor',
        default=lambda self: self.env.user
    )
    
    notes = fields.Text(string='Notes')
    
    # Color for calendar view
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color'
    )
    
    @api.depends('employee_id', 'site_id', 'start_datetime')
    def _compute_name(self):
        """Generate shift name."""
        for record in self:
            if record.employee_id and record.site_id and record.start_datetime:
                start = fields.Datetime.from_string(record.start_datetime)
                record.name = '%s - %s (%s)' % (
                    record.employee_id.name,
                    record.site_id.name,
                    start.strftime('%Y-%m-%d %H:%M')
                )
            else:
                record.name = 'New Shift'
    
    @api.depends('employee_id')
    def _compute_guard_id(self):
        """Link to guard profile."""
        for record in self:
            if record.employee_id:
                guard = self.env['guard.profile'].search([
                    ('employee_id', '=', record.employee_id.id)
                ], limit=1)
                record.guard_id = guard.id if guard else False
            else:
                record.guard_id = False
    
    @api.depends('start_datetime', 'end_datetime')
    def _compute_duration(self):
        """Calculate shift duration."""
        for record in self:
            if record.start_datetime and record.end_datetime:
                delta = record.end_datetime - record.start_datetime
                record.duration = delta.total_seconds() / 3600.0
            else:
                record.duration = 0.0
    
    @api.depends('attendance_ids')
    def _compute_attendance_count(self):
        """Count attendance records."""
        for record in self:
            record.attendance_count = len(record.attendance_ids)
    
    @api.depends('attendance_ids', 'attendance_ids.worked_hours')
    def _compute_actual_hours(self):
        """Calculate actual hours from attendance."""
        for record in self:
            record.actual_hours = sum(record.attendance_ids.mapped('worked_hours'))
    
    @api.depends('attendance_ids', 'attendance_ids.check_in', 'attendance_ids.check_out', 'start_datetime')
    def _compute_attendance_status(self):
        """Determine attendance status."""
        for record in self:
            if not record.attendance_ids:
                # Check if shift has passed
                if record.start_datetime < fields.Datetime.now():
                    # Grace period of 1 hour
                    if record.start_datetime < (fields.Datetime.now() - timedelta(hours=1)):
                        record.attendance_status = 'no_show'
                    else:
                        record.attendance_status = 'pending'
                else:
                    record.attendance_status = 'pending'
            else:
                # Check if any attendance is still open
                open_attendance = record.attendance_ids.filtered(lambda a: not a.check_out)
                if open_attendance:
                    record.attendance_status = 'checked_in'
                else:
                    record.attendance_status = 'completed'
    
    def _compute_color(self):
        """Set color based on status."""
        color_map = {
            'draft': 0,
            'published': 4,      # Blue
            'completed': 10,     # Green
            'cancelled': 1,      # Red
        }
        for record in self:
            record.color = color_map.get(record.status, 0)
    
    @api.constrains('start_datetime', 'end_datetime')
    def _check_dates(self):
        """Validate shift dates."""
        for record in self:
            if record.end_datetime <= record.start_datetime:
                raise ValidationError(_(
                    'End date/time must be after start date/time!'
                ))
    
    @api.constrains('employee_id', 'start_datetime', 'end_datetime')
    def _check_overlapping_shifts(self):
        """Check for overlapping shifts."""
        for record in self:
            if record.status not in ['cancelled']:
                overlapping = self.search([
                    ('id', '!=', record.id),
                    ('employee_id', '=', record.employee_id.id),
                    ('status', 'not in', ['cancelled']),
                    '|',
                    '&',
                    ('start_datetime', '<=', record.start_datetime),
                    ('end_datetime', '>', record.start_datetime),
                    '&',
                    ('start_datetime', '<', record.end_datetime),
                    ('end_datetime', '>=', record.end_datetime)
                ])
                if overlapping:
                    raise ValidationError(_(
                        'Employee %s already has a shift scheduled during this time: %s'
                    ) % (record.employee_id.name, overlapping[0].name))
    
    def action_publish(self):
        """Publish shift to make it visible to guard."""
        self.write({'status': 'published'})
        # Send notification to employee
        for record in self:
            if record.employee_id.user_id:
                body = Markup(
                    "<p><strong>Shift Published</strong></p>"
                    "<p>Your shift has been scheduled:</p>"
                    "<ul>"
                    "<li>Site: %s</li>"
                    "<li>Start: %s</li>"
                    "<li>End: %s</li>"
                    "<li>Shift Type: %s</li>"
                    "</ul>"
                    "<p>Please review and confirm availability.</p>"
                ) % (
                    Markup.escape(record.site_id.name or _('N/A')),
                    record.start_datetime,
                    record.end_datetime,
                    Markup.escape(dict(record._fields['shift_type'].selection).get(record.shift_type, _('N/A')))
                )
                record.message_post(
                    body=body,
                    partner_ids=record.employee_id.user_id.partner_id.ids,
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment'
                )
    
    def action_cancel(self):
        """Cancel the shift."""
        self.write({'status': 'cancelled'})
    
    def action_view_attendance(self):
        """Open actual attendance records."""
        self.ensure_one()
        return {
            'name': _('Attendance Records - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.attendance',
            'view_mode': 'list,form',
            'domain': [('planned_shift_id', '=', self.id)],
            'context': {
                'default_planned_shift_id': self.id,
                'default_employee_id': self.employee_id.id,
                'default_site_id': self.site_id.id
            }
        }
    
    @api.model
    def cron_check_no_shows(self):
        """Check for no-shows and send alerts.
        
        Run every 30 minutes to check for guards who haven't checked in.
        """
        grace_period = timedelta(minutes=30)
        cutoff_time = fields.Datetime.now() - grace_period
        
        # Find published shifts that started but have no attendance
        no_show_shifts = self.search([
            ('status', '=', 'published'),
            ('start_datetime', '<', cutoff_time),
            ('attendance_count', '=', 0)
        ])
        
        for shift in no_show_shifts:
            # Create activity for supervisor
            shift.activity_schedule(
                'mail.mail_activity_data_urgent',
                summary=_('No-Show Alert'),
                note=_(
                    'Employee %s has not checked in for shift at %s. '
                    'Shift was scheduled to start at %s.'
                ) % (
                    shift.employee_id.name,
                    shift.site_id.name,
                    shift.start_datetime
                ),
                user_id=shift.supervisor_id.id
            )
            
            _logger.warning(
                'No-show detected: Employee %s, Site %s, Start: %s',
                shift.employee_id.name,
                shift.site_id.name,
                shift.start_datetime
            )
        
        return True

