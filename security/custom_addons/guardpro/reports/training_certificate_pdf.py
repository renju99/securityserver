# -*- coding: utf-8 -*-
"""Training Course Certificate PDF Report Controller."""

from odoo import api, models


class ReportTrainingCertificatePdf(models.AbstractModel):
    """
    Controller for Training Course Certificate PDF Report.
    
    This class prepares data for the certificate template.
    """
    
    _name = 'report.guardpro.report_training_certificate_document'
    _description = 'Training Certificate Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Prepare certificate report data.
        
        Args:
            docids: IDs of slide.channel.partner records (enrollments)
            data: Additional data passed to report
            
        Returns:
            dict: Dictionary of values available in the report template
        """
        docs = self.env['slide.channel.partner'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'slide.channel.partner',
            'docs': docs,
            'data': data,
            # Helper functions
            'format_date': self._format_date,
        }
    
    def _format_date(self, date_value):
        """Format date for certificate display."""
        if not date_value:
            return 'N/A'
        return date_value.strftime('%B %d, %Y')










