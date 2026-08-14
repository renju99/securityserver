"""Clear past / missed patrol reminders so they never flood mobile."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Anything whose shift already started more than 30 minutes ago is
    # outside both the 30-min and 10-min show windows — clear it.
    cr.execute("""
        UPDATE tour_patrol_reminder r
           SET is_acknowledged = TRUE,
               acknowledged_date = NOW() AT TIME ZONE 'UTC'
          FROM guard_shift s
         WHERE s.id = r.shift_id
           AND r.is_acknowledged = FALSE
           AND (
                s.start_datetime IS NULL
                OR s.start_datetime < (NOW() AT TIME ZONE 'UTC' - INTERVAL '30 minutes')
                OR s.status IN ('cancelled', 'no_show', 'completed')
           )
    """)
    _logger.info(
        'Auto-acked %s past/missed patrol reminder(s)',
        cr.rowcount,
    )
