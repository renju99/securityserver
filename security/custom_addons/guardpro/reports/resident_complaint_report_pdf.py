# -*- coding: utf-8 -*-

from odoo import models, api


class ResidentComplaintReport(models.AbstractModel):
    """Resident Complaint PDF Report."""
    _name = 'report.guardpro.resident_complaint_report_template'
    _description = 'Resident Complaint PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for resident complaints."""
        docs = self.env['resident.complaint'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'resident.complaint',
            'docs': docs,
            'data': data,
        }

