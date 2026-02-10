# -*- coding: utf-8 -*-

from odoo import models, api


class GuardPerformanceReport(models.AbstractModel):
    """Guard Performance Review PDF Report."""
    _name = 'report.guardpro.guard_performance_report_template'
    _description = 'Guard Performance Review PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for guard performance reviews."""
        docs = self.env['guard.performance.review'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'guard.performance.review',
            'docs': docs,
            'data': data,
        }

