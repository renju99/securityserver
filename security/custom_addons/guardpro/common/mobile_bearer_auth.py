# -*- coding: utf-8 -*-
"""Shared helpers for Bearer token authentication on mobile APIs."""

from odoo.http import request


def current_bearer_user():
    """Return authenticated ``res.users`` from Authorization header or empty recordset."""
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

