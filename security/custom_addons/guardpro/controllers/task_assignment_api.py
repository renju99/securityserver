# -*- coding: utf-8 -*-
"""Task Assignment Notification API.

These endpoints power the guard's mobile "you have a new task" alert. They
mirror the emergency-broadcast and patrol-reminder endpoints so the WebView
poller (``mobile_task_assignment.js``) and the Android TWA native fallback
poller (``TwaLauncherActivity`` / ``LocationService``) can both raise an
OS-level notification the moment a supervisor assigns a task.
"""

from odoo import http, fields
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class TaskAssignmentAPIController(http.Controller):
    """HTTP endpoints used by the mobile app + TWA to surface new task
    assignments to guards."""

    # ------------------------------------------------------------------
    # Pending
    # ------------------------------------------------------------------
    @http.route(
        '/guardpro/api/tasks/pending',
        type='http',
        auth='user',
        methods=['GET'],
        csrf=False,
        website=True,
    )
    def get_pending_task_assignments(self, **kwargs):
        """Return task assignments the current guard has not yet
        acknowledged on their phone."""
        try:
            user = request.env.user

            # Use sudo() so guards can read their own pending tasks even if
            # they're not in a supervisor record rule domain.
            guard = request.env['guard.profile'].sudo().search(
                [('user_id', '=', user.id)], limit=1
            )
            if not guard:
                return request.make_json_response({
                    'success': True,
                    'tasks': [],
                })

            tasks = request.env['guard.task'].sudo().search([
                ('assigned_to', '=', guard.id),
                ('state', '=', 'assigned'),
                ('mobile_assignment_ack', '=', False),
            ], order='priority desc, due_date asc, id desc', limit=20)

            # Priority code -> human label used in the UI banner.
            priority_label = {
                '0': 'Low',
                '1': 'Normal',
                '2': 'High',
                '3': 'Urgent',
            }

            rows = []
            for task in tasks:
                # Strip HTML from description for phone display.
                description = task.description or ''
                if description:
                    import re
                    description = re.sub(r'<[^<]+?>', '', description).strip()

                rows.append({
                    'id': task.id,
                    # ack_id is the task id itself; separate key keeps the
                    # wire format identical to emergency / patrol endpoints.
                    'ack_id': task.id,
                    'name': task.name or '',
                    'description': description[:600],
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
                {
                    'success': True,
                    'tasks': rows,
                },
                headers=[('Cache-Control', 'no-store, no-cache, must-revalidate')],
            )
        except Exception as e:
            _logger.exception('task_assignment pending failed: %s', e)
            return request.make_json_response(
                {'success': False, 'error': str(e)},
                status=500,
            )

    # ------------------------------------------------------------------
    # Acknowledge
    # ------------------------------------------------------------------
    @http.route(
        '/guardpro/api/tasks/acknowledge_assignment',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def acknowledge_task_assignment(self, **kwargs):
        """Mark a task assignment notification as seen by the guard."""
        try:
            user = request.env.user

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
                [('user_id', '=', user.id)], limit=1
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
            _logger.exception('task_assignment ack failed: %s', e)
            return request.make_json_response(
                {'success': False, 'error': str(e)},
                status=500,
            )
