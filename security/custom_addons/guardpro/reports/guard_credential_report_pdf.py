# -*- coding: utf-8 -*-

from odoo import models, api


class GuardCredentialReport(models.AbstractModel):
    """Guard Credential Certificate PDF Report."""
    _name = 'report.guardpro.guard_credential_report_template'
    _description = 'Guard Credential Certificate PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for guard credentials."""
        docs = self.env['guard.credential'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'guard.credential',
            'docs': docs,
            'data': data,
        }

