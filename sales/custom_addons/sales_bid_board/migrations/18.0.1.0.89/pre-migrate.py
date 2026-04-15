"""Convert progress columns from integer to text before ORM sync (PostgreSQL)."""

import logging

_logger = logging.getLogger(__name__)

_NUMERIC = ("integer", "bigint", "smallint")


def migrate(cr, version):
    for table in ("bid_project", "bid_project_create_wizard"):
        cr.execute(
            """
            SELECT data_type FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s AND column_name = 'progress'
            """,
            (table,),
        )
        row = cr.fetchone()
        if not row or row[0] not in _NUMERIC:
            continue
        cr.execute(
            """
            ALTER TABLE {}
            ALTER COLUMN progress TYPE text USING progress::text
            """.format(table)
        )
        _logger.info("sales_bid_board pre-migrate: %s.progress -> text", table)
