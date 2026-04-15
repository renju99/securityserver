"""Before loading new Selection values: bonds, contract duration, KPI default."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        "UPDATE bid_project SET tender_bond = %s WHERE tender_bond = %s",
        ("not_required", "none"),
    )
    n1 = cr.rowcount
    cr.execute(
        "UPDATE bid_project SET tender_bond = %s WHERE tender_bond IN ('lt5', '5to10', 'gt10')",
        ("required_remarks",),
    )
    n2 = cr.rowcount
    cr.execute(
        "UPDATE bid_project SET performance_bond = %s WHERE performance_bond = %s",
        ("not_required", "none"),
    )
    n3 = cr.rowcount
    cr.execute(
        "UPDATE bid_project SET performance_bond = %s WHERE performance_bond IN ('lt5', '5to10', 'gt10')",
        ("required_remarks",),
    )
    n4 = cr.rowcount
    cr.execute(
        "UPDATE bid_project SET contract_duration = %s WHERE contract_duration = %s",
        ("6y", "3y_plus"),
    )
    n5 = cr.rowcount
    if any((n1, n2, n3, n4, n5)):
        _logger.info(
            "sales_bid_board pre-migrate: tender_bond rows=%s+%s performance_bond=%s+%s duration_3y_plus=%s",
            n1,
            n2,
            n3,
            n4,
            n5,
        )
