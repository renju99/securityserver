# -*- coding: utf-8 -*-
"""Force-replace menu groups so stale M2M rows are cleared.

- Website app root in Odoo 18 is website.menu_website_configuration (not only
  menu_website_root).
- GuardLink Configuration root must not keep GuardLink role groups on ir.ui.menu
  (menuitem + partial updates can leave extra ir_ui_menu_group_rel rows).
"""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    g_sys = env.ref('base.group_system', raise_if_not_found=False)
    g_erp = env.ref('base.group_erp_manager', raise_if_not_found=False)
    if not g_sys or not g_erp:
        return
    admin_groups = [g_sys.id, g_erp.id]
    for xmlid in (
        'website.menu_website_configuration',
        'website.menu_website_root',
        'guardpro.menu_guardpro_configuration',
    ):
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu:
            menu.write({'groups_id': [(6, 0, admin_groups)]})
    env.registry.clear_cache()
