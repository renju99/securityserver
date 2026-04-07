# -*- coding: utf-8 -*-
"""GuardPro - Comprehensive Security Guard Management System."""


def post_init_hook(cr, registry):
    """Fail module install/upgrade if handover model did not register (stale or partial deploy)."""
    if 'equipment.handover' not in registry:
        raise RuntimeError(
            "guardpro: model 'equipment.handover' is missing from the Odoo registry. "
            "Deploy guardpro (including models/equipment.py with class EquipmentHandover), "
            "restart all Odoo workers, then run: "
            "odoo -u guardpro -d <database> --stop-after-init"
        )


from . import models
from . import controllers
from . import wizard
from . import reports
