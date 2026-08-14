# -*- coding: utf-8 -*-
"""Checkpoint Scan Model - Scan Verification Tracking."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from psycopg2 import IntegrityError
import logging
import base64
from datetime import timedelta

from ..common.video_optimizer import VideoOptimizer
from ..common.image_optimizer import ImageOptimizer
from ..common.upload_validation import (
    MAX_FILES_PER_REQUEST,
    UploadValidationError,
    validate_json_media_payload,
)

_logger = logging.getLogger(__name__)


class CheckpointScan(models.Model):
    """Checkpoint Scan Verification."""

    _name = 'checkpoint.scan'
    _description = 'Checkpoint Scan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scan_time desc'
    
    # SQL constraints and indexes for performance
    _sql_constraints = [
        ('unique_scan_time_checkpoint_guard',
         'UNIQUE(checkpoint_id, guard_id, scan_time)',
         'A scan for this checkpoint by this guard at this time already exists!')
    ]

    # Basic Information
    checkpoint_id = fields.Many2one(
        'checkpoint',
        string='Checkpoint',
        required=True,
        tracking=True,
        index=True,
        ondelete='cascade'
    )
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        tracking=True,
        index=True,
        ondelete='cascade'
    )
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        related='checkpoint_id.site_id',
        store=True
    )
    
    # Tour Context
    tour_log_id = fields.Many2one(
        'tour.log',
        string='Tour Log',
        tracking=True,
        index=True,
        ondelete='cascade'
    )
    shift_id = fields.Many2one(
        'guard.shift',
        string='Shift',
        tracking=True,
        ondelete='cascade'
    )
    
    # Scan Details
    scan_time = fields.Datetime(
        string='Scan Time',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True
    )
    scan_type = fields.Selection([
        ('nfc', 'NFC'),
        ('qr', 'QR Code'),
        ('gps', 'GPS/Virtual'),
        ('manual', 'Manual'),
        ('walkaround', 'General Walkaround'),
        ('virtual', 'Virtual (GPS)'),
        ('both', 'NFC + QR'),
    ], string='Scan Type', required=True)
    
    scan_data = fields.Char(
        string='Scan Data',
        help='NFC tag ID or QR code data'
    )
    
    # Location
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7)
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7)
    )
    gps_accuracy = fields.Float(
        string='GPS Accuracy (meters)',
        help='GPS accuracy at time of scan'
    )
    
    # Verification
    status = fields.Selection([
        ('verified', 'Verified'),
        ('failed', 'Failed'),
        ('manual_override', 'Manual Override')
    ], string='Status', default='verified', required=True, tracking=True)
    
    verification_method = fields.Selection([
        ('auto', 'Automatic'),
        ('manual', 'Manual'),
        ('supervisor', 'Supervisor Override')
    ], string='Verification Method', default='auto')
    
    failure_reason = fields.Char(
        string='Failure Reason',
        help='Reason if scan verification failed'
    )
    
    # Distance Validation (for GPS scans)
    distance_from_checkpoint = fields.Float(
        string='Distance from Checkpoint (m)',
        digits=(10, 2),
        help='Distance from checkpoint at time of scan'
    )
    within_tolerance = fields.Boolean(
        string='Within Tolerance',
        default=True
    )
    
    # Media
    photo_required = fields.Boolean(
        string='Photo Required',
        related='checkpoint_id.requires_photo'
    )
    photo = fields.Binary(
        string='Checkpoint Photo',
        attachment=True
    )
    photo_ids = fields.Many2many(
        'ir.attachment',
        'checkpoint_scan_photo_rel',
        'scan_id',
        'attachment_id',
        string='Photos'
    )
    video_ids = fields.Many2many(
        'ir.attachment',
        'checkpoint_scan_video_rel',
        'scan_id',
        'attachment_id',
        string='Videos',
        help='Optional video evidence for this scan (never required by checkpoint rules).',
    )
    
    # Notes
    note_required = fields.Boolean(
        string='Note Required',
        related='checkpoint_id.requires_note'
    )
    notes = fields.Text(
        string='Scan Notes'
    )
    
    # Observations
    observations = fields.Text(
        string='Observations',
        help='Guard observations at checkpoint'
    )
    issues_found = fields.Boolean(
        string='Issues Found',
        default=False
    )
    issue_description = fields.Text(
        string='Issue Description'
    )
    has_findings = fields.Boolean(
        string='Has Findings',
        compute='_compute_findings_display',
        help='True when this scan has notes, issues, or media.',
    )
    findings_preview = fields.Char(
        string='Findings Preview',
        compute='_compute_findings_display',
    )
    media_summary = fields.Char(
        string='Media Summary',
        compute='_compute_findings_display',
    )
    photo_count = fields.Integer(
        string='Photo Count',
        compute='_compute_findings_display',
    )
    video_count = fields.Integer(
        string='Video Count',
        compute='_compute_findings_display',
    )

    @api.depends(
        'observations',
        'notes',
        'issues_found',
        'issue_description',
        'photo_ids',
        'video_ids',
        'photo',
    )
    def _compute_findings_display(self):
        """Lightweight display helpers for tour log Observations kanban."""
        for scan in self:
            photo_count = len(scan.photo_ids)
            if scan.photo:
                photo_count = max(photo_count, 1)
            video_count = len(scan.video_ids)
            scan.photo_count = photo_count
            scan.video_count = video_count
            scan.has_findings = bool(
                (scan.observations or '').strip()
                or ((scan.notes or '').strip()
                    and (scan.notes or '').strip() != (scan.observations or '').strip())
                or scan.issues_found
                or photo_count
                or video_count
            )
            preview = (scan.observations or '').strip()
            if not preview:
                preview = (scan.notes or '').strip()
            if preview and len(preview) > 160:
                preview = preview[:157] + '...'
            if scan.issues_found and not preview:
                preview = (scan.issue_description or '').strip() or _('Issue flagged')
            scan.findings_preview = preview or False
            bits = []
            if photo_count:
                bits.append(_('%d photo(s)') % photo_count)
            if video_count:
                bits.append(_('%d video(s)') % video_count)
            scan.media_summary = ', '.join(bits) if bits else False
    
    # Device Information
    device_id = fields.Char(
        string='Device ID'
    )
    app_version = fields.Char(
        string='App Version'
    )
    
    # Offline Sync
    offline_scan = fields.Boolean(
        string='Scanned Offline',
        default=False,
        help='Scan was performed offline and synced later'
    )
    sync_time = fields.Datetime(
        string='Sync Time',
        help='Time when offline scan was synced'
    )
    
    # Validation
    validated_by = fields.Many2one(
        'res.users',
        string='Validated By'
    )
    validation_notes = fields.Text(
        string='Validation Notes'
    )
    
    def init(self):
        """Create composite indexes for performance optimization."""
        # Index for statistics queries - checkpoint scans by status
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS checkpoint_scan_checkpoint_status_idx 
            ON checkpoint_scan(checkpoint_id, status, scan_time DESC)
        """)
        
        # Index for tour log statistics
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS checkpoint_scan_tour_status_idx 
            ON checkpoint_scan(tour_log_id, status) 
            WHERE tour_log_id IS NOT NULL
        """)
        
        # Index for duplicate scan detection
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS checkpoint_scan_duplicate_check_idx 
            ON checkpoint_scan(checkpoint_id, guard_id, scan_time DESC)
        """)
        
        _logger.info('Checkpoint scan indexes created successfully')

    @api.model_create_multi
    def create(self, vals_list):
        """Validate and process checkpoint scan."""
        for vals in vals_list:
            checkpoint = self.env['checkpoint'].browse(vals['checkpoint_id'])
            guard = self.env['guard.profile'].browse(vals['guard_id'])
            
            _logger.info('[Checkpoint Scan] Creating scan for checkpoint: %s (ID: %s), Guard: %s, Tour Log ID: %s',
                        checkpoint.name, checkpoint.id, guard.name, vals.get('tour_log_id'))

            # Defense in depth: never attach a scan to another guard's tour
            if vals.get('tour_log_id') and vals.get('guard_id'):
                tour_log = self.env['tour.log'].browse(vals['tour_log_id'])
                if tour_log.exists() and tour_log.guard_id.id != vals['guard_id']:
                    raise ValidationError(_(
                        'Cannot attach checkpoint scan to another guard\'s patrol.'
                    ))
            
            # Calculate distance if GPS coordinates provided
            if vals.get('latitude') and vals.get('longitude'):
                if checkpoint.scan_type == 'virtual':
                    # Get tolerance from tour_log if available
                    tolerance = None
                    if vals.get('tour_log_id'):
                        tour_log = self.env['tour.log'].browse(vals['tour_log_id'])
                        if tour_log.exists() and tour_log.gps_tolerance:
                            tolerance = tour_log.gps_tolerance
                    
                    # Calculate distance and check if within tolerance
                    if checkpoint.latitude and checkpoint.longitude:
                        distance_meters = self._calculate_distance(
                            checkpoint.latitude,
                            checkpoint.longitude,
                            vals['latitude'],
                            vals['longitude']
                        )
                        vals['distance_from_checkpoint'] = distance_meters
                        
                        # Use tour tolerance if available, otherwise checkpoint tolerance
                        if tolerance is None:
                            tolerance = checkpoint.gps_tolerance
                        
                        vals['within_tolerance'] = distance_meters <= tolerance
                    else:
                        vals['within_tolerance'] = False
            
            # Verify scan data
            # For NFC/QR checkpoints, scan_data is required
            scan_data = vals.get('scan_data')
            scan_type = str(checkpoint.scan_type).lower() if checkpoint.scan_type else ''
            
            if scan_type in ['nfc', 'qr', 'both']:
                if not scan_data:
                    _logger.error('[Checkpoint Scan] Missing scan_data for %s checkpoint %s', 
                                scan_type, checkpoint.name)
                    vals['status'] = 'failed'
                    vals['failure_reason'] = 'No scan data provided'
                else:
                    try:
                        # Ensure scan_data is a string
                        if not isinstance(scan_data, str):
                            scan_data = str(scan_data)
                        scan_data = scan_data.strip()
                        
                        if not scan_data:
                            _logger.error('[Checkpoint Scan] Empty scan_data after conversion for checkpoint %s', checkpoint.name)
                            vals['status'] = 'failed'
                            vals['failure_reason'] = 'Empty scan data provided'
                        else:
                            _logger.info('[Checkpoint Scan] Verifying scan data: %s for checkpoint %s (Type: %s, QR: %s, NFC: %s)',
                                        scan_data, checkpoint.name, scan_type,
                                        checkpoint.qr_code or 'Not set', checkpoint.nfc_tag_id or 'Not set')
                            
                            result = checkpoint.verify_scan(
                                scan_data,
                                vals['guard_id'],
                                vals.get('latitude'),
                                vals.get('longitude'),
                                vals.get('tour_log_id')  # Pass tour_log_id to allow rescanning in new tours
                            )
                            
                            if not result['success']:
                                _logger.warning('[Checkpoint Scan] Verification FAILED: %s', result['message'])
                                vals['status'] = 'failed'
                                vals['failure_reason'] = result['message']
                            else:
                                _logger.info('[Checkpoint Scan] Verification SUCCESS for checkpoint %s', checkpoint.name)
                    except Exception as e:
                        _logger.error('[Checkpoint Scan] Error during verification: %s', str(e), exc_info=True)
                        vals['status'] = 'failed'
                        vals['failure_reason'] = f'Verification error: {str(e)}'
            elif scan_type == 'virtual':
                # For virtual checkpoints, scan_data is optional but can be logged
                if scan_data:
                    _logger.info('[Checkpoint Scan] Scan data provided for virtual checkpoint: %s', scan_data)
            elif scan_type == 'walkaround':
                # No hardware/GPS validation — presence marked manually by the guard
                vals.setdefault('scan_data', scan_data or 'walkaround')
                vals['verification_method'] = 'manual'
                vals['status'] = vals.get('status') or 'verified'
                _logger.info(
                    '[Checkpoint Scan] Walkaround checkpoint %s marked without validation',
                    checkpoint.name,
                )
            else:
                _logger.warning('[Checkpoint Scan] Unknown scan_type "%s" for checkpoint %s', scan_type, checkpoint.name)
        
        scans = super().create(vals_list)
        
        # Log the created scans with detailed info
        for scan in scans:
            _logger.info('[Checkpoint Scan] ===== SCAN CREATED =====')
            _logger.info('[Checkpoint Scan] Scan ID: %s', scan.id)
            _logger.info('[Checkpoint Scan] Status: %s', scan.status)
            _logger.info('[Checkpoint Scan] Checkpoint: %s (ID: %s)', scan.checkpoint_id.name, scan.checkpoint_id.id)
            _logger.info('[Checkpoint Scan] Guard: %s (ID: %s)', scan.guard_id.name, scan.guard_id.id)
            _logger.info('[Checkpoint Scan] Tour Log ID: %s', scan.tour_log_id.id if scan.tour_log_id else 'None')
            _logger.info('[Checkpoint Scan] Scan Data: %s', scan.scan_data)
            _logger.info('[Checkpoint Scan] Will count toward progress: %s', 'YES' if scan.status == 'verified' and scan.tour_log_id else 'NO')
            if scan.status == 'failed':
                _logger.warning('[Checkpoint Scan] FAILURE REASON: %s', scan.failure_reason)
        
        # Update checkpoint and tour_log statistics using optimized SQL
        # This avoids lock contention from computed field recomputation
        _logger.info('[Checkpoint Scan] Calling _update_statistics_optimized() for %d scan(s)', len(scans))
        scans._update_statistics_optimized()
        
        return scans

    def write(self, vals):
        """Override write to update statistics when status changes."""
        # Track which scans need statistics update after write
        scans_to_update = self.env['checkpoint.scan']
        
        # Track old tour_log_ids that need updating (for scans moving between tours)
        old_tour_log_ids_to_update = set()
        
        # Get new values that will be applied
        new_status = vals.get('status')
        new_tour_log_id = vals.get('tour_log_id')
        if new_tour_log_id:
            tour_log = self.env['tour.log'].browse(new_tour_log_id)
            for record in self:
                guard_id = vals.get('guard_id') or record.guard_id.id
                if tour_log.exists() and tour_log.guard_id.id != guard_id:
                    raise ValidationError(_(
                        'Cannot attach checkpoint scan to another guard\'s patrol.'
                    ))
        
        for record in self:
            old_status = record.status
            old_tour_log_id = record.tour_log_id.id if record.tour_log_id else False
            
            # Determine the effective status after write
            effective_status = new_status if new_status is not None else old_status
            effective_tour_log_id = new_tour_log_id if new_tour_log_id is not None else old_tour_log_id
            
            # Check if status is changing to/from 'verified'
            status_changed = new_status is not None and old_status != new_status
            status_affects_count = (old_status == 'verified' or effective_status == 'verified')
            
            # Check if tour_log_id is being set/changed
            tour_log_changed = new_tour_log_id is not None and old_tour_log_id != new_tour_log_id
            
            # If tour_log_id is changing and the scan was verified, we need to update the old tour log
            if tour_log_changed and old_status == 'verified' and old_tour_log_id:
                old_tour_log_ids_to_update.add(old_tour_log_id)
                _logger.info('[Checkpoint Scan] Scan ID %s moving from Tour Log %s (was verified), will update old tour log',
                           record.id, old_tour_log_id)
            
            # Update statistics if:
            # 1. Status changed to/from 'verified', OR
            # 2. Tour log changed and the scan is/will be verified
            if (status_changed and status_affects_count) or \
               (tour_log_changed and effective_status == 'verified'):
                scans_to_update |= record
                if status_changed:
                    _logger.info('[Checkpoint Scan] Status change detected: Scan ID %s from %s to %s',
                               record.id, old_status, effective_status)
                if tour_log_changed:
                    _logger.info('[Checkpoint Scan] Tour log association change detected: Scan ID %s, Tour Log %s -> %s',
                               record.id, old_tour_log_id, effective_tour_log_id)
        
        # Perform the write operation
        result = super().write(vals)
        
        # Update statistics for affected scans (this updates new tour logs)
        if scans_to_update:
            _logger.info('[Checkpoint Scan] Updating statistics for %d scan(s) after status/tour_log change', len(scans_to_update))
            scans_to_update._update_statistics_optimized()
        
        # Update old tour logs AFTER write (scans have moved, so old tour logs need recalculation)
        if old_tour_log_ids_to_update:
            _logger.info('[Checkpoint Scan] Updating statistics for %d old tour log(s) after scan move', 
                        len(old_tour_log_ids_to_update))
            # Get all verified scans for the old tour logs (excluding the scans we just moved)
            old_scans = self.env['checkpoint.scan'].search([
                ('tour_log_id', 'in', list(old_tour_log_ids_to_update)),
                ('status', '=', 'verified')
            ])
            if old_scans:
                old_scans._update_statistics_optimized()
        
        return result

    @api.constrains('photo', 'photo_ids', 'status')
    def _check_photo_requirement(self):
        """Validate photo requirement."""
        for record in self:
            if record.photo_required and record.status == 'verified':
                if not (record.photo or record.photo_ids):
                    raise ValidationError(_(
                        'Photo is required for this checkpoint!'
                    ))

    @api.constrains('notes', 'status')
    def _check_note_requirement(self):
        """Validate note requirement."""
        for record in self:
            if record.note_required and record.status == 'verified':
                if not record.notes:
                    raise ValidationError(_(
                        'Note is required for this checkpoint!'
                    ))

    def action_manual_verify(self):
        """Manually verify failed scan."""
        self.write({
            'status': 'manual_override',
            'verification_method': 'supervisor',
            'validated_by': self.env.user.id
        })

    def _update_statistics_optimized(self):
        """
        Update checkpoint and tour_log statistics using optimized SQL.
        Uses CTEs and batch updates to minimize database queries and lock contention.
        """
        if not self:
            _logger.info('[Statistics Update] No scans to process')
            return
        
        _logger.info('[Statistics Update] ===== STARTING STATISTICS UPDATE =====')
        _logger.info('[Statistics Update] Processing %d scan(s)', len(self))
        
        # Group scans by checkpoint and tour_log
        checkpoint_ids = set()
        tour_log_ids = set()
        
        for scan in self:
            if scan.status == 'verified':
                checkpoint_ids.add(scan.checkpoint_id.id)
                if scan.tour_log_id:
                    tour_log_ids.add(scan.tour_log_id.id)
            else:
                _logger.info('[Statistics Update] Skipping scan ID %s (status: %s) for checkpoint %s',
                           scan.id, scan.status, scan.checkpoint_id.name)
        
        if not checkpoint_ids and not tour_log_ids:
            _logger.info('[Statistics Update] No verified scans to update statistics for')
            return
        
        _logger.info('[Statistics Update] Updating statistics for %d checkpoint(s) and %d tour log(s)',
                    len(checkpoint_ids), len(tour_log_ids))
        
        try:
            # Update checkpoint statistics with a single batch query using CTE
            if checkpoint_ids:
                self.env.cr.execute("""
                    WITH scan_stats AS (
                        SELECT 
                            checkpoint_id,
                            MAX(scan_time) as last_scan,
                            COUNT(*) as total_count,
                            MAX(scan_time) - MIN(scan_time) as time_range
                        FROM checkpoint_scan
                        WHERE checkpoint_id = ANY(%s) AND status = 'verified'
                        GROUP BY checkpoint_id
                    )
                    UPDATE checkpoint c
                    SET 
                        last_scan_time = s.last_scan,
                        total_scans = s.total_count,
                        scan_frequency = CASE
                            WHEN s.time_range IS NULL THEN 0
                            WHEN EXTRACT(EPOCH FROM s.time_range) / 86400.0 < 1 THEN s.total_count
                            ELSE s.total_count / (EXTRACT(EPOCH FROM s.time_range) / 86400.0)
                        END,
                        write_date = NOW() AT TIME ZONE 'UTC',
                        write_uid = %s
                    FROM scan_stats s
                    WHERE c.id = s.checkpoint_id
                """, (list(checkpoint_ids), self.env.uid))
            
            # Update tour_log statistics with a single batch query using CTE
            if tour_log_ids:
                _logger.info('[Statistics Update] Updating tour logs: %s', list(tour_log_ids))
                
                # First, get current state BEFORE update
                for tour_log_id in tour_log_ids:
                    tour_log = self.env['tour.log'].browse(tour_log_id)
                    _logger.info('[Statistics Update] BEFORE UPDATE - Tour Log %s: scanned=%d, expected=%d, percentage=%.1f%%',
                               tour_log.id, tour_log.scanned_checkpoints, tour_log.expected_checkpoints,
                               tour_log.completion_percentage)
                
                self.env.cr.execute("""
                    WITH tour_stats AS (
                        SELECT 
                            tour_log_id,
                            COUNT(DISTINCT checkpoint_id) as scanned_count
                        FROM checkpoint_scan
                        WHERE tour_log_id = ANY(%s) AND status = 'verified'
                        GROUP BY tour_log_id
                    )
                    UPDATE tour_log t
                    SET
                        scanned_checkpoints = s.scanned_count,
                        completion_percentage = CASE
                            WHEN t.expected_checkpoints > 0
                            THEN (s.scanned_count * 100.0 / t.expected_checkpoints)
                            ELSE 0
                        END,
                        write_date = NOW() AT TIME ZONE 'UTC',
                        write_uid = %s
                    FROM tour_stats s
                    WHERE t.id = s.tour_log_id
                    RETURNING t.id, t.scanned_checkpoints, t.expected_checkpoints, t.completion_percentage
                """, (list(tour_log_ids), self.env.uid))
                
                # Log the SQL results
                updated_rows = self.env.cr.fetchall()
                _logger.info('[Statistics Update] SQL UPDATE returned %d row(s)', len(updated_rows))
                for row in updated_rows:
                    _logger.info('[Statistics Update] SQL RESULT - Tour Log %s: scanned=%s, expected=%s, percentage=%.1f%%',
                               row[0], row[1], row[2], row[3])
            
            # Selective cache invalidation - only invalidate specific records
            # This must be done BEFORE logging to ensure fresh values are read
            if checkpoint_ids:
                self.env['checkpoint'].browse(list(checkpoint_ids)).invalidate_recordset(
                    ['last_scan_time', 'total_scans', 'scan_frequency']
                )
            if tour_log_ids:
                # Invalidate all cached fields including the scan_ids relationship
                tour_logs = self.env['tour.log'].browse(list(tour_log_ids))
                tour_logs.invalidate_recordset(
                    ['scanned_checkpoints', 'completion_percentage', 'scan_ids']
                )
                # Force invalidate the scan_ids relationship specifically
                for tour_log in tour_logs:
                    tour_log.invalidate_recordset(['scan_ids'])
                # Also invalidate the entire recordset to ensure the web controller gets fresh data
                tour_logs.invalidate_recordset()
            
            # Log successful updates AFTER cache invalidation
            if checkpoint_ids:
                _logger.info('[Statistics Update] Updated checkpoint statistics for checkpoint IDs: %s', list(checkpoint_ids))
            if tour_log_ids:
                _logger.info('[Statistics Update] Cache invalidated for tour log IDs: %s', list(tour_log_ids))
                # Log the updated values - now with fresh data from database
                for tour_log_id in tour_log_ids:
                    tour_log = self.env['tour.log'].browse(tour_log_id)
                    _logger.info('[Statistics Update] AFTER CACHE INVALIDATION - Tour Log %s (%s): %d/%d checkpoints (%.1f%%)',
                               tour_log.id, tour_log.name, tour_log.scanned_checkpoints,
                               tour_log.expected_checkpoints, tour_log.completion_percentage)
            
            _logger.info('[Statistics Update] ===== STATISTICS UPDATE COMPLETE =====')
            
            # Force flush to ensure statistics are persisted immediately
            # This is critical for real-time progress updates in mobile interface
            # NOTE: Do NOT call commit() here - Odoo's HTTP layer handles transaction management
            self.env.flush_all()  # Flush any pending ORM writes
            _logger.info('[Statistics Update] Database changes flushed (commit will be handled by Odoo framework)')
        
        except Exception as e:
            # Log error but don't block the scan - statistics can be updated later
            _logger.warning('Statistics update failed (non-critical): %s', str(e))

    @staticmethod
    def _calculate_distance(lat1, lon1, lat2, lon2):
        """
        Calculate distance between two GPS coordinates.
        
        Args:
            lat1, lon1: First coordinate
            lat2, lon2: Second coordinate
            
        Returns:
            float: Distance in meters
        """
        import math
        
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

    @api.model
    def _is_video_payload_dict(self, payload):
        """Detect JSON attachment dict as video (same rules as mobile incident API)."""
        if not payload or not isinstance(payload, dict):
            return False
        name = (payload.get('name') or '').lower()
        mimetype = (payload.get('mimetype') or payload.get('content_type') or '').lower()
        if mimetype.startswith('video/'):
            return True
        return name.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.3gp'))

    @api.model
    def _video_attachment_ids_from_payloads(self, videos_payloads):
        """Create ir.attachment rows from mobile JSON video payloads; returns attachment ids."""
        if not videos_payloads:
            return []
        ids = []
        Attachment = self.env['ir.attachment'].sudo()
        for payload in list(videos_payloads)[:MAX_FILES_PER_REQUEST]:
            if not payload or not isinstance(payload, dict):
                continue
            try:
                validated = validate_json_media_payload(
                    payload, allow_video=True, allow_image=False
                )
            except UploadValidationError as exc:
                _logger.warning('[Checkpoint Scan] Rejected video: %s', exc)
                continue
            if not validated['is_video']:
                continue
            payload_name = validated['filename'] or 'checkpoint_video.mp4'
            mimetype = validated['mimetype'] or 'video/mp4'
            optimized, compressed = VideoOptimizer.optimize_video(
                validated['data'],
                filename=payload_name,
            )
            if compressed:
                mimetype = 'video/mp4'
            b64_datas = optimized
            if isinstance(b64_datas, bytes):
                b64_datas = b64_datas.decode()
            att = Attachment.create({
                'name': payload_name,
                'datas': b64_datas,
                'res_model': 'checkpoint.scan',
                'mimetype': mimetype,
            })
            ids.append(att.id)
        return ids

    @api.model
    def _normalize_upload_b64(self, payload_data):
        """Strip data-URL prefix and whitespace from mobile base64 payloads."""
        if not payload_data:
            return None
        if isinstance(payload_data, bytes):
            try:
                payload_data = payload_data.decode('ascii')
            except Exception:
                payload_data = base64.b64encode(payload_data).decode('ascii')
        datas = str(payload_data).strip()
        if ',' in datas and datas.startswith('data:'):
            datas = datas.split(',', 1)[1]
        datas = ''.join(datas.split())
        if not datas:
            return None
        try:
            base64.b64decode(datas, validate=True)
        except Exception as exc:
            raise ValidationError(_('Invalid photo data: %s') % exc) from exc
        return datas

    @api.model
    def _photo_attachment_ids_from_payloads(self, photo_payloads):
        """Create image (non-video) attachments from mobile/JSON payloads; return new attachment ids."""
        if not photo_payloads:
            return []
        ids = []
        Attachment = self.env['ir.attachment'].sudo()
        for payload in list(photo_payloads)[:MAX_FILES_PER_REQUEST]:
            if not payload or not isinstance(payload, dict):
                continue
            if self._is_video_payload_dict(payload):
                continue
            try:
                validated = validate_json_media_payload(
                    payload, allow_video=False, allow_image=True
                )
            except UploadValidationError as exc:
                _logger.warning('[Checkpoint Scan] Rejected photo: %s', exc)
                continue
            payload_name = validated['filename'] or 'checkpoint_photo.jpg'
            mimetype = validated['mimetype'] or 'image/jpeg'
            datas = base64.b64encode(validated['data']).decode('ascii')
            try:
                optimized = ImageOptimizer.optimize_image(datas)
                if optimized:
                    if isinstance(optimized, bytes):
                        optimized = optimized.decode('ascii')
                    datas = optimized
                    mimetype = 'image/jpeg'
                    if not payload_name.lower().endswith(('.jpg', '.jpeg')):
                        base = payload_name.rsplit('.', 1)[0] if '.' in payload_name else payload_name
                        payload_name = f'{base}.jpg'
            except Exception as exc:
                _logger.warning(
                    '[Checkpoint Scan] Photo optimize skipped for %s: %s',
                    payload_name, exc,
                )
            try:
                att = Attachment.create({
                    'name': payload_name,
                    'datas': datas,
                    'res_model': 'checkpoint.scan',
                    'mimetype': mimetype,
                })
                ids.append(att.id)
                _logger.info(
                    '[Checkpoint Scan] Saved photo attachment %s (%s, %s bytes b64)',
                    att.id, payload_name, len(datas),
                )
            except Exception as exc:
                _logger.exception(
                    '[Checkpoint Scan] Failed to create attachment for %s', payload_name
                )
                raise ValidationError(
                    _('Could not save photo "%s": %s') % (payload_name, exc)
                ) from exc
        return ids

    @api.model
    def scan_checkpoint(self, checkpoint_id, guard_id, scan_data,
                        latitude=None, longitude=None, tour_log_id=None,
                        photo=None, notes=None, videos=None):
        """
        API method for mobile app to scan checkpoint.
        
        Args:
            checkpoint_id (int): Checkpoint ID
            guard_id (int): Guard ID
            scan_data (str): NFC/QR scan data
            latitude (float): GPS latitude
            longitude (float): GPS longitude
            tour_log_id (int): Tour log ID if part of tour
            photo (bytes): Photo data
            notes (str): Scan notes
            videos (list): Optional list of dicts with name, data (base64), mimetype

        Returns:
            dict: Scan result
        """
        checkpoint = self.env['checkpoint'].browse(checkpoint_id)

        if not checkpoint.exists():
            return {
                'success': False,
                'error': _('Checkpoint not found'),
                'message': _('The checkpoint you are trying to scan does not exist.')
            }

        # Validate tour_log_id if provided — must exist, be in progress, and
        # belong to the scanning guard (blocks cross-guard tour IDOR).
        if tour_log_id:
            tour_log = self.env['tour.log'].browse(tour_log_id)
            if not tour_log.exists():
                _logger.warning(
                    '[Checkpoint Scan API] Invalid tour_log_id: %s', tour_log_id
                )
                return {
                    'success': False,
                    'error': 'tour_not_found',
                    'message': _('Patrol not found.'),
                }
            if tour_log.guard_id.id != guard_id:
                _logger.warning(
                    '[Checkpoint Scan API] Tour log %s belongs to guard %s, '
                    'not scanning guard %s — rejecting',
                    tour_log_id,
                    tour_log.guard_id.id,
                    guard_id,
                )
                return {
                    'success': False,
                    'error': 'unauthorized_tour',
                    'message': _('This patrol does not belong to you.'),
                }
            if tour_log.status not in ('in_progress',):
                _logger.warning(
                    '[Checkpoint Scan API] Tour log %s is not in progress '
                    '(status: %s)',
                    tour_log_id, tour_log.status,
                )
                return {
                    'success': False,
                    'error': 'tour_not_active',
                    'message': _('No active patrol to record this scan.'),
                }
        
        # Get current shift if available
        shift = self.env['guard.shift'].search([
            ('guard_id', '=', guard_id),
            ('status', '=', 'in_progress')
        ], limit=1)
        
        # Safely convert coordinates to float
        try:
            if latitude is not None and latitude != '':
                latitude = float(latitude)
            else:
                latitude = False
                
            if longitude is not None and longitude != '':
                longitude = float(longitude)
            else:
                longitude = False
        except (ValueError, TypeError):
            _logger.warning('[Checkpoint Scan API] Invalid coordinates provided: lat=%s, lon=%s', latitude, longitude)
            # Should we fail? Or just ignore coordinates? 
            # If virtual checkpoint, we need them.
            if checkpoint.scan_type == 'virtual':
                return {
                    'success': False,
                    'error': 'invalid_coordinates',
                    'message': _('Invalid GPS coordinates provided.')
                }
            latitude = False
            longitude = False

        # Idempotent: already verified on this tour (double NFC tap / duplicate request)
        if tour_log_id:
            existing_tour_scan = self.search([
                ('checkpoint_id', '=', checkpoint_id),
                ('guard_id', '=', guard_id),
                ('tour_log_id', '=', tour_log_id),
                ('status', '=', 'verified'),
            ], limit=1, order='scan_time desc')
            if existing_tour_scan:
                _logger.info(
                    '[Checkpoint Scan API] Checkpoint %s already verified on tour log %s (scan %s)',
                    checkpoint.name, tour_log_id, existing_tour_scan.id,
                )
                return self._scan_success_response(existing_tour_scan, checkpoint, already_scanned=True)

        # Recent duplicate within min_scan_interval (retries / rapid double scan)
        interval_seconds = max(1, checkpoint.min_scan_interval or 60)
        duplicate_domain = [
            ('checkpoint_id', '=', checkpoint_id),
            ('guard_id', '=', guard_id),
            ('status', '=', 'verified'),
            ('scan_time', '>=', fields.Datetime.now() - timedelta(seconds=interval_seconds)),
        ]
        if tour_log_id:
            duplicate_domain.append(('tour_log_id', '=', tour_log_id))

        recent_verified = self.search(duplicate_domain, limit=1, order='scan_time desc')
        if recent_verified:
            _logger.info(
                '[Checkpoint Scan API] Recent verified scan %s for checkpoint %s, skipping duplicate create',
                recent_verified.id, checkpoint.name,
            )
            return self._scan_success_response(recent_verified, checkpoint, already_scanned=True)

        scan_time = self._next_unique_scan_time(checkpoint_id, guard_id)

        # Create scan record
        scan_vals = {
            'checkpoint_id': checkpoint_id,
            'guard_id': guard_id,
            'scan_time': scan_time,
            'scan_type': checkpoint.scan_type,
            'scan_data': scan_data,
            'latitude': latitude,
            'longitude': longitude,
            'tour_log_id': tour_log_id,
            'shift_id': shift.id if shift else False,
            'photo': photo,
            'notes': notes
        }
        video_att_ids = self._video_attachment_ids_from_payloads(videos or [])
        if video_att_ids:
            scan_vals['video_ids'] = [(6, 0, video_att_ids)]

        try:
            with self.env.cr.savepoint():
                scan = self.create(scan_vals)
        except IntegrityError as exc:
            dup_exc = exc
        except Exception as exc:
            if not self._is_duplicate_scan_db_error(exc):
                raise
            dup_exc = exc
        else:
            dup_exc = None

        if dup_exc is not None:
            existing = self._find_duplicate_scan_record(
                checkpoint_id, guard_id, scan_time, tour_log_id,
            )
            if existing:
                _logger.info(
                    '[Checkpoint Scan API] Concurrent duplicate scan resolved using existing record %s',
                    existing.id,
                )
                return self._scan_success_response(existing, checkpoint, already_scanned=True)
            _logger.error(
                '[Checkpoint Scan API] Duplicate scan DB error but no matching record found: %s',
                dup_exc,
            )
            return {
                'success': False,
                'error': 'duplicate_scan',
                'message': _('This scan was already recorded. Please refresh the tour.'),
            }

        # Check if scan was verified or failed
        if scan.status == 'failed':
            _logger.warning(
                '[Checkpoint Scan API] Scan created but FAILED verification: %s',
                scan.failure_reason or 'Unknown reason',
            )
            return {
                'success': False,
                'error': 'verification_failed',
                'scan_id': scan.id,
                'status': scan.status,
                'message': scan.failure_reason or _(
                    'Scan verification failed. Please try again or contact your supervisor.'
                ),
                'checkpoint': checkpoint.name,
            }

        _logger.info(
            '[Checkpoint Scan API] Scan created successfully: ID=%s, Status=%s, Tour Log=%s',
            scan.id, scan.status, tour_log_id or 'None',
        )
        return self._scan_success_response(scan, checkpoint, already_scanned=False)

    def _scan_success_response(self, scan, checkpoint, already_scanned=False):
        """Standard success payload for mobile clients."""
        if scan.tour_log_id and scan.status == 'verified':
            try:
                scan.tour_log_id._compute_checkpoint_progress()
            except Exception as exc:
                _logger.warning(
                    '[Checkpoint Scan API] Could not refresh tour progress for log %s: %s',
                    scan.tour_log_id.id, exc,
                )
        return {
            'success': True,
            'scan_id': scan.id,
            'status': scan.status,
            'message': _(
                'Checkpoint already scanned successfully!'
                if already_scanned else 'Checkpoint scanned successfully!'
            ),
            'checkpoint': checkpoint.name,
            'already_scanned': already_scanned,
        }

    @api.model
    def _next_unique_scan_time(self, checkpoint_id, guard_id):
        """Avoid UNIQUE(checkpoint_id, guard_id, scan_time) collisions (same-second double tap)."""
        scan_time = fields.Datetime.now()
        while self.search_count([
            ('checkpoint_id', '=', checkpoint_id),
            ('guard_id', '=', guard_id),
            ('scan_time', '=', scan_time),
        ]):
            scan_time += timedelta(seconds=1)
        return scan_time

    @api.model
    def _is_duplicate_scan_db_error(self, exc):
        """True when PostgreSQL rejected a duplicate (checkpoint, guard, scan_time)."""
        if isinstance(exc, IntegrityError):
            return True
        message = str(exc).lower()
        return (
            'duplicate key' in message
            or 'unique constraint' in message
            or 'unique_scan_time_checkpoint_guard' in message
        )

    @api.model
    def _find_duplicate_scan_record(self, checkpoint_id, guard_id, scan_time, tour_log_id=None):
        """Locate an existing scan after a unique-constraint race."""
        domain = [
            ('checkpoint_id', '=', checkpoint_id),
            ('guard_id', '=', guard_id),
            ('scan_time', '=', scan_time),
        ]
        existing = self.search(domain, limit=1)
        if existing:
            return existing
        if tour_log_id:
            return self.search([
                ('checkpoint_id', '=', checkpoint_id),
                ('guard_id', '=', guard_id),
                ('tour_log_id', '=', tour_log_id),
                ('status', '=', 'verified'),
            ], limit=1, order='scan_time desc')
        return self.search([
            ('checkpoint_id', '=', checkpoint_id),
            ('guard_id', '=', guard_id),
            ('status', '=', 'verified'),
        ], limit=1, order='scan_time desc')

