# -*- coding: utf-8 -*-
"""Test NFC and QR Code Checkpoint Functionality."""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestNFCQRCheckpoint(TransactionCase):
    """Test NFC and QR checkpoint scanning."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        
        # Create test site
        self.site = self.env['client.site'].create({
            'name': 'Test Security Site',
            'address': '123 Test Street',
            'city': 'Test City',
            'state': 'active'
        })
        
        # Create test guard
        self.test_user = self.env['res.users'].create({
            'name': 'Test Guard User',
            'login': 'testguard@test.com',
            'email': 'testguard@test.com',
        })
        
        self.guard = self.env['guard.profile'].create({
            'name': 'Test Guard',
            'badge_number': 'TEST001',
            'user_id': self.test_user.id,
            'phone': '+1234567890',
            'status': 'active'
        })
        
        # Test coordinates
        self.test_lat = 25.2048
        self.test_lng = 55.2708

    def test_01_create_nfc_checkpoint(self):
        """Test NFC checkpoint creation."""
        _logger.info("TEST 1: Creating NFC checkpoint...")
        
        checkpoint = self.env['checkpoint'].create({
            'name': 'Main Entrance NFC',
            'code': 'NFC-001',
            'site_id': self.site.id,
            'scan_type': 'nfc',
            'nfc_tag_id': 'NFC-TAG-12345678',
            'latitude': self.test_lat,
            'longitude': self.test_lng,
            'status': 'active'
        })
        
        self.assertTrue(checkpoint.id, "NFC checkpoint should be created")
        self.assertEqual(checkpoint.scan_type, 'nfc')
        self.assertEqual(checkpoint.nfc_tag_id, 'NFC-TAG-12345678')
        _logger.info("✓ NFC checkpoint created successfully: %s", checkpoint.name)

    def test_02_create_qr_checkpoint(self):
        """Test QR checkpoint creation."""
        _logger.info("TEST 2: Creating QR checkpoint...")
        
        checkpoint = self.env['checkpoint'].create({
            'name': 'Parking Lot QR',
            'code': 'QR-001',
            'site_id': self.site.id,
            'scan_type': 'qr',
            'qr_code': 'QR-ABCD1234',
            'latitude': self.test_lat,
            'longitude': self.test_lng,
            'status': 'active'
        })
        
        self.assertTrue(checkpoint.id, "QR checkpoint should be created")
        self.assertEqual(checkpoint.scan_type, 'qr')
        self.assertEqual(checkpoint.qr_code, 'QR-ABCD1234')
        self.assertTrue(checkpoint.qr_code_image, "QR code image should be generated")
        _logger.info("✓ QR checkpoint created successfully: %s", checkpoint.name)

    def test_03_create_both_checkpoint(self):
        """Test checkpoint with both NFC and QR."""
        _logger.info("TEST 3: Creating checkpoint with both NFC and QR...")
        
        checkpoint = self.env['checkpoint'].create({
            'name': 'Reception Dual',
            'code': 'BOTH-001',
            'site_id': self.site.id,
            'scan_type': 'both',
            'nfc_tag_id': 'NFC-TAG-BOTH-001',
            'qr_code': 'QR-BOTH-001',
            'latitude': self.test_lat,
            'longitude': self.test_lng,
            'status': 'active'
        })
        
        self.assertTrue(checkpoint.id, "Dual checkpoint should be created")
        self.assertEqual(checkpoint.scan_type, 'both')
        self.assertTrue(checkpoint.nfc_tag_id)
        self.assertTrue(checkpoint.qr_code)
        _logger.info("✓ Dual NFC+QR checkpoint created successfully")

    def test_04_auto_generate_qr_code(self):
        """Test automatic QR code generation."""
        _logger.info("TEST 4: Testing auto QR code generation...")
        
        checkpoint = self.env['checkpoint'].create({
            'name': 'Auto QR Test',
            'code': 'AUTO-QR-001',
            'site_id': self.site.id,
            'scan_type': 'qr',
            'latitude': self.test_lat,
            'longitude': self.test_lng
        })
        
        self.assertTrue(checkpoint.qr_code, "QR code should be auto-generated")
        self.assertTrue(checkpoint.qr_code.startswith('CP-'))
        _logger.info("✓ QR code auto-generated: %s", checkpoint.qr_code)

    def test_05_nfc_scan_verification(self):
        """Test NFC scan verification."""
        _logger.info("TEST 5: Testing NFC scan verification...")
        
        # Create NFC checkpoint
        checkpoint = self.env['checkpoint'].create({
            'name': 'NFC Scan Test',
            'code': 'NFC-SCAN-001',
            'site_id': self.site.id,
            'scan_type': 'nfc',
            'nfc_tag_id': 'NFC-VERIFY-001',
            'latitude': self.test_lat,
            'longitude': self.test_lng,
            'status': 'active'
        })
        
        # Test valid scan
        result = checkpoint.verify_scan(
            'NFC-VERIFY-001',
            self.guard.id,
            self.test_lat,
            self.test_lng
        )
        
        self.assertTrue(result['success'], "Valid NFC scan should succeed")
        _logger.info("✓ Valid NFC scan verified: %s", result['message'])
        
        # Test invalid scan
        result = checkpoint.verify_scan(
            'WRONG-TAG-ID',
            self.guard.id,
            self.test_lat,
            self.test_lng
        )
        
        self.assertFalse(result['success'], "Invalid NFC scan should fail")
        _logger.info("✓ Invalid NFC scan rejected: %s", result['message'])

    def test_06_qr_scan_verification(self):
        """Test QR scan verification."""
        _logger.info("TEST 6: Testing QR scan verification...")
        
        # Create QR checkpoint
        checkpoint = self.env['checkpoint'].create({
            'name': 'QR Scan Test',
            'code': 'QR-SCAN-001',
            'site_id': self.site.id,
            'scan_type': 'qr',
            'qr_code': 'QR-VERIFY-001',
            'latitude': self.test_lat,
            'longitude': self.test_lng,
            'status': 'active'
        })
        
        # Test valid scan
        result = checkpoint.verify_scan(
            'QR-VERIFY-001',
            self.guard.id,
            self.test_lat,
            self.test_lng
        )
        
        self.assertTrue(result['success'], "Valid QR scan should succeed")
        _logger.info("✓ Valid QR scan verified: %s", result['message'])
        
        # Test invalid scan
        result = checkpoint.verify_scan(
            'WRONG-QR-CODE',
            self.guard.id,
            self.test_lat,
            self.test_lng
        )
        
        self.assertFalse(result['success'], "Invalid QR scan should fail")
        _logger.info("✓ Invalid QR scan rejected: %s", result['message'])

    def test_07_create_nfc_scan_record(self):
        """Test creating NFC scan record."""
        _logger.info("TEST 7: Creating NFC scan record...")
        
        # Create checkpoint
        checkpoint = self.env['checkpoint'].create({
            'name': 'NFC Record Test',
            'code': 'NFC-REC-001',
            'site_id': self.site.id,
            'scan_type': 'nfc',
            'nfc_tag_id': 'NFC-RECORD-001',
            'latitude': self.test_lat,
            'longitude': self.test_lng,
            'status': 'active'
        })
        
        # Create scan record
        scan = self.env['checkpoint.scan'].create({
            'checkpoint_id': checkpoint.id,
            'guard_id': self.guard.id,
            'scan_type': 'nfc',
            'scan_data': 'NFC-RECORD-001',
            'latitude': self.test_lat,
            'longitude': self.test_lng,
            'status': 'verified'
        })
        
        self.assertTrue(scan.id, "NFC scan record should be created")
        self.assertEqual(scan.scan_type, 'nfc')
        self.assertEqual(scan.status, 'verified')
        _logger.info("✓ NFC scan record created: ID %d", scan.id)

    def test_08_create_qr_scan_record(self):
        """Test creating QR scan record."""
        _logger.info("TEST 8: Creating QR scan record...")
        
        # Create checkpoint
        checkpoint = self.env['checkpoint'].create({
            'name': 'QR Record Test',
            'code': 'QR-REC-001',
            'site_id': self.site.id,
            'scan_type': 'qr',
            'qr_code': 'QR-RECORD-001',
            'latitude': self.test_lat,
            'longitude': self.test_lng,
            'status': 'active'
        })
        
        # Create scan record
        scan = self.env['checkpoint.scan'].create({
            'checkpoint_id': checkpoint.id,
            'guard_id': self.guard.id,
            'scan_type': 'qr',
            'scan_data': 'QR-RECORD-001',
            'latitude': self.test_lat,
            'longitude': self.test_lng,
            'status': 'verified'
        })
        
        self.assertTrue(scan.id, "QR scan record should be created")
        self.assertEqual(scan.scan_type, 'qr')
        self.assertEqual(scan.status, 'verified')
        _logger.info("✓ QR scan record created: ID %d", scan.id)

    def test_09_scan_interval_check(self):
        """Test minimum scan interval."""
        _logger.info("TEST 9: Testing minimum scan interval...")
        
        # Create checkpoint with 60 second interval
        checkpoint = self.env['checkpoint'].create({
            'name': 'Interval Test',
            'code': 'INT-001',
            'site_id': self.site.id,
            'scan_type': 'nfc',
            'nfc_tag_id': 'NFC-INTERVAL-001',
            'min_scan_interval': 60,
            'status': 'active'
        })
        
        # First scan - should succeed
        result1 = checkpoint.verify_scan(
            'NFC-INTERVAL-001',
            self.guard.id
        )
        self.assertTrue(result1['success'])
        
        # Create the first scan
        self.env['checkpoint.scan'].create({
            'checkpoint_id': checkpoint.id,
            'guard_id': self.guard.id,
            'scan_type': 'nfc',
            'scan_data': 'NFC-INTERVAL-001',
            'status': 'verified'
        })
        
        # Immediate second scan - should fail
        result2 = checkpoint.verify_scan(
            'NFC-INTERVAL-001',
            self.guard.id
        )
        self.assertFalse(result2['success'], "Should reject scan within interval")
        _logger.info("✓ Scan interval check working: %s", result2['message'])

    def test_10_checkpoint_statistics(self):
        """Test checkpoint statistics computation."""
        _logger.info("TEST 10: Testing checkpoint statistics...")
        
        # Create checkpoint
        checkpoint = self.env['checkpoint'].create({
            'name': 'Stats Test',
            'code': 'STATS-001',
            'site_id': self.site.id,
            'scan_type': 'nfc',
            'nfc_tag_id': 'NFC-STATS-001',
            'status': 'active'
        })
        
        # Create multiple scans
        for i in range(5):
            self.env['checkpoint.scan'].create({
                'checkpoint_id': checkpoint.id,
                'guard_id': self.guard.id,
                'scan_type': 'nfc',
                'scan_data': 'NFC-STATS-001',
                'status': 'verified',
                'scan_time': datetime.now() - timedelta(days=i)
            })
        
        # Recompute statistics
        checkpoint._compute_statistics()
        
        self.assertEqual(checkpoint.total_scans, 5, "Should count 5 scans")
        self.assertTrue(checkpoint.last_scan_time, "Should have last scan time")
        _logger.info("✓ Statistics: %d scans, frequency: %.2f/day",
                    checkpoint.total_scans, checkpoint.scan_frequency)

    def test_11_api_scan_checkpoint(self):
        """Test API scan checkpoint method."""
        _logger.info("TEST 11: Testing API scan checkpoint method...")
        
        # Create checkpoint
        checkpoint = self.env['checkpoint'].create({
            'name': 'API Test',
            'code': 'API-001',
            'site_id': self.site.id,
            'scan_type': 'qr',
            'qr_code': 'QR-API-001',
            'latitude': self.test_lat,
            'longitude': self.test_lng,
            'status': 'active'
        })
        
        # Use API method to scan
        result = self.env['checkpoint.scan'].scan_checkpoint(
            checkpoint_id=checkpoint.id,
            guard_id=self.guard.id,
            scan_data='QR-API-001',
            latitude=self.test_lat,
            longitude=self.test_lng,
            notes='Test scan via API'
        )
        
        self.assertTrue(result['success'], "API scan should succeed")
        self.assertTrue(result['scan_id'], "Should return scan ID")
        _logger.info("✓ API scan successful: %s (ID: %d)",
                    result['message'], result['scan_id'])

    def test_12_validation_nfc_required(self):
        """Test NFC tag ID required for NFC checkpoints."""
        _logger.info("TEST 12: Testing NFC validation...")
        
        with self.assertRaises(ValidationError):
            self.env['checkpoint'].create({
                'name': 'Invalid NFC',
                'code': 'INVALID-NFC-001',
                'site_id': self.site.id,
                'scan_type': 'nfc',
                # Missing nfc_tag_id
                'status': 'active'
            })
        _logger.info("✓ Validation correctly rejects NFC checkpoint without tag ID")

    def test_13_validation_qr_required(self):
        """Test QR code required for QR checkpoints."""
        _logger.info("TEST 13: Testing QR validation...")
        
        with self.assertRaises(ValidationError):
            self.env['checkpoint'].create({
                'name': 'Invalid QR',
                'code': 'INVALID-QR-001',
                'site_id': self.site.id,
                'scan_type': 'qr',
                # Missing qr_code (and auto-gen won't work in this test scenario)
                'status': 'active'
            })
            # Force validation
            self.env['checkpoint'].flush_model()
        _logger.info("✓ Validation correctly enforces QR requirements")

    def test_14_unique_constraints(self):
        """Test unique constraints on NFC and QR codes."""
        _logger.info("TEST 14: Testing unique constraints...")
        
        # Create first checkpoint
        self.env['checkpoint'].create({
            'name': 'First',
            'code': 'UNIQUE-001',
            'site_id': self.site.id,
            'scan_type': 'nfc',
            'nfc_tag_id': 'UNIQUE-NFC-001',
            'status': 'active'
        })
        
        # Try to create duplicate NFC tag
        with self.assertRaises(Exception):  # psycopg2.IntegrityError
            self.env['checkpoint'].create({
                'name': 'Duplicate',
                'code': 'UNIQUE-002',
                'site_id': self.site.id,
                'scan_type': 'nfc',
                'nfc_tag_id': 'UNIQUE-NFC-001',  # Duplicate
                'status': 'active'
            })
        _logger.info("✓ Unique constraints working correctly")

    def test_15_inactive_checkpoint_scan(self):
        """Test scanning inactive checkpoint."""
        _logger.info("TEST 15: Testing inactive checkpoint scan...")
        
        # Create inactive checkpoint
        checkpoint = self.env['checkpoint'].create({
            'name': 'Inactive Test',
            'code': 'INACTIVE-001',
            'site_id': self.site.id,
            'scan_type': 'nfc',
            'nfc_tag_id': 'NFC-INACTIVE-001',
            'status': 'inactive'
        })
        
        # Try to scan
        result = checkpoint.verify_scan(
            'NFC-INACTIVE-001',
            self.guard.id
        )
        
        self.assertFalse(result['success'], "Should reject scan of inactive checkpoint")
        _logger.info("✓ Inactive checkpoint correctly rejected: %s", result['message'])

    def test_16_both_scan_type(self):
        """Test checkpoint accepting both NFC and QR."""
        _logger.info("TEST 16: Testing 'both' scan type...")
        
        # Create checkpoint with both
        checkpoint = self.env['checkpoint'].create({
            'name': 'Both Type Test',
            'code': 'BOTH-TEST-001',
            'site_id': self.site.id,
            'scan_type': 'both',
            'nfc_tag_id': 'NFC-BOTH-TEST',
            'qr_code': 'QR-BOTH-TEST',
            'status': 'active'
        })
        
        # Test NFC scan
        result_nfc = checkpoint.verify_scan('NFC-BOTH-TEST', self.guard.id)
        self.assertTrue(result_nfc['success'], "Should accept NFC")
        _logger.info("✓ Both-type checkpoint accepts NFC")
        
        # Test QR scan
        result_qr = checkpoint.verify_scan('QR-BOTH-TEST', self.guard.id)
        self.assertTrue(result_qr['success'], "Should accept QR")
        _logger.info("✓ Both-type checkpoint accepts QR")

    def test_17_scan_with_photo(self):
        """Test scan with photo requirement."""
        _logger.info("TEST 17: Testing photo requirement...")
        
        # Create checkpoint requiring photo
        checkpoint = self.env['checkpoint'].create({
            'name': 'Photo Required',
            'code': 'PHOTO-001',
            'site_id': self.site.id,
            'scan_type': 'qr',
            'qr_code': 'QR-PHOTO-001',
            'requires_photo': True,
            'status': 'active'
        })
        
        # Try to create scan without photo - should fail
        with self.assertRaises(ValidationError):
            self.env['checkpoint.scan'].create({
                'checkpoint_id': checkpoint.id,
                'guard_id': self.guard.id,
                'scan_type': 'qr',
                'scan_data': 'QR-PHOTO-001',
                'status': 'verified'
                # Missing photo
            })
        _logger.info("✓ Photo requirement validation working")

    def test_18_scan_with_notes(self):
        """Test scan with notes requirement."""
        _logger.info("TEST 18: Testing notes requirement...")
        
        # Create checkpoint requiring notes
        checkpoint = self.env['checkpoint'].create({
            'name': 'Notes Required',
            'code': 'NOTES-001',
            'site_id': self.site.id,
            'scan_type': 'qr',
            'qr_code': 'QR-NOTES-001',
            'requires_note': True,
            'status': 'active'
        })
        
        # Try to create scan without notes - should fail
        with self.assertRaises(ValidationError):
            self.env['checkpoint.scan'].create({
                'checkpoint_id': checkpoint.id,
                'guard_id': self.guard.id,
                'scan_type': 'qr',
                'scan_data': 'QR-NOTES-001',
                'status': 'verified'
                # Missing notes
            })
        _logger.info("✓ Notes requirement validation working")

    def test_19_manual_override(self):
        """Test manual scan override."""
        _logger.info("TEST 19: Testing manual override...")
        
        checkpoint = self.env['checkpoint'].create({
            'name': 'Override Test',
            'code': 'OVERRIDE-001',
            'site_id': self.site.id,
            'scan_type': 'nfc',
            'nfc_tag_id': 'NFC-OVERRIDE-001',
            'status': 'active'
        })
        
        # Create failed scan
        scan = self.env['checkpoint.scan'].create({
            'checkpoint_id': checkpoint.id,
            'guard_id': self.guard.id,
            'scan_type': 'nfc',
            'scan_data': 'WRONG-TAG',
            'status': 'failed',
            'failure_reason': 'Invalid tag ID'
        })
        
        # Manual override
        scan.action_manual_verify()
        
        self.assertEqual(scan.status, 'manual_override')
        self.assertEqual(scan.verification_method, 'supervisor')
        _logger.info("✓ Manual override successful")

    def test_20_gps_distance_calculation(self):
        """Test GPS distance calculation."""
        _logger.info("TEST 20: Testing GPS distance calculation...")
        
        # Dubai coordinates
        lat1, lon1 = 25.2048, 55.2708
        # About 1km away
        lat2, lon2 = 25.2148, 55.2708
        
        distance = self.env['checkpoint.scan']._calculate_distance(
            lat1, lon1, lat2, lon2
        )
        
        # Should be approximately 1000 meters
        self.assertGreater(distance, 900)
        self.assertLess(distance, 1200)
        _logger.info("✓ GPS distance calculation: %.2f meters", distance)

    def test_21_rescan_in_different_tours(self):
        """Test that checkpoints can be rescanned when a new tour starts."""
        _logger.info("TEST 21: Testing rescan in different tours...")
        
        # Create security tour
        tour = self.env['security.tour'].create({
            'name': 'Rescan Test Tour',
            'site_id': self.site.id,
            'tour_type': 'scheduled',
            'status': 'active'
        })
        
        # Create checkpoint with short interval
        checkpoint = self.env['checkpoint'].create({
            'name': 'Rescan Test Checkpoint',
            'code': 'RESCAN-001',
            'site_id': self.site.id,
            'scan_type': 'nfc',
            'nfc_tag_id': 'NFC-RESCAN-001',
            'min_scan_interval': 300,  # 5 minutes
            'status': 'active'
        })
        
        # Link checkpoint to tour
        tour.write({'checkpoint_ids': [(4, checkpoint.id)]})
        
        # Create first tour log
        tour_log_1 = self.env['tour.log'].create({
            'tour_id': tour.id,
            'guard_id': self.guard.id,
            'site_id': self.site.id,
            'status': 'in_progress'
        })
        
        # First scan with tour_log_1 - should succeed
        result1 = checkpoint.verify_scan(
            'NFC-RESCAN-001',
            self.guard.id,
            tour_log_id=tour_log_1.id
        )
        self.assertTrue(result1['success'], "First scan in tour 1 should succeed")
        _logger.info("✓ First scan in tour 1 succeeded")
        
        # Create the scan record for tour 1
        self.env['checkpoint.scan'].create({
            'checkpoint_id': checkpoint.id,
            'guard_id': self.guard.id,
            'scan_type': 'nfc',
            'scan_data': 'NFC-RESCAN-001',
            'status': 'verified',
            'tour_log_id': tour_log_1.id
        })
        
        # Immediate second scan with SAME tour_log_1 - should fail
        result2 = checkpoint.verify_scan(
            'NFC-RESCAN-001',
            self.guard.id,
            tour_log_id=tour_log_1.id
        )
        self.assertFalse(result2['success'], 
                        "Duplicate scan in same tour should fail")
        _logger.info("✓ Duplicate scan in same tour correctly rejected")
        
        # Create second tour log (new tour)
        tour_log_2 = self.env['tour.log'].create({
            'tour_id': tour.id,
            'guard_id': self.guard.id,
            'site_id': self.site.id,
            'status': 'in_progress'
        })
        
        # Scan with DIFFERENT tour_log_2 - should succeed even within interval
        result3 = checkpoint.verify_scan(
            'NFC-RESCAN-001',
            self.guard.id,
            tour_log_id=tour_log_2.id
        )
        self.assertTrue(result3['success'], 
                       "Scan in new tour should succeed even within interval")
        _logger.info("✓ Scan in new tour succeeded - tour cache properly cleared!")
        
        # Create the scan record for tour 2
        scan2 = self.env['checkpoint.scan'].create({
            'checkpoint_id': checkpoint.id,
            'guard_id': self.guard.id,
            'scan_type': 'nfc',
            'scan_data': 'NFC-RESCAN-001',
            'status': 'verified',
            'tour_log_id': tour_log_2.id
        })
        
        self.assertEqual(scan2.tour_log_id.id, tour_log_2.id,
                        "Scan should be linked to correct tour")
        _logger.info("✓ Test complete: Checkpoints can be rescanned in new tours")


def run_all_tests():
    """Run all NFC/QR tests and print summary."""
    import odoo
    from odoo.tests.common import Form
    
    _logger.info("="*70)
    def test_nfc_text_label_and_colon_uid(self):
        """Text labels and colon-separated UIDs match; compact hex is normalized."""
        checkpoint = self.env['checkpoint'].create({
            'name': 'NFC Format Test',
            'code': 'NFC-FMT-001',
            'site_id': self.site.id,
            'scan_type': 'nfc',
            'nfc_tag_id': 'SAFI-MNT-001',
            'latitude': self.test_lat,
            'longitude': self.test_lng,
            'status': 'active',
        })
        self.assertTrue(
            checkpoint._nfc_tags_match('SAFI-MNT-001', 'SAFI-MNT-001')
        )
        uid_checkpoint = self.env['checkpoint'].create({
            'name': 'NFC UID Test',
            'code': 'NFC-FMT-002',
            'site_id': self.site.id,
            'scan_type': 'nfc',
            'nfc_tag_id': '04:80:CC:01:06:02:03',
            'latitude': self.test_lat,
            'longitude': self.test_lng,
            'status': 'active',
        })
        self.assertTrue(
            uid_checkpoint._nfc_tags_match('04:80:CC:01:06:02:03', '0480CC01060203')
        )
        self.assertEqual(
            uid_checkpoint._nfc_format_for_display('0480CC01060203'),
            '04:80:cc:01:06:02:03',
        )
        prepared = self.env['checkpoint']._prepare_nfc_tag_id('043CCA6D396180')
        self.assertEqual(prepared, '04:3c:ca:6d:39:61:80')

    _logger.info("GUARD PRO NFC & QR CODE TESTING SUITE")
    _logger.info("="*70)
    
    # Note: Tests will be run by Odoo's test framework
    # Use: odoo-bin -c odoo.conf -u guardpro --test-enable --log-level=test
    
    _logger.info("\nTo run these tests, execute:")
    _logger.info("odoo-bin -c odoo.conf -d DATABASE -u guardpro --test-enable")
    _logger.info("="*70)


if __name__ == '__main__':
    run_all_tests()

