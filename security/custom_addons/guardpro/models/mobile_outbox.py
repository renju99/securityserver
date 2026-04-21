# -*- coding: utf-8 -*-
"""Unified Mobile Outbox.

Any model that needs to ping the guard/supervisor/manager phone (TWA)
calls ``env['guardpro.mobile.outbox'].push(...)`` which drops a row in
this table. The mobile page polls
``/guardpro/api/mobile_outbox/pending`` every few seconds; the TWA
``AndroidBridge`` also polls natively as a fallback when the WebView
is backgrounded, so guards receive a real Android tray notification
within a few seconds of the event.

This is the replacement for the dozen-or-so ``_send_*_email`` methods
that were turned into ``_logger.info('Email notifications are
disabled…')`` no-ops. Keeping the channel fan-in in a single model
means each new workflow only has to write ``outbox.push(...)``, and
the wire format (endpoint + JS + Android bridge) never has to change
again.
"""

from odoo import models, fields, api, _
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)


KIND_SELECTION = [
    ('incident_escalation', 'Incident Escalation'),
    ('incident_lifecycle', 'Incident Update'),
    ('incident_investigation', 'Investigation Assignment'),
    ('incident_panic', 'Panic / SOS'),
    ('emergency_procedure', 'Emergency Procedure Active'),
    ('geofence_violation', 'Geofence Violation'),
    ('shift_assigned', 'Shift Assigned'),
    ('shift_changed', 'Shift Updated'),
    ('shift_cancelled', 'Shift Cancelled'),
    ('shift_swap_decision', 'Shift Swap Decision'),
    ('credential_expiring', 'Credential Expiring'),
    ('training_enrolled', 'Training Enrolled'),
    ('feedback_received', 'Feedback Received'),
    ('complaint_received', 'Complaint Received'),
    ('dar_decision', 'Daily Activity Report'),
    ('dar_rejected', 'DAR Rejected'),
    ('message_received', 'New Message'),
    # Resident / client-side events (community sites).
    ('visitor_arrival', 'Visitor Arrival'),
    ('package_ready', 'Package Ready'),
    ('portal_access', 'Portal Access Granted'),
    # Manager / supervisor events.
    ('performance_review', 'Performance Review'),
    ('sla_breach', 'SLA Breach'),
    ('other', 'Other'),
]

PRIORITY_SELECTION = [
    ('low', 'Low'),
    ('normal', 'Normal'),
    ('high', 'High'),
    ('urgent', 'Urgent'),
]


class MobileOutbox(models.Model):
    """One row = one outstanding phone notification for one user."""
    _name = 'guardpro.mobile.outbox'
    _description = 'Mobile App Notification Outbox'
    _order = 'create_date desc, id desc'
    _rec_name = 'title'

    user_id = fields.Many2one(
        'res.users',
        string='Recipient',
        required=True,
        ondelete='cascade',
        index=True,
        help='User whose mobile app should surface this notification.'
    )
    kind = fields.Selection(
        KIND_SELECTION,
        string='Kind',
        required=True,
        default='other',
        index=True,
    )
    title = fields.Char(string='Title', required=True, translate=False)
    body = fields.Text(string='Body', default='')
    priority = fields.Selection(
        PRIORITY_SELECTION,
        string='Priority',
        default='normal',
        required=True,
        index=True,
    )

    # Loose reference to the source record so the mobile UI can deep-link
    # back (e.g. open /guardpro/mobile/incidents/42).
    res_model = fields.Char(string='Source Model')
    res_id = fields.Integer(string='Source Record ID')
    deep_link = fields.Char(
        string='Deep Link',
        help='Relative URL to open when the guard taps the notification, '
             'e.g. /guardpro/mobile/incidents/42'
    )

    acked = fields.Boolean(
        string='Acknowledged',
        default=False,
        index=True,
        copy=False,
    )
    acked_on = fields.Datetime(string='Acknowledged On', readonly=True, copy=False)

    # Auto-expire untouched rows so the pending endpoint stays lean.
    expiry_date = fields.Datetime(
        string='Expires On',
        index=True,
        help='Row is auto-deleted by cron after this date even if the guard '
             'never acknowledged it.'
    )

    # Optional de-duplication key - e.g. "shift:42" - so re-running the same
    # cron doesn't stack 50 identical rows in the guard's banner.
    dedup_key = fields.Char(string='Dedup Key', index=True)

    def init(self):
        """Create a partial unique index enforcing one-live-row-per-dedup-key.

        We use a raw CREATE INDEX IF NOT EXISTS because ``_sql_constraints``
        with ``EXCLUDE`` would require the ``btree_gist`` PostgreSQL
        extension, which we don't want to mandate for installers.
        """
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                guardpro_mobile_outbox_user_dedup_pending_uq
            ON guardpro_mobile_outbox (user_id, dedup_key)
            WHERE dedup_key IS NOT NULL AND acked = FALSE;
        """)

    # ---------------------------------------------------------------
    # Core push helper
    # ---------------------------------------------------------------
    @api.model
    def push(self, user, kind, title, body='', priority='normal',
             res_model=None, res_id=None, deep_link=None, dedup_key=None,
             expires_in_hours=168):
        """Queue one or more notifications for phones.

        ``user`` accepts a single ``res.users`` record, a recordset, or
        an iterable of records/ids. Safe to call from sudo context
        (most callers are crons).
        """
        users = self._coerce_users(user)
        if not users:
            return self.browse()

        if kind not in dict(KIND_SELECTION):
            kind = 'other'
        if priority not in dict(PRIORITY_SELECTION):
            priority = 'normal'

        Outbox = self.sudo()
        created = Outbox.browse()
        now = fields.Datetime.now()
        expiry = fields.Datetime.add(now, hours=int(expires_in_hours or 168))

        for target in users:
            if not target or not target.id:
                continue
            # Skip disabled users - they cannot log in, so the notification
            # would never be ack'd and would just hang around.
            if hasattr(target, 'active') and not target.active:
                continue

            # De-dup: if a pending row with the same dedup_key already
            # exists for this user, refresh it instead of creating a
            # duplicate. This is what the SQL constraint enforces.
            if dedup_key:
                existing = Outbox.search([
                    ('user_id', '=', target.id),
                    ('dedup_key', '=', dedup_key),
                    ('acked', '=', False),
                ], limit=1)
                if existing:
                    existing.write({
                        'title': (title or '')[:240],
                        'body': (body or '')[:4000],
                        'priority': priority,
                        'expiry_date': expiry,
                    })
                    created |= existing
                    continue

            try:
                created |= Outbox.create({
                    'user_id': target.id,
                    'kind': kind,
                    'title': (title or '')[:240],
                    'body': (body or '')[:4000],
                    'priority': priority,
                    'res_model': res_model or False,
                    'res_id': int(res_id) if res_id else 0,
                    'deep_link': deep_link or False,
                    'dedup_key': dedup_key or False,
                    'expiry_date': expiry,
                })
            except Exception as e:  # pragma: no cover - defensive
                _logger.exception(
                    'mobile_outbox.push failed for user %s kind %s: %s',
                    target.id, kind, e
                )
        _logger.info(
            'mobile_outbox.push kind=%s users=%s created=%s',
            kind, users.ids, created.ids
        )
        return created

    @api.model
    def push_to_guards(self, guards, kind, title, body='', **kwargs):
        """Convenience: accept ``guard.profile`` recordset and resolve
        to ``user_id``."""
        users = self.env['res.users']
        for guard in guards or []:
            if guard and guard.user_id:
                users |= guard.user_id
        return self.push(users, kind, title, body, **kwargs)

    # ---------------------------------------------------------------
    # Ack
    # ---------------------------------------------------------------
    def action_ack(self):
        self.sudo().write({
            'acked': True,
            'acked_on': fields.Datetime.now(),
        })
        return True

    # ---------------------------------------------------------------
    # Cron: purge
    # ---------------------------------------------------------------
    @api.model
    def _cron_purge_outbox(self):
        """Delete acknowledged rows older than 24h and expired rows."""
        now = fields.Datetime.now()
        old_ack = self.sudo().search([
            ('acked', '=', True),
            ('acked_on', '<', fields.Datetime.subtract(now, days=1)),
        ])
        if old_ack:
            _logger.info('mobile_outbox purge: acked rows=%s', len(old_ack))
            old_ack.unlink()
        expired = self.sudo().search([
            ('acked', '=', False),
            ('expiry_date', '!=', False),
            ('expiry_date', '<', now),
        ])
        if expired:
            _logger.info('mobile_outbox purge: expired rows=%s', len(expired))
            expired.unlink()
        return True

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------
    @api.model
    def _coerce_users(self, user):
        """Accept a ``res.users`` record, recordset, iterable of records,
        iterable of ids, or anything falsy."""
        Users = self.env['res.users']
        if not user:
            return Users
        # Odoo recordset of res.users
        if hasattr(user, '_name') and user._name == 'res.users':
            return user
        try:
            iterator = iter(user)
        except TypeError:
            return Users
        ids = []
        record_agg = Users
        for item in iterator:
            if not item:
                continue
            if hasattr(item, '_name') and item._name == 'res.users':
                record_agg |= item
            elif isinstance(item, int):
                ids.append(item)
        if ids:
            record_agg |= Users.browse(ids).exists()
        return record_agg

    # ---------------------------------------------------------------
    # Access: users should see only their own rows (enforced by
    # record rule). Writes/unlink are system-only except ack.
    # ---------------------------------------------------------------
    def write(self, vals):
        # Allow a user to flip their own row to acked=True through the
        # ack endpoint (which calls action_ack via sudo), but block
        # anyone from tampering with someone else's row.
        if not self.env.su:
            for rec in self:
                if rec.user_id and rec.user_id.id != self.env.uid:
                    raise AccessError(_('Cannot modify another user\'s '
                                        'mobile outbox entry.'))
                # Non-admins may only toggle ack state + acked_on.
                allowed = {'acked', 'acked_on'}
                illegal = set(vals.keys()) - allowed
                if illegal:
                    raise AccessError(_('Only the ack flag may be updated.'))
        return super().write(vals)
