# -*- coding: utf-8 -*-
"""Extra fields for push.to.talk.channel (loaded after base model for reliable upgrades)."""

from odoo import models, fields


class PushToTalkChannelAllSites(models.Model):
    """Extend PTT channel with all-sites / global access flag."""

    _inherit = 'push.to.talk.channel'

    all_sites_access = fields.Boolean(
        string='All Sites',
        default=False,
        help='If enabled, members can use this channel regardless of their user site assignment '
             '(e.g. company-wide or emergency). Live audio and notifications go to all members. '
             'Use together with explicit membership; Site is optional but still recommended for reporting.'
    )
