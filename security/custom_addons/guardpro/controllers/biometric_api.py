# -*- coding: utf-8 -*-
"""Biometric API Controllers for GuardLink."""

from odoo import http, fields
from odoo.http import request
import logging
import base64

_logger = logging.getLogger(__name__)


class GuardLinkBiometricAPI(http.Controller):
    """API endpoints for biometric enrollment and verification."""
    
    @http.route('/guardpro/api/biometric/enroll', type='json', auth='user', methods=['POST'], csrf=False)
    def enroll_biometric(self, guard_id, biometric_type, template_data,
                        device_id=None, device_model=None, quality_score=None,
                        latitude=None, longitude=None, location_name=None, **kwargs):
        """
        Enroll guard biometric template.
        
        Args:
            guard_id: Guard profile ID
            biometric_type: 'fingerprint', 'facial', 'voice'
            template_data: Base64 encoded biometric data or dict (for mobile devices)
            device_id: Device identifier
            device_model: Device model name
            quality_score: Quality of captured template (0-100)
            latitude: Enrollment location latitude
            longitude: Enrollment location longitude
            location_name: Enrollment location name
        
        Returns:
            dict: Enrollment result
        """
        try:
            # Verify user has permission (guards can enroll themselves, supervisors can enroll any guard)
            current_user = request.env.user
            guard = request.env['guard.profile'].browse(guard_id)
            
            if not guard.exists():
                return {'success': False, 'error': 'Guard not found'}
            
            # Check permission
            current_guard = request.env['guard.profile'].search([
                ('user_id', '=', current_user.id)
            ], limit=1)
            
            # Guards can only enroll themselves, supervisors can enroll any guard
            supervisor_group = request.env.ref('guardpro.group_guardpro_supervisor', raise_if_not_found=False)
            is_supervisor = supervisor_group and current_user in supervisor_group.users
            
            if not is_supervisor and (not current_guard or current_guard.id != guard_id):
                return {'success': False, 'error': 'Permission denied. You can only enroll your own biometrics.'}
            
            # Process template data
            processor = request.env['guard.biometric.processor']
            
            # Handle mobile device authentication result (dict format)
            if isinstance(template_data, dict):
                # Mobile device returned authentication result
                if not template_data.get('success'):
                    return {
                        'success': False,
                        'error': 'Device authentication failed',
                        'device_error': template_data.get('error')
                    }
                
                # For mobile devices, we store a reference token, not the actual biometric
                # The device handles the biometric matching
                template_data_str = f"mobile_auth_{device_id}_{fields.Datetime.now().isoformat()}"
            else:
                # Raw biometric data (for USB scanners, cameras, etc.)
                template_data_str = template_data
            
            # Encrypt template
            encrypted_template = processor.encrypt_template(template_data_str)
            template_hash = processor.create_template_hash(template_data_str)
            
            # Calculate quality if not provided
            if quality_score is None:
                quality_score = processor.calculate_quality(template_data, biometric_type)
            
            # Check if primary template exists
            existing_primary = request.env['guard.biometric.template'].search([
                ('guard_id', '=', guard_id),
                ('biometric_type', '=', biometric_type),
                ('is_primary', '=', True)
            ], limit=1)
            
            # Create template record (template_data is Binary field, accepts base64 string)
            # encrypted_template is already base64 encoded from processor
            template = request.env['guard.biometric.template'].create({
                'guard_id': guard_id,
                'biometric_type': biometric_type,
                'template_data': encrypted_template,  # Already base64 encoded
                'template_hash': template_hash,
                'device_id': device_id,
                'device_model': device_model or 'Mobile Device',
                'quality_score': quality_score,
                'is_primary': not existing_primary,
                'enrolled_by': current_user.id,
                'enrollment_location': location_name,
                'enrollment_latitude': latitude,
                'enrollment_longitude': longitude,
            })
            
            _logger.info(
                'Biometric template enrolled: Guard %s, Type %s, Template ID %s',
                guard.name, biometric_type, template.id
            )
            
            return {
                'success': True,
                'template_id': template.id,
                'is_primary': template.is_primary,
                'quality_score': quality_score
            }
            
        except Exception as e:
            _logger.error('Biometric enrollment error: %s', str(e), exc_info=True)
            return {'success': False, 'error': str(e)}
    
    @http.route('/guardpro/api/biometric/verify', type='json', auth='user', methods=['POST'], csrf=False)
    def verify_biometric(self, guard_id, biometric_type, captured_data,
                        verification_purpose='checkin', device_id=None,
                        device_model=None, device_type='mobile',
                        latitude=None, longitude=None, location_name=None,
                        attendance_id=None, shift_id=None, **kwargs):
        """
        Verify guard biometric.
        
        Args:
            guard_id: Guard profile ID
            biometric_type: 'fingerprint', 'facial', 'voice'
            captured_data: Base64 encoded biometric data or dict (for mobile devices)
            verification_purpose: 'checkin', 'checkout', 'access_control', etc.
            device_id: Device identifier
            device_model: Device model
            device_type: 'mobile', 'usb_scanner', 'webcam', etc.
            latitude: Verification location latitude
            longitude: Verification location longitude
            location_name: Verification location name
            attendance_id: Related attendance ID (optional)
            shift_id: Related shift ID (optional)
        
        Returns:
            dict: Verification result
        """
        try:
            # Get current user info
            current_user = request.env.user
            ip_address = request.httprequest.remote_addr
            user_agent = request.httprequest.user_agent.string
            
            # Verify guard
            guard = request.env['guard.profile'].browse(guard_id)
            if not guard.exists():
                return {'success': False, 'verified': False, 'error': 'Guard not found'}
            
            # Verify permission (guards can verify themselves, supervisors can verify any guard)
            current_guard = request.env['guard.profile'].search([
                ('user_id', '=', current_user.id)
            ], limit=1)
            
            supervisor_group = request.env.ref('guardpro.group_guardpro_supervisor', raise_if_not_found=False)
            is_supervisor = supervisor_group and current_user in supervisor_group.users
            
            if not is_supervisor and (not current_guard or current_guard.id != guard_id):
                return {'success': False, 'verified': False, 'error': 'Permission denied'}
            
            # Process verification
            processor = request.env['guard.biometric.processor']
            
            result = processor.verify_biometric(
                guard_id=guard_id,
                biometric_type=biometric_type,
                captured_data=captured_data,
                verification_purpose=verification_purpose,
                device_id=device_id,
                device_model=device_model,
                device_type=device_type,
                ip_address=ip_address,
                user_agent=user_agent,
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                attendance_id=attendance_id,
                shift_id=shift_id,
                **kwargs
            )
            
            return result
            
        except Exception as e:
            _logger.error('Biometric verification error: %s', str(e), exc_info=True)
            return {'success': False, 'verified': False, 'error': str(e)}
    
    @http.route('/guardpro/api/biometric/templates', type='json', auth='user')
    def get_guard_templates(self, guard_id=None, biometric_type=None, **kwargs):
        """Get biometric templates for guard."""
        try:
            # If guard_id not provided, get current user's guard
            if not guard_id:
                current_guard = request.env['guard.profile'].search([
                    ('user_id', '=', request.env.user.id)
                ], limit=1)
                if not current_guard:
                    return {'success': False, 'error': 'Guard profile not found'}
                guard_id = current_guard.id
            
            guard = request.env['guard.profile'].browse(guard_id)
            if not guard.exists():
                return {'success': False, 'error': 'Guard not found'}
            
            # Check permission
            current_guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            
            supervisor_group = request.env.ref('guardpro.group_guardpro_supervisor', raise_if_not_found=False)
            is_supervisor = supervisor_group and request.env.user in supervisor_group.users
            
            if not is_supervisor and (not current_guard or current_guard.id != guard_id):
                return {'success': False, 'error': 'Permission denied'}
            
            # Build domain
            domain = [('guard_id', '=', guard_id)]
            if biometric_type:
                domain.append(('biometric_type', '=', biometric_type))
            
            templates = request.env['guard.biometric.template'].search(domain)
            
            templates_list = []
            for template in templates:
                templates_list.append({
                    'id': template.id,
                    'biometric_type': template.biometric_type,
                    'device_model': template.device_model,
                    'quality_score': template.quality_score,
                    'is_active': template.is_active,
                    'is_primary': template.is_primary,
                    'enrolled_date': template.enrolled_date.isoformat() if template.enrolled_date else None,
                    'verification_count': template.verification_count,
                    'last_used': template.last_used.isoformat() if template.last_used else None
                })
            
            return {
                'success': True,
                'templates': templates_list,
                'total': len(templates_list)
            }
            
        except Exception as e:
            _logger.error('Error getting templates: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    @http.route('/guardpro/api/biometric/checkin', type='json', auth='user', methods=['POST'], csrf=False)
    def biometric_checkin(self, shift_id, biometric_type, captured_data,
                         device_id=None, latitude=None, longitude=None, **kwargs):
        """
        Check-in guard with biometric verification.
        
        Args:
            shift_id: Shift ID
            biometric_type: Type of biometric
            captured_data: Captured biometric data
            device_id: Device identifier
            latitude: GPS latitude
            longitude: GPS longitude
        
        Returns:
            dict: Check-in result
        """
        try:
            # Get shift
            shift = request.env['guard.shift'].browse(shift_id)
            if not shift.exists():
                return {'success': False, 'error': 'Shift not found'}
            
            # Verify biometric
            verification_result = request.env['guard.biometric.processor'].verify_biometric(
                guard_id=shift.guard_id.id,
                biometric_type=biometric_type,
                captured_data=captured_data,
                verification_purpose='checkin',
                device_id=device_id,
                device_type='mobile',
                latitude=latitude,
                longitude=longitude,
                shift_id=shift_id
            )
            
            if not verification_result.get('verified'):
                return {
                    'success': False,
                    'verified': False,
                    'error': 'Biometric verification failed',
                    'confidence': verification_result.get('confidence', 0),
                    'verification_id': verification_result.get('verification_id')
                }
            
            # Proceed with check-in
            checkin_result = shift.action_checkin(
                latitude=latitude,
                longitude=longitude,
                **kwargs
            )
            
            return {
                'success': True,
                'verified': True,
                'confidence': verification_result.get('confidence', 0),
                'verification_id': verification_result.get('verification_id'),
                'checkin_result': checkin_result
            }
            
        except Exception as e:
            _logger.error('Biometric check-in error: %s', str(e), exc_info=True)
            return {'success': False, 'error': str(e)}
    
    @http.route('/guardpro/api/biometric/checkout', type='json', auth='user', methods=['POST'], csrf=False)
    def biometric_checkout(self, shift_id, biometric_type, captured_data,
                          device_id=None, latitude=None, longitude=None, **kwargs):
        """
        Check-out guard with biometric verification.
        
        Args:
            shift_id: Shift ID
            biometric_type: Type of biometric
            captured_data: Captured biometric data
            device_id: Device identifier
            latitude: GPS latitude
            longitude: GPS longitude
        
        Returns:
            dict: Check-out result
        """
        try:
            # Get shift
            shift = request.env['guard.shift'].browse(shift_id)
            if not shift.exists():
                return {'success': False, 'error': 'Shift not found'}
            
            # Verify biometric
            verification_result = request.env['guard.biometric.processor'].verify_biometric(
                guard_id=shift.guard_id.id,
                biometric_type=biometric_type,
                captured_data=captured_data,
                verification_purpose='checkout',
                device_id=device_id,
                device_type='mobile',
                latitude=latitude,
                longitude=longitude,
                shift_id=shift_id
            )
            
            if not verification_result.get('verified'):
                return {
                    'success': False,
                    'verified': False,
                    'error': 'Biometric verification failed',
                    'confidence': verification_result.get('confidence', 0),
                    'verification_id': verification_result.get('verification_id')
                }
            
            # Proceed with check-out
            checkout_result = shift.action_checkout(
                latitude=latitude,
                longitude=longitude,
                complete_shift=kwargs.get('complete_shift', False)
            )
            
            return {
                'success': True,
                'verified': True,
                'confidence': verification_result.get('confidence', 0),
                'verification_id': verification_result.get('verification_id'),
                'checkout_result': checkout_result
            }
            
        except Exception as e:
            _logger.error('Biometric check-out error: %s', str(e), exc_info=True)
            return {'success': False, 'error': str(e)}

