# -*- coding: utf-8 -*-
"""Push-to-Talk API Controllers for GuardLink."""

from odoo import http
from odoo.http import request
from odoo import fields as odoo_fields
import logging
import base64
import json
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class PushToTalkAPI(http.Controller):
    """API endpoints for push-to-talk (walkie-talkie) functionality."""

    def _ptt_current_guard(self):
        return request.env['guard.profile'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)

    def _ptt_user_can_use_channel(self, channel):
        if not channel or not channel.exists():
            return False
        return channel.sudo().is_accessible_by_user(request.env.user)

    def _ptt_channels_for_user(self):
        return request.env['push.to.talk.channel'].get_available_channels_for_user(
            request.env.user
        )

    def _ptt_sender_vals(self):
        guard = self._ptt_current_guard()
        vals = {'sender_user_id': request.env.user.id}
        if guard:
            vals['sender_guard_id'] = guard.id
        return vals

    def _ptt_is_mine(self, message):
        uid = request.env.user.id
        if message.sender_user_id and message.sender_user_id.id == uid:
            return True
        guard = self._ptt_current_guard()
        return bool(guard and message.sender_guard_id and message.sender_guard_id.id == guard.id)

    def _ptt_sender_name(self, message):
        return message.sudo().sender_display_name()

    def _ptt_can_talk(self):
        return request.env['push.to.talk.channel']._user_is_ptt_operator(request.env.user)

    def _ptt_guard_can_use_channel(self, guard, channel):
        """Legacy helper — prefer ``_ptt_user_can_use_channel``."""
        if guard and guard.user_id:
            return channel.sudo().is_accessible_by_user(guard.user_id)
        if not guard or not channel or not channel.exists():
            return False
        return channel.sudo().is_accessible_by_guard(guard)

    def _ptt_json(self, payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[
                ('Content-Type', 'application/json'),
                ('Access-Control-Allow-Origin', '*'),
            ],
            status=status,
        )

    @http.route('/guardpro/api/push-to-talk/test', type='json', auth='user', methods=['POST'], csrf=False)
    def test_endpoint(self, **kwargs):
        """Test endpoint to verify routing works."""
        _logger.info('[Push-to-Talk API] Test endpoint called by user: %s', request.env.user.name)
        return {'success': True, 'message': 'Push-to-talk API is working', 'user': request.env.user.name}
    
    @http.route('/guardpro/api/push_to_talk/channels', type='http', auth='user', methods=['POST', 'GET', 'OPTIONS'], csrf=False)
    def get_channels_http_alt(self, **kwargs):
        """Alternative HTTP endpoint with underscores."""
        return self.get_channels_http(**kwargs)
    
    @http.route('/guardpro/api/push-to-talk/channels', type='http', auth='user', methods=['POST', 'GET', 'OPTIONS'], csrf=False)
    def get_channels_http(self, **kwargs):
        """HTTP endpoint for channels (primary method for browser compatibility)."""
        # Handle CORS preflight OPTIONS request
        if request.httprequest.method == 'OPTIONS':
            _logger.info('[Push-to-Talk API HTTP] OPTIONS preflight request')
            return request.make_response(
                '',
                headers=[
                    ('Content-Type', 'application/json'),
                    ('Access-Control-Allow-Origin', '*'),
                    ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                    ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
                    ('Access-Control-Max-Age', '3600')
                ],
                status=200
            )
        
        try:
            _logger.info('[Push-to-Talk API HTTP] get_channels called by user: %s (ID: %s), method: %s, path: %s', 
                        request.env.user.name, request.env.user.id, request.httprequest.method, request.httprequest.path)
            
            guard = self._ptt_current_guard()
            can_talk = self._ptt_can_talk()
            channels = self._ptt_channels_for_user()
            _logger.info(
                '[Push-to-Talk API HTTP] Found %d channels for user %s (guard=%s, can_talk=%s)',
                len(channels), request.env.user.name, bool(guard), can_talk,
            )
            
            channels_list = []
            for channel in channels:
                # Use sudo() to read channel properties (bypasses record rules)
                channel_sudo = channel.sudo()
                channels_list.append({
                    'id': channel.id,
                    'name': channel_sudo.name,
                    'code': channel_sudo.code,
                    'description': channel_sudo.description or '',
                    'channel_type': channel_sudo.channel_type,
                    'site_id': channel_sudo.site_id.id if channel_sudo.site_id else None,
                    'all_sites_access': bool(channel_sudo.all_sites_access),
                    'is_member': True,
                    'is_public': channel_sudo.is_public,
                    'active_members_count': channel_sudo.active_members_count,
                    'last_message_time': channel_sudo.last_message_time.isoformat() if channel_sudo.last_message_time else None,
                    'max_duration_seconds': channel_sudo.max_duration_seconds
                })
            
            response_data = {
                'success': True,
                'channels': channels_list,
                'total': len(channels_list),
                'has_guard_profile': bool(guard),
                'can_talk': can_talk,
                'warning': None,
            }
            
            if not can_talk:
                response_data['warning'] = (
                    'Your login is not enabled for push-to-talk. Contact your administrator.'
                )
            elif len(channels_list) == 0:
                response_data['warning'] = (
                    'No push-to-talk channel is configured for your site(s). '
                    'Please contact your supervisor to link a channel to your site.'
                )
            
            _logger.info('[Push-to-Talk API HTTP] Returning %d channels', len(channels_list))
            
            return request.make_response(
                json.dumps(response_data),
                headers=[
                    ('Content-Type', 'application/json'),
                    ('Access-Control-Allow-Origin', '*')
                ]
            )
        except Exception as e:
            _logger.error('[Push-to-Talk API HTTP] Error: %s', str(e), exc_info=True)
            return request.make_response(
                json.dumps({'success': False, 'error': str(e)}),
                headers=[
                    ('Content-Type', 'application/json'),
                    ('Access-Control-Allow-Origin', '*')
                ],
                status=500
            )

    @http.route(
        '/guardpro/api/push-to-talk/pending',
        type='http',
        auth='user',
        methods=['GET'],
        csrf=False,
        website=True,
    )
    def get_pending_ptt_http(self, **kwargs):
        """Newest unplayed incoming PTT so late devices jump to live, not a backlog."""
        try:
            empty = json.dumps({'success': True, 'message': None})
            headers = [('Content-Type', 'application/json')]
            if not self._ptt_can_talk():
                return request.make_response(empty, headers=headers)
            channels = self._ptt_channels_for_user()
            if not channels:
                return request.make_response(empty, headers=headers)
            uid = request.env.user.id
            recent = request.env['push.to.talk.message'].sudo().search([
                ('channel_id', 'in', channels.ids),
                ('is_streaming', '=', False),
                ('audio_data', '!=', False),
                ('file_size', '>', 4000),
            ], order='id desc', limit=15)
            pending = False
            for msg in recent:
                if self._ptt_is_mine(msg):
                    continue
                if uid not in msg.played_by_ids.ids:
                    pending = msg
                    break
            if not pending:
                return request.make_response(empty, headers=headers)
            payload = {
                'success': True,
                'message': {
                    'id': pending.id,
                    'channel_id': pending.channel_id.id,
                    'channel_name': pending.channel_id.name or '',
                    'sender_name': self._ptt_sender_name(pending),
                    'audio_url': pending.get_audio_url(),
                },
            }
            return request.make_response(json.dumps(payload), headers=headers)
        except Exception as e:
            _logger.exception('[Push-to-Talk] pending poll failed')
            return request.make_response(
                json.dumps({'success': False, 'error': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500,
            )

    @http.route(
        '/guardpro/api/push-to-talk/message/<int:message_id>/mark-played-http',
        type='http',
        auth='user',
        methods=['POST', 'GET'],
        csrf=False,
        website=True,
    )
    def mark_message_played_http(self, message_id, **kwargs):
        """HTTP mark-played for the native Android player (session cookie)."""
        result = self.mark_message_played(message_id)
        return request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route('/guardpro/api/push-to-talk/channel/<int:channel_id>/join', type='http', auth='user', methods=['POST', 'GET'], csrf=False)
    def join_channel(self, channel_id, **kwargs):
        """Connect to a channel (guards must be assigned to the channel).
        
        Note: Guards are already assigned to channels by supervisors based on projects.
        This endpoint just confirms the guard has access and is ready to communicate.
        """
        try:
            if not self._ptt_can_talk():
                return request.make_response(
                    json.dumps({
                        'success': False,
                        'error': 'Your login is not enabled for push-to-talk.',
                    }),
                    headers=[
                        ('Content-Type', 'application/json'),
                        ('Access-Control-Allow-Origin', '*')
                    ],
                    status=403
                )

            channel = request.env['push.to.talk.channel'].browse(channel_id)
            if not channel.exists():
                return request.make_response(
                    json.dumps({'success': False, 'error': 'Channel not found'}),
                    headers=[
                        ('Content-Type', 'application/json'),
                        ('Access-Control-Allow-Origin', '*')
                    ],
                    status=404
                )

            if not channel.active:
                return request.make_response(
                    json.dumps({'success': False, 'error': 'Channel is not active'}),
                    headers=[
                        ('Content-Type', 'application/json'),
                        ('Access-Control-Allow-Origin', '*')
                    ],
                    status=400
                )

            if not self._ptt_user_can_use_channel(channel):
                return request.make_response(
                    json.dumps({
                        'success': False, 
                        'error': 'Access denied. You are not assigned to this channel for your site(s), or the channel has no site set. Please contact your supervisor.'
                    }),
                    headers=[
                        ('Content-Type', 'application/json'),
                        ('Access-Control-Allow-Origin', '*')
                    ],
                    status=403
                )

            _logger.info('[Push-to-Talk API] User %s connected to channel %s (ID: %s)',
                        request.env.user.name, channel.sudo().name, channel.id)

            return request.make_response(
                json.dumps({
                    'success': True,
                    'channel_id': channel.id,
                    'message': f'Connected to channel: {channel.sudo().name}'
                }),
                headers=[
                    ('Content-Type', 'application/json'),
                    ('Access-Control-Allow-Origin', '*')
                ]
            )

        except Exception as e:
            _logger.error('[Push-to-Talk API] Error joining channel: %s', str(e), exc_info=True)
            return request.make_response(
                json.dumps({'success': False, 'error': str(e)}),
                headers=[
                    ('Content-Type', 'application/json'),
                    ('Access-Control-Allow-Origin', '*')
                ],
                status=500
            )

    @http.route('/guardpro/api/push-to-talk/channel/<int:channel_id>/leave', type='json', auth='user', methods=['POST'], csrf=False)
    def leave_channel(self, channel_id, **kwargs):
        """Leave a channel."""
        try:
            if not self._ptt_can_talk():
                return {'success': False, 'error': 'Access denied'}

            channel = request.env['push.to.talk.channel'].browse(channel_id)
            if not channel.exists():
                return {'success': False, 'error': 'Channel not found'}

            guard = self._ptt_current_guard()
            if guard:
                channel.action_leave_channel(guard.id)

            return {
                'success': True,
                'message': f'Left channel: {channel.name}'
            }

        except Exception as e:
            _logger.error('Error leaving channel: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/push-to-talk/channel/<int:channel_id>/messages', type='json', auth='user', methods=['POST'], csrf=False)
    def get_messages(self, channel_id, limit=50, offset=0, since_id=0, **kwargs):
        """Get recent messages from a channel.
        
        Args:
            channel_id: Channel ID
            limit: Maximum number of messages to return
            offset: Offset for pagination
            since_id: Only return messages with ID greater than this (for walkie-talkie real-time updates)
        """
        try:
            if not self._ptt_can_talk():
                return {'success': False, 'error': 'Access denied'}

            channel = request.env['push.to.talk.channel'].browse(channel_id)
            if not channel.exists():
                return {'success': False, 'error': 'Channel not found'}

            if not self._ptt_user_can_use_channel(channel):
                return {'success': False, 'error': 'Access denied. You cannot read messages on this channel for your site(s).'}

            # Get messages (use voice_message_ids to avoid conflict with mail.thread's message_ids)
            # Use sudo() to read messages - guards should be able to read messages from channels they're members of
            # If since_id is provided and > 0, filter to only get newer messages
            # If since_id is 0 or not provided, get recent messages for initialization
            domain = [('channel_id', '=', channel_id)]
            if since_id and since_id > 0:
                domain.append(('id', '>', since_id))
                # When since_id is provided, get messages newer than that ID, ordered by ID ascending (oldest first)
                messages = request.env['push.to.talk.message'].sudo().search(
                    domain,
                    order='id asc',  # Order by ID for walkie-talkie (oldest first)
                    limit=limit
                )
            else:
                # When since_id is 0 or not provided, get the most recent messages ordered by ID descending
                # This is used for initialization to get the latest message ID
                messages = request.env['push.to.talk.message'].sudo().search(
                    domain,
                    order='id desc',  # Order by ID descending to get most recent first
                    limit=limit,
                    offset=offset
                )

            messages_list = []
            for msg in messages:
                ready = bool(msg.audio_data) and not msg.is_streaming
                messages_list.append({
                    'id': msg.id,
                    'sender_guard_id': msg.sender_guard_id.id if msg.sender_guard_id else None,
                    'sender_user_id': msg.sender_user_id.id if msg.sender_user_id else None,
                    'sender_name': self._ptt_sender_name(msg),
                    'duration_seconds': msg.duration_seconds,
                    'is_urgent': msg.is_urgent,
                    'created_at': msg.created_at.isoformat(),
                    # Never advertise /audio until the burst is finalized —
                    # otherwise clients 404-loop during PTT hold (TETRA simplex).
                    'audio_url': msg.get_audio_url() if ready else None,
                    'has_audio': ready,
                    'is_streaming': bool(msg.is_streaming),
                    'location_latitude': msg.location_latitude,
                    'location_longitude': msg.location_longitude,
                    'is_sent_by_me': self._ptt_is_mine(msg),
                    'is_played': request.env.user.id in msg.sudo().played_by_ids.ids
                })

            return {
                'success': True,
                'messages': messages_list,
                'total': len(channel.voice_message_ids),
                'has_more': (offset + limit) < len(channel.voice_message_ids)
            }

        except Exception as e:
            _logger.error('Error fetching messages: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/push-to-talk/send', type='json', auth='user', methods=['POST'], csrf=False)
    def send_voice_message(self, channel_id, audio_data, duration_seconds, 
                          is_urgent=False, latitude=None, longitude=None, **kwargs):
        """Send a voice message to a channel."""
        try:
            if not self._ptt_can_talk():
                return {'success': False, 'error': 'Access denied'}

            channel = request.env['push.to.talk.channel'].browse(channel_id)
            if not channel.exists():
                return {'success': False, 'error': 'Channel not found'}

            if not channel.active:
                return {'success': False, 'error': 'Channel is not active'}

            if not self._ptt_user_can_use_channel(channel):
                return {
                    'success': False, 
                    'error': 'Access denied. You cannot send to this channel for your site(s).'
                }

            # Validate duration
            if duration_seconds < 0.1 or duration_seconds > channel.max_duration_seconds:
                return {
                    'success': False,
                    'error': f'Duration must be between 0.1 and {channel.max_duration_seconds} seconds'
                }

            # Decode audio data (expecting base64)
            try:
                if isinstance(audio_data, str):
                    # Remove data URL prefix if present
                    if audio_data.startswith('data:audio'):
                        audio_data = audio_data.split(',')[1]
                    audio_binary = base64.b64decode(audio_data)
                else:
                    audio_binary = audio_data
            except Exception as e:
                _logger.error('Error decoding audio data: %s', str(e))
                return {'success': False, 'error': 'Invalid audio data format'}

            # Calculate file size
            file_size = len(audio_binary)

            # Create message using sudo() to allow guards to create messages on their assigned channels
            # This is safe because we've already verified the guard has access to the channel
            Message = request.env['push.to.talk.message']
            message = Message.sudo().create({
                'channel_id': channel.id,
                **self._ptt_sender_vals(),
                'audio_data': base64.b64encode(audio_binary),
                'audio_filename': f'voice_message_{datetime.now().strftime("%Y%m%d_%H%M%S")}.ogg',
                'duration_seconds': duration_seconds,
                'file_size': file_size,
                'is_urgent': is_urgent,
                'location_latitude': latitude,
                'location_longitude': longitude,
                'created_at': datetime.now()
            })

            # Broadcast notification to channel members
            message.action_broadcast_notification()

            _logger.info('[Push-to-Talk] Voice message sent by user %s on channel %s (ID: %s)',
                        request.env.user.name, channel.name, channel.id)

            return {
                'success': True,
                'message_id': message.id,
                'created_at': message.created_at.isoformat(),
                'audio_url': message.get_audio_url()
            }

        except Exception as e:
            _logger.error('Error sending voice message: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/push-to-talk/stream/start', type='json', auth='user', methods=['POST'], csrf=False)
    def stream_start(self, channel_id, stream_id, is_urgent=False, latitude=None, longitude=None, **kwargs):
        """Start a new voice message stream session."""
        try:
            if not self._ptt_can_talk():
                return {'success': False, 'error': 'Access denied'}

            channel = request.env['push.to.talk.channel'].browse(channel_id)
            if not channel.exists() or not channel.active:
                return {'success': False, 'error': 'Channel not found or inactive'}

            if not self._ptt_user_can_use_channel(channel):
                return {'success': False, 'error': 'Access denied'}

            # Reuse an in-progress stream from this user so one press cannot
            # create two messages (that is the double-play on other phones).
            Message = request.env['push.to.talk.message']
            existing = Message.sudo().search([
                ('channel_id', '=', channel.id),
                ('is_streaming', '=', True),
                ('sender_user_id', '=', request.env.user.id),
            ], order='id desc', limit=1)
            if existing:
                if stream_id:
                    existing.sudo().write({'stream_id': stream_id})
                return {
                    'success': True,
                    'message_id': existing.id,
                    'reused': True,
                }

            message = Message.sudo().create({
                'channel_id': channel.id,
                **self._ptt_sender_vals(),
                'duration_seconds': 0.0,
                'file_size': 0,
                'is_urgent': is_urgent,
                'location_latitude': latitude,
                'location_longitude': longitude,
                'is_streaming': True,
                'stream_id': stream_id,
                'created_at': datetime.now()
            })

            message.broadcast_tx_state('start')
            return {
                'success': True,
                'message_id': message.id
            }
        except Exception as e:
            _logger.error('Error starting stream: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/push-to-talk/stream/chunk', type='json', auth='user', methods=['POST'], csrf=False)
    def stream_chunk(self, message_id, audio_chunk, is_last=False, duration_seconds=0, replace=False, **kwargs):
        """Receive a chunk of audio for an active stream."""
        try:
            message = request.env['push.to.talk.message'].sudo().browse(message_id)
            if not message.exists() or not message.is_streaming:
                return {'success': False, 'error': 'Message not found or not in streaming mode'}

            if not self._ptt_is_mine(message):
                return {'success': False, 'error': 'Access denied'}

            if audio_chunk:
                # Last blob is the complete recording — replace, do not concat clusters.
                message.append_audio_chunk(audio_chunk, replace=bool(replace or is_last))

            if is_last:
                has_audio = message.finalize_stream_audio()
                duration = max(float(duration_seconds or 0), 0.1)
                if not has_audio or (message.file_size or 0) < 4000:
                    message.unlink()
                    return {'success': True, 'cancelled': True}

                message.write({
                    'is_streaming': False,
                    'duration_seconds': duration,
                })
                message.broadcast_tx_state('end')
                message.action_broadcast_notification()

            return {'success': True}
        except Exception as e:
            _logger.error('Error in stream chunk: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/push-to-talk/message/<int:message_id>/audio', type='http', auth='user', methods=['GET'], csrf=False, website=True)
    def get_audio_file(self, message_id, **kwargs):
        """Serve audio file for a message with proper content-type headers."""
        try:
            # Use sudo() to read message (guards need to read messages from their channels)
            message = request.env['push.to.talk.message'].sudo().browse(message_id)
            if not message.exists():
                _logger.warning('[Push-to-Talk] Audio request for non-existent message: %s', message_id)
                return request.make_response('Message not found', status=404)
            
            if not self._ptt_user_can_use_channel(message.channel_id):
                _logger.warning(
                    '[Push-to-Talk] User %s denied audio access to channel %s',
                    request.env.user.name, message.channel_id.id)
                return request.make_response('Access denied', status=403)
            
            # Get audio data — 202 while the sender still holds PTT so clients
            # wait instead of treating it as a missing file (404 retry storm).
            if message.is_streaming or not message.audio_data:
                _logger.debug(
                    '[Push-to-Talk] Message %s audio not ready (streaming=%s)',
                    message_id, message.is_streaming,
                )
                return request.make_response(
                    'Audio not ready',
                    headers=[('Retry-After', '1')],
                    status=202,
                )
            
            # Binary field values may be raw audio bytes or a base64 payload depending
            # on how the record was created (streaming vs direct upload).
            payload = message.audio_data
            if isinstance(payload, str):
                payload = payload.encode()
            payload = bytes(payload or b'')
            if payload[:4] == b'\x1a\x45\xdf\xa3' or payload[:4] in (b'OggS', b'RIFF', b'fLaC', b'ID3\x03'):
                audio_binary = payload
            else:
                audio_binary = base64.b64decode(payload)

            content_type = 'audio/ogg'
            if audio_binary[:4] == b'\x1a\x45\xdf\xa3':
                content_type = 'audio/webm'
            elif audio_binary[:4] == b'OggS':
                content_type = 'audio/ogg'
            elif message.audio_filename:
                if message.audio_filename.endswith('.webm'):
                    content_type = 'audio/webm'
                elif message.audio_filename.endswith('.mp3'):
                    content_type = 'audio/mpeg'
                elif message.audio_filename.endswith('.wav'):
                    content_type = 'audio/wav'
                elif message.audio_filename.endswith('.ogg') or message.audio_filename.endswith('.opus'):
                    content_type = 'audio/ogg'
            
            # Set headers for streaming
            headers = [
                ('Content-Type', content_type),
                ('Content-Length', str(len(audio_binary))),
                ('Accept-Ranges', 'bytes'),
                ('Cache-Control', 'public, max-age=3600'),
            ]
            
            # Handle range requests for seeking
            range_header = request.httprequest.headers.get('Range')
            if range_header:
                # Parse range header (e.g., "bytes=0-1023")
                try:
                    range_match = range_header.replace('bytes=', '').split('-')
                    start = int(range_match[0]) if range_match[0] else 0
                    end = int(range_match[1]) if range_match[1] and range_match[1] else len(audio_binary) - 1
                    
                    if start < 0 or end >= len(audio_binary) or start > end:
                        return request.make_response('Range Not Satisfiable', status=416)
                    
                    audio_chunk = audio_binary[start:end+1]
                    content_length = len(audio_chunk)
                    
                    headers.append(('Content-Range', f'bytes {start}-{end}/{len(audio_binary)}'))
                    headers.append(('Content-Length', str(content_length)))
                    
                    _logger.debug('[Push-to-Talk] Serving audio range %s-%s for message %s', start, end, message_id)
                    return request.make_response(audio_chunk, headers=headers, status=206)  # 206 Partial Content
                except (ValueError, IndexError):
                    # Invalid range, serve full file
                    pass
            
            _logger.debug('[Push-to-Talk] Serving full audio file for message %s, size: %s bytes', message_id, len(audio_binary))
            return request.make_response(audio_binary, headers=headers)
            
        except Exception as e:
            _logger.error('[Push-to-Talk] Error serving audio file for message %s: %s', message_id, str(e))
            return request.make_response('Internal server error', status=500)

    @http.route('/guardpro/api/push-to-talk/message/<int:message_id>/mark-played', type='json', auth='user', methods=['POST'], csrf=False)
    def mark_message_played(self, message_id, **kwargs):
        """Mark a message as played."""
        try:
            message = request.env['push.to.talk.message'].sudo().browse(message_id)
            if not message.exists():
                return {'success': False, 'error': 'Message not found'}

            if not self._ptt_user_can_use_channel(message.channel_id):
                return {'success': False, 'error': 'Access denied'}

            message.mark_as_played(request.env.user.id)

            return {'success': True}

        except Exception as e:
            _logger.error('Error marking message as played: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/push-to-talk/active-guards', type='json', auth='user', methods=['POST'], csrf=False)
    def get_active_guards(self, channel_id=None, **kwargs):
        """Get guards who have been active on channels recently."""
        try:
            if not self._ptt_can_talk():
                return {'success': False, 'error': 'Access denied'}

            # Get talkers who sent messages in the last 5 minutes
            cutoff = odoo_fields.Datetime.now() - timedelta(minutes=5)

            domain = [('created_at', '>=', cutoff)]
            if channel_id:
                channel = request.env['push.to.talk.channel'].browse(channel_id)
                if not channel.exists() or not self._ptt_user_can_use_channel(channel):
                    return {'success': False, 'error': 'Access denied'}
                domain.append(('channel_id', '=', channel_id))

            messages = request.env['push.to.talk.message'].sudo().search(domain)
            seen = set()
            talkers = []
            for msg in messages:
                name = self._ptt_sender_name(msg)
                key = (msg.sender_user_id.id if msg.sender_user_id else 0,
                       msg.sender_guard_id.id if msg.sender_guard_id else 0, name)
                if key in seen:
                    continue
                seen.add(key)
                talkers.append({
                    'id': msg.sender_guard_id.id if msg.sender_guard_id else None,
                    'name': name,
                    'user_id': msg.sender_user_id.id if msg.sender_user_id else None,
                })
            
            return {
                'success': True,
                'guards': talkers,
                'total': len(talkers)
            }

        except Exception as e:
            _logger.error('Error fetching active guards: %s', str(e))
            return {'success': False, 'error': str(e)}
