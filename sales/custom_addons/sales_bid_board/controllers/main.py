# -*- coding: utf-8 -*-
"""Microsoft Entra: use auth code + PKCE (Odoo core uses implicit response_type=token, blocked by Azure)."""
import base64
import hashlib
import json
import logging
import secrets

import requests
import werkzeug.urls
from odoo import http
from odoo.addons.auth_oauth.controllers.main import (
    OAuthController,
    OAuthLogin,
    fragment_to_query_string,
)
from odoo.addons.web.controllers.utils import ensure_db
from odoo.http import request

_logger = logging.getLogger(__name__)


def _microsoft_token_url(auth_endpoint):
    if not auth_endpoint or "/authorize" not in auth_endpoint:
        return None
    return auth_endpoint.replace("/authorize", "/token")


def _is_microsoft_entra_provider(provider):
    ep = (provider.get("auth_endpoint") or "") + (provider.get("validation_endpoint") or "")
    return "login.microsoftonline.com" in ep or "graph.microsoft.com" in ep


class SalesBidBoardOAuthLogin(OAuthLogin):
    def list_providers(self):
        providers = super().list_providers()
        return_url = request.httprequest.url_root + "auth_oauth/signin"
        for provider in providers:
            if not _is_microsoft_entra_provider(provider):
                continue
            state = self.get_state(provider)
            verifier = (
                base64.urlsafe_b64encode(secrets.token_bytes(32))
                .rstrip(b"=")
                .decode("ascii")
            )
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
                .rstrip(b"=")
                .decode("ascii")
            )
            request.session["oauth_pkce_%s" % provider["id"]] = verifier
            params = {
                "client_id": provider["client_id"],
                "response_type": "code",
                "redirect_uri": return_url,
                "scope": provider["scope"],
                "state": json.dumps(state),
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "response_mode": "query",
            }
            provider["auth_link"] = "%s?%s" % (
                provider["auth_endpoint"],
                werkzeug.urls.url_encode(params),
            )
        return providers

    @http.route()
    def web_login(self, *args, **kw):
        # Force qcontext providers from our PKCE-aware list builder.
        ensure_db()
        if request.httprequest.method == "GET" and request.session.uid and request.params.get("redirect"):
            return request.redirect(request.params.get("redirect"))
        providers = self.list_providers()
        response = super(OAuthLogin, self).web_login(*args, **kw)
        if response.is_qweb:
            error = request.params.get("oauth_error")
            if error == "1":
                error = "Sign up is not allowed on this database."
            elif error == "2":
                error = "Access Denied"
            elif error == "3":
                error = (
                    "You do not have access to this database or your invitation has expired. "
                    "Please ask for an invitation and be sure to follow the link in your invitation email."
                )
            else:
                error = None
            response.qcontext["providers"] = providers
            if error:
                response.qcontext["error"] = error
        return response


class SalesBidBoardOAuthController(OAuthController):
    @http.route("/auth_oauth/signin", type="http", auth="none", readonly=False)
    @fragment_to_query_string
    def signin(self, **kw):
        if kw.get("code") and kw.get("state"):
            try:
                state = json.loads(kw["state"])
            except (TypeError, ValueError):
                state = {}
            provider_id = state.get("p")
            if provider_id:
                provider = request.env["auth.oauth.provider"].sudo().browse(provider_id)
                if provider.exists() and _is_microsoft_entra_provider(
                    {
                        "auth_endpoint": provider.auth_endpoint,
                        "validation_endpoint": provider.validation_endpoint,
                    }
                ):
                    session_key = "oauth_pkce_%s" % provider_id
                    verifier = request.session.pop(session_key, None)
                    token_url = _microsoft_token_url(provider.auth_endpoint)
                    return_url = request.httprequest.url_root + "auth_oauth/signin"
                    if verifier and token_url:
                        client_secret = (
                            request.env["ir.config_parameter"]
                            .sudo()
                            .get_param("sales_bid_board.microsoft_client_secret")
                        )
                        payload = {
                            "client_id": provider.client_id,
                            "scope": provider.scope,
                            "code": kw["code"],
                            "redirect_uri": return_url,
                            "grant_type": "authorization_code",
                            "code_verifier": verifier,
                        }
                        if client_secret:
                            payload["client_secret"] = client_secret
                        try:
                            tr = requests.post(token_url, data=payload, timeout=20)
                            body = tr.json() if tr.content else {}
                        except Exception:
                            _logger.exception("Microsoft OAuth token exchange failed")
                            return request.redirect("/web/login?oauth_error=2", 303)
                        if not tr.ok or "access_token" not in body:
                            _logger.warning(
                                "Microsoft token response error: %s %s",
                                tr.status_code,
                                body,
                            )
                            return request.redirect("/web/login?oauth_error=2", 303)
                        kw = dict(kw)
                        kw["access_token"] = body["access_token"]
        return super().signin(**kw)
