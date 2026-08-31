# -*- coding: utf-8 -*-
"""Mobile auth token storage for Flutter/Android clients."""

from datetime import timedelta
import hashlib
import secrets
import uuid

from odoo import api, fields, models


class GuardProMobileAuthToken(models.Model):
    """Stores hashed mobile access/refresh tokens."""

    _name = 'guardpro.mobile.auth.token'
    _description = 'GuardPro Mobile Auth Token'
    _order = 'id desc'

    user_id = fields.Many2one('res.users', required=True, index=True, ondelete='cascade')
    token_hash = fields.Char(required=True, index=True, readonly=True, copy=False)
    token_kind = fields.Selection(
        [('access', 'Access'), ('refresh', 'Refresh')],
        required=True,
        index=True,
        readonly=True,
    )
    session_uuid = fields.Char(required=True, index=True, readonly=True, copy=False)
    device_id = fields.Char(index=True)
    device_name = fields.Char()
    expires_at = fields.Datetime(required=True, index=True, readonly=True)
    revoked = fields.Boolean(default=False, index=True)
    revoked_at = fields.Datetime(readonly=True)
    last_used_at = fields.Datetime(readonly=True)

    _sql_constraints = [
        ('guardpro_mobile_auth_token_hash_uniq', 'unique(token_hash)', 'Token hash already exists.'),
    ]

    @api.model
    def _hash_token(self, raw_token):
        """Create deterministic hash for token lookup."""
        return hashlib.sha256((raw_token or '').encode('utf-8')).hexdigest()

    @api.model
    def _new_raw_token(self, prefix):
        """Generate cryptographically secure random token."""
        return '%s_%s' % (prefix, secrets.token_urlsafe(48))

    @api.model
    def _issue_pair(self, user, device_id=None, device_name=None):
        """Issue and persist a new access+refresh token pair."""
        now = fields.Datetime.now()
        session_uuid = str(uuid.uuid4())
        access_raw = self._new_raw_token('gl_at')
        refresh_raw = self._new_raw_token('gl_rt')
        access_ttl_min = int(self.env['ir.config_parameter'].sudo().get_param(
            'guardpro.mobile.access_token_minutes', '15'
        ))
        refresh_ttl_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'guardpro.mobile.refresh_token_days', '30'
        ))
        access_exp = now + timedelta(minutes=max(access_ttl_min, 5))
        refresh_exp = now + timedelta(days=max(refresh_ttl_days, 1))

        self.sudo().create([
            {
                'user_id': user.id,
                'token_hash': self._hash_token(access_raw),
                'token_kind': 'access',
                'session_uuid': session_uuid,
                'device_id': device_id,
                'device_name': device_name,
                'expires_at': access_exp,
            },
            {
                'user_id': user.id,
                'token_hash': self._hash_token(refresh_raw),
                'token_kind': 'refresh',
                'session_uuid': session_uuid,
                'device_id': device_id,
                'device_name': device_name,
                'expires_at': refresh_exp,
            },
        ])
        return {
            'access_token': access_raw,
            'refresh_token': refresh_raw,
            'access_expires_at': access_exp,
            'refresh_expires_at': refresh_exp,
            'session_uuid': session_uuid,
        }

    @api.model
    def _validate_raw_token(self, raw_token, token_kind='access'):
        """Validate an untrusted raw token and return matching row."""
        if not raw_token:
            return self.browse()
        token_hash = self._hash_token(raw_token.strip())
        rec = self.sudo().search([
            ('token_hash', '=', token_hash),
            ('token_kind', '=', token_kind),
            ('revoked', '=', False),
        ], limit=1)
        if not rec:
            return self.browse()
        if rec.expires_at and rec.expires_at < fields.Datetime.now():
            rec.sudo().write({'revoked': True, 'revoked_at': fields.Datetime.now()})
            return self.browse()
        rec.sudo().write({'last_used_at': fields.Datetime.now()})
        return rec

    @api.model
    def _revoke_session(self, session_uuid):
        """Revoke all tokens under one mobile session."""
        if not session_uuid:
            return 0
        rows = self.sudo().search([('session_uuid', '=', session_uuid), ('revoked', '=', False)])
        rows.sudo().write({'revoked': True, 'revoked_at': fields.Datetime.now()})
        return len(rows)

