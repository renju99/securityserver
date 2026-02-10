# -*- coding: utf-8 -*-
"""Package Delivery Summary PDF Report Controller."""

from odoo import api, fields, models


class ReportPackageDeliverySummaryPdf(models.AbstractModel):
    """Controller for Package Delivery Summary PDF Report."""
    
    _name = 'report.guardpro.report_package_delivery_summary_document'
    _description = 'Package Delivery Summary Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare package delivery summary report data."""
        docs = self.env['package.management'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'package.management',
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





