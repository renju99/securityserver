# -*- coding: utf-8 -*-
"""Guard Profile Model - Extends HR Employee.

Performance Optimizations:
- Computed fields (incident_count, attendance_rate, total_hours_worked) set to store=False
  to prevent concurrent update conflicts when related records are modified
- update_location() uses ORM write with retry logic and exponential backoff
  to handle concurrent updates gracefully without lock conflicts
- These optimizations prevent PostgreSQL serialization errors during high-concurrency scenarios
  (e.g., multiple guards updating locations or creating incidents simultaneously)
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
from markupsafe import Markup
import logging
import time
from ..common import constants, geo_utils

_logger = logging.getLogger(__name__)


class GuardProfile(models.Model):
    """Guard Profile extending HR Employee with security-specific fields."""

    _name = 'guard.profile'
    _description = 'Security Guard Profile'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # Basic Information
    name = fields.Char(
        string='Guard Name',
        required=True,
        tracking=True,
        index=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='User Account',
        ondelete='cascade',
        tracking=True,
        index=True,
        help='Portal user account for guard login'
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Related Employee',
        ondelete='cascade',
        tracking=True,
        help='Optional link to HR employee record (for payroll integration)'
    )
    badge_number = fields.Char(
        string='Badge Number',
        required=True,
        copy=False,
        tracking=True,
        index=True
    )
    phone = fields.Char(
        string='Phone Number',
        required=True,
        tracking=True
    )
    email = fields.Char(
        string='Email',
        tracking=True,
        related='user_id.email',
        readonly=False,
        store=True
    )
    photo = fields.Binary(
        string='Photo',
        attachment=True
    )
    
    # Employment Details
    hire_date = fields.Date(
        string='Hire Date',
        default=fields.Date.today,
        tracking=True
    )
    status = fields.Selection([
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated')
    ], string='Status', default='active', required=True, tracking=True)
    
    # Certifications & Training
    certifications = fields.Text(
        string='Certifications',
        help='List of security certifications held by guard'
    )
    license_number = fields.Char(
        string='Security License Number',
        tracking=True
    )
    license_expiry = fields.Date(
        string='License Expiry Date',
        tracking=True
    )
    training_ids = fields.One2many(
        'guard.training',
        'guard_id',
        string='Training Records'
    )
    
    # Credential & Compliance Management
    credential_ids = fields.One2many(
        'guard.credential',
        'guard_id',
        string='Credentials & Licenses'
    )
    background_check_ids = fields.One2many(
        'guard.background.check',
        'guard_id',
        string='Background Checks'
    )
    drug_test_ids = fields.One2many(
        'guard.drug.test',
        'guard_id',
        string='Drug/Alcohol Tests'
    )
    vaccination_ids = fields.One2many(
        'guard.vaccination',
        'guard_id',
        string='Vaccination Records'
    )
    
    # Compliance Status
    credential_compliance_status = fields.Selection([
        ('compliant', 'Fully Compliant'),
        ('warning', 'Warning - Action Needed'),
        ('non_compliant', 'Non-Compliant')
    ], string='Credential Compliance', compute='_compute_credential_compliance', store=False)
    
    expired_credentials_count = fields.Integer(
        string='Expired Credentials',
        compute='_compute_credential_compliance',
        store=False
    )
    expiring_soon_count = fields.Integer(
        string='Credentials Expiring Soon',
        compute='_compute_credential_compliance',
        store=False
    )
    background_check_status = fields.Selection([
        ('none', 'No Background Check'),
        ('pending', 'Pending'),
        ('clear', 'Clear'),
        ('expired', 'Expired'),
        ('flagged', 'Flagged')
    ], string='Background Check Status', compute='_compute_background_check_status', store=False)
    
    last_background_check_date = fields.Date(
        string='Last Background Check',
        compute='_compute_background_check_status',
        store=False
    )
    
    last_drug_test_date = fields.Date(
        string='Last Drug Test',
        compute='_compute_drug_test_status',
        store=False
    )
    last_drug_test_result = fields.Selection([
        ('negative', 'Negative'),
        ('positive', 'Positive'),
        ('pending', 'Pending')
    ], string='Last Test Result', compute='_compute_drug_test_status', store=False)
    
    # Contact Information
    emergency_contact = fields.Char(
        string='Emergency Contact Name'
    )
    emergency_phone = fields.Char(
        string='Emergency Contact Phone'
    )
    address = fields.Text(
        string='Address'
    )
    
    # Skills & Qualifications
    skills = fields.Many2many(
        'guard.skill',
        string='Skills',
        help='Special skills (Armed, K9, First Aid, etc.)'
    )
    languages = fields.Char(
        string='Languages Spoken'
    )
    
    # Shift & Availability
    shift_ids = fields.One2many(
        'guard.shift',
        'guard_id',
        string='Assigned Shifts'
    )
    site_ids = fields.Many2many(
        'client.site',
        related='user_id.site_ids',
        string='Assigned Sites',
        readonly=True,
        help='Sites assigned to this guard via their user account. '
             'To modify site assignments, go to Settings → Users and edit the user record.'
    )
    availability = fields.Selection([
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('on_call', 'On Call')
    ], string='Availability', default='full_time')
    
    # Performance Tracking
    incident_count = fields.Integer(
        string='Incidents Reported',
        compute='_compute_incident_count',
        store=False  # Changed to False to reduce concurrent update conflicts
    )
    attendance_rate = fields.Float(
        string='Attendance Rate %',
        compute='_compute_attendance_rate',
        store=False,  # Changed to False to reduce concurrent update conflicts
        help="Attendance rate: (attended shifts / total past shifts) × 100"
    )
    rating = fields.Selection([
        ('0', '0 - Not Rated'),
        ('1', '1 - Poor'),
        ('2', '2 - Fair'),
        ('3', '3 - Good'),
        ('4', '4 - Very Good'),
        ('5', '5 - Excellent')
    ], string='Rating', default='0', help='Overall performance rating (0-5)')
    
    # Current Location (for real-time tracking)
    # GPS coordinates: latitude range -90 to 90, longitude range -180 to 180
    # Removing digits parameter to fix Odoo 18 Float field reading issue
    # Standard Float field can handle GPS coordinates with full precision
    current_latitude = fields.Float(
        string='Current Latitude'
    )
    current_longitude = fields.Float(
        string='Current Longitude'
    )
    last_location_update = fields.Datetime(
        string='Last Location Update'
    )
    location_sharing_enabled = fields.Boolean(
        string='Location Sharing Enabled',
        default=True,
        help='Allow automatic GPS location tracking for this guard'
    )
    current_site_id = fields.Many2one(
        'client.site',
        string='Current Site',
        ondelete='set null',
        help='Site where guard is currently assigned'
    )
    
    # Device Information
    device_id = fields.Char(
        string='Mobile Device ID',
        help='Unique identifier for guard mobile device'
    )
    device_model = fields.Char(
        string='Device Model'
    )
    app_version = fields.Char(
        string='App Version'
    )
    last_sync = fields.Datetime(
        string='Last Sync Time'
    )
    
    # Statistics
    total_hours_worked = fields.Float(
        string='Total Hours Worked',
        compute='_compute_total_hours',
        store=False  # Changed to False to reduce concurrent update conflicts
    )
    active_tours = fields.Integer(
        string='Active Tours',
        compute='_compute_active_tours',
        store=False  # Explicitly set to False for clarity
    )
    
    # Performance Management
    performance_review_ids = fields.One2many(
        'guard.performance.review',
        'guard_id',
        string='Performance Reviews'
    )
    performance_badge_ids = fields.One2many(
        'guard.performance.badge',
        'guard_id',
        string='Performance Badges'
    )
    current_performance_score = fields.Float(
        string='Current Performance Score',
        compute='_compute_current_performance',
        store=False,
        help='Latest overall performance score'
    )
    performance_rating = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('satisfactory', 'Satisfactory'),
        ('needs_improvement', 'Needs Improvement'),
        ('unsatisfactory', 'Unsatisfactory'),
    ], string='Performance Rating', compute='_compute_current_performance',
       store=False)
    last_review_date = fields.Date(
        string='Last Review Date',
        compute='_compute_current_performance',
        store=False
    )
    badge_count = fields.Integer(
        string='Badges Earned',
        compute='_compute_badge_count'
    )
    
    # Notes
    notes = fields.Text(
        string='Internal Notes'
    )
    
    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    
    _sql_constraints = [
        ('badge_unique', 'unique(badge_number)',
         'Badge number must be unique!'),
    ]

    @api.depends('incident_report_ids')
    def _compute_incident_count(self):
        """Compute total number of incidents reported by guard."""
        for record in self:
            record.incident_count = len(record.incident_report_ids)

    incident_report_ids = fields.One2many(
        'incident.report',
        'guard_id',
        string='Incident Reports'
    )

    @api.depends('attendance_ids', 'shift_ids', 'shift_ids.start_datetime')
    def _compute_attendance_rate(self):
        """Calculate attendance rate based on scheduled vs actual attendance."""
        for record in self:
            # Get all past shifts (shifts that should have started by now)
            now = fields.Datetime.now()
            past_shifts = record.shift_ids.filtered(
                lambda s: s.start_datetime and s.start_datetime < now
            )
            
            if not past_shifts:
                record.attendance_rate = 0.0
                _logger.debug(f"Guard {record.name} (ID: {record.id}): No past shifts, attendance_rate = 0%")
                continue
            
            # Get attendance records that are linked to past shifts
            # Only count attendance records that have a valid shift_id
            attended_shifts = self.env['guard.shift'].browse()
            for shift in past_shifts:
                # Check if this shift has any attendance record
                has_attendance = record.attendance_ids.filtered(
                    lambda a: a.shift_id and a.shift_id.id == shift.id
                )
                if has_attendance:
                    attended_shifts |= shift
            
            attended_count = len(attended_shifts)
            total_shifts = len(past_shifts)
            
            # Don't multiply by 100 here - the percentage widget does it automatically
            record.attendance_rate = (
                (attended_count / total_shifts) if total_shifts > 0 else 0.0
            )
            
            _logger.info(
                f"Guard {record.name} (ID: {record.id}): "
                f"Attendance Rate = {record.attendance_rate * 100:.2f}% "
                f"({attended_count} attended / {total_shifts} total past shifts)"
            )

    attendance_ids = fields.One2many(
        'guard.attendance',
        'guard_id',
        string='Attendance Records'
    )

    @api.depends('attendance_ids.hours_worked')
    def _compute_total_hours(self):
        """Calculate total hours worked by guard."""
        for record in self:
            record.total_hours_worked = sum(
                record.attendance_ids.mapped('hours_worked')
            )

    def _compute_active_tours(self):
        """Count currently active tours."""
        for record in self:
            record.active_tours = self.env['tour.log'].search_count([
                ('guard_id', '=', record.id),
                ('status', '=', 'in_progress')
            ])

    @api.depends('performance_review_ids', 'performance_review_ids.overall_score',
                 'performance_review_ids.state')
    def _compute_current_performance(self):
        """Calculate current performance metrics from latest approved review."""
        for record in self:
            # Get latest approved review
            latest_review = self.env['guard.performance.review'].search([
                ('guard_id', '=', record.id),
                ('state', '=', 'approved'),
            ], order='review_date desc', limit=1)
            
            if latest_review:
                record.current_performance_score = latest_review.overall_score
                record.last_review_date = latest_review.review_date
                
                # Set rating based on score
                score = latest_review.overall_score
                if score >= 90:
                    record.performance_rating = 'excellent'
                elif score >= 80:
                    record.performance_rating = 'good'
                elif score >= 70:
                    record.performance_rating = 'satisfactory'
                elif score >= 60:
                    record.performance_rating = 'needs_improvement'
                else:
                    record.performance_rating = 'unsatisfactory'
            else:
                record.current_performance_score = 0.0
                record.performance_rating = False
                record.last_review_date = False

    @api.depends('performance_badge_ids')
    def _compute_badge_count(self):
        """Count earned badges."""
        for record in self:
            record.badge_count = len(record.performance_badge_ids)

    @api.depends('credential_ids', 'credential_ids.state', 'credential_ids.compliance_status')
    def _compute_credential_compliance(self):
        """Compute overall credential compliance status."""
        for record in self:
            expired = record.credential_ids.filtered(lambda c: c.state == 'expired')
            expiring = record.credential_ids.filtered(lambda c: c.state == 'expiring_soon')
            suspended = record.credential_ids.filtered(lambda c: c.state in ['suspended', 'revoked'])
            
            record.expired_credentials_count = len(expired)
            record.expiring_soon_count = len(expiring)
            
            # Determine overall status
            if expired or suspended:
                record.credential_compliance_status = 'non_compliant'
            elif expiring:
                record.credential_compliance_status = 'warning'
            else:
                record.credential_compliance_status = 'compliant'
    
    @api.depends('background_check_ids', 'background_check_ids.status', 'background_check_ids.check_date')
    def _compute_background_check_status(self):
        """Compute background check status."""
        for record in self:
            if not record.background_check_ids:
                record.background_check_status = 'none'
                record.last_background_check_date = False
            else:
                latest = record.background_check_ids.sorted('check_date', reverse=True)[0]
                record.last_background_check_date = latest.check_date
                record.background_check_status = latest.status
    
    @api.depends('drug_test_ids', 'drug_test_ids.status', 'drug_test_ids.test_date')
    def _compute_drug_test_status(self):
        """Compute drug test status."""
        for record in self:
            if not record.drug_test_ids:
                record.last_drug_test_date = False
                record.last_drug_test_result = False
            else:
                latest = record.drug_test_ids.sorted('test_date', reverse=True)[0]
                record.last_drug_test_date = latest.test_date.date() if latest.test_date else False
                if latest.status == 'negative':
                    record.last_drug_test_result = 'negative'
                elif latest.status == 'positive':
                    record.last_drug_test_result = 'positive'
                else:
                    record.last_drug_test_result = 'pending'

    @api.constrains('license_expiry')
    def _check_license_expiry(self):
        """Validate license expiry date."""
        for record in self:
            if record.license_expiry and record.license_expiry < fields.Date.today():
                raise ValidationError(_(
                    'Guard %s has an expired security license!'
                ) % record.name)

    @api.constrains('email')
    def _check_email(self):
        """Validate email format."""
        for record in self:
            if record.email:
                import re
                if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', record.email):
                    raise ValidationError(_('Invalid email format!'))

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure email is set for eLearning access."""
        # Create records - context flags from caller will be respected automatically
        records = super(GuardProfile, self).create(vals_list)
        
        # Ensure all new guards have valid emails for eLearning
        # Use mail_notrack context to prevent email notifications during email setup
        for record in records:
            try:
                record.with_context(mail_notrack=True)._ensure_elearning_email()
            except Exception:
                # Silently ignore email-related errors when suppressing mail
                pass
        
        return records

    def write(self, vals):
        """Override write to maintain email verification."""
        res = super(GuardProfile, self).write(vals)
        
        # If user_id changed, ensure email is set
        if 'user_id' in vals:
            for record in self:
                record._ensure_elearning_email()
        
        return res

    def _ensure_elearning_email(self):
        """
        Ensure guard has a valid email for eLearning access.
        
        This prevents the "Your Account has not yet been verified" error
        by ensuring all guards have valid email addresses in their partner records
        and setting karma to bypass verification checks.
        """
        self.ensure_one()
        
        if not self.user_id:
            return
        
        partner = self.user_id.partner_id
        if not partner:
            return
        
        # Check if partner has a valid email
        current_email = partner.email
        user_login = self.user_id.login
        
        if not current_email or '@' not in str(current_email):
            # Set email based on login if it's an email, otherwise create one
            if user_login and '@' in user_login:
                new_email = user_login
            else:
                new_email = f'{user_login}@guardpro.local' if user_login else f'guard{self.id}@guardpro.local'
            
            try:
                # Use mail_notrack context to prevent email notifications
                partner.sudo().with_context(mail_notrack=True).write({'email': new_email})
                _logger.info('Set email for guard %s partner: %s', self.name, new_email)
            except Exception as e:
                _logger.error('Error setting email for guard %s: %s', self.name, str(e))
        
        # Set karma to bypass email verification in website_profile
        # The website_profile module shows verification error if karma == 0
        if self.user_id.karma == 0:
            try:
                # Use mail_notrack context to prevent email notifications
                self.user_id.sudo().with_context(mail_notrack=True).write({'karma': 100})
                _logger.info('Set karma=100 for guard %s to bypass verification', self.name)
            except Exception as e:
                _logger.error('Error setting karma for guard %s: %s', self.name, str(e))

    def action_fix_elearning_access(self):
        """
        Action to fix eLearning access for selected guards.
        
        This is a manual action that can be triggered from the UI to ensure
        all selected guards have proper email configuration for eLearning.
        """
        for record in self:
            record._ensure_elearning_email()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('eLearning Access Fixed'),
                'message': _('%d guard(s) email configuration verified') % len(self),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_shifts(self):
        """Open guard's shift schedule."""
        self.ensure_one()
        return {
            'name': _('Shifts - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.shift',
            'view_mode': 'calendar,list,form',
            'domain': [('guard_id', '=', self.id)],
            'context': {'default_guard_id': self.id}
        }

    def action_view_incidents(self):
        """Open guard's incident reports."""
        self.ensure_one()
        return {
            'name': _('Incidents - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'incident.report',
            'view_mode': 'list,form',
            'domain': [('guard_id', '=', self.id)],
            'context': {'default_guard_id': self.id}
        }

    def action_view_attendance(self):
        """Open guard's attendance records."""
        self.ensure_one()
        return {
            'name': _('Attendance - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.attendance',
            'view_mode': 'list,form',
            'domain': [('guard_id', '=', self.id)],
            'context': {'default_guard_id': self.id}
        }
    
    def action_view_credentials(self):
        """Open guard's credentials and licenses."""
        self.ensure_one()
        return {
            'name': _('Credentials - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.credential',
            'view_mode': 'list,form',
            'domain': [('guard_id', '=', self.id)],
            'context': {'default_guard_id': self.id}
        }
    
    def action_view_background_checks(self):
        """Open guard's background checks."""
        self.ensure_one()
        return {
            'name': _('Background Checks - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.background.check',
            'view_mode': 'list,form',
            'domain': [('guard_id', '=', self.id)],
            'context': {'default_guard_id': self.id}
        }
    
    def action_view_drug_tests(self):
        """Open guard's drug/alcohol tests."""
        self.ensure_one()
        return {
            'name': _('Drug/Alcohol Tests - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.drug.test',
            'view_mode': 'list,form',
            'domain': [('guard_id', '=', self.id)],
            'context': {'default_guard_id': self.id}
        }
    
    def action_view_vaccinations(self):
        """Open guard's vaccination records."""
        self.ensure_one()
        return {
            'name': _('Vaccinations - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.vaccination',
            'view_mode': 'list,form',
            'domain': [('guard_id', '=', self.id)],
            'context': {'default_guard_id': self.id}
        }
    
    def action_recalculate_attendance_rate(self):
        """Manual action to recalculate attendance rate."""
        self.ensure_one()
        
        # Force complete cache invalidation
        self.invalidate_recordset(['attendance_rate', 'attendance_ids', 'shift_ids'])
        self._compute_attendance_rate()
        
        # Get the calculated rate
        rate = self.attendance_rate
        
        # Return window action with reload context
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'guard.profile',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {
                **self.env.context,
                'params': {
                    'reload': True,
                }
            },
            'flags': {
                'mode': 'readonly',
            }
        }

    def update_location(self, latitude, longitude, **kwargs):
        """Update guard's current GPS location.
        
        Uses optimistic concurrency control with retry logic.
        Location updates are non-critical and will be retried on next ping if they fail.
        
        Args:
            latitude: GPS latitude coordinate
            longitude: GPS longitude coordinate
            **kwargs: Optional parameters (accuracy, altitude, speed, heading, battery_level, etc.)
        """
        self.ensure_one()
        
        retry_count = 0
        
        while retry_count < constants.LOCATION_UPDATE_MAX_RETRIES:
            try:
                # Use ORM write with automatic transaction management
                # This will wait for locks instead of failing immediately
                self.write({
                    'current_latitude': latitude,
                    'current_longitude': longitude,
                    'last_location_update': fields.Datetime.now()
                })
                
                # Save location history for path tracking
                self._save_location_history(latitude, longitude, kwargs)
                
                # Check if guard is within any geofenced site
                self._check_geofence()
                
                _logger.debug('Location updated for guard %s: lat=%s, lon=%s', 
                             self.id, latitude, longitude)
                return True
                             
            except Exception as e:
                retry_count += 1
                error_msg = str(e)
                
                # Check if it's a serialization/lock error
                if 'could not serialize' in error_msg or 'could not obtain lock' in error_msg:
                    if retry_count < constants.LOCATION_UPDATE_MAX_RETRIES:
                        _logger.debug('Guard %s location update retry %d/%d due to concurrency', 
                                     self.id, retry_count, constants.LOCATION_UPDATE_MAX_RETRIES)
                        # Small delay before retry (exponential backoff)
                        delay = constants.LOCATION_UPDATE_RETRY_DELAY * retry_count if constants.LOCATION_UPDATE_RETRY_BACKOFF else constants.LOCATION_UPDATE_RETRY_DELAY
                        time.sleep(delay)
                        continue
                    else:
                        _logger.debug('Guard %s location update failed after %d retries (concurrent update)', 
                                     self.id, constants.LOCATION_UPDATE_MAX_RETRIES)
                        return False
                else:
                    # Unexpected error - log and exit
                    _logger.warning('Location update failed for guard %s: %s', self.id, error_msg)
                    return False
        
        return False
    
    @api.model
    def api_update_location(self, latitude, longitude, accuracy=None):
        """API method to update guard's current GPS location from frontend.
        
        This method is called from the GPS widget via ORM RPC.
        It finds the guard profile for the current user and updates their location.
        
        Args:
            latitude: GPS latitude coordinate
            longitude: GPS longitude coordinate
            accuracy: Optional GPS accuracy in meters
        
        Returns:
            dict: Response with success status or error details
        """
        try:
            # Find guard profile for current user
            guard = self.sudo().search([
                ('user_id', '=', self.env.user.id)
            ], limit=1)
            
            if not guard:
                _logger.warning(
                    '[GPS] Guard profile not found for user %s (ID: %s)',
                    self.env.user.name,
                    self.env.user.id
                )
                return {
                    'success': False,
                    'error': 'Guard profile not found',
                    'details': 'No guard profile linked to your user account. Contact your administrator.'
                }
            
            # Prepare kwargs with accuracy if provided
            kwargs = {}
            if accuracy is not None:
                kwargs['accuracy'] = accuracy
            
            # Update location using existing method
            _logger.info('[GPS] Updating location for guard %s (ID: %s)', guard.name, guard.id)
            success = guard.update_location(latitude, longitude, **kwargs)
            
            if success:
                _logger.info('[GPS] Location update successful for guard %s', guard.name)
                return {
                    'success': True,
                    'guard_id': guard.id,
                    'guard_name': guard.name,
                    'latitude': latitude,
                    'longitude': longitude,
                    'timestamp': fields.Datetime.now().isoformat()
                }
            else:
                _logger.warning('[GPS] Location update failed for guard %s', guard.name)
                return {
                    'success': False,
                    'error': 'Update failed',
                    'details': 'Failed to update location. Please try again.'
                }
                
        except Exception as e:
            _logger.error(
                '[GPS] Location update error for user %s: %s',
                self.env.user.name,
                str(e),
                exc_info=True
            )
            return {
                'success': False,
                'error': str(e),
                'details': 'An unexpected error occurred. Please contact your administrator.'
            }
    
    def _save_location_history(self, latitude, longitude, extra_data):
        """Save location to history for path tracking.
        
        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            extra_data: Dictionary with optional fields (accuracy, speed, etc.)
        """
        self.ensure_one()
        try:
            # Find active shift or tour
            active_shift = self.env['guard.shift'].search([
                ('guard_id', '=', self.id),
                ('status', '=', 'in_progress')
            ], limit=1)
            
            active_tour = self.env['tour.log'].search([
                ('guard_id', '=', self.id),
                ('status', '=', 'in_progress')
            ], limit=1)
            
            # Create location history record
            history_vals = {
                'guard_id': self.id,
                'latitude': latitude,
                'longitude': longitude,
                'site_id': self.current_site_id.id if self.current_site_id else None,
                'shift_id': active_shift.id if active_shift else None,
                'tour_log_id': active_tour.id if active_tour else None,
                'accuracy': extra_data.get('accuracy'),
                'altitude': extra_data.get('altitude'),
                'speed': extra_data.get('speed'),
                'heading': extra_data.get('heading'),
                'battery_level': extra_data.get('battery_level'),
                'is_manual': extra_data.get('is_manual', False),
            }
            
            # Note: Guards have create access to location history via ACL
            self.env['guard.location.history'].create(history_vals)
            _logger.debug('Location history saved for guard %s', self.id)
            
        except Exception as e:
            # Don't fail the location update if history saving fails
            _logger.warning('Failed to save location history for guard %s: %s', self.id, str(e))

    def _check_geofence(self):
        """Check if guard is within assigned site geofence.
        
        This method checks if the guard's current location is within
        the geofence of any active shifts' sites. It logs geofence
        violations but doesn't prevent location updates.
        """
        self.ensure_one()
        if not (self.current_latitude and self.current_longitude):
            return
        
        # Get guard's shifts that are active *right now*.
        Shift = self.env['guard.shift']
        now = fields.Datetime.now()
        
        active_shifts = Shift.search([
            ('guard_id', '=', self.id),
            ('status', 'in', ['scheduled', 'confirmed', 'in_progress']),
            ('start_datetime', '<=', now),
            ('end_datetime', '>=', now)
        ])
        
        if not active_shifts:
            _logger.debug('Guard %s has no active shifts - skipping geofence check', self.id)
            return
        
        # Deduplicate by site to avoid duplicate alerts when overlapping shifts
        # point to the same site for the same guard.
        shifts_by_site = {}
        for shift in active_shifts.sorted(
            key=lambda s: (s.status != 'in_progress', s.start_datetime or fields.Datetime.now())
        ):
            if shift.site_id and shift.site_id.id not in shifts_by_site:
                shifts_by_site[shift.site_id.id] = shift

        # Check geofence once per site
        for shift in shifts_by_site.values():
            site = shift.site_id
            
            # Skip if geofencing is disabled
            if not site.geofence_enabled:
                _logger.debug('Geofencing disabled for site %s', site.name)
                continue
            
            # Check if guard is within geofence
            is_inside = site.check_guard_in_geofence(
                self.current_latitude,
                self.current_longitude
            )
            
            if is_inside:
                _logger.info(
                    'Guard %s is INSIDE geofence of site %s (lat=%s, lon=%s)',
                    self.name, site.name,
                    self.current_latitude, self.current_longitude
                )
            else:
                # Calculate distance for debugging
                distance = self._calculate_distance_to_site(site)
                _logger.warning(
                    'Guard %s is OUTSIDE geofence of site %s! '
                    'Distance: %.2f meters (allowed: %.2f meters) '
                    'Guard location: (%.7f, %.7f), Site location: (%.7f, %.7f)',
                    self.name, site.name,
                    distance, site.geofence_radius,
                    self.current_latitude, self.current_longitude,
                    site.latitude, site.longitude
                )
                
                # Create alert (internally rate-limited by interval, default: 15 min).
                # No mail.activity here — those send "assigned to you" emails; bus + geofence.alert row is enough.
                self.env['geofence.alert'].sudo().create_alert(
                    guard_id=self.id,
                    alert_type='outside_geofence',
                    site_id=site.id,
                    shift_id=shift.id,
                    latitude=self.current_latitude,
                    longitude=self.current_longitude,
                    distance_from_site=distance / 1000  # Convert to km
                )
    
    def _calculate_distance_to_site(self, site):
        """Calculate distance between guard and site in meters using Haversine formula."""
        return geo_utils.haversine_distance(
            site.latitude, site.longitude,
            self.current_latitude, self.current_longitude,
            unit='meters'
        )
    
    def action_test_geofence(self):
        """Manual geofence test - shows detailed debug information.
        
        This action can be called from a button to diagnose geofence issues.
        """
        self.ensure_one()
        
        # Prepare debug message
        messages = []
        messages.append(f"=== Geofence Debug for {self.name} ===\n")
        
        # Check if guard has current location
        if not self.current_latitude or not self.current_longitude:
            messages.append("❌ ERROR: No GPS location recorded for this guard")
            messages.append(f"   Current location: ({self.current_latitude}, {self.current_longitude})")
            raise ValidationError('\n'.join(messages))
        
        messages.append(f"✓ Guard GPS Location: ({self.current_latitude:.7f}, {self.current_longitude:.7f})")
        messages.append(f"  Last updated: {self.last_location_update}\n")
        
        # Get active shifts (scheduled, confirmed, or in_progress) for today
        # This includes shifts that start today or are ongoing from previous days
        today = fields.Date.today()
        today_start = fields.Datetime.to_datetime(today)
        today_end = today_start + timedelta(days=1)
        
        active_shifts = self.env['guard.shift'].search([
            ('guard_id', '=', self.id),
            ('status', 'in', ['scheduled', 'confirmed', 'in_progress']),
            ('start_datetime', '<', today_end),
            ('end_datetime', '>', today_start)
        ])
        
        if not active_shifts:
            messages.append("⚠ WARNING: No active shifts found for today")
            messages.append("   Geofence checking only applies to active shifts\n")
        
        # Check all assigned sites (from current assignment or active shifts)
        sites_to_check = set()
        if self.current_site_id:
            sites_to_check.add(self.current_site_id)
        for shift in active_shifts:
            if shift.site_id:
                sites_to_check.add(shift.site_id)
        
        if not sites_to_check:
            messages.append("❌ ERROR: No sites assigned to this guard")
            raise ValidationError('\n'.join(messages))
        
        # Check each site
        for site in sites_to_check:
            messages.append(f"\n--- Checking Site: {site.name} ---")
            messages.append(f"Site Location: ({site.latitude:.7f}, {site.longitude:.7f})")
            
            # Check if geofencing is enabled
            if not site.geofence_enabled:
                messages.append("ℹ  Geofencing: DISABLED (all guards allowed)")
                continue
            
            messages.append(f"✓ Geofencing: ENABLED")
            messages.append(f"  Type: {site.geofence_type}")
            
            if site.geofence_type == 'circle':
                messages.append(f"  Radius: {site.geofence_radius} meters")
                
                # Calculate distance
                distance = self._calculate_distance_to_site(site)
                messages.append(f"  Distance from site: {distance:.2f} meters")
                
                # Check if inside
                is_inside = site.check_guard_in_geofence(
                    self.current_latitude,
                    self.current_longitude
                )
                
                if is_inside:
                    messages.append(f"✓ Status: INSIDE GEOFENCE")
                    messages.append(f"  You are {distance:.2f}m from center (within {site.geofence_radius}m radius)")
                else:
                    messages.append(f"❌ Status: OUTSIDE GEOFENCE")
                    messages.append(f"  You are {distance:.2f}m from center (exceeds {site.geofence_radius}m radius)")
                    messages.append(f"  You need to move {distance - site.geofence_radius:.2f}m closer")
            
            elif site.geofence_type == 'polygon':
                messages.append(f"  Polygon coordinates: {site.geofence_polygon}")
                
                # Check if inside polygon
                is_inside = site.check_guard_in_geofence(
                    self.current_latitude,
                    self.current_longitude
                )
                
                if is_inside:
                    messages.append(f"✓ Status: INSIDE POLYGON GEOFENCE")
                else:
                    messages.append(f"❌ Status: OUTSIDE POLYGON GEOFENCE")
        
        # Show the debug information
        message = '\n'.join(messages)
        _logger.info(message)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Geofence Test Results',
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }
    
    # ====================================================
    # SCHEDULED ACTIONS (CRON JOBS)
    # ====================================================
    
    @api.model
    def check_certification_expiry(self):
        """Check for expiring certifications and send alerts.
        
        Called by scheduled action daily at 8 AM.
        Alerts for certifications expiring within 30 days.
        """
        from datetime import datetime, timedelta
        
        now = fields.Date.today()
        warning_date = now + timedelta(days=30)
        critical_date = now + timedelta(days=7)
        
        # Find guards with expiring licenses
        guards_expiring = self.search([
            ('license_expiry', '!=', False),
            ('license_expiry', '<=', warning_date),
            ('license_expiry', '>=', now),
            ('status', 'in', ['active', 'on_shift'])
        ])
        
        if guards_expiring:
            _logger.info('Found %d guards with expiring licenses', len(guards_expiring))
        
        for guard in guards_expiring:
            days_remaining = (guard.license_expiry - now).days
            
            # Determine urgency
            if days_remaining <= 7:
                priority = 'urgent'
                activity_type = 'mail.mail_activity_data_urgent'
            elif days_remaining <= 14:
                priority = 'high'
                activity_type = 'mail.mail_activity_data_warning'
            else:
                priority = 'normal'
                activity_type = 'mail.mail_activity_data_todo'
            
            try:
                # Create activity for HR/Manager
                guard.activity_schedule(
                    activity_type,
                    summary=_('License Expiring: %s') % guard.name,
                    note=_(
                        'Guard %s (Badge: %s) license will expire in %d days on %s.\n\n'
                        'Action Required: Renew license immediately.'
                    ) % (guard.name, guard.badge_number, days_remaining, guard.license_expiry),
                    user_id=self.env.ref('base.group_system').users[0].id if self.env.ref('base.group_system').users else self.env.user.id
                )
                
                # Send notification to guard
                guard.message_post(
                    body=Markup(
                        '<p><strong>License Expiration Warning</strong></p>'
                        '<p>Your security license will expire in <strong>%d days</strong> on %s.</p>'
                        '<p>Please renew your license before the expiration date to avoid being removed from active assignments.</p>'
                        '<p style="margin-top: 16px; font-size: 12px; color: #888;">This is an automated reminder from GuardPro Compliance Monitoring.</p>'
                    ) % (days_remaining, guard.license_expiry.strftime('%Y-%m-%d')),
                    partner_ids=guard.user_id.partner_id.ids if guard.user_id else []
                )
                
                _logger.info('Created expiry alert for guard %s (expires in %d days)',
                           guard.name, days_remaining)
                           
            except Exception as e:
                _logger.error('Error creating certification expiry alert for guard %s: %s',
                            guard.id, str(e))
        
        # Check training certifications
        expiring_trainings = self.env['guard.training'].search([
            ('expiry_date', '!=', False),
            ('expiry_date', '<=', warning_date),
            ('expiry_date', '>=', now)
        ])
        
        if expiring_trainings:
            _logger.info('Found %d expiring training certifications', len(expiring_trainings))
        
        for training in expiring_trainings:
            days_remaining = (training.expiry_date - now).days
            
            try:
                training.guard_id.message_post(
                    body=Markup(
                        '<p><strong>Training Certification Expiring</strong></p>'
                        '<p>Your %s certification will expire in <strong>%d days</strong> on %s.</p>'
                        '<p>Please schedule a renewal training session before the expiration date.</p>'
                        '<p style="margin-top: 16px; font-size: 12px; color: #888;">This is an automated reminder from GuardPro Training Compliance.</p>'
                    ) % (
                        training.course_id.name,
                        days_remaining,
                        training.expiry_date.strftime('%Y-%m-%d')
                    ),
                    partner_ids=training.guard_id.user_id.partner_id.ids if training.guard_id.user_id else []
                )
            except Exception as e:
                _logger.error('Error notifying guard about training expiry: %s', str(e))
        
        return True
    
    @api.model
    def update_guard_status(self):
        """Update guard status based on current shifts and availability.
        
        Called by scheduled action every hour.
        Updates guard status (active, on_shift, off_duty, etc.).
        """
        now = fields.Datetime.now()
        
        # Find guards currently on shift
        active_shifts = self.env['guard.shift'].search([
            ('start_datetime', '<=', now),
            ('end_datetime', '>=', now),
            ('status', '=', 'in_progress')
        ])
        
        guards_on_shift = active_shifts.mapped('guard_id')
        
        # Update guards on shift
        if guards_on_shift:
            guards_on_shift.filtered(lambda g: g.status != 'on_shift').write({
                'status': 'on_shift'
            })
            _logger.debug('Updated %d guards to on_shift status', len(guards_on_shift))
        
        # Update guards who just finished shifts
        recently_finished = self.env['guard.shift'].search([
            ('end_datetime', '>=', now - timedelta(hours=1)),
            ('end_datetime', '<=', now),
            ('status', '=', 'completed')
        ]).mapped('guard_id')
        
        if recently_finished:
            recently_finished.filtered(lambda g: g.status == 'on_shift').write({
                'status': 'active'
            })
            _logger.debug('Updated %d guards to active status after shift end', len(recently_finished))
        
        return True


class GuardSkill(models.Model):
    """Guard Skills and Qualifications."""

    _name = 'guard.skill'
    _description = 'Guard Skill'
    _order = 'name'

    name = fields.Char(
        string='Skill Name',
        required=True
    )
    description = fields.Text(
        string='Description'
    )
    requires_certification = fields.Boolean(
        string='Requires Certification',
        default=False
    )
    color = fields.Integer(
        string='Color',
        default=0,
        help='Color index for tag display'
    )


class GuardTraining(models.Model):
    """Guard Training Records."""

    _name = 'guard.training'
    _description = 'Guard Training Record'
    _order = 'date desc'

    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char(
        string='Training Name',
        required=True
    )
    date = fields.Date(
        string='Training Date',
        required=True
    )
    instructor = fields.Char(
        string='Instructor'
    )
    hours = fields.Float(
        string='Training Hours'
    )
    certificate_issued = fields.Boolean(
        string='Certificate Issued',
        default=False
    )
    expiry_date = fields.Date(
        string='Certificate Expiry'
    )
    notes = fields.Text(
        string='Notes'
    )

