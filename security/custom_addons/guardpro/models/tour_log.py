# -*- coding: utf-8 -*-
"""Tour Log Model - Tour Execution Tracking."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup
import logging
from ..common import geo_utils
from ..common.image_optimizer import ImageOptimizer

_logger = logging.getLogger(__name__)


class TourLog(models.Model):
    """Tour Execution Log."""

    _name = 'tour.log'
    _description = 'Tour Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_time desc'

    # Basic Information
    name = fields.Char(
        string='Log Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True
    )
    # Tour logs are compliance records. Keep them even if the tour
    # definition is later edited/retired (RESTRICT), and when the
    # guard/shift disappears we still retain the log (SET NULL on
    # non-required fields, RESTRICT on required).
    tour_id = fields.Many2one(
        'security.tour',
        string='Tour',
        required=True,
        tracking=True,
        index=True,
        ondelete='restrict'
    )
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        tracking=True,
        index=True,
        ondelete='restrict'
    )
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True,
        tracking=True,
        ondelete='restrict'
    )
    shift_id = fields.Many2one(
        'guard.shift',
        string='Related Shift',
        tracking=True,
        ondelete='set null'
    )

    # Location Hierarchy (inherited from tour or can be specific to this execution)
    building_id = fields.Many2one(
        'site.building',
        string='Building',
        domain="[('site_id', '=', site_id)]",
        tracking=True,
        help='Building where this tour was executed'
    )
    floor_id = fields.Many2one(
        'building.floor',
        string='Floor',
        domain="[('building_id', '=', building_id)]",
        tracking=True,
        help='Floor where this tour was executed'
    )
    area_id = fields.Many2one(
        'floor.area',
        string='Area/Room',
        domain="[('floor_id', '=', floor_id)]",
        tracking=True,
        help='Area/room where this tour was executed'
    )
    
    # Timing
    start_time = fields.Datetime(
        string='Start Time',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True
    )
    end_time = fields.Datetime(
        string='End Time',
        tracking=True
    )
    scheduled_end_time = fields.Datetime(
        string='Scheduled End Time',
        compute='_compute_scheduled_end_time',
        store=True,
        help='Expected end time based on start time and tour estimated duration',
        index=True
    )
    duration = fields.Float(
        string='Duration (hours)',
        compute='_compute_duration',
        store=True,
        digits=(10, 2)
    )
    
    # Status
    status = fields.Selection([
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('incomplete', 'Incomplete'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='in_progress', required=True, tracking=True)
    
    # Checkpoint Progress
    expected_checkpoints = fields.Integer(
        string='Expected Checkpoints'
    )
    # Note: These fields are updated via optimized SQL in checkpoint.scan.create()
    # to avoid lock contention during concurrent scans.
    # The _compute_checkpoint_progress() method is available for manual recomputation if needed.
    scanned_checkpoints = fields.Integer(
        string='Scanned Checkpoints',
        default=0,
        readonly=True,
        help='Number of verified checkpoint scans'
    )
    completion_percentage = fields.Float(
        string='Completion %',
        default=0.0,
        readonly=True,
        help='Percentage of checkpoints completed'
    )
    
    # Checkpoint Scans
    scan_ids = fields.One2many(
        'checkpoint.scan',
        'tour_log_id',
        string='Checkpoint Scans'
    )
    
    # GPS Tracking
    gps_track = fields.Text(
        string='GPS Track',
        help='JSON array of GPS coordinates during tour'
    )
    distance_traveled = fields.Float(
        string='Distance Traveled (km)',
        digits=(10, 2)
    )
    gps_tolerance = fields.Float(
        string='GPS Tolerance (meters)',
        help='GPS tolerance for virtual checkpoints in this tour. If set, overrides checkpoint-specific tolerances.'
    )
    
    # Incidents
    incident_ids = fields.One2many(
        'incident.report',
        'tour_log_id',
        string='Incidents Reported'
    )
    incident_count = fields.Integer(
        string='Incidents',
        compute='_compute_incident_count',
        store=True
    )
    
    # Tasks
    task_ids = fields.Many2many(
        'guard.task',
        'tour_log_task_rel',
        'tour_log_id',
        'task_id',
        string='Related Tasks',
        help='Tasks that must be completed before this tour can be finished'
    )
    pending_task_ids = fields.Many2many(
        'guard.task',
        string='Pending Tasks',
        compute='_compute_pending_tasks',
        help='Tasks that are not yet completed'
    )
    pending_task_count = fields.Integer(
        string='Pending Tasks Count',
        compute='_compute_pending_tasks',
        store=False
    )
    can_complete = fields.Boolean(
        string='Can Complete',
        compute='_compute_can_complete',
        help='Whether tour can be completed (all tasks must be completed)'
    )
    
    # Observations
    observations = fields.Text(
        string='Tour Summary Notes',
        tracking=True,
        help='Overall patrol summary. Checkpoint-level notes are aggregated in '
             'Checkpoint Findings and can be edited per scan below.',
    )
    issues_found = fields.Text(
        string='Tour Issues / Follow-up',
        tracking=True,
        help='Overall issues or supervisor follow-up for this tour.',
    )
    checkpoint_findings = fields.Text(
        string='Checkpoint Findings',
        compute='_compute_checkpoint_findings',
        store=True,
        readonly=True,
        help='Aggregated notes, issues, and media flags from checkpoint scans.',
    )
    has_checkpoint_findings = fields.Boolean(
        compute='_compute_checkpoint_findings',
        store=True,
    )
    checkpoint_issue_count = fields.Integer(
        string='Checkpoint Issues',
        compute='_compute_checkpoint_findings',
        store=True,
    )
    facility_incident_count = fields.Integer(
        string='Facility Work Orders',
        compute='_compute_facility_incident_count',
    )

    def _compute_facility_incident_count(self):
        for record in self:
            incidents = record.scan_ids.mapped('facility_incident_id').filtered(lambda i: i)
            record.facility_incident_count = len(incidents)

    def action_view_facility_incidents(self):
        self.ensure_one()
        incident_ids = self.scan_ids.mapped('facility_incident_id').ids
        return {
            'name': _('Facility Issues'),
            'type': 'ir.actions.act_window',
            'res_model': 'incident.report',
            'view_mode': 'list,form',
            'domain': [('id', 'in', incident_ids)],
            'context': {'create': False},
        }
    
    # Photos
    photo_ids = fields.Many2many(
        'ir.attachment',
        'tour_log_photo_rel',
        'tour_log_id',
        'attachment_id',
        string='Tour Photos'
    )
    
    # Review
    reviewed = fields.Boolean(
        string='Reviewed',
        default=False,
        tracking=True
    )
    reviewed_by = fields.Many2one(
        'res.users',
        string='Reviewed By'
    )
    review_notes = fields.Text(
        string='Review Notes'
    )
    
    # Notes
    notes = fields.Text(
        string='Notes'
    )
    
    # Partial Completion
    partial_completion_reason = fields.Text(
        string='Partial Completion Reason',
        help='Reason why tour was not fully completed'
    )
    is_partial_completion = fields.Boolean(
        string='Partially Completed',
        default=False,
        tracking=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Generate tour log sequence number."""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'tour.log'
                ) or _('New')
        records = super().create(vals_list)
        
        # Optimize attached photos
        for record in records:
            if record.photo_ids:
                record._optimize_photos()
        
        return records
    
    def write(self, vals):
        """Override write to optimize photos on update."""
        result = super().write(vals)
        if 'photo_ids' in vals:
            self._optimize_photos()
        return result
    
    def _optimize_photos(self):
        """Optimize photo attachments for storage and PDF rendering."""
        for record in self:
            for attachment in record.photo_ids.filtered(
                lambda a: a.mimetype and a.mimetype.startswith('image/')
            ):
                try:
                    # Skip if already optimized
                    if attachment.file_size and attachment.file_size < 300 * 1024:
                        continue
                    
                    original_data = attachment.datas
                    if not original_data:
                        continue
                    
                    # Optimize image
                    optimized_data = ImageOptimizer.optimize_image(
                        original_data,
                        max_dimension=1200,
                        target_format='JPEG'
                    )
                    
                    if optimized_data != original_data:
                        attachment.write({
                            'datas': optimized_data,
                            'mimetype': 'image/jpeg',
                        })
                        _logger.info(
                            'Optimized photo %s for tour log %s',
                            attachment.name,
                            record.name
                        )
                except Exception as e:
                    _logger.error(
                        'Failed to optimize photo %s: %s',
                        attachment.id,
                        str(e)
                    )

    @api.depends('start_time', 'tour_id.estimated_duration')
    def _compute_scheduled_end_time(self):
        """Calculate scheduled end time based on start time and estimated duration."""
        from datetime import timedelta
        for record in self:
            if record.start_time and record.tour_id.estimated_duration:
                hours = record.tour_id.estimated_duration
                record.scheduled_end_time = record.start_time + timedelta(hours=hours)
            else:
                record.scheduled_end_time = False

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        """Calculate tour duration."""
        for record in self:
            if record.start_time and record.end_time:
                delta = record.end_time - record.start_time
                record.duration = delta.total_seconds() / 3600.0
            else:
                record.duration = 0.0

    # Note: @api.depends decorator removed to prevent automatic recomputation
    # on every scan. Statistics are updated via optimized SQL in checkpoint.scan.create()
    # This method is kept for manual recomputation if needed.
    def _compute_checkpoint_progress(self):
        """Calculate checkpoint completion progress.
        
        This method is available for manual recomputation but is not automatically
        triggered to avoid database lock contention during concurrent scans.
        Use checkpoint.scan.create() which updates statistics via optimized SQL.
        """
        for record in self:
            verified_scans = record.scan_ids.filtered(
                lambda s: s.status == 'verified'
            )
            scanned = len(verified_scans)
            vals = {
                'scanned_checkpoints': scanned
            }
            
            if record.expected_checkpoints:
                vals['completion_percentage'] = (scanned / record.expected_checkpoints) * 100.0
            else:
                vals['completion_percentage'] = 0.0
            
            # Use sudo to bypass readonly constraint during recomputation
            record.sudo().write(vals)
    
    def action_recompute_progress(self):
        """Manually recompute tour checkpoint progress.
        
        This action can be called from the UI or via code to recalculate
        progress from scan history.
        """
        self._compute_checkpoint_progress()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Progress Updated'),
                'message': _('Tour checkpoint progress has been recomputed.'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.depends(
        'scan_ids.observations',
        'scan_ids.notes',
        'scan_ids.issues_found',
        'scan_ids.issue_description',
        'scan_ids.facility_issue_type',
        'scan_ids.scan_time',
        'scan_ids.checkpoint_id',
        'scan_ids.photo_ids',
        'scan_ids.video_ids',
    )
    def _compute_checkpoint_findings(self):
        """Roll up per-checkpoint scan notes for the Observations tab."""
        for record in self:
            blocks = []
            issue_count = 0
            for scan in record.scan_ids.sorted('scan_time'):
                body_parts = []
                obs = (scan.observations or '').strip()
                notes = (scan.notes or '').strip()
                if obs:
                    body_parts.append(obs)
                if notes and notes != obs:
                    body_parts.append(_('Notes: %s') % notes)
                if scan.issues_found:
                    issue_count += 1
                    type_label = dict(
                        scan._fields['facility_issue_type'].selection
                    ).get(scan.facility_issue_type, '')
                    desc = (scan.issue_description or '').strip()
                    if type_label:
                        body_parts.append(
                            _('Facility issue (%s): %s') % (
                                type_label,
                                desc or _('flagged'),
                            )
                        )
                    else:
                        body_parts.append(
                            _('Issue: %s') % (desc or _('flagged at checkpoint'))
                        )
                media_bits = []
                if scan.photo_ids:
                    media_bits.append(
                        _('%d photo(s)') % len(scan.photo_ids)
                    )
                if scan.video_ids:
                    media_bits.append(
                        _('%d video(s)') % len(scan.video_ids)
                    )
                if media_bits:
                    body_parts.append(_('Media: %s') % ', '.join(media_bits))
                if not body_parts:
                    continue
                cp = scan.checkpoint_id.display_name or _('Checkpoint')
                if scan.scan_time:
                    local_dt = fields.Datetime.context_timestamp(record, scan.scan_time)
                    time_str = local_dt.strftime('%Y-%m-%d %H:%M')
                    header = '[%s] %s' % (cp, time_str)
                else:
                    header = '[%s]' % cp
                blocks.append('%s\n%s' % (header, '\n'.join(body_parts)))
            record.checkpoint_findings = '\n\n'.join(blocks) if blocks else False
            record.has_checkpoint_findings = bool(blocks)
            record.checkpoint_issue_count = issue_count

    @staticmethod
    def _append_text_field(existing, new_text):
        """Append non-empty text without duplicating the same trailing block."""
        new_text = (new_text or '').strip()
        if not new_text:
            return existing
        existing = (existing or '').strip()
        if not existing:
            return new_text
        if new_text in existing:
            return existing
        return '%s\n\n%s' % (existing, new_text)

    @api.depends('incident_ids')
    def _compute_incident_count(self):
        """Count incidents during tour."""
        for record in self:
            record.incident_count = len(record.incident_ids)

    @api.depends('task_ids', 'task_ids.state')
    def _compute_pending_tasks(self):
        """Compute pending tasks that are not completed."""
        for record in self:
            pending_tasks = record.task_ids.filtered(
                lambda t: t.state not in ['completed', 'cancelled']
            )
            record.pending_task_ids = pending_tasks
            record.pending_task_count = len(pending_tasks)

    @api.depends('pending_task_count', 'status')
    def _compute_can_complete(self):
        """Determine if tour can be completed based on task status."""
        for record in self:
            # Tour can be completed if there are no pending tasks
            # or if tour is already completed/cancelled
            record.can_complete = (
                record.pending_task_count == 0 or 
                record.status in ['completed', 'incomplete', 'cancelled']
            )

    def action_complete(
        self, partial=False, reason=None, observations=None, issues_found=None
    ):
        """Complete the tour.
        
        Args:
            partial (bool): If True, marks as partial completion
            reason (str): Reason for partial completion
            observations (str): Optional tour-level summary notes (mobile/backend)
            issues_found (str): Optional tour-level issues / follow-up text
        """
        self.ensure_one()
        
        if self.status != 'in_progress':
            raise ValidationError(_('Tour is not in progress!'))
        
        # Check if all required checkpoints have been completed
        if not partial and self.expected_checkpoints > 0:
            if self.scanned_checkpoints < self.expected_checkpoints:
                missing_count = self.expected_checkpoints - self.scanned_checkpoints
                raise ValidationError(
                    _('Cannot complete tour. %d checkpoint(s) have not been scanned yet.\n\n'
                      'Completed: %d/%d checkpoints (%.1f%%)\n\n'
                      'Please complete all checkpoints or mark the tour as partially complete.') % (
                          missing_count,
                          self.scanned_checkpoints,
                          self.expected_checkpoints,
                          self.completion_percentage
                      )
                )
        
        # Check if there are pending tasks that must be completed first
        if not partial and self.pending_task_count > 0:
            pending_task_names = ', '.join(self.pending_task_ids.mapped('name'))
            raise ValidationError(
                _('Cannot complete tour. The following tasks must be completed first:\n%s\n\n'
                  'Please complete all tasks or mark the tour as partially complete.') % pending_task_names
            )
        
        values = {
            'status': 'completed' if not partial else 'incomplete',
            'end_time': fields.Datetime.now()
        }
        
        if partial:
            values['is_partial_completion'] = True
            values['partial_completion_reason'] = reason or 'No reason provided'

        if observations:
            values['observations'] = self._append_text_field(
                self.observations, observations
            )
        if issues_found:
            values['issues_found'] = self._append_text_field(
                self.issues_found, issues_found
            )
        
        self.write(values)

    def action_cancel(self):
        """Cancel the tour."""
        self.write({'status': 'cancelled'})

    def action_review(self):
        """Mark tour as reviewed."""
        self.write({
            'reviewed': True,
            'reviewed_by': self.env.user.id
        })

    def add_gps_point(self, latitude, longitude):
        """
        Add GPS coordinate to tour track.
        
        Args:
            latitude (float): GPS latitude
            longitude (float): GPS longitude
        """
        self.ensure_one()
        
        import json
        
        # Get existing track or create new
        if self.gps_track:
            track = json.loads(self.gps_track)
        else:
            track = []
        
        # Add new point with timestamp
        track.append({
            'lat': latitude,
            'lng': longitude,
            'timestamp': fields.Datetime.now().isoformat()
        })
        
        self.gps_track = json.dumps(track)
        
        # Calculate distance if we have previous points
        if len(track) > 1:
            self._calculate_distance()

    def _calculate_distance(self):
        """Calculate total distance traveled using GPS track."""
        import json
        
        if not self.gps_track:
            return
        
        track = json.loads(self.gps_track)
        if len(track) < 2:
            return
        
        # Use geo_utils to calculate path distance (returns meters)
        distance_meters = geo_utils.calculate_path_distance(track)
        
        # Store as kilometers
        self.distance_traveled = distance_meters / 1000
    
    # ====================================================
    # SCHEDULED ACTIONS (CRON JOBS)
    # ====================================================
    
    @api.model
    def check_overdue_tours(self):
        """Check for tours that are overdue and send alerts.
        
        Called by scheduled action every hour.
        Alerts supervisors about tours not completed on time.
        """
        from datetime import datetime, timedelta
        
        now = fields.Datetime.now()
        
        # Find tours that are overdue (should have been completed)
        overdue_tours = self.search([
            ('status', '=', 'in_progress'),
            ('scheduled_end_time', '<', now),
            ('scheduled_end_time', '>', now - timedelta(hours=24))  # Within last 24 hours
        ])
        
        if overdue_tours:
            _logger.warning('Found %d overdue tours', len(overdue_tours))
        
        for tour in overdue_tours:
            try:
                minutes_overdue = int((now - tour.scheduled_end_time).total_seconds() / 60)
                
                # Planned activity intentionally disabled.
                
                # Send notification to guard
                tour.message_post(
                    body=Markup(
                        '<p><strong>Tour Overdue Notice</strong></p>'
                        '<p>Your tour was scheduled to complete at %s (%d minutes ago).</p>'
                        '<p>Please complete the tour or report any issues.</p>'
                    ) % (tour.scheduled_end_time, minutes_overdue),
                    partner_ids=tour.guard_id.user_id.partner_id.ids if tour.guard_id.user_id else []
                )
                
                _logger.info('Created alert for overdue tour %s (ID: %d)', tour.id, tour.id)
                
            except Exception as e:
                _logger.error('Error processing overdue tour %s: %s', tour.id, str(e))
        
        return True


class IncidentReport(models.Model):
    """Add tour_log_id to incident report."""

    _inherit = 'incident.report'

    tour_log_id = fields.Many2one(
        'tour.log',
        string='Tour Log',
        tracking=True
    )

