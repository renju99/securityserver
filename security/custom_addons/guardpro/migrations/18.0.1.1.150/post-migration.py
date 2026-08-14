"""Backfill site isolation fields and enforce updated record-rule domains."""

import logging

_logger = logging.getLogger(__name__)

_DOMAIN_UPDATES = {
    'rule_equipment_guard_portal':
        "['|', ('assigned_to.user_id', '=', user.id), ('assigned_site', 'in', user.site_ids.ids)]",
    'rule_equipment_assigned_sites':
        "[('assigned_site', 'in', user.site_ids.ids)]",
    'rule_equipment_manager':
        "[('assigned_site', 'in', user.site_ids.ids)]",
    'rule_compliance_audit_item_manager_supervisor':
        "[('audit_id.site_id', 'in', user.site_ids.ids)]",
    'rule_compliance_audit_item_site_based':
        "[('audit_id.site_id', 'in', user.site_ids.ids)]",
    'rule_emergency_broadcast_guard_portal':
        "['|', ('site_id', 'in', user.site_ids.ids), ('broadcast_type', '=', 'all')]",
    'rule_emergency_broadcast_assigned_sites':
        "['|', ('site_id', 'in', user.site_ids.ids), ('broadcast_type', '=', 'all')]",
    'rule_emergency_broadcast_acknowledgment_assigned_sites':
        "['|', ('broadcast_id.site_id', 'in', user.site_ids.ids), ('broadcast_id.broadcast_type', '=', 'all')]",
    'visitor_watchlist_rule_reception':
        "[('site_ids', 'in', user.site_ids.ids)]",
    'visitor_watchlist_rule_supervisor':
        "[('site_ids', 'in', user.site_ids.ids)]",
    'resident_complaint_client_rule':
        "[('site_id', 'in', user.site_ids.ids)]",
}


def migrate(cr, version):
    for xml_id, domain in _DOMAIN_UPDATES.items():
        cr.execute(
            """
            UPDATE ir_rule r
               SET domain_force = %s
              FROM ir_model_data d
             WHERE d.res_id = r.id
               AND d.model = 'ir.rule'
               AND d.module = 'guardpro'
               AND d.name = %s
            """,
            (domain, xml_id),
        )

    # Deactivate legacy global watchlist rule (replaced by site-scoped rules)
    cr.execute(
        """
        UPDATE ir_rule r
           SET active = FALSE
          FROM ir_model_data d
         WHERE d.res_id = r.id
           AND d.model = 'ir.rule'
           AND d.module = 'guardpro'
           AND d.name = 'rule_visitor_watchlist_all'
        """
    )

    # Do not auto-share historical watchlist entries across every site.
    # Unassigned entries remain admin-only until sites are set explicitly.

    # Backfill host sites from historical visitor entries
    cr.execute(
        """
        INSERT INTO visitor_host_site_rel (host_id, site_id)
        SELECT DISTINCT v.host_id, v.site_id
          FROM visitor_management v
         WHERE v.host_id IS NOT NULL
           AND v.site_id IS NOT NULL
           AND NOT EXISTS (
                SELECT 1 FROM visitor_host_site_rel r
                 WHERE r.host_id = v.host_id AND r.site_id = v.site_id
           )
        """
    )
    _logger.info('Visitor host site backfill rows: %s', cr.rowcount)

    _logger.info('Completed guardpro 18.0.1.1.150 site-isolation migration')
