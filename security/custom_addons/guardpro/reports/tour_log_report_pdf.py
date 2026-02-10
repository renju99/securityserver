# -*- coding: utf-8 -*-
"""Tour Log Report PDF generator."""

from odoo import models, api


class TourLogReportPdf(models.AbstractModel):
    """Abstract model for tour log report PDF generation."""

    _name = 'report.guardpro.tour_log_report_pdf_template'
    _description = 'Tour Log Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for the tour log report."""
        docs = self.env['tour.log'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'tour.log',
            'docs': docs,
            'data': data,
        }

