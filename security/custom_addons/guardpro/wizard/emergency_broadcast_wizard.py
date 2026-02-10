# -*- coding: utf-8 -*-
"""Emergency Broadcast Wizard."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class EmergencyBroadcastWizard(models.TransientModel):
    """Wizard for creating and sending emergency broadcasts."""

    _name = 'emergency.broadcast.wizard'
    _description = 'Emergency Broadcast Wizard'

    title = fields.Char(
        string='Title',
        required=True,
        default='EMERGENCY ALERT',
        help='Title of the emergency message'
    )
    message = fields.Text(
        string='Message',
        required=True,
        help='Emergency message to broadcast to guards'
    )
    priority = fields.Selection([
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string='Priority', default='urgent', required=True)

    broadcast_type = fields.Selection([
        ('all', 'All Guards'),
        ('by_site', 'Guards by Site'),
        ('active_only', 'Only Active Guards on Duty')
    ], string='Broadcast To', default='all', required=True)

    site_id = fields.Many2one(
        'client.site',
        string='Select Site',
        help='Select specific site (only applies if "Guards by Site" is selected)'
    )

    guard_count = fields.Integer(
        string='Guards to Notify',
        compute='_compute_guard_count',
        help='Number of guards who will receive this message'
    )

    @api.depends('broadcast_type', 'site_id')
    def _compute_guard_count(self):
        """Calculate how many guards will receive the message."""
        for wizard in self:
            domain = [('status', '=', 'active'), ('user_id', '!=', False)]

            if wizard.broadcast_type == 'by_site' and wizard.site_id:
                domain.append(('site_ids', 'in', [wizard.site_id.id]))
            elif wizard.broadcast_type == 'active_only':
                active_shifts = self.env['guard.shift'].search([
                    ('status', '=', 'in_progress'),
                    ('start_datetime', '<=', fields.Datetime.now()),
                    ('end_datetime', '>=', fields.Datetime.now())
                ])
                guard_ids = active_shifts.mapped('guard_id').ids
                if guard_ids:
                    domain.append(('id', 'in', guard_ids))
                else:
                    wizard.guard_count = 0
                    continue

            wizard.guard_count = self.env['guard.profile'].search_count(domain)

    @api.onchange('broadcast_type')
    def _onchange_broadcast_type(self):
        """Clear site selection if not broadcasting by site."""
        if self.broadcast_type != 'by_site':
            self.site_id = False

    def action_send_broadcast(self):
        """Create and send the emergency broadcast."""
        self.ensure_one()

        # Validate
        if self.broadcast_type == 'by_site' and not self.site_id:
            raise UserError(_('Please select a site for broadcasting.'))

        if self.guard_count == 0:
            raise UserError(_('No guards found matching the selected criteria.'))

        # Create the broadcast record
        broadcast = self.env['emergency.broadcast'].create({
            'title': self.title,
            'message': self.message,
            'priority': self.priority,
            'broadcast_type': self.broadcast_type,
            'site_id': self.site_id.id if self.site_id else False,
        })

        # Send the broadcast
        broadcast.action_send_broadcast()

        # Return action to view the broadcast
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'emergency.broadcast',
            'res_id': broadcast.id,
            'view_mode': 'form',
            'target': 'current',
        }

