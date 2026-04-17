# -*- coding: utf-8 -*-
"""Messaging API Controllers for GuardPro."""

from odoo import http
from odoo.http import request
import logging
import json
from datetime import datetime

_logger = logging.getLogger(__name__)


class GuardProMessagingAPI(http.Controller):
    """API endpoints for guard messaging system."""

    @http.route('/guardpro/api/messages/conversations', type='json', auth='user')
    def get_conversations(self, limit=20, **kwargs):
        """Get list of conversations for current user."""
        try:
            # Get current user's guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # Get conversations
            Conversation = request.env['guard.conversation']
            conversations = Conversation.search([
                ('guard_id', '=', guard.id),
                ('is_active', '=', True)
            ], order='last_message_time desc', limit=limit)

            conversations_list = []
            for conv in conversations:
                conversations_list.append({
                    'id': conv.id,
                    'name': conv.name,
                    'supervisor_name': conv.supervisor_id.name,
                    'supervisor_id': conv.supervisor_id.id,
                    'last_message': conv.last_message,
                    'last_message_time': conv.last_message_time.isoformat() if conv.last_message_time else None,
                    'unread_count': conv.unread_count_guard,
                    'is_active': conv.is_active
                })

            return {
                'success': True,
                'conversations': conversations_list,
                'total': len(conversations_list)
            }

        except Exception as e:
            _logger.error('Error fetching conversations: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/messages/conversation/<int:conversation_id>', type='json', auth='user')
    def get_conversation_messages(self, conversation_id, limit=50, offset=0, **kwargs):
        """Get messages in a conversation."""
        try:
            Conversation = request.env['guard.conversation']
            conversation = Conversation.browse(conversation_id)

            if not conversation.exists():
                return {'success': False, 'error': 'Conversation not found'}

            # Verify user has access to this conversation
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if guard and conversation.guard_id.id != guard.id:
                return {'success': False, 'error': 'Access denied'}

            # Get messages
            messages = conversation.message_ids.sorted('created_at', reverse=True)[offset:offset+limit]

            messages_list = []
            for msg in messages:
                messages_list.append({
                    'id': msg.id,
                    'sender_id': msg.sender_id.id,
                    'sender_name': msg.sender_id.name,
                    'receiver_id': msg.receiver_id.id,
                    'receiver_name': msg.receiver_id.name,
                    'message_type': msg.message_type,
                    'content': msg.content,
                    'media_url': msg.media_url,
                    'media_duration': msg.media_duration,
                    'is_read': msg.is_read,
                    'read_at': msg.read_at.isoformat() if msg.read_at else None,
                    'is_urgent': msg.is_urgent,
                    'created_at': msg.created_at.isoformat(),
                    'is_sent_by_me': msg.sender_id.id == request.env.user.id
                })

            # Mark unread messages as read
            unread_messages = messages.filtered(
                lambda m: not m.is_read and m.receiver_id.id == request.env.user.id
            )
            for msg in unread_messages:
                msg.mark_as_read()

            return {
                'success': True,
                'messages': messages_list,
                'total': len(conversation.message_ids),
                'has_more': (offset + limit) < len(conversation.message_ids)
            }

        except Exception as e:
            _logger.error('Error fetching conversation messages: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/messages/send', type='json', auth='user')
    def send_message(self, receiver_id, content, message_type='text', media_url=None,
                     media_duration=None, is_urgent=False, conversation_id=None, **kwargs):
        """Send a message to supervisor."""
        try:
            # Get current user
            sender = request.env.user

            # Get receiver
            receiver = request.env['res.users'].browse(receiver_id)
            if not receiver.exists():
                return {'success': False, 'error': 'Receiver not found'}

            # Get or create conversation
            if conversation_id:
                conversation = request.env['guard.conversation'].browse(conversation_id)
                if not conversation.exists():
                    return {'success': False, 'error': 'Conversation not found'}
            else:
                # Get guard profile
                guard = request.env['guard.profile'].search([
                    ('user_id', '=', sender.id)
                ], limit=1)

                if not guard:
                    return {'success': False, 'error': 'Guard profile not found'}

                # Find or create conversation
                Conversation = request.env['guard.conversation']
                conversation = Conversation.search([
                    ('guard_id', '=', guard.id),
                    ('supervisor_id', '=', receiver_id)
                ], limit=1)

                if not conversation:
                    conversation = Conversation.create({
                        'guard_id': guard.id,
                        'supervisor_id': receiver_id,
                        'is_active': True
                    })

            # Create message
            Message = request.env['guard.message']
            message = Message.create({
                'conversation_id': conversation.id,
                'sender_id': sender.id,
                'receiver_id': receiver_id,
                'message_type': message_type,
                'content': content,
                'media_url': media_url,
                'media_duration': media_duration,
                'is_urgent': is_urgent,
                'created_at': datetime.now()
            })

            # Create notification for receiver
            message.create_notification()

            return {
                'success': True,
                'message_id': message.id,
                'conversation_id': conversation.id,
                'created_at': message.created_at.isoformat()
            }

        except Exception as e:
            _logger.error('Error sending message: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/messages/mark-read', type='json', auth='user')
    def mark_messages_read(self, message_ids, **kwargs):
        """Mark multiple messages as read."""
        try:
            Message = request.env['guard.message']
            messages = Message.browse(message_ids)

            if not messages.exists():
                return {'success': False, 'error': 'Messages not found'}

            # Mark each message as read
            marked_count = 0
            for msg in messages:
                if msg.mark_as_read():
                    marked_count += 1

            return {
                'success': True,
                'marked_count': marked_count,
                'total_messages': len(messages)
            }

        except Exception as e:
            _logger.error('Error marking messages as read: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/status/update', type='json', auth='user')
    def update_status(self, status, notes=None, auto_end_duration=None,
                     latitude=None, longitude=None, **kwargs):
        """Update guard status."""
        try:
            # Get guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # End any previous active status
            StatusUpdate = request.env['guard.status.update']
            active_status = StatusUpdate.get_current_status(guard.id)
            if active_status:
                active_status.end_status()

            # Create new status
            new_status = StatusUpdate.create({
                'guard_id': guard.id,
                'status': status,
                'notes': notes,
                'auto_end_duration': auto_end_duration,
                'latitude': latitude,
                'longitude': longitude,
                'started_at': datetime.now()
            })

            # Send notification to supervisor if needed
            if status in ['need_assistance', 'emergency']:
                # TODO: Send urgent notification

                pass

            return {
                'success': True,
                'status_id': new_status.id,
                'status': status,
                'started_at': new_status.started_at.isoformat()
            }

        except Exception as e:
            _logger.error('Error updating status: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/status/end', type='json', auth='user')
    def end_current_status(self, **kwargs):
        """End current active status."""
        try:
            # Get guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # Get current active status
            StatusUpdate = request.env['guard.status.update']
            active_status = StatusUpdate.get_current_status(guard.id)

            if not active_status:
                return {'success': False, 'error': 'No active status found'}

            # End status
            active_status.end_status()

            return {
                'success': True,
                'status_id': active_status.id,
                'ended_at': active_status.ended_at.isoformat(),
                'duration_minutes': active_status.duration_minutes
            }

        except Exception as e:
            _logger.error('Error ending status: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/status/current', type='json', auth='user')
    def get_current_status(self, **kwargs):
        """Get current active status for the guard."""
        try:
            # Get guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # Get current status
            StatusUpdate = request.env['guard.status.update']
            active_status = StatusUpdate.get_current_status(guard.id)

            if not active_status:
                return {
                    'success': True,
                    'has_active_status': False,
                    'status': None
                }

            return {
                'success': True,
                'has_active_status': True,
                'status': {
                    'id': active_status.id,
                    'status': active_status.status,
                    'notes': active_status.notes,
                    'started_at': active_status.started_at.isoformat(),
                    'duration_minutes': active_status.duration_minutes,
                    'auto_end_duration': active_status.auto_end_duration
                }
            }

        except Exception as e:
            _logger.error('Error getting current status: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/messages/supervisors', type='json', auth='user')
    def get_available_supervisors(self, **kwargs):
        """Get list of available supervisors for messaging."""
        try:
            # Get users in supervisor groups
            supervisor_group = request.env.ref('guardpro.group_guardpro_supervisor')
            manager_group = request.env.ref('guardpro.group_guardpro_manager')

            supervisors = request.env['res.users'].search([
                '|',
                ('groups_id', 'in', [supervisor_group.id]),
                ('groups_id', 'in', [manager_group.id])
            ])

            supervisors_list = []
            for supervisor in supervisors:
                supervisors_list.append({
                    'id': supervisor.id,
                    'name': supervisor.name,
                    'email': supervisor.email,
                    'phone': supervisor.phone if hasattr(supervisor, 'phone') else None
                })

            return {
                'success': True,
                'supervisors': supervisors_list,
                'total': len(supervisors_list)
            }

        except Exception as e:
            _logger.error('Error getting supervisors: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    @http.route('/guardpro/api/messages/channels', type='json', auth='user')
    def get_channels(self, limit=20, **kwargs):
        """Get list of channels for current user."""
        try:
            # Get current user's guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            
            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}
            
            # Get channels where guard is a member or public channels, then apply site scope
            Channel = request.env['guard.message.channel']
            channels = Channel.search([
                '|',
                ('member_ids', 'in', [guard.id]),
                ('is_public', '=', True),
                ('is_archived', '=', False)
            ], order='last_message_time desc', limit=max(limit * 5, 50))
            channels = channels.filtered(lambda c: c.is_accessible_by_guard(guard))[:limit]
            
            channels_list = []
            for channel in channels:
                channels_list.append({
                    'id': channel.id,
                    'name': channel.name,
                    'channel_type': channel.channel_type,
                    'description': channel.description,
                    'site_id': channel.site_id.id if channel.site_id else None,
                    'all_sites_access': bool(channel.all_sites_access),
                    'message_count': channel.message_count,
                    'active_member_count': channel.active_member_count,
                    'last_message': channel.last_message,
                    'last_message_time': channel.last_message_time.isoformat() if channel.last_message_time else None,
                    'is_public': channel.is_public,
                    'is_member': guard.id in channel.member_ids.ids
                })
            
            return {
                'success': True,
                'channels': channels_list,
                'total': len(channels_list)
            }
            
        except Exception as e:
            _logger.error('Error fetching channels: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    @http.route('/guardpro/api/messages/channel/<int:channel_id>', type='json', auth='user')
    def get_channel_messages(self, channel_id, limit=50, offset=0, **kwargs):
        """Get messages in a channel."""
        try:
            Channel = request.env['guard.message.channel']
            channel = Channel.browse(channel_id)
            
            if not channel.exists():
                return {'success': False, 'error': 'Channel not found'}
            
            # Verify user has access
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            
            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}
            
            if not channel.is_accessible_by_guard(guard):
                return {'success': False, 'error': 'Access denied. You cannot access this channel for your site(s).'}
            
            # Get messages
            messages = channel.message_ids.sorted('created_at', reverse=True)[offset:offset+limit]
            
            messages_list = []
            for msg in messages:
                messages_list.append({
                    'id': msg.id,
                    'sender_id': msg.sender_id.id,
                    'sender_name': msg.sender_id.name,
                    'sender_guard_id': msg.sender_guard_id.id if msg.sender_guard_id else None,
                    'sender_guard_name': msg.sender_guard_id.name if msg.sender_guard_id else None,
                    'message_type': msg.message_type,
                    'content': msg.content,
                    'media_url': msg.media_url,
                    'media_duration': msg.media_duration,
                    'is_read': request.env.user.id in msg.read_by_ids.ids,
                    'is_urgent': msg.is_urgent,
                    'created_at': msg.created_at.isoformat(),
                    'is_sent_by_me': msg.sender_id.id == request.env.user.id
                })
            
            # Mark messages as read
            unread_messages = messages.filtered(
                lambda m: request.env.user.id not in m.read_by_ids.ids and m.sender_id.id != request.env.user.id
            )
            for msg in unread_messages:
                msg.mark_as_read()
            
            return {
                'success': True,
                'messages': messages_list,
                'total': len(channel.message_ids),
                'has_more': (offset + limit) < len(channel.message_ids)
            }
            
        except Exception as e:
            _logger.error('Error fetching channel messages: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    @http.route('/guardpro/api/messages/send-to-guard', type='json', auth='user')
    def send_message_to_guard(self, guard_id, content, message_type='text', is_urgent=False, **kwargs):
        """Send a message to another guard."""
        try:
            sender = request.env.user
            sender_guard = request.env['guard.profile'].search([
                ('user_id', '=', sender.id)
            ], limit=1)
            
            if not sender_guard:
                return {'success': False, 'error': 'Guard profile not found'}
            
            # Get receiver guard
            receiver_guard = request.env['guard.profile'].browse(guard_id)
            if not receiver_guard.exists() or not receiver_guard.user_id:
                return {'success': False, 'error': 'Receiver guard not found or has no user account'}

            # Multi-site: only message guards who share at least one assigned site
            su = sender
            ru = receiver_guard.user_id
            if su.site_ids and ru.site_ids:
                if not (set(su.site_ids.ids) & set(ru.site_ids.ids)):
                    return {
                        'success': False,
                        'error': 'You can only message guards assigned to the same site(s) as you.',
                    }
            
            # Get or create conversation
            Conversation = request.env['guard.conversation']
            conversation = Conversation.get_or_create_guard_conversation(
                sender_guard.id,
                receiver_guard.id
            )
            
            # Create message
            Message = request.env['guard.message']
            message = Message.create({
                'conversation_id': conversation.id,
                'sender_id': sender.id,
                'receiver_id': receiver_guard.user_id.id,
                'message_type': message_type,
                'content': content,
                'is_urgent': is_urgent,
                'media_url': kwargs.get('media_url'),
                'media_duration': kwargs.get('media_duration'),
                'created_at': datetime.now()
            })
            
            # Create notification
            message.create_notification()
            
            return {
                'success': True,
                'message_id': message.id,
                'conversation_id': conversation.id,
                'created_at': message.created_at.isoformat()
            }
            
        except Exception as e:
            _logger.error('Error sending message to guard: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    @http.route('/guardpro/api/messages/send-to-channel', type='json', auth='user')
    def send_message_to_channel(self, channel_id, content, message_type='text', is_urgent=False, **kwargs):
        """Send a message to a channel."""
        try:
            sender = request.env.user
            sender_guard = request.env['guard.profile'].search([
                ('user_id', '=', sender.id)
            ], limit=1)
            
            if not sender_guard:
                return {'success': False, 'error': 'Guard profile not found'}
            
            # Get channel
            channel = request.env['guard.message.channel'].browse(channel_id)
            if not channel.exists():
                return {'success': False, 'error': 'Channel not found'}
            
            if not channel.is_accessible_by_guard(sender_guard):
                return {'success': False, 'error': 'Access denied. You cannot post to this channel for your site(s).'}
            
            # Check if guards can post
            if not channel.allow_guards_to_post:
                # Check if user is supervisor
                if sender.id not in channel.supervisor_ids.ids:
                    return {'success': False, 'error': 'Only supervisors can post in this channel.'}
            
            # Create message
            Message = request.env['guard.message']
            message = Message.create({
                'channel_id': channel.id,
                'sender_id': sender.id,
                'message_type': message_type,
                'content': content,
                'is_urgent': is_urgent,
                'media_url': kwargs.get('media_url'),
                'media_duration': kwargs.get('media_duration'),
                'created_at': datetime.now()
            })
            
            # Create notification
            message.create_notification()
            
            return {
                'success': True,
                'message_id': message.id,
                'channel_id': channel.id,
                'created_at': message.created_at.isoformat()
            }
            
        except Exception as e:
            _logger.error('Error sending message to channel: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    @http.route('/guardpro/api/messages/broadcast', type='json', auth='user')
    def send_broadcast(self, content, broadcast_type='all_guards', recipient_ids=None,
                      site_id=None, shift_id=None, is_urgent=False, **kwargs):
        """Send broadcast message."""
        try:
            # Only supervisors/managers can send broadcasts
            supervisor_group = request.env.ref('guardpro.group_guardpro_supervisor', raise_if_not_found=False)
            manager_group = request.env.ref('guardpro.group_guardpro_manager', raise_if_not_found=False)
            
            if not supervisor_group and not manager_group:
                return {'success': False, 'error': 'Broadcast feature not available'}
            
            user_groups = request.env.user.groups_id.ids
            can_broadcast = (
                (supervisor_group and supervisor_group.id in user_groups) or
                (manager_group and manager_group.id in user_groups)
            )
            
            if not can_broadcast:
                return {'success': False, 'error': 'Only supervisors and managers can send broadcasts'}
            
            # Send broadcast
            Message = request.env['guard.message']
            message = Message.send_broadcast(
                content=content,
                broadcast_type=broadcast_type,
                recipient_ids=recipient_ids,
                site_id=site_id,
                shift_id=shift_id,
                is_urgent=is_urgent,
                sender_id=request.env.user.id,
                **kwargs
            )
            
            return {
                'success': True,
                'message_id': message.id,
                'recipient_count': len(message.broadcast_recipient_ids),
                'created_at': message.created_at.isoformat()
            }
            
        except Exception as e:
            _logger.error('Error sending broadcast: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    @http.route('/guardpro/api/messages/guards', type='json', auth='user')
    def get_available_guards(self, **kwargs):
        """Get list of available guards for messaging."""
        try:
            current_guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            
            user = request.env.user

            # Build domain using guard.profile/site_ids so guards can fetch peers
            # without tripping res.users record rules on other user records.
            domain = [('status', '=', 'active')]
            if current_guard:
                domain.append(('id', '!=', current_guard.id))
            if user.site_ids:
                domain.append(('site_ids', 'in', user.site_ids.ids))

            guards = request.env['guard.profile'].sudo().search(domain)
            
            guards_list = []
            for guard in guards:
                guards_list.append({
                    'id': guard.id,
                    'name': guard.name,
                    'badge_number': guard.badge_number,
                    'email': guard.email,
                    'phone': guard.phone,
                    'current_site': guard.current_site_id.name if guard.current_site_id else None
                })
            
            return {
                'success': True,
                'guards': guards_list,
                'total': len(guards_list)
            }
            
        except Exception as e:
            _logger.error('Error getting guards: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    @http.route('/guardpro/api/messages/templates', type='json', auth='user')
    def get_message_templates(self, template_type=None, **kwargs):
        """Get message templates."""
        try:
            domain = [('is_active', '=', True)]
            if template_type:
                domain.append(('template_type', '=', template_type))
            
            templates = request.env['guard.message.template'].search(domain)
            
            templates_list = []
            for template in templates:
                templates_list.append({
                    'id': template.id,
                    'name': template.name,
                    'template_type': template.template_type,
                    'subject': template.subject,
                    'content': template.content,
                    'description': template.description
                })
            
            return {
                'success': True,
                'templates': templates_list,
                'total': len(templates_list)
            }
            
        except Exception as e:
            _logger.error('Error getting templates: %s', str(e))
            return {'success': False, 'error': str(e)}

