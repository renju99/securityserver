# -*- coding: utf-8 -*-
"""Emergency Procedure PDF Report Controller."""

from odoo import api, models
import datetime


class ReportEmergencyProcedurePdf(models.AbstractModel):
    """
    Controller for Emergency Procedure PDF Report.
    
    This class prepares data for the emergency procedure document template.
    """
    
    _name = 'report.guardpro.report_emergency_procedure_document'
    _description = 'Emergency Procedure Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Prepare report data.
        
        Args:
            docids: IDs of emergency procedure records to generate report for
            data: Additional data passed to report
            
        Returns:
            dict: Dictionary of values available in the report template
        """
        docs = self.env['emergency.procedure'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'emergency.procedure',
            'docs': docs,
            'data': data,
            'datetime': datetime,
        }










