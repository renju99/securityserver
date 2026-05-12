# -*- coding: utf-8 -*-
from odoo import fields, models


class AttendanceJobCode(models.Model):
    _name = 'attendance.job.code'
    _description = 'Attendance job / activity code'
    _order = 'code'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    work_location_id = fields.Many2one('hr.work.location', string='Work location')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'Code must be unique per company.'),
    ]
