# -*- coding: utf-8 -*-
"""SLA Performance Report PDF Controller."""

from odoo import api, fields, models


class ReportSLAPerformancePdf(models.AbstractModel):
    """Controller for SLA Performance PDF Report."""
    
    _name = 'report.guardpro.report_sla_performance_document'
    _description = 'SLA Performance Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare SLA performance report data."""
        docs = self.env['sla.definition'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'sla.definition',
            'docs': docs,
            'data': data,
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










