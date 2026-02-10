# -*- coding: utf-8 -*-
"""Manual Tour Generation Wizard."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TourManualGenerationWizard(models.TransientModel):
    """Wizard for manually generating tours."""

    _name = 'tour.manual.generation.wizard'
    _description = 'Manual Tour Generation Wizard'

    # Basic Information
    tour_id = fields.Many2one(
        'security.tour',
        string='Tour',
        required=True,
        readonly=True
    )
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True,
        readonly=True
    )
    
    # Guard Selection
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        domain="[('site_ids', 'in', [site_id]), ('status', '=', 'active')]"
    )
    
    # Tour Configuration
    start_time = fields.Datetime(
        string='Start Time',
        required=True,
        default=fields.Datetime.now,
        help='When the tour should start'
    )
    notes = fields.Text(
        string='Notes',
        help='Additional notes for this manual tour generation'
    )
    
    # Tour Information (Read-only)
    tour_name = fields.Char(
        string='Tour Name',
        related='tour_id.name',
        readonly=True
    )
    tour_code = fields.Char(
        string='Tour Code',
        related='tour_id.code',
        readonly=True
    )
    estimated_duration = fields.Float(
        string='Estimated Duration (hours)',
        related='tour_id.estimated_duration',
        readonly=True
    )
    total_checkpoints = fields.Integer(
        string='Total Checkpoints',
        related='tour_id.total_checkpoints',
        readonly=True
    )

    @api.onchange('guard_id')
    def _onchange_guard_id(self):
        """Validate guard is assigned to the site."""
        if self.guard_id and self.site_id:
            if self.site_id not in self.guard_id.site_ids:
                return {
                    'warning': {
                        'title': _('Warning'),
                        'message': _('The selected guard is not assigned to this site.')
                    }
                }

    def action_generate_tour(self):
        """Generate the tour manually."""
        self.ensure_one()
        
        if not self.guard_id:
            raise ValidationError(_('Please select a guard!'))
        
        if not self.tour_id:
            raise ValidationError(_('Tour is required!'))
        
        if self.tour_id.status != 'active':
            raise ValidationError(_(
                'Cannot generate tour for inactive tour!'
            ))
        
        # Check if guard is available (not on another active tour)
        existing_tours = self.env['tour.log'].search([
            ('guard_id', '=', self.guard_id.id),
            ('status', '=', 'in_progress')
        ])
        
        if existing_tours:
            tour_names = ', '.join(existing_tours.mapped('tour_id.name'))
            raise ValidationError(_(
                'Guard %s is currently on active tour(s): %s\n\n'
                'Please complete existing tours before starting a new one.'
            ) % (self.guard_id.name, tour_names))
        
        # Create the tour log
        tour_log = self.env['tour.log'].create({
            'tour_id': self.tour_id.id,
            'guard_id': self.guard_id.id,
            'site_id': self.site_id.id,
            'start_time': self.start_time,
            'status': 'in_progress',
            'expected_checkpoints': self.tour_id.total_checkpoints,
            'notes': self.notes or 'Manually generated tour'
        })
        
        # Log the manual generation
        _logger.info(
            'Manual tour generated: Tour=%s, Guard=%s, Start=%s',
            self.tour_id.name, self.guard_id.name, self.start_time
        )
        
        # Show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tour Generated Successfully'),
                'message': _(
                    'Tour "%s" has been manually generated for guard %s.\n'
                    'Tour Log ID: %s'
                ) % (self.tour_id.name, self.guard_id.name, tour_log.name),
                'type': 'success',
                'sticky': True,
            }
        }

    def action_view_tour_log(self):
        """View the generated tour log."""
        self.ensure_one()
        
        # Find the most recent tour log for this guard and tour
        tour_log = self.env['tour.log'].search([
            ('tour_id', '=', self.tour_id.id),
            ('guard_id', '=', self.guard_id.id)
        ], order='start_time desc', limit=1)
        
        if not tour_log:
            raise ValidationError(_('No tour log found!'))
        
        return {
            'name': _('Tour Log - %s') % tour_log.name,
            'type': 'ir.actions.act_window',
            'res_model': 'tour.log',
            'res_id': tour_log.id,
            'view_mode': 'form',
            'target': 'current'
        }
