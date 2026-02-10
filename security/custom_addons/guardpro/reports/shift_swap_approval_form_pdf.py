# -*- coding: utf-8 -*-
"""Shift Swap Approval Form PDF Report Controller."""

from odoo import api, fields, models


class ReportShiftSwapApprovalPdf(models.AbstractModel):
    """
    Controller for Shift Swap Approval Form PDF Report.
    
    This class prepares data for the shift swap approval form template.
    """
    
    _name = 'report.guardpro.report_shift_swap_approval_document'
    _description = 'Shift Swap Approval Form Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Prepare shift swap approval form data.
        
        Args:
            docids: IDs of shift swap request records
            data: Additional data passed to report
            
        Returns:
            dict: Dictionary of values available in the report template
        """
        docs = self.env['shift.swap.request'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'shift.swap.request',
            'docs': docs,
            'data': data,
            # Helper functions
            'format_date': self._format_date,
            'format_datetime': self._format_datetime,
            'format_time': self._format_time,
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
    
    def _format_time(self, datetime_value):
        """Format time only for display."""
        if not datetime_value:
            return 'N/A'
        # Convert to user timezone
        tz_datetime = fields.Datetime.context_timestamp(self, datetime_value)
        return tz_datetime.strftime('%I:%M %p')










