# -*- coding: utf-8 -*-

from odoo import models, api


class EmergencyBroadcastReport(models.AbstractModel):
    """Emergency Broadcast PDF Report."""
    _name = 'report.guardpro.emergency_broadcast_report_template'
    _description = 'Emergency Broadcast PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for emergency broadcasts."""
        docs = self.env['emergency.broadcast'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'emergency.broadcast',
            'docs': docs,
            'data': data,
        }

