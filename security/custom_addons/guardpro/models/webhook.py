# -*- coding: utf-8 -*-
"""Webhook Integration System."""

from odoo import models, fields, api, _
import requests
import json
import hashlib
import hmac
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class Webhook(models.Model):
    """Webhook configuration for external integrations."""
    
    _name = 'guardpro.webhook'
    _description = 'Webhook Configuration'
    _order = 'name'
    
    name = fields.Char(
        string='Webhook Name',
        required=True,
        help='Descriptive name for this webhook'
    )
    
    url = fields.Char(
        string='Endpoint URL',
        required=True,
        help='HTTP(S) URL to send webhook payloads'
    )
    
    method = fields.Selection([
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH')
    ], string='HTTP Method', default='POST', required=True)
    
    events = fields.Selection([
        ('shift.created', 'Shift Created'),
        ('shift.completed', 'Shift Completed'),
        ('shift.cancelled', 'Shift Cancelled'),
        ('incident.created', 'Incident Created'),
        ('incident.critical', 'Critical Incident'),
        ('checkpoint.scanned', 'Checkpoint Scanned'),
        ('tour.completed', 'Tour Completed'),
        ('guard.checkin', 'Guard Check-in'),
        ('guard.checkout', 'Guard Check-out'),
        ('geofence.violation', 'Geofence Violation'),
        ('emergency.started', 'Emergency Procedure Started'),
        ('all', 'All Events')
    ], string='Trigger Events', required=True, default='all')
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    # Authentication
    auth_type = fields.Selection([
        ('none', 'None'),
        ('basic', 'Basic Auth'),
        ('bearer', 'Bearer Token'),
        ('custom', 'Custom Header')
    ], string='Authentication', default='none')
    
    auth_username = fields.Char('Username')
    auth_password = fields.Char('Password')
    auth_token = fields.Char('Bearer Token')
    auth_header_name = fields.Char('Header Name')
    auth_header_value = fields.Char('Header Value')
    
    # Signing
    enable_signing = fields.Boolean(
        string='Enable Payload Signing',
        help='Sign webhook payloads with HMAC-SHA256'
    )
    
    secret_key = fields.Char(
        string='Secret Key',
        help='Secret key for payload signing'
    )
    
    # Retry Configuration
    max_retries = fields.Integer(
        string='Max Retries',
        default=3,
        help='Number of times to retry failed webhooks'
    )
    
    retry_delay = fields.Integer(
        string='Initial Retry Delay (seconds)',
        default=60,
        help='Delay before first retry (will use exponential backoff)'
    )
    
    # Timeout
    timeout = fields.Integer(
        string='Timeout (seconds)',
        default=30,
        help='HTTP request timeout'
    )
    
    # Statistics
    total_sent = fields.Integer(
        string='Total Sent',
        readonly=True,
        default=0
    )
    
    total_failed = fields.Integer(
        string='Total Failed',
        readonly=True,
        default=0
    )
    
    success_rate = fields.Float(
        string='Success Rate (%)',
        compute='_compute_success_rate',
        store=True
    )
    
    last_sent = fields.Datetime(
        string='Last Sent',
        readonly=True
    )
    
    last_error = fields.Text(
        string='Last Error',
        readonly=True
    )
    
    @api.depends('total_sent', 'total_failed')
    def _compute_success_rate(self):
        """Compute success rate."""
        for record in self:
            total = record.total_sent + record.total_failed
            if total > 0:
                record.success_rate = (record.total_sent / total) * 100
            else:
                record.success_rate = 0.0
    
    def send_webhook(self, event_type, payload):
        """Send webhook with retry logic."""
        self.ensure_one()
        
        if not self.active:
            return False
        
        # Check if this webhook handles this event
        if self.events != 'all' and self.events != event_type:
            return False
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'GuardPro-Odoo/1.0',
            'X-GuardPro-Event': event_type,
            'X-GuardPro-Delivery': str(self.env['guardpro.webhook.log'].search_count([]) + 1)
        }
        
        # Add authentication
        if self.auth_type == 'basic' and self.auth_username:
            import base64
            credentials = f'{self.auth_username}:{self.auth_password}'.encode()
            headers['Authorization'] = f'Basic {base64.b64encode(credentials).decode()}'
        elif self.auth_type == 'bearer' and self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        elif self.auth_type == 'custom' and self.auth_header_name:
            headers[self.auth_header_name] = self.auth_header_value
        
        # Sign payload if enabled
        if self.enable_signing and self.secret_key:
            payload_json = json.dumps(payload)
            signature = hmac.new(
                self.secret_key.encode(),
                payload_json.encode(),
                hashlib.sha256
            ).hexdigest()
            headers['X-GuardPro-Signature'] = f'sha256={signature}'
        
        # Send webhook with retry logic
        attempt = 0
        while attempt <= self.max_retries:
            try:
                response = requests.request(
                    method=self.method,
                    url=self.url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )
                
                # Log webhook
                self.env['guardpro.webhook.log'].create({
                    'webhook_id': self.id,
                    'event_type': event_type,
                    'payload': json.dumps(payload, indent=2),
                    'response_status': response.status_code,
                    'response_body': response.text[:1000],  # Limit size
                    'success': 200 <= response.status_code < 300,
                    'attempt': attempt + 1
                })
                
                if 200 <= response.status_code < 300:
                    self.write({
                        'total_sent': self.total_sent + 1,
                        'last_sent': fields.Datetime.now()
                    })
                    return True
                else:
                    raise Exception(f'HTTP {response.status_code}: {response.text}')
                
            except Exception as e:
                _logger.warning('Webhook delivery failed (attempt %d/%d): %s', 
                               attempt + 1, self.max_retries + 1, str(e))
                
                if attempt >= self.max_retries:
                    # Final failure
                    self.write({
                        'total_failed': self.total_failed + 1,
                        'last_error': str(e)
                    })
                    
                    # Log failure
                    self.env['guardpro.webhook.log'].create({
                        'webhook_id': self.id,
                        'event_type': event_type,
                        'payload': json.dumps(payload, indent=2),
                        'error_message': str(e),
                        'success': False,
                        'attempt': attempt + 1
                    })
                    
                    return False
                else:
                    # Wait with exponential backoff
                    import time
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)
                    attempt += 1
        
        return False
    
    def action_test_webhook(self):
        """Test webhook with sample payload."""
        self.ensure_one()
        
        test_payload = {
            'event': 'test.webhook',
            'timestamp': fields.Datetime.now().isoformat(),
            'data': {
                'message': 'This is a test webhook from GuardPro',
                'webhook_name': self.name
            }
        }
        
        success = self.send_webhook('test.webhook', test_payload)
        
        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Test webhook sent successfully!'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Webhook test failed. Check the error log.'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def action_view_logs(self):
        """View webhook logs."""
        self.ensure_one()
        return {
            'name': _('Webhook Logs: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guardpro.webhook.log',
            'view_mode': 'list,form',
            'domain': [('webhook_id', '=', self.id)],
            'context': {'default_webhook_id': self.id}
        }


class WebhookLog(models.Model):
    """Log of webhook deliveries."""
    
    _name = 'guardpro.webhook.log'
    _description = 'Webhook Delivery Log'
    _order = 'create_date desc'
    _rec_name = 'webhook_id'
    
    webhook_id = fields.Many2one(
        'guardpro.webhook',
        string='Webhook',
        required=True,
        ondelete='cascade'
    )
    
    event_type = fields.Char(
        string='Event Type',
        required=True
    )
    
    payload = fields.Text(
        string='Payload',
        required=True
    )
    
    response_status = fields.Integer(
        string='Response Status'
    )
    
    response_body = fields.Text(
        string='Response Body'
    )
    
    error_message = fields.Text(
        string='Error Message'
    )
    
    success = fields.Boolean(
        string='Success',
        default=False
    )
    
    attempt = fields.Integer(
        string='Attempt Number',
        default=1
    )
    
    create_date = fields.Datetime(
        string='Sent At',
        readonly=True
    )


# Helper mixin to trigger webhooks from models
class WebhookMixin(models.AbstractModel):
    """Mixin to add webhook triggering capability to models."""
    
    _name = 'guardpro.webhook.mixin'
    _description = 'Webhook Trigger Mixin'
    
    def trigger_webhooks(self, event_type, custom_payload=None):
        """Trigger webhooks for an event."""
        webhooks = self.env['guardpro.webhook'].search([
            ('active', '=', True),
            '|',
            ('events', '=', 'all'),
            ('events', '=', event_type)
        ])
        
        if not webhooks:
            return
        
        # Build default payload
        payload = {
            'event': event_type,
            'timestamp': fields.Datetime.now().isoformat(),
            'data': custom_payload or self._webhook_payload()
        }
        
        # Send to each webhook (non-blocking)
        for webhook in webhooks:
            try:
                # Execute in separate transaction to avoid blocking
                self.env.cr.commit()
                webhook.send_webhook(event_type, payload)
            except Exception as e:
                _logger.error('Error sending webhook: %s', str(e))
    
    def _webhook_payload(self):
        """Build webhook payload for this record. Override in models."""
        return {
            'id': self.id,
            'name': self.name if hasattr(self, 'name') else str(self.id)
        }

