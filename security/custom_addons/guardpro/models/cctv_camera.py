# -*- coding: utf-8 -*-
"""CCTV Camera Model."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class CCTVCamera(models.Model):
    """CCTV Camera for monitoring sites."""

    _name = 'cctv.camera'
    _description = 'CCTV Camera'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # Basic Information
    name = fields.Char(
        string='Camera Name',
        required=True,
        tracking=True,
        index=True,
        help='Name or identifier for this camera'
    )
    code = fields.Char(
        string='Camera Code',
        required=True,
        copy=False,
        tracking=True,
        index=True,
        help='Unique code for this camera'
    )
    
    # Site Association
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True,
        tracking=True,
        ondelete='cascade',
        help='Site where this camera is located'
    )
    checkpoint_id = fields.Many2one(
        'checkpoint',
        string='Checkpoint',
        tracking=True,
        domain="[('site_id', '=', site_id)]",
        help='Optional checkpoint associated with this camera'
    )
    
    # Camera Details
    camera_type = fields.Selection([
        ('fixed', 'Fixed Camera'),
        ('ptz', 'PTZ Camera'),
        ('dome', 'Dome Camera'),
        ('bullet', 'Bullet Camera'),
        ('thermal', 'Thermal Camera'),
        ('lpr', 'License Plate Recognition'),
        ('other', 'Other')
    ], string='Camera Type', default='fixed', required=True, tracking=True)
    
    location_description = fields.Text(
        string='Location Description',
        help='Detailed description of camera location (e.g., "Main entrance, facing north")'
    )
    
    # Streaming Configuration
    stream_url = fields.Char(
        string='Stream URL',
        required=True,
        tracking=True,
        help='URL for camera stream (RTSP, HTTP, HLS, or WebRTC). '
             'Examples: rtsp://ip:port/path, http://ip:port/stream, or https://example.com/hls/stream.m3u8'
    )
    stream_type = fields.Selection([
        ('rtsp', 'RTSP'),
        ('http', 'HTTP/HTTPS'),
        ('hls', 'HLS (m3u8)'),
        ('webrtc', 'WebRTC'),
        ('iframe', 'iFrame Embed'),
        ('other', 'Other')
    ], string='Stream Type', default='http', required=True, tracking=True,
       help='Type of video stream protocol')
    
    # Authentication
    username = fields.Char(
        string='Username',
        help='Username for camera authentication (if required)'
    )
    password = fields.Char(
        string='Password',
        help='Password for camera authentication (if required)'
    )
    
    # Status
    status = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('maintenance', 'Maintenance'),
        ('error', 'Error')
    ], string='Status', default='online', required=True, tracking=True)
    
    is_active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='Whether this camera is currently active and should be displayed'
    )
    
    # Additional Info
    ip_address = fields.Char(
        string='IP Address',
        tracking=True,
        help='Camera IP address'
    )
    port = fields.Integer(
        string='Port',
        default=80,
        help='Camera port number'
    )
    manufacturer = fields.Char(
        string='Manufacturer',
        help='Camera manufacturer (e.g., Hikvision, Dahua, Axis)'
    )
    model = fields.Char(
        string='Model',
        help='Camera model number'
    )
    
    # Notes
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this camera'
    )
    
    # Constraints
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Camera code must be unique!'),
    ]
    
    @api.constrains('code')
    def _check_code(self):
        """Ensure camera code is unique."""
        for record in self:
            if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]):
                raise ValidationError(_('Camera code must be unique!'))
    
    @api.model
    def _get_stream_url_with_auth(self, camera):
        """Get stream URL with embedded authentication if needed.
        
        Note: For security, consider using a proxy endpoint that handles
        authentication server-side rather than embedding credentials in URLs.
        """
        if camera.stream_type == 'rtsp' and camera.username and camera.password:
            # RTSP URL with authentication
            url = camera.stream_url
            if '@' not in url:  # Only add auth if not already present
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(url)
                netloc = f"{camera.username}:{camera.password}@{parsed.netloc}"
                new_parsed = parsed._replace(netloc=netloc)
                return urlunparse(new_parsed)
        return camera.stream_url
    
    def name_get(self):
        """Return display name with site."""
        result = []
        for record in self:
            name = record.name
            if record.site_id:
                name = f"{name} ({record.site_id.name})"
            result.append((record.id, name))
        return result
    
    def action_play_stream(self):
        """Live CCTV viewing is not exposed in the web UI."""
        self.ensure_one()
        raise UserError(_('CCTV monitoring is not available.'))