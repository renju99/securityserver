# -*- coding: utf-8 -*-
from odoo import api, models


class AuthOAuthProvider(models.Model):
    _inherit = "auth.oauth.provider"

    @api.model
    def _sales_bid_board_ensure_microsoft_oauth_provider(self):
        """Ensure Microsoft Azure AD provider has a visible label and correct userinfo endpoint."""
        vals = {
            "name": "Microsoft",
            "client_id": "fef07c3d-a541-43a9-95ab-57c25d324666",
            "auth_endpoint": (
                "https://login.microsoftonline.com/"
                "6db8cefc-eb9a-44ea-ac9b-f7097100afce/oauth2/v2.0/authorize"
            ),
            "validation_endpoint": "https://graph.microsoft.com/oidc/userinfo",
            "scope": "openid profile email User.Read",
            "enabled": True,
            "css_class": "fa fa-fw fa-windows",
            "body": "Log in with Microsoft",
            "sequence": 5,
        }
        existing = self.search([("name", "=", "Microsoft")], limit=1)
        if existing:
            existing.write(vals)
        else:
            self.create(vals)

        openerp = self.env.ref("auth_oauth.provider_openerp", raise_if_not_found=False)
        if openerp:
            openerp.write({"enabled": False})
