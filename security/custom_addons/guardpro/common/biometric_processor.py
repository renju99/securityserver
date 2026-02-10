# -*- coding: utf-8 -*-
"""Biometric Processing Service - Encryption and Matching."""

import hashlib
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2SHA256
import os

_logger = logging.getLogger(__name__)


class BiometricProcessor:
    """Process and match biometric data."""
    
    def __init__(self, env):
        self.env = env
        self.encryption_key = self._get_encryption_key()
    
    def _get_encryption_key(self):
        """Get or generate encryption key for biometric templates."""
        # Store key in system parameters (encrypted)
        key_param = self.env['ir.config_parameter'].sudo().get_param(
            'guardpro.biometric_encryption_key'
        )
        
        if not key_param:
            # Generate new key
            key = Fernet.generate_key()
            self.env['ir.config_parameter'].sudo().set_param(
                'guardpro.biometric_encryption_key',
                key.decode()
            )
            _logger.info('Generated new biometric encryption key')
            return key
        
        try:
            return key_param.encode()
        except Exception as e:
            _logger.error('Error loading encryption key: %s', str(e))
            # Generate new key if current one is invalid
            key = Fernet.generate_key()
            self.env['ir.config_parameter'].sudo().set_param(
                'guardpro.biometric_encryption_key',
                key.decode()
            )
            return key
    
    def encrypt_template(self, template_data):
        """
        Encrypt biometric template.
        
        Args:
            template_data: Raw template data (string or bytes)
        
        Returns:
            str: Base64 encoded encrypted template
        """
        try:
            f = Fernet(self.encryption_key)
            
            # Convert to bytes if string
            if isinstance(template_data, str):
                template_bytes = template_data.encode('utf-8')
            else:
                template_bytes = template_data
            
            # Encrypt
            encrypted = f.encrypt(template_bytes)
            
            # Return base64 encoded string for storage
            return base64.b64encode(encrypted).decode('utf-8')
            
        except Exception as e:
            _logger.error('Template encryption error: %s', str(e))
            raise ValueError(f'Failed to encrypt template: {str(e)}')
    
    def decrypt_template(self, encrypted_template):
        """
        Decrypt biometric template.
        
        Args:
            encrypted_template: Encrypted template (bytes from base64 decode, or base64 string)
        
        Returns:
            bytes: Decrypted template data
        """
        try:
            f = Fernet(self.encryption_key)
            
            # If it's a string, it might be base64 encoded
            if isinstance(encrypted_template, str):
                # Try to decode from base64
                try:
                    encrypted_bytes = base64.b64decode(encrypted_template)
                except:
                    # Not base64, encode to bytes directly
                    encrypted_bytes = encrypted_template.encode('utf-8')
            else:
                # Already bytes
                encrypted_bytes = encrypted_template
            
            # Decrypt
            decrypted = f.decrypt(encrypted_bytes)
            
            return decrypted
            
        except Exception as e:
            _logger.error('Template decryption error: %s', str(e))
            raise ValueError(f'Failed to decrypt template: {str(e)}')
    
    def create_template_hash(self, template_data):
        """
        Create hash for template lookup.
        
        Args:
            template_data: Raw template data
        
        Returns:
            str: SHA256 hash
        """
        if isinstance(template_data, str):
            template_bytes = template_data.encode('utf-8')
        else:
            template_bytes = template_data
        
        return hashlib.sha256(template_bytes).hexdigest()
    
    def match_fingerprint(self, captured_data, stored_template, threshold=0.7):
        """
        Match fingerprint data (simplified - for mobile device sensors).
        
        For mobile devices (Touch ID, Android fingerprint), we rely on the
        device's native authentication. The device returns a success/failure
        and we store that result.
        
        For USB scanners, this would integrate with device SDKs.
        
        Args:
            captured_data: Raw fingerprint data from scanner (or device auth result)
            stored_template: Encrypted template from database
            threshold: Matching threshold (0-1)
        
        Returns:
            tuple: (matched: bool, confidence: float)
        """
        try:
            # For mobile device authentication (WebAuthn, Touch ID, etc.)
            # The device handles matching and returns success/failure
            # We just verify the device authentication was successful
            
            # If captured_data is a dict with 'success' key (from mobile device)
            if isinstance(captured_data, dict):
                if captured_data.get('success'):
                    # Device authenticated successfully
                    confidence = captured_data.get('confidence', 0.95)
                    return True, confidence
                else:
                    return False, 0.0
            
            # For USB scanners or raw fingerprint data
            # This would integrate with fingerprint SDKs
            # For now, return a simplified match
            # In production, use: pyfingerprint, fprint, or device SDK
            
            # Decrypt template for comparison
            template_data = self.decrypt_template(stored_template)
            
            # Simplified matching (in production, use proper fingerprint matching)
            # This is a placeholder - actual implementation would use fingerprint SDK
            if captured_data and template_data:
                # Basic comparison (not real fingerprint matching)
                # Real implementation would use fingerprint minutiae matching
                return True, 0.85  # Placeholder confidence
            
            return False, 0.0
            
        except Exception as e:
            _logger.error('Fingerprint matching error: %s', str(e))
            return False, 0.0
    
    def match_facial(self, captured_image, stored_template, threshold=0.85):
        """
        Match facial recognition data.
        
        Args:
            captured_image: Image data (base64 string or file path)
            stored_template: Encrypted facial template
            threshold: Matching threshold (0-1)
        
        Returns:
            tuple: (matched: bool, confidence: float)
        """
        try:
            # Try to import face_recognition library
            try:
                import face_recognition
                import numpy as np
                from PIL import Image
                import io
            except ImportError:
                _logger.warning('face_recognition library not installed. Using simplified matching.')
                # Fallback: basic image comparison
                return self._simple_image_match(captured_image, stored_template, threshold)
            
            # Decrypt template
            template_data = self.decrypt_template(stored_template)
            stored_encoding = np.frombuffer(template_data, dtype=np.float64)
            
            # Process captured image
            if isinstance(captured_image, str):
                # Base64 image
                if captured_image.startswith('data:image'):
                    # Remove data URL prefix
                    captured_image = captured_image.split(',')[1]
                
                image_data = base64.b64decode(captured_image)
                image = Image.open(io.BytesIO(image_data))
            else:
                # File path
                image = Image.open(captured_image)
            
            # Convert to RGB
            rgb_image = image.convert('RGB')
            rgb_array = np.array(rgb_image)
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(rgb_array)
            
            if not face_encodings:
                _logger.warning('No face detected in image')
                return False, 0.0
            
            # Compare with stored template
            distances = face_recognition.face_distance([stored_encoding], face_encodings[0])
            confidence = 1 - distances[0]
            
            return confidence >= threshold, confidence
            
        except Exception as e:
            _logger.error('Facial matching error: %s', str(e))
            return False, 0.0
    
    def _simple_image_match(self, captured_image, stored_template, threshold):
        """Simplified image matching fallback."""
        # Basic image hash comparison (not real facial recognition)
        # This is a placeholder until face_recognition is installed
        try:
            import hashlib
            from PIL import Image
            import io
            
            # Process captured image
            if isinstance(captured_image, str):
                if captured_image.startswith('data:image'):
                    captured_image = captured_image.split(',')[1]
                image_data = base64.b64decode(captured_image)
                image = Image.open(io.BytesIO(image_data))
            else:
                image = Image.open(captured_image)
            
            # Simple hash comparison (not secure, just for basic matching)
            image_hash = hashlib.md5(image.tobytes()).hexdigest()
            template_hash = hashlib.md5(self.decrypt_template(stored_template)).hexdigest()
            
            # Very basic matching (not recommended for production)
            if image_hash == template_hash:
                return True, 0.9
            
            return False, 0.0
            
        except Exception as e:
            _logger.error('Simple image match error: %s', str(e))
            return False, 0.0
    
    def match_voice(self, captured_audio, stored_template, threshold=0.75):
        """
        Match voice recognition data.
        
        Args:
            captured_audio: Audio data (WAV file or base64)
            stored_template: Encrypted voice template
            threshold: Matching threshold (0-1)
        
        Returns:
            tuple: (matched: bool, confidence: float)
        """
        try:
            # Voice recognition would require specialized libraries
            # For now, return placeholder
            # In production, use: pyAudioAnalysis, speech_recognition, or commercial SDKs
            
            _logger.warning('Voice recognition not fully implemented. Using placeholder.')
            
            # Placeholder implementation
            # Real implementation would extract voice features (MFCC, etc.)
            # and compare with stored template
            
            return False, 0.0
            
        except Exception as e:
            _logger.error('Voice matching error: %s', str(e))
            return False, 0.0
    
    def calculate_quality_score(self, biometric_data, biometric_type):
        """
        Calculate quality score for biometric data.
        
        Args:
            biometric_data: Raw biometric data
            biometric_type: Type of biometric
        
        Returns:
            float: Quality score (0-100)
        """
        try:
            if biometric_type == 'facial':
                # For facial: check image quality, face detection, etc.
                try:
                    import face_recognition
                    from PIL import Image
                    import io
                    import numpy as np
                    
                    # Process image
                    if isinstance(biometric_data, str):
                        if biometric_data.startswith('data:image'):
                            biometric_data = biometric_data.split(',')[1]
                        image_data = base64.b64decode(biometric_data)
                        image = Image.open(io.BytesIO(image_data))
                    else:
                        image = Image.open(biometric_data)
                    
                    rgb_array = np.array(image.convert('RGB'))
                    
                    # Check if face is detected
                    face_locations = face_recognition.face_locations(rgb_array)
                    if not face_locations:
                        return 0.0
                    
                    # Check image quality (resolution, brightness, etc.)
                    height, width = rgb_array.shape[:2]
                    resolution_score = min(100, (width * height) / 10000)  # Normalize
                    
                    # Check brightness
                    brightness = np.mean(rgb_array)
                    brightness_score = 100 - abs(brightness - 128) / 128 * 100
                    
                    # Overall quality
                    quality = (resolution_score + brightness_score) / 2
                    return min(100, max(0, quality))
                    
                except ImportError:
                    # Fallback: basic quality check
                    return 70.0
            
            elif biometric_type == 'fingerprint':
                # For fingerprint: check quality based on device feedback
                # Mobile devices provide quality feedback
                if isinstance(biometric_data, dict):
                    return biometric_data.get('quality', 80.0)
                return 80.0  # Default quality
            
            else:
                return 75.0  # Default quality
                
        except Exception as e:
            _logger.error('Quality calculation error: %s', str(e))
            return 50.0  # Low quality on error

