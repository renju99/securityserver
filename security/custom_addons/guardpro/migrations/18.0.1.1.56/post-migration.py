# -*- coding: utf-8 -*-
"""Fix GuardPro menu parents: views file had top-level menus without menu_guardpro_root."""

from odoo import api, SUPERUSER_ID

# (child_xml_id, parent_xml_id)
MENU_PARENTS = [
    ('guardpro.menu_guardpro_dashboard', 'guardpro.menu_guardpro_root'),
    ('guardpro.menu_guardpro_operations', 'guardpro.menu_guardpro_root'),
    ('guardpro.menu_operations_scheduling', 'guardpro.menu_guardpro_operations'),
    ('guardpro.menu_operations_attendance', 'guardpro.menu_guardpro_operations'),
    ('guardpro.menu_guardpro_site_management', 'guardpro.menu_guardpro_root'),
    ('guardpro.menu_visitor_watchlist', 'guardpro.menu_guardpro_site_management'),
    ('guardpro.menu_package_management', 'guardpro.menu_guardpro_site_management'),
    ('guardpro.menu_key_management', 'guardpro.menu_guardpro_site_management'),
    ('guardpro.menu_residents_tenants_root', 'guardpro.menu_guardpro_site_management'),
    ('guardpro.menu_guardpro_incidents_emergency', 'guardpro.menu_guardpro_root'),
    ('guardpro.menu_guardpro_compliance', 'guardpro.menu_guardpro_root'),
    ('guardpro.menu_guardpro_resources', 'guardpro.menu_guardpro_root'),
    ('guardpro.menu_guardpro_training_knowledge', 'guardpro.menu_guardpro_root'),
    ('guardpro.menu_guardpro_tracking', 'guardpro.menu_guardpro_root'),
    ('guardpro.menu_route_optimizer', 'guardpro.menu_operations_tours'),
    ('guardpro.menu_guardpro_feedback', 'guardpro.menu_guardpro_root'),
    ('guardpro.menu_guardpro_configuration', 'guardpro.menu_guardpro_root'),
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Menu = env['ir.ui.menu'].sudo()

    for child_xid, parent_xid in MENU_PARENTS:
        child = env.ref(child_xid, raise_if_not_found=False)
        parent = env.ref(parent_xid, raise_if_not_found=False)
        if child and parent and child.parent_id != parent:
            child.write({'parent_id': parent.id})

    stale = env.ref('guardpro.menu_guardpro_time_attendance', raise_if_not_found=False)
    if stale:
        stale.unlink()

    root = env.ref('guardpro.menu_guardpro_root', raise_if_not_found=False)
    if root:
        gnames = [
            'guardpro.group_guardpro_client_user',
            'guardpro.group_guardpro_reception',
            'guardpro.group_guardpro_supervisor',
            'guardpro.group_guardpro_manager',
            'guardpro.group_guardpro_admin',
            'guardpro.group_guardpro_guard_portal',
        ]
        gids = []
        for gx in gnames:
            g = env.ref(gx, raise_if_not_found=False)
            if g:
                gids.append(g.id)
        if gids:
            root.write({'groups_id': [(6, 0, gids)]})

    env.registry.clear_cache()
    Menu.invalidate_model(['parent_path'])
