# -*- coding: utf-8 -*-

from odoo import models, api


class GuardVaccinationReport(models.AbstractModel):
    """Guard Vaccination PDF Report."""
    _name = 'report.guardpro.guard_vaccination_report_template'
    _description = 'Guard Vaccination PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for guard vaccinations."""
        docs = self.env['guard.vaccination'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'guard.vaccination',
            'docs': docs,
            'data': data,
        }

