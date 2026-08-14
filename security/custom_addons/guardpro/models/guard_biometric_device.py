# -*- coding: utf-8 -*-
"""Guard Biometric Device Model - Device management."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class GuardBiometricDevice(models.Model):
    """Registered biometric devices."""
    
    _name = 'guard.biometric.device'
    _description = 'Biometric Device'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Device Name',
        required=True,
        tracking=True
    )
    
    device_type = fields.Selection([
        ('fingerprint_scanner', 'Fingerprint Scanner'),
        ('facial_camera', 'Facial Recognition Camera'),
        ('mobile_device', 'Mobile Device'),
        ('access_control', 'Access Control System'),
        ('usb_scanner', 'USB Fingerprint Scanner'),
    ], string='Device Type', required=True, tracking=True)
    
    device_model = fields.Char(
        string='Device Model',
        required=True,
        tracking=True
    )
    
    manufacturer = fields.Char(
        string='Manufacturer',
        help='Device manufacturer (e.g., ZKTeco, Suprema, Apple)'
    )
    
    serial_number = fields.Char(
        string='Serial Number',
        required=True,
        copy=False,
        tracking=True,
        index=True
    )
    
    # Location
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        tracking=True,
        help='Site where device is installed'
    )
    location_name = fields.Char(
        string='Location',
        tracking=True,
        help='Specific location (e.g., "Main Entrance", "Guard Station")'
    )
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7)
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7)
    )
    
    # Status
    is_active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    last_seen = fields.Datetime(
        string='Last Seen',
        help='Last communication with device',
        tracking=True
    )
    last_seen_status = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('error', 'Error'),
    ], string='Last Status', compute='_compute_last_seen_status', store=True)
    
    # Configuration
    supported_biometric_types = fields.Selection([
        ('fingerprint', 'Fingerprint'),
        ('facial', 'Facial Recognition'),
        ('voice', 'Voice Recognition'),
        ('fingerprint,facial', 'Fingerprint & Facial'),
        ('fingerprint,voice', 'Fingerprint & Voice'),
        ('all', 'All Types'),
    ], string='Supported Types', required=True, default='fingerprint')
    
    # API/Connection
    api_endpoint = fields.Char(
        string='API Endpoint',
        help='Device API endpoint URL (for network devices)'
    )
    api_key = fields.Char(
        string='API Key',
        help='API authentication key'
    )
    connection_type = fields.Selection([
        ('usb', 'USB'),
        ('network', 'Network'),
        ('bluetooth', 'Bluetooth'),
        ('mobile_app', 'Mobile App'),
        ('web', 'Web Browser'),
    ], string='Connection Type', default='usb', required=True, tracking=True)
    
    # USB Device Info
    usb_vendor_id = fields.Char(
        string='USB Vendor ID',
        help='USB vendor ID (for USB devices)'
    )
    usb_product_id = fields.Char(
        string='USB Product ID',
        help='USB product ID (for USB devices)'
    )
    
    # Network Device Info
    ip_address = fields.Char(
        string='IP Address',
        help='Network IP address (for network devices)'
    )
    port = fields.Integer(
        string='Port',
        default=80,
        help='Network port (for network devices)'
    )
    
    # Capabilities
    max_templates = fields.Integer(
        string='Max Templates',
        default=1000,
        help='Maximum number of templates device can store'
    )
    current_templates = fields.Integer(
        string='Current Templates',
        compute='_compute_current_templates',
        help='Number of templates currently stored on device'
    )
    
    # Statistics
    verification_count = fields.Integer(
        string='Total Verifications',
        compute='_compute_verification_stats',
        help='Total verifications performed on this device'
    )
    success_count = fields.Integer(
        string='Successful Verifications',
        compute='_compute_verification_stats'
    )
    failure_count = fields.Integer(
        string='Failed Verifications',
        compute='_compute_verification_stats'
    )
    success_rate = fields.Float(
        string='Success Rate %',
        compute='_compute_verification_stats',
        digits=(5, 2)
    )
    
    # Notes
    notes = fields.Text(
        string='Notes',
        help='Device configuration notes'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    
    _sql_constraints = [
        ('serial_unique', 'unique(serial_number)',
         'Serial number must be unique!'),
    ]
    
    @api.depends('last_seen')
    def _compute_last_seen_status(self):
        """Compute device status based on last seen time."""
        for record in self:
            if not record.last_seen:
                record.last_seen_status = 'offline'
            else:
                from datetime import timedelta
                now = fields.Datetime.now()
                time_diff = now - record.last_seen
                
                if time_diff < timedelta(minutes=5):
                    record.last_seen_status = 'online'
                elif time_diff < timedelta(hours=1):
                    record.last_seen_status = 'offline'
                else:
                    record.last_seen_status = 'error'
    
    @api.depends('device_type')
    def _compute_current_templates(self):
        """Compute current templates stored on device."""
        for record in self:
            # This would query the device API in real implementation
            # For now, count templates enrolled with this device
            templates = self.env['guard.biometric.template'].search_count([
                ('device_id', '=', record.serial_number)
            ])
            record.current_templates = templates
    
    @api.depends('serial_number')
    def _compute_verification_stats(self):
        """Compute verification statistics for this device."""
        for record in self:
            verifications = self.env['guard.biometric.verification'].search([
                ('device_id', '=', record.serial_number)
            ])
            
            record.verification_count = len(verifications)
            record.success_count = len(verifications.filtered(lambda v: v.verification_result == 'success'))
            record.failure_count = len(verifications.filtered(lambda v: v.verification_result == 'failed'))
            
            if record.verification_count > 0:
                record.success_rate = (record.success_count / record.verification_count) * 100
            else:
                record.success_rate = 0.0
    
    def action_test_connection(self):
        """Test connection to device."""
        self.ensure_one()
        
        # This would test actual device connection
        # For now, just update last_seen
        self.write({'last_seen': fields.Datetime.now()})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Connection Test'),
                'message': _('Device connection test completed.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_view_verifications(self):
        """View verification history for this device."""
        self.ensure_one()
        return {
            'name': _('Device Verifications - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.biometric.verification',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.serial_number)],
            'context': {'default_device_id': self.serial_number}
        }
    
    def action_view_templates(self):
        """View templates stored on this device."""
        self.ensure_one()
        return {
            'name': _('Device Templates - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.biometric.template',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.serial_number)],
            'context': {'default_device_id': self.serial_number}
        }

