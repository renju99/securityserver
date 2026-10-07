# -*- coding: utf-8 -*-
"""Remove CCTV monitoring feature leftovers before model drop."""

import logging

_logger = logging.getLogger(__name__)

MENU_XMLIDS = (
    'menu_cctv_manage_cameras',
    'menu_guardpro_cctv',
)

ACTION_XMLIDS = (
    'action_cctv_monitoring',
    'action_cctv_camera',
    'action_cctv_viewer_wizard',
    'action_cctv_monitoring_view_list',
    'action_cctv_monitoring_view_kanban',
    'action_cctv_monitoring_view_form',
)


def _delete_xmlid(cr, name):
    cr.execute(
        """
        SELECT model, res_id FROM ir_model_data
         WHERE module = 'guardpro' AND name = %s
        """,
        (name,),
    )
    row = cr.fetchone()
    if not row:
        return
    model, res_id = row
    table = model.replace('.', '_')
    # Menus: use cascade-safe delete via ir.ui.menu
    try:
        if model == 'ir.ui.menu':
            cr.execute('DELETE FROM ir_ui_menu WHERE id = %s', (res_id,))
        elif model == 'ir.actions.act_window':
            cr.execute('DELETE FROM ir_act_window_view WHERE act_window_id = %s', (res_id,))
            cr.execute('DELETE FROM ir_act_window WHERE id = %s', (res_id,))
        elif model == 'ir.actions.act_window.view':
            cr.execute('DELETE FROM ir_act_window_view WHERE id = %s', (res_id,))
        elif model == 'ir.ui.view':
            cr.execute('DELETE FROM ir_ui_view WHERE id = %s', (res_id,))
        elif model == 'ir.rule':
            cr.execute('DELETE FROM ir_rule WHERE id = %s', (res_id,))
        else:
            cr.execute('DELETE FROM "%s" WHERE id = %%s' % table, (res_id,))
    except Exception as exc:
        _logger.warning('pre-migrate 250: skip delete %s (%s): %s', name, model, exc)
        return
    cr.execute(
        "DELETE FROM ir_model_data WHERE module = 'guardpro' AND name = %s",
        (name,),
    )
    _logger.info('pre-migrate 250: removed %s', name)


def migrate(cr, version):
    for name in MENU_XMLIDS + ACTION_XMLIDS:
        _delete_xmlid(cr, name)

    # Drop CCTV data tables if present (model removed from code)
    for table in (
        'cctv_viewer_wizard_cctv_camera_rel',
        'cctv_camera',
        'cctv_viewer_wizard',
    ):
        cr.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (table,),
        )
        if cr.fetchone():
            cr.execute('DROP TABLE IF EXISTS "%s" CASCADE' % table)
            _logger.info('pre-migrate 250: dropped table %s', table)

    # Clean ir.model / access leftovers by model name
    cr.execute(
        """
        DELETE FROM ir_model_access
         WHERE model_id IN (
            SELECT id FROM ir_model WHERE model IN ('cctv.camera', 'cctv.viewer.wizard')
         )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_rule
         WHERE model_id IN (
            SELECT id FROM ir_model WHERE model IN ('cctv.camera', 'cctv.viewer.wizard')
         )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'guardpro'
           AND (name LIKE '%%cctv_camera%%'
                OR name LIKE '%%cctv_viewer%%'
                OR name LIKE '%%cctv_monitoring%%'
                OR name LIKE 'menu_guardpro_cctv%%'
                OR name LIKE 'menu_cctv_%%')
        """
    )
    cr.execute(
        "DELETE FROM ir_model WHERE model IN ('cctv.camera', 'cctv.viewer.wizard')"
    )
    _logger.info('pre-migrate 250: CCTV monitoring cleanup complete')
