# -*- coding: utf-8 -*-
"""Push Notifications v2 with User Preferences."""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class NotificationPreference(models.Model):
    """User notification preferences."""
    
    _name = 'notification.preference'
    _description = 'Notification Preference'
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        default=lambda self: self.env.user
    )
    
    # Channel Preferences
    enable_push = fields.Boolean(
        string='Push Notifications',
        default=True
    )
    
    enable_email = fields.Boolean(
        string='Email Notifications',
        default=True
    )
    
    enable_sms = fields.Boolean(
        string='SMS Notifications',
        default=False
    )
    
    # Event Type Preferences
    notify_shift_assigned = fields.Boolean(
        string='Shift Assigned',
        default=True
    )
    
    notify_shift_reminder = fields.Boolean(
        string='Shift Reminders',
        default=True
    )
    
    notify_shift_changed = fields.Boolean(
        string='Shift Changes',
        default=True
    )
    
    notify_incident_created = fields.Boolean(
        string='New Incidents',
        default=True
    )
    
    notify_incident_critical = fields.Boolean(
        string='Critical Incidents',
        default=True
    )
    
    notify_emergency = fields.Boolean(
        string='Emergency Alerts',
        default=True
    )
    
    notify_tour_assigned = fields.Boolean(
        string='Tour Assigned',
        default=True
    )
    
    notify_feedback_received = fields.Boolean(
        string='Feedback Received',
        default=True
    )
    
    notify_training_due = fields.Boolean(
        string='Training Due',
        default=True
    )
    
    # Quiet Hours
    enable_quiet_hours = fields.Boolean(
        string='Enable Quiet Hours',
        default=False
    )
    
    quiet_start_time = fields.Float(
        string='Quiet Hours Start',
        default=22.0,  # 10 PM
        help='Hour of day (0-23.99)'
    )
    
    quiet_end_time = fields.Float(
        string='Quiet Hours End',
        default=7.0,  # 7 AM
        help='Hour of day (0-23.99)'
    )
    
    # Priority Filtering
    only_critical = fields.Boolean(
        string='Only Critical Notifications',
        default=False,
        help='During quiet hours, only send critical notifications'
    )
    
    # Digest
    enable_daily_digest = fields.Boolean(
        string='Daily Digest',
        default=False,
        help='Receive daily summary instead of individual notifications'
    )
    
    digest_time = fields.Float(
        string='Digest Time',
        default=8.0,  # 8 AM
        help='Time to send daily digest'
    )
    
    _sql_constraints = [
        ('user_unique', 'unique(user_id)', 'Each user can only have one notification preference record!'),
    ]
    
    @api.model
    def get_user_preferences(self, user_id=None):
        """Get notification preferences for user."""
        if not user_id:
            user_id = self.env.user.id
        
        pref = self.search([('user_id', '=', user_id)], limit=1)
        
        if not pref:
            # Create default preferences
            pref = self.create({'user_id': user_id})
        
        return pref
    
    def should_send_notification(self, notification_type, is_critical=False):
        """Check if notification should be sent based on preferences."""
        self.ensure_one()
        
        # Check if in quiet hours
        if self.enable_quiet_hours and not is_critical:
            # Get current time in user's timezone
            utc_now = fields.Datetime.now()
            user_tz = self.env.user.tz or 'UTC'
            user_time = fields.Datetime.context_timestamp(self.with_context(tz=user_tz), utc_now)
            current_hour = user_time.hour + (user_time.minute / 60.0)
            
            if self.quiet_start_time < self.quiet_end_time:
                in_quiet_hours = self.quiet_start_time <= current_hour < self.quiet_end_time
            else:  # Quiet hours span midnight
                in_quiet_hours = current_hour >= self.quiet_start_time or current_hour < self.quiet_end_time
            
            if in_quiet_hours and self.only_critical:
                return False
        
        # Check specific notification type
        type_field_map = {
            'shift_assigned': 'notify_shift_assigned',
            'shift_reminder': 'notify_shift_reminder',
            'shift_changed': 'notify_shift_changed',
            'incident_created': 'notify_incident_created',
            'incident_critical': 'notify_incident_critical',
            'emergency': 'notify_emergency',
            'tour_assigned': 'notify_tour_assigned',
            'feedback_received': 'notify_feedback_received',
            'training_due': 'notify_training_due',
        }
        
        field_name = type_field_map.get(notification_type)
        if field_name:
            return getattr(self, field_name, True)
        
        return True


class ResUsers(models.Model):
    """Extend users with notification preferences."""
    
    _inherit = 'res.users'
    
    notification_preference_id = fields.Many2one(
        'notification.preference',
        string='Notification Preferences',
        compute='_compute_notification_preference'
    )
    
    def _compute_notification_preference(self):
        """Get or create notification preferences."""
        for user in self:
            pref = self.env['notification.preference'].search([
                ('user_id', '=', user.id)
            ], limit=1)
            
            if not pref:
                pref = self.env['notification.preference'].create({
                    'user_id': user.id
                })
            
            user.notification_preference_id = pref.id
    
    def action_configure_notifications(self):
        """Open notification preferences."""
        self.ensure_one()
        
        pref = self.env['notification.preference'].search([
            ('user_id', '=', self.id)
        ], limit=1)
        
        if not pref:
            pref = self.env['notification.preference'].create({
                'user_id': self.id
            })
        
        return {
            'name': _('Notification Preferences'),
            'type': 'ir.actions.act_window',
            'res_model': 'notification.preference',
            'res_id': pref.id,
            'view_mode': 'form',
            'target': 'new'
        }

