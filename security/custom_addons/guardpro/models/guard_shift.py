# -*- coding: utf-8 -*-
"""Guard Shift Model - Scheduling."""

from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class GuardShift(models.Model):
    """Guard Shift Scheduling."""

    _name = 'guard.shift'
    _description = 'Guard Shift'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_datetime desc'

    # Basic Information
    name = fields.Char(
        string='Shift Name',
        compute='_compute_name',
        store=True
    )
    # Shifts are payroll + attendance records. Block deletion of the
    # underlying guard/site while shifts exist - the admin must archive
    # instead. Otherwise a simple "delete user" wipes every attendance
    # entry for that guard across the year.
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
        index=True,
        ondelete='restrict'
    )
    
    # Timing
    start_datetime = fields.Datetime(
        string='Start Date/Time',
        tracking=True,
        index=True
    )
    end_datetime = fields.Datetime(
        string='End Date/Time',
        tracking=True
    )
    duration = fields.Float(
        string='Duration (hours)',
        compute='_compute_duration',
        store=True
    )
    
    # Shift Type
    shift_type = fields.Selection([
        ('regular', 'Regular'),
        ('overtime', 'Overtime'),
        ('holiday', 'Holiday'),
        ('emergency', 'Emergency')
    ], string='Shift Type', default='regular', required=True, tracking=True)
    
    # Status
    status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show')
    ], string='Status', default='scheduled', required=True, tracking=True)
    
    # Assignment Details
    assignment_type = fields.Selection([
        ('patrol', 'Patrol'),
        ('static', 'Static Post'),
        ('event', 'Special Event'),
        ('emergency', 'Emergency Response')
    ], string='Assignment Type', default='patrol')
    
    post_location = fields.Char(
        string='Post Location',
        help='Specific location within the site'
    )
    
    # Tours
    tour_ids = fields.Many2many(
        'security.tour',
        string='Assigned Tours',
        help='Tours to be completed during this shift',
        ondelete='cascade'
    )
    
    # Requirements
    armed = fields.Boolean(
        string='Armed Required',
        default=False
    )
    uniform_type = fields.Selection([
        ('standard', 'Standard'),
        ('formal', 'Formal'),
        ('casual', 'Casual'),
        ('special', 'Special Event')
    ], string='Uniform Type', default='standard')
    
    special_equipment = fields.Text(
        string='Special Equipment Required'
    )
    
    # Notifications
    reminder_sent = fields.Boolean(
        string='Reminder Sent',
        default=False,
        help='Whether shift reminder notification has been sent'
    )
    
    # Shift Start/Shift End
    checkin_time = fields.Datetime(
        string='Shift Start Time',
        tracking=True
    )
    checkout_time = fields.Datetime(
        string='Shift End Time',
        tracking=True
    )
    checkin_latitude = fields.Float(
        string='Shift Start Latitude',
        digits=(10, 7)
    )
    checkin_longitude = fields.Float(
        string='Shift Start Longitude',
        digits=(10, 7)
    )
    checkout_latitude = fields.Float(
        string='Shift End Latitude',
        digits=(10, 7)
    )
    checkout_longitude = fields.Float(
        string='Shift End Longitude',
        digits=(10, 7)
    )
    
    # Attendance (Multiple shift starts/ends allowed)
    attendance_ids = fields.One2many(
        'guard.attendance',
        'shift_id',
        string='Attendance Records',
        readonly=True
    )
    total_hours_worked = fields.Float(
        string='Total Hours Worked',
        compute='_compute_total_hours_worked',
        store=True,
        digits=(10, 2),
        help='Sum of all attendance hours for this shift'
    )
    remaining_hours = fields.Float(
        string='Remaining Hours',
        compute='_compute_remaining_hours',
        digits=(10, 2),
        help='Remaining time available for shift start based on shift duration'
    )
    attendance_count = fields.Integer(
        string='Shift Start Count',
        compute='_compute_attendance_count',
        store=True,
        help='Number of shift start/end pairs'
    )
    
    # Incidents
    incident_ids = fields.One2many(
        'incident.report',
        'shift_id',
        string='Incidents During Shift'
    )
    incident_count = fields.Integer(
        string='Incident Count',
        compute='_compute_incident_count',
        store=True
    )
    
    # Tour Logs
    tour_log_ids = fields.One2many(
        'tour.log',
        'shift_id',
        string='Tour Logs'
    )
    tours_completed = fields.Integer(
        string='Tours Completed',
        compute='_compute_tours_completed',
        store=True
    )
    
    # Supervisor
    supervisor_id = fields.Many2one(
        'res.users',
        string='Supervisor',
        ondelete='set null'
    )
    supervisor_notes = fields.Text(
        string='Supervisor Notes'
    )
    
    # Instructions
    instructions = fields.Text(
        string='Shift Instructions',
        help='Specific instructions for this shift'
    )
    briefing = fields.Html(
        string='Pre-Shift Briefing'
    )
    
    # Billing
    hourly_rate = fields.Float(
        string='Hourly Rate',
        digits=(10, 2)
    )
    total_cost = fields.Float(
        string='Total Cost',
        compute='_compute_total_cost',
        store=True
    )
    
    # Notes
    notes = fields.Text(
        string='Shift Notes'
    )
    
    # Security & Integrity Monitoring
    gps_spoofing_suspected = fields.Boolean(
        string='GPS Spoofing Suspected',
        default=False,
        help='Flagged if identical GPS coordinates detected across multiple check-ins'
    )
    attendance_pattern_suspicious = fields.Boolean(
        string='Suspicious Attendance Pattern',
        default=False,
        help='Flagged for unusual check-in/check-out patterns'
    )
    integrity_review_required = fields.Boolean(
        string='Integrity Review Required',
        compute='_compute_integrity_review',
        store=True
    )
    integrity_notes = fields.Text(
        string='Integrity Review Notes'
    )
    
    # Color for calendar view
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color'
    )

    @api.depends('guard_id', 'site_id', 'start_datetime')
    def _compute_name(self):
        """Generate shift name."""
        for record in self:
            if record.guard_id and record.site_id and record.start_datetime:
                start = fields.Datetime.from_string(record.start_datetime)
                record.name = '%s - %s (%s)' % (
                    record.guard_id.name,
                    record.site_id.name,
                    start.strftime('%Y-%m-%d %H:%M')
                )
            else:
                record.name = 'New Shift'

    @api.depends('start_datetime', 'end_datetime')
    def _compute_duration(self):
        """Calculate shift duration in hours."""
        for record in self:
            if record.start_datetime and record.end_datetime:
                delta = record.end_datetime - record.start_datetime
                record.duration = delta.total_seconds() / 3600.0
            else:
                record.duration = 0.0

    @api.depends('incident_ids')
    def _compute_incident_count(self):
        """Count incidents during shift."""
        for record in self:
            record.incident_count = len(record.incident_ids)

    @api.depends('tour_log_ids', 'tour_log_ids.status')
    def _compute_tours_completed(self):
        """Count completed tours."""
        for record in self:
            record.tours_completed = len(
                record.tour_log_ids.filtered(lambda t: t.status == 'completed')
            )

    @api.depends('duration', 'hourly_rate')
    def _compute_total_cost(self):
        """Calculate total shift cost."""
        for record in self:
            record.total_cost = record.duration * record.hourly_rate

    def _compute_color(self):
        """Set color based on shift status and conflicts."""
        color_map = {
            'scheduled': 3,    # Blue
            'confirmed': 7,    # Green
            'in_progress': 9,  # Orange
            'completed': 10,   # Green
            'cancelled': 1,    # Red
            'no_show': 2       # Red
        }
        for record in self:
            # Conflict takes priority in coloring
            if record.has_conflict and not record.conflict_override:
                if record.conflict_type == 'overlap':
                    record.color = 1  # Red - Critical conflict
                elif record.conflict_type == 'both':
                    record.color = 1  # Red - Critical conflict
                else:
                    record.color = 8  # Orange - Warning (rest period only)
            else:
                record.color = color_map.get(record.status, 0)

    @api.depends('attendance_ids', 'attendance_ids.hours_worked')
    def _compute_total_hours_worked(self):
        """Calculate total hours worked across all attendance records."""
        for record in self:
            record.total_hours_worked = sum(
                record.attendance_ids.mapped('hours_worked')
            )

    @api.depends('duration', 'total_hours_worked')
    def _compute_remaining_hours(self):
        """Calculate remaining hours available for check-in."""
        for record in self:
            record.remaining_hours = max(
                0.0,
                record.duration - record.total_hours_worked
            )

    @api.depends('attendance_ids')
    def _compute_attendance_count(self):
        """Count number of attendance records."""
        for record in self:
            record.attendance_count = len(record.attendance_ids)
    
    @api.depends('gps_spoofing_suspected', 'attendance_pattern_suspicious')
    def _compute_integrity_review(self):
        """Determine if shift needs integrity review."""
        for record in self:
            record.integrity_review_required = (
                record.gps_spoofing_suspected or 
                record.attendance_pattern_suspicious
            )

    @api.constrains('start_datetime', 'end_datetime', 'status')
    def _check_dates(self):
        """Validate shift dates."""
        for record in self:
            # Require dates to be set for non-scheduled shifts
            if record.status != 'scheduled' and (not record.start_datetime or not record.end_datetime):
                raise ValidationError(_(
                    'Start and End Date/Time are required!'
                ))
            
            # Skip further validation if dates are not set (e.g., during duplication)
            if not record.start_datetime or not record.end_datetime:
                continue
                
            if record.end_datetime <= record.start_datetime:
                raise ValidationError(_(
                    'End date/time must be after start date/time!'
                ))

    # Shift conflict detection fields
    has_conflict = fields.Boolean(
        string='Has Conflict',
        compute='_compute_has_conflict',
        store=True,
        help='Indicates if this shift has scheduling conflicts'
    )
    conflict_type = fields.Selection([
        ('overlap', 'Overlapping Shifts'),
        ('rest_period', 'Insufficient Rest Period'),
        ('both', 'Overlap and Rest Period')
    ], string='Conflict Type', compute='_compute_has_conflict', store=True)
    conflict_details = fields.Text(
        string='Conflict Details',
        compute='_compute_has_conflict',
        store=True
    )
    conflict_override = fields.Boolean(
        string='Conflict Override',
        default=False,
        help='Supervisor has approved this shift despite conflicts'
    )
    conflict_override_reason = fields.Text(
        string='Override Reason',
        help='Reason for overriding the conflict warning'
    )
    conflict_override_by = fields.Many2one(
        'res.users',
        string='Override Approved By',
        readonly=True
    )
    conflict_override_date = fields.Datetime(
        string='Override Date',
        readonly=True
    )
    
    @api.depends('guard_id', 'start_datetime', 'end_datetime', 'status')
    def _compute_has_conflict(self):
        """Detect shift conflicts including overlaps and rest period violations."""
        for record in self:
            if not record.start_datetime or not record.end_datetime or not record.guard_id:
                record.has_conflict = False
                record.conflict_type = False
                record.conflict_details = False
                continue
            
            if record.status in ['cancelled', 'no_show']:
                record.has_conflict = False
                record.conflict_type = False
                record.conflict_details = False
                continue
            
            conflicts = record._detect_shift_conflicts()
            
            if conflicts:
                record.has_conflict = True
                if conflicts['overlap'] and conflicts['rest_period']:
                    record.conflict_type = 'both'
                elif conflicts['overlap']:
                    record.conflict_type = 'overlap'
                else:
                    record.conflict_type = 'rest_period'
                record.conflict_details = conflicts['details']
            else:
                record.has_conflict = False
                record.conflict_type = False
                record.conflict_details = False
    
    def _detect_shift_conflicts(self):
        """
        Detect various types of shift conflicts.
        
        Returns:
            dict: Dictionary with conflict information
                {
                    'overlap': bool,
                    'rest_period': bool,
                    'details': str,
                    'conflicting_shifts': recordset
                }
        """
        self.ensure_one()
        
        if not self.guard_id or not self.start_datetime or not self.end_datetime:
            return {}
        
        # Get minimum rest period from config (default 8 hours)
        min_rest_hours = float(self.env['ir.config_parameter'].sudo().get_param(
            'guardpro.minimum_rest_period_hours', 8.0))
        
        min_rest_delta = timedelta(hours=min_rest_hours)
        
        # Find potentially conflicting shifts
        domain = [
            ('id', '!=', self.id),
            ('guard_id', '=', self.guard_id.id),
            ('status', 'not in', ['cancelled', 'no_show']),
            ('start_datetime', '!=', False),
            ('end_datetime', '!=', False),
        ]
        
        # Look for shifts within the conflict window
        # (current shift start - rest period) to (current shift end + rest period)
        start_check = self.start_datetime - min_rest_delta
        end_check = self.end_datetime + min_rest_delta
        
        domain.extend([
            '|',
            '&', ('start_datetime', '>=', start_check), ('start_datetime', '<', end_check),
            '&', ('end_datetime', '>', start_check), ('end_datetime', '<=', end_check)
        ])
        
        nearby_shifts = self.search(domain)
        
        has_overlap = False
        has_rest_violation = False
        details = []
        conflicting_shifts = self.env['guard.shift']
        
        for shift in nearby_shifts:
            # Check for direct overlap
            if (shift.start_datetime < self.end_datetime and 
                shift.end_datetime > self.start_datetime):
                has_overlap = True
                conflicting_shifts |= shift
                details.append(
                    _('⚠️ OVERLAP: Shift "%s" from %s to %s overlaps with this shift') % (
                        shift.name,
                        shift.start_datetime.strftime('%Y-%m-%d %H:%M'),
                        shift.end_datetime.strftime('%Y-%m-%d %H:%M')
                    )
                )
            
            # Check for insufficient rest period before this shift
            elif shift.end_datetime <= self.start_datetime:
                rest_period = self.start_datetime - shift.end_datetime
                if rest_period < min_rest_delta:
                    has_rest_violation = True
                    conflicting_shifts |= shift
                    hours_short = (min_rest_delta - rest_period).total_seconds() / 3600
                    details.append(
                        _('⚠️ REST PERIOD: Only %.1f hours between shift "%s" (ends %s) and this shift (starts %s). Minimum required: %.1f hours. Short by: %.1f hours') % (
                            rest_period.total_seconds() / 3600,
                            shift.name,
                            shift.end_datetime.strftime('%Y-%m-%d %H:%M'),
                            self.start_datetime.strftime('%Y-%m-%d %H:%M'),
                            min_rest_hours,
                            hours_short
                        )
                    )
            
            # Check for insufficient rest period after this shift
            elif shift.start_datetime >= self.end_datetime:
                rest_period = shift.start_datetime - self.end_datetime
                if rest_period < min_rest_delta:
                    has_rest_violation = True
                    conflicting_shifts |= shift
                    hours_short = (min_rest_delta - rest_period).total_seconds() / 3600
                    details.append(
                        _('⚠️ REST PERIOD: Only %.1f hours between this shift (ends %s) and shift "%s" (starts %s). Minimum required: %.1f hours. Short by: %.1f hours') % (
                            rest_period.total_seconds() / 3600,
                            self.end_datetime.strftime('%Y-%m-%d %H:%M'),
                            shift.name,
                            shift.start_datetime.strftime('%Y-%m-%d %H:%M'),
                            min_rest_hours,
                            hours_short
                        )
                    )
        
        if has_overlap or has_rest_violation:
            return {
                'overlap': has_overlap,
                'rest_period': has_rest_violation,
                'details': '\n'.join(details),
                'conflicting_shifts': conflicting_shifts
            }
        
        return {}
    
    @api.constrains('guard_id', 'start_datetime', 'end_datetime')
    def _check_overlapping_shifts(self):
        """Check for overlapping shifts for the same guard."""
        for record in self:
            # Skip validation if dates are not set (e.g., during duplication)
            if not record.start_datetime or not record.end_datetime:
                continue
            
            # Skip if conflict has been overridden by supervisor
            if record.conflict_override:
                continue
                
            if record.status not in ['cancelled', 'no_show']:
                conflicts = record._detect_shift_conflicts()
                
                if conflicts and conflicts.get('overlap'):
                    # Get supervisor group
                    supervisor_group = self.env.ref('guardpro.group_guardpro_supervisor', raise_if_not_found=False)
                    
                    # Check if current user is supervisor
                    if supervisor_group and self.env.user in supervisor_group.users:
                        # Supervisor can override - open wizard instead of blocking
                        # Return context flag to trigger wizard
                        return {
                            'type': 'ir.actions.act_window',
                            'res_model': 'guard.shift.conflict.wizard',
                            'view_mode': 'form',
                            'target': 'new',
                            'context': {
                                'default_shift_id': record.id,
                                'default_conflict_details': conflicts['details']
                            }
                        }
                    else:
                        # Non-supervisors cannot override overlaps
                        raise ValidationError(_(
                            'SHIFT OVERLAP DETECTED!\n\n'
                            'Guard %s already has a shift scheduled during this time.\n\n'
                            '%s\n\n'
                            'Please contact a supervisor to override this conflict.'
                        ) % (record.guard_id.name, conflicts['details']))
    
    @api.constrains('attendance_ids')
    def _check_attendance_integrity(self):
        """
        Detect suspicious attendance patterns (abuse prevention).
        Flags issues but doesn't block to avoid false positives.
        """
        for shift in self:
            if not shift.attendance_ids:
                continue
            
            completed_attendances = shift.attendance_ids.filtered(
                lambda a: a.status == 'checked_out'
            )
            
            if not completed_attendances:
                continue
            
            suspicious = False
            notes = []
            
            # Check 1: Excessive number of check-in/check-out cycles
            if len(completed_attendances) > 10:
                suspicious = True
                notes.append(
                    f'⚠️ Excessive check-in cycles: {len(completed_attendances)} cycles detected'
                )
            
            # Check 2: Multiple very short sessions (less than 6 minutes)
            short_sessions = completed_attendances.filtered(
                lambda a: a.hours_worked < 0.1
            )
            if len(short_sessions) > 5:
                suspicious = True
                notes.append(
                    f'⚠️ Multiple short sessions: {len(short_sessions)} sessions under 6 minutes'
                )
            
            # Check 3: Identical GPS coordinates across multiple check-ins
            if len(completed_attendances) >= 3:
                coords = []
                for attendance in completed_attendances:
                    if attendance.checkin_latitude and attendance.checkin_longitude:
                        # Round to 6 decimal places (~10cm precision)
                        coord = (
                            round(attendance.checkin_latitude, 6),
                            round(attendance.checkin_longitude, 6)
                        )
                        coords.append(coord)
                
                # If all coordinates are exactly the same
                if coords and len(set(coords)) == 1:
                    suspicious = True
                    shift.gps_spoofing_suspected = True
                    notes.append(
                        '🚨 GPS spoofing suspected: All check-ins from identical coordinates'
                    )
            
            # Flag the shift if suspicious patterns detected
            if suspicious:
                shift.write({
                    'attendance_pattern_suspicious': True,
                    'integrity_notes': '\n'.join(notes)
                })
                
                # Notify supervisor
                shift.message_post(
                    body='<br/>'.join(notes),
                    subject='⚠️ Attendance Integrity Alert',
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment'  # Shows prominently
                )
                
                _logger.warning(
                    'Suspicious attendance pattern detected for shift %s (Guard: %s): %s',
                    shift.name, shift.guard_id.name, '; '.join(notes)
                )

    def find_alternative_guards(self):
        """
        Find available alternative guards for this shift.
        
        Returns:
            recordset: Available guard.profile records
        """
        self.ensure_one()
        
        if not self.start_datetime or not self.end_datetime or not self.site_id:
            return self.env['guard.profile']
        
        # Get minimum rest period
        min_rest_hours = float(self.env['ir.config_parameter'].sudo().get_param(
            'guardpro.minimum_rest_period_hours', 8.0))
        min_rest_delta = timedelta(hours=min_rest_hours)
        
        # Find all active guards
        all_guards = self.env['guard.profile'].search([
            ('status', '=', 'active'),
            ('id', '!=', self.guard_id.id if self.guard_id else False)
        ])
        
        # Filter guards who are available (no conflicts)
        available_guards = self.env['guard.profile']
        
        for guard in all_guards:
            # Check for overlapping shifts
            conflicting_shifts = self.search([
                ('guard_id', '=', guard.id),
                ('status', 'not in', ['cancelled', 'no_show']),
                ('start_datetime', '!=', False),
                ('end_datetime', '!=', False),
                '|',
                # Direct overlap
                '&',
                ('start_datetime', '<', self.end_datetime),
                ('end_datetime', '>', self.start_datetime),
                # Rest period violation
                '|',
                '&',
                ('end_datetime', '>', self.start_datetime - min_rest_delta),
                ('end_datetime', '<=', self.start_datetime),
                '&',
                ('start_datetime', '<', self.end_datetime + min_rest_delta),
                ('start_datetime', '>=', self.end_datetime)
            ])
            
            if not conflicting_shifts:
                available_guards |= guard
        
        # Sort by preference: same site experience, certifications, etc.
        # Guards who have worked at this site before get priority
        site_experienced = available_guards.filtered(
            lambda g: self.site_id.id in g.assigned_site_ids.ids
        )
        other_guards = available_guards - site_experienced
        
        return site_experienced + other_guards
    
    def action_open_conflict_wizard(self):
        """Open conflict resolution wizard."""
        self.ensure_one()
        
        conflicts = self._detect_shift_conflicts()
        
        return {
            'name': _('Shift Conflict Warning'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.shift.conflict.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_shift_id': self.id,
                'default_conflict_details': conflicts.get('details', '') if conflicts else '',
                'default_has_overlap': conflicts.get('overlap', False) if conflicts else False,
                'default_has_rest_violation': conflicts.get('rest_period', False) if conflicts else False
            }
        }
    
    def action_override_conflict(self, reason):
        """
        Override a shift conflict (supervisor only).
        
        Args:
            reason (str): Reason for overriding the conflict
        """
        self.ensure_one()
        
        # Check supervisor permission
        supervisor_group = self.env.ref('guardpro.group_guardpro_supervisor', raise_if_not_found=False)
        if not supervisor_group or self.env.user not in supervisor_group.users:
            raise ValidationError(_('Only supervisors can override shift conflicts.'))
        
        self.write({
            'conflict_override': True,
            'conflict_override_reason': reason,
            'conflict_override_by': self.env.user.id,
            'conflict_override_date': fields.Datetime.now()
        })
        
        # Log the override
        self.message_post(
            body=Markup(
                '<p><strong>Shift Conflict Override</strong></p>'
                '<p>Supervisor %s has approved this shift despite scheduling conflicts.</p>'
                '<p><strong>Reason:</strong> %s</p>'
                '<p><strong>Conflicts:</strong></p><pre>%s</pre>'
            ) % (self.env.user.name, reason or _('No reason provided'), self.conflict_details or ''),
            subject=_('Shift Conflict Override'),
            message_type='notification',
            subtype_xmlid='mail.mt_comment'
        )
        
        return True
    
    def action_confirm(self):
        """Confirm the shift."""
        # Check for conflicts before confirming
        for record in self:
            if record.has_conflict and not record.conflict_override:
                # Open conflict wizard instead of just confirming
                return record.action_open_conflict_wizard()

        self.write({'status': 'confirmed'})
        for shift in self:
            shift._push_shift_mobile_notification(
                kind='shift_assigned',
                title=_('Shift confirmed'),
                body_extra=_('Your shift has been confirmed.'),
                priority='high',
            )

    def action_cancel(self):
        """Cancel the shift."""
        self.write({'status': 'cancelled'})

        # Fire the mobile notification to the assigned guard.
        self._send_shift_change_email()

    @api.model_create_multi
    def create(self, vals_list):
        """Ping the assigned guard when a new shift is scheduled for them."""
        records = super().create(vals_list)
        for record in records:
            if record.guard_id and record.guard_id.user_id:
                record._push_shift_mobile_notification(
                    kind='shift_assigned',
                    title=_('New shift assigned'),
                    priority='high',
                )
        return records

    def write(self, vals):
        """Detect shift reassignment or schedule changes and notify the
        guards involved."""
        trigger_fields = {
            'guard_id', 'start_datetime', 'end_datetime', 'site_id', 'status',
        }
        before = {}
        if trigger_fields & set(vals.keys()):
            for rec in self:
                before[rec.id] = {
                    'guard_id': rec.guard_id.id,
                    'start_datetime': rec.start_datetime,
                    'end_datetime': rec.end_datetime,
                    'site_id': rec.site_id.id,
                    'status': rec.status,
                }

        result = super().write(vals)

        for rec in self:
            prev = before.get(rec.id)
            if not prev:
                continue
            # Reassigned: notify new guard AND old guard (if different).
            if 'guard_id' in vals and prev['guard_id'] != rec.guard_id.id:
                if rec.guard_id and rec.guard_id.user_id:
                    rec._push_shift_mobile_notification(
                        kind='shift_assigned',
                        title=_('Shift reassigned to you'),
                        priority='high',
                    )
                # Tell the previous guard the shift was taken off them.
                if prev['guard_id']:
                    prev_user = self.env['guard.profile'].sudo().browse(
                        prev['guard_id']
                    ).user_id
                    if prev_user:
                        self.env['guardpro.mobile.outbox'].sudo().push(
                            user=prev_user,
                            kind='shift_changed',
                            title=_('Shift reassigned to another guard'),
                            body=_('Shift on %s at %s is no longer yours.') % (
                                rec.start_datetime or '-',
                                rec.site_id.name if rec.site_id else '-',
                            ),
                            priority='normal',
                            res_model='guard.shift',
                            res_id=rec.id,
                            dedup_key='shift_unassigned:%s:%s' % (rec.id, prev['guard_id']),
                        )
                continue
            # Time or site changed on the same guard.
            schedule_changed = (
                prev['start_datetime'] != rec.start_datetime
                or prev['end_datetime'] != rec.end_datetime
                or prev['site_id'] != (rec.site_id.id if rec.site_id else False)
            )
            if schedule_changed and rec.guard_id and rec.guard_id.user_id:
                rec._push_shift_mobile_notification(
                    kind='shift_changed',
                    title=_('Shift updated'),
                    priority='normal',
                )
        return result

    def _push_shift_mobile_notification(self, kind, title, body_extra=None,
                                        priority='normal'):
        """Shared helper used by create/write/action_confirm/action_cancel."""
        self.ensure_one()
        if not self.guard_id or not self.guard_id.user_id:
            return
        body_parts = []
        if self.site_id:
            body_parts.append(_('Site: %s') % self.site_id.name)
        if self.start_datetime:
            body_parts.append(_('Start: %s') % self.start_datetime)
        if self.end_datetime:
            body_parts.append(_('End: %s') % self.end_datetime)
        if body_extra:
            body_parts.append(body_extra)
        self.env['guardpro.mobile.outbox'].sudo().push(
            user=self.guard_id.user_id,
            kind=kind,
            title=title,
            body='\n'.join(body_parts),
            priority=priority,
            res_model='guard.shift',
            res_id=self.id,
            deep_link='/guardpro/mobile/shifts',
            dedup_key='shift:%s:%s' % (self.id, kind),
        )

    def _send_shift_change_email(self):
        """Fire a mobile outbox notification about the shift change."""
        for shift in self:
            if not shift.guard_id or not shift.guard_id.user_id:
                continue
            kind = 'shift_cancelled' if shift.status == 'cancelled' else 'shift_changed'
            title = _('Shift cancelled') if kind == 'shift_cancelled' else _('Shift updated')
            shift._push_shift_mobile_notification(
                kind=kind,
                title=title,
                priority='high' if kind == 'shift_cancelled' else 'normal',
            )

    def action_checkin(self, latitude=None, longitude=None, checkpoint_scan_id=None, photo=None,
                      biometric_type=None, biometric_data=None, device_id=None):
        """
        Start shift for guard.
        Supports multiple shift starts during a shift.
        
        Args:
            latitude (float): Shift start GPS latitude
            longitude (float): Shift start GPS longitude
            checkpoint_scan_id (int): Optional checkpoint scan ID for physical verification
            photo (binary): Optional photo for verification
        """
        self.ensure_one()
        
        # Check if guard already has an active shift started (not ended)
        active_attendance = self.attendance_ids.filtered(
            lambda a: a.status == 'checked_in'
        )
        if active_attendance:
            raise ValidationError(_(
                'Your shift has already started! Please end your shift first before starting it again.'
            ))
        
        # Check if shift is already completed
        if self.status == 'completed':
            raise ValidationError(_(
                'This shift is already completed. Cannot start shift.'
            ))
        
        # Check if there's remaining time
        if self.remaining_hours <= 0:
            raise ValidationError(_(
                'Shift duration limit reached! Total hours worked: %.2f hours. '
                'Shift duration: %.2f hours.'
            ) % (self.total_hours_worked, self.duration))
        
        now = fields.Datetime.now()
        
        # BIOMETRIC VERIFICATION (if required and provided)
        if biometric_type and biometric_data:
            # Verify biometric
            processor = self.env['guard.biometric.processor']
            verification_result = processor.verify_biometric(
                guard_id=self.guard_id.id,
                biometric_type=biometric_type,
                captured_data=biometric_data,
                verification_purpose='checkin',
                device_id=device_id,
                device_type='mobile',
                latitude=latitude,
                longitude=longitude,
                shift_id=self.id
            )
            
            if not verification_result.get('verified'):
                raise ValidationError(_(
                    'Biometric verification failed! '
                    'Confidence: %.1f%%. Please try again.'
                ) % (verification_result.get('confidence', 0) * 100))
        
        # SECURITY: Physical verification requirement (GPS spoofing prevention)
        if self.site_id.require_physical_verification:
            verification_passed = False
            verification_method = self.site_id.verification_method
            
            if verification_method == 'nfc' and checkpoint_scan_id:
                # Verify NFC scan
                scan = self.env['checkpoint.scan'].browse(checkpoint_scan_id)
                if scan.exists() and scan.scan_type == 'nfc' and scan.status == 'verified':
                    verification_passed = True
            elif verification_method == 'qr' and checkpoint_scan_id:
                # Verify QR scan
                scan = self.env['checkpoint.scan'].browse(checkpoint_scan_id)
                if scan.exists() and scan.scan_type == 'qr' and scan.status == 'verified':
                    verification_passed = True
            elif verification_method == 'nfc_or_qr' and checkpoint_scan_id:
                # Verify either NFC or QR
                scan = self.env['checkpoint.scan'].browse(checkpoint_scan_id)
                if scan.exists() and scan.scan_type in ['nfc', 'qr'] and scan.status == 'verified':
                    verification_passed = True
            elif verification_method == 'photo' and photo:
                verification_passed = True
            elif verification_method == 'any' and (checkpoint_scan_id or photo):
                verification_passed = True
            
            if not verification_passed:
                method_text = {
                    'nfc': 'NFC tag scan',
                    'qr': 'QR code scan',
                    'nfc_or_qr': 'NFC or QR code scan',
                    'photo': 'photo at site entrance',
                    'any': 'physical verification (NFC/QR/photo)'
                }.get(verification_method, 'physical verification')
                
                raise ValidationError(_(
                    'Physical verification required!\n\n'
                    'This site requires %s to start shift to prevent GPS spoofing.\n\n'
                    'Please scan the NFC tag or QR code at the site entrance.'
                ) % method_text)
        
        # Verify geofence if enabled
        if self.site_id.geofence_enabled:
            if not (latitude and longitude):
                raise ValidationError(_(
                    'GPS coordinates required to start shift at this site!'
                ))
            if not self.site_id.check_guard_in_geofence(latitude, longitude):
                raise ValidationError(_(
                    'You are not within the site geofence!'
                ))
        
        # Update shift status on first shift start
        if not self.attendance_ids:
            self.write({
                'status': 'in_progress',
                'checkin_time': now,
                'checkin_latitude': latitude,
                'checkin_longitude': longitude
            })
        
        # Create new attendance record
        attendance = self.env['guard.attendance'].create({
            'guard_id': self.guard_id.id,
            'site_id': self.site_id.id,
            'shift_id': self.id,
            'checkin_time': now,
            'checkin_latitude': latitude,
            'checkin_longitude': longitude
        })
        
        return {
            'success': True,
            'message': _('Shift started successfully! (Start #%d)') % len(self.attendance_ids),
            'attendance_id': attendance.id,
            'remaining_hours': self.remaining_hours
        }

    def action_checkout(self, latitude=None, longitude=None, complete_shift=False,
                       biometric_type=None, biometric_data=None, device_id=None):
        """
        End shift for guard.
        Supports multiple shift ends during a shift.
        
        Args:
            latitude (float): Shift end GPS latitude
            longitude (float): Shift end GPS longitude
            complete_shift (bool): If True, mark shift as completed (final end)
        """
        self.ensure_one()
        
        # Find the active (started but not ended) attendance record
        active_attendance = self.attendance_ids.filtered(
            lambda a: a.status == 'checked_in'
        )
        
        if not active_attendance:
            raise ValidationError(_(
                'No active shift found! Please start your shift first before ending it.'
            ))
        
        if len(active_attendance) > 1:
            # This shouldn't happen, but take the most recent one
            active_attendance = active_attendance.sorted('checkin_time', reverse=True)[0]
        else:
            active_attendance = active_attendance[0]
        
        now = fields.Datetime.now()
        
        # BIOMETRIC VERIFICATION (if required and provided)
        if biometric_type and biometric_data:
            # Verify biometric
            processor = self.env['guard.biometric.processor']
            verification_result = processor.verify_biometric(
                guard_id=self.guard_id.id,
                biometric_type=biometric_type,
                captured_data=biometric_data,
                verification_purpose='checkout',
                device_id=device_id,
                device_type='mobile',
                latitude=latitude,
                longitude=longitude,
                shift_id=self.id
            )
            
            if not verification_result.get('verified'):
                raise ValidationError(_(
                    'Biometric verification failed! '
                    'Confidence: %.1f%%. Please try again.'
                ) % (verification_result.get('confidence', 0) * 100))
        
        # Verify geofence if enabled
        if self.site_id.geofence_enabled:
            if not (latitude and longitude):
                raise ValidationError(_(
                    'GPS coordinates required to end shift at this site!'
                ))
            if not self.site_id.check_guard_in_geofence(latitude, longitude):
                raise ValidationError(_(
                    'You are not within the site geofence!'
                ))
        
        # Calculate hours for this shift end
        delta = now - active_attendance.checkin_time
        checkout_hours = delta.total_seconds() / 3600.0
        
        # Check if this shift end would exceed shift duration
        total_after_checkout = self.total_hours_worked + checkout_hours
        if total_after_checkout > self.duration:
            # Allow end but cap at shift duration
            exceeded_hours = total_after_checkout - self.duration
            raise ValidationError(_(
                'Ending shift would exceed shift duration!\n'
                'Shift duration: %.2f hours\n'
                'Already worked: %.2f hours\n'
                'This session: %.2f hours\n'
                'Total would be: %.2f hours (exceeds by %.2f hours)\n\n'
                'Please end shift earlier or contact your supervisor.'
            ) % (
                self.duration,
                self.total_hours_worked,
                checkout_hours,
                total_after_checkout,
                exceeded_hours
            ))
        
        # Update the active attendance record
        active_attendance.write({
            'checkout_time': now,
            'checkout_latitude': latitude,
            'checkout_longitude': longitude
        })
        
        # Update shift end time (last end)
        self.write({
            'checkout_time': now,
            'checkout_latitude': latitude,
            'checkout_longitude': longitude
        })
        
        # Complete shift if requested or if no time remaining
        if complete_shift or self.remaining_hours <= 0.01:  # 0.01 hour = 36 seconds tolerance
            self.write({'status': 'completed'})
            message = _('Shift ended successfully! Shift completed.')
        else:
            message = _(
                'Shift ended successfully! Remaining time: %.2f hours. '
                'You can start your shift again if needed.'
            ) % self.remaining_hours
        
        return {
            'success': True,
            'message': message,
            'hours_worked': checkout_hours,
            'total_hours': self.total_hours_worked,
            'remaining_hours': self.remaining_hours,
            'shift_completed': self.status == 'completed'
        }

    def action_view_attendance(self):
        """Open attendance records for this shift."""
        self.ensure_one()
        return {
            'name': _('Attendance Records - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.attendance',
            'view_mode': 'list,form',
            'domain': [('shift_id', '=', self.id)],
            'context': {
                'default_shift_id': self.id,
                'default_guard_id': self.guard_id.id,
                'default_site_id': self.site_id.id
            }
        }

    def action_view_incidents(self):
        """Open incidents from this shift."""
        self.ensure_one()
        return {
            'name': _('Incidents - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'incident.report',
            'view_mode': 'list,form',
            'domain': [('shift_id', '=', self.id)],
            'context': {'default_shift_id': self.id}
        }

    def copy(self, default=None):
        """
        Override copy method to create duplicate with empty start/end times.
        This prevents validation errors for overlapping shifts.
        """
        if default is None:
            default = {}
        
        # Clear start and end times to avoid overlap validation
        default.update({
            'start_datetime': False,
            'end_datetime': False,
            'status': 'scheduled',
            'checkin_time': False,
            'checkout_time': False,
            'checkin_latitude': False,
            'checkin_longitude': False,
            'checkout_latitude': False,
            'checkout_longitude': False,
            'reminder_sent': False,
            'gps_spoofing_suspected': False,
            'attendance_pattern_suspicious': False,
            'integrity_notes': False,
        })
        
        return super(GuardShift, self).copy(default)

    # ====================================================
    # SCHEDULED ACTIONS (CRON JOBS)
    # ====================================================
    
    @api.model
    def send_shift_reminders(self):
        """Send notifications to guards 30 minutes before shift.
        
        Called by scheduled action every 30 minutes.
        """
        from datetime import datetime, timedelta
        
        # Get reminder time from system parameters
        reminder_minutes = int(self.env['ir.config_parameter'].sudo().get_param(
            'guardpro.shift_reminder_minutes', 30))
        
        now = fields.Datetime.now()
        start_time = now + timedelta(minutes=reminder_minutes - 5)
        end_time = now + timedelta(minutes=reminder_minutes + 5)
        
        # Find upcoming shifts that need reminders
        shifts = self.search([
            ('start_datetime', '>=', start_time),
            ('start_datetime', '<=', end_time),
            ('status', '=', 'scheduled'),
            ('reminder_sent', '=', False)
        ])
        
        _logger.info('Sending shift reminders for %d shifts', len(shifts))
        
        for shift in shifts:
            try:
                # Send notification
                shift.message_post(
                    body=Markup(
                        "<p><strong>Shift Reminder</strong></p>"
                        "<p>Your shift starts in %d minutes at <strong>%s</strong>.</p>"
                        "<ul>"
                        "<li>Site: %s</li>"
                        "<li>Start: %s</li>"
                        "<li>End: %s</li>"
                        "<li>Duration: %.1f hours</li>"
                        "</ul>"
                        "<p>Please arrive on time and be prepared.</p>"
                    ) % (
                        reminder_minutes,
                        shift.site_id.name,
                        shift.site_id.name,
                        shift.start_datetime,
                        shift.end_datetime,
                        shift.duration
                    ),
                    partner_ids=shift.guard_id.user_id.partner_id.ids,
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment'
                )
                
                # Mark reminder as sent
                shift.reminder_sent = True
                
                _logger.debug('Shift reminder sent for shift %s to guard %s', 
                            shift.name, shift.guard_id.name)
                            
            except Exception as e:
                _logger.error('Error sending shift reminder for shift %s: %s', 
                            shift.id, str(e))
        
        return True
    
    @api.model
    def check_missed_checkins(self):
        """Alert supervisors about guards who haven't started their shift.
        
        Called by scheduled action every 15 minutes.
        """
        from datetime import datetime, timedelta
        
        now = fields.Datetime.now()
        grace_period = timedelta(minutes=15)
        
        # Find shifts that should have started but no shift start
        missed_shifts = self.search([
            ('start_datetime', '<', now - grace_period),
            ('start_datetime', '>', now - timedelta(hours=4)),
            ('status', '=', 'scheduled'),
            ('attendance_count', '=', 0)
        ])
        
        if missed_shifts:
            _logger.warning('Found %d shifts with missed shift starts', len(missed_shifts))
        
        for shift in missed_shifts:
            try:
                # Create activity for supervisor
                shift.activity_schedule(
                    'mail.mail_activity_data_urgent',
                    summary=_('Missed Shift Start'),
                    note=_(
                        'Guard %s has not started their shift at %s. '
                        'Shift was scheduled to start at %s.'
                    ) % (shift.guard_id.name, shift.site_id.name, shift.start_datetime),
                    user_id=(
                        shift.site_id.manager_id.user_ids[:1].id
                        if shift.site_id.manager_id and shift.site_id.manager_id.user_ids
                        else self.env.user.id
                    )
                )
                
                # Update shift status
                shift.status = 'no_show'
                
                _logger.info('Created alert for missed shift start: shift %s, guard %s',
                           shift.id, shift.guard_id.name)
                           
            except Exception as e:
                _logger.error('Error processing missed shift start for shift %s: %s',
                            shift.id, str(e))
        
        return True
    
    def init(self):
        """Create database indexes for performance optimization."""
        # Composite index for guard schedule queries
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS guard_shift_guard_date_idx 
            ON guard_shift (guard_id, start_datetime DESC, status);
        """)
        
        # Index for site-based shift queries
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS guard_shift_site_date_idx 
            ON guard_shift (site_id, start_datetime DESC, status);
        """)
        
        # Index for upcoming shifts
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS guard_shift_upcoming_idx 
            ON guard_shift (start_datetime, status) 
            WHERE status IN ('scheduled', 'confirmed');
        """)
        
        # Index for shift status monitoring
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS guard_shift_status_date_idx 
            ON guard_shift (status, start_datetime DESC);
        """)
        
        # Index for template-based shifts
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS guard_shift_template_idx 
            ON guard_shift (template_id, start_datetime DESC) 
            WHERE template_id IS NOT NULL;
        """)


