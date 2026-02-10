# -*- coding: utf-8 -*-
"""Unit Tests for Input Validators."""

from odoo.tests import TransactionCase, tagged
from ..common import validators


@tagged('post_install', '-at_install', 'guardpro')
class TestValidators(TransactionCase):
    """Test cases for validators module."""
    
    def test_validate_id_valid(self):
        """Test validation of valid ID."""
        valid, error, id_value = validators.validate_id(123, 'test_id')
        
        self.assertTrue(valid)
        self.assertIsNone(error)
        self.assertEqual(id_value, 123)
    
    def test_validate_id_string_number(self):
        """Test validation of ID as string number."""
        valid, error, id_value = validators.validate_id('456', 'test_id')
        
        self.assertTrue(valid)
        self.assertIsNone(error)
        self.assertEqual(id_value, 456)
    
    def test_validate_id_invalid(self):
        """Test validation of invalid ID."""
        valid, error, id_value = validators.validate_id('abc', 'test_id')
        
        self.assertFalse(valid)
        self.assertIn('Invalid', error)
        self.assertIsNone(id_value)
    
    def test_validate_id_negative(self):
        """Test validation of negative ID."""
        valid, error, id_value = validators.validate_id(-1, 'test_id')
        
        self.assertFalse(valid)
        self.assertIn('positive', error)
    
    def test_validate_gps_coordinates_valid(self):
        """Test validation of valid GPS coordinates."""
        valid, error = validators.validate_gps_coordinates(25.2048, 55.2708)
        
        self.assertTrue(valid)
        self.assertIsNone(error)
    
    def test_validate_gps_coordinates_invalid_latitude(self):
        """Test validation of invalid latitude."""
        valid, error = validators.validate_gps_coordinates(95.0, 55.2708)
        
        self.assertFalse(valid)
        self.assertIn('Latitude', error)
    
    def test_validate_gps_coordinates_invalid_longitude(self):
        """Test validation of invalid longitude."""
        valid, error = validators.validate_gps_coordinates(25.2048, 185.0)
        
        self.assertFalse(valid)
        self.assertIn('Longitude', error)
    
    def test_validate_gps_coordinates_not_required(self):
        """Test optional GPS coordinates."""
        valid, error = validators.validate_gps_coordinates(None, None, required=False)
        
        self.assertTrue(valid)
        self.assertIsNone(error)
    
    def test_validate_gps_coordinates_required_missing(self):
        """Test required GPS coordinates when missing."""
        valid, error = validators.validate_gps_coordinates(None, None, required=True)
        
        self.assertFalse(valid)
        self.assertIn('required', error)
    
    def test_validate_string_length_valid(self):
        """Test validation of valid string length."""
        valid, error = validators.validate_string_length(
            'Test string', 'test_field', max_length=100
        )
        
        self.assertTrue(valid)
        self.assertIsNone(error)
    
    def test_validate_string_length_too_long(self):
        """Test validation of string exceeding max length."""
        long_string = 'x' * 101
        valid, error = validators.validate_string_length(
            long_string, 'test_field', max_length=100
        )
        
        self.assertFalse(valid)
        self.assertIn('exceeds', error)
    
    def test_validate_selection_valid(self):
        """Test validation of valid selection value."""
        valid, error = validators.validate_selection(
            'medium', ['low', 'medium', 'high'], 'severity'
        )
        
        self.assertTrue(valid)
        self.assertIsNone(error)
    
    def test_validate_selection_invalid(self):
        """Test validation of invalid selection value."""
        valid, error = validators.validate_selection(
            'invalid', ['low', 'medium', 'high'], 'severity'
        )
        
        self.assertFalse(valid)
        self.assertIn('Invalid', error)
    
    def test_validate_boolean_true(self):
        """Test validation of boolean true values."""
        # Test various true representations
        for value in [True, 'true', 'True', '1', 'yes', 1]:
            valid, error, parsed = validators.validate_boolean(value, 'test_bool')
            self.assertTrue(valid)
            self.assertTrue(parsed)
    
    def test_validate_boolean_false(self):
        """Test validation of boolean false values."""
        # Test various false representations
        for value in [False, 'false', 'False', '0', 'no', 0]:
            valid, error, parsed = validators.validate_boolean(value, 'test_bool')
            self.assertTrue(valid)
            self.assertFalse(parsed)
    
    def test_validate_required_params_all_present(self):
        """Test validation when all required parameters are present."""
        params = {'shift_id': 1, 'latitude': 25.2048, 'longitude': 55.2708}
        required = ['shift_id', 'latitude', 'longitude']
        
        valid, error = validators.validate_required_params(params, required)
        
        self.assertTrue(valid)
        self.assertIsNone(error)
    
    def test_validate_required_params_missing(self):
        """Test validation when required parameters are missing."""
        params = {'shift_id': 1}
        required = ['shift_id', 'latitude', 'longitude']
        
        valid, error = validators.validate_required_params(params, required)
        
        self.assertFalse(valid)
        self.assertIn('Missing', error)
        self.assertIn('latitude', error)
        self.assertIn('longitude', error)
    
    def test_create_error_response(self):
        """Test creation of standardized error response."""
        response = validators.create_error_response('Test error', 'TEST_ERROR')
        
        self.assertFalse(response['success'])
        self.assertEqual(response['error'], 'Test error')
        self.assertEqual(response['error_code'], 'TEST_ERROR')
    
    def test_create_success_response(self):
        """Test creation of standardized success response."""
        response = validators.create_success_response(
            data={'id': 123},
            message='Success message'
        )
        
        self.assertTrue(response['success'])
        self.assertEqual(response['message'], 'Success message')
        self.assertEqual(response['id'], 123)



