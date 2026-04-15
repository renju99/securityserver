"""Backfill bid_project.client_name before NOT NULL is enforced on upgrade."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'bid_project'
        )
        """
    )
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        UPDATE bid_project
        SET client_name = COALESCE(
            NULLIF(TRIM(client_name), ''),
            NULLIF(TRIM(name), ''),
            '-'
        )
        WHERE client_name IS NULL OR TRIM(COALESCE(client_name, '')) = ''
        """
    )
    n = cr.rowcount
    if n:
        _logger.info("sales_bid_board pre-migrate: filled %s bid_project.client_name row(s)", n)
