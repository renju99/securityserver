# -*- coding: utf-8 -*-
"""Live Guard Location Model for Real-Time Client Portal Tracking."""

from odoo import models, fields, api, _
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class GuardLocationLive(models.Model):
    """Current live location of guards - optimized for client portal real-time tracking."""
    
    _name = 'guard.location.live'
    _description = 'Guard Live Location'
    _order = 'last_update desc'
    _rec_name = 'guard_id'
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    # Current Location
    latitude = fields.Float(
        string='Latitude',
        required=True,
        digits=(10, 7)
    )
    
    longitude = fields.Float(
        string='Longitude',
        required=True,
        digits=(10, 7)
    )
    
    accuracy = fields.Float(
        string='Accuracy (meters)',
        help='GPS accuracy in meters'
    )
    
    altitude = fields.Float(
        string='Altitude (meters)'
    )
    
    speed = fields.Float(
        string='Speed (km/h)'
    )
    
    heading = fields.Float(
        string='Heading (degrees)',
        help='Direction of movement (0-360)'
    )
    
    # Timestamp
    last_update = fields.Datetime(
        string='Last Update',
        required=True,
        default=fields.Datetime.now,
        index=True
    )
    
    # Context
    site_id = fields.Many2one(
        'client.site',
        string='Current Site',
        index=True,
        ondelete='set null'
    )
    
    shift_id = fields.Many2one(
        'guard.shift',
        string='Current Shift',
        index=True,
        ondelete='set null'
    )
    
    # Status
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Guard is currently active and location is being tracked'
    )
    
    is_on_duty = fields.Boolean(
        string='On Duty',
        compute='_compute_on_duty_status',
        store=True
    )
    
    # Battery and device info
    battery_level = fields.Integer(
        string='Battery Level (%)',
        help='Device battery level'
    )
    
    device_info = fields.Char(
        string='Device Info',
        help='Device model and OS info'
    )
    
    # Visibility Control
    share_with_client = fields.Boolean(
        string='Share with Client',
        default=True,
        help='Share location with client in portal'
    )
    
    # Computed fields for portal display
    time_since_update = fields.Char(
        string='Time Since Update',
        compute='_compute_time_since_update'
    )
    
    is_recent = fields.Boolean(
        string='Recent Location',
        compute='_compute_is_recent',
        help='Location updated within last 5 minutes'
    )
    
    guard_name = fields.Char(
        related='guard_id.name',
        string='Guard Name',
        readonly=True,
        store=True
    )
    
    site_name = fields.Char(
        related='site_id.name',
        string='Site Name',
        readonly=True,
        store=True
    )
    
    @api.depends('shift_id', 'shift_id.status')
    def _compute_on_duty_status(self):
        """Check if guard is currently on duty."""
        for record in self:
            if record.shift_id:
                now = fields.Datetime.now()
                record.is_on_duty = (
                    record.shift_id.status == 'in_progress' and
                    record.shift_id.start_datetime <= now <= record.shift_id.end_datetime
                )
            else:
                record.is_on_duty = False
    
    @api.depends('last_update')
    def _compute_time_since_update(self):
        """Compute human-readable time since last update."""
        for record in self:
            if record.last_update:
                delta = fields.Datetime.now() - record.last_update
                
                if delta.total_seconds() < 60:
                    record.time_since_update = _('Just now')
                elif delta.total_seconds() < 3600:
                    minutes = int(delta.total_seconds() / 60)
                    record.time_since_update = _('%d minutes ago') % minutes
                elif delta.total_seconds() < 86400:
                    hours = int(delta.total_seconds() / 3600)
                    record.time_since_update = _('%d hours ago') % hours
                else:
                    days = delta.days
                    record.time_since_update = _('%d days ago') % days
            else:
                record.time_since_update = _('Never')
    
    @api.depends('last_update')
    def _compute_is_recent(self):
        """Check if location is recent (within 5 minutes)."""
        for record in self:
            if record.last_update:
                delta = fields.Datetime.now() - record.last_update
                record.is_recent = delta.total_seconds() < 300  # 5 minutes
            else:
                record.is_recent = False
    
    @api.model
    def update_guard_location(self, guard_id, latitude, longitude, **kwargs):
        """Update or create live location for a guard.
        
        Args:
            guard_id: ID of the guard
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            **kwargs: Additional location data (accuracy, speed, heading, etc.)
        
        Returns:
            Record ID
        """
        # Find existing record
        existing = self.search([('guard_id', '=', guard_id)], limit=1)
        
        # Prepare values
        vals = {
            'guard_id': guard_id,
            'latitude': latitude,
            'longitude': longitude,
            'last_update': fields.Datetime.now(),
            'accuracy': kwargs.get('accuracy'),
            'altitude': kwargs.get('altitude'),
            'speed': kwargs.get('speed'),
            'heading': kwargs.get('heading'),
            'battery_level': kwargs.get('battery_level'),
            'device_info': kwargs.get('device_info'),
            'site_id': kwargs.get('site_id'),
            'shift_id': kwargs.get('shift_id'),
            'is_active': True,
        }
        
        if existing:
            existing.write(vals)
            record = existing
        else:
            record = self.create(vals)
        
        # Also save to history
        self.env['guard.location.history'].create({
            'guard_id': guard_id,
            'latitude': latitude,
            'longitude': longitude,
            'accuracy': kwargs.get('accuracy'),
            'altitude': kwargs.get('altitude'),
            'speed': kwargs.get('speed'),
            'heading': kwargs.get('heading'),
            'battery_level': kwargs.get('battery_level'),
            'site_id': kwargs.get('site_id'),
            'shift_id': kwargs.get('shift_id'),
        })
        
        return record.id
    
    @api.model
    def get_active_guards_for_site(self, site_id):
        """Get all active guards currently at a site.
        
        Args:
            site_id: Site ID
            
        Returns:
            List of dicts with guard location data
        """
        records = self.search([
            ('site_id', '=', site_id),
            ('is_active', '=', True),
            ('share_with_client', '=', True)
        ])
        
        result = []
        for record in records:
            if record.is_recent:
                result.append({
                    'id': record.id,
                    'guard_id': record.guard_id.id,
                    'guard_name': record.guard_name,
                    'latitude': record.latitude,
                    'longitude': record.longitude,
                    'accuracy': record.accuracy,
                    'last_update': record.last_update.isoformat() if record.last_update else None,
                    'time_since_update': record.time_since_update,
                    'is_on_duty': record.is_on_duty,
                    'battery_level': record.battery_level,
                    'site_name': record.site_name,
                })
        
        return result
    
    @api.model
    def cleanup_stale_locations(self):
        """Mark locations as inactive if not updated in 30 minutes.
        
        Called by scheduled action.
        """
        threshold = fields.Datetime.now() - timedelta(minutes=30)
        
        stale = self.search([
            ('last_update', '<', threshold),
            ('is_active', '=', True)
        ])
        
        if stale:
            stale.write({'is_active': False})
            _logger.info('Marked %d guard locations as inactive', len(stale))
        
        return True


class GuardProfile(models.Model):
    """Extend guard profile with live location."""
    
    _inherit = 'guard.profile'
    
    live_location_id = fields.One2many(
        'guard.location.live',
        'guard_id',
        string='Live Location'
    )
    
    current_latitude = fields.Float(
        string='Current Latitude',
        compute='_compute_current_location',
        digits=(10, 7)
    )
    
    current_longitude = fields.Float(
        string='Current Longitude',
        compute='_compute_current_location',
        digits=(10, 7)
    )
    
    location_last_update = fields.Datetime(
        string='Location Last Update',
        compute='_compute_current_location'
    )
    
    location_sharing_enabled = fields.Boolean(
        string='Location Sharing Enabled',
        default=True,
        help='Allow sharing location with clients in portal'
    )
    
    @api.depends('live_location_id', 'live_location_id.latitude', 'live_location_id.longitude')
    def _compute_current_location(self):
        """Get current location from live location."""
        for record in self:
            live = record.live_location_id.filtered(lambda l: l.is_active)[:1]
            if live:
                record.current_latitude = live.latitude
                record.current_longitude = live.longitude
                record.location_last_update = live.last_update
            else:
                record.current_latitude = 0.0
                record.current_longitude = 0.0
                record.location_last_update = False

