# -*- coding: utf-8 -*-
"""Push-to-Talk (Walkie-Talkie) System for Guards."""

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from odoo.tools.translate import _
import logging
import base64
import os
import tempfile
from datetime import timedelta, datetime

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
        ('site', 'Project Channel'),
        ('team', 'Team Channel'),
        ('emergency', 'Emergency Channel'),
        ('general', 'General Channel'),
        ('custom', 'Custom Channel')
    ], string='Channel Type', default='general', required=True)
    
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        help='Required for multi-site deployments: only guards assigned to this site '
             '(via their user account) can use this channel. Leave empty only for legacy '
             'single-tenant setups; site-assigned guards will not see channels without a site.'
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
        help='Supervisors who can talk and listen on this channel'
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
        """Get channels available for a guard (legacy helper)."""
        guard = self.env['guard.profile'].sudo().browse(guard_id)
        if not guard.exists():
            return self.env['push.to.talk.channel']
        return self.get_available_channels_for_user(guard.user_id)

    def get_available_channels_for_user(self, user):
        """Channels the logged-in user may talk and listen on."""
        if not user or user._is_public():
            return self.env['push.to.talk.channel']
        channels = self.sudo().search([('active', '=', True)])
        return channels.filtered(lambda c: c.is_accessible_by_user(user))

    @api.model
    def _user_is_ptt_operator(self, user):
        """Guards, supervisors, managers, admins, and client staff may use radio."""
        if not user or user._is_public():
            return False
        if user.has_group('guardpro.group_guardpro_admin'):
            return True
        if user.has_group('guardpro.group_guardpro_supervisor'):
            return True
        if user.has_group('guardpro.group_guardpro_manager'):
            return True
        if user.has_group('guardpro.group_guardpro_client_user'):
            return True
        if user.has_group('guardpro.group_guardpro_guard_portal'):
            return True
        return bool(self.env['guard.profile'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1))

    def is_accessible_by_user(self, user):
        """Project/site scope for any talker (guard, supervisor, or client)."""
        self.ensure_one()
        user = user.sudo() if user else user
        if not user or user._is_public():
            return False
        if user.has_group('guardpro.group_guardpro_admin'):
            return True
        if user.id in self.sudo().supervisor_ids.ids:
            return True
        if not self._user_is_ptt_operator(user):
            return False

        site_ids = set(user.site_ids.ids)
        if self.all_sites_access:
            if user.has_group('guardpro.group_guardpro_supervisor') or user.has_group('guardpro.group_guardpro_manager'):
                return True
            guard = self.env['guard.profile'].sudo().search([('user_id', '=', user.id)], limit=1)
            return bool(guard and guard.id in self.sudo().member_ids.ids)

        if self.site_id and self.site_id.id in site_ids:
            return True

        guard = self.env['guard.profile'].sudo().search([('user_id', '=', user.id)], limit=1)
        if guard:
            return self.is_accessible_by_guard(guard)
        return False

    def is_accessible_by_guard(self, guard):
        """Project scope + optional explicit membership.

        - ``all_sites_access``: explicit members only (global / emergency).
        - ``site_id`` set: any guard whose user is assigned to that site.
        - no ``site_id``: explicit ``member_ids`` only (legacy).
        """
        self.ensure_one()
        guard = guard.sudo() if guard else guard
        if not guard or not guard.exists():
            return False
        user = guard.user_id

        if self.all_sites_access:
            return guard.id in self.sudo().member_ids.ids

        if self.site_id and user and user.site_ids:
            return self.site_id.id in user.site_ids.ids

        if user and user.site_ids:
            return guard.id in self.sudo().member_ids.ids

        return guard.id in self.sudo().member_ids.ids

    def _get_guards_in_channel_scope(self):
        """Guards who may use or receive notifications on this channel."""
        self.ensure_one()
        Guard = self.env['guard.profile'].sudo()
        if self.all_sites_access:
            return self.member_ids
        if self.site_id:
            return Guard.search([('site_ids', 'in', [self.site_id.id])])
        return self.member_ids


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
        required=False,
        ondelete='restrict',
        index=True,
        help='Set when a guard transmits. Empty for supervisor/client talkers.',
    )

    sender_user_id = fields.Many2one(
        'res.users',
        string='Sender User',
        required=False,
        index=True,
        ondelete='restrict',
        help='Login that transmitted this burst (guard, supervisor, or client).',
    )
    
    audio_data = fields.Binary(
        string='Audio File',
        attachment=True,
        required=False,  # Now optional during streaming
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
    
    is_streaming = fields.Boolean(
        string='Is Streaming',
        default=False,
        help='Whether the message is currently being streamed'
    )
    
    stream_id = fields.Char(
        string='Stream ID',
        index=True,
        help='Unique ID for the audio stream session'
    )
    
    chunk_count = fields.Integer(
        string='Chunk Count',
        default=0
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
    
    @api.constrains('duration_seconds', 'is_streaming')
    def _check_duration(self):
        """Validate message duration."""
        for record in self:
            # Streaming sessions start at 0s until the final chunk arrives.
            if record.is_streaming:
                continue
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
    
    def sender_display_name(self):
        """Name shown on occupancy and playback."""
        self.ensure_one()
        if self.sender_guard_id:
            return self.sender_guard_id.name or 'Radio'
        if self.sender_user_id:
            return self.sender_user_id.name or 'Radio'
        return 'Radio'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('sender_user_id') and vals.get('sender_guard_id'):
                guard = self.env['guard.profile'].sudo().browse(vals['sender_guard_id'])
                if guard.user_id:
                    vals['sender_user_id'] = guard.user_id.id
            if not vals.get('sender_user_id'):
                vals['sender_user_id'] = self.env.uid
        return super().create(vals_list)

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

    def _ptt_bus_send(self, notification_type, payload):
        """Odoo 18 Community only has bus.bus._sendone (no _sendmany)."""
        partner_ids = self._get_ptt_bus_recipient_partner_ids()
        if not partner_ids:
            return True
        bus = self.env['bus.bus']
        partners = self.env['res.partner'].browse(partner_ids).exists()
        try:
            for partner in partners:
                bus._sendone(partner, notification_type, payload)
        except Exception as e:
            _logger.error('Failed to broadcast %s: %s', notification_type, e)
        return True

    def broadcast_tx_state(self, state):
        """TETRA-style channel occupancy: start/end of a live transmission."""
        self.ensure_one()
        return self._ptt_bus_send('push_to_talk_tx', {
            'message_id': self.id,
            'channel_id': self.channel_id.id,
            'sender_name': self.sender_display_name(),
            'state': state,
        })

    def action_broadcast_notification(self):
        """Notify channel members that a complete voice message is available (history / UI)."""
        self.ensure_one()
        channel = self.channel_id.sudo()
        return self._ptt_bus_send('push_to_talk_message', {
            'message_id': self.id,
            'channel_id': channel.id,
            'sender_name': self.sender_display_name(),
            'is_urgent': self.is_urgent,
            'audio_url': self.get_audio_url(),
        })

    def _get_ptt_bus_recipient_partner_ids(self):
        """Partner IDs for bus notifications, respecting channel site scope."""
        self.ensure_one()
        channel = self.channel_id.sudo()
        recipients = []
        for guard in channel._get_guards_in_channel_scope():
            if guard.user_id and guard.user_id.partner_id:
                recipients.append(guard.user_id.partner_id.id)
        for supervisor in channel.supervisor_ids:
            if supervisor.partner_id:
                recipients.append(supervisor.partner_id.id)
        if channel.site_id:
            extra_users = self.env['res.users'].sudo().search([
                ('site_ids', 'in', [channel.site_id.id]),
                ('share', '=', False),
            ])
            for user in extra_users:
                if channel.is_accessible_by_user(user) and user.partner_id:
                    recipients.append(user.partner_id.id)
        return list(set(recipients))

    def append_audio_chunk(self, chunk_data, replace=False):
        """Append a streaming chunk to a temporary file and broadcast occupancy.

        ``replace=True`` overwrites the temp file (used for the final complete
        MediaRecorder blob so players do not stop after the first cluster).
        """
        self.ensure_one()
        try:
            # Decode chunk
            if isinstance(chunk_data, str):
                if chunk_data.startswith('data:audio'):
                    chunk_data = chunk_data.split(',')[1]
                chunk_binary = base64.b64decode(chunk_data)
            else:
                chunk_binary = chunk_data

            temp_path = self._get_stream_temp_path()
            mode = 'wb' if replace else 'ab'
            with open(temp_path, mode) as tmp_file:
                tmp_file.write(chunk_binary)

            # Keep metadata updates minimal during streaming
            self.write({
                'chunk_count': self.chunk_count + 1,
            })
            
            # Broadcast chunk specifically
            self._broadcast_chunk(chunk_data)
            
            return True
        except Exception as e:
            _logger.error('Failed to append audio chunk: %s', str(e))
            return False

    def finalize_stream_audio(self):
        """Finalize streaming data by moving accumulated temp bytes into Binary field."""
        self.ensure_one()
        try:
            temp_path = self._get_stream_temp_path()
            if not os.path.exists(temp_path):
                return False

            with open(temp_path, 'rb') as tmp_file:
                audio_binary = tmp_file.read()

            # Match non-streaming uploads: Binary fields expect base64 payloads.
            self.write({
                'audio_data': base64.b64encode(audio_binary),
                'file_size': len(audio_binary),
            })

            try:
                os.remove(temp_path)
            except Exception:
                pass

            return True
        except Exception as e:
            _logger.error('Failed to finalize stream audio: %s', str(e))
            return False

    def _get_stream_temp_path(self):
        """Build deterministic temp path for message stream buffering."""
        self.ensure_one()
        safe_stream_id = (self.stream_id or f'msg_{self.id}').replace('/', '_')
        filename = f'guardpro_ptt_{self.id}_{safe_stream_id}.bin'
        return os.path.join(tempfile.gettempdir(), filename)

    @api.model
    def cron_close_stale_streams(self, max_minutes=2):
        """Close abandoned PTT holds so listeners are not stuck on occupancy."""
        cutoff = fields.Datetime.now() - timedelta(minutes=max(int(max_minutes or 2), 1))
        stale = self.sudo().search([
            ('is_streaming', '=', True),
            ('create_date', '<', cutoff),
        ])
        closed_ids = []
        for msg in stale:
            try:
                msg.finalize_stream_audio()
            except Exception as e:
                _logger.warning('Stale PTT stream %s finalize failed: %s', msg.id, e)
            if not msg.audio_data:
                closed_ids.append(msg.id)
                msg.unlink()
                continue
            vals = {'is_streaming': False}
            if (msg.duration_seconds or 0) < 0.1:
                vals['duration_seconds'] = 0.1
            msg.write(vals)
            closed_ids.append(msg.id)
        if closed_ids:
            _logger.info('Closed %s stale PTT stream(s): %s', len(closed_ids), closed_ids)
        return True

    @api.model
    def cron_cleanup_stale_stream_temp_files(self):
        """Remove stale push-to-talk temp files left by interrupted sessions.

        Retention is controlled by ``guardpro.ptt_temp_retention_hours`` (default 24).
        """
        param = self.env['ir.config_parameter'].sudo().get_param(
            'guardpro.ptt_temp_retention_hours', '24'
        )
        try:
            retention_hours = max(int(param or 24), 1)
        except (TypeError, ValueError):
            retention_hours = 24

        self.cron_close_stale_streams()

        cutoff = fields.Datetime.now() - timedelta(hours=retention_hours)
        temp_dir = tempfile.gettempdir()
        prefix = 'guardpro_ptt_'
        suffix = '.bin'
        removed = 0

        # Skip temp files belonging to currently active streams.
        active_message_ids = set(
            self.sudo().search([('is_streaming', '=', True)]).ids
        )

        try:
            with os.scandir(temp_dir) as entries:
                for entry in entries:
                    if not entry.is_file():
                        continue
                    name = entry.name
                    if not (name.startswith(prefix) and name.endswith(suffix)):
                        continue

                    # Filename format: guardpro_ptt_<message_id>_<stream_id>.bin
                    try:
                        parts = name[:-len(suffix)].split('_')
                        message_id = int(parts[2])
                    except (ValueError, IndexError):
                        # Unknown shape; leave it untouched.
                        continue

                    if message_id in active_message_ids:
                        continue

                    mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                    if mtime <= cutoff:
                        try:
                            os.remove(entry.path)
                            removed += 1
                        except Exception as remove_err:
                            _logger.warning(
                                'GuardLink PTT temp cleanup: failed removing %s: %s',
                                entry.path,
                                remove_err,
                            )
        except Exception as scan_err:
            _logger.error('GuardLink PTT temp cleanup scan failed: %s', scan_err)
            return False

        if removed:
            _logger.info(
                'GuardLink PTT temp cleanup: removed %s stale file(s) older than %s hour(s)',
                removed,
                retention_hours,
            )
        return True

    def _broadcast_chunk(self, chunk_data):
        """Broadcast occupancy only. MediaRecorder fragments are not playable."""
        self.ensure_one()
        self._ptt_bus_send('push_to_talk_chunk', {
            'message_id': self.id,
            'stream_id': self.stream_id,
            'chunk_index': self.chunk_count,
            'sender_name': self.sender_display_name(),
            'channel_id': self.channel_id.id,
        })
