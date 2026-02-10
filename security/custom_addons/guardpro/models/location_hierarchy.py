# -*- coding: utf-8 -*-
"""Location Hierarchy Models - Buildings, Floors, Areas."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SiteBuilding(models.Model):
    """Buildings within client sites."""

    _name = 'site.building'
    _description = 'Site Building'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'site_id, name'

    # Basic Information
    name = fields.Char(
        string='Building Name',
        required=True,
        tracking=True,
        index=True
    )
    code = fields.Char(
        string='Building Code',
        required=True,
        copy=False,
        tracking=True,
        index=True
    )
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    # Location Details
    description = fields.Text(
        string='Description',
        help='Description of the building'
    )
    building_type = fields.Selection([
        ('office', 'Office Building'),
        ('residential', 'Residential Building'),
        ('retail', 'Retail Building'),
        ('industrial', 'Industrial Building'),
        ('warehouse', 'Warehouse'),
        ('parking', 'Parking Structure'),
        ('other', 'Other')
    ], string='Building Type', default='office', tracking=True)

    # Address within site
    street_address = fields.Char(
        string='Street Address',
        help='Specific address within the site'
    )

    # GPS coordinates (if different from site)
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7),
        help='Building-specific latitude (optional)'
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7),
        help='Building-specific longitude (optional)'
    )

    # Structural Information
    total_floors = fields.Integer(
        string='Total Floors',
        help='Total number of floors in the building'
    )
    basement_floors = fields.Integer(
        string='Basement Floors',
        default=0,
        help='Number of basement levels'
    )
    ground_floors = fields.Integer(
        string='Ground Floors',
        default=1,
        help='Number of ground level floors'
    )

    # Operational Details
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the building'
    )
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
        ('construction', 'Under Construction')
    ], string='Status', default='active', required=True, tracking=True)

    # Relationships
    floor_ids = fields.One2many(
        'building.floor',
        'building_id',
        string='Floors'
    )
    checkpoint_ids = fields.One2many(
        'checkpoint',
        'building_id',
        string='Checkpoints'
    )
    tour_ids = fields.Many2many(
        'security.tour',
        string='Tours',
        help='Tours that include this building'
    )

    # Statistics
    total_floors_count = fields.Integer(
        string='Total Floors Count',
        compute='_compute_statistics',
        store=True
    )
    total_checkpoints = fields.Integer(
        string='Total Checkpoints',
        compute='_compute_statistics',
        store=True
    )
    total_areas = fields.Integer(
        string='Total Areas',
        compute='_compute_statistics',
        store=True
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
         'Building code must be unique!'),
        ('name_site_unique', 'unique(name, site_id)',
         'Building name must be unique within a site!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Create buildings and auto-generate codes if not provided."""
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('site.building') or '/'
        return super().create(vals_list)

    @api.depends('floor_ids', 'checkpoint_ids', 'floor_ids.area_ids')
    def _compute_statistics(self):
        """Compute building statistics."""
        for record in self:
            record.total_floors_count = len(record.floor_ids)
            record.total_checkpoints = len(record.checkpoint_ids)
            record.total_areas = sum(len(floor.area_ids) for floor in record.floor_ids)

    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        """Validate GPS coordinates."""
        for record in self:
            if record.latitude and not (-90 <= record.latitude <= 90):
                raise ValidationError(_(
                    'Latitude must be between -90 and 90!'
                ))
            if record.longitude and not (-180 <= record.longitude <= 180):
                raise ValidationError(_(
                    'Longitude must be between -180 and 180!'
                ))

    def action_view_floors(self):
        """Open building's floors."""
        self.ensure_one()
        return {
            'name': _('Floors - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'building.floor',
            'view_mode': 'list,form',
            'domain': [('building_id', '=', self.id)],
            'context': {'default_building_id': self.id}
        }

    def action_view_checkpoints(self):
        """Open building's checkpoints."""
        self.ensure_one()
        return {
            'name': _('Checkpoints - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'checkpoint',
            'view_mode': 'list,form',
            'domain': [('building_id', '=', self.id)],
            'context': {'default_building_id': self.id, 'default_site_id': self.site_id.id}
        }


class BuildingFloor(models.Model):
    """Floors within buildings."""

    _name = 'building.floor'
    _description = 'Building Floor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'building_id, floor_number'

    # Basic Information
    name = fields.Char(
        string='Floor Name',
        required=True,
        tracking=True,
        index=True
    )
    code = fields.Char(
        string='Floor Code',
        required=True,
        copy=False,
        tracking=True,
        index=True
    )
    building_id = fields.Many2one(
        'site.building',
        string='Building',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        related='building_id.site_id',
        store=True,
        readonly=True
    )

    # Floor Details
    description = fields.Text(
        string='Description'
    )
    floor_number = fields.Integer(
        string='Floor Number',
        help='Floor number (negative for basement, 0 for ground, positive for upper floors)',
        tracking=True
    )
    floor_type = fields.Selection([
        ('basement', 'Basement'),
        ('ground', 'Ground Floor'),
        ('standard', 'Standard Floor'),
        ('penthouse', 'Penthouse'),
        ('roof', 'Roof'),
        ('mezzanine', 'Mezzanine'),
        ('parking', 'Parking Level')
    ], string='Floor Type', compute='_compute_floor_type', store=True)

    # Operational Details
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the floor'
    )
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
        ('construction', 'Under Construction')
    ], string='Status', default='active', required=True, tracking=True)

    # Relationships
    area_ids = fields.One2many(
        'floor.area',
        'floor_id',
        string='Areas/Rooms'
    )
    checkpoint_ids = fields.One2many(
        'checkpoint',
        'floor_id',
        string='Checkpoints'
    )

    # Statistics
    total_areas = fields.Integer(
        string='Total Areas',
        compute='_compute_statistics',
        store=True
    )
    total_checkpoints = fields.Integer(
        string='Total Checkpoints',
        compute='_compute_statistics',
        store=True
    )

    # Notes
    notes = fields.Text(
        string='Internal Notes'
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)',
         'Floor code must be unique!'),
        ('floor_building_unique', 'unique(floor_number, building_id)',
         'Floor number must be unique within a building!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Create floors and auto-generate codes if not provided."""
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('building.floor') or '/'
        return super().create(vals_list)

    @api.depends('floor_number')
    def _compute_floor_type(self):
        """Compute floor type based on floor number."""
        for record in self:
            if record.floor_number < 0:
                record.floor_type = 'basement'
            elif record.floor_number == 0:
                record.floor_type = 'ground'
            elif record.floor_number == 999:  # Special case for roof
                record.floor_type = 'roof'
            else:
                record.floor_type = 'standard'

    @api.depends('area_ids', 'checkpoint_ids')
    def _compute_statistics(self):
        """Compute floor statistics."""
        for record in self:
            record.total_areas = len(record.area_ids)
            record.total_checkpoints = len(record.checkpoint_ids)

    def action_view_areas(self):
        """Open floor's areas."""
        self.ensure_one()
        return {
            'name': _('Areas - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'floor.area',
            'view_mode': 'list,form',
            'domain': [('floor_id', '=', self.id)],
            'context': {'default_floor_id': self.id}
        }

    def action_view_checkpoints(self):
        """Open floor's checkpoints."""
        self.ensure_one()
        return {
            'name': _('Checkpoints - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'checkpoint',
            'view_mode': 'list,form',
            'domain': [('floor_id', '=', self.id)],
            'context': {'default_floor_id': self.id, 'default_building_id': self.building_id.id, 'default_site_id': self.site_id.id}
        }


class FloorArea(models.Model):
    """Areas/Rooms within floors."""

    _name = 'floor.area'
    _description = 'Floor Area/Room'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'floor_id, name'

    # Basic Information
    name = fields.Char(
        string='Area/Room Name',
        required=True,
        tracking=True,
        index=True
    )
    code = fields.Char(
        string='Area Code',
        required=True,
        copy=False,
        tracking=True,
        index=True
    )
    floor_id = fields.Many2one(
        'building.floor',
        string='Floor',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    building_id = fields.Many2one(
        'site.building',
        string='Building',
        related='floor_id.building_id',
        store=True,
        readonly=True
    )
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        related='floor_id.site_id',
        store=True,
        readonly=True
    )

    # Area Details
    description = fields.Text(
        string='Description'
    )
    area_type = fields.Selection([
        ('office', 'Office'),
        ('meeting_room', 'Meeting Room'),
        ('conference_room', 'Conference Room'),
        ('lobby', 'Lobby/Reception'),
        ('corridor', 'Corridor'),
        ('stairwell', 'Stairwell'),
        ('elevator', 'Elevator'),
        ('restroom', 'Restroom'),
        ('break_room', 'Break Room'),
        ('server_room', 'Server Room'),
        ('storage', 'Storage Room'),
        ('utility', 'Utility Room'),
        ('parking_area', 'Parking Area'),
        ('loading_dock', 'Loading Dock'),
        ('other', 'Other')
    ], string='Area Type', default='office', tracking=True)

    # Physical Details
    area_size = fields.Float(
        string='Area Size (sq m)',
        help='Size of the area in square meters'
    )

    # Operational Details
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the area'
    )
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
        ('construction', 'Under Construction'),
        ('closed', 'Closed')
    ], string='Status', default='active', required=True, tracking=True)

    # Relationships
    checkpoint_ids = fields.One2many(
        'checkpoint',
        'area_id',
        string='Checkpoints'
    )

    # Statistics
    total_checkpoints = fields.Integer(
        string='Total Checkpoints',
        compute='_compute_statistics',
        store=True
    )

    # Access Control
    access_level = fields.Selection([
        ('public', 'Public Access'),
        ('restricted', 'Restricted Access'),
        ('secure', 'Secure Area'),
        ('high_security', 'High Security')
    ], string='Access Level', default='public', tracking=True)

    # Notes
    notes = fields.Text(
        string='Internal Notes'
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)',
         'Area code must be unique!'),
        ('name_floor_unique', 'unique(name, floor_id)',
         'Area name must be unique within a floor!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Create areas and auto-generate codes if not provided."""
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('floor.area') or '/'
        return super().create(vals_list)

    @api.depends('checkpoint_ids')
    def _compute_statistics(self):
        """Compute area statistics."""
        for record in self:
            record.total_checkpoints = len(record.checkpoint_ids)

    def action_view_checkpoints(self):
        """Open area's checkpoints."""
        self.ensure_one()
        return {
            'name': _('Checkpoints - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'checkpoint',
            'view_mode': 'list,form',
            'domain': [('area_id', '=', self.id)],
            'context': {'default_area_id': self.id, 'default_floor_id': self.floor_id.id, 'default_building_id': self.building_id.id, 'default_site_id': self.site_id.id}
        }
