"""Sync guard user site_ids from recent shift sites; analytics AccessError fix."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Guards with empty user.site_ids but shifts at a site are invisible under
    # guard.profile rules (site_ids in user.site_ids) while their shifts remain
    # readable — analytics then AccessErrors on shift.guard_id.name.
    cr.execute(
        """
        INSERT INTO guardpro_user_site_rel (user_id, site_id)
        SELECT DISTINCT gp.user_id, gs.site_id
          FROM guard_profile gp
          JOIN guard_shift gs ON gs.guard_id = gp.id
         WHERE gp.user_id IS NOT NULL
           AND gs.site_id IS NOT NULL
           AND NOT EXISTS (
               SELECT 1
                 FROM guardpro_user_site_rel rel
                WHERE rel.user_id = gp.user_id
                  AND rel.site_id = gs.site_id
           )
        """
    )
    _logger.info('Synced guard site assignments from shifts: %s rows', cr.rowcount)
