# -*- coding: utf-8 -*-
"""Biometric Processor Model - Wrapper for biometric processing service."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..common.biometric_processor import BiometricProcessor
import logging

_logger = logging.getLogger(__name__)


class GuardBiometricProcessor(models.AbstractModel):
    """Biometric processing service accessible via Odoo models."""
    
    _name = 'guard.biometric.processor'
    _description = 'Biometric Processor Service'
    
    def get_processor(self):
        """Get biometric processor instance."""
        return BiometricProcessor(self.env)
    
    @api.model
    def encrypt_template(self, template_data):
        """Encrypt biometric template."""
        processor = self.get_processor()
        return processor.encrypt_template(template_data)
    
    @api.model
    def decrypt_template(self, encrypted_template):
        """Decrypt biometric template."""
        processor = self.get_processor()
        return processor.decrypt_template(encrypted_template)
    
    @api.model
    def create_template_hash(self, template_data):
        """Create template hash."""
        processor = self.get_processor()
        return processor.create_template_hash(template_data)
    
    @api.model
    def match_biometric(self, biometric_type, captured_data, stored_template, threshold=None):
        """
        Match biometric data.
        
        Args:
            biometric_type: 'fingerprint', 'facial', 'voice'
            captured_data: Raw captured biometric data
            stored_template: Encrypted template from database
            threshold: Matching threshold (optional, uses system default)
        
        Returns:
            tuple: (matched: bool, confidence: float)
        """
        processor = self.get_processor()
        
        # Get threshold from system parameters if not provided
        if threshold is None:
            threshold_param = self.env['ir.config_parameter'].sudo().get_param(
                f'guardpro.biometric_threshold_{biometric_type}',
                self.env['ir.config_parameter'].sudo().get_param(
                    'guardpro.biometric_threshold', 0.75
                )
            )
            threshold = float(threshold_param)
        
        if biometric_type == 'fingerprint':
            return processor.match_fingerprint(captured_data, stored_template, threshold)
        elif biometric_type == 'facial':
            return processor.match_facial(captured_data, stored_template, threshold)
        elif biometric_type == 'voice':
            return processor.match_voice(captured_data, stored_template, threshold)
        else:
            raise ValidationError(_('Unsupported biometric type: %s') % biometric_type)
    
    @api.model
    def calculate_quality(self, biometric_data, biometric_type):
        """Calculate quality score for biometric data."""
        processor = self.get_processor()
        return processor.calculate_quality_score(biometric_data, biometric_type)
    
    @api.model
    def verify_biometric(self, guard_id, biometric_type, captured_data,
                        verification_purpose='checkin', device_id=None, **kwargs):
        """
        Verify guard biometric and create verification log.
        
        Args:
            guard_id: Guard profile ID
            biometric_type: Type of biometric
            captured_data: Captured biometric data
            verification_purpose: Purpose of verification
            device_id: Device identifier
            **kwargs: Additional context (latitude, longitude, etc.)
        
        Returns:
            dict: Verification result with success, confidence, verification_id
        """
        guard = self.env['guard.profile'].browse(guard_id)
        if not guard.exists():
            return {
                'success': False,
                'verified': False,
                'error': 'Guard not found'
            }
        
        # Get guard's active biometric templates
        templates = self.env['guard.biometric.template'].search([
            ('guard_id', '=', guard_id),
            ('biometric_type', '=', biometric_type),
            ('is_active', '=', True)
        ], order='is_primary desc, quality_score desc')
        
        if not templates:
            return {
                'success': False,
                'verified': False,
                'error': 'No biometric template found for guard'
            }
        
        # Try to match with templates
        best_match = None
        best_confidence = 0.0
        matched_template = None
        
        for template in templates:
            try:
                # Binary field stores base64 string, need to decode and decrypt
                import base64
                processor = self.get_processor()
                
                # template_data from Binary field is base64 string
                if isinstance(template.template_data, str):
                    # Decode from base64 to get encrypted bytes
                    encrypted_data = base64.b64decode(template.template_data)
                else:
                    encrypted_data = template.template_data
                
                # Decrypt to get original template data
                stored_template = processor.decrypt_template(encrypted_data)
                
                matched, confidence = self.match_biometric(
                    biometric_type=biometric_type,
                    captured_data=captured_data,
                    stored_template=stored_template
                )
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = matched
                    matched_template = template
                    
            except Exception as e:
                _logger.error('Template matching error for template %s: %s', template.id, str(e))
                continue
        
        # Determine if verification passed
        threshold = float(self.env['ir.config_parameter'].sudo().get_param(
            f'guardpro.biometric_threshold_{biometric_type}',
            self.env['ir.config_parameter'].sudo().get_param(
                'guardpro.biometric_threshold', 0.75
            )
        ))
        
        verified = best_match and best_confidence >= threshold
        
        # Create verification log
        verification_log = self.env['guard.biometric.verification'].create({
            'guard_id': guard_id,
            'biometric_type': biometric_type,
            'verification_result': 'success' if verified else 'failed',
            'confidence_score': best_confidence * 100,
            'verification_purpose': verification_purpose,
            'device_id': device_id,
            'device_model': kwargs.get('device_model'),
            'device_type': kwargs.get('device_type', 'mobile'),
            'ip_address': kwargs.get('ip_address'),
            'user_agent': kwargs.get('user_agent'),
            'latitude': kwargs.get('latitude'),
            'longitude': kwargs.get('longitude'),
            'location_name': kwargs.get('location_name'),
            'error_message': kwargs.get('error_message') if not verified else False,
            'is_suspicious': best_confidence < threshold * 0.5 if best_confidence else False,
            'template_id': matched_template.id if matched_template else False,
            'attendance_id': kwargs.get('attendance_id'),
            'shift_id': kwargs.get('shift_id'),
            'tour_log_id': kwargs.get('tour_log_id'),
            'incident_id': kwargs.get('incident_id'),
        })

        return {
            'success': True,
            'verified': verified,
            'confidence': best_confidence,
            'verification_id': verification_log.id,
            'template_id': matched_template.id if matched_template else False
        }
    
    @api.model
    def verify_via_api(self, guard_id, biometric_type, captured_data, purpose, options=None):
        """
        Verify biometric via API (called from JavaScript).
        
        This is a convenience method for API calls.
        """
        if options is None:
            options = {}
        
        return self.verify_biometric(
            guard_id=guard_id,
            biometric_type=biometric_type,
            captured_data=captured_data,
            verification_purpose=purpose,
            device_id=options.get('device_id'),
            device_type=options.get('device_type', 'mobile'),
            latitude=options.get('latitude'),
            longitude=options.get('longitude'),
            location_name=options.get('location_name'),
            attendance_id=options.get('attendance_id'),
            shift_id=options.get('shift_id'),
            **options
        )

