"""Clear leftover shift acknowledgement outbox rows."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE guardpro_mobile_outbox
           SET acked = TRUE,
               acked_on = NOW() AT TIME ZONE 'UTC'
         WHERE acked = FALSE
           AND kind IN (
               'shift_assigned', 'shift_changed',
               'shift_cancelled', 'shift_swap_decision'
           )
    """)
    _logger.info(
        'Cleared %s pending shift acknowledgement(s)',
        cr.rowcount,
    )
