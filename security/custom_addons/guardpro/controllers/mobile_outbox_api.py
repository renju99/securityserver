# -*- coding: utf-8 -*-
"""Mobile Outbox API.

Single endpoint pair that powers the unified TWA notification channel.
Every new feature that wants to ping the guard phone just writes to
``guardpro.mobile.outbox`` - no new endpoints, no new JS, no new
Android code required after this point.
"""

from odoo import http, fields
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class MobileOutboxController(http.Controller):
    """Pending / ack endpoints for the unified mobile outbox."""

    @http.route(
        '/guardpro/api/mobile_outbox/pending',
        type='http',
        auth='user',
        methods=['GET'],
        csrf=False,
        website=True,
    )
    def pending(self, **kwargs):
        """Return unacknowledged outbox rows for the current user."""
        try:
            user = request.env.user
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

            # Priority order for the JS to decide whether to raise a
            # high-importance Android channel.
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
                    'created_on': row.create_date.isoformat()
                    if row.create_date else None,
                })

            return request.make_json_response(
                {'success': True, 'notifications': items},
                headers=[
                    ('Cache-Control',
                     'no-store, no-cache, must-revalidate'),
                ],
            )
        except Exception as e:
            _logger.exception('mobile_outbox pending failed: %s', e)
            return request.make_json_response(
                {'success': False, 'error': str(e)},
                status=500,
            )

    @http.route(
        '/guardpro/api/mobile_outbox/ack',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def ack(self, **kwargs):
        """Acknowledge one or many outbox rows."""
        try:
            user = request.env.user
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
            _logger.exception('mobile_outbox ack failed: %s', e)
            return request.make_json_response(
                {'success': False, 'error': str(e)},
                status=500,
            )

    @http.route(
        '/guardpro/api/mobile_outbox/ack_all',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def ack_all(self, **kwargs):
        """Acknowledge every pending row for the current user."""
        try:
            user = request.env.user
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
            _logger.exception('mobile_outbox ack_all failed: %s', e)
            return request.make_json_response(
                {'success': False, 'error': str(e)},
                status=500,
            )
