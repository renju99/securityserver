"""Map legacy bid.project.state into outcome_status and is_priority before the state column is dropped."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND column_name = 'state'
        """,
        ("bid_project",),
    )
    if not cr.fetchone():
        return

    cr.execute("ALTER TABLE bid_project ADD COLUMN IF NOT EXISTS outcome_status VARCHAR")
    cr.execute("ALTER TABLE bid_project ADD COLUMN IF NOT EXISTS is_priority BOOLEAN DEFAULT FALSE")

    cr.execute(
        """
        UPDATE bid_project
        SET outcome_status = CASE
                WHEN state = 'declined' THEN 'closed'
                ELSE 'open'
            END,
            is_priority = (state = 'priority')
        """
    )
    cr.execute(
        """
        UPDATE bid_project SET outcome_status = 'open'
        WHERE outcome_status IS NULL
        """
    )
    _logger.info("sales_bid_board: migrated bid.project.state -> outcome_status / is_priority")
