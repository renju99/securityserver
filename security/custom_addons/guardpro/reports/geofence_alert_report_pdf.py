# -*- coding: utf-8 -*-
"""Geofence Alert PDF Report Controller."""

from odoo import api, fields, models
import datetime


class ReportGeofenceAlertPdf(models.AbstractModel):
    """
    Controller for Geofence Alert PDF Report.
    
    This class prepares data for the geofence violation report template.
    """
    
    _name = 'report.guardpro.report_geofence_alert_document'
    _description = 'Geofence Alert Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Prepare geofence alert report data.
        
        Args:
            docids: IDs of geofence alert records
            data: Additional data passed to report
            
        Returns:
            dict: Dictionary of values available in the report template
        """
        docs = self.env['geofence.alert'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'geofence.alert',
            'docs': docs,
            'data': data,
            'datetime': datetime,
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










