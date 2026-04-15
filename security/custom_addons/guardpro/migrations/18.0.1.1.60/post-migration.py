# -*- coding: utf-8 -*-
"""Restrict Contacts root menu to Odoo admin groups."""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    g_sys = env.ref('base.group_system', raise_if_not_found=False)
    g_erp = env.ref('base.group_erp_manager', raise_if_not_found=False)
    if not g_sys or not g_erp:
        return
    m = env.ref('contacts.menu_contacts', raise_if_not_found=False)
    if m:
        m.write({'groups_id': [(6, 0, [g_sys.id, g_erp.id])]})
    env.registry.clear_cache()
