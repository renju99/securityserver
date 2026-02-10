# -*- coding: utf-8 -*-

from odoo import models, api


class ShiftSwapRequestReport(models.AbstractModel):
    """Shift Swap Request PDF Report."""
    _name = 'report.guardpro.shift_swap_request_report_template'
    _description = 'Shift Swap Request PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for shift swap requests."""
        docs = self.env['shift.swap.request'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'shift.swap.request',
            'docs': docs,
            'data': data,
        }

