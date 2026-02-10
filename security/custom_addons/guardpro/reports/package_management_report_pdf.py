# -*- coding: utf-8 -*-

from odoo import models, api


class PackageManagementReport(models.AbstractModel):
    """Package Management PDF Report."""
    _name = 'report.guardpro.package_management_report_template'
    _description = 'Package Management PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for package management."""
        docs = self.env['package.management'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'package.management',
            'docs': docs,
            'data': data,
        }

