# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, http
from odoo.http import Response, request

_logger = logging.getLogger(__name__)


class AttendanceBiometricController(http.Controller):
    @http.route(
        '/attendance_core/biometric/punch',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def biometric_punch(self, **_kwargs):
        try:
            raw_body = request.httprequest.get_data(cache=False, as_text=True) or '{}'
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            return self._json_response({'ok': False, 'error': 'invalid_json'}, 400)
        device_key = (request.httprequest.headers.get('X-Device-Key') or '').strip()
        if not device_key:
            return self._json_response({'ok': False, 'error': 'missing_device_key'}, 401)
        Device = request.env['attendance.biometric.device'].sudo()
        device = Device.search([('device_key', '=', device_key), ('active', '=', True)], limit=1)
        if not device:
            return self._json_response({'ok': False, 'error': 'unknown_device'}, 401)
        device.write({'last_seen_ip': request.httprequest.remote_addr})
        staff_id = (data.get('staff_id') or data.get('staff_key') or '').strip()
        if not staff_id:
            return self._json_response({'ok': False, 'error': 'missing_staff_id'}, 400)
        direction = (data.get('direction') or 'in').lower()
        if direction not in ('in', 'out'):
            return self._json_response({'ok': False, 'error': 'invalid_direction'}, 400)
        event_time = fields.Datetime.now()
        if data.get('event_time'):
            try:
                event_time = fields.Datetime.to_datetime(data['event_time'])
            except (TypeError, ValueError, OverflowError):
                event_time = fields.Datetime.now()
        Event = request.env['attendance.biometric.event'].sudo().with_company(device.company_id)
        event = Event.create({
            'company_id': device.company_id.id,
            'device_id': device.id,
            'staff_key': staff_id,
            'direction': direction,
            'event_time': event_time,
            'payload_json': data,
        })
        ok = event._process_one()
        event.invalidate_recordset()
        if not ok and event.state == 'error':
            return self._json_response(
                {'ok': False, 'error': event.last_error or 'process_failed', 'event_id': event.id},
                422,
            )
        return self._json_response(
            {
                'ok': True,
                'event_id': event.id,
                'attendance_id': event.attendance_id.id if event.attendance_id else None,
            },
            200,
        )

    def _json_response(self, payload, status):
        body = json.dumps(payload)
        return Response(body, status=status, content_type='application/json; charset=utf-8')
