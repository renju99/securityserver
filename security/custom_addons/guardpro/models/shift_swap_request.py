# -*- coding: utf-8 -*-
"""Shift Swap Request Management."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class ShiftSwapRequest(models.Model):
    """Manage shift swap requests between guards."""
    
    _name = 'shift.swap.request'
    _description = 'Shift Swap Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Reference',
        required=True,
        default=lambda self: _('New'),
        copy=False,
        readonly=True,
        tracking=True
    )
    
    requesting_guard_id = fields.Many2one(
        'guard.profile',
        string='Requesting Guard',
        required=True,
        tracking=True
    )
    
    target_guard_id = fields.Many2one(
        'guard.profile',
        string='Target Guard',
        required=True,
        domain="[('status', 'in', ['available', 'on_shift']), ('id', '!=', requesting_guard_id)]",
        tracking=True
    )
    
    shift_id = fields.Many2one(
        'guard.shift',
        string='Shift to Swap',
        required=True,
        domain="[('guard_id', '=', requesting_guard_id), ('status', '=', 'scheduled')]",
        tracking=True
    )
    
    compensation_shift_id = fields.Many2one(
        'guard.shift',
        string='Compensation Shift',
        help='Optional: Shift from target guard to swap in return',
        domain="[('guard_id', '=', target_guard_id), ('status', '=', 'scheduled')]",
        tracking=True
    )
    
    reason = fields.Text(
        string='Reason for Swap',
        required=True
    )
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Guard Approval'),
        ('accepted', 'Accepted by Guard'),
        ('approved', 'Approved by Supervisor'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True, required=True)
    
    guard_response = fields.Text(
        string='Guard Response',
        readonly=True
    )
    
    supervisor_notes = fields.Text(
        string='Supervisor Notes'
    )
    
    supervisor_id = fields.Many2one(
        'res.users',
        string='Approving Supervisor',
        readonly=True
    )
    
    swap_date = fields.Datetime(
        related='shift_id.start_datetime',
        string='Swap Date',
        store=True
    )
    
    site_id = fields.Many2one(
        related='shift_id.site_id',
        string='Site',
        store=True
    )
    
    # Constraints
    @api.constrains('requesting_guard_id', 'target_guard_id')
    def _check_guards(self):
        """Ensure guards are different."""
        for record in self:
            if record.requesting_guard_id == record.target_guard_id:
                raise ValidationError(_('Cannot swap shift with yourself!'))
    
    @api.constrains('shift_id', 'compensation_shift_id')
    def _check_shifts(self):
        """Ensure shifts are different if compensation provided."""
        for record in self:
            if record.compensation_shift_id and record.shift_id == record.compensation_shift_id:
                raise ValidationError(_('Cannot swap the same shift!'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence on create."""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('shift.swap.request') or _('New')
        return super().create(vals_list)
    
    def action_submit(self):
        """Submit swap request to target guard."""
        self.ensure_one()
        if self.status != 'draft':
            raise ValidationError(_('Only draft requests can be submitted.'))
        
        # Validate shift is not too soon (minimum 24 hours notice)
        if self.shift_id.start_datetime < (fields.Datetime.now() + timedelta(hours=24)):
            raise ValidationError(_('Shift swap must be requested at least 24 hours in advance.'))
        
        self.status = 'pending'

        # Mobile push to the target guard.
        if self.target_guard_id and self.target_guard_id.user_id:
            self.env['guardpro.mobile.outbox'].sudo().push(
                user=self.target_guard_id.user_id,
                kind='shift_swap_decision',
                title=_('Shift swap request'),
                body=_('%s wants to swap the shift on %s at %s.') % (
                    self.requesting_guard_id.name or '-',
                    self.shift_id.start_datetime or '-',
                    self.shift_id.site_id.name if self.shift_id.site_id else '-',
                ),
                priority='high',
                res_model='shift.swap.request',
                res_id=self.id,
                dedup_key='swap_submit:%s' % self.id,
            )

        # Send notification to target guard
        if self.target_guard_id.user_id:
            self.message_post(
                body=Markup('Shift swap request from %s for shift on %s at %s.<br/>Reason: %s') % (
                    Markup.escape(self.requesting_guard_id.name or ''),
                    Markup.escape(self.shift_id.start_datetime.strftime('%Y-%m-%d %H:%M')),
                    Markup.escape(self.shift_id.site_id.name or ''),
                    Markup.escape(self.reason or _('No reason provided'))
                ),
                partner_ids=self.target_guard_id.user_id.partner_id.ids,
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Shift swap request sent to %s') % self.target_guard_id.name,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_accept(self):
        """Target guard accepts the swap."""
        self.ensure_one()
        if self.status != 'pending':
            raise ValidationError(_('Only pending requests can be accepted.'))
        
        self.status = 'accepted'
        
        # Send notification to supervisors for approval
        try:
            supervisor_group = self.env.ref('guardpro.group_guardpro_supervisor')
            supervisor_ids = self.env['res.users'].search([('groups_id', 'in', supervisor_group.id)])
            
            if supervisor_ids:
                self.message_post(
                    body=_('Shift swap accepted by %s. Requires supervisor approval.') % self.target_guard_id.name,
                    partner_ids=supervisor_ids.mapped('partner_id').ids,
                    message_type='notification'
                )
        except Exception as e:
            _logger.warning('Could not send notification to supervisors: %s', str(e))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Shift swap request accepted. Waiting for supervisor approval.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_reject_by_guard(self):
        """Target guard rejects the swap."""
        self.ensure_one()
        if self.status != 'pending':
            raise ValidationError(_('Only pending requests can be rejected.'))
        
        self.status = 'rejected'

        # Notify requesting guard
        if self.requesting_guard_id.user_id:
            self.env['guardpro.mobile.outbox'].sudo().push(
                user=self.requesting_guard_id.user_id,
                kind='shift_swap_decision',
                title=_('Shift swap rejected'),
                body=_('%s rejected your swap request.\nResponse: %s') % (
                    self.target_guard_id.name or '-',
                    self.guard_response or _('No reason provided'),
                ),
                priority='normal',
                res_model='shift.swap.request',
                res_id=self.id,
                dedup_key='swap_reject_guard:%s' % self.id,
            )
            self.message_post(
                body=Markup('Shift swap request rejected by %s.<br/>Response: %s') % (
                    Markup.escape(self.target_guard_id.name or ''),
                    Markup.escape(self.guard_response or _('No reason provided'))
                ),
                partner_ids=self.requesting_guard_id.user_id.partner_id.ids,
                message_type='notification'
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rejected'),
                'message': _('Shift swap request rejected.'),
                'type': 'warning',
                'sticky': False,
            }
        }
    
    def action_approve(self):
        """Supervisor approves and executes the swap."""
        self.ensure_one()
        if self.status != 'accepted':
            raise ValidationError(_('Only accepted requests can be approved.'))
        
        # Perform the swap
        original_guard = self.requesting_guard_id
        target_guard = self.target_guard_id
        
        # Swap main shift
        self.shift_id.write({'guard_id': target_guard.id})
        
        # Swap compensation shift if provided
        if self.compensation_shift_id:
            self.compensation_shift_id.write({'guard_id': original_guard.id})
        
        self.write({
            'status': 'completed',
            'supervisor_id': self.env.user.id
        })

        # Mobile push both guards.
        swap_users = self.env['res.users']
        if original_guard.user_id:
            swap_users |= original_guard.user_id
        if target_guard.user_id:
            swap_users |= target_guard.user_id
        if swap_users:
            self.env['guardpro.mobile.outbox'].sudo().push(
                user=swap_users,
                kind='shift_swap_decision',
                title=_('Shift swap approved'),
                body=_('Supervisor %s approved the swap.') % self.env.user.name,
                priority='high',
                res_model='shift.swap.request',
                res_id=self.id,
                dedup_key='swap_approved:%s' % self.id,
            )

        # Notify both guards
        partner_ids = []
        if original_guard.user_id:
            partner_ids.append(original_guard.user_id.partner_id.id)
        if target_guard.user_id:
            partner_ids.append(target_guard.user_id.partner_id.id)
        
        if partner_ids:
            self.message_post(
                body=Markup('Shift swap approved and completed by %s.<br/>Notes: %s') % (
                    Markup.escape(self.env.user.name or ''),
                    Markup.escape(self.supervisor_notes or _('No additional notes'))
                ),
                partner_ids=partner_ids,
                message_type='notification'
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Shift swap approved and completed successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_reject_by_supervisor(self):
        """Supervisor rejects the swap."""
        self.ensure_one()
        if self.status != 'accepted':
            raise ValidationError(_('Only accepted requests can be rejected by supervisor.'))
        
        self.status = 'rejected'

        # Mobile push to both guards.
        swap_users = self.env['res.users']
        if self.requesting_guard_id.user_id:
            swap_users |= self.requesting_guard_id.user_id
        if self.target_guard_id.user_id:
            swap_users |= self.target_guard_id.user_id
        if swap_users:
            self.env['guardpro.mobile.outbox'].sudo().push(
                user=swap_users,
                kind='shift_swap_decision',
                title=_('Shift swap rejected by supervisor'),
                body=self.supervisor_notes or _('No reason provided'),
                priority='normal',
                res_model='shift.swap.request',
                res_id=self.id,
                dedup_key='swap_rejected_sup:%s' % self.id,
            )

        # Notify both guards
        partner_ids = []
        if self.requesting_guard_id.user_id:
            partner_ids.append(self.requesting_guard_id.user_id.partner_id.id)
        if self.target_guard_id.user_id:
            partner_ids.append(self.target_guard_id.user_id.partner_id.id)

        if partner_ids:
            self.message_post(
                body=Markup('Shift swap request rejected by supervisor.<br/>Reason: %s') % (
                    Markup.escape(self.supervisor_notes or _('No reason provided'))
                ),
                partner_ids=partner_ids,
                message_type='notification'
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rejected'),
                'message': _('Shift swap request rejected.'),
                'type': 'warning',
                'sticky': False,
            }
        }
    
    def action_cancel(self):
        """Requesting guard cancels the request."""
        self.ensure_one()
        if self.status not in ['draft', 'pending', 'accepted']:
            raise ValidationError(_('Cannot cancel request in current status.'))
        
        self.status = 'cancelled'
        
        # Notify target guard if already sent
        if self.status != 'draft' and self.target_guard_id.user_id:
            self.message_post(
                body=_('Shift swap request cancelled by %s.') % self.requesting_guard_id.name,
                partner_ids=self.target_guard_id.user_id.partner_id.ids,
                message_type='notification'
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cancelled'),
                'message': _('Shift swap request cancelled.'),
                'type': 'info',
                'sticky': False,
            }
        }

