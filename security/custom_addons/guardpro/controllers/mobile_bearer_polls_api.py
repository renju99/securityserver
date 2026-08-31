# -*- coding: utf-8 -*-
"""Bearer-token poll endpoints (read-only) for Flutter/Android.

IMPORTANT COMPATIBILITY NOTE:
These routes are added alongside the existing cookie/session endpoints.
We do NOT change or remove the current Play Store API routes.
"""

import json
import logging
import re

from odoo import http
from odoo.http import request

from ..common.mobile_bearer_auth import current_bearer_user

_logger = logging.getLogger(__name__)


class GuardLinkMobileBearerPollsAPIController(http.Controller):
    """Bearer-token versions of the mobile 'pending' poll endpoints."""

    def _unauthorized(self):
        return request.make_json_response(
            {'success': False, 'error': 'Unauthorized'},
            status=401,
        )

    @http.route(
        '/guardpro/api/mobile_bearer/emergency_broadcasts/pending',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
        website=True,
    )
    def emergency_pending(self, **kwargs):
        user = current_bearer_user()
        if not user:
            return self._unauthorized()

        acknowledgments = request.env['emergency.broadcast.acknowledgment'].sudo().search(
            [
                ('user_id', '=', user.id),
                ('is_acknowledged', '=', False),
                ('broadcast_id.state', '=', 'sent'),
            ],
            order='create_date desc',
            limit=5,
        )

        broadcasts = []
        for ack in acknowledgments:
            if not ack.broadcast_id or ack.broadcast_id.state != 'sent':
                continue
            broadcasts.append({
                'id': ack.broadcast_id.id,
                'ack_id': ack.id,
                'title': ack.broadcast_id.title,
                'message': ack.broadcast_id.message,
                'priority': ack.broadcast_id.priority,
                'sent_date': ack.broadcast_id.sent_date.isoformat() if ack.broadcast_id.sent_date else None,
            })

        return request.make_json_response(
            {'success': True, 'broadcasts': broadcasts},
            headers=[('Cache-Control', 'no-store, no-cache, must-revalidate')],
        )

    @http.route(
        '/guardpro/api/mobile_bearer/tasks/pending',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
        website=True,
    )
    def tasks_pending(self, **kwargs):
        user = current_bearer_user()
        if not user:
            return self._unauthorized()

        guard = request.env['guard.profile'].sudo().search(
            [('user_id', '=', user.id)],
            limit=1,
        )
        if not guard:
            return request.make_json_response({'success': True, 'tasks': []})

        tasks = request.env['guard.task'].sudo().search(
            [
                ('assigned_to', '=', guard.id),
                ('state', '=', 'assigned'),
                ('mobile_assignment_ack', '=', False),
            ],
            order='priority desc, due_date asc, id desc',
            limit=20,
        )

        priority_label = {
            '0': 'Low',
            '1': 'Normal',
            '2': 'High',
            '3': 'Urgent',
        }

        rows = []
        for task in tasks:
            description = task.description or ''
            if description:
                # Strip HTML from description for phone display.
                description = re.sub(r'<[^<]+?>', '', description).strip()

            rows.append({
                'id': task.id,
                'ack_id': task.id,
                'name': task.name or '',
                'description': (description or '')[:600],
                'task_type': task.task_type or 'other',
                'priority': task.priority or '1',
                'priority_label': priority_label.get(task.priority or '1', 'Normal'),
                'site_name': task.site_id.name if task.site_id else '',
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'assigned_by': task.created_by.name if task.created_by else '',
                'notified_on': task.mobile_assignment_notified_on.isoformat()
                if task.mobile_assignment_notified_on else None,
            })

        return request.make_json_response(
            {'success': True, 'tasks': rows},
            headers=[('Cache-Control', 'no-store, no-cache, must-revalidate')],
        )

    @http.route(
        '/guardpro/api/mobile_bearer/mobile_outbox/pending',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
        website=True,
    )
    def outbox_pending(self, **kwargs):
        user = current_bearer_user()
        if not user:
            return self._unauthorized()

        Outbox = request.env['guardpro.mobile.outbox'].sudo()
        rows = Outbox.search(
            [
                ('user_id', '=', user.id),
                ('acked', '=', False),
                ('kind', 'not in', [
                    'shift_assigned', 'shift_changed',
                    'shift_cancelled', 'shift_swap_decision',
                ]),
            ],
            order='priority desc, create_date asc, id asc',
            limit=100,
        )

        priority_weight = {'urgent': 3, 'high': 2, 'normal': 1, 'low': 0}
        items = []
        for row in rows:
            items.append({
                'id': row.id,
                'kind': row.kind,
                'title': row.title or '',
                'body': row.body or '',
                'priority': row.priority or 'normal',
                'priority_weight': priority_weight.get(row.priority, 1),
                'res_model': row.res_model or '',
                'res_id': row.res_id or 0,
                'deep_link': row.deep_link or '',
                'created_on': row.create_date.isoformat() if row.create_date else None,
            })

        return request.make_json_response(
            {'success': True, 'notifications': items},
            headers=[('Cache-Control', 'no-store, no-cache, must-revalidate')],
        )

