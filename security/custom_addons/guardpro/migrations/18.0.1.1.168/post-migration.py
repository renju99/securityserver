"""Expire stuck emergency broadcasts; disable invalid 0,0 geofences."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Ack leftover pending emergency acks so popups cannot remain stuck
    cr.execute(
        """
        UPDATE emergency_broadcast_acknowledgment
           SET is_acknowledged = TRUE,
               acknowledged_date = COALESCE(acknowledged_date, NOW() AT TIME ZONE 'UTC')
         WHERE COALESCE(is_acknowledged, FALSE) = FALSE
        """
    )
    _logger.info('Acknowledged pending emergency acks: %s', cr.rowcount)

    cr.execute(
        """
        UPDATE emergency_broadcast
           SET state = 'expired'
         WHERE state = 'sent'
        """
    )
    _logger.info('Expired stuck emergency broadcasts: %s', cr.rowcount)

    # Sites with Null-Island center flood outside-geofence alerts
    cr.execute(
        """
        UPDATE client_site
           SET geofence_enabled = FALSE
         WHERE COALESCE(geofence_enabled, FALSE) = TRUE
           AND COALESCE(latitude, 0) = 0
           AND COALESCE(longitude, 0) = 0
        """
    )
    _logger.info('Disabled geofence on unconfigured sites: %s', cr.rowcount)

    cr.execute(
        """
        UPDATE geofence_alert g
           SET status = 'false_alarm',
               resolved_date = NOW() AT TIME ZONE 'UTC',
               notes = COALESCE(g.notes, '') || E'\n[migrate 168] false_alarm: site geofence center was 0,0'
          FROM client_site s
         WHERE s.id = g.site_id
           AND g.status IN ('new', 'acknowledged')
           AND COALESCE(s.latitude, 0) = 0
           AND COALESCE(s.longitude, 0) = 0
        """
    )
    _logger.info('Closed 0,0-site geofence alerts: %s', cr.rowcount)
