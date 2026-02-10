# -*- coding: utf-8 -*-
"""Checkpoint Model - NFC/QR/Virtual Points."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
from ..common.image_optimizer import ImageOptimizer
import logging

_logger = logging.getLogger(__name__)


class Checkpoint(models.Model):
    """Checkpoint for guard verification (NFC, QR, Virtual)."""

    _name = 'checkpoint'
    _description = 'Checkpoint'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'site_id, name'

    # Basic Information
    name = fields.Char(
        string='Checkpoint Name',
        required=True,
        tracking=True,
        index=True
    )
    code = fields.Char(
        string='Checkpoint Code',
        required=True,
        copy=False,
        tracking=True,
        index=True
    )
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    # Location Hierarchy
    building_id = fields.Many2one(
        'site.building',
        string='Building',
        domain="[('site_id', '=', site_id)]",
        tracking=True,
        help='Building where this checkpoint is located'
    )
    floor_id = fields.Many2one(
        'building.floor',
        string='Floor',
        domain="[('building_id', '=', building_id)]",
        tracking=True,
        help='Floor where this checkpoint is located'
    )
    area_id = fields.Many2one(
        'floor.area',
        string='Area/Room',
        domain="[('floor_id', '=', floor_id)]",
        tracking=True,
        help='Specific area or room where this checkpoint is located'
    )

    # Legacy Location (for backward compatibility)
    location_description = fields.Char(
        string='Location Description',
        help='Detailed description of checkpoint location'
    )
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7),
        tracking=True
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7),
        tracking=True
    )
    floor = fields.Char(
        string='Legacy Floor/Level',
        help='Legacy floor field - use Floor field above for new checkpoints'
    )
    zone = fields.Char(
        string='Legacy Zone/Area',
        help='Legacy zone field - use Area/Room field above for new checkpoints'
    )
    
    # Scan Type
    scan_type = fields.Selection([
        ('nfc', 'NFC Tag'),
        ('qr', 'QR Code'),
        ('virtual', 'Virtual (GPS)'),
        ('both', 'NFC + QR')
    ], string='Scan Type', default='nfc', required=True, tracking=True)
    
    # NFC Configuration
    nfc_tag_id = fields.Char(
        string='NFC Tag ID',
        help='Unique NFC tag identifier',
        index=True
    )
    nfc_tag_type = fields.Char(
        string='NFC Tag Type'
    )
    
    # QR Code Configuration
    qr_code = fields.Char(
        string='QR Code',
        help='Unique QR code identifier',
        index=True
    )
    qr_code_image = fields.Binary(
        string='QR Code Image',
        attachment=True,
        compute='_compute_qr_code_image'
    )
    
    # Virtual Checkpoint
    gps_tolerance = fields.Float(
        string='GPS Tolerance (meters)',
        default=50.0,
        help='Acceptable distance from checkpoint for virtual scan'
    )
    
    # Status
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance')
    ], string='Status', default='active', required=True, tracking=True)
    
    # Tours
    tour_ids = fields.Many2many(
        'security.tour',
        'tour_checkpoint_rel',
        'checkpoint_id',
        'tour_id',
        string='Tours'
    )
    
    # Scanning Requirements
    requires_photo = fields.Boolean(
        string='Require Photo',
        default=False
    )
    requires_note = fields.Boolean(
        string='Require Note',
        default=False
    )
    min_scan_interval = fields.Integer(
        string='Minimum Scan Interval (seconds)',
        default=60,
        help='Minimum time between scans to prevent duplicate scans'
    )
    
    # Scan History
    scan_ids = fields.One2many(
        'checkpoint.scan',
        'checkpoint_id',
        string='Scan History'
    )
    
    # Statistics
    # Note: These fields are updated via optimized SQL in checkpoint.scan.create()
    # to avoid lock contention during concurrent scans.
    # The _compute_statistics() method is available for manual recomputation if needed.
    total_scans = fields.Integer(
        string='Total Scans',
        default=0,
        readonly=True,
        help='Total number of verified scans'
    )
    last_scan_time = fields.Datetime(
        string='Last Scan',
        readonly=True,
        help='Time of last verified scan'
    )
    scan_frequency = fields.Float(
        string='Scans per Day',
        default=0.0,
        readonly=True,
        help='Average scans per day'
    )
    
    # Instructions
    instructions = fields.Text(
        string='Checkpoint Instructions',
        help='What guards should check at this point'
    )
    special_notes = fields.Text(
        string='Special Notes'
    )
    
    # Attachments
    photo = fields.Binary(
        string='Checkpoint Photo',
        attachment=True
    )
    
    photo_ids = fields.Many2many(
        'ir.attachment',
        'checkpoint_photo_rel',
        'checkpoint_id',
        'attachment_id',
        string='Location Photos',
        help='Multiple photos showing checkpoint location (automatically optimized)'
    )
    
    photo_count = fields.Integer(
        string='Photo Count',
        compute='_compute_photo_count',
        store=True
    )
    
    # Notes
    notes = fields.Text(
        string='Internal Notes'
    )
    
    _sql_constraints = [
        ('code_unique', 'unique(code)',
         'Checkpoint code must be unique!'),
        ('nfc_unique', 'unique(nfc_tag_id)',
         'NFC tag ID must be unique!'),
        ('qr_unique', 'unique(qr_code)',
         'QR code must be unique!'),
    ]

    @api.depends('qr_code')
    def _compute_qr_code_image(self):
        """Generate QR code image."""
        for record in self:
            if record.qr_code:
                try:
                    import qrcode
                    import base64
                    from io import BytesIO
                    
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(record.qr_code)
                    qr.make(fit=True)
                    
                    img = qr.make_image(fill_color="black", back_color="white")
                    buffer = BytesIO()
                    img.save(buffer, format='PNG')
                    record.qr_code_image = base64.b64encode(buffer.getvalue())
                except ImportError:
                    _logger.warning('qrcode library not installed')
                    record.qr_code_image = False
            else:
                record.qr_code_image = False

    # Note: @api.depends decorator removed to prevent automatic recomputation
    # on every scan. Statistics are updated via optimized SQL in checkpoint.scan.create()
    # This method is kept for manual recomputation if needed.
    def _compute_statistics(self):
        """Compute checkpoint statistics.
        
        This method is available for manual recomputation but is not automatically
        triggered to avoid database lock contention during concurrent scans.
        Use checkpoint.scan.create() which updates statistics via optimized SQL.
        """
        for record in self:
            scans = record.scan_ids.filtered(lambda s: s.status == 'verified')
            vals = {
                'total_scans': len(scans)
            }
            
            if scans:
                vals['last_scan_time'] = max(scans.mapped('scan_time'))
                
                # Calculate scans per day
                first_scan = min(scans.mapped('scan_time'))
                last_scan = vals['last_scan_time']
                days = (last_scan - first_scan).days or 1
                vals['scan_frequency'] = len(scans) / days
            else:
                vals['last_scan_time'] = False
                vals['scan_frequency'] = 0.0
            
            # Use sudo to bypass readonly constraint during recomputation
            record.sudo().write(vals)
    
    @api.depends('photo_ids')
    def _compute_photo_count(self):
        """Compute number of photo attachments."""
        for record in self:
            record.photo_count = len(record.photo_ids)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create checkpoint and optimize photos."""
        records = super().create(vals_list)
        for record in records:
            if record.photo_ids or record.photo:
                record._optimize_photos()
        return records
    
    def write(self, vals):
        """Override write to optimize photos on update."""
        result = super().write(vals)
        if 'photo_ids' in vals or 'photo' in vals:
            self._optimize_photos()
        return result
    
    def _optimize_photos(self):
        """Optimize photo attachments for storage."""
        for record in self:
            # Optimize Many2many photos
            for attachment in record.photo_ids.filtered(
                lambda a: a.mimetype and a.mimetype.startswith('image/')
            ):
                try:
                    if attachment.file_size and attachment.file_size < 300 * 1024:
                        continue
                    
                    original_data = attachment.datas
                    if not original_data:
                        continue
                    
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
                            'Optimized photo %s for checkpoint %s',
                            attachment.name,
                            record.name
                        )
                except Exception as e:
                    _logger.error(
                        'Failed to optimize photo %s: %s',
                        attachment.id,
                        str(e)
                    )
            
            # Optimize Binary field (photo)
            if record.photo:
                try:
                    optimized_data = ImageOptimizer.optimize_image(
                        record.photo,
                        max_dimension=800,
                        target_format='JPEG'
                    )
                    if optimized_data != record.photo:
                        record.photo = optimized_data
                        _logger.info('Optimized checkpoint photo for %s', record.name)
                except Exception as e:
                    _logger.error(
                        'Failed to optimize checkpoint photo: %s',
                        str(e)
                    )
    
    def action_recompute_statistics(self):
        """Manually recompute checkpoint statistics.
        
        This action can be called from the UI or via code to recalculate
        statistics from scan history.
        """
        self._compute_statistics()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Statistics Updated'),
                'message': _('Checkpoint statistics have been recomputed.'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        """Validate GPS coordinates for virtual checkpoints."""
        for record in self:
            if record.scan_type == 'virtual':
                if not (record.latitude and record.longitude):
                    raise ValidationError(_(
                        'Virtual checkpoints require GPS coordinates!'
                    ))
                if not (-90 <= record.latitude <= 90):
                    raise ValidationError(_(
                        'Latitude must be between -90 and 90!'
                    ))
                if not (-180 <= record.longitude <= 180):
                    raise ValidationError(_(
                        'Longitude must be between -180 and 180!'
                    ))

    @api.constrains('scan_type', 'nfc_tag_id', 'qr_code')
    def _check_scan_configuration(self):
        """Validate scan type configuration."""
        for record in self:
            if record.scan_type == 'nfc' and not record.nfc_tag_id:
                raise ValidationError(_(
                    'NFC checkpoints require NFC tag ID!'
                ))
            if record.scan_type == 'qr' and not record.qr_code:
                raise ValidationError(_(
                    'QR checkpoints require QR code!'
                ))
            if record.scan_type == 'both':
                if not (record.nfc_tag_id and record.qr_code):
                    raise ValidationError(_(
                        'Both NFC tag ID and QR code are required!'
                    ))

    @api.model_create_multi
    def create(self, vals_list):
        """Generate checkpoint code and QR code if not provided."""
        import uuid
        for vals in vals_list:
            # Auto-generate checkpoint code if not provided
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('checkpoint.code') or '/'
            
            # Auto-generate QR code if not provided
            if vals.get('scan_type') in ['qr', 'both'] and not vals.get('qr_code'):
                vals['qr_code'] = 'CP-' + str(uuid.uuid4())[:8].upper()
        return super().create(vals_list)

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

    def action_view_scans(self):
        """Open checkpoint scan history."""
        self.ensure_one()
        return {
            'name': _('Scan History - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'checkpoint.scan',
            'view_mode': 'list,form',
            'domain': [('checkpoint_id', '=', self.id)],
            'context': {'default_checkpoint_id': self.id}
        }

    def _normalize_nfc_tag(self, tag_id):
        """
        Normalize NFC tag ID for comparison.
        Handles different formats: serial numbers, text records, case differences, separators.
        
        Returns:
            str: Normalized tag ID
        """
        try:
            if not tag_id:
                return ''
            
            # Convert to string and strip whitespace
            normalized = str(tag_id).strip().lower()
            
            if not normalized:
                return ''
            
            # Normalize all common separators to colons
            for char in ['-', ' ', '_', '.', ',']:
                normalized = normalized.replace(char, ':')
            
            # Remove any duplicate separators
            while '::' in normalized:
                normalized = normalized.replace('::', ':')
            
            # Strip leading/trailing separators
            normalized = normalized.strip(':')
            
            # SECRECY: Some readers might provide UIDs without separators (e.g., '044715...')
            # while others provide separators. If it looks like a hex UID (long enough),
            # we might want to also allow comparison without separators.
            # But for now, we'll keep the colon-separated format as standard.
            
            return normalized
        except Exception as e:
            _logger.error('[Checkpoint Normalize] Error normalizing tag_id %s: %s', tag_id, str(e))
            return str(tag_id).lower() if tag_id else ''
    
    def verify_scan(self, scan_data, guard_id, latitude=None, longitude=None, tour_log_id=None):
        """
        Verify a checkpoint scan.
        
        Args:
            scan_data (str): NFC tag ID or QR code data
            guard_id (int): ID of guard performing scan
            latitude (float): Guard's latitude for virtual checkpoints
            longitude (float): Guard's longitude for virtual checkpoints
            tour_log_id (int): Current tour log ID to allow rescanning in new tours
            
        Returns:
            dict: Verification result
        """
        self.ensure_one()
        
        # Validate scan_data
        if not scan_data:
            _logger.warning('[Checkpoint Verify] No scan data provided for checkpoint %s', self.name)
            return {
                'success': False,
                'message': _('No scan data provided. Please try scanning again.')
            }
        
        # Ensure scan_data is a string
        try:
            scan_data = str(scan_data).strip()
        except Exception as e:
            _logger.error('[Checkpoint Verify] Error converting scan_data to string: %s', str(e))
            return {
                'success': False,
                'message': _('Invalid scan data format. Please ensure the NFC tag is properly encoded and try again.')
            }

        if not scan_data:
            _logger.warning('[Checkpoint Verify] Empty scan data after conversion for checkpoint %s', self.name)
            return {
                'success': False,
                'message': _('No data found on NFC tag. Please ensure the tag contains valid data and try scanning again.')
            }
        
        if self.status != 'active':
            _logger.warning('[Checkpoint Verify] Checkpoint %s is not active', self.name)
            return {
                'success': False,
                'message': _('Checkpoint is not active!')
            }
        
        # Check scan type - STRICT VALIDATION
        valid = False
        validation_msg = ''
        
        # Ensure scan_type is a valid string
        scan_type = str(self.scan_type).lower() if self.scan_type else ''
        
        if scan_type == 'nfc':
            if not self.nfc_tag_id:
                validation_msg = _('NFC tag is not configured for this checkpoint. Please contact your supervisor.')
                _logger.error('[Checkpoint Verify] NFC checkpoint %s has no nfc_tag_id configured!', self.name)
            else:
                try:
                    _logger.info('[Checkpoint Verify] Starting NFC verification for checkpoint %s', self.name)
                    _logger.info('[Checkpoint Verify] Raw scan_data: "%s" (type: %s, length: %d)',
                               scan_data, type(scan_data).__name__, len(scan_data) if scan_data else 0)

                    # Validate that both stored and scanned data are not empty after normalization
                    normalized_stored = self._normalize_nfc_tag(self.nfc_tag_id)
                    normalized_scanned = self._normalize_nfc_tag(scan_data)

                    if not normalized_stored:
                        _logger.error('[Checkpoint Verify] Stored NFC tag ID is empty after normalization: "%s"', self.nfc_tag_id)
                        validation_msg = _('Checkpoint NFC configuration is invalid. Please contact your supervisor.')
                    elif not normalized_scanned:
                        _logger.warning('[Checkpoint Verify] Scanned NFC data is empty after normalization: "%s"', scan_data)
                        validation_msg = _('NFC tag data could not be processed. Please ensure the tag contains valid data.')
                    else:
                        _logger.info('[Checkpoint Verify] NFC comparison - Stored: "%s" (normalized: "%s"), Scanned: "%s" (normalized: "%s")',
                                   self.nfc_tag_id, normalized_stored, scan_data, normalized_scanned)

                        # Try exact match first, then normalized match
                        if scan_data == self.nfc_tag_id or normalized_scanned == normalized_stored:
                            valid = True
                            _logger.info('[Checkpoint Verify] NFC scan SUCCESS for checkpoint %s', self.name)
                        else:
                            validation_msg = _('NFC tag does not match. Expected: %s, Got: %s') % (self.nfc_tag_id, scan_data)
                            _logger.warning('[Checkpoint Verify] NFC scan FAILED: %s', validation_msg)
                            _logger.warning('[Checkpoint Verify] NFC mismatch details - Expected normalized: "%s", Got normalized: "%s"',
                                          normalized_stored, normalized_scanned)
                except Exception as e:
                    _logger.error('[Checkpoint Verify] Error during NFC verification: %s', str(e), exc_info=True)
                    validation_msg = _('Error processing NFC tag data. Please ensure the tag is properly formatted and try again.')
                
        elif scan_type == 'qr':
            if not self.qr_code:
                validation_msg = _('QR code is not configured for this checkpoint. Please contact your supervisor.')
                _logger.error('[Checkpoint Verify] QR checkpoint %s has no qr_code configured!', self.name)
            elif scan_data == self.qr_code:
                valid = True
                _logger.info('[Checkpoint Verify] QR scan SUCCESS for checkpoint %s', self.name)
            else:
                validation_msg = _('QR code does not match. Expected: %s, Got: %s') % (self.qr_code, scan_data)
                _logger.warning('[Checkpoint Verify] QR scan FAILED: %s', validation_msg)
                
        elif scan_type == 'both':
            has_nfc = bool(self.nfc_tag_id)
            has_qr = bool(self.qr_code)
            
            if not has_nfc and not has_qr:
                validation_msg = _('Neither QR code nor NFC tag is configured for this checkpoint. Please contact your supervisor.')
                _logger.error('[Checkpoint Verify] Both-type checkpoint %s has neither qr_code nor nfc_tag_id configured!', self.name)
            else:
                try:
                    # Check QR code match (exact match)
                    qr_match = scan_data == self.qr_code if has_qr else False
                    
                    # Check NFC tag match (normalized comparison)
                    nfc_match = False
                    if has_nfc:
                        normalized_stored = self._normalize_nfc_tag(self.nfc_tag_id)
                        normalized_scanned = self._normalize_nfc_tag(scan_data)
                        nfc_match = scan_data == self.nfc_tag_id or normalized_scanned == normalized_stored
                    
                    if qr_match or nfc_match:
                        valid = True
                        _logger.info('[Checkpoint Verify] NFC/QR scan SUCCESS for checkpoint %s (QR: %s, NFC: %s)',
                                   self.name, qr_match, nfc_match)
                    else:
                        validation_msg = _('Scan data does not match NFC (%s) or QR (%s). Got: %s') % (
                            self.nfc_tag_id or 'not set', self.qr_code or 'not set', scan_data)
                        _logger.warning('[Checkpoint Verify] NFC/QR scan FAILED: %s', validation_msg)
                except Exception as e:
                    _logger.error('[Checkpoint Verify] Error processing both-type scan: %s', str(e), exc_info=True)
                    validation_msg = _('Error processing scan data. Please try again.')
                
        elif scan_type == 'virtual':
            if latitude and longitude:
                # Get tolerance from tour_log if available, otherwise use checkpoint tolerance
                tolerance = None
                if tour_log_id:
                    tour_log = self.env['tour.log'].browse(tour_log_id)
                    if tour_log.exists() and tour_log.gps_tolerance:
                        tolerance = tour_log.gps_tolerance
                        _logger.info('[Checkpoint Verify] Using tour tolerance: %s meters', tolerance)
                
                # Use checkpoint tolerance if tour tolerance not available
                if tolerance is None:
                    tolerance = self.gps_tolerance
                    _logger.info('[Checkpoint Verify] Using checkpoint tolerance: %s meters', tolerance)
                
                valid = self._verify_gps_proximity(latitude, longitude, tolerance=tolerance)
                if valid:
                    _logger.info('[Checkpoint Verify] GPS scan SUCCESS for checkpoint %s', self.name)
                else:
                    validation_msg = _('Location is too far from checkpoint (tolerance: %s meters)') % tolerance
                    _logger.warning('[Checkpoint Verify] GPS scan FAILED: %s', validation_msg)
            else:
                validation_msg = _('GPS coordinates not provided for virtual checkpoint')
                _logger.warning('[Checkpoint Verify] GPS scan FAILED: %s', validation_msg)
        else:
            # Unknown scan type
            _logger.error('[Checkpoint Verify] Unknown scan_type "%s" for checkpoint %s', scan_type, self.name)
            validation_msg = _('Unknown checkpoint scan type: %s') % scan_type
        
        if not valid:
            error_msg = validation_msg if validation_msg else _('Invalid scan data or location!')
            return {
                'success': False,
                'message': error_msg
            }
        
        # Check for duplicate scans within the same tour context
        # If tour_log_id is provided, only check for scans within that tour
        # This allows the same checkpoint to be scanned in different tours
        domain = [
            ('checkpoint_id', '=', self.id),
            ('guard_id', '=', guard_id),
            ('scan_time', '>=', fields.Datetime.now() -
             timedelta(seconds=self.min_scan_interval))
        ]
        
        # Only check for duplicates within the same tour if tour_log_id is provided
        # This allows scanning the same checkpoint again when a new tour starts
        if tour_log_id:
            domain.append(('tour_log_id', '=', tour_log_id))
            _logger.info('[Checkpoint Verify] Checking for duplicate scans within tour_log_id=%s', tour_log_id)
        
        # Add filtering for failed scans - allow retrying failed scans immediately
        domain.append(('status', '!=', 'failed'))
        
        recent_scan = self.env['checkpoint.scan'].search(domain, limit=1)
        
        if recent_scan:
            _logger.warning('[Checkpoint Verify] Duplicate scan detected: scan_id=%s, checkpoint=%s, guard=%s, tour_log=%s, status=%s',
                          recent_scan.id, self.name, guard_id, tour_log_id or 'None', recent_scan.status)
            return {
                'success': False,
                'message': _('Checkpoint scanned too recently!')
            }
        
        return {
            'success': True,
            'message': _('Checkpoint verified successfully!'),
            'checkpoint': self.name
        }

    def _verify_gps_proximity(self, lat, lng, tolerance=None):
        """
        Check if GPS coordinates are within tolerance.
        
        Args:
            lat (float): Guard's latitude
            lng (float): Guard's longitude
            tolerance (float, optional): GPS tolerance in meters. If None, uses checkpoint's gps_tolerance.
        
        Returns:
            bool: True if within tolerance, False otherwise
        """
        import math
        
        if not (self.latitude and self.longitude):
            return False
        
        # Use provided tolerance or fall back to checkpoint tolerance
        if tolerance is None:
            tolerance = self.gps_tolerance
        
        R = 6371000  # Earth's radius in meters
        
        lat1 = math.radians(self.latitude)
        lat2 = math.radians(lat)
        delta_lat = math.radians(lat - self.latitude)
        delta_lng = math.radians(lng - self.longitude)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1) * math.cos(lat2) *
             math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        
        return distance <= tolerance

