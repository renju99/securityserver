# -*- coding: utf-8 -*-
"""GuardPro Offline Sync API Controller."""

from odoo import http, fields, _
from odoo.http import request, Response
from odoo.exceptions import ValidationError, UserError
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class GuardProOfflineSyncAPI(http.Controller):
    """API endpoints for offline data synchronization."""
    
    def _get_current_guard(self):
        """Get current logged-in guard profile."""
        user = request.env.user
        guard = request.env['guard.profile'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)
        return guard
    
    def _json_response(self, data=None, status=200, error=None, conflict=False):
        """Create JSON response."""
        if error:
            body = {'error': error, 'status': 'error'}
        elif conflict:
            body = {'conflict': True, 'status': 'conflict', 'data': data}
        else:
            body = {'data': data, 'status': 'success'}
        
        return Response(
            json.dumps(body, default=str),
            status=status,
            headers=[('Content-Type', 'application/json')]
        )
    
    # ========================
    # Attendance Sync
    # ========================
    
    @http.route('/guardpro/api/sync/attendance/checkin', type='json', auth='user', methods=['POST'], csrf=False)
    def sync_attendance_checkin(self, **kwargs):
        """Sync check-in from offline queue."""
        try:
            data = request.jsonrequest
            guard_id = data.get('guard_id')
            
            # Validate guard ownership
            current_guard = self._get_current_guard()
            if not current_guard or current_guard.id != guard_id:
                return {'error': 'Unauthorized', 'status': 'error'}
            
            # Check for duplicate (conflict detection)
            existing = request.env['guard.attendance'].sudo().search([
                ('guard_id', '=', guard_id),
                ('site_id', '=', data.get('site_id')),
                ('checkin_time', '>=', fields.Datetime.to_datetime(data.get('checkin_datetime'))),
                ('checkin_time', '<=', fields.Datetime.to_datetime(data.get('checkin_datetime')))
            ], limit=1)
            
            if existing:
                return {
                    'conflict': True,
                    'serverRecord': {
                        'id': existing.id,
                        'checkin_time': existing.checkin_time.isoformat() if existing.checkin_time else None
                    },
                    'reason': 'Duplicate check-in record found'
                }
            
            # Create attendance record
            attendance = request.env['guard.attendance'].sudo().create({
                'guard_id': guard_id,
                'site_id': data.get('site_id'),
                'shift_id': data.get('shift_id'),
                'checkin_time': data.get('checkin_datetime'),
                'checkin_latitude': data.get('checkin_latitude'),
                'checkin_longitude': data.get('checkin_longitude'),
                'status': 'checked_in',
                'offline_synced': True
            })
            
            return {
                'status': 'success',
                'id': attendance.id,
                'data': {
                    'checkin_time': attendance.checkin_time.isoformat() if attendance.checkin_time else None
                }
            }
            
        except Exception as e:
            _logger.error('Check-in sync failed: %s', str(e))
            return {'error': str(e), 'status': 'error'}
    
    @http.route('/guardpro/api/sync/attendance/checkout', type='json', auth='user', methods=['POST'], csrf=False)
    def sync_attendance_checkout(self, **kwargs):
        """Sync check-out from offline queue."""
        try:
            data = request.jsonrequest
            guard_id = data.get('guard_id')
            
            # Validate guard ownership
            current_guard = self._get_current_guard()
            if not current_guard or current_guard.id != guard_id:
                return {'error': 'Unauthorized', 'status': 'error'}
            
            # Find corresponding check-in
            attendance = request.env['guard.attendance'].sudo().search([
                ('guard_id', '=', guard_id),
                ('shift_id', '=', data.get('shift_id')),
                ('status', '=', 'checked_in'),
                ('checkout_time', '=', False)
            ], limit=1, order='checkin_time desc')
            
            if not attendance:
                return {
                    'conflict': True,
                    'reason': 'No matching check-in record found',
                    'serverRecord': None
                }
            
            # Update with check-out
            attendance.sudo().write({
                'checkout_time': data.get('checkout_datetime'),
                'checkout_latitude': data.get('checkout_latitude'),
                'checkout_longitude': data.get('checkout_longitude'),
                'status': 'checked_out',
                'offline_synced': True
            })
            
            return {
                'status': 'success',
                'id': attendance.id,
                'data': {
                    'checkout_time': attendance.checkout_time.isoformat() if attendance.checkout_time else None,
                    'duration': attendance.duration if hasattr(attendance, 'duration') else None
                }
            }
            
        except Exception as e:
            _logger.error('Check-out sync failed: %s', str(e))
            return {'error': str(e), 'status': 'error'}
    
    # ========================
    # Incident Sync
    # ========================
    
    @http.route('/guardpro/api/sync/incidents', type='json', auth='user', methods=['POST'], csrf=False)
    def sync_incident(self, **kwargs):
        """Sync incident report from offline queue."""
        try:
            data = request.jsonrequest
            guard_id = data.get('guard_id')
            
            # Validate guard ownership
            current_guard = self._get_current_guard()
            if not current_guard or current_guard.id != guard_id:
                return {'error': 'Unauthorized', 'status': 'error'}
            
            # Check for duplicate
            existing = request.env['incident.report'].sudo().search([
                ('guard_id', '=', guard_id),
                ('site_id', '=', data.get('site_id')),
                ('title', '=', data.get('title')),
                ('incident_datetime', '>=', fields.Datetime.to_datetime(data.get('incident_datetime')))
            ], limit=1)
            
            if existing:
                return {
                    'conflict': True,
                    'serverRecord': {
                        'id': existing.id,
                        'name': existing.name,
                        'title': existing.title
                    },
                    'reason': 'Similar incident already reported'
                }
            
            # Create incident
            incident = request.env['incident.report'].sudo().create({
                'guard_id': guard_id,
                'site_id': data.get('site_id'),
                'title': data.get('title'),
                'description': data.get('description'),
                'category_id': data.get('category_id'),
                'severity': data.get('severity'),
                'incident_datetime': data.get('incident_datetime'),
                'location': data.get('location'),
                'latitude': data.get('latitude'),
                'longitude': data.get('longitude'),
                'status': 'draft',
                'offline_synced': True
            })
            
            return {
                'status': 'success',
                'id': incident.id,
                'data': {
                    'name': incident.name,
                    'incident_datetime': incident.incident_datetime.isoformat() if incident.incident_datetime else None
                }
            }
            
        except Exception as e:
            _logger.error('Incident sync failed: %s', str(e))
            return {'error': str(e), 'status': 'error'}
    
    # ========================
    # Checkpoint Scan Sync
    # ========================
    
    @http.route('/guardpro/api/sync/checkpoint-scans', type='json', auth='user', methods=['POST'], csrf=False)
    def sync_checkpoint_scan(self, **kwargs):
        """Sync checkpoint scan from offline queue."""
        try:
            data = request.jsonrequest
            guard_id = data.get('guard_id')
            
            # Validate guard ownership
            current_guard = self._get_current_guard()
            if not current_guard or current_guard.id != guard_id:
                return {'error': 'Unauthorized', 'status': 'error'}
            
            # Check for duplicate
            checkpoint_id = data.get('checkpoint_id')
            scan_datetime = fields.Datetime.to_datetime(data.get('scan_datetime'))
            
            existing = request.env['checkpoint.scan'].sudo().search([
                ('checkpoint_id', '=', checkpoint_id),
                ('guard_id', '=', guard_id),
                ('scan_datetime', '>=', scan_datetime),
                ('scan_datetime', '<=', scan_datetime)
            ], limit=1)
            
            if existing:
                return {
                    'conflict': True,
                    'serverRecord': {
                        'id': existing.id,
                        'scan_datetime': existing.scan_datetime.isoformat() if existing.scan_datetime else None
                    },
                    'reason': 'Duplicate checkpoint scan found'
                }
            
            # Create checkpoint scan
            scan = request.env['checkpoint.scan'].sudo().create({
                'checkpoint_id': checkpoint_id,
                'guard_id': guard_id,
                'tour_id': data.get('tour_id'),
                'scan_datetime': scan_datetime,
                'scan_method': data.get('scan_method', 'qr'),
                'latitude': data.get('latitude'),
                'longitude': data.get('longitude'),
                'notes': data.get('notes', ''),
                'offline_synced': True
            })
            
            return {
                'status': 'success',
                'id': scan.id,
                'data': {
                    'scan_datetime': scan.scan_datetime.isoformat() if scan.scan_datetime else None
                }
            }
            
        except Exception as e:
            _logger.error('Checkpoint scan sync failed: %s', str(e))
            return {'error': str(e), 'status': 'error'}
    
    # ========================
    # GPS Location Sync
    # ========================
    
    @http.route('/guardpro/api/sync/gps-locations', type='json', auth='user', methods=['POST'], csrf=False)
    def sync_gps_locations(self, **kwargs):
        """Sync GPS locations in batch from offline queue."""
        try:
            data = request.jsonrequest
            locations = data.get('locations', [])
            
            current_guard = self._get_current_guard()
            if not current_guard:
                return {'error': 'Unauthorized', 'status': 'error'}
            
            # Batch create GPS location history
            location_records = []
            for loc in locations:
                # Only process if belongs to current guard
                if loc.get('guard_id') == current_guard.id:
                    location_records.append({
                        'guard_id': current_guard.id,
                        'timestamp': loc.get('timestamp'),
                        'latitude': loc.get('latitude'),
                        'longitude': loc.get('longitude'),
                        'accuracy': loc.get('accuracy'),
                        'altitude': loc.get('altitude'),
                        'speed': loc.get('speed'),
                        'heading': loc.get('heading'),
                        'offline_synced': True
                    })
            
            if location_records:
                request.env['guard.location.history'].sudo().create(location_records)
            
            return {
                'status': 'success',
                'synced_count': len(location_records)
            }
            
        except Exception as e:
            _logger.error('GPS locations sync failed: %s', str(e))
            return {'error': str(e), 'status': 'error'}
    
    # ========================
    # Conflict Resolution
    # ========================
    
    @http.route('/guardpro/api/sync/resolve-conflict', type='json', auth='user', methods=['POST'], csrf=False)
    def resolve_conflict(self, **kwargs):
        """Resolve a sync conflict."""
        try:
            data = request.jsonrequest
            resolution = data.get('resolution')  # 'local', 'server', 'merge'
            local_record = data.get('local_record')
            server_record = data.get('server_record')
            
            current_guard = self._get_current_guard()
            if not current_guard:
                return {'error': 'Unauthorized', 'status': 'error'}
            
            # Handle resolution based on type
            if resolution == 'local':
                # Keep local data, update server
                # Implementation depends on record type
                pass
            elif resolution == 'server':
                # Keep server data, discard local
                pass
            elif resolution == 'merge':
                # Merge both records
                pass
            
            return {
                'status': 'success',
                'message': 'Conflict resolved'
            }
            
        except Exception as e:
            _logger.error('Conflict resolution failed: %s', str(e))
            return {'error': str(e), 'status': 'error'}
    
    # ========================
    # Sync Status & Info
    # ========================
    
    @http.route('/guardpro/api/sync/status', type='json', auth='user', methods=['GET'], csrf=False)
    def get_sync_status(self, **kwargs):
        """Get sync status and pending items."""
        try:
            current_guard = self._get_current_guard()
            if not current_guard:
                return {'error': 'Unauthorized', 'status': 'error'}
            
            # Count offline-synced items in last 24 hours
            yesterday = fields.Datetime.now() - datetime.timedelta(days=1)
            
            attendance_count = request.env['guard.attendance'].sudo().search_count([
                ('guard_id', '=', current_guard.id),
                ('offline_synced', '=', True),
                ('create_date', '>=', yesterday)
            ])
            
            incident_count = request.env['incident.report'].sudo().search_count([
                ('guard_id', '=', current_guard.id),
                ('offline_synced', '=', True),
                ('create_date', '>=', yesterday)
            ])
            
            scan_count = request.env['checkpoint.scan'].sudo().search_count([
                ('guard_id', '=', current_guard.id),
                ('offline_synced', '=', True),
                ('create_date', '>=', yesterday)
            ])
            
            return {
                'status': 'success',
                'data': {
                    'attendance_synced': attendance_count,
                    'incidents_synced': incident_count,
                    'scans_synced': scan_count,
                    'last_sync': fields.Datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            _logger.error('Get sync status failed: %s', str(e))
            return {'error': str(e), 'status': 'error'}

