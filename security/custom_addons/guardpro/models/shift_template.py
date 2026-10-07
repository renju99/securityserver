# -*- coding: utf-8 -*-
"""Shift Template for Recurring Schedules."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, time as dt_time
from calendar import monthrange
import logging
import pytz

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
        string='Project',
        required=True,
        ondelete='restrict',
    )

    shift_type = fields.Selection([
        ('day', 'Day Shift'),
        ('night', 'Night Shift'),
        ('swing', 'Swing Shift'),
        ('split', 'Split Shift')
    ], string='Shift Type', required=True, default='day')

    start_time = fields.Float(
        string='Start Time',
        required=True,
        default=8.0,
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
        default=1,
        help='For monthly recurrence (1-31)'
    )

    # Guard Assignment
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=False,
        help='Deprecated: use Guards instead',
    )

    guard_ids = fields.Many2many(
        'guard.profile',
        string='Guards',
        required=False,
        help='Guards to assign to shifts generated from this template'
    )

    tour_ids = fields.Many2many(
        'security.tour',
        'shift_template_tour_rel',
        'template_id',
        'tour_id',
        string='Assigned Tours',
        domain="[('site_id', '=', site_id)]",
        help='Tours to complete during shifts generated from this template',
    )

    special_instructions = fields.Text(
        string='Special Instructions'
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Inactive templates will not generate new shifts'
    )

    last_generation_date = fields.Date(
        string='Last Generation Date',
        readonly=True
    )

    generation_start_date = fields.Date(
        string='From Date',
        default=fields.Date.today,
        help='Start date for manual shift generation'
    )

    generation_end_date = fields.Date(
        string='To Date',
        default=lambda self: fields.Date.today() + timedelta(days=13),
        help='End date for manual shift generation'
    )

    generated_shift_count = fields.Integer(
        string='Generated Shifts',
        compute='_compute_generated_shift_count',
        help='Number of shifts generated from this template'
    )

    preview_shift_count = fields.Integer(
        string='Will create',
        compute='_compute_preview_shift_count',
        help='Estimated shifts for the selected date range × guards'
    )

    preview_date_count = fields.Integer(
        string='Matching days',
        compute='_compute_preview_shift_count',
    )

    @api.depends('site_id')
    def _compute_generated_shift_count(self):
        for record in self:
            record.generated_shift_count = self.env['guard.shift'].search_count([
                ('template_id', '=', record.id)
            ])

    @api.depends(
        'generation_start_date', 'generation_end_date', 'recurrence_type',
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
        'day_of_month', 'guard_ids', 'guard_id',
    )
    def _compute_preview_shift_count(self):
        for record in self:
            guards = record._get_template_guards()
            start = record.generation_start_date
            end = record.generation_end_date
            if not start or not end or end < start or not guards:
                record.preview_date_count = 0
                record.preview_shift_count = 0
                continue
            dates = list(record._iter_matching_dates(start, end))
            record.preview_date_count = len(dates)
            record.preview_shift_count = len(dates) * len(guards)

    def _get_template_guards(self):
        self.ensure_one()
        if self.guard_ids:
            return self.guard_ids
        if self.guard_id:
            return self.guard_id
        return self.env['guard.profile']

    @api.constrains('start_time')
    def _check_start_time(self):
        for record in self:
            if record.start_time < 0 or record.start_time >= 24:
                raise ValidationError(_('Start time must be between 0 and 24 hours.'))

    @api.constrains('duration_hours')
    def _check_duration(self):
        for record in self:
            if record.duration_hours <= 0:
                raise ValidationError(_('Duration must be greater than 0 hours.'))
            if record.duration_hours > 24:
                raise ValidationError(_('Duration cannot exceed 24 hours.'))

    @api.constrains('day_of_month')
    def _check_day_of_month(self):
        for record in self:
            if record.recurrence_type == 'monthly':
                if not record.day_of_month or record.day_of_month < 1 or record.day_of_month > 31:
                    raise ValidationError(_('Day of month must be between 1 and 31 for monthly recurrence.'))

    @api.constrains('generation_start_date', 'generation_end_date')
    def _check_generation_dates(self):
        for record in self:
            if record.generation_start_date and record.generation_end_date:
                if record.generation_end_date < record.generation_start_date:
                    raise ValidationError(_('End date must be after start date.'))

    # -------------------------------------------------------------------------
    # Quick presets
    # -------------------------------------------------------------------------

    def action_preset_day_mon_fri(self):
        """Day shift 08:00–16:00, Mon–Fri."""
        for record in self:
            record.write({
                'shift_type': 'day',
                'start_time': 8.0,
                'duration_hours': 8.0,
                'recurrence_type': 'weekly',
                'monday': True,
                'tuesday': True,
                'wednesday': True,
                'thursday': True,
                'friday': True,
                'saturday': False,
                'sunday': False,
            })
        return True

    def action_preset_night_mon_fri(self):
        """Night shift 20:00–08:00, Mon–Fri."""
        for record in self:
            record.write({
                'shift_type': 'night',
                'start_time': 20.0,
                'duration_hours': 12.0,
                'recurrence_type': 'weekly',
                'monday': True,
                'tuesday': True,
                'wednesday': True,
                'thursday': True,
                'friday': True,
                'saturday': False,
                'sunday': False,
            })
        return True

    def action_preset_daily_all(self):
        """Daily every day of the week."""
        for record in self:
            record.write({
                'recurrence_type': 'daily',
                'monday': True,
                'tuesday': True,
                'wednesday': True,
                'thursday': True,
                'friday': True,
                'saturday': True,
                'sunday': True,
            })
        return True

    def action_preset_dates_this_week(self):
        today = fields.Date.today()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        self.write({
            'generation_start_date': start,
            'generation_end_date': end,
        })
        return True

    def action_preset_dates_next_14(self):
        today = fields.Date.today()
        self.write({
            'generation_start_date': today,
            'generation_end_date': today + timedelta(days=13),
        })
        return True

    def action_preset_dates_next_month(self):
        today = fields.Date.today()
        if today.month == 12:
            first_next = today.replace(year=today.year + 1, month=1, day=1)
        else:
            first_next = today.replace(month=today.month + 1, day=1)
        last_day = monthrange(first_next.year, first_next.month)[1]
        end = first_next.replace(day=last_day)
        self.write({
            'generation_start_date': first_next,
            'generation_end_date': end,
        })
        return True

    def action_copy_template(self):
        """Duplicate this template for another site/guards."""
        self.ensure_one()
        copy = self.copy({
            'name': _('%s (copy)') % self.name,
            'last_generation_date': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Shift Template'),
            'res_model': 'shift.template',
            'res_id': copy.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # -------------------------------------------------------------------------
    # Generation
    # -------------------------------------------------------------------------

    def _iter_matching_dates(self, start_date, end_date, ignore_recurrence=False):
        """Yield each date in range that matches the recurrence pattern."""
        self.ensure_one()
        current = start_date
        while current <= end_date:
            if ignore_recurrence or self._should_create_shift(current):
                yield current
            current += timedelta(days=1)

    def _should_create_shift(self, date):
        """Check if shift should be created on given date."""
        if self.recurrence_type == 'daily':
            return True
        if self.recurrence_type == 'weekly':
            weekday = date.weekday()  # 0=Monday, 6=Sunday
            weekday_fields = [
                'monday', 'tuesday', 'wednesday', 'thursday',
                'friday', 'saturday', 'sunday',
            ]
            return bool(getattr(self, weekday_fields[weekday]))
        if self.recurrence_type == 'monthly':
            target = self.day_of_month or 1
            # Cap to last day of month (e.g. 31 in February → 28/29)
            last = monthrange(date.year, date.month)[1]
            return date.day == min(target, last)
        return False

    def action_generate_shifts(self, start_date=None, end_date=None, ignore_recurrence=False):
        """
        Generate shifts from template for the assigned guards.

        Walks day-by-day and creates a shift on every matching date
        (Mon–Fri weekly templates create Mon–Fri shifts, not one weekday).
        """
        self.ensure_one()

        guards = self._get_template_guards()
        if not guards:
            raise ValidationError(_(
                'Please select at least one guard for this template before generating shifts.'
            ))

        if not start_date:
            start_date = fields.Date.today()
        if not end_date:
            end_date = start_date + timedelta(days=13)
        if end_date < start_date:
            raise ValidationError(_('End date must be after start date.'))

        matching_dates = list(self._iter_matching_dates(
            start_date, end_date, ignore_recurrence=ignore_recurrence))
        if not matching_dates:
            raise ValidationError(_(
                'No matching days in this date range for the selected recurrence pattern.'
            ))

        shifts_created = []
        shifts_updated = []
        tour_ids = self.tour_ids.ids

        for guard in guards:
            for current_date in matching_dates:
                self._register_shift_result(
                    self._create_shift_for_date(
                        current_date, guard, tour_ids=tour_ids),
                    shifts_created, shifts_updated)

        self.last_generation_date = fields.Date.today()

        if len(guards) == 1:
            guard_names = guards[0].name
        else:
            guard_names = _('%d guards') % len(guards)

        message_parts = []
        if shifts_created:
            message_parts.append(_('%d shift(s) created') % len(shifts_created))
        if shifts_updated:
            message_parts.append(
                _('%d existing shift(s) updated with template tours') % len(shifts_updated))
        if not message_parts:
            message_parts.append(_('No shifts were created or updated.'))

        all_ids = shifts_created + shifts_updated
        # Nested params.next is NOT passed through clean_action(), so views must
        # be explicit — otherwise the web client crashes on action.views.map.
        open_action = {
            'type': 'ir.actions.act_window',
            'name': _('Shifts from %s') % self.name,
            'res_model': 'guard.shift',
            'view_mode': 'list,form,calendar',
            'views': [(False, 'list'), (False, 'form'), (False, 'calendar')],
            'domain': [('id', 'in', all_ids)] if all_ids else [('template_id', '=', self.id)],
            'context': {'create': False},
            'target': 'current',
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shifts generated'),
                'message': _('%s from template "%s" for %s') % (
                    '; '.join(message_parts), self.name, guard_names),
                'type': 'success',
                'sticky': False,
                'next': open_action,
            }
        }

    def _register_shift_result(self, result, shifts_created, shifts_updated):
        """Track created vs updated shifts from template generation."""
        shift, created = result
        if not shift:
            return
        if created:
            shifts_created.append(shift.id)
        else:
            shifts_updated.append(shift.id)

    def _create_shift_for_date(self, current_date, guard=None, tour_ids=None):
        """
        Create or update a shift for the given date.

        Returns:
            tuple (guard.shift|False, created_bool)
        """
        if not guard:
            guard = self.guard_id
        if not guard:
            return False, False

        if tour_ids is None:
            tour_ids = self.tour_ids.ids

        user_tz = self.env.user.tz or 'UTC'
        hours = int(self.start_time)
        minutes = int(round((self.start_time - hours) * 60))
        local_dt = datetime.combine(current_date, dt_time(hour=hours, minute=minutes))

        if user_tz and user_tz != 'UTC':
            try:
                tz = pytz.timezone(user_tz)
                local_dt = tz.localize(local_dt, is_dst=None)
                utc_dt = local_dt.astimezone(pytz.UTC)
                shift_datetime = utc_dt.replace(tzinfo=None)
            except Exception as e:
                _logger.warning('Error converting timezone for shift creation: %s', str(e))
                shift_datetime = local_dt
        else:
            shift_datetime = local_dt

        day_start = fields.Datetime.to_datetime(current_date)
        day_end = day_start + timedelta(days=1)
        if user_tz and user_tz != 'UTC':
            try:
                tz = pytz.timezone(user_tz)
                local_day_start = tz.localize(
                    datetime.combine(current_date, datetime.min.time()), is_dst=None)
                local_day_end = tz.localize(
                    datetime.combine(current_date + timedelta(days=1), datetime.min.time()),
                    is_dst=None)
                day_start = local_day_start.astimezone(pytz.UTC).replace(tzinfo=None)
                day_end = local_day_end.astimezone(pytz.UTC).replace(tzinfo=None)
            except Exception:
                pass

        existing = self.env['guard.shift'].search([
            ('guard_id', '=', guard.id),
            ('site_id', '=', self.site_id.id),
            ('start_datetime', '>=', day_start),
            ('start_datetime', '<', day_end),
            ('template_id', '=', self.id)
        ])

        if existing:
            existing.write({'tour_ids': [(6, 0, tour_ids)]})
            return existing, False

        end_datetime = shift_datetime + timedelta(hours=self.duration_hours)
        shift = self.env['guard.shift'].create({
            'site_id': self.site_id.id,
            'guard_id': guard.id,
            'start_datetime': shift_datetime,
            'end_datetime': end_datetime,
            'shift_type': 'regular',
            'tour_ids': [(6, 0, tour_ids)],
            'notes': self.special_instructions,
            'template_id': self.id,
            'status': 'scheduled'
        })
        return shift, True

    def action_generate_shifts_from_form(self):
        """Generate shifts using the date fields from the form."""
        self.ensure_one()
        guards = self._get_template_guards()
        if not guards:
            raise ValidationError(_(
                'Please select at least one guard for this template before generating shifts.'
            ))
        if not self.generation_start_date or not self.generation_end_date:
            raise ValidationError(_(
                'Please specify both From Date and To Date before generating shifts.'
            ))
        return self.action_generate_shifts(
            start_date=self.generation_start_date,
            end_date=self.generation_end_date,
            ignore_recurrence=False,
        )

    def action_open_generate_wizard(self):
        """Open generate wizard with presets and preview."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Shifts'),
            'res_model': 'shift.template.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'default_template_id': self.id,
            },
        }

    def action_view_generated_shifts(self):
        """View shifts generated from this template."""
        self.ensure_one()
        return {
            'name': _('Shifts from Template: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.shift',
            'view_mode': 'list,form,calendar',
            'views': [(False, 'list'), (False, 'form'), (False, 'calendar')],
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
