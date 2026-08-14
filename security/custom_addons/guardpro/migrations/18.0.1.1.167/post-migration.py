"""Tighten task checklist / template record-rule domains (fail closed)."""

import logging

_logger = logging.getLogger(__name__)

_DOMAIN_UPDATES = {
    'rule_guard_task_checklist_all':
        "[('task_id.site_id', 'in', user.site_ids.ids)]",
    'rule_guard_task_template_all':
        "['|', ('site_id', 'in', user.site_ids.ids), ('site_id', '=', False)]",
    'rule_guard_task_checklist_admin':
        "[(1, '=', 1)]",
    'rule_guard_task_template_admin':
        "[(1, '=', 1)]",
    'rule_guard_task_checklist_template_admin':
        "[(1, '=', 1)]",
    'rule_guard_task_checklist_template_sites':
        "['|', ('template_id.site_id', 'in', user.site_ids.ids), ('template_id.site_id', '=', False)]",
    'rule_guard_task_checklist_item_admin':
        "[(1, '=', 1)]",
    'rule_guard_task_checklist_item_sites':
        "['|', ('template_id.site_id', 'in', user.site_ids.ids), ('template_id.site_id', '=', False)]",
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
        if cr.rowcount:
            _logger.info('Updated domain for guardpro.%s', xml_id)

    # Drop admin from the shared checklist / template rules (admin has own rules).
    for xml_id in (
        'rule_guard_task_checklist_all',
        'rule_guard_task_template_all',
    ):
        cr.execute(
            """
            DELETE FROM rule_group_rel
             WHERE rule_group_id IN (
                SELECT r.id FROM ir_rule r
                  JOIN ir_model_data d ON d.res_id = r.id
                 WHERE d.model = 'ir.rule'
                   AND d.module = 'guardpro'
                   AND d.name = %s
             )
               AND group_id IN (
                SELECT res_id FROM ir_model_data
                 WHERE model = 'res.groups'
                   AND module = 'guardpro'
                   AND name = 'group_guardpro_admin'
               )
            """,
            (xml_id,),
        )

    _logger.info('Completed guardpro 18.0.1.1.167 checklist/template visibility migration')
