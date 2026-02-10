# -*- coding: utf-8 -*-
"""Emergency Drill Report PDF Controller."""

from odoo import api, fields, models


class ReportEmergencyDrillPdf(models.AbstractModel):
    """Controller for Emergency Drill Report PDF."""
    
    _name = 'report.guardpro.report_emergency_drill_document'
    _description = 'Emergency Drill Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare emergency drill report data."""
        docs = self.env['emergency.drill'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'emergency.drill',
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




