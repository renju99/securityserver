# -*- coding: utf-8 -*-
"""Bearer-token versions of mobile action endpoints (write).

Compatibility rule:
Do not change existing cookie/session endpoints.
Only add /guardpro/api/mobile_bearer/... routes.
"""

import json
import logging

from odoo import http, fields
from odoo.http import request

from ..common.mobile_bearer_auth import current_bearer_user

_logger = logging.getLogger(__name__)


class GuardLinkMobileBearerActionsAPIController(http.Controller):
    def _unauthorized(self):
        return request.make_json_response(
            {'success': False, 'error': 'Unauthorized'},
            status=401,
        )

    @http.route(
        '/guardpro/api/mobile_bearer/emergency_broadcasts/acknowledge',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def emergency_acknowledge(self, **kwargs):
        user = current_bearer_user()
        if not user:
            return self._unauthorized()

        try:
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            data = {}

        acknowledgment_id = data.get('acknowledgment_id')
        if not acknowledgment_id:
            return request.make_json_response(
                {'success': False, 'error': 'acknowledgment_id is required'},
                status=400,
            )

        acknowledgment = request.env['emergency.broadcast.acknowledgment'].sudo().search([
            ('id', '=', int(acknowledgment_id)),
            ('user_id', '=', user.id),
        ], limit=1)

        if not acknowledgment:
            return request.make_json_response(
                {'success': False, 'error': 'Acknowledgment not found or not authorized'},
                status=404,
            )

        if not acknowledgment.is_acknowledged:
            acknowledgment.action_acknowledge()

        # If broadcast is no longer live, still treat as success.
        if acknowledgment.broadcast_id.state != 'sent':
            return request.make_json_response({
                'success': True,
                'message': 'Broadcast no longer active; acknowledgment cleared',
                'dismissed': True,
            })

        return request.make_json_response({
            'success': True,
            'message': 'Broadcast acknowledged successfully',
        })

    @http.route(
        '/guardpro/api/mobile_bearer/tasks/acknowledge_assignment',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def tasks_acknowledge_assignment(self, **kwargs):
        user = current_bearer_user()
        if not user:
            return self._unauthorized()

        try:
            try:
                data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            except (ValueError, UnicodeDecodeError):
                data = {}

            task_id = data.get('task_id') or data.get('ack_id')
            if not task_id:
                return request.make_json_response(
                    {'success': False, 'error': 'task_id is required'},
                    status=400,
                )
            try:
                task_id = int(task_id)
            except (TypeError, ValueError):
                return request.make_json_response(
                    {'success': False, 'error': 'task_id must be an integer'},
                    status=400,
                )

            guard = request.env['guard.profile'].sudo().search(
                [('user_id', '=', user.id)],
                limit=1,
            )
            if not guard:
                return request.make_json_response(
                    {'success': False, 'error': 'Guard profile not found'},
                    status=404,
                )

            task = request.env['guard.task'].sudo().search([
                ('id', '=', task_id),
                ('assigned_to', '=', guard.id),
            ], limit=1)
            if not task:
                return request.make_json_response(
                    {'success': False, 'error': 'Task not found or not assigned to you'},
                    status=404,
                )

            task.write({
                'mobile_assignment_ack': True,
                'mobile_assignment_acked_on': fields.Datetime.now(),
            })
            _logger.info(
                'Guard %s acknowledged task assignment notification %s',
                user.login, task.id,
            )
            return request.make_json_response({'success': True})
        except Exception as e:
            _logger.exception('task_assignment ack (bearer) failed: %s', e)
            return request.make_json_response(
                {'success': False, 'error': str(e)},
                status=500,
            )

    @http.route(
        '/guardpro/api/mobile_bearer/mobile_outbox/ack',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def outbox_ack(self, **kwargs):
        user = current_bearer_user()
        if not user:
            return self._unauthorized()

        try:
            try:
                data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            except (ValueError, UnicodeDecodeError):
                data = {}

            raw_id = data.get('id')
            raw_ids = data.get('ids') or ([] if raw_id is None else [raw_id])
            ids = []
            for v in raw_ids:
                try:
                    ids.append(int(v))
                except (TypeError, ValueError):
                    continue

            if not ids:
                return request.make_json_response(
                    {'success': False, 'error': 'id or ids required'},
                    status=400,
                )

            rows = request.env['guardpro.mobile.outbox'].sudo().search([
                ('id', 'in', ids),
                ('user_id', '=', user.id),
            ])
            rows.write({
                'acked': True,
                'acked_on': fields.Datetime.now(),
            })
            return request.make_json_response({
                'success': True,
                'acked_ids': rows.ids,
            })
        except Exception as e:
            _logger.exception('mobile_outbox ack (bearer) failed: %s', e)
            return request.make_json_response(
                {'success': False, 'error': str(e)},
                status=500,
            )

    @http.route(
        '/guardpro/api/mobile_bearer/mobile_outbox/ack_all',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def outbox_ack_all(self, **kwargs):
        user = current_bearer_user()
        if not user:
            return self._unauthorized()

        try:
            rows = request.env['guardpro.mobile.outbox'].sudo().search([
                ('user_id', '=', user.id),
                ('acked', '=', False),
            ])
            rows.write({
                'acked': True,
                'acked_on': fields.Datetime.now(),
            })
            return request.make_json_response({
                'success': True,
                'acked_ids': rows.ids,
            })
        except Exception as e:
            _logger.exception('mobile_outbox ack_all (bearer) failed: %s', e)
            return request.make_json_response(
                {'success': False, 'error': str(e)},
                status=500,
            )

