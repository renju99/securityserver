"""Strip Client User (Internal) from resident/tenant accounts.

Client User implies base.group_user and must not be assigned to residents.
Residents use portal + group_guardpro_resident_user only.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT d.res_id FROM ir_model_data d
         WHERE d.module = 'guardpro' AND d.name = 'group_guardpro_client_user'
           AND d.model = 'res.groups'
        """
    )
    row = cr.fetchone()
    if not row:
        _logger.warning('group_guardpro_client_user not found; skip remediation')
        return
    client_gid = row[0]

    cr.execute(
        """
        SELECT d.res_id FROM ir_model_data d
         WHERE d.module = 'guardpro' AND d.name = 'group_guardpro_resident_user'
           AND d.model = 'res.groups'
        """
    )
    row = cr.fetchone()
    resident_gid = row[0] if row else None

    # 1) Anyone with both client_user and resident_user → drop client_user
    if resident_gid:
        cr.execute(
            """
            DELETE FROM res_groups_users_rel
             WHERE gid = %s
               AND uid IN (
                    SELECT uid FROM res_groups_users_rel WHERE gid = %s
               )
            """,
            (client_gid, resident_gid),
        )
        _logger.info(
            'Removed Client User from users also in Resident group: %s',
            cr.rowcount,
        )

    # 2) Anyone linked to tenant.resident → drop client_user
    cr.execute(
        """
        DELETE FROM res_groups_users_rel
         WHERE gid = %s
           AND uid IN (
                SELECT DISTINCT user_id FROM tenant_resident
                 WHERE user_id IS NOT NULL
           )
        """,
        (client_gid,),
    )
    _logger.info(
        'Removed Client User from tenant.resident linked users: %s',
        cr.rowcount,
    )

    # Ensure resident users keep portal + resident groups
    if resident_gid:
        cr.execute(
            """
            SELECT d.res_id FROM ir_model_data d
             WHERE d.module = 'base' AND d.name = 'group_portal'
               AND d.model = 'res.groups'
            """
        )
        portal_row = cr.fetchone()
        if portal_row:
            portal_gid = portal_row[0]
            cr.execute(
                """
                INSERT INTO res_groups_users_rel (gid, uid)
                SELECT %s, tr.user_id
                  FROM tenant_resident tr
                 WHERE tr.user_id IS NOT NULL
                   AND NOT EXISTS (
                        SELECT 1 FROM res_groups_users_rel r
                         WHERE r.gid = %s AND r.uid = tr.user_id
                   )
                """,
                (portal_gid, portal_gid),
            )
            cr.execute(
                """
                INSERT INTO res_groups_users_rel (gid, uid)
                SELECT %s, tr.user_id
                  FROM tenant_resident tr
                 WHERE tr.user_id IS NOT NULL
                   AND NOT EXISTS (
                        SELECT 1 FROM res_groups_users_rel r
                         WHERE r.gid = %s AND r.uid = tr.user_id
                   )
                """,
                (resident_gid, resident_gid),
            )

    _logger.info('Completed guardpro 18.0.1.1.162 client-user/resident separation')
