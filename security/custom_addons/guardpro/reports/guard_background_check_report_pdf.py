# -*- coding: utf-8 -*-

from odoo import models, api


class GuardBackgroundCheckReport(models.AbstractModel):
    """Guard Background Check PDF Report."""
    _name = 'report.guardpro.guard_background_check_report_template'
    _description = 'Guard Background Check PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for guard background checks."""
        docs = self.env['guard.background.check'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'guard.background.check',
            'docs': docs,
            'data': data,
        }

