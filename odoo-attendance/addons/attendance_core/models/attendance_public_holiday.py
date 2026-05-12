# -*- coding: utf-8 -*-
from odoo import fields, models


class AttendancePublicHoliday(models.Model):
    _name = 'attendance.public.holiday'
    _description = 'Public holiday (attendance)'
    _order = 'date_start desc, name'

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    work_location_id = fields.Many2one('hr.work.location', string='Work location')
    date_start = fields.Date(required=True)
    date_end = fields.Date(string='End date', help='Leave empty for single day.')
    active = fields.Boolean(default=True)
