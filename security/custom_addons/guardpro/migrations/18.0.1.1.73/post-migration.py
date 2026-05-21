# -*- coding: utf-8 -*-
"""Build tour checkpoint sequence lines for existing tours on upgrade."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    env['security.tour'].migrate_all_tour_checkpoint_sequences()
