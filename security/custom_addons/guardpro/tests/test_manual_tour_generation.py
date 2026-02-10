# -*- coding: utf-8 -*-
"""Test Manual Tour Generation Functionality."""

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TestManualTourGeneration(TransactionCase):
    """Test manual tour generation functionality."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        
        # Create test site
        self.site = self.env['client.site'].create({
            'name': 'Test Site',
            'address': '123 Test Street',
            'latitude': 40.7128,
            'longitude': -74.0060
        })
        
        # Create test guard
        self.guard = self.env['guard.profile'].create({
            'name': 'Test Guard',
            'employee_id': self.env['hr.employee'].create({
                'name': 'Test Guard Employee'
            }).id,
            'site_id': self.site.id,
            'active': True
        })
        
        # Create test checkpoint
        self.checkpoint = self.env['checkpoint'].create({
            'name': 'Test Checkpoint',
            'code': 'TC001',
            'site_id': self.site.id,
            'latitude': 40.7128,
            'longitude': -74.0060,
            'scan_type': 'nfc_tag'
        })
        
        # Create test tour
        self.tour = self.env['security.tour'].create({
            'name': 'Test Tour',
            'code': 'TT001',
            'site_id': self.site.id,
            'status': 'active',
            'estimated_duration': 1.0,
            'frequency': 'hourly',
            'checkpoint_ids': [(6, 0, [self.checkpoint.id])]
        })

    def test_manual_tour_generation_wizard_creation(self):
        """Test manual tour generation wizard creation."""
        wizard = self.env['tour.manual.generation.wizard'].create({
            'tour_id': self.tour.id,
            'site_id': self.site.id,
            'guard_id': self.guard.id,
            'start_time': '2024-01-01 10:00:00',
            'notes': 'Test manual generation'
        })
        
        self.assertEqual(wizard.tour_id, self.tour)
        self.assertEqual(wizard.guard_id, self.guard)
        self.assertEqual(wizard.site_id, self.site)
        self.assertEqual(wizard.notes, 'Test manual generation')

    def test_manual_tour_generation_success(self):
        """Test successful manual tour generation."""
        wizard = self.env['tour.manual.generation.wizard'].create({
            'tour_id': self.tour.id,
            'site_id': self.site.id,
            'guard_id': self.guard.id,
            'start_time': '2024-01-01 10:00:00',
            'notes': 'Test manual generation'
        })
        
        # Generate the tour
        result = wizard.action_generate_tour()
        
        # Check that tour log was created
        tour_log = self.env['tour.log'].search([
            ('tour_id', '=', self.tour.id),
            ('guard_id', '=', self.guard.id)
        ])
        
        self.assertTrue(tour_log)
        self.assertEqual(tour_log.status, 'in_progress')
        self.assertEqual(tour_log.expected_checkpoints, 1)
        self.assertEqual(tour_log.notes, 'Manually generated tour')

    def test_manual_tour_generation_inactive_tour(self):
        """Test manual tour generation fails for inactive tour."""
        # Set tour to inactive
        self.tour.write({'status': 'inactive'})
        
        wizard = self.env['tour.manual.generation.wizard'].create({
            'tour_id': self.tour.id,
            'site_id': self.site.id,
            'guard_id': self.guard.id,
            'start_time': '2024-01-01 10:00:00'
        })
        
        # Should raise validation error
        with self.assertRaises(ValidationError):
            wizard.action_generate_tour()

    def test_manual_tour_generation_guard_busy(self):
        """Test manual tour generation fails when guard is busy."""
        # Create existing in-progress tour for guard
        self.env['tour.log'].create({
            'tour_id': self.tour.id,
            'guard_id': self.guard.id,
            'site_id': self.site.id,
            'start_time': '2024-01-01 09:00:00',
            'status': 'in_progress'
        })
        
        wizard = self.env['tour.manual.generation.wizard'].create({
            'tour_id': self.tour.id,
            'site_id': self.site.id,
            'guard_id': self.guard.id,
            'start_time': '2024-01-01 10:00:00'
        })
        
        # Should raise validation error
        with self.assertRaises(ValidationError):
            wizard.action_generate_tour()

    def test_security_tour_manual_generate_action(self):
        """Test security tour manual generate action."""
        # Test the action method
        result = self.tour.action_manual_generate_tour()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'tour.manual.generation.wizard')
        self.assertEqual(result['view_mode'], 'form')
        self.assertEqual(result['target'], 'new')
        self.assertEqual(result['context']['default_tour_id'], self.tour.id)

    def test_security_tour_manual_generate_inactive(self):
        """Test manual generate action fails for inactive tour."""
        # Set tour to inactive
        self.tour.write({'status': 'inactive'})
        
        # Should raise validation error
        with self.assertRaises(ValidationError):
            self.tour.action_manual_generate_tour()

    def test_wizard_guard_domain(self):
        """Test that guard domain filters correctly."""
        # Create another guard for different site
        other_site = self.env['client.site'].create({
            'name': 'Other Site',
            'address': '456 Other Street'
        })
        
        other_guard = self.env['guard.profile'].create({
            'name': 'Other Guard',
            'employee_id': self.env['hr.employee'].create({
                'name': 'Other Guard Employee'
            }).id,
            'site_id': other_site.id,
            'active': True
        })
        
        wizard = self.env['tour.manual.generation.wizard'].create({
            'tour_id': self.tour.id,
            'site_id': self.site.id
        })
        
        # Test onchange guard_id
        wizard.guard_id = other_guard
        wizard._onchange_guard_id()
        
        # Site should not change because guard is from different site
        self.assertEqual(wizard.site_id, self.site)
