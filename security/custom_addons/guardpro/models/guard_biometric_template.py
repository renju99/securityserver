# -*- coding: utf-8 -*-
"""Guard Biometric Template Model - Encrypted biometric storage."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class GuardBiometricTemplate(models.Model):
    """Store encrypted biometric templates for guards."""
    
    _name = 'guard.biometric.template'
    _description = 'Guard Biometric Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'enrolled_date desc'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade',
        tracking=True,
        index=True
    )
    
    biometric_type = fields.Selection([
        ('fingerprint', 'Fingerprint'),
        ('facial', 'Facial Recognition'),
        ('voice', 'Voice Recognition'),
        ('iris', 'Iris Recognition'),
    ], string='Biometric Type', required=True, tracking=True)
    
    # Encrypted template data (never store raw biometrics)
    template_data = fields.Binary(
        string='Encrypted Template',
        required=True,
        attachment=True,
        help='Encrypted biometric template (AES-256)'
    )
    
    # Template metadata (for matching algorithms)
    template_hash = fields.Char(
        string='Template Hash',
        index=True,
        help='Hash of template for quick lookup'
    )
    
    # Device/algorithm information
    device_model = fields.Char(
        string='Device Model',
        help='Device used to capture template'
    )
    device_id = fields.Char(
        string='Device ID',
        help='Unique device identifier'
    )
    algorithm_version = fields.Char(
        string='Algorithm Version',
        default='1.0',
        help='Version of matching algorithm used'
    )
    
    # Quality metrics
    quality_score = fields.Float(
        string='Quality Score',
        digits=(5, 2),
        help='Template quality (0-100)'
    )
    
    # Status
    is_active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='Active templates are used for verification'
    )
    is_primary = fields.Boolean(
        string='Primary Template',
        default=False,
        tracking=True,
        help='Primary template for this biometric type'
    )
    
    # Enrollment
    enrolled_date = fields.Datetime(
        string='Enrolled Date',
        default=fields.Datetime.now,
        readonly=True,
        tracking=True
    )
    enrolled_by = fields.Many2one(
        'res.users',
        string='Enrolled By',
        readonly=True,
        tracking=True
    )
    enrollment_location = fields.Char(
        string='Enrollment Location',
        help='GPS coordinates or location name'
    )
    enrollment_latitude = fields.Float(
        string='Enrollment Latitude',
        digits=(10, 7)
    )
    enrollment_longitude = fields.Float(
        string='Enrollment Longitude',
        digits=(10, 7)
    )
    
    # Security
    encryption_key_id = fields.Char(
        string='Encryption Key ID',
        help='ID of encryption key used'
    )
    
    # Usage tracking
    verification_count = fields.Integer(
        string='Verification Count',
        default=0,
        readonly=True,
        help='Number of successful verifications'
    )
    last_used = fields.Datetime(
        string='Last Used',
        readonly=True,
        help='Last successful verification'
    )
    last_used_location = fields.Char(
        string='Last Used Location'
    )
    
    # Notes
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this template'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='guard_id.company_id',
        store=True
    )
    
    _sql_constraints = [
        ('unique_primary_template',
         'UNIQUE(guard_id, biometric_type, is_primary)',
         'Only one primary template per biometric type per guard!'),
    ]
    
    @api.depends('guard_id', 'biometric_type', 'is_primary')
    def _compute_display_name(self):
        """Compute display name."""
        for record in self:
            if record.guard_id and record.biometric_type:
                type_name = dict(record._fields['biometric_type'].selection).get(record.biometric_type, '')
                primary = ' (Primary)' if record.is_primary else ''
                record.display_name = f"{record.guard_id.name} - {type_name}{primary}"
            else:
                record.display_name = 'New Biometric Template'
    
    @api.constrains('is_primary', 'biometric_type', 'guard_id')
    def _check_primary_template(self):
        """Ensure only one primary template per biometric type per guard."""
        for record in self:
            if record.is_primary:
                existing_primary = self.search([
                    ('guard_id', '=', record.guard_id.id),
                    ('biometric_type', '=', record.biometric_type),
                    ('is_primary', '=', True),
                    ('id', '!=', record.id)
                ], limit=1)
                
                if existing_primary:
                    raise ValidationError(_(
                        'Guard %s already has a primary %s template. '
                        'Please set the existing template as non-primary first.'
                    ) % (record.guard_id.name, dict(record._fields['biometric_type'].selection).get(record.biometric_type)))
    
    @api.constrains('quality_score')
    def _check_quality_score(self):
        """Validate quality score range."""
        for record in self:
            if record.quality_score and (record.quality_score < 0 or record.quality_score > 100):
                raise ValidationError(_('Quality score must be between 0 and 100.'))
    
    def action_set_as_primary(self):
        """Set this template as primary for the guard's biometric type."""
        self.ensure_one()
        
        # Unset existing primary
        existing_primary = self.search([
            ('guard_id', '=', self.guard_id.id),
            ('biometric_type', '=', self.biometric_type),
            ('is_primary', '=', True),
            ('id', '!=', self.id)
        ])
        existing_primary.write({'is_primary': False})
        
        # Set this as primary
        self.write({'is_primary': True})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Template Set as Primary'),
                'message': _('This template is now the primary %s template for %s.') % (
                    dict(self._fields['biometric_type'].selection).get(self.biometric_type),
                    self.guard_id.name
                ),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_deactivate(self):
        """Deactivate this template."""
        self.write({'is_active': False})
    
    def action_activate(self):
        """Activate this template."""
        self.write({'is_active': True})
    
    def action_view_verifications(self):
        """View verification history for this template."""
        self.ensure_one()
        return {
            'name': _('Verification History - %s') % self.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.biometric.verification',
            'view_mode': 'list,form',
            'domain': [
                ('guard_id', '=', self.guard_id.id),
                ('biometric_type', '=', self.biometric_type)
            ],
            'context': {
                'default_guard_id': self.guard_id.id,
                'default_biometric_type': self.biometric_type
            }
        }
    
    @api.model
    def enroll_via_api(self, guard_id, biometric_type, template_data, options=None):
        """
        Enroll biometric template via API (called from JavaScript).
        
        This method is called from the mobile app/JavaScript to enroll biometrics.
        """
        if options is None:
            options = {}
        
        guard = self.env['guard.profile'].browse(guard_id)
        if not guard.exists():
            return {'success': False, 'error': 'Guard not found'}
        
        # Process template
        processor = self.env['guard.biometric.processor']
        
        # Handle mobile device authentication result
        if isinstance(template_data, dict):
            if not template_data.get('success'):
                return {
                    'success': False,
                    'error': 'Device authentication failed',
                    'device_error': template_data.get('error')
                }
            template_data_str = f"mobile_auth_{options.get('device_id', 'unknown')}_{fields.Datetime.now().isoformat()}"
        else:
            template_data_str = template_data
        
        # Encrypt template
        encrypted_template = processor.encrypt_template(template_data_str)
        template_hash = processor.create_template_hash(template_data_str)
        
        # Calculate quality
        quality_score = options.get('quality_score')
        if quality_score is None:
            quality_score = processor.calculate_quality(template_data, biometric_type)
        
        # Check if primary exists
        existing_primary = self.search([
            ('guard_id', '=', guard_id),
            ('biometric_type', '=', biometric_type),
            ('is_primary', '=', True)
        ], limit=1)
        
        # Create template (template_data field is Binary, expects base64 string)
        # encrypted_template is already base64 encoded from processor
        template = self.create({
            'guard_id': guard_id,
            'biometric_type': biometric_type,
            'template_data': encrypted_template,  # Already base64 encoded string
            'template_hash': template_hash,
            'device_id': options.get('device_id'),
            'device_model': options.get('device_model', 'Mobile Device'),
            'quality_score': quality_score,
            'is_primary': not existing_primary,
            'enrolled_by': self.env.user.id,
            'enrollment_location': options.get('location_name'),
            'enrollment_latitude': options.get('latitude'),
            'enrollment_longitude': options.get('longitude'),
        })
        
        return {
            'success': True,
            'template_id': template.id,
            'is_primary': template.is_primary,
            'quality_score': quality_score
        }

