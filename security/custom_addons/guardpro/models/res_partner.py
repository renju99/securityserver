# -*- coding: utf-8 -*-
"""Extension of res.partner for GuardPro multi-tenancy."""

from odoo import models, fields


class ResPartner(models.Model):
    """Extend res.partner to link with guard profiles."""

    _inherit = 'res.partner'

    guard_profile_ids = fields.One2many(
        'guard.profile',
        'user_id',
        compute='_compute_guard_profile_ids',
        string='Guard Profiles',
        help='Guard profiles linked to this partner via user account'
    )

    def _compute_guard_profile_ids(self):
        """Compute guard profiles associated with this partner's user."""
        for partner in self:
            if partner.user_ids:
                # Get all guard profiles for all users linked to this partner
                partner.guard_profile_ids = self.env['guard.profile'].search([
                    ('user_id', 'in', partner.user_ids.ids)
                ])
            else:
                partner.guard_profile_ids = False

