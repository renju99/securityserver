# -*- coding: utf-8 -*-
"""Guard Location History Model.

Stores historical location data for guards to enable:
- Path tracking over time
- Movement analysis
- Historical playback
- Coverage reports
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class GuardLocationHistory(models.Model):
    """Historical location tracking for security guards."""

    _name = 'guard.location.history'
    _description = 'Guard Location History'
    _order = 'timestamp desc'
    _rec_name = 'guard_id'

    # Guard Reference
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade',
        index=True,
        help='The guard whose location is being tracked'
    )
    
    # Location Data
    latitude = fields.Float(
        string='Latitude',
        required=True,
        digits=(10, 7),
        help='Latitude coordinate (WGS84)'
    )
    longitude = fields.Float(
        string='Longitude',
        required=True,
        digits=(10, 7),
        help='Longitude coordinate (WGS84)'
    )
    accuracy = fields.Float(
        string='Accuracy (meters)',
        help='GPS accuracy in meters'
    )
    altitude = fields.Float(
        string='Altitude (meters)',
        help='Altitude above sea level'
    )
    speed = fields.Float(
        string='Speed (km/h)',
        help='Speed at time of recording'
    )
    heading = fields.Float(
        string='Heading (degrees)',
        help='Direction of movement (0-360 degrees)'
    )
    
    # Timestamp
    timestamp = fields.Datetime(
        string='Timestamp',
        required=True,
        default=fields.Datetime.now,
        index=True,
        help='When this location was recorded'
    )
    
    # Context Data
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        index=True,
        ondelete='set null',
        help='Site the guard was assigned to at this time'
    )
    shift_id = fields.Many2one(
        'guard.shift',
        string='Shift',
        index=True,
        ondelete='set null',
        help='Shift during which this location was recorded'
    )
    tour_log_id = fields.Many2one(
        'tour.log',
        string='Tour Log',
        index=True,
        help='Tour log associated with this location'
    )
    
    # Metadata
    battery_level = fields.Integer(
        string='Battery Level (%)',
        help='Device battery level at time of recording'
    )
    is_manual = fields.Boolean(
        string='Manual Update',
        default=False,
        help='Whether this was a manual location update by the guard'
    )
    notes = fields.Text(
        string='Notes',
        help='Additional context or notes'
    )
    
    # Archiving
    is_archived = fields.Boolean(
        string='Archived',
        default=False,
        index=True,
        help='Archived location history records are older than retention period'
    )
    archived_date = fields.Datetime(
        string='Archived Date',
        readonly=True,
        help='Date when this record was archived'
    )
    
    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        """Validate latitude and longitude ranges."""
        for record in self:
            if not (-90 <= record.latitude <= 90):
                raise ValidationError(_('Latitude must be between -90 and 90 degrees.'))
            if not (-180 <= record.longitude <= 180):
                raise ValidationError(_('Longitude must be between -180 and 180 degrees.'))
    
    @api.model
    def create_location_point(self, guard_id, latitude, longitude, **kwargs):
        """Create a location history point.
        
        Args:
            guard_id: ID of the guard
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            **kwargs: Additional optional fields
            
        Returns:
            Created location history record
        """
        values = {
            'guard_id': guard_id,
            'latitude': latitude,
            'longitude': longitude,
        }
        values.update(kwargs)
        return self.create(values)
    
    @api.model
    def cleanup_old_records(self):
        """Archive location records older than retention period.
        
        Called by scheduled action daily at 2 AM.
        Archives location history older than configured retention period (30 days).
        Archived records are preserved but excluded from normal queries.
        """
        from datetime import datetime, timedelta
        
        # Get retention period from system parameters (default: 30 days for archiving)
        retention_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'guardpro.location_history_retention', 30))
        
        cutoff_date = fields.Datetime.now() - timedelta(days=retention_days)
        
        # Find old records that are not already archived
        old_records = self.search([
            ('timestamp', '<', cutoff_date),
            ('is_archived', '=', False)
        ])
        
        record_count = len(old_records)
        
        if record_count > 0:
            _logger.info(
                'Archiving %d location history records older than %d days (before %s)',
                record_count, retention_days, cutoff_date
            )
            
            # Archive old records instead of deleting them
            archive_date = fields.Datetime.now()
            old_records.write({
                'is_archived': True,
                'archived_date': archive_date
            })
            
            _logger.info('Successfully archived %d location history records', record_count)
        else:
            _logger.debug('No old location history records to archive')
        
        return True
    
    @api.model
    def get_guard_path(self, guard_id, start_datetime=None, end_datetime=None, limit=1000, include_archived=False):
        """Get historical path for a guard.
        
        Args:
            guard_id: ID of the guard
            start_datetime: Start of time range (datetime string or object)
            end_datetime: End of time range (datetime string or object)
            limit: Maximum number of points to return
            include_archived: If True, includes archived records (default: False)
            
        Returns:
            List of location points ordered by timestamp
        """
        domain = [('guard_id', '=', guard_id)]
        
        # Exclude archived records by default
        if not include_archived:
            domain.append(('is_archived', '=', False))
        
        if start_datetime:
            domain.append(('timestamp', '>=', start_datetime))
        if end_datetime:
            domain.append(('timestamp', '<=', end_datetime))
        
        locations = self.search(domain, limit=limit, order='timestamp asc')
        
        return [{
            'id': loc.id,
            'latitude': loc.latitude,
            'longitude': loc.longitude,
            'timestamp': loc.timestamp.isoformat() if loc.timestamp else None,
            'site_id': loc.site_id.id if loc.site_id else None,
            'site_name': loc.site_id.name if loc.site_id else None,
            'accuracy': loc.accuracy,
            'speed': loc.speed,
            'heading': loc.heading,
        } for loc in locations]
    
    @api.model
    def cleanup_old_locations(self, days=30):
        """Archive location history older than specified days.
        
        Args:
            days: Number of days to keep before archiving (default 30)
            
        Returns:
            Number of records archived
        """
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        old_records = self.search([
            ('timestamp', '<', cutoff_date),
            ('is_archived', '=', False)
        ])
        count = len(old_records)
        if count > 0:
            archive_date = fields.Datetime.now()
            old_records.write({
                'is_archived': True,
                'archived_date': archive_date
            })
        _logger.info(f"Archived {count} location history records older than {days} days")
        return count
    
    def init(self):
        """Create database indexes for performance optimization."""
        # Composite index for common queries (guard + timestamp)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS guard_location_guard_timestamp_idx 
            ON guard_location_history (guard_id, timestamp DESC);
        """)
        
        # Index for site-based queries
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS guard_location_site_timestamp_idx 
            ON guard_location_history (site_id, timestamp DESC) 
            WHERE site_id IS NOT NULL;
        """)
        
        # Index for shift-based queries
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS guard_location_shift_idx 
            ON guard_location_history (shift_id, timestamp DESC) 
            WHERE shift_id IS NOT NULL;
        """)
        
        # Spatial index for geospatial queries (if PostGIS/earthdistance is available)
        # Use savepoint to prevent transaction abortion on error
        try:
            self.env.cr.execute("SAVEPOINT before_spatial_index")
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS guard_location_spatial_idx 
                ON guard_location_history 
                USING GIST (ll_to_earth(latitude, longitude));
            """)
            self.env.cr.execute("RELEASE SAVEPOINT before_spatial_index")
        except Exception as e:
            self.env.cr.execute("ROLLBACK TO SAVEPOINT before_spatial_index")
            _logger.info('Spatial index not created (earthdistance extension not available): %s', str(e))

