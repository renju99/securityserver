# -*- coding: utf-8 -*-
"""REST API v1 for GuardPro."""

from odoo import http, fields, _
from odoo.http import request, Response
import json
import logging

_logger = logging.getLogger(__name__)


class GuardProAPIv1(http.Controller):
    """REST API endpoints for GuardPro."""
    
    def _authenticate_api_key(self):
        """Authenticate using API key from header."""
        api_key = request.httprequest.headers.get('X-API-Key')
        
        if not api_key:
            return None
        
        # Get IP address
        ip_address = request.httprequest.remote_addr
        
        # Validate key
        user = request.env['guardpro.api.key'].sudo().validate_api_key(api_key, ip_address)
        
        return user
    
    def _json_response(self, data=None, status=200, error=None):
        """Create JSON response."""
        if error:
            body = {'error': error, 'status': 'error'}
        else:
            body = {'data': data, 'status': 'success'}
        
        return Response(
            json.dumps(body),
            status=status,
            headers=[('Content-Type', 'application/json')]
        )
    
    # ========================
    # Guard Endpoints
    # ========================
    
    @http.route('/api/v1/guards', type='http', auth='none', methods=['GET'], csrf=False)
    def get_guards(self, **kwargs):
        """Get list of guards."""
        user = self._authenticate_api_key()
        if not user:
            return self._json_response(error='Invalid API key', status=401)
        
        try:
            guards = request.env['guard.profile'].sudo().search([
                ('status', '=', 'active')
            ])
            
            data = [{
                'id': guard.id,
                'name': guard.name,
                'badge_number': guard.badge_number,
                'status': guard.status,
                'phone': guard.phone,
                'email': guard.user_id.email if guard.user_id else None
            } for guard in guards]
            
            return self._json_response(data=data)
        except Exception as e:
            _logger.error('API error in get_guards: %s', str(e))
            return self._json_response(error=str(e), status=500)
    
    @http.route('/api/v1/guards/<int:guard_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_guard(self, guard_id, **kwargs):
        """Get single guard details."""
        user = self._authenticate_api_key()
        if not user:
            return self._json_response(error='Invalid API key', status=401)
        
        try:
            guard = request.env['guard.profile'].sudo().browse(guard_id)
            
            if not guard.exists():
                return self._json_response(error='Guard not found', status=404)
            
            data = {
                'id': guard.id,
                'name': guard.name,
                'badge_number': guard.badge_number,
                'status': guard.status,
                'phone': guard.phone,
                'mobile': guard.mobile,
                'email': guard.user_id.email if guard.user_id else None,
                'skills': [skill.name for skill in guard.skill_ids],
                'average_rating': guard.average_rating if hasattr(guard, 'average_rating') else 0
            }
            
            return self._json_response(data=data)
        except Exception as e:
            _logger.error('API error in get_guard: %s', str(e))
            return self._json_response(error=str(e), status=500)
    
    # ========================
    # Shift Endpoints
    # ========================
    
    @http.route('/api/v1/shifts', type='http', auth='none', methods=['GET'], csrf=False)
    def get_shifts(self, **kwargs):
        """Get list of shifts."""
        user = self._authenticate_api_key()
        if not user:
            return self._json_response(error='Invalid API key', status=401)
        
        try:
            # Parse query parameters
            limit = int(kwargs.get('limit', 100))
            offset = int(kwargs.get('offset', 0))
            status = kwargs.get('status')
            
            domain = []
            if status:
                domain.append(('status', '=', status))
            
            shifts = request.env['guard.shift'].sudo().search(
                domain,
                limit=limit,
                offset=offset,
                order='start_datetime desc'
            )
            
            data = [{
                'id': shift.id,
                'guard_id': shift.guard_id.id if shift.guard_id else None,
                'guard_name': shift.guard_id.name if shift.guard_id else None,
                'site_id': shift.site_id.id,
                'site_name': shift.site_id.name,
                'start_datetime': shift.start_datetime.isoformat() if shift.start_datetime else None,
                'end_datetime': shift.end_datetime.isoformat() if shift.end_datetime else None,
                'status': shift.status,
                'shift_type': shift.shift_type
            } for shift in shifts]
            
            return self._json_response(data=data)
        except Exception as e:
            _logger.error('API error in get_shifts: %s', str(e))
            return self._json_response(error=str(e), status=500)
    
    @http.route('/api/v1/shifts', type='json', auth='none', methods=['POST'], csrf=False)
    def create_shift(self, **kwargs):
        """Create a new shift."""
        user = self._authenticate_api_key()
        if not user:
            return {'error': 'Invalid API key', 'status': 'error'}
        
        try:
            # Check write permission
            api_key = request.env['guardpro.api.key'].sudo().search([
                ('user_id', '=', user.id),
                ('scope_create', '=', True)
            ], limit=1)
            
            if not api_key:
                return {'error': 'Insufficient permissions', 'status': 'error'}
            
            # Odoo 18: ``type='json'`` routes surface JSON-RPC ``params`` as
            # kwargs. ``request.jsonrequest`` was removed in Odoo 17.
            data = kwargs
            
            shift = request.env['guard.shift'].sudo().create({
                'guard_id': data.get('guard_id'),
                'site_id': data['site_id'],
                'start_datetime': data['start_datetime'],
                'end_datetime': data['end_datetime'],
                'shift_type': data.get('shift_type', 'day'),
                'status': 'scheduled'
            })
            
            return {
                'data': {'id': shift.id, 'name': shift.name},
                'status': 'success'
            }
        except Exception as e:
            _logger.error('API error in create_shift: %s', str(e))
            return {'error': str(e), 'status': 'error'}
    
    # ========================
    # Incident Endpoints
    # ========================
    
    @http.route('/api/v1/incidents', type='http', auth='none', methods=['GET'], csrf=False)
    def get_incidents(self, **kwargs):
        """Get list of incidents."""
        user = self._authenticate_api_key()
        if not user:
            return self._json_response(error='Invalid API key', status=401)
        
        try:
            limit = int(kwargs.get('limit', 100))
            severity = kwargs.get('severity')
            
            domain = []
            if severity:
                domain.append(('severity', '=', severity))
            
            incidents = request.env['incident.report'].sudo().search(
                domain,
                limit=limit,
                order='incident_datetime desc'
            )
            
            data = [{
                'id': incident.id,
                'name': incident.name,
                'incident_type': incident.category_id.name if incident.category_id else None,
                'severity': incident.severity,
                'status': incident.status,
                'site_id': incident.site_id.id,
                'site_name': incident.site_id.name,
                'guard_name': incident.guard_id.name if incident.guard_id else None,
                'incident_datetime': incident.incident_datetime.isoformat() if incident.incident_datetime else None
            } for incident in incidents]
            
            return self._json_response(data=data)
        except Exception as e:
            _logger.error('API error in get_incidents: %s', str(e))
            return self._json_response(error=str(e), status=500)
    
    # ========================
    # Attendance Endpoints
    # ========================
    
    @http.route('/api/v1/attendance/checkin', type='json', auth='none', methods=['POST'], csrf=False)
    def checkin(self, **kwargs):
        """Guard check-in via API."""
        user = self._authenticate_api_key()
        if not user:
            return {'error': 'Invalid API key', 'status': 'error'}
        
        try:
            data = kwargs
            
            attendance = request.env['guard.attendance'].sudo().create({
                'guard_id': data['guard_id'],
                'site_id': data['site_id'],
                'checkin_time': fields.Datetime.now(),
                'checkin_latitude': data.get('latitude'),
                'checkin_longitude': data.get('longitude'),
                'status': 'checked_in'
            })
            
            return {
                'data': {'id': attendance.id, 'checkin_time': attendance.checkin_time.isoformat()},
                'status': 'success'
            }
        except Exception as e:
            _logger.error('API error in checkin: %s', str(e))
            return {'error': str(e), 'status': 'error'}
    
    @http.route('/api/v1/attendance/checkout', type='json', auth='none', methods=['POST'], csrf=False)
    def checkout(self, **kwargs):
        """Guard check-out via API."""
        user = self._authenticate_api_key()
        if not user:
            return {'error': 'Invalid API key', 'status': 'error'}
        
        try:
            data = kwargs
            
            attendance = request.env['guard.attendance'].sudo().browse(data['attendance_id'])
            
            if not attendance.exists():
                return {'error': 'Attendance record not found', 'status': 'error'}
            
            attendance.write({
                'checkout_time': fields.Datetime.now(),
                'checkout_latitude': data.get('latitude'),
                'checkout_longitude': data.get('longitude'),
                'status': 'checked_out'
            })
            
            return {
                'data': {
                    'id': attendance.id,
                    'checkout_time': attendance.checkout_time.isoformat(),
                    'duration': attendance.duration
                },
                'status': 'success'
            }
        except Exception as e:
            _logger.error('API error in checkout: %s', str(e))
            return {'error': str(e), 'status': 'error'}
    
    # ========================
    # Health Check
    # ========================
    
    @http.route('/api/v1/health', type='http', auth='none', methods=['GET'], csrf=False)
    def health_check(self, **kwargs):
        """API health check endpoint."""
        return self._json_response(data={
            'status': 'healthy',
            'version': '1.0.0',
            'timestamp': fields.Datetime.now().isoformat()
        })

