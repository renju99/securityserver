# -*- coding: utf-8 -*-
"""Shift Report PDF generator."""

from odoo import models, api


class ShiftReportPdf(models.AbstractModel):
    """Abstract model for shift report PDF generation."""

    _name = 'report.guardpro.shift_report_pdf_template'
    _description = 'Shift Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for the shift report."""
        docs = self.env['guard.shift'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'guard.shift',
            'docs': docs,
            'data': data,
        }

