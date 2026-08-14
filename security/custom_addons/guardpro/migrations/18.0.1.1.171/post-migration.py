"""Repair sticky no_show shifts that have attendance / hours worked."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Open attendance on a no_show shift → in_progress
    cr.execute(
        """
        UPDATE guard_shift AS s
           SET status = 'in_progress'
         WHERE s.status = 'no_show'
           AND EXISTS (
               SELECT 1
                 FROM guard_attendance a
                WHERE a.shift_id = s.id
                  AND a.checkin_time IS NOT NULL
                  AND a.checkout_time IS NULL
           )
        """
    )
    _logger.info('no_show → in_progress (open attendance): %s', cr.rowcount)

    # Closed attendance on a no_show shift → completed
    cr.execute(
        """
        UPDATE guard_shift AS s
           SET status = 'completed'
         WHERE s.status = 'no_show'
           AND EXISTS (
               SELECT 1
                 FROM guard_attendance a
                WHERE a.shift_id = s.id
                  AND a.checkin_time IS NOT NULL
           )
           AND NOT EXISTS (
               SELECT 1
                 FROM guard_attendance a
                WHERE a.shift_id = s.id
                  AND a.checkin_time IS NOT NULL
                  AND a.checkout_time IS NULL
           )
        """
    )
    _logger.info('no_show → completed (closed attendance): %s', cr.rowcount)
