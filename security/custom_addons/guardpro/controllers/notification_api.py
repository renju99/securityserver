# -*- coding: utf-8 -*-
"""Notification API Controllers."""

from odoo import http
from odoo.http import request
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class NotificationAPIController(http.Controller):
    """Notification API endpoints for GuardPro mobile app."""

    @http.route('/guardpro/api/notifications/list', type='json', auth='user', methods=['POST'], csrf=False)
    def list_notifications(self, limit=20, **kwargs):
        """
        Get list of notifications for current user.
        
        Args:
            limit: Maximum number of notifications to return (default: 20)
        
        Returns:
            dict: {
                'success': True,
                'notifications': [...],
                'unread_count': int
            }
        """
        try:
            user = request.env.user
            
            # Get guard profile for the current user
            # Use sudo() here as users need to access their own profile regardless of site assignment
            guard = request.env['guard.profile'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)
            
            if not guard:
                _logger.warning('No guard profile found for user: %s', user.name)
                return {
                    'result': {
                        'success': True,
                        'notifications': [],
                        'unread_count': 0
                    }
                }
            
            # Get notifications from mail.message
            # Look for messages related to the guard's profile and shifts
            notifications_data = []
            
            # Get recent messages for the guard
            cutoff_time = datetime.now() - timedelta(days=7)  # Last 7 days
            
            messages = request.env['mail.message'].search([
                ('model', '=', 'guard.profile'),
                ('res_id', '=', guard.id),
                ('create_date', '>=', cutoff_time),
                ('message_type', 'in', ['notification', 'comment'])
            ], order='create_date desc', limit=limit)
            
            for msg in messages:
                # Determine notification type based on message content
                notif_type = 'info'
                if 'emergency' in msg.body.lower() or 'alert' in msg.body.lower():
                    notif_type = 'danger'
                elif 'warning' in msg.body.lower():
                    notif_type = 'warning'
                elif 'complete' in msg.body.lower() or 'success' in msg.body.lower():
                    notif_type = 'success'
                
                # Extract text from HTML body
                from markupsafe import Markup
                import re
                body_text = re.sub('<[^<]+?>', '', msg.body or '')[:200]
                
                # Check if message is read via partner notifications
                is_read = False
                if user.partner_id:
                    partner_notifications = request.env['mail.notification'].search([
                        ('mail_message_id', '=', msg.id),
                        ('res_partner_id', '=', user.partner_id.id)
                    ], limit=1)
                    is_read = partner_notifications.is_read if partner_notifications else False
                
                notifications_data.append({
                    'id': msg.id,
                    'type': notif_type,
                    'title': msg.subject or 'Notification',
                    'message': body_text,
                    'time': msg.create_date.isoformat(),
                    'read': is_read
                })
            
            # Get shift-related notifications
            # Find shifts starting soon (within next 2 hours)
            upcoming_shifts = request.env['guard.shift'].search([
                ('guard_id', '=', guard.id),
                ('status', '=', 'scheduled'),
                ('start_datetime', '>', datetime.now()),
                ('start_datetime', '<', datetime.now() + timedelta(hours=2))
            ], order='start_datetime asc', limit=3)
            
            # Find scheduled shifts that have passed start time (not started)
            overdue_shifts = request.env['guard.shift'].search([
                ('guard_id', '=', guard.id),
                ('status', '=', 'scheduled'),
                ('start_datetime', '<=', datetime.now()),
                ('start_datetime', '>=', datetime.now() - timedelta(hours=2))
            ], order='start_datetime desc', limit=2)
            
            # Find shifts that have started and are in progress
            in_progress_shifts = request.env['guard.shift'].search([
                ('guard_id', '=', guard.id),
                ('status', '=', 'in_progress'),
                ('start_datetime', '<=', datetime.now()),
                ('end_datetime', '>=', datetime.now())
            ], order='start_datetime desc', limit=2)
            
            # Process upcoming shifts
            for shift in upcoming_shifts:
                time_until = shift.start_datetime - datetime.now()
                minutes = int(time_until.total_seconds() / 60)
                
                # Only show "starting soon" if within 30 minutes
                if minutes <= 30:
                    notifications_data.append({
                        'id': f'shift_{shift.id}',
                        'type': 'info',
                        'title': 'Shift Starting Soon',
                        'message': f'Your shift at {shift.site_id.name} starts in {minutes} minutes',
                        'time': datetime.now().isoformat(),
                        'read': False
                    })
            
            # Process overdue shifts (scheduled but start time has passed)
            for shift in overdue_shifts:
                time_since_start = datetime.now() - shift.start_datetime
                minutes_ago = int(time_since_start.total_seconds() / 60)
                
                # Show notification for shifts that should have started within the last 2 hours
                if minutes_ago <= 120:
                    if minutes_ago < 60:
                        time_text = f'{minutes_ago} minutes ago'
                    else:
                        hours_ago = minutes_ago // 60
                        time_text = f'{hours_ago} hour{"s" if hours_ago > 1 else ""} ago'
                    
                    notifications_data.append({
                        'id': f'shift_overdue_{shift.id}',
                        'type': 'danger',
                        'title': 'Shift Started - Action Required',
                        'message': f'Your shift at {shift.site_id.name} started {time_text} at {shift.start_datetime.strftime("%H:%M")}. Please start your shift now!',
                        'time': shift.start_datetime.isoformat(),
                        'read': False
                    })
            
            # Process in-progress shifts that just started
            for shift in in_progress_shifts:
                time_since_start = datetime.now() - shift.start_datetime
                minutes_ago = int(time_since_start.total_seconds() / 60)
                
                # Only show notification for shifts that started within the last 2 hours
                if minutes_ago <= 120:
                    if minutes_ago < 60:
                        time_text = f'{minutes_ago} minutes ago'
                    else:
                        hours_ago = minutes_ago // 60
                        time_text = f'{hours_ago} hour{"s" if hours_ago > 1 else ""} ago'
                    
                    notifications_data.append({
                        'id': f'shift_started_{shift.id}',
                        'type': 'warning',
                        'title': 'Shift Already Started',
                        'message': f'Your shift at {shift.site_id.name} started {time_text} at {shift.start_datetime.strftime("%H:%M")}',
                        'time': shift.start_datetime.isoformat(),
                        'read': False
                    })
            
            # Count unread notifications
            unread_count = len([n for n in notifications_data if not n.get('read', False)])
            
            return {
                'result': {
                    'success': True,
                    'notifications': notifications_data[:limit],
                    'unread_count': unread_count
                }
            }
            
        except Exception as e:
            _logger.exception('Failed to load notifications')
            return {
                'result': {
                    'success': False,
                    'error': str(e),
                    'notifications': [],
                    'unread_count': 0
                }
            }

    @http.route('/guardpro/api/notifications/mark_read', type='json', auth='user', methods=['POST'], csrf=False)
    def mark_notification_read(self, notification_id, **kwargs):
        """
        Mark a notification as read.
        
        Args:
            notification_id: ID of the notification (can be message ID or shift_X format)
        
        Returns:
            dict: {'success': True} or {'success': False, 'error': '...'}
        """
        try:
            user = request.env.user
            
            # Handle shift notifications (format: "shift_123", "shift_started_123", "shift_overdue_123")
            if isinstance(notification_id, str) and (notification_id.startswith('shift_') or 
                                                       notification_id.startswith('shift_started_') or
                                                       notification_id.startswith('shift_overdue_')):
                # These are ephemeral notifications, just return success
                return {'result': {'success': True}}
            
            # Handle regular mail.message notifications
            message = request.env['mail.message'].browse(int(notification_id))
            
            if message.exists():
                # Mark notification as read for this user
                notifications = request.env['mail.notification'].search([
                    ('mail_message_id', '=', message.id),
                    ('res_partner_id', '=', user.partner_id.id)
                ])
                notifications.write({'is_read': True})
            
            return {'result': {'success': True}}
            
        except Exception as e:
            _logger.exception('Failed to mark notification as read')
            return {
                'result': {
                    'success': False,
                    'error': str(e)
                }
            }

    @http.route('/guardpro/api/notifications/clear_all', type='json', auth='user', methods=['POST'], csrf=False)
    def clear_all_notifications(self, **kwargs):
        """
        Clear all notifications for the current user.
        
        Returns:
            dict: {'success': True} or {'success': False, 'error': '...'}
        """
        try:
            user = request.env.user
            
            # Mark all notifications for this user as read
            notifications = request.env['mail.notification'].search([
                ('res_partner_id', '=', user.partner_id.id),
                ('is_read', '=', False)
            ])
            notifications.write({'is_read': True})
            
            return {'result': {'success': True}}
            
        except Exception as e:
            _logger.exception('Failed to clear all notifications')
            return {
                'result': {
                    'success': False,
                    'error': str(e)
                }
            }

