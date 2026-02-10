# -*- coding: utf-8 -*-
"""Guard Biometric Verification Log Model."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class GuardBiometricVerification(models.Model):
    """Log of all biometric verification attempts."""
    
    _name = 'guard.biometric.verification'
    _description = 'Biometric Verification Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'verification_time desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True
    )
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        tracking=True,
        index=True,
        ondelete='cascade'
    )
    
    biometric_type = fields.Selection([
        ('fingerprint', 'Fingerprint'),
        ('facial', 'Facial Recognition'),
        ('voice', 'Voice Recognition'),
    ], string='Biometric Type', required=True, tracking=True, index=True)
    
    verification_result = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('error', 'Error'),
    ], string='Result', required=True, tracking=True, index=True)
    
    confidence_score = fields.Float(
        string='Confidence Score',
        digits=(5, 2),
        help='Matching confidence (0-100)',
        tracking=True
    )
    
    verification_time = fields.Datetime(
        string='Verification Time',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        index=True
    )
    
    # Context
    verification_purpose = fields.Selection([
        ('checkin', 'Check-in'),
        ('checkout', 'Check-out'),
        ('access_control', 'Access Control'),
        ('incident_verification', 'Incident Verification'),
        ('tour_verification', 'Tour Verification'),
    ], string='Purpose', required=True, tracking=True, index=True)
    
    # Related records
    attendance_id = fields.Many2one(
        'guard.attendance',
        string='Attendance Record',
        ondelete='set null',
        help='Related attendance record'
    )
    shift_id = fields.Many2one(
        'guard.shift',
        string='Shift',
        ondelete='set null',
        help='Related shift'
    )
    tour_log_id = fields.Many2one(
        'tour.log',
        string='Tour Log',
        ondelete='set null',
        help='Related tour log'
    )
    incident_id = fields.Many2one(
        'incident.report',
        string='Incident',
        ondelete='set null',
        help='Related incident'
    )
    
    # Device information
    device_id = fields.Char(
        string='Device ID',
        help='Device identifier',
        index=True
    )
    device_model = fields.Char(
        string='Device Model',
        help='Model of device used'
    )
    device_type = fields.Selection([
        ('mobile', 'Mobile Device'),
        ('usb_scanner', 'USB Scanner'),
        ('network_device', 'Network Device'),
        ('webcam', 'Webcam'),
    ], string='Device Type', help='Type of device used')
    
    ip_address = fields.Char(
        string='IP Address',
        help='IP address of device'
    )
    user_agent = fields.Char(
        string='User Agent',
        help='Browser/App user agent'
    )
    
    # Location
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7)
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7)
    )
    location_name = fields.Char(
        string='Location Name'
    )
    
    # Error details
    error_message = fields.Text(
        string='Error Message',
        help='Error details if verification failed'
    )
    error_code = fields.Char(
        string='Error Code',
        help='Error code for troubleshooting'
    )
    
    # Security flags
    is_suspicious = fields.Boolean(
        string='Suspicious',
        default=False,
        tracking=True,
        help='Flagged for review'
    )
    fraud_indicators = fields.Text(
        string='Fraud Indicators',
        help='Indicators of potential fraud'
    )
    review_required = fields.Boolean(
        string='Review Required',
        default=False,
        help='Requires manual review'
    )
    reviewed_by = fields.Many2one(
        'res.users',
        string='Reviewed By',
        readonly=True
    )
    reviewed_date = fields.Datetime(
        string='Reviewed Date',
        readonly=True
    )
    review_notes = fields.Text(
        string='Review Notes'
    )
    
    # Template used (if successful)
    template_id = fields.Many2one(
        'guard.biometric.template',
        string='Template Used',
        ondelete='set null',
        help='Template that matched (if successful)'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='guard_id.company_id',
        store=True
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence for verification log."""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'guard.biometric.verification'
                ) or _('New')
        
        records = super().create(vals_list)
        
        # Update template usage if successful
        for record in records:
            if record.verification_result == 'success' and record.template_id:
                record.template_id.write({
                    'verification_count': record.template_id.verification_count + 1,
                    'last_used': record.verification_time,
                    'last_used_location': record.location_name
                })
        
        return records
    
    def action_mark_suspicious(self):
        """Mark verification as suspicious."""
        self.write({
            'is_suspicious': True,
            'review_required': True
        })
    
    def action_review(self):
        """Mark verification as reviewed."""
        self.write({
            'review_required': False,
            'reviewed_by': self.env.user.id,
            'reviewed_date': fields.Datetime.now()
        })
    
    def action_view_guard(self):
        """View guard profile."""
        self.ensure_one()
        return {
            'name': _('Guard Profile'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.profile',
            'res_id': self.guard_id.id,
            'view_mode': 'form',
            'target': 'current'
        }









