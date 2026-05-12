# -*- coding: utf-8 -*-
from odoo import fields, models


class AttendanceBulkCheckoutWizard(models.TransientModel):
    _name = 'attendance.bulk.checkout.wizard'
    _description = 'Bulk check-out open attendances'

    employee_ids = fields.Many2many('hr.employee', string='Employees', required=True)
    checkout_time = fields.Datetime(string='Check out time', required=True, default=fields.Datetime.now)
    notes = fields.Text(string='Notes')

    def action_apply(self):
        self.ensure_one()
        Attendance = self.env['hr.attendance']
        for emp in self.employee_ids:
            open_att = Attendance.search(
                [('employee_id', '=', emp.id), ('check_out', '=', False)],
                order='check_in desc',
                limit=1,
            )
            if open_att:
                vals = {'check_out': self.checkout_time, 'out_mode': 'manual'}
                if self.notes:
                    body = open_att.work_context_note or ''
                    body = (body + '\n' + self.notes).strip() if body else self.notes
                    vals['work_context_note'] = body
                open_att.write(vals)
        return {'type': 'ir.actions.act_window_close'}
