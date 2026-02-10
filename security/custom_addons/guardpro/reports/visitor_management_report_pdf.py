# -*- coding: utf-8 -*-

from odoo import models, api


class VisitorManagementReport(models.AbstractModel):
    """Visitor Management PDF Report."""
    _name = 'report.guardpro.visitor_management_report_template'
    _description = 'Visitor Management PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for visitor management."""
        docs = self.env['visitor.management'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'visitor.management',
            'docs': docs,
            'data': data,
        }

