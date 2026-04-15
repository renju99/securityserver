# -*- coding: utf-8 -*-
"""Restore legacy primary menu placement (top-level/left behavior)."""

from odoo import api, SUPERUSER_ID

PRIMARY_TOP_LEVEL = [
    'guardpro.menu_guardpro_dashboard',
    'guardpro.menu_guardpro_operations',
    'guardpro.menu_guardpro_site_management',
    'guardpro.menu_guardpro_incidents_emergency',
    'guardpro.menu_guardpro_compliance',
    'guardpro.menu_guardpro_resources',
    'guardpro.menu_guardpro_training_knowledge',
    'guardpro.menu_guardpro_tracking',
    'guardpro.menu_guardpro_feedback',
    'guardpro.menu_guardpro_configuration',
]

# keep agreed submenu placements
CHILD_PARENTS = [
    ('guardpro.menu_operations_scheduling', 'guardpro.menu_guardpro_operations'),
    ('guardpro.menu_operations_attendance', 'guardpro.menu_guardpro_operations'),
    ('guardpro.menu_visitor_watchlist', 'guardpro.menu_guardpro_site_management'),
    ('guardpro.menu_package_management', 'guardpro.menu_guardpro_site_management'),
    ('guardpro.menu_key_management', 'guardpro.menu_guardpro_site_management'),
    ('guardpro.menu_residents_tenants_root', 'guardpro.menu_guardpro_site_management'),
    ('guardpro.menu_route_optimizer', 'guardpro.menu_operations_tours'),
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Menu = env['ir.ui.menu'].sudo()

    # return primary menus to top-level
    for xmlid in PRIMARY_TOP_LEVEL:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu and menu.parent_id:
            menu.write({'parent_id': False})

    for child_xid, parent_xid in CHILD_PARENTS:
        child = env.ref(child_xid, raise_if_not_found=False)
        parent = env.ref(parent_xid, raise_if_not_found=False)
        if child and parent and child.parent_id != parent:
            child.write({'parent_id': parent.id})

    root = env.ref('guardpro.menu_guardpro_root', raise_if_not_found=False)
    hidden = env.ref('base.group_no_one', raise_if_not_found=False)
    if root and hidden:
        root.write({'groups_id': [(6, 0, [hidden.id])]})

    env.registry.clear_cache()
    Menu.invalidate_model(['parent_path'])
