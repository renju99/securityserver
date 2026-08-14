# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    Parent = env['incident.form.parent']
    ok = Parent.seed_from_excel_json()
    _logger.info('18.0.1.1.141 form definition seed: %s', ok)
