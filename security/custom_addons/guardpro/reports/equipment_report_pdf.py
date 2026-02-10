# -*- coding: utf-8 -*-

from odoo import models, api


class EquipmentReport(models.AbstractModel):
    """Equipment Log PDF Report."""
    _name = 'report.guardpro.equipment_report_template'
    _description = 'Equipment Log PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for equipment."""
        docs = self.env['guardpro.equipment'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'guardpro.equipment',
            'docs': docs,
            'data': data,
        }

