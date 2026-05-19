# -*- coding: utf-8 -*-
"""Security Tour Model - Patrol Routes."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SecurityTour(models.Model):
    """Security Tour defining patrol routes and checkpoints."""

    _name = 'security.tour'
    _description = 'Security Tour / Patrol Route'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'site_id, name'

    # Basic Information
    name = fields.Char(
        string='Tour Name',
        required=True,
        tracking=True,
        index=True
    )
    code = fields.Char(
        string='Tour Code',
        required=True,
        copy=False,
        tracking=True
    )
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    # Location Hierarchy (optional - tours can be site-wide or specific to locations)
    building_id = fields.Many2one(
        'site.building',
        string='Building',
        domain="[('site_id', '=', site_id)]",
        tracking=True,
        help='Specific building for this tour (leave empty for site-wide tours)'
    )
    floor_id = fields.Many2one(
        'building.floor',
        string='Floor',
        domain="[('building_id', '=', building_id)]",
        tracking=True,
        help='Specific floor for this tour (leave empty for building-wide or site-wide tours)'
    )
    area_id = fields.Many2one(
        'floor.area',
        string='Area/Room',
        domain="[('floor_id', '=', floor_id)]",
        tracking=True,
        help='Specific area/room for this tour (leave empty for floor-wide, building-wide, or site-wide tours)'
    )

    # Tour Configuration
    description = fields.Text(
        string='Description'
    )
    status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string='Status', default='draft', required=True, tracking=True)
    
    # Checkpoints
    checkpoint_ids = fields.Many2many(
        'checkpoint',
        'tour_checkpoint_rel',
        'tour_id',
        'checkpoint_id',
        string='Checkpoints',
        help='Ordered list of checkpoints for this tour'
    )
    checkpoint_sequence = fields.Text(
        string='Checkpoint Sequence',
        help='JSON array defining the order of checkpoints'
    )
    total_checkpoints = fields.Integer(
        string='Total Checkpoints',
        compute='_compute_total_checkpoints',
        store=True
    )
    
    # Timing
    estimated_duration = fields.Float(
        string='Estimated Duration (hours)',
        help='Expected time to complete the tour',
        default=1.0
    )
    frequency = fields.Selection([
        ('hourly', 'Hourly'),
        ('every_2_hours', 'Every 2 Hours'),
        ('every_4_hours', 'Every 4 Hours'),
        ('daily', 'Daily'),
        ('custom', 'Custom')
    ], string='Tour Frequency', default='hourly')
    frequency_custom = fields.Char(
        string='Custom Frequency',
        tracking=True,
        help='Describe the patrol schedule when Tour Frequency is Custom '
             '(e.g. "Twice per night shift", "Mon/Wed/Fri at 22:00").'
    )
    frequency_display = fields.Char(
        string='Frequency (display)',
        compute='_compute_frequency_display',
        store=True,
    )
    
    # Requirements
    requires_supervisor = fields.Boolean(
        string='Requires Supervisor Approval',
        default=False
    )
    requires_photos = fields.Boolean(
        string='Require Photos at Checkpoints',
        default=False
    )
    requires_notes = fields.Boolean(
        string='Require Notes',
        default=False
    )
    
    # GPS Configuration for Virtual Checkpoints
    gps_tolerance = fields.Float(
        string='GPS Tolerance (meters)',
        default=50.0,
        help='Default GPS tolerance for virtual checkpoints in this tour. If set, this overrides individual checkpoint tolerances. Leave empty to use checkpoint-specific tolerances.',
        tracking=True
    )
    use_tour_tolerance = fields.Boolean(
        string='Use Tour Tolerance',
        default=False,
        help='If enabled, all virtual checkpoints in this tour will use the tour tolerance instead of their individual tolerances',
        tracking=True
    )
    
    # Tour Logs
    tour_log_ids = fields.One2many(
        'tour.log',
        'tour_id',
        string='Tour Logs'
    )
    
    # Statistics
    total_tours = fields.Integer(
        string='Total Tours Completed',
        compute='_compute_statistics',
        store=True
    )
    completion_rate = fields.Float(
        string='Completion Rate %',
        compute='_compute_statistics',
        store=True
    )
    average_duration = fields.Float(
        string='Average Duration (hours)',
        compute='_compute_statistics',
        store=True
    )
    
    # Instructions
    instructions = fields.Html(
        string='Tour Instructions',
        help='Detailed instructions for guards'
    )
    special_requirements = fields.Text(
        string='Special Requirements'
    )
    
    # Notes
    notes = fields.Text(
        string='Internal Notes'
    )
    
    _sql_constraints = [
        ('code_unique', 'unique(code)',
         'Tour code must be unique!'),
    ]

    @api.depends('frequency', 'frequency_custom')
    def _compute_frequency_display(self):
        """Human-readable frequency for reports and mobile."""
        labels = dict(self._fields['frequency'].selection)
        for record in self:
            if record.frequency == 'custom' and record.frequency_custom:
                record.frequency_display = record.frequency_custom.strip()
            elif record.frequency:
                record.frequency_display = labels.get(record.frequency, record.frequency)
            else:
                record.frequency_display = False

    @api.onchange('frequency')
    def _onchange_frequency(self):
        """Clear custom text when a preset frequency is chosen."""
        if self.frequency != 'custom':
            self.frequency_custom = False

    @api.depends('checkpoint_ids')
    def _compute_total_checkpoints(self):
        """Count total checkpoints in tour."""
        for record in self:
            record.total_checkpoints = len(record.checkpoint_ids)

    @api.depends('tour_log_ids', 'tour_log_ids.status', 'tour_log_ids.duration')
    def _compute_statistics(self):
        """Compute tour statistics."""
        for record in self:
            logs = record.tour_log_ids
            record.total_tours = len(logs.filtered(
                lambda l: l.status == 'completed'
            ))
            
            total_logs = len(logs)
            if total_logs:
                completed = len(logs.filtered(lambda l: l.status == 'completed'))
                # Store as decimal (0.0-1.0) for percentage widget which multiplies by 100 automatically
                record.completion_rate = completed / total_logs
            else:
                record.completion_rate = 0.0
            
            completed_logs = logs.filtered(lambda l: l.status == 'completed' and l.duration)
            if completed_logs:
                record.average_duration = sum(
                    completed_logs.mapped('duration')
                ) / len(completed_logs)
            else:
                record.average_duration = 0.0

    @api.onchange('building_id')
    def _onchange_building_id(self):
        """Update site_id when building is selected."""
        if self.building_id and not self.site_id:
            self.site_id = self.building_id.site_id

    @api.onchange('floor_id')
    def _onchange_floor_id(self):
        """Update building_id and site_id when floor is selected."""
        if self.floor_id:
            if not self.building_id:
                self.building_id = self.floor_id.building_id
            if not self.site_id:
                self.site_id = self.floor_id.site_id

    @api.onchange('area_id')
    def _onchange_area_id(self):
        """Update floor_id, building_id and site_id when area is selected."""
        if self.area_id:
            if not self.floor_id:
                self.floor_id = self.area_id.floor_id
            if not self.building_id:
                self.building_id = self.area_id.building_id
            if not self.site_id:
                self.site_id = self.area_id.site_id

    @api.constrains('estimated_duration')
    def _check_duration(self):
        """Validate estimated duration."""
        for record in self:
            if record.estimated_duration <= 0:
                raise ValidationError(_(
                    'Estimated duration must be greater than 0!'
                ))

    @api.constrains('frequency', 'frequency_custom')
    def _check_frequency_custom(self):
        """Require a description when frequency is Custom."""
        for record in self:
            if record.frequency == 'custom' and not (record.frequency_custom or '').strip():
                raise ValidationError(_(
                    'Please describe the custom tour frequency '
                    '(e.g. "Twice per shift" or "Every 30 minutes").'
                ))

    def action_activate(self):
        """Activate the tour."""
        self.write({'status': 'active'})

    def action_deactivate(self):
        """Deactivate the tour."""
        self.write({'status': 'inactive'})

    def action_view_logs(self):
        """Open tour logs."""
        self.ensure_one()
        return {
            'name': _('Tour Logs - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'tour.log',
            'view_mode': 'list,form',
            'domain': [('tour_id', '=', self.id)],
            'context': {'default_tour_id': self.id}
        }

    def start_tour(self, guard_id):
        """
        Start a new tour for a guard.
        Automatically completes any existing in-progress tours for this guard.
        
        Args:
            guard_id (int): ID of the guard starting the tour
            
        Returns:
            dict: Tour log record data
        """
        self.ensure_one()
        
        if self.status not in ['active', 'draft']:
            raise ValidationError(_(
                'Cannot start inactive tour!'
            ))
        
        # Auto-activate draft tours when started
        if self.status == 'draft':
            _logger.info('Auto-activating draft tour %s upon start', self.id)
            self.action_activate()
        
        # Auto-complete ANY existing in-progress tours for this guard (any tour)
        # This handles browser refresh, crashes, and multiple tour scenarios
        existing_tours = self.env['tour.log'].search([
            ('guard_id', '=', guard_id),
            ('status', '=', 'in_progress')
        ])
        
        if existing_tours:
            _logger.info(
                'Auto-completing %d existing in-progress tour(s) for guard %s before starting new tour',
                len(existing_tours), guard_id
            )
            for old_tour in existing_tours:
                try:
                    old_tour.action_complete(
                        partial=True,
                        reason='Auto-completed: New tour started'
                    )
                    _logger.info('Successfully auto-completed tour %s', old_tour.id)
                except Exception as e:
                    _logger.warning('Failed to auto-complete old tour %s: %s', old_tour.id, str(e))
                    # Force close it anyway
                    old_tour.write({
                        'status': 'completed',
                        'end_time': fields.Datetime.now()
                    })
                    _logger.info('Force-closed tour %s', old_tour.id)
        
        tour_log = self.env['tour.log'].create({
            'tour_id': self.id,
            'guard_id': guard_id,
            'site_id': self.site_id.id,
            'start_time': fields.Datetime.now(),
            'status': 'in_progress',
            'expected_checkpoints': self.total_checkpoints,
            'gps_tolerance': self.gps_tolerance if self.use_tour_tolerance else False
        })
        
        return {
            'tour_log_id': tour_log.id,
            'checkpoints': self.checkpoint_ids.read([
                'id', 'name', 'code', 'latitude', 'longitude',
                'scan_type', 'nfc_tag_id', 'qr_code'
            ])
        }

    def action_manual_generate_tour(self):
        """
        Manual tour generation action.
        Opens a wizard to select guard and generate tour manually.
        """
        self.ensure_one()
        
        if self.status != 'active':
            raise ValidationError(_(
                'Cannot generate tour for inactive tour!'
            ))
        
        return {
            'name': _('Manual Tour Generation - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'tour.manual.generation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tour_id': self.id,
                'default_site_id': self.site_id.id
            }
        }

