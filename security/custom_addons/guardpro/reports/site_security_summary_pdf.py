# -*- coding: utf-8 -*-
"""Project Security Summary PDF Report Controller."""

from odoo import api, fields, models
import datetime


class ReportSiteSecuritySummaryPdf(models.AbstractModel):
    """
    Controller for Project Security Summary PDF Report.
    
    This class prepares comprehensive site security data for the report template.
    """
    
    _name = 'report.guardpro.report_site_security_summary_document'
    _description = 'Project Security Summary Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Prepare site security summary report data.
        
        Args:
            docids: IDs of client project records
            data: Additional data passed to report
            
        Returns:
            dict: Dictionary of values available in the report template
        """
        docs = self.env['client.site'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'client.site',
            'docs': docs,
            'data': data,
            'datetime': datetime,
            # Helper functions
            'format_date': self._format_date,
            'format_datetime': self._format_datetime,
            'get_current_date': self._get_current_date,
        }
    
    def _format_date(self, date_value):
        """Format date for display."""
        if not date_value:
            return 'N/A'
        return date_value.strftime('%B %d, %Y')
    
    def _format_datetime(self, datetime_value):
        """Format datetime for display."""
        if not datetime_value:
            return 'N/A'
        # Convert to user timezone
        tz_datetime = fields.Datetime.context_timestamp(self, datetime_value)
        return tz_datetime.strftime('%B %d, %Y %I:%M %p')
    
    def _get_current_date(self):
        """Get current date formatted for display."""
        return fields.Date.context_today(self).strftime('%B %d, %Y')










