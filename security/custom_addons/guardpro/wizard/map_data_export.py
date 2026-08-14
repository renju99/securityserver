# -*- coding: utf-8 -*-
"""Map Data Export Wizard."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
from datetime import datetime, timedelta
import logging
import csv
import io

_logger = logging.getLogger(__name__)


class MapDataExport(models.TransientModel):
    """Wizard to export map data to CSV/PDF."""

    _name = 'map.data.export.wizard'
    _description = 'Map Data Export Wizard'

    export_type = fields.Selection([
        ('current_locations', 'Current Guard Locations'),
        ('location_history', 'Location History'),
        ('geofences', 'Project Geofences'),
        ('patrol_routes', 'Patrol Routes')
    ], string='Export Type', required=True, default='current_locations')
    
    export_format = fields.Selection([
        ('csv', 'CSV'),
        ('pdf', 'PDF')
    ], string='Format', required=True, default='csv')
    
    date_from = fields.Datetime(
        string='From Date',
        default=lambda self: fields.Datetime.now() - timedelta(days=1)
    )
    date_to = fields.Datetime(
        string='To Date',
        default=fields.Datetime.now
    )
    
    guard_ids = fields.Many2many(
        'guard.profile',
        string='Guards',
        help='Leave empty to export all guards'
    )
    
    site_ids = fields.Many2many(
        'client.site',
        string='Sites',
        help='Leave empty to export all sites'
    )
    
    file_name = fields.Char(string='File Name', readonly=True)
    file_data = fields.Binary(string='File', readonly=True)
    
    def action_export(self):
        """Generate and download export file."""
        self.ensure_one()
        
        if self.export_format == 'csv':
            self._export_csv()
        else:
            self._export_pdf()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'map.data.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'show_download': True}
        }
    
    def _export_csv(self):
        """Export data to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        if self.export_type == 'current_locations':
            self._export_current_locations_csv(writer)
        elif self.export_type == 'location_history':
            self._export_location_history_csv(writer)
        elif self.export_type == 'geofences':
            self._export_geofences_csv(writer)
        elif self.export_type == 'patrol_routes':
            self._export_patrol_routes_csv(writer)
        
        # Save file
        csv_data = output.getvalue().encode('utf-8')
        self.file_data = base64.b64encode(csv_data)
        self.file_name = f'{self.export_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    def _export_current_locations_csv(self, writer):
        """Export current guard locations to CSV."""
        writer.writerow(['Guard Name', 'Badge Number', 'Latitude', 'Longitude', 
                        'Last Update', 'Site', 'Status', 'Phone'])
        
        domain = [
            ('status', '=', 'active'),
            ('current_latitude', '!=', False),
            ('current_longitude', '!=', False)
        ]
        
        if self.guard_ids:
            domain.append(('id', 'in', self.guard_ids.ids))
        
        if self.site_ids:
            domain.append(('current_site_id', 'in', self.site_ids.ids))
        
        guards = self.env['guard.profile'].search(domain)
        
        for guard in guards:
            writer.writerow([
                guard.name,
                guard.badge_number,
                guard.current_latitude,
                guard.current_longitude,
                guard.last_location_update.strftime('%Y-%m-%d %H:%M:%S') if guard.last_location_update else '',
                guard.current_site_id.name if guard.current_site_id else '',
                guard.status,
                guard.phone
            ])
    
    def _export_location_history_csv(self, writer):
        """Export location history to CSV."""
        writer.writerow(['Guard Name', 'Badge Number', 'Latitude', 'Longitude', 
                        'Timestamp', 'Site', 'Shift', 'Accuracy', 'Speed'])
        
        domain = [
            ('timestamp', '>=', self.date_from),
            ('timestamp', '<=', self.date_to)
        ]
        
        if self.guard_ids:
            domain.append(('guard_id', 'in', self.guard_ids.ids))
        
        if self.site_ids:
            domain.append(('site_id', 'in', self.site_ids.ids))
        
        locations = self.env['guard.location.history'].search(domain, order='timestamp asc')
        
        for loc in locations:
            writer.writerow([
                loc.guard_id.name,
                loc.guard_id.badge_number,
                loc.latitude,
                loc.longitude,
                loc.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                loc.site_id.name if loc.site_id else '',
                loc.shift_id.name if loc.shift_id else '',
                loc.accuracy or '',
                loc.speed or ''
            ])
    
    def _export_geofences_csv(self, writer):
        """Export project geofences to CSV."""
        writer.writerow(['Project Name', 'Project Code', 'Client', 'Latitude', 'Longitude',
                        'Geofence Type', 'Radius (m)', 'Status'])
        
        domain = [('geofence_enabled', '=', True)]
        
        if self.site_ids:
            domain.append(('id', 'in', self.site_ids.ids))
        
        sites = self.env['client.site'].search(domain)
        
        for site in sites:
            writer.writerow([
                site.name,
                site.code,
                site.client_id.name if site.client_id else '',
                site.latitude,
                site.longitude,
                site.geofence_type,
                site.geofence_radius if site.geofence_type == 'circle' else '',
                site.status
            ])
    
    def _export_patrol_routes_csv(self, writer):
        """Export patrol routes to CSV."""
        writer.writerow(['Tour Name', 'Site', 'Guard', 'Start Time', 'End Time',
                        'Status', 'Checkpoints Scanned', 'Total Checkpoints'])
        
        domain = [
            ('start_datetime', '>=', self.date_from),
            ('start_datetime', '<=', self.date_to)
        ]
        
        if self.guard_ids:
            domain.append(('guard_id', 'in', self.guard_ids.ids))
        
        if self.site_ids:
            domain.append(('tour_id.site_id', 'in', self.site_ids.ids))
        
        tour_logs = self.env['tour.log'].search(domain, order='start_datetime desc')
        
        for log in tour_logs:
            writer.writerow([
                log.tour_id.name,
                log.tour_id.site_id.name if log.tour_id.site_id else '',
                log.guard_id.name,
                log.start_datetime.strftime('%Y-%m-%d %H:%M:%S') if log.start_datetime else '',
                log.end_datetime.strftime('%Y-%m-%d %H:%M:%S') if log.end_datetime else '',
                log.status,
                log.checkpoints_scanned,
                log.total_checkpoints
            ])
    
    def _export_pdf(self):
        """Export data to PDF format."""
        raise UserError(_('PDF export is not implemented yet. Please use CSV export.'))

