# -*- coding: utf-8 -*-
"""Migrate incident mail templates from legacy ${} to Odoo 18 {{ }} syntax."""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['mail.template']._guardpro_migrate_odoo18_inline_templates()
