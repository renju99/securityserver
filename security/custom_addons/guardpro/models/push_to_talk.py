# -*- coding: utf-8 -*-
"""Push-to-Talk (Walkie-Talkie) System for Guards."""

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from odoo.tools.translate import _
import logging
import base64

_logger = logging.getLogger(__name__)


class PushToTalkChannel(models.Model):
    """Push-to-talk communication channel (like a walkie-talkie channel)."""

    _name = 'push.to.talk.channel'
    _description = 'Push-to-Talk Channel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _active_name = 'active'

    name = fields.Char(
        string='Channel Name',
        required=True,
        help='Name of the communication channel (e.g., "Site 1", "Patrol Team A")'
    )
    code = fields.Char(
        string='Channel Code',
        required=True,
        copy=False,
        index=True,
        help='Unique code for the channel'
    )
    description = fields.Text(
        string='Description'
    )
    channel_type = fields.Selection([
        ('site', 'Site Channel'),
        ('team', 'Team Channel'),
        ('emergency', 'Emergency Channel'),
        ('general', 'General Channel'),
        ('custom', 'Custom Channel')
    ], string='Channel Type', default='general', required=True)
    
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        help='Associated site (for site channels)'
    )
    
    member_ids = fields.Many2many(
        'guard.profile',
        'push_to_talk_channel_guard_rel',
        'channel_id',
        'guard_id',
        string='Members',
        help='Guards who can use this channel'
    )
    
    supervisor_ids = fields.Many2many(
        'res.users',
        'push_to_talk_channel_supervisor_rel',
        'channel_id',
        'user_id',
        string='Supervisors',
        help='Supervisors who can monitor this channel'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Only active channels can be used'
    )
    
    is_public = fields.Boolean(
        string='Public Channel',
        default=False,
        help='Public channels can be joined by any guard'
    )
    
    max_duration_seconds = fields.Integer(
        string='Max Message Duration (seconds)',
        default=60,
        help='Maximum duration for a voice message in seconds'
    )
    
    voice_message_ids = fields.One2many(
        'push.to.talk.message',
        'channel_id',
        string='Voice Messages',
        readonly=True,
        help='Voice messages sent on this channel'
    )
    
    last_message_time = fields.Datetime(
        string='Last Message Time',
        compute='_compute_last_message',
        store=True
    )
    
    active_members_count = fields.Integer(
        string='Active Members',
        compute='_compute_active_members',
        help='Number of guards currently active on this channel'
    )
    
    @api.depends('voice_message_ids', 'voice_message_ids.created_at')
    def _compute_last_message(self):
        """Compute last message time."""
        for record in self:
            last_msg = record.voice_message_ids.sorted('created_at', reverse=True)[:1]
            if last_msg:
                record.last_message_time = last_msg.created_at
            else:
                record.last_message_time = False
    
    @api.depends('member_ids')
    def _compute_active_members(self):
        """Compute active members count."""
        for record in self:
            # Count guards who have sent messages in the last 5 minutes
            from datetime import timedelta
            cutoff = fields.Datetime.now() - timedelta(minutes=5)
            active_guards = record.voice_message_ids.filtered(
                lambda m: m.created_at >= cutoff
            ).mapped('sender_guard_id')
            record.active_members_count = len(set(active_guards.ids))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate channel code if not provided."""
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('push.to.talk.channel') or 'CH-0000'
        return super().create(vals_list)
    
    @api.constrains('code')
    def _check_code_unique(self):
        """Ensure channel code is unique."""
        for record in self:
            if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]):
                raise ValidationError(_('Channel code must be unique.'))
    
    @api.constrains('max_duration_seconds')
    def _check_max_duration(self):
        """Validate max duration."""
        for record in self:
            if record.max_duration_seconds < 1 or record.max_duration_seconds > 300:
                raise ValidationError(_('Max duration must be between 1 and 300 seconds.'))
    
    def action_join_channel(self, guard_id):
        """Add a guard to the channel.
        
        Uses sudo() to allow guards to join channels even if they don't have
        write access to the channel model. This is safe because we're only
        adding the guard to the member_ids list.
        """
        self.ensure_one()
        # Use sudo() to read guard profile (bypasses record rules)
        guard = self.env['guard.profile'].sudo().browse(guard_id)
        if not guard.exists():
            raise UserError(_('Guard not found.'))
        
        # Check if guard is already a member (using sudo to read member_ids)
        if guard.id not in self.sudo().member_ids.ids:
            # Use sudo() to allow guards to join channels
            # This is safe because we're only modifying member_ids
            self.sudo().write({'member_ids': [(4, guard.id)]})
            _logger.info('Guard %s joined channel %s', guard.name, self.name)
        
        return True
    
    def action_leave_channel(self, guard_id):
        """Remove a guard from the channel.
        
        Uses sudo() to allow guards to leave channels even if they don't have
        write access to the channel model. This is safe because we're only
        removing the guard from the member_ids list.
        """
        self.ensure_one()
        # Use sudo() to read guard profile (bypasses record rules)
        guard = self.env['guard.profile'].sudo().browse(guard_id)
        if not guard.exists():
            raise UserError(_('Guard not found.'))
        
        # Check if guard is a member (using sudo to read member_ids)
        if guard.id in self.sudo().member_ids.ids:
            # Use sudo() to allow guards to leave channels
            # This is safe because we're only modifying member_ids
            self.sudo().write({'member_ids': [(3, guard.id)]})
            _logger.info('Guard %s left channel %s', guard.name, self.name)
        
        return True
    
    def get_available_channels_for_guard(self, guard_id):
        """Get channels available for a guard.
        
        Returns active channels where the guard is assigned as a member.
        Channels are assigned to guards based on projects they manage.
        """
        guard = self.env['guard.profile'].browse(guard_id)
        if not guard.exists():
            return self.env['push.to.talk.channel']
        
        # Get only channels where guard is a member (assigned channels)
        # Use sudo() to bypass record rules for this search
        # This is safe because we're filtering by guard membership
        channels = self.sudo().search([
            ('active', '=', True),
            ('member_ids', 'in', [guard.id])
        ])
        
        return channels


class PushToTalkMessage(models.Model):
    """Voice message sent via push-to-talk."""
    
    _name = 'push.to.talk.message'
    _description = 'Push-to-Talk Message'
    _order = 'created_at desc'

    channel_id = fields.Many2one(
        'push.to.talk.channel',
        string='Channel',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    sender_guard_id = fields.Many2one(
        'guard.profile',
        string='Sender Guard',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    sender_user_id = fields.Many2one(
        'res.users',
        string='Sender User',
        related='sender_guard_id.user_id',
        store=True,
        readonly=True
    )
    
    audio_data = fields.Binary(
        string='Audio File',
        attachment=True,
        required=True,
        help='Voice message audio data'
    )
    
    audio_filename = fields.Char(
        string='Audio Filename',
        default='voice_message.ogg'
    )
    
    duration_seconds = fields.Float(
        string='Duration (seconds)',
        required=True,
        help='Duration of the voice message'
    )
    
    file_size = fields.Integer(
        string='File Size (bytes)',
        help='Size of the audio file'
    )
    
    created_at = fields.Datetime(
        string='Sent At',
        default=fields.Datetime.now,
        required=True,
        index=True
    )
    
    is_urgent = fields.Boolean(
        string='Urgent',
        default=False,
        help='Urgent messages are highlighted and played immediately'
    )
    
    location_latitude = fields.Float(
        string='Latitude',
        digits=(10, 7),
        help='Guard location when message was sent'
    )
    
    location_longitude = fields.Float(
        string='Longitude',
        digits=(10, 7),
        help='Guard location when message was sent'
    )
    
    played_by_ids = fields.Many2many(
        'res.users',
        'push_to_talk_message_played_rel',
        'message_id',
        'user_id',
        string='Played By',
        help='Users who have played this message'
    )
    
    @api.constrains('duration_seconds')
    def _check_duration(self):
        """Validate message duration."""
        for record in self:
            if record.duration_seconds < 0.1:
                raise ValidationError(_('Message duration must be at least 0.1 seconds.'))
            
            if record.channel_id and record.duration_seconds > record.channel_id.max_duration_seconds:
                raise ValidationError(
                    _('Message duration (%s seconds) exceeds channel maximum (%s seconds).') %
                    (record.duration_seconds, record.channel_id.max_duration_seconds)
                )
    
    @api.constrains('file_size')
    def _check_file_size(self):
        """Validate file size (max 5MB)."""
        for record in self:
            if record.file_size and record.file_size > 5 * 1024 * 1024:
                raise ValidationError(_('Audio file size cannot exceed 5MB.'))
    
    def mark_as_played(self, user_id):
        """Mark message as played by a user."""
        self.ensure_one()
        user = self.env['res.users'].browse(user_id)
        if user.exists() and user not in self.played_by_ids:
            self.write({'played_by_ids': [(4, user.id)]})
            return True
        return False
    
    def get_audio_url(self):
        """Get URL to stream the audio file."""
        self.ensure_one()
        # Use the API endpoint for better control over content-type and streaming
        return f'/guardpro/api/push-to-talk/message/{self.id}/audio'
    
    def action_broadcast_notification(self):
        """Send notification to all channel members about new message."""
        self.ensure_one()
        
        # Get all channel members and supervisors
        recipients = []
        for guard in self.channel_id.member_ids:
            if guard.user_id:
                recipients.append(guard.user_id.partner_id.id)
        
        for supervisor in self.channel_id.supervisor_ids:
            if supervisor.partner_id:
                recipients.append(supervisor.partner_id.id)
        
        if recipients:
            # Send via Odoo bus for real-time notification
            try:
                self.env['bus.bus']._sendmany(
                    [(partner_id, 'push_to_talk_message', {
                        'message_id': self.id,
                        'channel_id': self.channel_id.id,
                        'channel_name': self.channel_id.name,
                        'sender_name': self.sender_guard_id.name,
                        'duration': self.duration_seconds,
                        'is_urgent': self.is_urgent,
                        'created_at': self.created_at.isoformat(),
                        'audio_url': self.get_audio_url()
                    }) for partner_id in recipients]
                )
            except Exception as e:
                _logger.error('Failed to send push-to-talk notification: %s', str(e))
        
        return True
