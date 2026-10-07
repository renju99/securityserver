# -*- coding: utf-8 -*-
"""Attach default incident SLA policies to open incidents and refresh stored SLA fields."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

OPEN_STATUSES = ('draft', 'submitted', 'under_review', 'investigating')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Policy = env['incident.sla.policy'].sudo()
    Incident = env['incident.report'].sudo()

    policy_count = Policy.with_context(active_test=False).search_count([])
    _logger.info('SLA post-migrate: %s incident.sla.policy record(s)', policy_count)

    open_incidents = Incident.search([('status', 'in', list(OPEN_STATUSES))])
    if not open_incidents:
        _logger.info('SLA post-migrate: no open incidents to recompute')
        return

    # Stored sla_policy_id only recomputes when severity/site/category change.
    open_incidents.invalidate_recordset([
        'sla_policy_id',
        'sla_response_deadline',
        'sla_resolution_deadline',
        'sla_status',
        'sla_breach',
    ])
    open_incidents._compute_sla_policy()
    open_incidents._compute_sla_deadlines()
    open_incidents._compute_sla_status()

    with_policy = open_incidents.filtered('sla_policy_id')
    breached = with_policy.filtered('sla_breach')
    _logger.info(
        'SLA post-migrate: open=%s with_policy=%s breached=%s',
        len(open_incidents),
        len(with_policy),
        len(breached),
    )
