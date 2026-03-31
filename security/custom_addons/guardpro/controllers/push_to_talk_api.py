# -*- coding: utf-8 -*-
"""Push-to-Talk API Controllers for GuardPro."""

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

    def _ptt_guard_can_use_channel(self, guard, channel):
        """Membership + site scope (see ``push.to.talk.channel.is_accessible_by_guard``)."""
        if not guard or not channel or not channel.exists():
            return False
        return channel.sudo().is_accessible_by_guard(guard)

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
            
            # Use sudo() to check if guard profile exists (bypasses record rules for existence check)
            # This is safe because we're only checking existence, not reading sensitive data
            guard = request.env['guard.profile'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            
            Channel = request.env['push.to.talk.channel']
            
            # Guards can only access channels they're assigned to (based on projects)
            if not guard:
                _logger.warning('[Push-to-Talk API HTTP] No guard profile for user: %s, cannot access channels', request.env.user.name)
                channels = Channel.env['push.to.talk.channel']  # Empty recordset
                _logger.info('[Push-to-Talk API HTTP] No channels available (no guard profile)')
            else:
                # Get only channels where guard is assigned as a member
                channels = Channel.get_available_channels_for_guard(guard.id)
                _logger.info('[Push-to-Talk API HTTP] Found %d assigned channels for guard %s (ID: %s)', len(channels), guard.name, guard.id)
                
                # Log total channels in system for debugging
                total_channels = Channel.sudo().search_count([('active', '=', True)])
                assigned_channels_count = Channel.sudo().search_count([
                    ('active', '=', True),
                    ('member_ids', 'in', [guard.id])
                ])
                _logger.debug('[Push-to-Talk API HTTP] Total active channels: %d, Assigned to guard: %d', total_channels, assigned_channels_count)
            
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
                    'is_member': True,  # All channels returned are ones guard is assigned to
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
                'warning': 'No guard profile found. You need a guard profile to access push-to-talk channels.' if not guard else None
            }
            
            if guard and len(channels_list) == 0:
                response_data['warning'] = 'No channels assigned. Please contact your supervisor to be assigned to a channel for your project.'
            
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


    @http.route('/guardpro/api/push-to-talk/channel/<int:channel_id>/join', type='http', auth='user', methods=['POST', 'GET'], csrf=False)
    def join_channel(self, channel_id, **kwargs):
        """Connect to a channel (guards must be assigned to the channel).
        
        Note: Guards are already assigned to channels by supervisors based on projects.
        This endpoint just confirms the guard has access and is ready to communicate.
        """
        try:
            # Use sudo() to check if guard profile exists (bypasses record rules for existence check)
            guard = request.env['guard.profile'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return request.make_response(
                    json.dumps({
                        'success': False, 
                        'error': 'Guard profile not found. You need a guard profile to access channels and send messages.'
                    }),
                    headers=[
                        ('Content-Type', 'application/json'),
                        ('Access-Control-Allow-Origin', '*')
                    ],
                    status=404
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

            # Member + site scope (multi-site)
            if not self._ptt_guard_can_use_channel(guard, channel):
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

            # Guard is already assigned, just confirm connection
            # No need to call action_join_channel since guard is already a member
            _logger.info('[Push-to-Talk API] Guard %s (ID: %s) connected to channel %s (ID: %s)', 
                        guard.name, guard.id, channel.sudo().name, channel.id)

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
            # Use sudo() to check if guard profile exists (bypasses record rules for existence check)
            guard = request.env['guard.profile'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            channel = request.env['push.to.talk.channel'].browse(channel_id)
            if not channel.exists():
                return {'success': False, 'error': 'Channel not found'}

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
            # Use sudo() to check if guard profile exists (bypasses record rules for existence check)
            guard = request.env['guard.profile'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            channel = request.env['push.to.talk.channel'].browse(channel_id)
            if not channel.exists():
                return {'success': False, 'error': 'Channel not found'}

            if not self._ptt_guard_can_use_channel(guard, channel):
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
                # Use sudo() to read sender_guard_id.name (guards might not have read access to other guards)
                sender_name = msg.sudo().sender_guard_id.name if msg.sender_guard_id else 'Unknown'
                messages_list.append({
                    'id': msg.id,
                    'sender_guard_id': msg.sender_guard_id.id,
                    'sender_name': sender_name,
                    'duration_seconds': msg.duration_seconds,
                    'is_urgent': msg.is_urgent,
                    'created_at': msg.created_at.isoformat(),
                    'audio_url': msg.get_audio_url(),
                    'location_latitude': msg.location_latitude,
                    'location_longitude': msg.location_longitude,
                    'is_sent_by_me': msg.sender_guard_id.id == guard.id,
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
            # Use sudo() to check if guard profile exists (bypasses record rules for existence check)
            guard = request.env['guard.profile'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            channel = request.env['push.to.talk.channel'].browse(channel_id)
            if not channel.exists():
                return {'success': False, 'error': 'Channel not found'}

            if not channel.active:
                return {'success': False, 'error': 'Channel is not active'}

            if not self._ptt_guard_can_use_channel(guard, channel):
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
                'sender_guard_id': guard.id,
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

            _logger.info('[Push-to-Talk] Voice message sent by guard %s (ID: %s) on channel %s (ID: %s)', 
                        guard.name, guard.id, channel.name, channel.id)

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
            guard = request.env['guard.profile'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            channel = request.env['push.to.talk.channel'].browse(channel_id)
            if not channel.exists() or not channel.active:
                return {'success': False, 'error': 'Channel not found or inactive'}

            if not self._ptt_guard_can_use_channel(guard, channel):
                return {'success': False, 'error': 'Access denied'}

            # Create initial message record in streaming mode
            Message = request.env['push.to.talk.message']
            message = Message.sudo().create({
                'channel_id': channel.id,
                'sender_guard_id': guard.id,
                'duration_seconds': 0.0,
                'file_size': 0,
                'is_urgent': is_urgent,
                'location_latitude': latitude,
                'location_longitude': longitude,
                'is_streaming': True,
                'stream_id': stream_id,
                'created_at': datetime.now()
            })

            return {
                'success': True,
                'message_id': message.id
            }
        except Exception as e:
            _logger.error('Error starting stream: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/push-to-talk/stream/chunk', type='json', auth='user', methods=['POST'], csrf=False)
    def stream_chunk(self, message_id, audio_chunk, is_last=False, duration_seconds=0, **kwargs):
        """Receive a chunk of audio for an active stream."""
        try:
            message = request.env['push.to.talk.message'].sudo().browse(message_id)
            if not message.exists() or not message.is_streaming:
                return {'success': False, 'error': 'Message not found or not in streaming mode'}

            guard = request.env['guard.profile'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            if not guard or message.sender_guard_id.id != guard.id:
                return {'success': False, 'error': 'Access denied'}

            # Append chunk and broadcast
            message.append_audio_chunk(audio_chunk)

            if is_last:
                # Assemble temp stream data into final audio payload once.
                message.finalize_stream_audio()
                message.write({
                    'is_streaming': False,
                    'duration_seconds': duration_seconds
                })
                # Final broadcast of the full message notification so it appears in history
                message.action_broadcast_notification()

            return {'success': True}
        except Exception as e:
            _logger.error('Error in stream chunk: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/push-to-talk/message/<int:message_id>/audio', type='http', auth='user', methods=['GET'], csrf=False)
    def get_audio_file(self, message_id, **kwargs):
        """Serve audio file for a message with proper content-type headers."""
        try:
            # Use sudo() to read message (guards need to read messages from their channels)
            message = request.env['push.to.talk.message'].sudo().browse(message_id)
            if not message.exists():
                _logger.warning('[Push-to-Talk] Audio request for non-existent message: %s', message_id)
                return request.make_response('Message not found', status=404)
            
            # Check if user has access to this channel
            guard = request.env['guard.profile'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            
            if not guard:
                return request.make_response('Guard profile not found', status=403)
            
            if not self._ptt_guard_can_use_channel(guard, message.channel_id):
                _logger.warning(
                    '[Push-to-Talk] User %s (guard %s) denied audio access to channel %s',
                    request.env.user.name, guard.id, message.channel_id.id)
                return request.make_response('Access denied', status=403)
            
            # Get audio data
            if not message.audio_data:
                _logger.warning('[Push-to-Talk] Message %s has no audio data', message_id)
                return request.make_response('No audio data', status=404)
            
            # Decode base64 audio data
            audio_binary = base64.b64decode(message.audio_data)
            
            # Determine content type based on filename
            content_type = 'audio/ogg'  # Default to OGG
            if message.audio_filename:
                if message.audio_filename.endswith('.mp3'):
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

            guard = request.env['guard.profile'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            if not guard or not self._ptt_guard_can_use_channel(guard, message.channel_id):
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
            guard = request.env['guard.profile'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # Get guards who sent messages in the last 5 minutes
            cutoff = odoo_fields.Datetime.now() - timedelta(minutes=5)

            domain = [('created_at', '>=', cutoff)]
            if channel_id:
                channel = request.env['push.to.talk.channel'].browse(channel_id)
                if not channel.exists() or not self._ptt_guard_can_use_channel(guard, channel):
                    return {'success': False, 'error': 'Access denied'}
                domain.append(('channel_id', '=', channel_id))

            messages = request.env['push.to.talk.message'].search(domain)
            active_guards = messages.mapped('sender_guard_id')
            
            guards_list = []
            for guard in active_guards:
                guards_list.append({
                    'id': guard.id,
                    'name': guard.name,
                    'user_id': guard.user_id.id if guard.user_id else None
                })
            
            return {
                'success': True,
                'guards': guards_list,
                'total': len(guards_list)
            }

        except Exception as e:
            _logger.error('Error fetching active guards: %s', str(e))
            return {'success': False, 'error': str(e)}
