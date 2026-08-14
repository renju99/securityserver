# -*- coding: utf-8 -*-
"""REST API v1 for GuardLink."""

from odoo import http, fields, _
from odoo.http import request, Response
import json
import logging

_logger = logging.getLogger(__name__)


class GuardLinkAPIv1(http.Controller):
    """REST API endpoints for GuardLink."""

    def _authenticate_api_key(self):
        """Authenticate using API key from header.

        Returns the ``res.users`` bound to the key, or ``None``.
        """
        api_key = request.httprequest.headers.get('X-API-Key')

        if not api_key:
            return None

        ip_address = request.httprequest.remote_addr
        user = request.env['guardpro.api.key'].sudo().validate_api_key(api_key, ip_address)
        return user

    def _is_api_admin(self, user):
        """True when the API key user may access all sites."""
        return user and user.has_group('guardpro.group_guardpro_admin')

    def _allowed_site_ids(self, user):
        """Site IDs the API key user may access.

        Admins: unrestricted (returns ``None``).
        Non-admins with no sites: empty frozenset (deny all).
        """
        if self._is_api_admin(user):
            return None
        return frozenset(user.site_ids.ids)

    def _site_domain(self, user, site_field='site_id'):
        """Domain fragment restricting to the caller's assigned projects."""
        allowed = self._allowed_site_ids(user)
        if allowed is None:
            return []
        return [(site_field, 'in', list(allowed))]

    def _guard_domain(self, user):
        """Domain restricting guards to those sharing a site with the caller."""
        allowed = self._allowed_site_ids(user)
        if allowed is None:
            return []
        if not allowed:
            return [('id', '=', False)]
        return [('site_ids', 'in', list(allowed))]

    def _site_allowed(self, user, site_id):
        """Return True if ``site_id`` is in the caller's permitted sites."""
        if not site_id:
            return False
        allowed = self._allowed_site_ids(user)
        if allowed is None:
            return True
        return site_id in allowed

    def _guard_allowed(self, user, guard):
        """Return True if ``guard`` overlaps the caller's assigned projects."""
        if not guard or not guard.exists():
            return False
        allowed = self._allowed_site_ids(user)
        if allowed is None:
            return True
        if not allowed:
            return False
        return bool(set(guard.site_ids.ids) & allowed)

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
        """Get list of guards (scoped to API key user's sites)."""
        user = self._authenticate_api_key()
        if not user:
            return self._json_response(error='Invalid API key', status=401)

        try:
            domain = [('status', '=', 'active')] + self._guard_domain(user)
            guards = request.env['guard.profile'].sudo().search(domain)

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
        """Get single guard details (scoped to API key user's sites)."""
        user = self._authenticate_api_key()
        if not user:
            return self._json_response(error='Invalid API key', status=401)

        try:
            guard = request.env['guard.profile'].sudo().browse(guard_id)

            if not guard.exists() or not self._guard_allowed(user, guard):
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
        """Get list of shifts (scoped to API key user's sites)."""
        user = self._authenticate_api_key()
        if not user:
            return self._json_response(error='Invalid API key', status=401)

        try:
            limit = int(kwargs.get('limit', 100))
            offset = int(kwargs.get('offset', 0))
            status = kwargs.get('status')

            domain = list(self._site_domain(user))
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
        """Create a new shift (site must be in API key user's assignments)."""
        user = self._authenticate_api_key()
        if not user:
            return {'error': 'Invalid API key', 'status': 'error'}

        try:
            api_key = request.env['guardpro.api.key'].sudo().search([
                ('user_id', '=', user.id),
                ('scope_create', '=', True),
                ('active', '=', True),
            ], limit=1)

            if not api_key:
                return {'error': 'Insufficient permissions', 'status': 'error'}

            data = kwargs
            site_id = data.get('site_id')
            if not self._site_allowed(user, site_id):
                return {'error': 'Project not allowed for this API key', 'status': 'error'}

            guard_id = data.get('guard_id')
            if guard_id:
                guard = request.env['guard.profile'].sudo().browse(guard_id)
                if not self._guard_allowed(user, guard):
                    return {'error': 'Guard not allowed for this API key', 'status': 'error'}

            shift = request.env['guard.shift'].sudo().create({
                'guard_id': guard_id,
                'site_id': site_id,
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
        """Get list of incidents (scoped to API key user's sites)."""
        user = self._authenticate_api_key()
        if not user:
            return self._json_response(error='Invalid API key', status=401)

        try:
            limit = int(kwargs.get('limit', 100))
            severity = kwargs.get('severity')

            domain = list(self._site_domain(user))
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
        """Guard check-in via API (site/guard scoped to API key user)."""
        user = self._authenticate_api_key()
        if not user:
            return {'error': 'Invalid API key', 'status': 'error'}

        try:
            data = kwargs
            site_id = data.get('site_id')
            if not self._site_allowed(user, site_id):
                return {'error': 'Project not allowed for this API key', 'status': 'error'}

            guard = request.env['guard.profile'].sudo().browse(data.get('guard_id'))
            if not self._guard_allowed(user, guard):
                return {'error': 'Guard not allowed for this API key', 'status': 'error'}

            attendance = request.env['guard.attendance'].sudo().create({
                'guard_id': data['guard_id'],
                'site_id': site_id,
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
        """Guard check-out via API (attendance must be on an allowed site)."""
        user = self._authenticate_api_key()
        if not user:
            return {'error': 'Invalid API key', 'status': 'error'}

        try:
            data = kwargs

            attendance = request.env['guard.attendance'].sudo().browse(data['attendance_id'])

            if not attendance.exists():
                return {'error': 'Attendance record not found', 'status': 'error'}

            if not self._site_allowed(user, attendance.site_id.id if attendance.site_id else False):
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
