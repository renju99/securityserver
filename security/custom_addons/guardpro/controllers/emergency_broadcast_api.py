# -*- coding: utf-8 -*-
"""Emergency Broadcast API Controller."""

from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class EmergencyBroadcastAPIController(http.Controller):
    """API endpoints for emergency broadcast functionality."""

    @http.route('/guardpro/api/emergency_broadcasts/pending', 
                type='http', auth='user', methods=['GET'], csrf=False)
    def get_pending_broadcasts(self, **kwargs):
        """Get all pending (unacknowledged) emergency broadcasts for the current user."""
        try:
            user = request.env.user
            
            # Get pending acknowledgments for this user
            acknowledgments = request.env['emergency.broadcast.acknowledgment'].sudo().search([
                ('user_id', '=', user.id),
                ('is_acknowledged', '=', False)
            ])

            broadcasts = []
            for ack in acknowledgments:
                broadcasts.append({
                    'id': ack.broadcast_id.id,
                    'ack_id': ack.id,
                    'title': ack.broadcast_id.title,
                    'message': ack.broadcast_id.message,
                    'priority': ack.broadcast_id.priority,
                    'sent_date': ack.broadcast_id.sent_date.isoformat() if ack.broadcast_id.sent_date else None,
                })

            return request.make_json_response({
                'success': True,
                'broadcasts': broadcasts
            })

        except Exception as e:
            _logger.error('Failed to get pending broadcasts: %s', str(e))
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)

    @http.route('/guardpro/api/emergency_broadcasts/acknowledge', 
                type='http', auth='user', methods=['POST'], csrf=False)
    def acknowledge_broadcast(self, **kwargs):
        """Acknowledge an emergency broadcast."""
        try:
            user = request.env.user
            
            # Get acknowledgment_id from POST data (JSON body)
            data = json.loads(request.httprequest.data.decode('utf-8'))
            acknowledgment_id = data.get('acknowledgment_id')
            
            if not acknowledgment_id:
                return request.make_json_response({
                    'success': False,
                    'error': 'acknowledgment_id is required'
                }, status=400)
            
            # Find the acknowledgment
            acknowledgment = request.env['emergency.broadcast.acknowledgment'].sudo().search([
                ('id', '=', int(acknowledgment_id)),
                ('user_id', '=', user.id)
            ], limit=1)

            if not acknowledgment:
                return request.make_json_response({
                    'success': False,
                    'error': 'Acknowledgment not found or not authorized'
                }, status=404)

            # Acknowledge it
            acknowledgment.action_acknowledge()

            return request.make_json_response({
                'success': True,
                'message': 'Broadcast acknowledged successfully'
            })

        except ValueError as e:
            _logger.error('Invalid acknowledgment_id: %s', str(e))
            return request.make_json_response({
                'success': False,
                'error': 'Invalid acknowledgment_id'
            }, status=400)
        except Exception as e:
            _logger.error('Failed to acknowledge broadcast: %s', str(e))
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)

