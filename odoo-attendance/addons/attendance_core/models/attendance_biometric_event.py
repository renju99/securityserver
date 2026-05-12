# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class AttendanceBiometricEvent(models.Model):
    _name = 'attendance.biometric.event'
    _description = 'Biometric punch event'
    _order = 'id desc'

    name = fields.Char(string='Reference', default='New', copy=False)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    device_id = fields.Many2one(
        'attendance.biometric.device',
        string='Device',
        required=True,
        ondelete='cascade',
    )
    staff_key = fields.Char(
        string='Staff badge',
        required=True,
        help='Matched against hr.employee.barcode in the same company.',
    )
    direction = fields.Selection(
        selection=[('in', 'Check in'), ('out', 'Check out')],
        string='Direction',
        required=True,
    )
    event_time = fields.Datetime(required=True, default=fields.Datetime.now)
    payload_json = fields.Json(string='Raw payload')
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('done', 'Processed'),
            ('error', 'Error'),
        ],
        string='Status',
        default='pending',
        index=True,
    )
    last_error = fields.Text(readonly=True)
    process_attempts = fields.Integer(string='Attempts', default=0, readonly=True)
    next_retry_at = fields.Datetime(default=fields.Datetime.now)
    attendance_id = fields.Many2one(
        'hr.attendance',
        string='Attendance',
        readonly=True,
        ondelete='set null',
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.name in (False, 'New'):
                rec.name = 'BIO/%s' % rec.id
        return records

    def _parse_event_time(self, payload):
        raw = (payload or {}).get('event_time')
        if not raw:
            return fields.Datetime.now()
        try:
            return OdooDatetime.to_datetime(raw)
        except Exception:
            return fields.Datetime.now()

    def _process_one(self):
        self.ensure_one()
        self = self.sudo()
        if self.state == 'done':
            return True
        Attendance = self.env['hr.attendance']
        Employee = self.env['hr.employee']
        device = self.device_id
        company = device.company_id
        emp = Employee.search(
            [('barcode', '=', self.staff_key), ('company_id', '=', company.id)],
            limit=1,
        )
        if not emp:
            self.write({
                'state': 'error',
                'last_error': 'No employee with this badge (barcode) in the device company.',
                'process_attempts': self.process_attempts + 1,
            })
            return False
        work_location = device.work_location_id
        if self.direction == 'in':
            open_att = Attendance.search(
                [('employee_id', '=', emp.id), ('check_out', '=', False)],
                order='check_in desc',
                limit=1,
            )
            if open_att:
                self.write({
                    'state': 'error',
                    'last_error': 'Employee already has an open attendance.',
                    'process_attempts': self.process_attempts + 1,
                })
                return False
            vals = {
                'employee_id': emp.id,
                'check_in': self.event_time,
                'in_mode': 'kiosk',
                'check_work_location_id': work_location.id if work_location else False,
            }
            payload = self.payload_json or {}
            if payload.get('latitude') is not None and payload.get('longitude') is not None:
                vals['in_latitude'] = float(payload['latitude'])
                vals['in_longitude'] = float(payload['longitude'])
            att = Attendance.create(vals)
            self.write({
                'state': 'done',
                'attendance_id': att.id,
                'last_error': False,
                'process_attempts': self.process_attempts + 1,
            })
            return True
        open_att = Attendance.search(
            [('employee_id', '=', emp.id), ('check_out', '=', False)],
            order='check_in desc',
            limit=1,
        )
        if not open_att:
            self.write({
                'state': 'error',
                'last_error': 'No open attendance to close.',
                'process_attempts': self.process_attempts + 1,
            })
            return False
        vals = {'check_out': self.event_time, 'out_mode': 'kiosk'}
        payload = self.payload_json or {}
        if payload.get('latitude') is not None and payload.get('longitude') is not None:
            vals['out_latitude'] = float(payload['latitude'])
            vals['out_longitude'] = float(payload['longitude'])
        open_att.write(vals)
        self.write({
            'state': 'done',
            'attendance_id': open_att.id,
            'last_error': False,
            'process_attempts': self.process_attempts + 1,
        })
        return True

    @api.model
    def cron_process_pending_events(self):
        horizon = fields.Datetime.now()
        domain = [
            ('state', '=', 'pending'),
            ('next_retry_at', '<=', horizon),
            ('process_attempts', '<', 20),
        ]
        for event in self.search(domain, limit=200, order='id asc'):
            try:
                event._process_one()
            except Exception as exc:
                event.write({
                    'last_error': str(exc),
                    'process_attempts': event.process_attempts + 1,
                    'next_retry_at': fields.Datetime.now() + timedelta(minutes=5),
                })
                if event.process_attempts >= 20:
                    event.write({'state': 'error'})
