# -*- coding: utf-8 -*-
"""Incident Investigation PDF Report Controller."""

from odoo import api, fields, models
import datetime


class ReportIncidentInvestigationPdf(models.AbstractModel):
    """
    Controller for Incident Investigation PDF Report.
    
    This class prepares data and performs calculations for the investigation report template.
    """
    
    _name = 'report.guardpro.report_incident_investigation_document'
    _description = 'Incident Investigation Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Prepare report data and calculations.
        
        Args:
            docids: IDs of investigation records to generate report for
            data: Additional data passed to report
            
        Returns:
            dict: Dictionary of values available in the report template
        """
        docs = self.env['incident.investigation'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'incident.investigation',
            'docs': docs,
            'data': data,
            'datetime': datetime,
            # Helper functions
            'format_date': self._format_date,
            'format_datetime': self._format_datetime,
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










