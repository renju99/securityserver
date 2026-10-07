# -*- coding: utf-8 -*-
"""Unblock module upgrade: clean leftover resident ACLs before group delete."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
         WHERE module = 'guardpro' AND name = 'group_guardpro_resident_user'
           AND model = 'res.groups'
        """
    )
    row = cr.fetchone()
    if not row:
        _logger.info('pre-migrate 247: resident group already gone')
        return

    group_id = row[0]

    # Clear every FK that blocks deleting res.groups
    cleanup = [
        ("DELETE FROM ir_model_access WHERE group_id = %s", (group_id,)),
        ("DELETE FROM rule_group_rel WHERE group_id = %s", (group_id,)),
        ("DELETE FROM res_groups_users_rel WHERE gid = %s", (group_id,)),
        ("DELETE FROM res_groups_implied_rel WHERE gid = %s OR hid = %s", (group_id, group_id)),
        ("DELETE FROM ir_model_fields_group_rel WHERE group_id = %s", (group_id,)),
        ("DELETE FROM ir_ui_menu_group_rel WHERE gid = %s", (group_id,)),
        ("DELETE FROM ir_ui_view_group_rel WHERE group_id = %s", (group_id,)),
        ("DELETE FROM ir_act_window_group_rel WHERE gid = %s", (group_id,)),
        ("DELETE FROM ir_act_server_group_rel WHERE gid = %s", (group_id,)),
        ("DELETE FROM ir_embedded_actions_res_groups_rel WHERE res_groups_id = %s", (group_id,)),
        ("DELETE FROM res_groups_report_rel WHERE gid = %s", (group_id,)),
        ("DELETE FROM mail_canned_response_res_groups_rel WHERE res_groups_id = %s", (group_id,)),
        ("DELETE FROM discuss_channel_res_groups_rel WHERE res_groups_id = %s", (group_id,)),
        ("UPDATE discuss_channel SET group_public_id = NULL WHERE group_public_id = %s", (group_id,)),
        ("UPDATE digest_tip SET group_id = NULL WHERE group_id = %s", (group_id,)),
        ("DELETE FROM res_groups_website_menu_rel WHERE res_groups_id = %s", (group_id,)),
        ("DELETE FROM res_groups_slide_channel_rel WHERE res_groups_id = %s", (group_id,)),
        ("DELETE FROM rel_upload_groups WHERE group_id = %s", (group_id,)),
    ]
    for sql, params in cleanup:
        cr.execute(sql, params)

    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'guardpro'
           AND name = 'access_resident_complaint_resident'
        """
    )
    _logger.info('pre-migrate 247: resident group %s cleaned for deletion', group_id)
