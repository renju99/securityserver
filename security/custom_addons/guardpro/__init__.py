# -*- coding: utf-8 -*-
"""GuardLink - Comprehensive Security Guard Management System."""


def post_init_hook(cr, registry):
    """On first install only: fail if handover model did not register.

    Odoo does not run post_init_hook on module upgrade, only on *install*.
    """
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
