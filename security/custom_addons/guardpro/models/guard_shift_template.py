# -*- coding: utf-8 -*-
"""Simplified Shift Template for Recurring Schedules."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class GuardShiftTemplate(models.Model):
    """Simple template for creating recurring shift schedules."""
    
    _name = 'guard.shift.template'
    _description = 'Guard Shift Template'
    _order = 'name'
    
    name = fields.Char(
        string='Template Name',
        required=True,
        help='e.g., "Morning Security - Dubai Marina"'
    )
    
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True
    )
    
    shift_type = fields.Selection([
        ('day', 'Day Shift'),
        ('night', 'Night Shift'),
        ('swing', 'Swing Shift')
    ], string='Shift Type', required=True, default='day')
    
    start_time = fields.Float(
        string='Start Time',
        required=True,
        help='Hour of day (0-23.99)',
        default=8.0
    )
    
    duration_hours = fields.Float(
        string='Duration (Hours)',
        required=True,
        default=8.0
    )
    
    required_guards = fields.Integer(
        string='Required Guards',
        default=1,
        help='Number of guards needed per shift'
    )
    
    # Recurrence - Simple weekly pattern
    monday = fields.Boolean('Monday', default=True)
    tuesday = fields.Boolean('Tuesday', default=True)
    wednesday = fields.Boolean('Wednesday', default=True)
    thursday = fields.Boolean('Thursday', default=True)
    friday = fields.Boolean('Friday', default=True)
    saturday = fields.Boolean('Saturday', default=False)
    sunday = fields.Boolean('Sunday', default=False)
    
    # Assignment
    preferred_employee_ids = fields.Many2many(
        'hr.employee',
        string='Preferred Employees',
        help='Employees who are usually assigned to this shift'
    )
    
    tour_ids = fields.Many2many(
        'security.tour',
        string='Assigned Tours',
        help='Tours to complete during this shift'
    )
    
    special_requirements = fields.Text(
        string='Special Requirements'
    )
    
    instructions = fields.Html(
        string='Shift Instructions'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Inactive templates will not generate new shifts'
    )
    
    # Generation settings
    auto_generate_days_ahead = fields.Integer(
        string='Auto-generate Days Ahead',
        default=14,
        help='Automatically generate shifts this many days in advance'
    )
    
    last_generation_date = fields.Date(
        string='Last Generation Date',
        readonly=True
    )
    
    generated_shift_count = fields.Integer(
        string='Generated Shifts',
        compute='_compute_generated_shift_count'
    )
    
    @api.depends('site_id')
    def _compute_generated_shift_count(self):
        """Count shifts generated from this template."""
        for record in self:
            record.generated_shift_count = self.env['guard.shift.plan'].search_count([
                ('template_id', '=', record.id)
            ])
    
    @api.constrains('start_time')
    def _check_start_time(self):
        """Validate start time."""
        for record in self:
            if record.start_time < 0 or record.start_time >= 24:
                raise ValidationError(_('Start time must be between 0 and 24 hours.'))
    
    @api.constrains('duration_hours')
    def _check_duration(self):
        """Validate duration."""
        for record in self:
            if record.duration_hours <= 0:
                raise ValidationError(_('Duration must be greater than 0 hours.'))
            if record.duration_hours > 24:
                raise ValidationError(_('Duration cannot exceed 24 hours.'))
    
    @api.constrains('required_guards')
    def _check_required_guards(self):
        """Validate required guards."""
        for record in self:
            if record.required_guards <= 0:
                raise ValidationError(_('Required guards must be at least 1.'))
    
    def action_generate_shifts(self, start_date=None, end_date=None):
        """Generate shifts from template."""
        self.ensure_one()
        
        if not start_date:
            start_date = fields.Date.today()
        if not end_date:
            end_date = start_date + timedelta(days=self.auto_generate_days_ahead)
        
        ShiftPlan = self.env['guard.shift.plan']
        shifts_created = []
        current_date = start_date
        
        while current_date <= end_date:
            # Check if shift should be created on this day
            if self._should_create_shift(current_date):
                # Create shift datetime in user's timezone, then convert to UTC
                user_tz = self.env.user.tz or 'UTC'
                from datetime import time as dt_time
                
                # Create datetime in user's timezone
                hours = int(self.start_time)
                minutes = int(round((self.start_time - hours) * 60))
                local_dt = datetime.combine(current_date, dt_time(hour=hours, minute=minutes))
                
                # Convert to UTC for database storage
                if user_tz and user_tz != 'UTC':
                    try:
                        import pytz
                        tz = pytz.timezone(user_tz)
                        local_dt = tz.localize(local_dt, is_dst=None)
                        shift_datetime = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
                    except Exception:
                        shift_datetime = local_dt
                else:
                    shift_datetime = local_dt
                
                # Create day boundaries in UTC for search
                day_start = fields.Datetime.to_datetime(current_date)
                day_end = day_start + timedelta(days=1)
                
                # Convert boundaries to user's timezone then UTC for consistent comparison
                if user_tz and user_tz != 'UTC':
                    try:
                        import pytz
                        tz = pytz.timezone(user_tz)
                        local_day_start = tz.localize(datetime.combine(current_date, datetime.min.time()), is_dst=None)
                        local_day_end = tz.localize(datetime.combine(current_date + timedelta(days=1), datetime.min.time()), is_dst=None)
                        day_start = local_day_start.astimezone(pytz.UTC).replace(tzinfo=None)
                        day_end = local_day_end.astimezone(pytz.UTC).replace(tzinfo=None)
                    except Exception:
                        pass
                
                existing = ShiftPlan.search([
                    ('site_id', '=', self.site_id.id),
                    ('start_datetime', '>=', day_start),
                    ('start_datetime', '<', day_end),
                    ('template_id', '=', self.id)
                ])
                
                if not existing:
                    # Create shifts for required guards
                    for i in range(self.required_guards):
                        # Try to assign preferred employee if available
                        employee = None
                        if self.preferred_employee_ids:
                            # Simple round-robin assignment
                            idx = i % len(self.preferred_employee_ids)
                            employee = self.preferred_employee_ids[idx]
                        
                        if employee:
                            # Check if employee already has a shift
                            conflicts = ShiftPlan.search([
                                ('employee_id', '=', employee.id),
                                ('start_datetime', '>=', shift_datetime),
                                ('start_datetime', '<', shift_datetime + timedelta(hours=self.duration_hours)),
                                ('status', '!=', 'cancelled')
                            ])
                            if conflicts:
                                employee = None  # Will need manual assignment
                        
                        shift = ShiftPlan.create({
                            'site_id': self.site_id.id,
                            'employee_id': employee.id if employee else False,
                            'start_datetime': shift_datetime,
                            'end_datetime': shift_datetime + timedelta(hours=self.duration_hours),
                            'shift_type': self.shift_type,
                            'tour_ids': [(6, 0, self.tour_ids.ids)],
                            'special_requirements': self.special_requirements,
                            'instructions': self.instructions,
                            'template_id': self.id,
                            'status': 'draft'
                        })
                        shifts_created.append(shift.id)
            
            current_date += timedelta(days=1)
        
        self.last_generation_date = fields.Date.today()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d shifts created from template "%s"') % (len(shifts_created), self.name),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _should_create_shift(self, date):
        """Check if shift should be created on given date."""
        weekday = date.weekday()  # 0=Monday, 6=Sunday
        weekday_fields = ['monday', 'tuesday', 'wednesday', 'thursday', 
                        'friday', 'saturday', 'sunday']
        return getattr(self, weekday_fields[weekday])
    
    @api.model
    def cron_generate_shifts(self):
        """Cron job to auto-generate shifts from active templates."""
        templates = self.search([('active', '=', True)])
        
        for template in templates:
            try:
                template.action_generate_shifts()
                _logger.info('Generated shifts for template: %s', template.name)
            except Exception as e:
                _logger.error('Failed to generate shifts from template %s: %s', 
                             template.name, str(e))
        
        return True
    
    def action_view_generated_shifts(self):
        """View shifts generated from this template."""
        self.ensure_one()
        return {
            'name': _('Shifts from Template: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.shift.plan',
            'view_mode': 'list,form,calendar',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id}
        }

