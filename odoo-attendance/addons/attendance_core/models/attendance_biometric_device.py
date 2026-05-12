# -*- coding: utf-8 -*-
from odoo import fields, models


class AttendanceBiometricDevice(models.Model):
    _name = 'attendance.biometric.device'
    _description = 'Biometric attendance device'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    device_key = fields.Char(
        required=True,
        copy=False,
        groups='hr.group_hr_manager',
        help='Sent as HTTP header X-Device-Key. Keep secret.',
    )
    work_location_id = fields.Many2one(
        'hr.work.location',
        string='Work location',
    )
    last_seen_ip = fields.Char(string='Last caller IP', readonly=True)
    notes = fields.Text()

    _sql_constraints = [
        ('device_key_company_uniq', 'unique(device_key, company_id)', 'Device key must be unique per company.'),
    ]
