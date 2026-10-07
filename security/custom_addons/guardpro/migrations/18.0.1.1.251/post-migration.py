# -*- coding: utf-8 -*-
"""Enable GPS retention cron and set 90-day default."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ICP = env['ir.config_parameter'].sudo()
    ICP.set_param('guardpro.location_history_retention', '90')

    cron = env.ref('guardpro.cron_cleanup_location_history', raise_if_not_found=False)
    if cron:
        cron.write({
            'name': 'GuardLink: Purge Old Location History (retention)',
            'active': True,
            'code': 'model.cleanup_old_records()',
            'interval_number': 1,
            'interval_type': 'days',
        })
        _logger.info('Activated GPS retention cron id=%s (90 days)', cron.id)
    else:
        _logger.warning('cron_cleanup_location_history not found')
