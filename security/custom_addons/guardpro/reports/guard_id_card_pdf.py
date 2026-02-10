# -*- coding: utf-8 -*-
"""Guard ID Card PDF generator."""

from odoo import models, api, fields
from datetime import datetime


class GuardIdCardReportPdf(models.AbstractModel):
    """Abstract model for guard ID card PDF generation."""

    _name = 'report.guardpro.guard_id_card_pdf_template'
    _description = 'Guard ID Card PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for the guard ID card report."""
        docs = self.env['guard.profile'].browse(docids)
        
        # Get company logo
        company = self.env.company
        company_logo = company.logo if hasattr(company, 'logo') and company.logo else False
        
        # Prepare docs with photo data
        # Force read photo field to ensure it's loaded (handles attachment=True)
        for doc in docs:
            if not doc.photo:
                # Try to fetch from attachment if not directly available
                doc._fields['photo']  # Ensure field is computed
        
        return {
            'doc_ids': docids,
            'doc_model': 'guard.profile',
            'docs': docs,
            'data': data,
            'company': company,
            'company_logo': company_logo,
            'current_date': fields.Date.context_today(self),
        }

