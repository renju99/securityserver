# -*- coding: utf-8 -*-
"""Tests for facility issues created from checkpoint patrol scans."""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestFacilityPatrolIssue(TransactionCase):
    """Facility issue workflow on checkpoint scans."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env['res.partner'].create({
            'name': 'FM Test Client',
            'is_company': True,
        })
        cls.site = cls.env['client.site'].create({
            'name': 'Test Site FM',
            'code': 'FM-SITE-01',
            'client_id': cls.client.id,
            'address': 'FM Test Address',
            'city': 'Dubai',
            'latitude': 25.2048,
            'longitude': 55.2708,
            'status': 'active',
        })
        cls.guard = cls.env['guard.profile'].create({
            'name': 'FM Test Guard',
            'badge_number': 'FM-001',
            'phone': '+971500000099',
            'status': 'active',
        })
        cls.checkpoint = cls.env['checkpoint'].create({
            'name': 'FM Checkpoint',
            'code': 'FM-CP',
            'site_id': cls.site.id,
            'scan_type': 'nfc',
            'nfc_tag_id': 'FM-NFC-TEST',
            'status': 'active',
        })
        cls.tour = cls.env['security.tour'].create({
            'name': 'FM Tour',
            'code': 'FM-TOUR',
            'site_id': cls.site.id,
            'status': 'active',
        })
        cls.tour_log = cls.env['tour.log'].create({
            'tour_id': cls.tour.id,
            'guard_id': cls.guard.id,
            'site_id': cls.site.id,
            'expected_checkpoints': 1,
        })
        cls.scan = cls.env['checkpoint.scan'].create({
            'checkpoint_id': cls.checkpoint.id,
            'guard_id': cls.guard.id,
            'site_id': cls.site.id,
            'tour_log_id': cls.tour_log.id,
            'scan_time': '2026-05-20 12:00:00',
            'scan_type': 'nfc',
            'status': 'verified',
        })
        cls.category = cls.env.ref('guardpro.incident_cat_facility_patrol')

    def test_facility_issue_requires_description(self):
        """Issue flag without enough detail must fail validation."""
        with self.assertRaises(ValidationError):
            self.scan.append_post_scan_evidence(
                issues_found=True,
                facility_issue_type='lighting',
                issue_description='short',
            )

    def test_facility_issue_creates_incident(self):
        """Reporting an issue creates a linked facility incident."""
        self.scan.append_post_scan_evidence(
            observations_text='Pool area dark',
            issues_found=True,
            facility_issue_type='lighting',
            issue_description='Multiple lights out near main entrance',
        )
        self.assertTrue(self.scan.issues_found)
        self.assertTrue(self.scan.facility_incident_id)
        incident = self.scan.facility_incident_id
        self.assertEqual(incident.category_id, self.category)
        self.assertEqual(incident.source, 'patrol_checkpoint')
        self.assertEqual(incident.checkpoint_scan_id, self.scan)
        self.assertEqual(incident.tour_log_id, self.tour_log)
        self.assertEqual(
            incident.incident_datetime,
            self.scan.scan_time,
        )
        self.assertEqual(incident.status, 'submitted')
        self.assertTrue(incident.is_facility_patrol)

    def test_facility_issue_update_not_duplicate(self):
        """Second save updates the same incident."""
        self.scan.append_post_scan_evidence(
            issues_found=True,
            facility_issue_type='plumbing',
            issue_description='Water leak at checkpoint area',
        )
        first_id = self.scan.facility_incident_id.id
        self.scan.append_post_scan_evidence(
            issue_description='Water leak spreading — urgent',
        )
        self.assertEqual(self.scan.facility_incident_id.id, first_id)

    def test_tour_log_facility_count(self):
        """Tour log counts linked facility incidents."""
        self.scan.append_post_scan_evidence(
            issues_found=True,
            facility_issue_type='cleanliness',
            issue_description='Trash overflow at checkpoint',
        )
        self.tour_log.invalidate_recordset(['facility_incident_count'])
        self.assertEqual(self.tour_log.facility_incident_count, 1)
