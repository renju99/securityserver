# -*- coding: utf-8 -*-
"""Test cases for Guard Location History functionality."""

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from odoo import fields
import logging

_logger = logging.getLogger(__name__)


class TestGuardLocationHistory(TransactionCase):
    """Test Guard Location History model and methods."""

    def setUp(self):
        """Set up test data."""
        super(TestGuardLocationHistory, self).setUp()
        
        # Create test guard profile
        self.guard = self.env['guard.profile'].create({
            'name': 'Test Guard',
            'employee_id': 'G001',
            'phone': '+1234567890',
            'email': 'testguard@example.com',
        })
        
        # Create test site
        self.site = self.env['client.site'].create({
            'name': 'Test Site',
            'address': '123 Test Street',
            'latitude': 25.2048,
            'longitude': 55.2708,
        })
        
        # Create test shift
        self.shift = self.env['guard.shift'].create({
            'name': 'Test Shift',
            'guard_id': self.guard.id,
            'site_id': self.site.id,
            'start_datetime': fields.Datetime.now(),
            'end_datetime': fields.Datetime.now() + timedelta(hours=8),
            'state': 'scheduled',
        })
        
        # Location History model
        self.LocationHistory = self.env['guard.location.history']

    def test_01_create_location_history(self):
        """Test basic creation of location history record."""
        _logger.info("Test 01: Creating location history record")
        
        location = self.LocationHistory.create({
            'guard_id': self.guard.id,
            'latitude': 25.2048,
            'longitude': 55.2708,
            'accuracy': 10.0,
            'site_id': self.site.id,
            'shift_id': self.shift.id,
        })
        
        self.assertTrue(location.id, "Location history record should be created")
        self.assertEqual(location.guard_id.id, self.guard.id)
        self.assertEqual(location.latitude, 25.2048)
        self.assertEqual(location.longitude, 55.2708)
        _logger.info("✓ Location history record created successfully")

    def test_02_latitude_validation(self):
        """Test latitude validation constraints."""
        _logger.info("Test 02: Testing latitude validation")
        
        # Test invalid latitude > 90
        with self.assertRaises(ValidationError):
            self.LocationHistory.create({
                'guard_id': self.guard.id,
                'latitude': 95.0,
                'longitude': 55.2708,
            })
        _logger.info("✓ Rejected latitude > 90")
        
        # Test invalid latitude < -90
        with self.assertRaises(ValidationError):
            self.LocationHistory.create({
                'guard_id': self.guard.id,
                'latitude': -95.0,
                'longitude': 55.2708,
            })
        _logger.info("✓ Rejected latitude < -90")
        
        # Test valid latitude
        location = self.LocationHistory.create({
            'guard_id': self.guard.id,
            'latitude': 45.0,
            'longitude': 55.2708,
        })
        self.assertTrue(location.id)
        _logger.info("✓ Valid latitude accepted")

    def test_03_longitude_validation(self):
        """Test longitude validation constraints."""
        _logger.info("Test 03: Testing longitude validation")
        
        # Test invalid longitude > 180
        with self.assertRaises(ValidationError):
            self.LocationHistory.create({
                'guard_id': self.guard.id,
                'latitude': 25.2048,
                'longitude': 185.0,
            })
        _logger.info("✓ Rejected longitude > 180")
        
        # Test invalid longitude < -180
        with self.assertRaises(ValidationError):
            self.LocationHistory.create({
                'guard_id': self.guard.id,
                'latitude': 25.2048,
                'longitude': -185.0,
            })
        _logger.info("✓ Rejected longitude < -180")
        
        # Test valid longitude
        location = self.LocationHistory.create({
            'guard_id': self.guard.id,
            'latitude': 25.2048,
            'longitude': 120.0,
        })
        self.assertTrue(location.id)
        _logger.info("✓ Valid longitude accepted")

    def test_04_create_location_point_method(self):
        """Test create_location_point helper method."""
        _logger.info("Test 04: Testing create_location_point method")
        
        location = self.LocationHistory.create_location_point(
            guard_id=self.guard.id,
            latitude=25.2048,
            longitude=55.2708,
            accuracy=15.0,
            speed=20.5,
            heading=180.0,
            battery_level=85,
            site_id=self.site.id,
        )
        
        self.assertTrue(location.id)
        self.assertEqual(location.guard_id.id, self.guard.id)
        self.assertEqual(location.accuracy, 15.0)
        self.assertEqual(location.speed, 20.5)
        self.assertEqual(location.heading, 180.0)
        self.assertEqual(location.battery_level, 85)
        _logger.info("✓ create_location_point method works correctly")

    def test_05_get_guard_path(self):
        """Test get_guard_path method for retrieving location history."""
        _logger.info("Test 05: Testing get_guard_path method")
        
        # Create multiple location points
        now = fields.Datetime.now()
        locations = []
        for i in range(5):
            loc = self.LocationHistory.create({
                'guard_id': self.guard.id,
                'latitude': 25.2048 + (i * 0.001),
                'longitude': 55.2708 + (i * 0.001),
                'timestamp': now + timedelta(minutes=i*5),
                'site_id': self.site.id,
            })
            locations.append(loc)
        
        # Get guard path
        path = self.LocationHistory.get_guard_path(self.guard.id)
        
        self.assertEqual(len(path), 5, "Should return 5 location points")
        self.assertEqual(path[0]['guard_id'], self.guard.id)
        self.assertIn('latitude', path[0])
        self.assertIn('longitude', path[0])
        self.assertIn('timestamp', path[0])
        _logger.info("✓ get_guard_path method returns correct data")

    def test_06_get_guard_path_with_date_range(self):
        """Test get_guard_path with date range filtering."""
        _logger.info("Test 06: Testing get_guard_path with date range")
        
        now = fields.Datetime.now()
        
        # Create location points over 3 days
        for day in range(3):
            for hour in range(3):
                self.LocationHistory.create({
                    'guard_id': self.guard.id,
                    'latitude': 25.2048,
                    'longitude': 55.2708,
                    'timestamp': now - timedelta(days=day, hours=hour),
                })
        
        # Get path for today only
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        path = self.LocationHistory.get_guard_path(
            self.guard.id,
            start_datetime=start_date,
            end_datetime=end_date
        )
        
        self.assertGreater(len(path), 0, "Should return location points")
        _logger.info(f"✓ Date range filtering works: {len(path)} points found")

    def test_07_cleanup_old_records(self):
        """Test cleanup_old_records scheduled action."""
        _logger.info("Test 07: Testing cleanup_old_records method")
        
        now = fields.Datetime.now()
        
        # Create old records (100 days old)
        old_records = []
        for i in range(3):
            rec = self.LocationHistory.create({
                'guard_id': self.guard.id,
                'latitude': 25.2048,
                'longitude': 55.2708,
                'timestamp': now - timedelta(days=100),
            })
            old_records.append(rec)
        
        # Create recent records
        recent_records = []
        for i in range(3):
            rec = self.LocationHistory.create({
                'guard_id': self.guard.id,
                'latitude': 25.2048,
                'longitude': 55.2708,
                'timestamp': now - timedelta(days=30),
            })
            recent_records.append(rec)
        
        # Run cleanup (default 90 days retention)
        self.LocationHistory.cleanup_old_records()
        
        # Check that old records are deleted
        for rec in old_records:
            self.assertFalse(rec.exists(), "Old records should be deleted")
        
        # Check that recent records still exist
        for rec in recent_records:
            self.assertTrue(rec.exists(), "Recent records should still exist")
        
        _logger.info("✓ cleanup_old_records works correctly")

    def test_08_cleanup_old_locations_method(self):
        """Test cleanup_old_locations method with custom days."""
        _logger.info("Test 08: Testing cleanup_old_locations method")
        
        now = fields.Datetime.now()
        
        # Create records 35 days old
        old_count = 5
        for i in range(old_count):
            self.LocationHistory.create({
                'guard_id': self.guard.id,
                'latitude': 25.2048,
                'longitude': 55.2708,
                'timestamp': now - timedelta(days=35),
            })
        
        # Cleanup records older than 30 days
        deleted_count = self.LocationHistory.cleanup_old_locations(days=30)
        
        self.assertEqual(deleted_count, old_count, 
                        f"Should delete {old_count} old records")
        _logger.info(f"✓ cleanup_old_locations deleted {deleted_count} records")

    def test_09_location_history_with_all_fields(self):
        """Test location history with all optional fields."""
        _logger.info("Test 09: Testing location history with all fields")
        
        tour_log = self.env['tour.log'].create({
            'guard_id': self.guard.id,
            'site_id': self.site.id,
            'tour_id': False,  # We don't have a tour created
            'start_time': fields.Datetime.now(),
        })
        
        location = self.LocationHistory.create({
            'guard_id': self.guard.id,
            'latitude': 25.2048,
            'longitude': 55.2708,
            'accuracy': 12.5,
            'altitude': 150.0,
            'speed': 5.5,
            'heading': 270.0,
            'site_id': self.site.id,
            'shift_id': self.shift.id,
            'tour_log_id': tour_log.id,
            'battery_level': 75,
            'is_manual': True,
            'notes': 'Manual location update during patrol',
        })
        
        self.assertTrue(location.id)
        self.assertEqual(location.altitude, 150.0)
        self.assertEqual(location.speed, 5.5)
        self.assertEqual(location.heading, 270.0)
        self.assertEqual(location.battery_level, 75)
        self.assertTrue(location.is_manual)
        self.assertEqual(location.notes, 'Manual location update during patrol')
        _logger.info("✓ All optional fields stored correctly")

    def test_10_location_history_ordering(self):
        """Test that location history is ordered by timestamp desc."""
        _logger.info("Test 10: Testing location history ordering")
        
        now = fields.Datetime.now()
        
        # Create locations with different timestamps
        loc1 = self.LocationHistory.create({
            'guard_id': self.guard.id,
            'latitude': 25.2048,
            'longitude': 55.2708,
            'timestamp': now - timedelta(hours=2),
        })
        
        loc2 = self.LocationHistory.create({
            'guard_id': self.guard.id,
            'latitude': 25.2050,
            'longitude': 55.2710,
            'timestamp': now - timedelta(hours=1),
        })
        
        loc3 = self.LocationHistory.create({
            'guard_id': self.guard.id,
            'latitude': 25.2052,
            'longitude': 55.2712,
            'timestamp': now,
        })
        
        # Search with default ordering
        locations = self.LocationHistory.search([
            ('guard_id', '=', self.guard.id)
        ], limit=3)
        
        # Check ordering (most recent first)
        self.assertEqual(locations[0].id, loc3.id, "Most recent should be first")
        self.assertEqual(locations[1].id, loc2.id, "Second most recent")
        self.assertEqual(locations[2].id, loc1.id, "Oldest should be last")
        _logger.info("✓ Location history ordered correctly by timestamp desc")

    def test_11_multiple_guards_location_history(self):
        """Test location history for multiple guards."""
        _logger.info("Test 11: Testing multiple guards location history")
        
        # Create second guard
        guard2 = self.env['guard.profile'].create({
            'name': 'Test Guard 2',
            'employee_id': 'G002',
            'phone': '+1234567891',
            'email': 'testguard2@example.com',
        })
        
        # Create locations for both guards
        for i in range(3):
            self.LocationHistory.create({
                'guard_id': self.guard.id,
                'latitude': 25.2048 + (i * 0.001),
                'longitude': 55.2708 + (i * 0.001),
            })
            
            self.LocationHistory.create({
                'guard_id': guard2.id,
                'latitude': 25.3048 + (i * 0.001),
                'longitude': 55.3708 + (i * 0.001),
            })
        
        # Get path for each guard
        path1 = self.LocationHistory.get_guard_path(self.guard.id)
        path2 = self.LocationHistory.get_guard_path(guard2.id)
        
        self.assertEqual(len(path1), 3, "Guard 1 should have 3 locations")
        self.assertEqual(len(path2), 3, "Guard 2 should have 3 locations")
        
        # Verify locations are separate
        for loc in path1:
            self.assertEqual(loc['guard_id'], self.guard.id)
        for loc in path2:
            self.assertEqual(loc['guard_id'], guard2.id)
        
        _logger.info("✓ Multiple guards location history handled correctly")

    def test_12_location_history_cascade_delete(self):
        """Test that location history is deleted when guard is deleted."""
        _logger.info("Test 12: Testing cascade delete of location history")
        
        # Create guard and locations
        temp_guard = self.env['guard.profile'].create({
            'name': 'Temp Guard',
            'employee_id': 'G999',
            'phone': '+9999999999',
            'email': 'temp@example.com',
        })
        
        locations = []
        for i in range(3):
            loc = self.LocationHistory.create({
                'guard_id': temp_guard.id,
                'latitude': 25.2048,
                'longitude': 55.2708,
            })
            locations.append(loc)
        
        # Delete guard
        temp_guard.unlink()
        
        # Check that locations are also deleted (cascade)
        for loc in locations:
            self.assertFalse(loc.exists(), 
                           "Location history should be deleted with guard")
        
        _logger.info("✓ Cascade delete works correctly")

    def test_13_location_history_access_rights(self):
        """Test access rights for location history model."""
        _logger.info("Test 13: Testing access rights")
        
        # Check that model exists and has proper access rules
        model = self.env['ir.model'].search([
            ('model', '=', 'guard.location.history')
        ])
        self.assertTrue(model.id, "guard.location.history model should exist")
        
        # Check access rules exist
        access_rules = self.env['ir.model.access'].search([
            ('model_id', '=', model.id)
        ])
        self.assertGreater(len(access_rules), 0, 
                          "Access rules should be defined")
        
        _logger.info(f"✓ Found {len(access_rules)} access rules")

    def test_14_location_history_with_limit(self):
        """Test get_guard_path with limit parameter."""
        _logger.info("Test 14: Testing get_guard_path with limit")
        
        # Create 20 location points
        for i in range(20):
            self.LocationHistory.create({
                'guard_id': self.guard.id,
                'latitude': 25.2048 + (i * 0.001),
                'longitude': 55.2708 + (i * 0.001),
            })
        
        # Get path with limit
        path = self.LocationHistory.get_guard_path(self.guard.id, limit=10)
        
        self.assertEqual(len(path), 10, "Should return only 10 location points")
        _logger.info("✓ Limit parameter works correctly")


def run_all_tests():
    """Run all location history tests and generate report."""
    _logger.info("=" * 80)
    _logger.info("GUARD LOCATION HISTORY - COMPREHENSIVE TEST SUITE")
    _logger.info("=" * 80)
    
    test_suite = TestGuardLocationHistory()
    test_suite.setUp()
    
    tests = [
        ('Basic Creation', test_suite.test_01_create_location_history),
        ('Latitude Validation', test_suite.test_02_latitude_validation),
        ('Longitude Validation', test_suite.test_03_longitude_validation),
        ('Create Location Point Method', test_suite.test_04_create_location_point_method),
        ('Get Guard Path', test_suite.test_05_get_guard_path),
        ('Date Range Filtering', test_suite.test_06_get_guard_path_with_date_range),
        ('Cleanup Old Records', test_suite.test_07_cleanup_old_records),
        ('Cleanup Old Locations', test_suite.test_08_cleanup_old_locations_method),
        ('All Fields Storage', test_suite.test_09_location_history_with_all_fields),
        ('Ordering', test_suite.test_10_location_history_ordering),
        ('Multiple Guards', test_suite.test_11_multiple_guards_location_history),
        ('Cascade Delete', test_suite.test_12_location_history_cascade_delete),
        ('Access Rights', test_suite.test_13_location_history_access_rights),
        ('Limit Parameter', test_suite.test_14_location_history_with_limit),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
            _logger.info(f"✅ PASSED: {test_name}")
        except Exception as e:
            failed += 1
            _logger.error(f"❌ FAILED: {test_name} - {str(e)}")
    
    _logger.info("=" * 80)
    _logger.info(f"TEST RESULTS: {passed} PASSED, {failed} FAILED")
    _logger.info("=" * 80)

