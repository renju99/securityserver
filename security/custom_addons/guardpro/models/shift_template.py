# -*- coding: utf-8 -*-
"""Shift Template for Recurring Schedules."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from calendar import monthrange
import logging

_logger = logging.getLogger(__name__)


class ShiftTemplate(models.Model):
    """Template for creating recurring shifts."""
    
    _name = 'shift.template'
    _description = 'Shift Template'
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
        ('swing', 'Swing Shift'),
        ('split', 'Split Shift')
    ], string='Shift Type', required=True)
    
    start_time = fields.Float(
        string='Start Time',
        required=True,
        help='Hour of day (0-23.99)'
    )
    
    duration_hours = fields.Float(
        string='Duration (Hours)',
        required=True,
        default=8.0
    )
    
    # Recurrence settings
    recurrence_type = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly')
    ], string='Recurrence', required=True, default='weekly')
    
    monday = fields.Boolean('Monday', default=True)
    tuesday = fields.Boolean('Tuesday', default=True)
    wednesday = fields.Boolean('Wednesday', default=True)
    thursday = fields.Boolean('Thursday', default=True)
    friday = fields.Boolean('Friday', default=True)
    saturday = fields.Boolean('Saturday', default=False)
    sunday = fields.Boolean('Sunday', default=False)
    
    day_of_month = fields.Integer(
        string='Day of Month',
        help='For monthly recurrence (1-31)'
    )
    
    # Guard Assignment
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=False,  # Deprecated - use guard_ids instead
        help='Guard to assign to shifts generated from this template (Deprecated: Use Guards field instead)'
    )
    
    guard_ids = fields.Many2many(
        'guard.profile',
        string='Guards',
        required=False,
        help='Guards to assign to shifts generated from this template'
    )
    
    tour_id = fields.Many2one(
        'security.tour',
        string='Assigned Tour',
        domain="[('site_id', '=', site_id)]"
    )
    
    special_instructions = fields.Text(
        string='Special Instructions'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Inactive templates will not generate new shifts'
    )
    
    # Generation settings
    last_generation_date = fields.Date(
        string='Last Generation Date',
        readonly=True
    )
    
    # Manual generation date range
    generation_start_date = fields.Date(
        string='From Date',
        help='Start date for manual shift generation'
    )
    
    generation_end_date = fields.Date(
        string='To Date',
        help='End date for manual shift generation'
    )
    
    generated_shift_count = fields.Integer(
        string='Generated Shifts',
        compute='_compute_generated_shift_count',
        help='Number of shifts generated from this template'
    )
    
    @api.depends('site_id')
    def _compute_generated_shift_count(self):
        """Count shifts generated from this template."""
        for record in self:
            record.generated_shift_count = self.env['guard.shift'].search_count([
                ('template_id', '=', record.id)
            ])
    
    @api.constrains('start_time')
    def _check_start_time(self):
        """Validate start time is within 0-24 hours."""
        for record in self:
            if record.start_time < 0 or record.start_time >= 24:
                raise ValidationError(_('Start time must be between 0 and 24 hours.'))
    
    @api.constrains('duration_hours')
    def _check_duration(self):
        """Validate duration is positive."""
        for record in self:
            if record.duration_hours <= 0:
                raise ValidationError(_('Duration must be greater than 0 hours.'))
            if record.duration_hours > 24:
                raise ValidationError(_('Duration cannot exceed 24 hours.'))
    
    @api.constrains('day_of_month')
    def _check_day_of_month(self):
        """Validate day of month."""
        for record in self:
            if record.recurrence_type == 'monthly':
                if not record.day_of_month or record.day_of_month < 1 or record.day_of_month > 31:
                    raise ValidationError(_('Day of month must be between 1 and 31 for monthly recurrence.'))
    
    def action_generate_shifts(self, start_date=None, end_date=None, ignore_recurrence=False):
        """
        Generate shifts from template for the assigned guards.
        
        Args:
            start_date: Start date for shift generation (defaults to today)
            end_date: End date for shift generation (defaults to start_date + auto_generate_days_ahead)
            ignore_recurrence: If True, generate shifts for all days in range, ignoring recurrence pattern
                              If False, respect the recurrence pattern:
                              - Daily: Create shifts for every day in range
                              - Weekly: Create only 1 shift (first matching weekday in range)
                              - Monthly: Create only 1 shift (first matching day of month in range)
        """
        self.ensure_one()
        
        # Support both old guard_id field and new guard_ids field for backwards compatibility
        guards = self.guard_ids if self.guard_ids else (self.guard_id if self.guard_id else self.env['guard.profile'])
        
        if not guards:
            raise ValidationError(_('Please select at least one guard for this template before generating shifts.'))
        
        if not start_date:
            start_date = fields.Date.today()
        if not end_date:
            # Default to 30 days if not specified
            end_date = start_date + timedelta(days=30)
        
        shifts_created = []
        
        # Generate shifts for each guard
        for guard in guards:
            if ignore_recurrence:
                # Generate for all days in range
                current_date = start_date
                while current_date <= end_date:
                    shift = self._create_shift_for_date(current_date, guard)
                    if shift:
                        shifts_created.append(shift.id)
                    current_date += timedelta(days=1)
            else:
                # Respect recurrence pattern, starting from start_date
                if self.recurrence_type == 'daily':
                    # Daily: Create shifts for every day from start_date to end_date
                    current_date = start_date
                    while current_date <= end_date:
                        shift = self._create_shift_for_date(current_date, guard)
                        if shift:
                            shifts_created.append(shift.id)
                        current_date += timedelta(days=1)
                elif self.recurrence_type == 'weekly':
                    # Weekly: Create shifts every 7 days starting from start_date
                    # Check if start_date matches the selected weekday(s)
                    if self._should_create_shift(start_date):
                        current_date = start_date
                        while current_date <= end_date:
                            shift = self._create_shift_for_date(current_date, guard)
                            if shift:
                                shifts_created.append(shift.id)
                            # Move to next week (7 days later)
                            current_date += timedelta(days=7)
                    else:
                        # If start_date doesn't match, find first matching weekday
                        current_date = start_date
                        found_first = False
                        while current_date <= end_date:
                            if self._should_create_shift(current_date):
                                found_first = True
                                break
                            current_date += timedelta(days=1)
                        
                        # Create shifts every 7 days from the first matching date
                        if found_first:
                            while current_date <= end_date:
                                shift = self._create_shift_for_date(current_date, guard)
                                if shift:
                                    shifts_created.append(shift.id)
                                current_date += timedelta(days=7)
                elif self.recurrence_type == 'monthly':
                    # Monthly: Create shifts on the same day of month, starting from start_date
                    # Use the day of start_date as the reference
                    reference_day = start_date.day
                    current_date = start_date
                    
                    while current_date <= end_date:
                        # Check if current date matches the day of month
                        if current_date.day == reference_day:
                            shift = self._create_shift_for_date(current_date, guard)
                            if shift:
                                shifts_created.append(shift.id)
                        
                        # Move to next month
                        # Calculate next month's date with same day
                        if current_date.month == 12:
                            next_month = current_date.replace(year=current_date.year + 1, month=1, day=reference_day)
                        else:
                            try:
                                next_month = current_date.replace(month=current_date.month + 1, day=reference_day)
                            except ValueError:
                                # Handle case where next month doesn't have that day (e.g., Jan 31 -> Feb 31)
                                # Move to last day of next month
                                if current_date.month == 12:
                                    next_month = current_date.replace(year=current_date.year + 1, month=1, day=1)
                                else:
                                    next_month = current_date.replace(month=current_date.month + 1, day=1)
                                # Get last day of that month
                                last_day = monthrange(next_month.year, next_month.month)[1]
                                next_month = next_month.replace(day=last_day)
                        
                        current_date = next_month
        
        self.last_generation_date = fields.Date.today()
        
        # Format guard names for message
        if len(guards) == 1:
            guard_names = guards[0].name
        else:
            guard_names = _('%d guards') % len(guards)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d shifts created from template "%s" for %s') % (
                    len(shifts_created), self.name, guard_names
                ),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _should_create_shift(self, date):
        """Check if shift should be created on given date."""
        if self.recurrence_type == 'daily':
            return True
        elif self.recurrence_type == 'weekly':
            weekday = date.weekday()  # 0=Monday, 6=Sunday
            weekday_fields = ['monday', 'tuesday', 'wednesday', 'thursday', 
                            'friday', 'saturday', 'sunday']
            return getattr(self, weekday_fields[weekday])
        elif self.recurrence_type == 'monthly':
            return date.day == self.day_of_month
        
        return False
    
    def _create_shift_for_date(self, current_date, guard=None):
        """
        Create a shift for the given date if it doesn't already exist.
        
        Args:
            current_date: Date to create shift for
            guard: guard.profile record to assign (defaults to self.guard_id for backwards compatibility)
            
        Returns:
            guard.shift record if created, False if already exists or creation failed
        """
        # Support backwards compatibility with single guard_id field
        if not guard:
            guard = self.guard_id
        
        if not guard:
            return False
        # Create datetime in user's timezone, then convert to UTC for storage
        # Use Odoo's datetime utilities to handle timezone properly
        user_tz = self.env.user.tz or 'UTC'
        
        # Create a time object from the start_time float
        # start_time is stored as float (e.g., 7.0 for 7:00, 7.5 for 7:30)
        hours = int(self.start_time)
        minutes = int(round((self.start_time - hours) * 60))
        
        # Create datetime in user's timezone
        from datetime import time as dt_time
        import pytz
        
        # Create naive datetime representing the time in user's timezone
        local_dt = datetime.combine(current_date, dt_time(hour=hours, minute=minutes))
        
        # Convert to UTC for database storage using Odoo's method
        # Odoo stores datetimes in UTC, so we need to convert from user's timezone to UTC
        if user_tz and user_tz != 'UTC':
            try:
                tz = pytz.timezone(user_tz)
                # Localize the naive datetime to user's timezone
                local_dt = tz.localize(local_dt, is_dst=None)
                # Convert to UTC
                utc_dt = local_dt.astimezone(pytz.UTC)
                # Remove timezone info to get naive datetime (Odoo expects naive datetime)
                shift_datetime = utc_dt.replace(tzinfo=None)
            except Exception as e:
                _logger.warning('Error converting timezone for shift creation: %s', str(e))
                # Fallback: use naive datetime as-is
                shift_datetime = local_dt
        else:
            # No timezone or UTC - use as-is
            shift_datetime = local_dt
        
        # Check if shift already exists for this guard on this date
        # Use Odoo's datetime utilities to create day boundaries in UTC
        day_start = fields.Datetime.to_datetime(current_date)
        day_end = day_start + timedelta(days=1)
        
        # Convert day boundaries to user's timezone first, then to UTC for consistent comparison
        # This ensures we're comparing within the same day in user's timezone
        if user_tz and user_tz != 'UTC':
            try:
                tz = pytz.timezone(user_tz)
                # Create boundaries in user's timezone
                local_day_start = tz.localize(datetime.combine(current_date, datetime.min.time()), is_dst=None)
                local_day_end = tz.localize(datetime.combine(current_date + timedelta(days=1), datetime.min.time()), is_dst=None)
                # Convert to UTC for database comparison
                day_start = local_day_start.astimezone(pytz.UTC).replace(tzinfo=None)
                day_end = local_day_end.astimezone(pytz.UTC).replace(tzinfo=None)
            except Exception:
                # Fallback to UTC boundaries
                pass
        
        existing = self.env['guard.shift'].search([
            ('guard_id', '=', guard.id),
            ('site_id', '=', self.site_id.id),
            ('start_datetime', '>=', day_start),
            ('start_datetime', '<', day_end),
            ('template_id', '=', self.id)
        ])
        
        if existing:
            return False
        
        # Calculate end datetime (already in UTC)
        end_datetime = shift_datetime + timedelta(hours=self.duration_hours)
        
        shift = self.env['guard.shift'].create({
            'site_id': self.site_id.id,
            'guard_id': guard.id,
            'start_datetime': shift_datetime,
            'end_datetime': end_datetime,
            'shift_type': 'regular',  # Template-generated shifts are regular scheduled shifts
            'tour_ids': [(6, 0, [self.tour_id.id])] if self.tour_id else False,
            'notes': self.special_instructions,
            'template_id': self.id,
            'status': 'scheduled'
        })
        
        return shift
    
    
    def action_generate_shifts_from_form(self):
        """Generate shifts using the date fields from the form."""
        self.ensure_one()
        
        # Support both old guard_id field and new guard_ids field
        guards = self.guard_ids if self.guard_ids else (self.guard_id if self.guard_id else self.env['guard.profile'])
        
        if not guards:
            raise ValidationError(_('Please select at least one guard for this template before generating shifts.'))
        
        if not self.generation_start_date or not self.generation_end_date:
            raise ValidationError(_('Please specify both From Date and To Date before generating shifts.'))
        
        start_date = self.generation_start_date
        end_date = self.generation_end_date
        
        if end_date < start_date:
            raise ValidationError(_('End date must be after start date.'))
        
        return self.action_generate_shifts(
            start_date=start_date,
            end_date=end_date,
            ignore_recurrence=False
        )
    
    
    def action_view_generated_shifts(self):
        """View shifts generated from this template."""
        self.ensure_one()
        return {
            'name': _('Shifts from Template: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.shift',
            'view_mode': 'list,form,calendar',
            'domain': [('template_id', '=', self.id)],
            'context': {'search_default_group_by_status': 1}
        }


class GuardShift(models.Model):
    """Inherit guard.shift to add template_id field."""
    
    _inherit = 'guard.shift'
    
    template_id = fields.Many2one(
        'shift.template',
        string='Created from Template',
        readonly=True,
        ondelete='set null',
        help='The template that was used to create this shift'
    )

