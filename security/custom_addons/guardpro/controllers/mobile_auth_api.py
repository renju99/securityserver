# -*- coding: utf-8 -*-
"""Mobile token authentication endpoints for Flutter/Android."""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class GuardLinkMobileAuthAPI(http.Controller):
    """Auth endpoints for token-based mobile clients."""

    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, default=str),
            headers=[('Content-Type', 'application/json')],
            status=status,
        )

    def _authenticate_login(self, login, password):
        """Authenticate against current DB and return uid or False."""
        if not request.db:
            return False
        try:
            return request.session.authenticate(request.db, login, password)
        except TypeError:
            # Compatibility fallback for environments expecting a credentials dict.
            return request.session.authenticate(
                request.db,
                {'login': login, 'password': password, 'type': 'password'},
            )

    def _bearer_user(self):
        """Resolve user from Authorization: Bearer token."""
        auth_header = request.httprequest.headers.get('Authorization', '')
        if not auth_header.lower().startswith('bearer '):
            return request.env['res.users'].browse()
        raw_token = auth_header.split(' ', 1)[1].strip()
        if not raw_token:
            return request.env['res.users'].browse()
        token_row = request.env['guardpro.mobile.auth.token']._validate_raw_token(
            raw_token,
            token_kind='access',
        )
        if not token_row:
            return request.env['res.users'].browse()
        return token_row.user_id

    @http.route(
        '/guardpro/api/mobile/auth/login',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def mobile_login(self, **kwargs):
        """Issue access/refresh tokens using Odoo username + password."""
        try:
            raw = request.httprequest.data.decode('utf-8') if request.httprequest.data else '{}'
            body = json.loads(raw or '{}')
        except (ValueError, UnicodeDecodeError):
            return self._json_response({'success': False, 'error': 'Invalid JSON body'}, status=400)

        login = (body.get('username') or body.get('login') or '').strip()
        password = body.get('password') or ''
        device_id = (body.get('device_id') or '').strip() or None
        device_name = (body.get('device_name') or '').strip() or None

        if not login or not password:
            return self._json_response(
                {'success': False, 'error': 'username and password are required'},
                status=400,
            )

        uid = self._authenticate_login(login, password)
        if not uid:
            return self._json_response({'success': False, 'error': 'Invalid credentials'}, status=401)

        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists() or not user.active:
            return self._json_response({'success': False, 'error': 'User inactive'}, status=403)

        token_model = request.env['guardpro.mobile.auth.token']
        token_pair = token_model._issue_pair(user, device_id=device_id, device_name=device_name)
        # We do not depend on web session after token issuance.
        request.session.logout(keep_db=True)

        return self._json_response({
            'success': True,
            'access_token': token_pair['access_token'],
            'refresh_token': token_pair['refresh_token'],
            'token_type': 'Bearer',
            'access_expires_at': token_pair['access_expires_at'],
            'refresh_expires_at': token_pair['refresh_expires_at'],
            'session_uuid': token_pair['session_uuid'],
            'user': {
                'id': user.id,
                'name': user.name,
                'login': user.login,
            },
        })

    @http.route(
        '/guardpro/api/mobile/auth/refresh',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def mobile_refresh(self, **kwargs):
        """Rotate access token using a valid refresh token."""
        try:
            raw = request.httprequest.data.decode('utf-8') if request.httprequest.data else '{}'
            body = json.loads(raw or '{}')
        except (ValueError, UnicodeDecodeError):
            return self._json_response({'success': False, 'error': 'Invalid JSON body'}, status=400)

        refresh_token = (body.get('refresh_token') or '').strip()
        if not refresh_token:
            return self._json_response({'success': False, 'error': 'refresh_token is required'}, status=400)

        token_model = request.env['guardpro.mobile.auth.token']
        refresh_row = token_model._validate_raw_token(refresh_token, token_kind='refresh')
        if not refresh_row:
            return self._json_response({'success': False, 'error': 'Invalid or expired refresh token'}, status=401)

        user = refresh_row.user_id
        # Revoke entire old session and issue a fresh pair (rotating refresh token).
        token_model._revoke_session(refresh_row.session_uuid)
        token_pair = token_model._issue_pair(
            user,
            device_id=refresh_row.device_id,
            device_name=refresh_row.device_name,
        )
        return self._json_response({
            'success': True,
            'access_token': token_pair['access_token'],
            'refresh_token': token_pair['refresh_token'],
            'token_type': 'Bearer',
            'access_expires_at': token_pair['access_expires_at'],
            'refresh_expires_at': token_pair['refresh_expires_at'],
            'session_uuid': token_pair['session_uuid'],
        })

    @http.route(
        '/guardpro/api/mobile/auth/logout',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def mobile_logout(self, **kwargs):
        """Revoke current token session."""
        auth_header = request.httprequest.headers.get('Authorization', '')
        bearer = auth_header.split(' ', 1)[1].strip() if auth_header.lower().startswith('bearer ') else ''
        refresh_from_body = ''
        try:
            raw = request.httprequest.data.decode('utf-8') if request.httprequest.data else '{}'
            refresh_from_body = (json.loads(raw or '{}').get('refresh_token') or '').strip()
        except Exception:
            pass

        token_model = request.env['guardpro.mobile.auth.token']
        row = token_model._validate_raw_token(bearer, token_kind='access')
        if not row and refresh_from_body:
            row = token_model._validate_raw_token(refresh_from_body, token_kind='refresh')
        if not row:
            return self._json_response({'success': True, 'revoked': 0})
        revoked = token_model._revoke_session(row.session_uuid)
        return self._json_response({'success': True, 'revoked': revoked})

    @http.route(
        '/guardpro/api/mobile/auth/me',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
    )
    def mobile_me(self, **kwargs):
        """Validate bearer token and return current user profile."""
        user = self._bearer_user()
        if not user:
            return self._json_response({'success': False, 'error': 'Unauthorized'}, status=401)
        guard = request.env['guard.profile'].sudo().search([('user_id', '=', user.id)], limit=1)
        return self._json_response({
            'success': True,
            'user': {
                'id': user.id,
                'name': user.name,
                'login': user.login,
                'is_guard': bool(guard),
                'guard_id': guard.id if guard else None,
            },
        })

