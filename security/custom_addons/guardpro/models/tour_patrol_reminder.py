# -*- coding: utf-8 -*-
"""Patrol reminders (30 / 10 minutes before shift start) per assigned tour, mobile ack."""

from datetime import timedelta

from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)

# How long after the exact due moment a reminder may still surface.
# Outside this window it is treated as missed / stale (never pile up).
DUE_WINDOW_MINUTES = 8


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

    def _due_at(self):
        """Exact moment this reminder should fire (shift start − N minutes)."""
        self.ensure_one()
        start = self.shift_id.start_datetime or self.scheduled_start
        if not start or not self.reminder_type:
            return False
        try:
            minutes = int(self.reminder_type)
        except (TypeError, ValueError):
            return False
        return start - timedelta(minutes=minutes)

    def is_due_now(self, now=None):
        """True only inside the short window after the due moment."""
        self.ensure_one()
        now = now or fields.Datetime.now()
        due_at = self._due_at()
        if not due_at:
            return False
        window_end = due_at + timedelta(minutes=DUE_WINDOW_MINUTES)
        return due_at <= now <= window_end

    def is_past_due_window(self, now=None):
        """True once the show-window has passed (missed / too late)."""
        self.ensure_one()
        now = now or fields.Datetime.now()
        due_at = self._due_at()
        if not due_at:
            return True
        return now > due_at + timedelta(minutes=DUE_WINDOW_MINUTES)

    @api.model
    def cron_create_from_shifts(self):
        """Create pending reminders only when the due moment is reached (±2 min)."""
        Shift = self.env['guard.shift'].sudo()
        now = fields.Datetime.now()
        # Narrow creation window so rows appear only at firing time.
        for minutes_before, code in ((30, '30'), (10, '10')):
            low = now + timedelta(minutes=minutes_before - 2)
            high = now + timedelta(minutes=minutes_before + 2)
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
        # Auto-clear missed / obsolete backlog so it never floods mobile.
        self._auto_ack_missed_and_stale()
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
        """Hide / skip if past due window, shift dead, or tour already running."""
        self.ensure_one()
        now = fields.Datetime.now()
        shift = self.shift_id
        if not shift:
            return True
        if shift.status in ('cancelled', 'no_show', 'completed'):
            return True
        if self.is_past_due_window(now):
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
    def _auto_ack_missed_and_stale(self, user=None):
        """Acknowledge reminders that are past their show window or obsolete."""
        Reminder = self.sudo()
        now = fields.Datetime.now()
        # Only scan reminders whose shift start is old enough that the
        # 30-min window has already closed (start < now - 22 min), or
        # any for this user still unacked — capped for safety.
        domain = [
            ('is_acknowledged', '=', False),
            '|',
            ('scheduled_start', '<', now - timedelta(minutes=22)),
            ('scheduled_start', '=', False),
        ]
        if user:
            domain = [
                ('is_acknowledged', '=', False),
                ('user_id', '=', user.id),
            ]
        rows = Reminder.search(domain, limit=2000)
        stale = Reminder.browse()
        for rec in rows:
            try:
                if rec.is_stale_or_obsolete() or rec.is_past_due_window(now):
                    stale |= rec
            except Exception:
                stale |= rec
        if stale:
            stale.action_acknowledge()
            _logger.info(
                'Patrol reminder auto-acked %s missed/stale row(s)',
                len(stale),
            )
        return len(stale)

    @api.model
    def get_due_pending_reminders(self, user):
        """All reminders for this user that are due right now (not early, not late)."""
        self._auto_ack_missed_and_stale(user=user)
        now = fields.Datetime.now()
        # Only consider shifts that could still be in a due window:
        # earliest: 10-min due = start-10, window+8 → start > now-18
        # latest: 30-min due = start-30 → start < now+32
        reminders = self.sudo().search([
            ('user_id', '=', user.id),
            ('is_acknowledged', '=', False),
            ('scheduled_start', '>=', now - timedelta(minutes=20)),
            ('scheduled_start', '<=', now + timedelta(minutes=35)),
        ], order='reminder_type desc, scheduled_start asc, id asc', limit=100)
        due = self.browse()
        for rec in reminders:
            if rec.is_stale_or_obsolete():
                continue
            if rec.is_due_now(now):
                due |= rec
        return due

    @api.model
    def get_pending_mobile_reminder(self, user):
        """Primary due reminder for mobile (first of the due batch)."""
        due = self.get_due_pending_reminders(user)
        return due[:1] if due else self.browse()

    @api.model
    def acknowledge_all_due_for_user(self, user, reminder_id=None):
        """Ack every currently due reminder for the user in one tap.

        Also acks the requested id if present (belt-and-braces).
        """
        due = self.get_due_pending_reminders(user)
        if reminder_id:
            extra = self.sudo().search([
                ('id', '=', int(reminder_id)),
                ('user_id', '=', user.id),
                ('is_acknowledged', '=', False),
            ], limit=1)
            due |= extra
        if due:
            due.action_acknowledge()
        return due

    @api.model
    def build_mobile_payload(self, user):
        """JSON fields for pending/check endpoints (one modal for all due)."""
        due = self.get_due_pending_reminders(user)
        if not due:
            return {'patrol_reminder': False}
        primary = due[0]
        tour_names = []
        for rec in due:
            name = rec.tour_id.name or ''
            if name and name not in tour_names:
                tour_names.append(name)
        return {
            'patrol_reminder': True,
            'reminder_id': primary.id,
            'reminder_ids': due.ids,
            'count': len(due),
            'tour_name': tour_names[0] if tour_names else '',
            'tour_names': tour_names,
            'site_name': primary.shift_id.site_id.name if primary.shift_id.site_id else '',
            'scheduled_start_iso': primary.scheduled_start.isoformat()
            if primary.scheduled_start else False,
            'minutes_before': primary.reminder_type,
        }