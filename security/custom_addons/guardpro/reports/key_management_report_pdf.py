# -*- coding: utf-8 -*-

from odoo import models, api


class KeyManagementReport(models.AbstractModel):
    """Key Management PDF Report."""
    _name = 'report.guardpro.key_management_report_template'
    _description = 'Key Management PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for key transactions."""
        docs = self.env['key.transaction'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'key.transaction',
            'docs': docs,
            'data': data,
        }

