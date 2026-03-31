# -*- coding: utf-8 -*-
"""Extra fields for guard.message.channel (loaded after base model for reliable upgrades)."""

from odoo import models, fields


class GuardMessageChannelAllSites(models.Model):
    """Extend team chat channel with all-sites / global access flag."""

    _inherit = 'guard.message.channel'

    all_sites_access = fields.Boolean(
        string='All Sites',
        default=False,
        help='If enabled, members can use this channel regardless of user site assignment '
             '(e.g. company-wide). Public discovery still requires matching rules below.'
    )
