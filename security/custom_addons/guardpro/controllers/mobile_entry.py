# -*- coding: utf-8 -*-
"""Keep the GuardLink APK on the mobile shell after login.

Internal users (supervisors, managers, clients) normally land on ``/odoo``
after login. That is the desktop back office and looks like a website inside
the Android WebView. The app User-Agent includes ``GuardLink-App``.
"""

import logging

from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import Home

_logger = logging.getLogger(__name__)

_MOBILE_UA_TOKENS = (
    'iphone', 'ipad', 'ipod', 'android', 'mobile', 'silk/', 'blackberry',
)


def request_wants_mobile_shell():
    """True for the GuardLink app and typical phone browsers."""
    ua = (request.httprequest.user_agent.string or '').lower()
    if 'guardlink-app' in ua:
        return True
    if request.httprequest.args.get('mobile') in ('1', 'true', 'yes'):
        return True
    return any(token in ua for token in _MOBILE_UA_TOKENS)


def request_is_guardlink_app():
    ua = (request.httprequest.user_agent.string or '').lower()
    return 'guardlink-app' in ua


def user_uses_mobile_shell(user):
    """Guards, supervisors, managers, admins, and clients get the phone UI."""
    if not user or not user.exists() or user._is_public():
        return False
    if user.has_group('guardpro.group_guardpro_guard_portal'):
        return True
    if user.has_group('guardpro.group_guardpro_supervisor'):
        return True
    if user.has_group('guardpro.group_guardpro_manager'):
        return True
    if user.has_group('guardpro.group_guardpro_admin'):
        return True
    if user.has_group('guardpro.group_guardpro_client_user'):
        return True
    return bool(request.env['guard.profile'].sudo().search([
        ('user_id', '=', user.id)
    ], limit=1))


class GuardLinkHome(Home):
    """Send app sessions to /guardpro/mobile instead of the Odoo backend."""

    def _login_redirect(self, uid, redirect=None):
        user = request.env['res.users'].sudo().browse(uid)
        if request_wants_mobile_shell() and user_uses_mobile_shell(user):
            _logger.info(
                '[GuardLink] Login redirect to mobile shell for %s (uid=%s)',
                user.login, uid,
            )
            return '/guardpro/mobile'
        return super()._login_redirect(uid, redirect=redirect)

    @http.route(
        ['/web', '/odoo', '/odoo/<path:subpath>', '/scoped_app/<path:subpath>'],
        type='http',
        auth='none',
        readonly=Home._web_client_readonly,
    )
    def web_client(self, s_action=None, **kw):
        if request.session.uid and request_is_guardlink_app():
            user = request.env['res.users'].sudo().browse(request.session.uid)
            if user_uses_mobile_shell(user):
                _logger.info(
                    '[GuardLink] App requested backend; sending %s to mobile shell',
                    user.login,
                )
                return request.redirect('/guardpro/mobile')
        return super().web_client(s_action=s_action, **kw)
