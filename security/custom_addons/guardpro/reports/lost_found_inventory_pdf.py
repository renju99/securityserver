# -*- coding: utf-8 -*-
"""Lost & Found Inventory PDF Report Controller."""

import datetime
from odoo import api, models, fields


class ReportLostFoundInventoryPdf(models.AbstractModel):
    """Controller for Lost & Found Inventory PDF Report."""
    
    _name = 'report.guardpro.report_lost_found_inventory_document'
    _description = 'Lost & Found Inventory Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare lost & found inventory report data."""
        docs = self.env['lost.found.item'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'lost.found.item',
            'docs': docs,
            'data': data,
            'format_date': self._format_date,
        }
    
    def _format_date(self, date_value):
        """Format date for display."""
        if not date_value:
            return 'N/A'
        # Convert to user timezone if it's a datetime
        if isinstance(date_value, datetime.datetime):
            date_value = fields.Datetime.context_timestamp(self, date_value)
        return date_value.strftime('%B %d, %Y')

