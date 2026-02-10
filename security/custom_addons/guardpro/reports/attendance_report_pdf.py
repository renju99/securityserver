# -*- coding: utf-8 -*-
"""Attendance Report PDF generator."""

from odoo import models, api


class AttendanceReportPdf(models.AbstractModel):
    """Abstract model for attendance report PDF generation."""

    _name = 'report.guardpro.attendance_report_pdf_template'
    _description = 'Attendance Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for the attendance report."""
        docs = self.env['guard.attendance'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'guard.attendance',
            'docs': docs,
            'data': data,
        }

