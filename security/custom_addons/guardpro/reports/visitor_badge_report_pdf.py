# -*- coding: utf-8 -*-
"""Visitor Badge PDF Report."""

from odoo import models


class VisitorBadgeReport(models.AbstractModel):
    """
    Visitor Badge PDF Report.
    
    Generates a printable visitor badge with QR code, photo, and access details.
    """
    
    _name = 'report.guardpro.report_visitor_badge_document'
    _description = 'Visitor Badge Report'
    
    def _get_report_values(self, docids, data=None):
        """
        Get report values for visitor badge.
        
        Args:
            docids: List of visitor management record IDs
            data: Additional data from context
            
        Returns:
            dict: Report data with visitor records
        """
        visitors = self.env['visitor.management'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'visitor.management',
            'docs': visitors,
            'data': data,
        }

