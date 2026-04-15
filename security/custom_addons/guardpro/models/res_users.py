# -*- coding: utf-8 -*-
"""User Extension for Site-Based Access Control."""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    """Extend res.users to add site assignment for access control."""

    _inherit = 'res.users'

    site_ids = fields.Many2many(
        'client.site',
        'guardpro_user_site_rel',
        'user_id',
        'site_id',
        string='Assigned Sites',
        help='Sites that this user has access to. '
             'Administrators see all sites regardless of this field. '
             'Other users (Client User, Guard Portal, Manager, Supervisor) '
             'only see records related to their assigned sites.'
    )
    
    guard_profile_id = fields.One2many(
        'guard.profile',
        'user_id',
        string='Guard Profile',
        help='Guard profile associated with this user'
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-assign sites to client users based on their partner's client relationship."""
        users = super(ResUsers, self).create(vals_list)
        
        for user in users:
            # Auto-assign sites for client users based on partner relationship
            if user.has_group('guardpro.group_guardpro_client_user') and user.partner_id:
                user._auto_assign_client_sites()
        
        return users

    def write(self, vals):
        """Auto-assign sites when user is assigned to client user group."""
        result = super(ResUsers, self).write(vals)
        
        # Check if user was just assigned to client user group
        if 'groups_id' in vals or 'partner_id' in vals:
            for user in self:
                if user.has_group('guardpro.group_guardpro_client_user') and user.partner_id:
                    user._auto_assign_client_sites()
        
        return result

    def _auto_assign_client_sites(self):
        """Automatically assign sites to client users based on their partner's client relationship."""
        self.ensure_one()
        
        if not self.partner_id:
            return
        
        # Find all sites where the user's partner is the client
        # Check both direct client relationship and if partner is a company client
        partner = self.partner_id
        
        # Get sites where partner is the client
        sites = self.env['client.site'].search([
            ('client_id', '=', partner.id)
        ])
        
        # Also check if partner is a contact of a client company
        if partner.parent_id and partner.parent_id.is_company:
            parent_sites = self.env['client.site'].search([
                ('client_id', '=', partner.parent_id.id)
            ])
            sites |= parent_sites
        
        # Update site_ids if sites were found and not already assigned
        if sites:
            current_sites = self.site_ids.ids
            new_sites = sites.ids
            # Only add sites that aren't already assigned
            sites_to_add = [sid for sid in new_sites if sid not in current_sites]
            if sites_to_add:
                self.write({'site_ids': [(4, sid) for sid in sites_to_add]})
                _logger.info(
                    'Auto-assigned %d site(s) to client user %s (ID: %s)',
                    len(sites_to_add), self.name, self.id
                )

    def action_refresh_site_assignments(self):
        """Manually refresh site assignments for client users.
        
        This method can be called from a button or server action to
        refresh site assignments for existing client users.
        """
        client_users = self.filtered(
            lambda u: u.has_group('guardpro.group_guardpro_client_user')
        )
        
        for user in client_users:
            user._auto_assign_client_sites()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Site Assignments Refreshed'),
                'message': _('Site assignments have been refreshed for %d user(s).') % len(client_users),
                'type': 'success',
                'sticky': False,
            }
        }

