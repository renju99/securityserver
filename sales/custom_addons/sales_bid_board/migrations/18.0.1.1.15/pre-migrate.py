"""Backfill deadline_datetime from legacy deadline_date before deadline_date becomes computed-only."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE bid_project
        SET deadline_datetime = deadline_date::timestamp
        WHERE deadline_datetime IS NULL AND deadline_date IS NOT NULL
        """
    )
    n = cr.rowcount
    if n:
        _logger.info(
            "sales_bid_board: backfilled deadline_datetime on %s bid.project row(s) from deadline_date",
            n,
        )
