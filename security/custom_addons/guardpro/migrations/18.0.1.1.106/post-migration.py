# -*- coding: utf-8 -*-
"""Patrol issues: hide FACILITY category from guard incident reports."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    cat = env.ref('guardpro.incident_cat_facility_patrol', raise_if_not_found=False)
    if cat and not cat.hide_from_guard_incidents:
        cat.write({'hide_from_guard_incidents': True})
        _logger.info('Set hide_from_guard_incidents on facility patrol category')
    patrol = env['incident.report'].search([
        '|',
        ('source', '=', 'patrol_checkpoint'),
        ('category_id.code', '=', 'FACILITY'),
    ])
    if patrol:
        patrol._compute_is_facility_patrol()
        env.flush_all()
