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
        string='Project',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    zone_id = fields.Many2one(
        'site.zone',
        string='Zone',
        domain="[('site_id', '=', site_id)]",
        ondelete='set null',
        tracking=True,
        index=True,
        help='Operational zone for this tour (used for user access filtering)',
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
    
    # Checkpoints (ordered via checkpoint_line_ids)
    checkpoint_line_ids = fields.One2many(
        'security.tour.checkpoint.line',
        'tour_id',
        string='Checkpoint Sequence',
        copy=True,
        help='Patrol order for checkpoints in this tour',
    )
    checkpoint_ids = fields.Many2many(
        'checkpoint',
        'tour_checkpoint_rel',
        'tour_id',
        'checkpoint_id',
        string='Checkpoints',
        help='Checkpoints linked to this tour (kept in sync with checkpoint sequence lines)',
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

    @api.depends('checkpoint_line_ids', 'checkpoint_ids')
    def _compute_total_checkpoints(self):
        """Count total checkpoints in tour."""
        for record in self:
            if record.checkpoint_line_ids:
                record.total_checkpoints = len(record.checkpoint_line_ids)
            else:
                record.total_checkpoints = len(record.checkpoint_ids)

    @api.model_create_multi
    def create(self, vals_list):
        tours = super().create(vals_list)
        for tour, vals in zip(tours, vals_list):
            checkpoint_order = tour._extract_checkpoint_order_from_commands(
                vals.get('checkpoint_ids')
            )
            if checkpoint_order:
                tour._rebuild_checkpoint_lines(checkpoint_order)
            elif vals.get('checkpoint_line_ids'):
                tour._sync_checkpoint_ids_from_lines()
            elif tour.checkpoint_ids:
                tour._ensure_checkpoint_lines()
        return tours

    def write(self, vals):
        if self.env.context.get('skip_checkpoint_sync'):
            return super().write(vals)
        checkpoint_order = None
        if 'checkpoint_ids' in vals and 'checkpoint_line_ids' not in vals:
            checkpoint_order = self._extract_checkpoint_order_from_commands(
                vals['checkpoint_ids']
            )
        res = super().write(vals)
        if checkpoint_order is not None:
            self._rebuild_checkpoint_lines(checkpoint_order)
        elif 'checkpoint_line_ids' in vals:
            self._sync_checkpoint_ids_from_lines()
        return res

    @api.model
    def _extract_checkpoint_order_from_commands(self, commands):
        """Return checkpoint id list from a replace-all M2M command, if present."""
        if not commands:
            return None
        for command in commands:
            if command[0] == 6:
                return list(command[2])
        return None

    def _ensure_checkpoint_lines(self):
        """Create sequence lines from existing M2M links (upgrade / legacy data)."""
        for tour in self:
            if tour.checkpoint_line_ids or not tour.checkpoint_ids:
                continue
            tour._rebuild_checkpoint_lines(tour._get_m2m_checkpoint_order())

    def _get_m2m_checkpoint_order(self):
        """Build checkpoint order from legacy M2M links (stable by checkpoint id)."""
        self.ensure_one()
        self.env.cr.execute(
            """
            SELECT checkpoint_id
            FROM tour_checkpoint_rel
            WHERE tour_id = %s
            ORDER BY checkpoint_id
            """,
            (self.id,),
        )
        ordered_ids = [row[0] for row in self.env.cr.fetchall()]
        if ordered_ids:
            return ordered_ids
        return self.checkpoint_ids.ids

    def _rebuild_checkpoint_lines(self, checkpoint_ids):
        """Replace sequence lines using the given checkpoint id order."""
        Line = self.env['security.tour.checkpoint.line']
        for tour in self:
            tour.checkpoint_line_ids.unlink()
            if not checkpoint_ids:
                tour.checkpoint_ids = [(5, 0, 0)]
                continue
            sequence = 10
            line_vals = []
            for checkpoint_id in checkpoint_ids:
                line_vals.append({
                    'tour_id': tour.id,
                    'checkpoint_id': checkpoint_id,
                    'sequence': sequence,
                })
                sequence += 10
            Line.create(line_vals)
            tour.with_context(skip_checkpoint_sync=True).write({
                'checkpoint_ids': [(6, 0, list(checkpoint_ids))],
            })

    def _sync_checkpoint_ids_from_lines(self):
        """Keep legacy M2M field aligned with ordered sequence lines."""
        for tour in self:
            ordered_ids = tour.checkpoint_line_ids.sorted('sequence').mapped(
                'checkpoint_id'
            ).ids
            if ordered_ids != tour.checkpoint_ids.ids:
                tour.with_context(skip_checkpoint_sync=True).write({
                    'checkpoint_ids': [(6, 0, ordered_ids)],
                })

    def get_ordered_checkpoints(self):
        """Return checkpoints in patrol sequence for mobile and reports."""
        self.ensure_one()
        if not self.checkpoint_line_ids:
            self._ensure_checkpoint_lines()
        if self.checkpoint_line_ids:
            return self.checkpoint_line_ids.sorted('sequence').mapped('checkpoint_id')
        return self.checkpoint_ids.sorted(key=lambda cp: (cp.name or '').lower())

    def get_ordered_checkpoint_lines(self):
        """Return sequence lines sorted for display."""
        self.ensure_one()
        if not self.checkpoint_line_ids:
            self._ensure_checkpoint_lines()
        return self.checkpoint_line_ids.sorted('sequence')

    def get_checkpoint_api_payloads(self, scanned_checkpoint_ids=None):
        """Build ordered checkpoint dicts for mobile/API consumers."""
        self.ensure_one()
        scanned = set(scanned_checkpoint_ids or [])
        payloads = []
        for seq, checkpoint in enumerate(self.get_ordered_checkpoints(), start=1):
            payloads.append({
                'id': checkpoint.id,
                'name': checkpoint.name,
                'code': checkpoint.code,
                'scan_type': checkpoint.scan_type,
                'latitude': checkpoint.latitude,
                'longitude': checkpoint.longitude,
                'qr_code': checkpoint.qr_code or '',
                'nfc_tag_id': checkpoint.nfc_tag_id or '',
                'nfc_tag_normalized': checkpoint._prepare_nfc_tag_id(
                    checkpoint.nfc_tag_id
                ) if checkpoint.nfc_tag_id else '',
                'notes': checkpoint.notes or '',
                'sequence': seq * 10,
                'sequence_number': seq,
                'is_scanned': checkpoint.id in scanned,
                'status': 'completed' if checkpoint.id in scanned else 'pending',
            })
        return payloads

    @api.model
    def migrate_all_tour_checkpoint_sequences(self):
        """Post-install hook: build sequence lines for existing tours."""
        tours = self.search([('checkpoint_ids', '!=', False)])
        for tour in tours:
            if not tour.checkpoint_line_ids:
                tour._ensure_checkpoint_lines()
        _logger.info(
            'Migrated checkpoint sequence lines for %d security tour(s)',
            len(tours),
        )

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

    @api.onchange('zone_id')
    def _onchange_zone_id(self):
        if self.zone_id and not self.site_id:
            self.site_id = self.zone_id.site_id

    @api.onchange('building_id')
    def _onchange_building_id(self):
        """Update site_id when building is selected."""
        if self.building_id:
            if not self.site_id:
                self.site_id = self.building_id.site_id
            if not self.zone_id and self.building_id.zone_id:
                self.zone_id = self.building_id.zone_id

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
        
        existing_tours = self.env['tour.log'].search([
            ('guard_id', '=', guard_id),
            ('status', '=', 'in_progress'),
        ], order='start_time desc')

        if existing_tours:
            same_tour_log = existing_tours.filtered(
                lambda log: log.tour_id.id == self.id
            )[:1]
            if same_tour_log:
                _logger.info(
                    'Resuming in-progress tour log %s for guard %s (tour %s)',
                    same_tour_log.id, guard_id, self.name,
                )
                return self._tour_start_response(same_tour_log, resumed=True)

            blocking = existing_tours[0]
            return {
                'blocked': True,
                'message': _(
                    'You have an unfinished patrol (%(tour)s). '
                    'Continue it on the Tours screen or use Partial Completion '
                    'to end it before starting another tour.',
                    tour=blocking.tour_id.name,
                ),
                'blocking_tours': [
                    self._tour_blocking_payload(log)
                    for log in existing_tours
                ],
            }

        tour_log = self.env['tour.log'].create({
            'tour_id': self.id,
            'guard_id': guard_id,
            'site_id': self.site_id.id,
            'start_time': fields.Datetime.now(),
            'status': 'in_progress',
            'expected_checkpoints': self.total_checkpoints,
            'gps_tolerance': self.gps_tolerance if self.use_tour_tolerance else False
        })
        
        checkpoints = []
        for seq, checkpoint in enumerate(self.get_ordered_checkpoints(), start=1):
            checkpoints.append({
                'id': checkpoint.id,
                'name': checkpoint.name,
                'code': checkpoint.code,
                'latitude': checkpoint.latitude,
                'longitude': checkpoint.longitude,
                'scan_type': checkpoint.scan_type,
                'nfc_tag_id': checkpoint.nfc_tag_id,
                'qr_code': checkpoint.qr_code,
                'sequence': seq * 10,
                'sequence_number': seq,
            })
        return self._tour_start_response(tour_log, resumed=False, checkpoints=checkpoints)

    def _tour_blocking_payload(self, tour_log):
        """Serialize an in-progress tour log for mobile conflict UI."""
        return {
            'tour_log_id': tour_log.id,
            'tour_id': tour_log.tour_id.id,
            'tour_name': tour_log.tour_id.name,
            'start_time': fields.Datetime.to_string(tour_log.start_time),
            'scanned_checkpoints': tour_log.scanned_checkpoints,
            'expected_checkpoints': tour_log.expected_checkpoints,
            'completion_percentage': (
                tour_log.completion_percentage / 100.0
                if tour_log.completion_percentage else 0.0
            ),
        }

    def _tour_start_response(self, tour_log, resumed=False, checkpoints=None):
        """Build start/resume API payload with checkpoint list."""
        if checkpoints is None:
            scanned_ids = tour_log.scan_ids.filtered(
                lambda s: s.status == 'verified'
            ).mapped('checkpoint_id').ids
            checkpoints = []
            for seq, checkpoint in enumerate(
                tour_log.tour_id.get_ordered_checkpoints(), start=1
            ):
                checkpoints.append({
                    'id': checkpoint.id,
                    'name': checkpoint.name,
                    'code': checkpoint.code,
                    'latitude': checkpoint.latitude,
                    'longitude': checkpoint.longitude,
                    'scan_type': checkpoint.scan_type,
                    'nfc_tag_id': checkpoint.nfc_tag_id,
                    'qr_code': checkpoint.qr_code,
                    'sequence': seq * 10,
                    'sequence_number': seq,
                    'scanned': checkpoint.id in scanned_ids,
                })
        return {
            'tour_log_id': tour_log.id,
            'resumed': resumed,
            'checkpoints': checkpoints,
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

