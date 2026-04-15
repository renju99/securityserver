# -*- coding: utf-8 -*-
"""Restrict Discuss / To-do / etc. to Odoo admin groups (same as guardpro_menus.xml records)."""

from odoo import api, SUPERUSER_ID

MENU_XMLS = [
    'base.menu_management',
    'hr.menu_hr_root',
    'website.menu_website_root',
    'utm.menu_link_tracker_root',
    'base.menu_administration',
    'mail.menu_root_discuss',
    'mail.menu_configuration',
    'project_todo.menu_todo_todos',
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
