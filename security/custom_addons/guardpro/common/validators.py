# -*- coding: utf-8 -*-
"""Input Validation Helpers for API Endpoints.

This module provides validation functions for API input data
to ensure data integrity and security.
"""

from odoo.exceptions import UserError, AccessError
from .constants import (
    GPS_LATITUDE_MIN, GPS_LATITUDE_MAX,
    GPS_LONGITUDE_MIN, GPS_LONGITUDE_MAX,
    MAX_NOTES_LENGTH, MAX_DESCRIPTION_LENGTH
)


def validate_required_params(params, required_fields):
    """
    Validate that all required parameters are present.
    
    Args:
        params (dict): Parameters to validate
        required_fields (list): List of required field names
        
    Returns:
        tuple: (is_valid, error_message)
        
    Example:
        >>> valid, error = validate_required_params(
        ...     {'shift_id': 1},
        ...     ['shift_id', 'latitude', 'longitude']
        ... )
        >>> if not valid:
        ...     return {'success': False, 'error': error}
    """
    missing = []
    for field in required_fields:
        if field not in params or params[field] is None:
            missing.append(field)
    
    if missing:
        return False, f"Missing required parameters: {', '.join(missing)}"
    
    return True, None


def validate_id(value, field_name='ID'):
    """
    Validate that a value is a valid positive integer ID.
    
    Args:
        value: Value to validate
        field_name (str): Name of the field (for error messages)
        
    Returns:
        tuple: (is_valid, error_message, parsed_value)
        
    Example:
        >>> valid, error, id_value = validate_id('123', 'shift_id')
        >>> if not valid:
        ...     return {'success': False, 'error': error}
    """
    if value is None:
        return False, f"{field_name} is required", None
    
    try:
        id_value = int(value)
        if id_value <= 0:
            return False, f"{field_name} must be a positive integer", None
        return True, None, id_value
    except (ValueError, TypeError):
        return False, f"Invalid {field_name} format", None


def validate_gps_coordinates(latitude, longitude, required=False):
    """
    Validate GPS coordinates.
    
    Args:
        latitude: Latitude value to validate
        longitude: Longitude value to validate
        required (bool): Whether coordinates are required
        
    Returns:
        tuple: (is_valid, error_message)
        
    Example:
        >>> valid, error = validate_gps_coordinates(25.2048, 55.2708)
        >>> if not valid:
        ...     return {'success': False, 'error': error}
    """
    # Check if coordinates are provided
    if latitude is None or longitude is None:
        if required:
            return False, "GPS coordinates are required"
        else:
            return True, None  # Optional and not provided
    
    # Validate types
    if not isinstance(latitude, (int, float)):
        return False, "Latitude must be a number"
    
    if not isinstance(longitude, (int, float)):
        return False, "Longitude must be a number"
    
    # Validate ranges
    if not (GPS_LATITUDE_MIN <= latitude <= GPS_LATITUDE_MAX):
        return False, f"Latitude must be between {GPS_LATITUDE_MIN} and {GPS_LATITUDE_MAX}"
    
    if not (GPS_LONGITUDE_MIN <= longitude <= GPS_LONGITUDE_MAX):
        return False, f"Longitude must be between {GPS_LONGITUDE_MIN} and {GPS_LONGITUDE_MAX}"
    
    return True, None


def validate_string_length(value, field_name, max_length=None, required=False):
    """
    Validate string length.
    
    Args:
        value: String value to validate
        field_name (str): Name of the field (for error messages)
        max_length (int): Maximum allowed length
        required (bool): Whether field is required
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if value is None or (isinstance(value, str) and value.strip() == ''):
        if required:
            return False, f"{field_name} is required"
        else:
            return True, None
    
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    
    if max_length and len(value) > max_length:
        return False, f"{field_name} exceeds maximum length of {max_length} characters"
    
    return True, None


def validate_selection(value, allowed_values, field_name):
    """
    Validate that a value is one of the allowed options.
    
    Args:
        value: Value to validate
        allowed_values (list): List of allowed values
        field_name (str): Name of the field (for error messages)
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if value not in allowed_values:
        return False, f"Invalid {field_name}. Must be one of: {', '.join(str(v) for v in allowed_values)}"
    
    return True, None


def validate_boolean(value, field_name):
    """
    Validate boolean value.
    
    Args:
        value: Value to validate
        field_name (str): Name of the field (for error messages)
        
    Returns:
        tuple: (is_valid, error_message, parsed_value)
    """
    if value is None:
        return True, None, False  # Default to False
    
    if isinstance(value, bool):
        return True, None, value
    
    # Try to parse string values
    if isinstance(value, str):
        if value.lower() in ('true', '1', 'yes'):
            return True, None, True
        elif value.lower() in ('false', '0', 'no'):
            return True, None, False
    
    # Try to parse numeric values
    if isinstance(value, (int, float)):
        return True, None, bool(value)
    
    return False, f"Invalid {field_name} value", None


def sanitize_html(html_content):
    """
    Sanitize HTML content to prevent XSS attacks.
    
    Args:
        html_content (str): HTML content to sanitize
        
    Returns:
        str: Sanitized HTML
        
    Note:
        Odoo's Html field automatically sanitizes, but this provides
        additional security for API inputs.
    """
    if not html_content:
        return html_content
    
    # Odoo provides HTML sanitization
    from odoo.tools import html_sanitize
    return html_sanitize(html_content)


def validate_shift_checkin_params(params):
    """
    Validate parameters for shift check-in API.
    
    Args:
        params (dict): Request parameters
        
    Returns:
        tuple: (is_valid, error_message, validated_params)
        
    Example:
        >>> valid, error, validated = validate_shift_checkin_params(request.params)
        >>> if not valid:
        ...     return {'success': False, 'error': error}
    """
    # Validate shift_id
    valid, error, shift_id = validate_id(params.get('shift_id'), 'shift_id')
    if not valid:
        return False, error, None
    
    # Validate GPS coordinates (optional but recommended)
    latitude = params.get('latitude')
    longitude = params.get('longitude')
    
    if latitude is not None or longitude is not None:
        valid, error = validate_gps_coordinates(latitude, longitude, required=False)
        if not valid:
            return False, error, None
    
    return True, None, {
        'shift_id': shift_id,
        'latitude': latitude,
        'longitude': longitude
    }


def validate_incident_create_params(params):
    """
    Validate parameters for incident creation API.
    
    Args:
        params (dict): Request parameters
        
    Returns:
        tuple: (is_valid, error_message, validated_params)
    """
    # Required fields (site_id made optional to allow reporting without active shift)
    required = ['title', 'description', 'category_id']
    valid, error = validate_required_params(params, required)
    if not valid:
        return False, error, None
    
    # Validate category_id
    valid, error, category_id = validate_id(params.get('category_id'), 'category_id')
    if not valid:
        return False, error, None
    
    # Validate site_id if provided (optional)
    site_id = params.get('site_id')
    if site_id:
        valid, error, site_id = validate_id(site_id, 'site_id')
        if not valid:
            return False, error, None
    
    # Validate shift_id if provided (optional)
    shift_id = params.get('shift_id')
    if shift_id:
        valid, error, shift_id = validate_id(shift_id, 'shift_id')
        if not valid:
            return False, error, None
    
    # Validate strings
    valid, error = validate_string_length(
        params.get('title'), 'title',
        max_length=200, required=True
    )
    if not valid:
        return False, error, None
    
    valid, error = validate_string_length(
        params.get('description'), 'description',
        max_length=MAX_DESCRIPTION_LENGTH, required=True
    )
    if not valid:
        return False, error, None
    
    # Validate severity
    severity = params.get('severity', 'medium')
    valid, error = validate_selection(
        severity,
        ['low', 'medium', 'high', 'critical'],
        'severity'
    )
    if not valid:
        return False, error, None
    
    # Validate GPS coordinates (optional)
    latitude = params.get('latitude')
    longitude = params.get('longitude')
    
    if latitude is not None or longitude is not None:
        valid, error = validate_gps_coordinates(latitude, longitude, required=False)
        if not valid:
            return False, error, None
    
    # Validate location string
    valid, error = validate_string_length(
        params.get('location'), 'location',
        max_length=500, required=False
    )
    if not valid:
        return False, error, None
    
    return True, None, {
        'site_id': site_id,
        'shift_id': shift_id,
        'title': params.get('title'),
        'description': sanitize_html(params.get('description')),
        'category_id': category_id,
        'severity': severity,
        'latitude': latitude,
        'longitude': longitude,
        'location': params.get('location')
    }


def create_error_response(error_message, error_code='VALIDATION_ERROR'):
    """
    Create a standardized error response.
    
    Args:
        error_message (str): Error message
        error_code (str): Error code for categorization
        
    Returns:
        dict: Standardized error response
    """
    return {
        'success': False,
        'error': error_message,
        'error_code': error_code
    }


def create_success_response(data=None, message=None):
    """
    Create a standardized success response.
    
    Args:
        data (dict): Response data
        message (str): Success message
        
    Returns:
        dict: Standardized success response
    """
    response = {'success': True}
    
    if message:
        response['message'] = message
    
    if data:
        response.update(data)
    
    return response



