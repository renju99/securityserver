# -*- coding: utf-8 -*-
"""Credential Compliance Summary PDF Report Controller."""

from odoo import api, models


class ReportCredentialComplianceSummaryPdf(models.AbstractModel):
    """Controller for Credential Compliance Summary PDF Report."""
    
    _name = 'report.guardpro.report_credential_compliance_summary_document'
    _description = 'Credential Compliance Summary Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare credential compliance summary report data."""
        docs = self.env['guard.credential'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'guard.credential',
            'docs': docs,
            'data': data,
            'format_date': self._format_date,
        }
    
    def _format_date(self, date_value):
        """Format date for display."""
        if not date_value:
            return 'N/A'
        return date_value.strftime('%B %d, %Y')










