# -*- coding: utf-8 -*-
"""Refresh security.tour form view after checkpoint line field fix."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    xmlids = (
        'guardpro.view_security_tour_form',
        'guardpro.view_security_tour_checkpoint_line_list',
        'guardpro.view_security_tour_checkpoint_line_form',
    )
    for xid in xmlids:
        view = env.ref(xid, raise_if_not_found=False)
        if view:
            # Drop cached arch so the next module load uses XML from disk.
            view.with_context(lang=None).write({'arch_db': view.arch_db})
    env['ir.ui.view'].invalidate_model(['arch_db'])
