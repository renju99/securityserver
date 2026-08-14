"""Enforce site-scoped domains on previously unrestricted record rules."""

import logging

_logger = logging.getLogger(__name__)

# xml_id (without module prefix) -> new domain_force
_SITE_SCOPED_UPDATES = {
    # Tasks
    'guard_task_rule_supervisor': "[('site_id', 'in', user.site_ids.ids)]",
    'guard_task_rule_manager': "[('site_id', 'in', user.site_ids.ids)]",
    # Credentials / HR (supervisor+manager rules)
    'guard_credential_supervisor_rule': "[('guard_id.site_ids', 'in', user.site_ids.ids)]",
    'guard_background_check_supervisor_rule': "[('guard_id.site_ids', 'in', user.site_ids.ids)]",
    'guard_drug_test_supervisor_rule': "[('guard_id.site_ids', 'in', user.site_ids.ids)]",
    'guard_vaccination_supervisor_rule': "[('guard_id.site_ids', 'in', user.site_ids.ids)]",
    # Performance
    'guard_performance_metric_supervisor_rule': "[('guard_id.site_ids', 'in', user.site_ids.ids)]",
    'guard_performance_metric_manager_rule': "[('guard_id.site_ids', 'in', user.site_ids.ids)]",
    'guard_performance_review_supervisor_rule': "[('guard_id.site_ids', 'in', user.site_ids.ids)]",
    'guard_performance_review_manager_rule': "[('guard_id.site_ids', 'in', user.site_ids.ids)]",
    'guard_performance_badge_supervisor_rule': "[('guard_id.site_ids', 'in', user.site_ids.ids)]",
    'guard_performance_badge_manager_rule': "[('guard_id.site_ids', 'in', user.site_ids.ids)]",
    # Portal enhancements
    'incident_status_update_manager_rule': "[('site_id', 'in', user.site_ids.ids)]",
    'guard_location_live_manager_rule': "[('site_id', 'in', user.site_ids.ids)]",
    # Complaints
    'resident_complaint_manager_rule': "[('site_id', 'in', user.site_ids.ids)]",
}


def migrate(cr, version):
    updated = 0
    for xml_id, domain in _SITE_SCOPED_UPDATES.items():
        cr.execute(
            """
            UPDATE ir_rule r
               SET domain_force = %s,
                   name = CASE
                       WHEN r.name ILIKE '%%All %%' OR r.name ILIKE '%%Full Access%%'
                       THEN replace(replace(r.name, 'All ', 'Assigned-Sites '),
                                    'Full Access', 'Assigned Sites')
                       ELSE r.name
                   END
              FROM ir_model_data d
             WHERE d.res_id = r.id
               AND d.model = 'ir.rule'
               AND d.module = 'guardpro'
               AND d.name = %s
            """,
            (domain, xml_id),
        )
        updated += cr.rowcount

    # Remove admin from supervisor credential/complaint rules that previously
    # bundled Admin into the same unrestricted rule (admin has dedicated rules
    # created by XML on upgrade with noupdate=0).
    for xml_id, group_xml in (
        ('guard_credential_supervisor_rule', 'group_guardpro_admin'),
        ('guard_background_check_supervisor_rule', 'group_guardpro_admin'),
        ('guard_drug_test_supervisor_rule', 'group_guardpro_admin'),
        ('guard_vaccination_supervisor_rule', 'group_guardpro_admin'),
        ('resident_complaint_manager_rule', 'group_guardpro_admin'),
        ('guard_performance_metric_manager_rule', 'group_guardpro_admin'),
        ('guard_performance_review_manager_rule', 'group_guardpro_admin'),
        ('guard_performance_badge_manager_rule', 'group_guardpro_admin'),
    ):
        cr.execute(
            """
            DELETE FROM rule_group_rel rel
             USING ir_model_data dr, ir_model_data dg
             WHERE rel.rule_group_id = dr.res_id
               AND rel.group_id = dg.res_id
               AND dr.module = 'guardpro' AND dr.model = 'ir.rule' AND dr.name = %s
               AND dg.module = 'guardpro' AND dg.model = 'res.groups' AND dg.name = %s
            """,
            (xml_id, group_xml),
        )

    _logger.info(
        'Site-scoped %s legacy unrestricted record rule domain(s) for isolation fix',
        updated,
    )
