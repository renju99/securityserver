# -*- coding: utf-8 -*-
"""Record rules: relax domain validation when equipment.handover is not in the registry.

During module upgrades, ir.rule _check_domain resolves the model via env[model]; if workers
are stale or the class was not loaded yet, that raises and blocks XML. We skip checks only
for equipment.handover when it is missing; after restart, validation runs on those rules again.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

_HANDOVER_MODEL = 'equipment.handover'


class IrRule(models.Model):
    _inherit = 'ir.rule'

    @api.constrains('active', 'domain_force', 'model_id')
    def _check_domain(self):
        if not self:
            return
        other = self.filtered(lambda r: r.model_id.model != _HANDOVER_MODEL)
        handover = self - other
        super(IrRule, other)._check_domain()
        handover_ready = handover.filtered(lambda r: _HANDOVER_MODEL in self.env)
        handover_stale = handover - handover_ready
        for rule in handover_stale:
            _logger.warning(
                'guardpro: deferred ir.rule domain validation for %r (%s not in registry yet; '
                'restart Odoo workers after deploying equipment.py).',
                rule.name,
                _HANDOVER_MODEL,
            )
        super(IrRule, handover_ready)._check_domain()
