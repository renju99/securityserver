# -*- coding: utf-8 -*-
"""Client Site Model with Geofencing."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
import logging
from ..common import geo_utils

_logger = logging.getLogger(__name__)


class ClientSite(models.Model):
    """Client Site with GPS coordinates and geofencing."""

    _name = 'client.site'
    _description = 'Client Site Location'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # Basic Information
    name = fields.Char(
        string='Site Name',
        required=True,
        tracking=True,
        index=True
    )
    code = fields.Char(
        string='Site Code',
        required=True,
        copy=False,
        tracking=True,
        index=True
    )
    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        domain=[('is_company', '=', True)],
        tracking=True
    )
    manager_id = fields.Many2one(
        'res.partner',
        string='Site Manager',
        tracking=True,
        help='Site manager contact person'
    )
    
    # Location Details
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    state_id = fields.Many2one(
        'res.country.state',
        string='State'
    )
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one(
        'res.country',
        string='Country'
    )
    address = fields.Char(
        string='Full Address',
        compute='_compute_address',
        store=False
    )
    
    # GPS Coordinates
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7),
        required=True,
        tracking=True
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7),
        required=True,
        tracking=True
    )
    
    # Geofencing
    geofence_enabled = fields.Boolean(
        string='Enable Geofencing',
        default=True,
        tracking=True
    )
    geofence_type = fields.Selection([
        ('circle', 'Circle'),
        ('polygon', 'Polygon')
    ], string='Geofence Type', default='circle', required=True)
    
    geofence_radius = fields.Float(
        string='Geofence Radius (meters)',
        default=1000.0,
        help='Radius in meters for circular geofence'
    )
    geofence_polygon = fields.Text(
        string='Geofence Polygon',
        help='JSON array of lat/lng coordinates for polygon geofence'
    )
    
    # Dummy field for map widget (not stored, used to trigger map interface)
    geofence_map = fields.Char(
        string='Geofence Map',
        help='Interactive map for selecting geofence area - click "Mark Geofence on Map" button to open'
    )
    
    # Physical Verification (GPS Spoofing Prevention)
    require_physical_verification = fields.Boolean(
        string='Require Physical Verification',
        default=False,
        help='Require NFC/QR scan in addition to GPS for check-in (prevents GPS spoofing)'
    )
    verification_method = fields.Selection([
        ('nfc', 'NFC Tag Required'),
        ('qr', 'QR Code Required'),
        ('nfc_or_qr', 'NFC or QR Code'),
        ('photo', 'Photo Required'),
        ('any', 'Any Physical Proof')
    ], string='Verification Method', default='nfc_or_qr',
       help='Type of physical verification required for check-in')
    
    entrance_checkpoint_id = fields.Many2one(
        'checkpoint',
        string='Entrance Checkpoint',
        help='Main entrance checkpoint for mandatory check-in scan'
    )
    
    # Contact Information
    site_manager = fields.Char(
        string='Site Manager Name'
    )
    site_phone = fields.Char(
        string='Site Phone'
    )
    site_email = fields.Char(
        string='Site Email'
    )
    emergency_contact = fields.Char(
        string='Emergency Contact'
    )
    emergency_phone = fields.Char(
        string='Emergency Phone'
    )
    
    # Operational Details
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the site'
    )
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended')
    ], string='Status', default='active', required=True, tracking=True)
    
    site_type = fields.Selection([
        ('office', 'Office Building'),
        ('retail', 'Retail Store'),
        ('industrial', 'Industrial Facility'),
        ('warehouse', 'Warehouse'),
        ('healthcare', 'Healthcare Facility'),
        ('educational', 'Educational Institution'),
        ('residential', 'Residential Complex'),
        ('government', 'Government Facility'),
        ('other', 'Other')
    ], string='Site Type', default='other', tracking=True,
       help='Type of facility or building')
    
    contract_start = fields.Date(
        string='Contract Start Date',
        tracking=True
    )
    contract_end = fields.Date(
        string='Contract End Date',
        tracking=True
    )
    
    # Site Requirements
    guards_required = fields.Integer(
        string='Guards Required',
        default=1,
        help='Number of guards required per shift'
    )
    armed_required = fields.Boolean(
        string='Armed Guards Required',
        default=False
    )
    
    # Location Hierarchy
    building_ids = fields.One2many(
        'site.building',
        'site_id',
        string='Buildings'
    )

    # Shifts & Tours
    shift_ids = fields.One2many(
        'guard.shift',
        'site_id',
        string='Shifts'
    )
    tour_ids = fields.One2many(
        'security.tour',
        'site_id',
        string='Security Tours'
    )
    checkpoint_ids = fields.One2many(
        'checkpoint',
        'site_id',
        string='Checkpoints'
    )
    
    # Access Instructions
    access_instructions = fields.Text(
        string='Access Instructions',
        help='How to access the site'
    )
    parking_instructions = fields.Text(
        string='Parking Instructions'
    )
    special_instructions = fields.Text(
        string='Special Instructions',
        help='Any special requirements or procedures'
    )
    
    # Statistics
    total_shifts = fields.Integer(
        string='Total Shifts',
        compute='_compute_statistics',
        store=True
    )
    total_incidents = fields.Integer(
        string='Total Incidents',
        compute='_compute_statistics',
        store=True
    )
    active_guards = fields.Integer(
        string='Active Guards',
        compute='_compute_active_guards'
    )
    
    # Attachments
    site_map = fields.Binary(
        string='Site Map',
        attachment=True
    )
    site_photos = fields.Many2many(
        'ir.attachment',
        string='Site Photos'
    )
    
    # Notes
    notes = fields.Text(
        string='Internal Notes'
    )
    
    # UI Enhancement
    color = fields.Integer(
        string='Color Index',
        default=0,
        help='Color index for kanban view'
    )
    
    _sql_constraints = [
        ('code_unique', 'unique(code)',
         'Site code must be unique!'),
    ]

    @api.depends('shift_ids', 'incident_ids')
    def _compute_statistics(self):
        """Compute site statistics."""
        for record in self:
            record.total_shifts = len(record.shift_ids)
            record.total_incidents = len(record.incident_ids)

    incident_ids = fields.One2many(
        'incident.report',
        'site_id',
        string='Incidents'
    )

    def _compute_active_guards(self):
        """Count guards currently active at this site."""
        for record in self:
            record.active_guards = self.env['guard.profile'].search_count([
                ('current_site_id', '=', record.id),
                ('status', '=', 'active')
            ])

    @api.depends('street', 'street2', 'city', 'state_id', 'zip', 'country_id')
    def _compute_address(self):
        """Compute full formatted address."""
        for record in self:
            address_parts = []
            if record.street:
                address_parts.append(record.street)
            if record.street2:
                address_parts.append(record.street2)
            if record.city:
                address_parts.append(record.city)
            if record.state_id:
                address_parts.append(record.state_id.name)
            if record.zip:
                address_parts.append(record.zip)
            if record.country_id:
                address_parts.append(record.country_id.name)
            
            record.address = ', '.join(address_parts) if address_parts else ''

    @api.constrains('geofence_polygon')
    def _check_geofence_polygon(self):
        """Validate geofence polygon JSON format."""
        for record in self:
            if record.geofence_type == 'polygon' and record.geofence_polygon:
                try:
                    polygon = json.loads(record.geofence_polygon)
                    if not isinstance(polygon, list) or len(polygon) < 3:
                        raise ValidationError(_(
                            'Polygon must have at least 3 points!'
                        ))
                    for point in polygon:
                        if not (isinstance(point, dict) and
                                'lat' in point and 'lng' in point):
                            raise ValidationError(_(
                                'Each polygon point must have lat and lng!'
                            ))
                except json.JSONDecodeError:
                    raise ValidationError(_(
                        'Invalid JSON format for geofence polygon!'
                    ))

    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        """Validate GPS coordinates."""
        for record in self:
            if not (-90 <= record.latitude <= 90):
                raise ValidationError(_(
                    'Latitude must be between -90 and 90!'
                ))
            if not (-180 <= record.longitude <= 180):
                raise ValidationError(_(
                    'Longitude must be between -180 and 180!'
                ))

    @api.constrains('contract_start', 'contract_end')
    def _check_contract_dates(self):
        """Validate contract dates."""
        for record in self:
            if (record.contract_start and record.contract_end and
                    record.contract_end < record.contract_start):
                raise ValidationError(_(
                    'Contract end date must be after start date!'
                ))

    def action_view_shifts(self):
        """Open site's shift schedule."""
        self.ensure_one()
        return {
            'name': _('Shifts - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.shift',
            'view_mode': 'calendar,list,form',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id}
        }

    def action_view_checkpoints(self):
        """Open site's checkpoints."""
        self.ensure_one()
        return {
            'name': _('Checkpoints - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'checkpoint',
            'view_mode': 'list,form,map',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id}
        }

    def action_view_incidents(self):
        """Open site's incident reports."""
        self.ensure_one()
        return {
            'name': _('Incidents - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'incident.report',
            'view_mode': 'list,form',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id}
        }

    def action_view_tours(self):
        """Open site's security tours."""
        self.ensure_one()
        return {
            'name': _('Tours - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'security.tour',
            'view_mode': 'list,form',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id}
        }

    def action_open_geofence_map(self):
        """Open geofencing map page for this site."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/guardpro/site/%s/geofence' % self.id,
            'target': 'new',
        }

    def check_guard_in_geofence(self, latitude, longitude):
        """
        Check if given coordinates are within site geofence.
        
        Args:
            latitude (float): Guard's latitude
            longitude (float): Guard's longitude
            
        Returns:
            bool: True if within geofence, False otherwise
        """
        self.ensure_one()
        
        if not self.geofence_enabled:
            return True
            
        if self.geofence_type == 'circle':
            return self._check_circle_geofence(latitude, longitude)
        else:
            return self._check_polygon_geofence(latitude, longitude)

    def _check_circle_geofence(self, lat, lng):
        """Check if point is within circular geofence."""
        return geo_utils.check_point_in_circle(
            lat, lng,
            self.latitude, self.longitude,
            self.geofence_radius
        )

    def _check_polygon_geofence(self, lat, lng):
        """Check if point is within polygon geofence using ray casting."""
        if not self.geofence_polygon:
            return False
        
        return geo_utils.check_point_in_polygon(lat, lng, self.geofence_polygon)


