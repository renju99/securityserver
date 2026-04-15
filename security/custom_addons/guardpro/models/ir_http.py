# -*- coding: utf-8 -*-
"""HTTP tweaks for GuardPro (e.g. allow camera on mobile PWA pages)."""

import logging

from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)

# Browsers may block getUserMedia if Permissions-Policy does not delegate camera to self.
_GUARDPRO_MOBILE_PP = 'camera=(self), microphone=(self)'


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

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
            _logger.debug('GuardPro Permissions-Policy hook skipped: %s', e)
