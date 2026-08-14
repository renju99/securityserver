# -*- coding: utf-8 -*-
"""Sync zone-restricted group for users with existing zone assignments."""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    users = env['res.users'].search([('zone_ids', '!=', False)])
    if users:
        users._sync_zone_access_group()
