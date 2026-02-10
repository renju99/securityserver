# -*- coding: utf-8 -*-
"""API Key Management for REST API."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import secrets
import hashlib
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class ApiKey(models.Model):
    """API keys for external integrations."""
    
    _name = 'guardpro.api.key'
    _description = 'API Key'
    _order = 'create_date desc'
    
    name = fields.Char(
        string='Key Name',
        required=True,
        help='Descriptive name for this API key'
    )
    
    key = fields.Char(
        string='API Key',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_key()
    )
    
    key_prefix = fields.Char(
        string='Key Prefix',
        compute='_compute_key_prefix',
        store=True,
        help='First 8 characters for identification'
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        help='Organization using this API key'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        help='User context for API requests'
    )
    
    # Permissions
    scope_read = fields.Boolean(
        string='Read Access',
        default=True
    )
    
    scope_write = fields.Boolean(
        string='Write Access',
        default=False
    )
    
    scope_create = fields.Boolean(
        string='Create Access',
        default=False
    )
    
    scope_delete = fields.Boolean(
        string='Delete Access',
        default=False
    )
    
    # Rate Limiting
    rate_limit = fields.Integer(
        string='Rate Limit (requests/hour)',
        default=1000,
        help='Maximum requests per hour'
    )
    
    # IP Whitelist
    allowed_ips = fields.Text(
        string='Allowed IP Addresses',
        help='Comma-separated list of IP addresses. Leave empty to allow all.'
    )
    
    # Validity
    expiry_date = fields.Datetime(
        string='Expiry Date',
        help='Leave empty for no expiration'
    )
    
    is_expired = fields.Boolean(
        string='Expired',
        compute='_compute_is_expired'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    # Usage Statistics
    last_used = fields.Datetime(
        string='Last Used',
        readonly=True
    )
    
    request_count = fields.Integer(
        string='Request Count',
        readonly=True,
        default=0
    )
    
    @api.depends('key')
    def _compute_key_prefix(self):
        """Extract key prefix."""
        for record in self:
            record.key_prefix = record.key[:8] if record.key else ''
    
    @api.depends('expiry_date')
    def _compute_is_expired(self):
        """Check if key is expired."""
        for record in self:
            if record.expiry_date:
                record.is_expired = fields.Datetime.now() > record.expiry_date
            else:
                record.is_expired = False
    
    @api.model
    def _generate_key(self):
        """Generate secure random API key."""
        # Generate 32-byte random key
        random_bytes = secrets.token_bytes(32)
        # Create hex representation with prefix
        key = 'gpk_' + random_bytes.hex()
        return key
    
    def regenerate_key(self):
        """Regenerate API key."""
        self.ensure_one()
        
        new_key = self._generate_key()
        self.sudo().write({'key': new_key})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('API key has been regenerated. Update your applications with the new key.'),
                'type': 'warning',
                'sticky': True,
            }
        }
    
    @api.model
    def validate_api_key(self, key, ip_address=None):
        """Validate API key and return associated user."""
        api_key = self.search([
            ('key', '=', key),
            ('active', '=', True)
        ], limit=1)
        
        if not api_key:
            return False
        
        # Check expiry
        if api_key.is_expired:
            _logger.warning('Expired API key used: %s', api_key.name)
            return False
        
        # Check IP whitelist
        if api_key.allowed_ips and ip_address:
            allowed_list = [ip.strip() for ip in api_key.allowed_ips.split(',')]
            if ip_address not in allowed_list:
                _logger.warning('API key %s used from unauthorized IP: %s', api_key.name, ip_address)
                return False
        
        # Update usage stats
        api_key.sudo().write({
            'last_used': fields.Datetime.now(),
            'request_count': api_key.request_count + 1
        })
        
        return api_key.user_id
    
    def action_view_usage(self):
        """View API usage logs."""
        self.ensure_one()
        # TODO: Implement API usage log model
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Info'),
                'message': _('Usage logs will be available in a future update.'),
                'type': 'info',
            }
        }

