"""Ensure attendance create sync is live; heal past scheduled shifts with hours."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Past shifts still "scheduled/confirmed" but with attendance → completed
    cr.execute(
        """
        UPDATE guard_shift AS s
           SET status = 'completed'
         WHERE s.status IN ('scheduled', 'confirmed')
           AND s.end_datetime < (NOW() AT TIME ZONE 'UTC')
           AND EXISTS (
               SELECT 1 FROM guard_attendance a
                WHERE a.shift_id = s.id
                  AND a.checkin_time IS NOT NULL
           )
           AND NOT EXISTS (
               SELECT 1 FROM guard_attendance a
                WHERE a.shift_id = s.id
                  AND a.checkin_time IS NOT NULL
                  AND a.checkout_time IS NULL
           )
        """
    )
    _logger.info('past scheduled/confirmed → completed: %s', cr.rowcount)

    cr.execute(
        """
        UPDATE guard_shift AS s
           SET status = 'in_progress'
         WHERE s.status IN ('scheduled', 'confirmed', 'no_show')
           AND EXISTS (
               SELECT 1 FROM guard_attendance a
                WHERE a.shift_id = s.id
                  AND a.checkin_time IS NOT NULL
                  AND a.checkout_time IS NULL
           )
        """
    )
    _logger.info('open attendance → in_progress: %s', cr.rowcount)

    cr.execute(
        """
        UPDATE guard_shift AS s
           SET status = 'completed'
         WHERE s.status = 'no_show'
           AND EXISTS (
               SELECT 1 FROM guard_attendance a
                WHERE a.shift_id = s.id
                  AND a.checkin_time IS NOT NULL
           )
           AND NOT EXISTS (
               SELECT 1 FROM guard_attendance a
                WHERE a.shift_id = s.id
                  AND a.checkin_time IS NOT NULL
                  AND a.checkout_time IS NULL
           )
        """
    )
    _logger.info('no_show with closed attendance → completed: %s', cr.rowcount)
