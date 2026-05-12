# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo.http import request, Response

from odoo.addons.attendance_core.lib.zkteco import (
    parse_zk_attlog_lines,
    zk_in_out_to_direction,
    zk_timestamp_to_datetime,
)

_logger = logging.getLogger(__name__)


def _plain_ok():
    return Response('OK', status=200, content_type='text/plain; charset=utf-8')


def _plain_err():
    return Response('ERROR', status=503, content_type='text/plain; charset=utf-8')


class ZktecoIclockController(http.Controller):
    """ZKTeco iClock push protocol (text ATTLOG)."""

    @http.route(
        ['/iclock/getrequest', '/iclock/Getrequest'],
        type='http',
        auth='public',
        csrf=False,
        methods=['GET'],
        save_session=False,
    )
    def iclock_getrequest(self, **_kwargs):
        return _plain_ok()

    @http.route(
        ['/iclock/ping', '/iclock/Ping'],
        type='http',
        auth='public',
        csrf=False,
        methods=['GET'],
        save_session=False,
    )
    def iclock_ping(self, **_kwargs):
        return _plain_ok()

    @http.route(
        ['/iclock/fdata', '/iclock/Fdata'],
        type='http',
        auth='public',
        csrf=False,
        methods=['GET', 'POST'],
        save_session=False,
    )
    def iclock_fdata(self, **_kwargs):
        return _plain_ok()

    @http.route(
        ['/iclock/cdata', '/iclock/Cdata'],
        type='http',
        auth='public',
        csrf=False,
        methods=['POST'],
        save_session=False,
    )
    def iclock_cdata(self, **kwargs):
        req = request.httprequest
        q = req.args or {}
        sn = (q.get('SN') or q.get('sn') or q.get('Sn') or '').strip()
        table_raw = (q.get('table') or q.get('Table') or '')
        table = str(table_raw).upper()
        body = req.get_data(cache=False, as_text=True) or ''

        if not sn:
            _logger.warning('[iclock] cdata without SN')
            return _plain_ok()

        if table in ('ATTPHOTO', 'ATT_PHOTO', 'BIOPHOTO'):
            return _plain_ok()

        if table not in ('ATTLOG', ''):
            return _plain_ok()

        Device = request.env['attendance.biometric.device'].sudo()
        device = Device.search([('device_key', '=', sn), ('active', '=', True)], limit=1)
        if not device:
            _logger.warning('[iclock] unknown device SN=%s (register device_key)', sn)
            return _plain_ok()

        prefix = request.env['ir.config_parameter'].sudo().get_param('attendance_core.zk_staff_prefix', '')
        Event = request.env['attendance.biometric.event'].sudo().with_company(device.company_id)
        transient = False
        ok_lines = 0
        for rec in parse_zk_attlog_lines(body):
            dt = zk_timestamp_to_datetime(rec['timestamp_str'])
            if not dt:
                continue
            staff_key = '%s%s' % (prefix or '', rec['user_id'])
            direction = zk_in_out_to_direction(rec['in_out_mode'])
            event = Event.create(
                {
                    'company_id': device.company_id.id,
                    'device_id': device.id,
                    'staff_key': staff_key,
                    'direction': direction,
                    'event_time': dt,
                    'payload_json': {
                        'source': 'zk_iclock',
                        'sn': sn,
                        'table': table or 'ATTLOG',
                        'in_out_mode': rec['in_out_mode'],
                        'verify_type': rec['verify_type'],
                        'line': rec['line'],
                    },
                }
            )
            ok = event._process_one()
            event.invalidate_recordset()
            if ok:
                ok_lines += 1
            elif event.state == 'error' and 'No employee' in (event.last_error or ''):
                transient = True
        if transient and ok_lines == 0:
            return _plain_err()
        return _plain_ok()
