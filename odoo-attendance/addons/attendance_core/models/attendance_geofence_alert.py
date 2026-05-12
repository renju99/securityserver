# -*- coding: utf-8 -*-
from odoo import fields, models


class AttendanceGeofenceAlert(models.Model):
    _name = 'attendance.geofence.alert'
    _description = 'Geofence attendance alert'
    _order = 'id desc'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    work_location_id = fields.Many2one('hr.work.location', string='Work location', ondelete='set null')
    attendance_id = fields.Many2one('hr.attendance', string='Attendance', ondelete='set null')
    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))
    distance_meters = fields.Float(string='Distance (m)', digits=(16, 2))
    message = fields.Text()
    state = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('reviewed', 'Reviewed'),
            ('false_positive', 'False positive'),
        ],
        string='Status',
        default='open',
        index=True,
    )
