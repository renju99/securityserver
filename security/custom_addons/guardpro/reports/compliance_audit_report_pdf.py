# -*- coding: utf-8 -*-

from odoo import models, api


class ComplianceAuditReport(models.AbstractModel):
    """Compliance Audit PDF Report."""
    _name = 'report.guardpro.compliance_audit_report_template'
    _description = 'Compliance Audit PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for compliance audits."""
        docs = self.env['compliance.audit'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'compliance.audit',
            'docs': docs,
            'data': data,
        }

