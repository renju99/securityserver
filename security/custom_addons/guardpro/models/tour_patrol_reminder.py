# -*- coding: utf-8 -*-
"""Patrol reminders (30 / 10 minutes before shift start) per assigned tour, mobile ack."""

from datetime import timedelta

from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class TourPatrolReminder(models.Model):
    """One popup per (shift, tour, 30|10): timed from shift start, guard must acknowledge."""

    _name = 'tour.patrol.reminder'
    _description = 'Patrol Reminder (ack required)'
    _order = 'scheduled_start asc, reminder_type desc, id asc'

    shift_id = fields.Many2one(
        'guard.shift',
        string='Shift',
        required=True,
        ondelete='cascade',
        index=True,
    )
    tour_id = fields.Many2one(
        'security.tour',
        string='Tour',
        required=True,
        ondelete='cascade',
        index=True,
    )
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True,
    )
    reminder_type = fields.Selection(
        [('30', '30 minutes before shift'), ('10', '10 minutes before shift')],
        string='Reminder',
        required=True,
    )
    scheduled_start = fields.Datetime(
        string='Shift start (reminder reference)',
        related='shift_id.start_datetime',
        store=True,
        readonly=True,
    )
    is_acknowledged = fields.Boolean(default=False, index=True)
    acknowledged_date = fields.Datetime(string='Acknowledged At', readonly=True)

    _sql_constraints = [
        (
            'tour_patrol_reminder_shift_tour_type_uniq',
            'unique(shift_id, tour_id, reminder_type)',
            'A reminder of this type already exists for this tour on this shift.',
        ),
    ]

    def action_acknowledge(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.is_acknowledged:
                rec.write({
                    'is_acknowledged': True,
                    'acknowledged_date': now,
                })

    @api.model
    def cron_create_from_shifts(self):
        """Create pending reminders when shift start is ~30 or ~10 minutes away (per assigned tour)."""
        Shift = self.env['guard.shift'].sudo()
        now = fields.Datetime.now()
        for minutes_before, code in ((30, '30'), (10, '10')):
            low = now + timedelta(minutes=minutes_before - 5)
            high = now + timedelta(minutes=minutes_before + 5)
            shifts = Shift.search([
                ('start_datetime', '>=', low),
                ('start_datetime', '<=', high),
                ('status', 'in', ('scheduled', 'confirmed', 'in_progress')),
            ])
            for shift in shifts:
                if not shift.tour_ids:
                    continue
                for tour in shift.tour_ids:
                    try:
                        self.create_for_shift_tour_if_needed(shift, tour, code)
                    except Exception as err:
                        _logger.exception(
                            'Patrol reminder cron failed shift=%s tour=%s (%s): %s',
                            shift.id,
                            tour.id,
                            code,
                            err,
                        )
        return True

    @api.model
    def create_for_shift_tour_if_needed(self, shift, tour, reminder_type):
        """Enqueue a reminder for this shift’s guard only."""
        Reminder = self.sudo()
        if Reminder.search_count([
            ('shift_id', '=', shift.id),
            ('tour_id', '=', tour.id),
            ('reminder_type', '=', reminder_type),
        ]):
            return Reminder.browse()

        if shift.status in ('cancelled', 'no_show', 'completed'):
            return Reminder.browse()
        if shift.end_datetime and shift.end_datetime < fields.Datetime.now():
            return Reminder.browse()
        guard = shift.guard_id
        if not guard or not guard.user_id:
            return Reminder.browse()
        if tour not in shift.tour_ids:
            return Reminder.browse()
        if not shift.start_datetime:
            return Reminder.browse()

        if Reminder._patrol_already_started(shift, tour):
            return Reminder.browse()

        return Reminder.create({
            'shift_id': shift.id,
            'tour_id': tour.id,
            'guard_id': guard.id,
            'user_id': guard.user_id.id,
            'reminder_type': reminder_type,
        })

    @api.model
    def _patrol_already_started(self, shift, tour):
        """Skip if this tour was already started on this shift by shift start time."""
        return bool(self.env['tour.log'].sudo().search([
            ('guard_id', '=', shift.guard_id.id),
            ('tour_id', '=', tour.id),
            ('shift_id', '=', shift.id),
            ('status', 'in', ('in_progress', 'completed')),
            ('start_time', '<=', shift.start_datetime),
        ], limit=1))

    def is_stale_or_obsolete(self):
        """Hide popup if shift started long ago or tour already in progress."""
        self.ensure_one()
        now = fields.Datetime.now()
        ref = self.shift_id.start_datetime or self.scheduled_start
        if ref and ref < now - timedelta(hours=1):
            return True
        if self.env['tour.log'].sudo().search_count([
            ('guard_id', '=', self.guard_id.id),
            ('tour_id', '=', self.tour_id.id),
            ('shift_id', '=', self.shift_id.id),
            ('status', '=', 'in_progress'),
        ]):
            return True
        return False

    @api.model
    def get_pending_mobile_reminder(self, user):
        """Next reminder for this user (own shift tours only)."""
        reminders = self.sudo().search([
            ('user_id', '=', user.id),
            ('is_acknowledged', '=', False),
        ], order='create_date asc, id asc', limit=50)
        for rec in reminders:
            if rec.is_stale_or_obsolete():
                continue
            return rec
        return self.browse()
