"""Store site_id on approval requests and backfill from related records."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Backfill from tour.log
    cr.execute(
        """
        UPDATE guard_approval_request a
           SET site_id = t.site_id
          FROM tour_log t
         WHERE a.site_id IS NULL
           AND a.reference_model = 'tour.log'
           AND a.reference_id = t.id
           AND t.site_id IS NOT NULL
        """
    )
    tours = cr.rowcount

    # Backfill from incident.report
    cr.execute(
        """
        UPDATE guard_approval_request a
           SET site_id = i.site_id
          FROM incident_report i
         WHERE a.site_id IS NULL
           AND a.reference_model = 'incident.report'
           AND a.reference_id = i.id
           AND i.site_id IS NOT NULL
        """
    )
    incidents = cr.rowcount

    # Remaining: first site on the guard's user account (guard.profile.site_ids related)
    cr.execute(
        """
        UPDATE guard_approval_request a
           SET site_id = rel.site_id
          FROM guard_profile g
          JOIN (
                SELECT DISTINCT ON (user_id) user_id, site_id
                  FROM guardpro_user_site_rel
                 ORDER BY user_id, site_id
          ) rel ON rel.user_id = g.user_id
         WHERE a.site_id IS NULL
           AND a.guard_id = g.id
           AND g.user_id IS NOT NULL
        """
    )
    guards = cr.rowcount

    _logger.info(
        'Backfilled approval site_id: tours=%s incidents=%s guards=%s',
        tours, incidents, guards,
    )
