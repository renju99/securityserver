# -*- coding: utf-8 -*-
"""Guard Approval Requests — supervisor sign-off for partial tours and critical incidents."""

from odoo import models, fields, api
from odoo.exceptions import UserError, AccessError
import logging

_logger = logging.getLogger(__name__)


class GuardApprovalRequest(models.Model):
    _name = 'guard.approval.request'
    _description = 'Guard Supervisor Approval Request'
    _order = 'request_date desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Reference', compute='_compute_name', store=True)

    request_type = fields.Selection([
        ('partial_tour', 'Partial Tour Completion'),
        ('critical_incident', 'Critical / High Incident'),
        ('other', 'Other'),
    ], string='Type', required=True, default='other')

    guard_id = fields.Many2one(
        'guard.profile', string='Guard', required=True, ondelete='cascade', index=True)
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        index=True,
        help='Site this approval belongs to. Used for supervisor site isolation.',
    )

    # Polymorphic reference (tour.log or incident.report)
    reference_model = fields.Char('Related Model')
    reference_id = fields.Integer('Related Record ID')

    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending', required=True, index=True)

    guard_notes = fields.Text('Guard Notes')
    supervisor_notes = fields.Text('Supervisor Notes')

    request_date = fields.Datetime(
        string='Requested', default=fields.Datetime.now, required=True)
    resolve_date = fields.Datetime('Resolved On')
    resolved_by = fields.Many2one(
        'res.users', string='Resolved By', readonly=True)

    # ── computed ─────────────────────────────────────────────────────────────

    @api.depends('request_type', 'guard_id', 'request_date')
    def _compute_name(self):
        labels = {
            'partial_tour': 'Partial Tour',
            'critical_incident': 'Critical Incident',
            'other': 'Approval',
        }
        for rec in self:
            date_str = rec.request_date.strftime('%d/%m %H:%M') if rec.request_date else ''
            guard_name = rec.guard_id.name if rec.guard_id else ''
            label = labels.get(rec.request_type, 'Approval')
            rec.name = f"{label} — {guard_name} [{date_str}]"

    @api.model
    def _resolve_site_id(self, vals):
        """Derive site from explicit value, related record, or guard assignment."""
        if vals.get('site_id'):
            return vals['site_id']

        ref_model = vals.get('reference_model')
        ref_id = vals.get('reference_id')
        if ref_model and ref_id and ref_model in self.env:
            try:
                related = self.env[ref_model].sudo().browse(ref_id)
                if related.exists() and 'site_id' in related._fields and related.site_id:
                    return related.site_id.id
            except Exception as exc:
                _logger.debug('Could not resolve site from %s,%s: %s', ref_model, ref_id, exc)

        guard_id = vals.get('guard_id')
        if guard_id:
            guard = self.env['guard.profile'].sudo().browse(guard_id)
            if guard.exists() and guard.site_ids:
                return guard.site_ids[0].id
        return False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('site_id'):
                vals['site_id'] = self._resolve_site_id(vals)
        return super().create(vals_list)

    def user_has_site_access(self, user=None):
        """True when ``user`` may view/resolve this approval (admins always)."""
        self.ensure_one()
        user = user or self.env.user
        if user.has_group('guardpro.group_guardpro_admin'):
            return True
        allowed = set(user.site_ids.ids)
        if not allowed:
            return False
        if self.site_id:
            return self.site_id.id in allowed
        # Legacy rows without site: fall back to guard site overlap
        if self.guard_id and self.guard_id.site_ids:
            return bool(allowed & set(self.guard_id.site_ids.ids))
        return False

    # ── actions ──────────────────────────────────────────────────────────────

    def action_approve(self, supervisor_notes=None):
        self.ensure_one()
        if not self.user_has_site_access():
            raise AccessError('You can only resolve approvals for your assigned projects.')
        self.write({
            'state': 'approved',
            'resolve_date': fields.Datetime.now(),
            'resolved_by': self.env.user.id,
            'supervisor_notes': supervisor_notes or self.supervisor_notes,
        })

    def action_reject(self, supervisor_notes=None):
        self.ensure_one()
        if not self.user_has_site_access():
            raise AccessError('You can only resolve approvals for your assigned projects.')
        if not supervisor_notes and not self.supervisor_notes:
            raise UserError('Please provide a reason for rejection.')
        self.write({
            'state': 'rejected',
            'resolve_date': fields.Datetime.now(),
            'resolved_by': self.env.user.id,
            'supervisor_notes': supervisor_notes or self.supervisor_notes,
        })
