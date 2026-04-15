# -*- coding: utf-8 -*-
"""Enforce Odoo admin-only visibility on standard app roots (DB may lag XML)."""

from odoo import api, SUPERUSER_ID

MENU_XMLS = [
    'base.menu_management',
    'hr.menu_hr_root',
    'website.menu_website_root',
    'utm.menu_link_tracker_root',
    'base.menu_administration',
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    g_sys = env.ref('base.group_system', raise_if_not_found=False)
    g_erp = env.ref('base.group_erp_manager', raise_if_not_found=False)
    if not g_sys or not g_erp:
        return
    gids = [g_sys.id, g_erp.id]
    for xid in MENU_XMLS:
        m = env.ref(xid, raise_if_not_found=False)
        if not m:
            continue
        m.write({'groups_id': [(6, 0, gids)]})
    env.registry.clear_cache()
