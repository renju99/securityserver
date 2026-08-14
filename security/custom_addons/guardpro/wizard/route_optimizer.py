# -*- coding: utf-8 -*-
"""Route Optimization Wizard for Guard Patrols."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import math
import logging

_logger = logging.getLogger(__name__)


class RouteOptimizer(models.TransientModel):
    """Wizard to optimize patrol routes for guards."""

    _name = 'route.optimizer.wizard'
    _description = 'Route Optimization Wizard'

    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True,
        help='Site for which to optimize the patrol route'
    )
    checkpoint_ids = fields.Many2many(
        'checkpoint',
        string='Checkpoints',
        help='Checkpoints to include in the route'
    )
    start_location = fields.Selection([
        ('site', 'Site Center'),
        ('first_checkpoint', 'First Checkpoint'),
        ('custom', 'Custom Location')
    ], string='Start Location', default='site', required=True)
    custom_start_lat = fields.Float(string='Custom Start Latitude', digits=(10, 7))
    custom_start_lng = fields.Float(string='Custom Start Longitude', digits=(10, 7))
    
    return_to_start = fields.Boolean(
        string='Return to Start',
        default=True,
        help='Whether the route should end at the starting point'
    )
    
    optimized_route = fields.Text(
        string='Optimized Route',
        readonly=True,
        help='JSON representation of the optimized route'
    )
    total_distance = fields.Float(
        string='Total Distance (km)',
        readonly=True,
        help='Total distance of the optimized route'
    )
    
    @api.onchange('site_id')
    def _onchange_site_id(self):
        """Update checkpoint domain when site changes."""
        if self.site_id:
            # Get checkpoints for this site
            checkpoints = self.env['checkpoint'].search([
                ('site_id', '=', self.site_id.id)
            ])
            self.checkpoint_ids = checkpoints

    def action_optimize_route(self):
        """Calculate optimal route using nearest neighbor algorithm."""
        self.ensure_one()
        
        if not self.checkpoint_ids:
            raise UserError(_('Please select at least one checkpoint.'))
        
        # Get start location
        if self.start_location == 'site':
            start_point = {
                'lat': self.site_id.latitude,
                'lng': self.site_id.longitude,
                'name': self.site_id.name
            }
        elif self.start_location == 'custom':
            if not self.custom_start_lat or not self.custom_start_lng:
                raise UserError(_('Please provide custom start coordinates.'))
            start_point = {
                'lat': self.custom_start_lat,
                'lng': self.custom_start_lng,
                'name': 'Custom Start'
            }
        else:  # first_checkpoint
            first_cp = self.checkpoint_ids[0]
            start_point = {
                'lat': first_cp.latitude,
                'lng': first_cp.longitude,
                'name': first_cp.name
            }
        
        # Convert checkpoints to points
        points = [{
            'id': cp.id,
            'lat': cp.latitude,
            'lng': cp.longitude,
            'name': cp.name,
            'code': cp.code
        } for cp in self.checkpoint_ids]
        
        # Calculate optimal route using nearest neighbor
        route, total_distance = self._nearest_neighbor_route(start_point, points, self.return_to_start)
        
        # Save results
        import json
        self.optimized_route = json.dumps(route, indent=2)
        self.total_distance = total_distance
        
        # Show result in a wizard
        return {
            'name': _('Optimized Route'),
            'type': 'ir.actions.act_window',
            'res_model': 'route.optimizer.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'show_route': True}
        }
    
    def _nearest_neighbor_route(self, start_point, points, return_to_start=True):
        """Calculate route using nearest neighbor algorithm.
        
        Args:
            start_point: Starting location dict with lat/lng
            points: List of checkpoint dicts with lat/lng
            return_to_start: Whether to return to start point
            
        Returns:
            Tuple of (route_list, total_distance)
        """
        route = [start_point]
        unvisited = points.copy()
        current = start_point
        total_distance = 0
        
        while unvisited:
            # Find nearest unvisited checkpoint
            nearest = min(unvisited, key=lambda p: self._calculate_distance(
                current['lat'], current['lng'],
                p['lat'], p['lng']
            ))
            
            distance = self._calculate_distance(
                current['lat'], current['lng'],
                nearest['lat'], nearest['lng']
            )
            
            route.append(nearest)
            total_distance += distance
            unvisited.remove(nearest)
            current = nearest
        
        # Return to start if requested
        if return_to_start and points:
            distance = self._calculate_distance(
                current['lat'], current['lng'],
                start_point['lat'], start_point['lng']
            )
            route.append(start_point)
            total_distance += distance
        
        return route, total_distance
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula.
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in kilometers
        """
        # Radius of Earth in kilometers
        R = 6371.0
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        distance = R * c
        
        return distance
    
    def action_show_route_on_map(self):
        """Open map view with optimized route."""
        self.ensure_one()
        
        if not self.optimized_route:
            raise UserError(_('Please optimize the route first.'))
        
        # Return action to open the route map in a new window
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        map_url = f"{base_url}/guardpro/route/map/{self.id}"
        
        return {
            'type': 'ir.actions.act_url',
            'url': map_url,
            'target': 'new',
        }

