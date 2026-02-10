# -*- coding: utf-8 -*-

from odoo import models, api


class GuardTaskReport(models.AbstractModel):
    """Guard Task Assignment PDF Report."""
    _name = 'report.guardpro.guard_task_report_template'
    _description = 'Guard Task Assignment PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report data for guard tasks."""
        docs = self.env['guard.task'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'guard.task',
            'docs': docs,
            'data': data,
        }

