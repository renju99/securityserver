# -*- coding: utf-8 -*-
"""Avoid Discuss /mail/data 404 for anonymous requests without guest cookie.

Stock Odoo raises werkzeug NotFound when ``init_messaging`` is requested for the
public user but no ``mail.guest`` is in context (no ``dgid`` cookie). That
surfaces as RPC_ERROR 404 and can block the web client when the session is
missing or not yet bound (e.g. stale tab, wrong base URL, cookie issues).
"""
from odoo.addons.mail.controllers.webclient import WebclientController as MailWebclientController
from odoo.http import request


class WebclientController(MailWebclientController):
    def _process_request_for_all(self, store, **kwargs):
        if (
            'init_messaging' in kwargs
            and request.env.user._is_public()
            and not request.env['mail.guest']._get_guest_from_context()
        ):
            return
        return super()._process_request_for_all(store, **kwargs)
