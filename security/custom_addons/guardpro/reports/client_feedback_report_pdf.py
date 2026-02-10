# -*- coding: utf-8 -*-

from odoo import models, api


class ClientFeedbackReport(models.AbstractModel):
    """Client Feedback PDF Report."""
    _name = 'report.guardpro.client_feedback_report_template'
    _description = 'Client Feedback PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for client feedback."""
        docs = self.env['client.feedback'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'client.feedback',
            'docs': docs,
            'data': data,
        }

