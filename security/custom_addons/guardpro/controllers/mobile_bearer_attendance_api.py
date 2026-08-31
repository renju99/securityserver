# -*- coding: utf-8 -*-
"""Bearer-token attendance endpoints for Flutter/Android.

Compatibility rule:
Do not modify existing cookie/session endpoints.
Only add /guardpro/api/mobile_bearer/... routes.
"""

from odoo import http
from odoo.http import request

from ..common.mobile_bearer_auth import current_bearer_user
from ..common import validators


class GuardLinkMobileBearerAttendanceAPIController(http.Controller):
    def _auth_user(self):
        user = current_bearer_user()
        if not user:
            return None
        return user

    @http.route(
        '/guardpro/api/mobile_bearer/shift/checkin',
        type='json',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def shift_checkin(self, shift_id=None, latitude=None, longitude=None, checkpoint_scan_id=None, photo=None):
        """Bearer version of /guardpro/api/shift/checkin."""
        user = self._auth_user()
        if not user:
            return {'success': False, 'error': 'Authentication required'}

        valid, error, validated = validators.validate_shift_checkin_params({
            'shift_id': shift_id,
            'latitude': latitude,
            'longitude': longitude,
        })
        if not valid:
            return validators.create_error_response(error)

        shift_id = validated['shift_id']
        latitude = validated['latitude']
        longitude = validated['longitude']

        # Use user context for security checks.
        env = request.env(user=user)
        shift = env['guard.shift'].browse(shift_id)
        if not shift.exists():
            return validators.create_error_response('Shift not found', 'NOT_FOUND')

        guard = env['guard.profile'].sudo().search([
            ('user_id', '=', user.id),
        ], limit=1)
        if not guard:
            return validators.create_error_response('Guard profile not found', 'NOT_FOUND')

        if shift.guard_id.id != guard.id:
            return validators.create_error_response(
                'Unauthorized: This shift is not assigned to you',
                'ACCESS_DENIED',
            )

        result = shift.action_checkin(
            latitude=latitude,
            longitude=longitude,
            checkpoint_scan_id=checkpoint_scan_id,
            photo=photo,
        )
        if isinstance(result, dict):
            if 'error' not in result and 'success' not in result:
                result['success'] = True
            return result

        return validators.create_success_response(message='Shift started successfully')

    @http.route(
        '/guardpro/api/mobile_bearer/shift/checkout',
        type='json',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def shift_checkout(self, shift_id=None, latitude=None, longitude=None, complete_shift=False):
        """Bearer version of /guardpro/api/shift/checkout."""
        user = self._auth_user()
        if not user:
            return {'success': False, 'error': 'Authentication required'}

        if not shift_id:
            return {'success': False, 'error': 'Shift ID is required'}

        env = request.env(user=user)
        shift = env['guard.shift'].browse(int(shift_id))
        if not shift.exists():
            return {'success': False, 'error': 'Shift not found'}

        guard = env['guard.profile'].sudo().search([
            ('user_id', '=', user.id),
        ], limit=1)
        if not guard:
            return {'success': False, 'error': 'Guard profile not found'}

        if shift.guard_id.id != guard.id:
            return {'success': False, 'error': 'Unauthorized: This shift is not assigned to you'}

        result = shift.action_checkout(latitude, longitude, complete_shift)
        if isinstance(result, dict):
            if 'error' not in result and 'success' not in result:
                result['success'] = True
            return result

        return {'success': True, 'message': 'Shift ended successfully'}

