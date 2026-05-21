# -*- coding: utf-8 -*-
"""Image Optimization Utility for Photo Uploads."""

import io
import base64
import logging
from PIL import Image

_logger = logging.getLogger(__name__)


class ImageOptimizer:
    """
    Utility class for optimizing images uploaded to the system.
    
    Reduces image file sizes while maintaining quality suitable for PDF reports.
    Target: ~200KB per image, 1200px max dimension for high-quality PDF rendering.
    """
    
    # Image optimization settings
    MAX_DIMENSION = 1200  # Max width or height in pixels
    JPEG_QUALITY = 85  # JPEG compression quality (1-100)
    PNG_OPTIMIZE = True  # Enable PNG optimization
    
    # Format-specific settings
    FORMAT_SETTINGS = {
        'JPEG': {'quality': JPEG_QUALITY, 'optimize': True},
        'PNG': {'optimize': PNG_OPTIMIZE, 'compress_level': 6},
        'WEBP': {'quality': JPEG_QUALITY, 'method': 6}
    }
    
    @classmethod
    def optimize_image(cls, image_data, max_dimension=None, target_format='JPEG'):
        """
        Optimize an image for storage and PDF rendering.
        
        Args:
            image_data: Base64 encoded image data or binary image data
            max_dimension: Maximum dimension (width or height) in pixels
            target_format: Output format ('JPEG', 'PNG', 'WEBP')
            
        Returns:
            Base64 encoded optimized image data
        """
        if not image_data:
            return image_data
        
        try:
            # Decode base64 if needed
            if isinstance(image_data, str):
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data
            
            # Open image
            img = Image.open(io.BytesIO(image_bytes))
            
            # Convert RGBA to RGB for JPEG
            if target_format == 'JPEG' and img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')
            
            # Get original dimensions
            original_width, original_height = img.size
            original_size = len(image_bytes)
            
            # Calculate new dimensions
            max_dim = max_dimension or cls.MAX_DIMENSION
            if original_width > max_dim or original_height > max_dim:
                # Calculate resize ratio
                ratio = min(max_dim / original_width, max_dim / original_height)
                new_width = int(original_width * ratio)
                new_height = int(original_height * ratio)
                
                # Resize with high-quality resampling
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                _logger.info(
                    'Resized image from %dx%d to %dx%d',
                    original_width, original_height, new_width, new_height
                )
            
            # Save optimized image
            output = io.BytesIO()
            save_kwargs = cls.FORMAT_SETTINGS.get(target_format, {})
            img.save(output, format=target_format, **save_kwargs)
            
            # Get optimized data
            optimized_bytes = output.getvalue()
            optimized_size = len(optimized_bytes)
            
            # Calculate compression ratio
            compression_ratio = (1 - optimized_size / original_size) * 100 if original_size > 0 else 0
            
            _logger.info(
                'Image optimized: %d KB -> %d KB (%.1f%% reduction)',
                original_size // 1024,
                optimized_size // 1024,
                compression_ratio
            )
            
            # Return base64-encoded string (Odoo Binary fields expect str, not bytes)
            encoded = base64.b64encode(optimized_bytes)
            return encoded.decode('ascii') if isinstance(encoded, bytes) else encoded

        except Exception as e:
            _logger.error('Error optimizing image: %s', str(e))
            # Return original if optimization fails (always as str)
            if isinstance(image_data, str):
                return image_data
            if isinstance(image_data, bytes):
                return base64.b64encode(image_data).decode('ascii')
            return image_data
    
    @classmethod
    def optimize_multiple(cls, image_data_list, max_dimension=None, target_format='JPEG'):
        """
        Optimize multiple images.
        
        Args:
            image_data_list: List of base64 encoded images
            max_dimension: Maximum dimension for all images
            target_format: Output format
            
        Returns:
            List of optimized base64 encoded images
        """
        return [
            cls.optimize_image(img_data, max_dimension, target_format)
            for img_data in image_data_list
        ]
    
    @classmethod
    def get_image_info(cls, image_data):
        """
        Get information about an image.
        
        Args:
            image_data: Base64 encoded image data
            
        Returns:
            dict with image info (format, size, dimensions)
        """
        try:
            if isinstance(image_data, str):
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data
            
            img = Image.open(io.BytesIO(image_bytes))
            
            return {
                'format': img.format,
                'mode': img.mode,
                'size': len(image_bytes),
                'width': img.size[0],
                'height': img.size[1],
                'size_kb': len(image_bytes) // 1024
            }
        except Exception as e:
            _logger.error('Error getting image info: %s', str(e))
            return None
    
    @classmethod
    def validate_image_size(cls, image_data, max_size_mb=10):
        """
        Validate if image is within acceptable size limit.
        
        Args:
            image_data: Base64 encoded image
            max_size_mb: Maximum size in megabytes
            
        Returns:
            tuple (is_valid, actual_size_mb)
        """
        try:
            if isinstance(image_data, str):
                size_bytes = len(base64.b64decode(image_data))
            else:
                size_bytes = len(image_data)
            
            size_mb = size_bytes / (1024 * 1024)
            return (size_mb <= max_size_mb, size_mb)
        except Exception as e:
            _logger.error('Error validating image size: %s', str(e))
            return (False, 0)











