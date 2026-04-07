# -*- coding: utf-8 -*-
import requests
from werkzeug import http, datastructures

from odoo import models
from odoo.exceptions import AccessDenied

if hasattr(datastructures.WWWAuthenticate, "from_header"):
    _parse_auth = datastructures.WWWAuthenticate.from_header
else:
    _parse_auth = http.parse_www_authenticate_header


class ResUsers(models.Model):
    _inherit = "res.users"

    def _auth_oauth_rpc(self, endpoint, access_token):
        """Microsoft Graph OIDC userinfo requires Bearer; Odoo default sends token as query param."""
        if endpoint and "graph.microsoft.com" in endpoint:
            response = requests.get(
                endpoint,
                headers={"Authorization": "Bearer %s" % access_token},
                timeout=10,
            )
            if response.ok:
                return response.json()
            challenge = _parse_auth(response.headers.get("WWW-Authenticate"))
            if challenge and challenge.type == "bearer" and "error" in challenge:
                return dict(challenge)
            return {"error": "invalid_request"}
        return super()._auth_oauth_rpc(endpoint, access_token)

    def _auth_oauth_signin(self, provider, validation, params):
        """Link existing local user by email on first Microsoft OAuth login."""
        try:
            return super()._auth_oauth_signin(provider, validation, params)
        except AccessDenied:
            email = (validation or {}).get("email")
            oauth_uid = (validation or {}).get("user_id")
            if not email or not oauth_uid:
                raise
            user = self.search(
                self._get_login_domain(email),
                order=self._get_login_order(),
                limit=1,
            )
            if not user:
                raise
            user.write(
                {
                    "oauth_provider_id": provider,
                    "oauth_uid": oauth_uid,
                    "oauth_access_token": params.get("access_token"),
                }
            )
            return user.login
