# -*- coding: utf-8 -*-

from odoo import models, api


class GuardDrugTestReport(models.AbstractModel):
    """Guard Drug Test PDF Report."""
    _name = 'report.guardpro.guard_drug_test_report_template'
    _description = 'Guard Drug Test PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for guard drug tests."""
        docs = self.env['guard.drug.test'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'guard.drug.test',
            'docs': docs,
            'data': data,
        }

