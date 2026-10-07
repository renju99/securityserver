# -*- coding: utf-8 -*-
"""Guard shift handover / takeover between outgoing and incoming guards."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class GuardHandover(models.Model):
    """Formal post / shift handover from one guard to another."""

    _name = 'guard.handover'
    _description = 'Guard Shift Handover'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'handover_datetime desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Reference',
        required=True,
        default='New',
        copy=False,
        readonly=True,
        index=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('pending', 'Awaiting Takeover'),
            ('accepted', 'Taken Over'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    post_location = fields.Char(
        string='Post / Location',
        help='e.g. Main Gate, Lobby, Control Room',
        tracking=True,
    )
    handover_datetime = fields.Datetime(
        string='Handover Date/Time',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True,
    )
    from_guard_id = fields.Many2one(
        'guard.profile',
        string='Handing Over',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    to_guard_id = fields.Many2one(
        'guard.profile',
        string='Taking Over',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    outgoing_shift_id = fields.Many2one(
        'guard.shift',
        string='Outgoing Shift',
        ondelete='set null',
        domain="[('site_id', '=', site_id), ('guard_id', '=', from_guard_id)]",
    )
    notes = fields.Text(
        string='Handover Notes',
        help='Summary for the incoming guard.',
    )
    open_issues = fields.Text(
        string='Open Issues',
        help='Unresolved incidents, alarms, or follow-ups.',
    )
    keys_equipment = fields.Text(
        string='Keys / Equipment',
        help='Keys, radio, or other items handed over.',
    )
    submitted_at = fields.Datetime(string='Submitted At', readonly=True)
    accepted_at = fields.Datetime(string='Taken Over At', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'from_guard_id' in fields_list and not res.get('from_guard_id'):
            guard = self.env['guard.profile'].search(
                [('user_id', '=', self.env.user.id)], limit=1
            )
            if guard:
                res['from_guard_id'] = guard.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') in ('New', _('New')):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('guard.handover') or 'New'
                )
        return super().create(vals_list)

    @api.constrains('from_guard_id', 'to_guard_id')
    def _check_distinct_guards(self):
        for rec in self:
            if (
                rec.from_guard_id
                and rec.to_guard_id
                and rec.from_guard_id.id == rec.to_guard_id.id
            ):
                raise ValidationError(_(
                    'Handing over and taking over guards must be different.'
                ))

    def _current_guard(self):
        """Return the guard.profile for the current user, if any."""
        return self.env['guard.profile'].search(
            [('user_id', '=', self.env.user.id)], limit=1
        )

    def _is_handover_manager(self):
        """Supervisors/admins may act on any handover."""
        user = self.env.user
        return (
            user.has_group('base.group_system')
            or user.has_group('guardpro.group_guardpro_manager')
            or user.has_group('guardpro.group_guardpro_supervisor')
        )

    def action_submit(self):
        guard = self._current_guard()
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft handovers can be submitted.'))
            if (
                not self._is_handover_manager()
                and (not guard or guard.id != rec.from_guard_id.id)
            ):
                raise UserError(_('Only the outgoing guard can submit this handover.'))
            rec.write({
                'state': 'pending',
                'submitted_at': fields.Datetime.now(),
            })
            rec.message_post(body=_(
                'Handover submitted by %s — awaiting takeover by %s.'
            ) % (rec.from_guard_id.name, rec.to_guard_id.name))
        return True

    def action_accept(self):
        guard = self._current_guard()
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('Only handovers awaiting takeover can be accepted.'))
            if (
                not self._is_handover_manager()
                and (not guard or guard.id != rec.to_guard_id.id)
            ):
                raise UserError(_('Only the incoming guard can accept this handover.'))
            rec.write({
                'state': 'accepted',
                'accepted_at': fields.Datetime.now(),
            })
            rec.message_post(body=_(
                'Taken over by %s from %s.'
            ) % (rec.to_guard_id.name, rec.from_guard_id.name))
        return True

    def action_cancel(self):
        guard = self._current_guard()
        for rec in self:
            if rec.state in ('accepted', 'cancelled'):
                raise UserError(_('This handover can no longer be cancelled.'))
            if (
                not self._is_handover_manager()
                and (not guard or guard.id not in (rec.from_guard_id.id, rec.to_guard_id.id))
            ):
                raise UserError(_('You are not allowed to cancel this handover.'))
            rec.write({'state': 'cancelled'})
        return True

    def action_reset_draft(self):
        for rec in self:
            if not self._is_handover_manager():
                raise UserError(_('Only supervisors can reset a handover to draft.'))
            if rec.state not in ('cancelled', 'pending'):
                raise UserError(_('Only pending or cancelled handovers can be reset.'))
            rec.write({
                'state': 'draft',
                'submitted_at': False,
                'accepted_at': False,
            })
        return True
