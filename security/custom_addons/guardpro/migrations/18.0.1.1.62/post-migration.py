# -*- coding: utf-8 -*-
"""Restore primary apps sidebar for users stuck on invisible.

GuardPro previously redefined res.users.sidebar_type with default 'invisible',
which overrides MuK AppsBar (default 'large') and hides the vertical app menu.
This migration resets affected users so the apps bar is visible again.
"""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'sidebar_type' not in env['res.users']._fields:
        return
    users = env['res.users'].sudo().search(
        ['|', ('sidebar_type', '=', False), ('sidebar_type', '=', 'invisible')]
    )
    if users:
        users.write({'sidebar_type': 'large'})
    env.registry.clear_cache()
