# -*- coding: utf-8 -*-

from odoo import models, api


class LostFoundReport(models.AbstractModel):
    """Lost & Found PDF Report."""
    _name = 'report.guardpro.lost_found_report_template'
    _description = 'Lost & Found PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for lost & found items."""
        docs = self.env['lost.found.item'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'lost.found.item',
            'docs': docs,
            'data': data,
        }

