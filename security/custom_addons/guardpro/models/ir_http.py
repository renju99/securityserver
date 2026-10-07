# -*- coding: utf-8 -*-
"""HTTP tweaks for GuardLink (e.g. allow camera on mobile PWA pages)."""

import logging

import werkzeug.exceptions

from odoo import http, models
from odoo.http import request

_logger = logging.getLogger(__name__)

# Browsers may block getUserMedia if Permissions-Policy does not delegate camera to self.
_GUARDPRO_MOBILE_PP = 'camera=(self), microphone=(self)'

# Native Android polls these paths with session cookies — must get JSON 401, not
# 303 redirect to /web/login (which breaks HttpURLConnection / OkHttp).
_GUARDPRO_NATIVE_API_PREFIX = '/guardpro/api/'


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _handle_error(cls, exception):
        try:
            path = request.httprequest.path or ''
        except Exception:
            path = ''
        if path.startswith(_GUARDPRO_NATIVE_API_PREFIX):
            if isinstance(exception, http.SessionExpiredException):
                return request.make_json_response(
                    {
                        'success': False,
                        'error': 'Session expired',
                        'error_code': 'SESSION_EXPIRED',
                    },
                    status=401,
                )
            if isinstance(exception, werkzeug.exceptions.Unauthorized):
                return request.make_json_response(
                    {
                        'success': False,
                        'error': 'Unauthorized',
                        'error_code': 'UNAUTHORIZED',
                    },
                    status=401,
                )
        return super()._handle_error(exception)

    @classmethod
    def _post_dispatch(cls, response):
        super()._post_dispatch(response)
        try:
            httprequest = request.httprequest
            if not httprequest or not str(httprequest.path).startswith('/guardpro/mobile'):
                return
            headers = getattr(response, 'headers', None)
            if headers is None:
                return
            existing = (headers.get('Permissions-Policy') or headers.get('permissions-policy') or '').strip()
            if existing:
                low = existing.lower()
                if 'camera=' in low:
                    return
                headers['Permissions-Policy'] = f'{existing}, {_GUARDPRO_MOBILE_PP}'
            else:
                headers['Permissions-Policy'] = _GUARDPRO_MOBILE_PP
        except Exception as e:
            _logger.debug('GuardLink Permissions-Policy hook skipped: %s', e)
