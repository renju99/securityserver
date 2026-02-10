# -*- coding: utf-8 -*-

from odoo import models, api


class SLAManagementReport(models.AbstractModel):
    """SLA Management PDF Report."""
    _name = 'report.guardpro.sla_management_report_template'
    _description = 'SLA Management PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for SLA performance."""
        docs = self.env['sla.performance'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'sla.performance',
            'docs': docs,
            'data': data,
        }

