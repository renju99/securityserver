# -*- coding: utf-8 -*-
"""Guard Messaging System - Real-time communication between guards, supervisors, and teams."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class GuardConversation(models.Model):
    """Conversation thread between guards and/or supervisors."""
    
    _name = 'guard.conversation'
    _description = 'Guard Conversation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'last_message_time desc'

    name = fields.Char(
        string='Conversation Name',
        compute='_compute_name',
        store=True
    )
    conversation_type = fields.Selection([
        ('guard_supervisor', 'Guard ↔ Supervisor'),
        ('guard_guard', 'Guard ↔ Guard'),
        ('group', 'Group Chat')
    ], string='Conversation Type', default='guard_supervisor', required=True)
    
    # For guard-supervisor conversations
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        ondelete='cascade',
        index=True,
        help='Guard in this conversation (for guard-supervisor type)'
    )
    supervisor_id = fields.Many2one(
        'res.users',
        string='Supervisor',
        ondelete='cascade',
        index=True,
        help='Supervisor in this conversation (for guard-supervisor type)'
    )
    
    # For guard-guard conversations
    guard1_id = fields.Many2one(
        'guard.profile',
        string='Guard 1',
        ondelete='cascade',
        index=True,
        help='First guard in guard-to-guard conversation'
    )
    guard2_id = fields.Many2one(
        'guard.profile',
        string='Guard 2',
        ondelete='cascade',
        index=True,
        help='Second guard in guard-to-guard conversation'
    )
    
    # For group conversations
    participant_ids = fields.Many2many(
        'guard.profile',
        'guard_conversation_participant_rel',
        'conversation_id',
        'guard_id',
        string='Participants',
        help='Guards participating in this group conversation'
    )
    supervisor_participant_ids = fields.Many2many(
        'res.users',
        'guard_conversation_supervisor_rel',
        'conversation_id',
        'user_id',
        string='Supervisor Participants',
        help='Supervisors participating in this group conversation'
    )
    
    message_ids = fields.One2many(
        'guard.message',
        'conversation_id',
        string='Messages'
    )
    last_message = fields.Text(
        string='Last Message',
        compute='_compute_last_message',
        store=True
    )
    last_message_time = fields.Datetime(
        string='Last Message Time',
        compute='_compute_last_message',
        store=True
    )
    unread_count_guard = fields.Integer(
        string='Unread Messages (Guard)',
        compute='_compute_unread_counts',
        store=True
    )
    unread_count_supervisor = fields.Integer(
        string='Unread Messages (Supervisor)',
        compute='_compute_unread_counts',
        store=True
    )
    is_active = fields.Boolean(
        string='Active',
        default=True
    )
    
    @api.depends('conversation_type', 'guard_id', 'supervisor_id', 'guard1_id', 'guard2_id', 'participant_ids')
    def _compute_name(self):
        """Compute conversation name."""
        for record in self:
            if record.conversation_type == 'guard_supervisor':
                if record.guard_id and record.supervisor_id:
                    record.name = f"{record.guard_id.name} ↔ {record.supervisor_id.name}"
                else:
                    record.name = 'New Conversation'
            elif record.conversation_type == 'guard_guard':
                if record.guard1_id and record.guard2_id:
                    record.name = f"{record.guard1_id.name} ↔ {record.guard2_id.name}"
                else:
                    record.name = 'Guard Conversation'
            elif record.conversation_type == 'group':
                if record.participant_ids:
                    names = record.participant_ids.mapped('name')[:3]
                    record.name = ', '.join(names)
                    if len(record.participant_ids) > 3:
                        record.name += f" +{len(record.participant_ids) - 3} more"
                else:
                    record.name = 'Group Chat'
            else:
                record.name = 'New Conversation'
    
    @api.depends('message_ids', 'message_ids.content', 'message_ids.created_at')
    def _compute_last_message(self):
        """Compute last message details."""
        for record in self:
            last_msg = record.message_ids.sorted('created_at', reverse=True)[:1]
            if last_msg:
                record.last_message = last_msg.content[:100]
                record.last_message_time = last_msg.created_at
            else:
                record.last_message = False
                record.last_message_time = False
    
    @api.depends('message_ids', 'message_ids.is_read', 'message_ids.sender_id', 'conversation_type')
    def _compute_unread_counts(self):
        """Compute unread message counts for both parties."""
        for record in self:
            current_user = self.env.user
            current_guard = self.env['guard.profile'].search([
                ('user_id', '=', current_user.id)
            ], limit=1)
            
            if record.conversation_type == 'guard_supervisor':
                # Count unread messages sent by supervisor (for guard to read)
                if record.supervisor_id:
                    record.unread_count_guard = len(record.message_ids.filtered(
                        lambda m: not m.is_read and m.sender_id.id == record.supervisor_id.id
                    ))
                else:
                    record.unread_count_guard = 0
                
                # Count unread messages sent by guard (for supervisor to read)
                guard_user = record.guard_id.user_id if record.guard_id else False
                if guard_user:
                    record.unread_count_supervisor = len(record.message_ids.filtered(
                        lambda m: not m.is_read and m.sender_id.id == guard_user.id
                    ))
                else:
                    record.unread_count_supervisor = 0
            else:
                # For guard-guard and group conversations, count unread for current user
                if current_guard:
                    # Count messages not sent by current user and not read
                    unread = record.message_ids.filtered(
                        lambda m: not m.is_read and m.sender_id.id != current_user.id
                    )
                    record.unread_count_guard = len(unread)
                    record.unread_count_supervisor = 0
                else:
                    record.unread_count_guard = 0
                    record.unread_count_supervisor = 0
    
    def action_new_message(self):
        """Open form to create a new message in this conversation."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Message'),
            'res_model': 'guard.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_conversation_id': self.id,
            }
        }
    
    @api.model
    def get_or_create_guard_conversation(self, guard1_id, guard2_id):
        """Get or create a guard-to-guard conversation."""
        # Ensure consistent ordering (lower ID first)
        if guard1_id > guard2_id:
            guard1_id, guard2_id = guard2_id, guard1_id
        
        conversation = self.search([
            ('conversation_type', '=', 'guard_guard'),
            ('guard1_id', '=', guard1_id),
            ('guard2_id', '=', guard2_id)
        ], limit=1)
        
        if not conversation:
            conversation = self.create({
                'conversation_type': 'guard_guard',
                'guard1_id': guard1_id,
                'guard2_id': guard2_id,
                'is_active': True
            })
        
        return conversation


class GuardMessage(models.Model):
    """Individual message in a conversation or channel."""
    
    _name = 'guard.message'
    _description = 'Guard Message'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'created_at desc'

    conversation_id = fields.Many2one(
        'guard.conversation',
        string='Conversation',
        ondelete='cascade',
        index=True,
        help='Direct conversation (guard-guard or guard-supervisor)'
    )
    channel_id = fields.Many2one(
        'guard.message.channel',
        string='Channel',
        ondelete='cascade',
        index=True,
        help='Team chat channel'
    )
    is_broadcast = fields.Boolean(
        string='Broadcast Message',
        default=False,
        help='Message sent to all guards or specific group'
    )
    broadcast_type = fields.Selection([
        ('all_guards', 'All Guards'),
        ('site_guards', 'Site Guards'),
        ('shift_guards', 'Shift Guards'),
        ('custom_group', 'Custom Group')
    ], string='Broadcast Type', help='Type of broadcast message')
    broadcast_recipient_ids = fields.Many2many(
        'guard.profile',
        'guard_message_broadcast_rel',
        'message_id',
        'guard_id',
        string='Broadcast Recipients',
        help='Guards who received this broadcast'
    )
    
    sender_id = fields.Many2one(
        'res.users',
        string='Sender',
        required=True,
        default=lambda self: self.env.user,
        ondelete='cascade',
        index=True
    )
    sender_guard_id = fields.Many2one(
        'guard.profile',
        string='Sender Guard',
        compute='_compute_sender_guard',
        store=True,
        help='Guard profile of sender'
    )
    receiver_id = fields.Many2one(
        'res.users',
        string='Receiver',
        ondelete='cascade',
        help='Direct message receiver (for 1-on-1 conversations)'
    )
    
    @api.depends('sender_id')
    def _compute_sender_guard(self):
        """Compute sender guard profile."""
        for record in self:
            if record.sender_id:
                guard = self.env['guard.profile'].search([
                    ('user_id', '=', record.sender_id.id)
                ], limit=1)
                record.sender_guard_id = guard.id if guard else False
            else:
                record.sender_guard_id = False
    
    @api.constrains('conversation_id', 'channel_id', 'is_broadcast')
    def _check_message_context(self):
        """Ensure message has exactly one context (conversation, channel, or broadcast)."""
        for record in self:
            contexts = sum([
                bool(record.conversation_id),
                bool(record.channel_id),
                bool(record.is_broadcast)
            ])
            if contexts != 1:
                raise ValidationError(_(
                    'Message must have exactly one context: conversation, channel, or broadcast.'
                ))
    message_type = fields.Selection([
        ('text', 'Text Message'),
        ('voice', 'Voice Message'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('location', 'Location'),
        ('system', 'System Message')
    ], string='Message Type', default='text', required=True)
    
    content = fields.Text(
        string='Message Content'
    )
    media_url = fields.Char(
        string='Media URL'
    )
    media_duration = fields.Integer(
        string='Media Duration (seconds)',
        help='For voice/video messages'
    )
    media_size = fields.Integer(
        string='Media Size (bytes)'
    )
    
    is_read = fields.Boolean(
        string='Read',
        default=False,
        index=True
    )
    read_at = fields.Datetime(
        string='Read At'
    )
    
    is_urgent = fields.Boolean(
        string='Urgent',
        default=False,
        help='Urgent messages are highlighted'
    )
    is_system = fields.Boolean(
        string='System Message',
        default=False,
        help='Automated system messages'
    )
    
    created_at = fields.Datetime(
        string='Sent At',
        default=fields.Datetime.now,
        required=True,
        index=True
    )
    
    # Location data (for location type messages)
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7)
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7)
    )
    location_name = fields.Char(
        string='Location Name'
    )
    
    # Related records (for context)
    related_shift_id = fields.Many2one(
        'guard.shift',
        string='Related Shift',
        help='Shift this message relates to'
    )
    related_incident_id = fields.Many2one(
        'incident.report',
        string='Related Incident',
        help='Incident this message relates to'
    )
    related_site_id = fields.Many2one(
        'client.site',
        string='Related Site',
        help='Site this message relates to'
    )
    
    # Message template (if used)
    template_id = fields.Many2one(
        'guard.message.template',
        string='Message Template',
        help='Template used to create this message'
    )
    
    # Read receipts for group messages
    read_by_ids = fields.Many2many(
        'res.users',
        'guard_message_read_rel',
        'message_id',
        'user_id',
        string='Read By',
        help='Users who have read this message'
    )
    
    @api.constrains('media_size')
    def _check_media_size(self):
        """Validate media file size."""
        for record in self:
            if record.media_size:
                # Images: max 5MB, Videos: max 20MB, Voice: max 2MB
                max_size = {
                    'image': 5 * 1024 * 1024,  # 5MB
                    'video': 20 * 1024 * 1024,  # 20MB
                    'voice': 2 * 1024 * 1024   # 2MB
                }
                limit = max_size.get(record.message_type, 5 * 1024 * 1024)
                
                if record.media_size > limit:
                    raise ValidationError(
                        f'Media file too large. Maximum size for {record.message_type} is {limit / 1024 / 1024}MB'
                    )
    
    def mark_as_read(self):
        """Mark message as read."""
        self.ensure_one()
        current_user = self.env.user
        
        # For direct messages
        if self.receiver_id and self.receiver_id.id == current_user.id:
            if not self.is_read:
                self.write({
                    'is_read': True,
                    'read_at': fields.Datetime.now()
                })
                return True
        
        # For channel/broadcast messages, add to read_by
        if (self.channel_id or self.is_broadcast) and current_user.id not in self.read_by_ids.ids:
            self.write({
                'read_by_ids': [(4, current_user.id)]
            })
            return True
        
        return False
    
    def create_notification(self):
        """Create notification for receiver(s)."""
        self.ensure_one()
        
        recipients = []
        
        # Direct message
        if self.receiver_id:
            recipients.append(self.receiver_id.partner_id.id)
        
        # Channel message - notify all channel members
        elif self.channel_id:
            for member in self.channel_id.member_ids:
                if member.user_id and member.user_id.partner_id:
                    recipients.append(member.user_id.partner_id.id)
        
        # Broadcast message - notify all recipients
        elif self.is_broadcast and self.broadcast_recipient_ids:
            for guard in self.broadcast_recipient_ids:
                if guard.user_id and guard.user_id.partner_id:
                    recipients.append(guard.user_id.partner_id.id)
        
        if recipients:
            # Create Odoo notification
            self.env['mail.message'].sudo().create({
                'message_type': 'notification',
                'subtype_id': self.env.ref('mail.mt_comment').id,
                'body': Markup(
                    '<p><strong>New message from %s</strong></p>'
                    '<p>%s</p>'
                    '%s'
                ) % (
                    self.sender_id.name,
                    self.content[:200] if self.content else '[Media Message]',
                    '<p style="color: red;"><strong>⚠️ URGENT</strong></p>' if self.is_urgent else ''
                ),
                'author_id': self.sender_id.partner_id.id,
                'model': 'guard.message',
                'res_id': self.id,
                'partner_ids': [(6, 0, recipients)]
            })
    
    @api.model
    def send_broadcast(self, content, broadcast_type='all_guards', recipient_ids=None, 
                      site_id=None, shift_id=None, is_urgent=False, sender_id=None, **kwargs):
        """
        Send broadcast message to multiple guards.
        
        Args:
            content: Message content
            broadcast_type: Type of broadcast ('all_guards', 'site_guards', 'shift_guards', 'custom_group')
            recipient_ids: List of guard IDs (for custom_group)
            site_id: Site ID (for site_guards)
            shift_id: Shift ID (for shift_guards)
            is_urgent: Whether message is urgent
            sender_id: Sender user ID (defaults to current user)
        
        Returns:
            Created message record
        """
        if sender_id is None:
            sender_id = self.env.user.id
        
        # Determine recipients based on broadcast type
        GuardProfile = self.env['guard.profile']
        recipients = GuardProfile.browse()
        
        if broadcast_type == 'all_guards':
            recipients = GuardProfile.search([('status', '=', 'active')])
        elif broadcast_type == 'site_guards' and site_id:
            site = self.env['client.site'].browse(site_id)
            if site.exists():
                # Get guards assigned to this site
                recipients = GuardProfile.search([
                    ('status', '=', 'active'),
                    ('site_ids', 'in', [site_id])
                ])
        elif broadcast_type == 'shift_guards' and shift_id:
            shift = self.env['guard.shift'].browse(shift_id)
            if shift.exists():
                # Get guards on this shift
                recipients = GuardProfile.search([
                    ('status', '=', 'active'),
                    ('shift_ids', 'in', [shift_id])
                ])
        elif broadcast_type == 'custom_group' and recipient_ids:
            recipients = GuardProfile.browse(recipient_ids)
        
        if not recipients:
            raise ValidationError(_('No recipients found for broadcast message.'))
        
        # Create broadcast message
        message = self.create({
            'is_broadcast': True,
            'broadcast_type': broadcast_type,
            'broadcast_recipient_ids': [(6, 0, recipients.ids)],
            'sender_id': sender_id,
            'content': content,
            'is_urgent': is_urgent,
            'related_site_id': site_id,
            'related_shift_id': shift_id,
            'message_type': kwargs.get('message_type', 'text'),
            'media_url': kwargs.get('media_url'),
            'media_duration': kwargs.get('media_duration'),
            **kwargs
        })
        
        # Create notifications
        message.create_notification()
        
        _logger.info(
            'Broadcast message sent by user %s to %d guards (type: %s)',
            sender_id, len(recipients), broadcast_type
        )
        
        return message


class GuardStatusUpdate(models.Model):
    """Guard status updates (on break, patrolling, etc.)."""
    
    _name = 'guard.status.update'
    _description = 'Guard Status Update'
    _order = 'started_at desc'

    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade',
        index=True
    )
    status = fields.Selection([
        ('on_duty', 'On Duty'),
        ('on_break', 'On Break'),
        ('restroom', 'Restroom'),
        ('patrolling', 'Patrolling'),
        ('need_assistance', 'Need Assistance'),
        ('meal_break', 'Meal Break'),
        ('training', 'In Training'),
        ('other', 'Other')
    ], string='Status', required=True, default='on_duty')
    
    notes = fields.Text(
        string='Notes'
    )
    started_at = fields.Datetime(
        string='Started At',
        default=fields.Datetime.now,
        required=True
    )
    ended_at = fields.Datetime(
        string='Ended At'
    )
    auto_end_duration = fields.Integer(
        string='Auto-End Duration (minutes)',
        help='Automatically end status after X minutes'
    )
    is_active = fields.Boolean(
        string='Currently Active',
        compute='_compute_is_active',
        store=True
    )
    duration_minutes = fields.Integer(
        string='Duration (minutes)',
        compute='_compute_duration'
    )
    
    # Location when status was set
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7)
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7)
    )
    
    @api.depends('ended_at')
    def _compute_is_active(self):
        """Compute if status is currently active."""
        for record in self:
            record.is_active = not record.ended_at
    
    @api.depends('started_at', 'ended_at')
    def _compute_duration(self):
        """Compute duration of status."""
        for record in self:
            if record.started_at:
                end_time = record.ended_at or fields.Datetime.now()
                duration = end_time - record.started_at
                record.duration_minutes = int(duration.total_seconds() / 60)
            else:
                record.duration_minutes = 0
    
    def end_status(self):
        """End the current status."""
        self.ensure_one()
        if not self.ended_at:
            self.write({'ended_at': fields.Datetime.now()})
            return True
        return False
    
    @api.model
    def get_current_status(self, guard_id):
        """Get current active status for a guard."""
        return self.search([
            ('guard_id', '=', guard_id),
            ('ended_at', '=', False)
        ], limit=1)
    
    @api.model
    def auto_end_expired_statuses(self):
        """Cron job to auto-end statuses that have exceeded their duration."""
        now = fields.Datetime.now()
        
        expired_statuses = self.search([
            ('ended_at', '=', False),
            ('auto_end_duration', '>', 0)
        ])
        
        for status in expired_statuses:
            duration = (now - status.started_at).total_seconds() / 60
            if duration >= status.auto_end_duration:
                status.end_status()
                _logger.info(f'Auto-ended status {status.id} for guard {status.guard_id.name}')


class GuardMessageChannel(models.Model):
    """Team chat channels for guards."""
    
    _name = 'guard.message.channel'
    _description = 'Guard Message Channel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'last_message_time desc'

    name = fields.Char(
        string='Channel Name',
        required=True,
        tracking=True
    )
    description = fields.Text(
        string='Description',
        help='Channel purpose and guidelines'
    )
    channel_type = fields.Selection([
        ('site', 'Site Channel'),
        ('shift', 'Shift Channel'),
        ('team', 'Team Channel'),
        ('project', 'Project Channel'),
        ('general', 'General')
    ], string='Channel Type', default='general', required=True, tracking=True)
    
    # Channel membership
    member_ids = fields.Many2many(
        'guard.profile',
        'guard_channel_member_rel',
        'channel_id',
        'guard_id',
        string='Members',
        help='Guards who are members of this channel'
    )
    supervisor_ids = fields.Many2many(
        'res.users',
        'guard_channel_supervisor_rel',
        'channel_id',
        'user_id',
        string='Supervisors',
        help='Supervisors who can moderate this channel'
    )
    
    # Channel settings
    is_public = fields.Boolean(
        string='Public Channel',
        default=False,
        help='All guards can join public channels'
    )
    is_archived = fields.Boolean(
        string='Archived',
        default=False,
        help='Archived channels are read-only'
    )
    allow_guards_to_post = fields.Boolean(
        string='Allow Guards to Post',
        default=True,
        help='If disabled, only supervisors can post'
    )
    
    # Related records
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        help='Site this channel is for (for site channels)'
    )
    shift_id = fields.Many2one(
        'guard.shift',
        string='Shift',
        help='Shift this channel is for (for shift channels)'
    )
    
    # Messages
    message_ids = fields.One2many(
        'guard.message',
        'channel_id',
        string='Messages'
    )
    message_count = fields.Integer(
        string='Message Count',
        compute='_compute_message_count',
        store=True
    )
    last_message = fields.Text(
        string='Last Message',
        compute='_compute_last_message',
        store=True
    )
    last_message_time = fields.Datetime(
        string='Last Message Time',
        compute='_compute_last_message',
        store=True
    )

    def is_accessible_by_guard(self, guard):
        """Team chat channel: membership/public rules + site scope (user.site_ids).

        Site-assigned guards only see channels linked to one of their sites, or
        legacy channels with no site if they are explicit members (not public).

        If ``all_sites_access`` is enabled, members may use the channel regardless
        of site assignment.
        """
        self.ensure_one()
        if self.is_archived:
            return False
        if not guard or not guard.exists():
            return False
        user = guard.user_id
        if not self.is_public and guard.id not in self.member_ids.ids:
            return False
        # Global channel: only explicit members skip site checks (not anonymous public viewers)
        if self.all_sites_access and guard.id in self.member_ids.ids:
            return True
        if user and user.site_ids:
            if self.site_id:
                return self.site_id.id in user.site_ids.ids
            if self.is_public:
                return False
            return guard.id in self.member_ids.ids
        return True
    
    # Statistics
    active_member_count = fields.Integer(
        string='Active Members',
        compute='_compute_active_members',
        store=True
    )
    
    @api.depends('message_ids')
    def _compute_message_count(self):
        """Compute total message count."""
        for record in self:
            record.message_count = len(record.message_ids)
    
    @api.depends('message_ids', 'message_ids.content', 'message_ids.created_at')
    def _compute_last_message(self):
        """Compute last message details."""
        for record in self:
            last_msg = record.message_ids.sorted('created_at', reverse=True)[:1]
            if last_msg:
                record.last_message = last_msg.content[:100] if last_msg.content else '[Media Message]'
                record.last_message_time = last_msg.created_at
            else:
                record.last_message = False
                record.last_message_time = False
    
    @api.depends('member_ids')
    def _compute_active_members(self):
        """Compute active member count."""
        for record in self:
            record.active_member_count = len(record.member_ids.filtered(lambda m: m.status == 'active'))
    
    def action_add_members(self):
        """Action to add members to channel."""
        self.ensure_one()
        return {
            'name': _('Add Members to Channel'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.profile',
            'view_mode': 'list',
            'domain': [('status', '=', 'active')],
            'context': {
                'default_channel_ids': [(4, self.id)],
                'channel_id': self.id
            },
            'target': 'new'
        }
    
    def action_view_messages(self):
        """Open channel messages."""
        self.ensure_one()
        return {
            'name': _('Channel Messages - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.message',
            'view_mode': 'list,form',
            'domain': [('channel_id', '=', self.id)],
            'context': {'default_channel_id': self.id}
        }


class GuardMessageTemplate(models.Model):
    """Message templates for quick messaging."""
    
    _name = 'guard.message.template'
    _description = 'Guard Message Template'
    _order = 'name'

    name = fields.Char(
        string='Template Name',
        required=True,
        tracking=True
    )
    description = fields.Text(
        string='Description',
        help='When to use this template'
    )
    template_type = fields.Selection([
        ('incident', 'Incident Related'),
        ('shift', 'Shift Related'),
        ('general', 'General'),
        ('emergency', 'Emergency'),
        ('reminder', 'Reminder')
    ], string='Template Type', default='general', required=True)
    
    subject = fields.Char(
        string='Subject',
        help='Message subject (if applicable)'
    )
    content = fields.Text(
        string='Message Content',
        required=True,
        help='Template message content. Use {{variable}} for placeholders.'
    )
    
    # Variables that can be used in template
    available_variables = fields.Text(
        string='Available Variables',
        compute='_compute_available_variables',
        help='List of variables that can be used in this template'
    )
    
    # Usage tracking
    usage_count = fields.Integer(
        string='Usage Count',
        default=0,
        help='Number of times this template has been used'
    )
    last_used = fields.Datetime(
        string='Last Used',
        help='When this template was last used'
    )
    
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Only active templates are available for use'
    )
    
    @api.depends('template_type')
    def _compute_available_variables(self):
        """Compute available variables based on template type."""
        for record in self:
            variables = {
                'general': ['{{guard_name}}', '{{sender_name}}', '{{date}}', '{{time}}'],
                'incident': ['{{guard_name}}', '{{incident_type}}', '{{incident_location}}', '{{incident_time}}', '{{incident_id}}'],
                'shift': ['{{guard_name}}', '{{shift_time}}', '{{site_name}}', '{{shift_date}}'],
                'emergency': ['{{guard_name}}', '{{location}}', '{{emergency_type}}', '{{time}}'],
                'reminder': ['{{guard_name}}', '{{reminder_text}}', '{{due_date}}']
            }
            record.available_variables = '\n'.join(variables.get(record.template_type, variables['general']))
    
    def render_template(self, context=None):
        """Render template with context variables."""
        self.ensure_one()
        if context is None:
            context = {}
        
        content = self.content
        # Simple variable replacement
        for key, value in context.items():
            content = content.replace(f'{{{{{key}}}}}', str(value))
        
        return content
    
    def action_use_template(self):
        """Action to use this template."""
        self.ensure_one()
        self.write({
            'usage_count': self.usage_count + 1,
            'last_used': fields.Datetime.now()
        })
        
        return {
            'name': _('Send Message'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
                'default_content': self.content
            }
        }

