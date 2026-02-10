# -*- coding: utf-8 -*-

from odoo import models, api


class SecurityTourRouteReport(models.AbstractModel):
    """Security Tour Route PDF Report."""
    _name = 'report.guardpro.security_tour_route_report_template'
    _description = 'Security Tour Route PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for security tour routes."""
        docs = self.env['security.tour'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'security.tour',
            'docs': docs,
            'data': data,
        }

