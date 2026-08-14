"""Clear stuck mobile alert pipelines (emergency + task assignment)."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE emergency_broadcast_acknowledgment
           SET is_acknowledged = TRUE,
               acknowledged_date = COALESCE(acknowledged_date, (NOW() AT TIME ZONE 'UTC'))
         WHERE COALESCE(is_acknowledged, FALSE) = FALSE
        """
    )
    _logger.info('Acked emergency rows: %s', cr.rowcount)

    cr.execute(
        """
        UPDATE emergency_broadcast
           SET state = 'expired'
         WHERE state = 'sent'
        """
    )
    _logger.info('Expired broadcasts: %s', cr.rowcount)

    # Un-ack'd assignment notifications block the TWA with a modal that feels
    # like an "emergency" flood when several tasks are waiting.
    cr.execute(
        """
        UPDATE guard_task
           SET mobile_assignment_ack = TRUE,
               mobile_assignment_acked_on = COALESCE(
                    mobile_assignment_acked_on, (NOW() AT TIME ZONE 'UTC')
               )
         WHERE COALESCE(mobile_assignment_ack, FALSE) = FALSE
           AND assigned_to IN (
                SELECT id FROM guard_profile WHERE user_id IN (
                    SELECT id FROM res_users WHERE login = 'test@berkeleyuae.com'
                )
           )
        """
    )
    _logger.info('Acked Test Guard task assignment alerts: %s', cr.rowcount)
