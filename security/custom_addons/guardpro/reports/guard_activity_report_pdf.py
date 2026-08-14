# -*- coding: utf-8 -*-
"""Guard Activity Report PDF generator."""

from odoo import api, models


class GuardActivityReportPdf(models.AbstractModel):
    _name = 'report.guardpro.guard_activity_report_pdf_template'
    _description = 'Guard Activity Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['guard.activity.report'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'guard.activity.report',
            'docs': docs,
            'data': data,
        }
