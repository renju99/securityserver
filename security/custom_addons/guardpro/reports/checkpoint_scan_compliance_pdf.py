# -*- coding: utf-8 -*-
"""Checkpoint Scan Compliance PDF Report Controller."""

from odoo import api, fields, models


class ReportCheckpointScanCompliancePdf(models.AbstractModel):
    """
    Controller for Checkpoint Scan Compliance PDF Report.
    
    This class prepares checkpoint scan compliance data for the report template.
    """
    
    _name = 'report.guardpro.report_checkpoint_scan_compliance_document'
    _description = 'Checkpoint Scan Compliance Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Prepare checkpoint scan compliance report data.
        
        Args:
            docids: IDs of checkpoint scan records
            data: Additional data passed to report
            
        Returns:
            dict: Dictionary of values available in the report template
        """
        docs = self.env['checkpoint.scan'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'checkpoint.scan',
            'docs': docs,
            'data': data,
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










