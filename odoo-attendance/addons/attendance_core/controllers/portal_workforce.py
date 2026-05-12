# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PortalBerkeleyWorkforce(http.Controller):
    """Employee self-service: check-in/out + offline punch replay (portal user → employee)."""

    def _portal_employee(self):
        return request.env.user.sudo().employee_id

    def _punch(self, emp, direction, check_in_dt=None, check_out_dt=None):
        if not emp:
            return {'ok': False, 'error': 'no_employee'}
        Attendance = request.env['hr.attendance'].sudo().with_context(berkeley_workforce_disable_bus=True)
        direction = (direction or 'in').lower()
        if direction == 'in':
            open_att = Attendance.search(
                [('employee_id', '=', emp.id), ('check_out', '=', False)],
                limit=1,
            )
            if open_att:
                return {'ok': False, 'error': 'already_checked_in'}
            cin = check_in_dt or fields.Datetime.now()
            Attendance.create(
                {
                    'employee_id': emp.id,
                    'check_in': cin,
                    'in_mode': 'systray',
                }
            )
            return {'ok': True, 'status': 'checked_in'}
        open_att = Attendance.search(
            [('employee_id', '=', emp.id), ('check_out', '=', False)],
            order='check_in desc',
            limit=1,
        )
        if not open_att:
            return {'ok': False, 'error': 'nothing_to_close'}
        cout = check_out_dt or fields.Datetime.now()
        open_att.write({'check_out': cout, 'out_mode': 'systray'})
        return {'ok': True, 'status': 'checked_out'}

    @http.route(['/my/berkeley_workforce'], type='http', auth='user', website=False)
    def portal_workforce_page(self, **kwargs):
        emp = self._portal_employee()
        if not emp:
            return request.redirect('/my')
        Attendance = request.env['hr.attendance'].sudo()
        open_att = Attendance.search(
            [('employee_id', '=', emp.id), ('check_out', '=', False)],
            order='check_in desc',
            limit=1,
        )
        return request.render(
            'attendance_core.portal_berkeley_workforce_page',
            {
                'employee': emp,
                'open_attendance': open_att,
                'csrf_token': request.csrf_token(),
            },
        )

    @http.route(['/my/berkeley_workforce/punch'], type='http', auth='user', methods=['POST'], website=False, csrf=True)
    def portal_workforce_punch(self, **kwargs):
        emp = self._portal_employee()
        if not emp:
            return request.redirect('/my')
        post = request.httprequest.form.to_dict() if request.httprequest.form else {}
        direction = post.get('direction', 'in')
        res = self._punch(emp, direction)
        accept = request.httprequest.headers.get('Accept', '')
        if 'application/json' in accept:
            return request.make_json_response(res)
        return request.redirect('/my/berkeley_workforce')

    @http.route(['/my/berkeley_workforce/sync'], type='http', auth='user', methods=['POST'], website=False, csrf=True)
    def portal_workforce_sync(self, **kwargs):
        emp = self._portal_employee()
        if not emp:
            return request.make_json_response({'ok': False, 'error': 'no_employee'}, status=403)
        post = request.httprequest.form.to_dict() if request.httprequest.form else {}
        raw = post.get('punches_json') or '[]'
        try:
            punches = json.loads(raw)
        except json.JSONDecodeError:
            return request.make_json_response({'ok': False, 'error': 'invalid_json'}, status=400)
        if not isinstance(punches, list):
            return request.make_json_response({'ok': False, 'error': 'invalid_payload'}, status=400)
        done = 0
        for item in punches:
            direction = (item.get('direction') or 'in').lower()
            ts = item.get('time')
            dt = None
            if ts:
                try:
                    dt = fields.Datetime.to_datetime(ts)
                except (TypeError, ValueError, OverflowError):
                    dt = None
            if direction == 'in':
                r = self._punch(emp, 'in', check_in_dt=dt)
            else:
                r = self._punch(emp, 'out', check_out_dt=dt)
            if r.get('ok'):
                done += 1
        return request.make_json_response({'ok': True, 'processed': done})

    @http.route(['/my/berkeley_workforce/location'], type='http', auth='user', methods=['POST'], website=False, csrf=True)
    def portal_workforce_location(self, **kwargs):
        emp = self._portal_employee()
        if not emp:
            return request.make_json_response({'ok': False, 'error': 'no_employee'}, status=403)
        post = request.httprequest.form.to_dict() if request.httprequest.form else {}
        raw = post.get('logs_json') or '[]'
        try:
            logs = json.loads(raw)
        except json.JSONDecodeError:
            return request.make_json_response({'ok': False, 'error': 'invalid_json'}, status=400)
        if not isinstance(logs, list):
            return request.make_json_response({'ok': False, 'error': 'invalid_payload'}, status=400)
        Log = request.env['attendance.location.log'].sudo()
        company = emp.company_id
        created = 0
        for row in logs:
            try:
                ev = row.get('time')
                ev_dt = fields.Datetime.to_datetime(ev) if ev else fields.Datetime.now()
                Log.create(
                    {
                        'employee_id': emp.id,
                        'company_id': company.id,
                        'event_time': ev_dt,
                        'latitude': float(row['lat']),
                        'longitude': float(row['lng']),
                        'speed': float(row['speed']) if row.get('speed') is not None else 0.0,
                        'raw_json': row,
                    }
                )
                created += 1
            except (KeyError, TypeError, ValueError):
                continue
        return request.make_json_response({'ok': True, 'created': created})
