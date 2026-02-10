# -*- coding: utf-8 -*-
"""Unit Tests for Guard Profile Model."""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


@tagged('post_install', '-at_install', 'guardpro')
class TestGuardProfile(TransactionCase):
    """Test cases for guard.profile model."""
    
    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.Guard = self.env['guard.profile']
        self.User = self.env['res.users']
        
        # Create test user
        self.test_user = self.User.create({
            'name': 'Test Guard User',
            'login': 'test_guard@example.com',
            'email': 'test_guard@example.com'
        })
    
    def test_create_guard_with_valid_data(self):
        """Test creating a guard with valid data."""
        guard = self.Guard.create({
            'name': 'John Doe',
            'badge_number': 'GRD001',
            'phone': '1234567890',
            'user_id': self.test_user.id,
            'status': 'active'
        })
        
        self.assertEqual(guard.name, 'John Doe')
        self.assertEqual(guard.badge_number, 'GRD001')
        self.assertEqual(guard.status, 'active')
    
    def test_badge_number_unique_constraint(self):
        """Test that badge numbers must be unique."""
        # Create first guard
        self.Guard.create({
            'name': 'Guard 1',
            'badge_number': 'GRD001',
            'phone': '1234567890'
        })
        
        # Try to create second guard with same badge number
        with self.assertRaises(Exception):  # psycopg2.IntegrityError
            self.Guard.create({
                'name': 'Guard 2',
                'badge_number': 'GRD001',  # Duplicate
                'phone': '0987654321'
            })
    
    def test_license_expiry_validation(self):
        """Test that expired licenses raise validation error."""
        yesterday = (datetime.now() - timedelta(days=1)).date()
        
        with self.assertRaises(ValidationError):
            self.Guard.create({
                'name': 'Guard Expired',
                'badge_number': 'GRD002',
                'phone': '1234567890',
                'license_expiry': yesterday
            })
    
    def test_email_validation(self):
        """Test email format validation."""
        guard = self.Guard.create({
            'name': 'Guard Email Test',
            'badge_number': 'GRD003',
            'phone': '1234567890'
        })
        
        # Test invalid email format
        with self.assertRaises(ValidationError):
            guard.write({'email': 'invalid-email'})
        
        # Test valid email format
        guard.write({'email': 'valid.email@example.com'})
        self.assertEqual(guard.email, 'valid.email@example.com')
    
    def test_compute_incident_count(self):
        """Test incident count computation."""
        guard = self.Guard.create({
            'name': 'Guard Incident Test',
            'badge_number': 'GRD004',
            'phone': '1234567890'
        })
        
        # Initially should be 0
        self.assertEqual(guard.incident_count, 0)
    
    def test_update_location_with_valid_coordinates(self):
        """Test updating guard location with valid GPS coordinates."""
        guard = self.Guard.create({
            'name': 'Guard Location Test',
            'badge_number': 'GRD005',
            'phone': '1234567890'
        })
        
        # Update location
        result = guard.update_location(25.2048, 55.2708)
        
        self.assertTrue(result)
        self.assertEqual(guard.current_latitude, 25.2048)
        self.assertEqual(guard.current_longitude, 55.2708)
        self.assertIsNotNone(guard.last_location_update)
    
    def test_compute_site_ids(self):
        """Test computation of assigned sites."""
        # This test requires creating shifts with sites
        # For now, just verify the field exists
        guard = self.Guard.create({
            'name': 'Guard Sites Test',
            'badge_number': 'GRD006',
            'phone': '1234567890'
        })
        
        # Should be empty recordset initially
        self.assertEqual(len(guard.site_ids), 0)



