# -*- coding: utf-8 -*-
"""Equipment Maintenance History PDF Report Controller."""

from odoo import api, models


class ReportEquipmentMaintenanceHistoryPdf(models.AbstractModel):
    """Controller for Equipment Maintenance History PDF Report."""
    
    _name = 'report.guardpro.report_equipment_maintenance_history_document'
    _description = 'Equipment Maintenance History Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare equipment maintenance history report data."""
        docs = self.env['guard.equipment'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'guard.equipment',
            'docs': docs,
            'data': data,
            'format_date': self._format_date,
        }
    
    def _format_date(self, date_value):
        """Format date for display."""
        if not date_value:
            return 'N/A'
        return date_value.strftime('%B %d, %Y')










