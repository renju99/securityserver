# -*- coding: utf-8 -*-
"""Incident Report Model."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup
import logging
import base64
from datetime import timedelta

_logger = logging.getLogger(__name__)


class IncidentReport(models.Model):
    """Incident Reporting and Management."""

    _name = 'incident.report'
    _description = 'Incident Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'incident_datetime desc'

    # Basic Information
    name = fields.Char(
        string='Incident Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True
    )
    # Incidents are legal-audit records. A deleted guard/site/shift must
    # NOT vaporise the incident history: SET NULL the guard/shift so we
    # keep the body of the report, and RESTRICT on the (required) site
    # so a site with open incidents cannot be deleted silently.
    guard_id = fields.Many2one(
        'guard.profile',
        string='Reporting Guard',
        required=False,
        tracking=True,
        index=True,
        ondelete='set null',
        help='Guard who reported the incident (if applicable)'
    )
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True,
        tracking=True,
        index=True,
        ondelete='restrict'
    )
    zone_id = fields.Many2one(
        'site.zone',
        string='Zone',
        domain="[('site_id', '=', site_id)]",
        ondelete='set null',
        tracking=True,
        index=True,
        help='Operational zone for access control and reporting',
    )
    shift_id = fields.Many2one(
        'guard.shift',
        string='Related Shift',
        tracking=True,
        ondelete='set null'
    )
    
    # Incident Details
    incident_datetime = fields.Datetime(
        string='Incident Date/Time',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True
    )
    reported_datetime = fields.Datetime(
        string='Reported Date/Time',
        default=fields.Datetime.now,
        readonly=True
    )
    
    # Category
    category_id = fields.Many2one(
        'incident.category',
        string='Category',
        required=True,
        tracking=True,
        ondelete='restrict'
    )
    form_parent_id = fields.Many2one(
        'incident.form.parent',
        string='Parent Category',
        tracking=True,
        help='Excel-aligned parent form category (Parent Category → Form Section → Field).',
    )
    form_value_ids = fields.One2many(
        'incident.form.value', 'incident_id', string='Form Field Values',
    )
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Severity', default='medium', required=True, tracking=True, index=True)
    
    # Location
    checkpoint_id = fields.Many2one(
        'checkpoint',
        string='Selected Location',
        help='Select a predefined location at the site'
    )
    location = fields.Char(
        string='Location Details',
        help='Specific location within site or additional details'
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
    
    # Description
    title = fields.Char(
        string='Incident Title',
        required=True,
        tracking=True
    )
    description = fields.Html(
        string='Detailed Description',
        required=True
    )
    
    # People Involved
    persons_involved = fields.Text(
        string='Persons Involved',
        help='Names and descriptions of people involved'
    )
    witnesses = fields.Text(
        string='Witnesses',
        help='Names and contact info of witnesses'
    )
    involved_community = fields.Char(
        string='Community',
        help='Community of the involved person (e.g. residential community name)'
    )
    involved_unit_number = fields.Char(
        string='Unit Number',
        help='Unit / villa / apartment number of the involved person'
    )
    involved_parking_slot = fields.Char(
        string='Parking Slot Number',
        help='Parking slot number (for parking violations)'
    )
    
    # Actions Taken
    immediate_actions = fields.Text(
        string='Immediate Actions Taken'
    )
    
    # Emergency Services
    police_notified = fields.Boolean(
        string='Police Notified',
        default=False
    )
    police_report_number = fields.Char(
        string='Police Report Number'
    )
    medical_required = fields.Boolean(
        string='Medical Assistance Required',
        default=False
    )
    ambulance_called = fields.Boolean(
        string='Ambulance Called',
        default=False
    )
    fire_department = fields.Boolean(
        string='Fire Department Notified',
        default=False
    )
    
    # Injuries/Damage
    injuries = fields.Boolean(
        string='Injuries Occurred',
        default=False
    )
    injury_details = fields.Text(
        string='Injury Details'
    )
    property_damage = fields.Boolean(
        string='Property Damage',
        default=False
    )
    damage_details = fields.Text(
        string='Damage Details'
    )
    estimated_cost = fields.Float(
        string='Estimated Cost',
        digits=(10, 2)
    )
    
    # Media
    photo_ids = fields.Many2many(
        'ir.attachment',
        'incident_photo_rel',
        'incident_id',
        'attachment_id',
        string='Photos'
    )
    video_ids = fields.Many2many(
        'ir.attachment',
        'incident_video_rel',
        'incident_id',
        'attachment_id',
        string='Videos'
    )
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ], string='Status', default='draft', required=True, tracking=True)
    
    escalated = fields.Boolean(
        string='Escalated',
        default=False,
        help='Indicates if this incident has been escalated to management',
        tracking=True
    )
    
    # ============================================================
    # SLA TRACKING FIELDS
    # ============================================================
    
    # SLA Policy
    sla_policy_id = fields.Many2one(
        'incident.sla.policy',
        string='SLA Policy',
        compute='_compute_sla_policy',
        store=True,
        help='Applicable SLA policy for this incident'
    )
    
    # SLA Deadlines
    sla_response_deadline = fields.Datetime(
        string='Response Deadline',
        compute='_compute_sla_deadlines',
        store=True,
        help='SLA deadline for first response'
    )
    sla_resolution_deadline = fields.Datetime(
        string='Resolution Deadline',
        compute='_compute_sla_deadlines',
        store=True,
        help='SLA deadline for resolution'
    )
    
    # Time Tracking
    response_time_minutes = fields.Float(
        string='Response Time (minutes)',
        compute='_compute_response_time',
        store=True,
        help='Time taken to first respond to incident'
    )
    resolution_time_hours = fields.Float(
        string='Resolution Time (hours)',
        compute='_compute_resolution_time',
        store=True,
        help='Time taken to resolve incident'
    )
    
    # SLA Status
    sla_status = fields.Selection([
        ('on_track', 'On Track'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('breached', 'Breached')
    ], string='SLA Status', compute='_compute_sla_status', store=True, index=True)
    
    sla_breach = fields.Boolean(
        string='SLA Breached',
        compute='_compute_sla_status',
        store=True,
        index=True,
        help='Indicates if SLA has been breached'
    )
    
    sla_breach_time = fields.Float(
        string='SLA Breach Time (minutes)',
        help='How much the SLA was breached by'
    )
    
    # Time Progress
    time_to_response_deadline = fields.Float(
        string='Time to Response Deadline (minutes)',
        compute='_compute_time_to_deadlines',
        help='Minutes remaining until response deadline'
    )
    time_to_resolution_deadline = fields.Float(
        string='Time to Resolution Deadline (hours)',
        compute='_compute_time_to_deadlines',
        help='Hours remaining until resolution deadline'
    )
    
    response_sla_percentage = fields.Float(
        string='Response SLA Progress (%)',
        compute='_compute_sla_percentage',
        help='Percentage of response SLA time elapsed'
    )
    
    # Escalation Tracking
    escalation_count = fields.Integer(
        string='Escalation Count',
        compute='_compute_escalation_stats',
        help='Number of times this incident has been escalated'
    )
    escalation_level = fields.Integer(
        string='Current Escalation Level',
        compute='_compute_escalation_stats',
        help='Current escalation level'
    )
    escalation_log_ids = fields.One2many(
        'incident.escalation.log',
        'incident_id',
        string='Escalation History'
    )
    
    # First Response Tracking
    first_response_datetime = fields.Datetime(
        string='First Response Time',
        help='When incident was first responded to'
    )
    responded_by = fields.Many2one(
        'res.users',
        string='Responded By',
        help='User who first responded'
    )
    
    # ============================================================
    # INVESTIGATION TRACKING
    # ============================================================
    
    investigation_id = fields.Many2one(
        'incident.investigation',
        string='Investigation',
        help='Related formal investigation'
    )
    investigation_required = fields.Boolean(
        string='Investigation Required',
        default=False,
        tracking=True,
        help='Does this incident require formal investigation?'
    )
    investigation_status = fields.Selection(
        related='investigation_id.status',
        string='Investigation Status',
        store=True
    )
    
    # Review
    reviewed_by = fields.Many2one(
        'res.users',
        string='Reviewed By',
        tracking=True
    )
    review_datetime = fields.Datetime(
        string='Review Date/Time'
    )
    review_notes = fields.Text(
        string='Review Notes'
    )
    
    # Follow-up
    requires_followup = fields.Boolean(
        string='Requires Follow-up',
        default=False
    )
    followup_notes = fields.Text(
        string='Follow-up Notes'
    )
    followup_completed = fields.Boolean(
        string='Follow-up Completed',
        default=False
    )
    
    # Client Notification
    client_notified = fields.Boolean(
        string='Client Notified',
        default=False
    )
    client_notification_datetime = fields.Datetime(
        string='Client Notification Time'
    )
    
    # Priority
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Priority', default='0', index=True)
    
    # Tags
    tag_ids = fields.Many2many(
        'incident.tag',
        'incident_report_tag_rel',
        'incident_id',
        'tag_id',
        string='Tags'
    )
    
    # Notes
    notes = fields.Text(
        string='Additional Notes'
    )
    
    # Color for kanban view
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color'
    )
    
    # Computed fields for dynamic form behavior
    is_medical_incident = fields.Boolean(
        compute='_compute_incident_type',
        string='Is Medical Incident'
    )
    is_fire_incident = fields.Boolean(
        compute='_compute_incident_type',
        string='Is Fire Incident'
    )
    is_security_incident = fields.Boolean(
        compute='_compute_incident_type',
        string='Is Security Incident'
    )
    is_vehicle_incident = fields.Boolean(
        compute='_compute_incident_type',
        string='Is Vehicle Incident'
    )
    is_safety_incident = fields.Boolean(
        compute='_compute_incident_type',
        string='Is Safety Incident'
    )
    is_statement_incident = fields.Boolean(
        compute='_compute_incident_type',
        string='Is Statement Incident'
    )
    is_fire_emergency_incident = fields.Boolean(
        compute='_compute_incident_type',
        string='Is Fire Alarm Emergency Incident'
    )
    is_found_item_incident = fields.Boolean(
        compute='_compute_incident_type',
        string='Is Found Item Incident'
    )
    is_return_form_incident = fields.Boolean(
        compute='_compute_incident_type',
        string='Is Return Form Incident'
    )
    is_community_violation_incident = fields.Boolean(
        compute='_compute_incident_type',
        string='Is Community Violation Incident'
    )
    is_facility_incident = fields.Boolean(
        string='Is Facility Patrol Issue',
        compute='_compute_incident_type',
        store=False,
    )
    is_door_lock_incident = fields.Boolean(
        compute='_compute_incident_type',
        string='Is Door Lock Incident'
    )

    # Statement Form Specific Fields
    statement_person_name = fields.Char(string='Full Name (Person Writing Statement)')
    statement_person_mobile = fields.Char(string='Mobile Number')
    statement_person_email = fields.Char(string='Email Address')
    statement_person_nationality = fields.Char(string='Nationality')
    statement_person_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender')
    statement_person_eid_number = fields.Char(string='EID Number')
    statement_person_eid_expiry = fields.Date(string='EID Expiry Date')
    statement_person_eid_front = fields.Image(string='EID Front')
    statement_person_eid_back = fields.Image(string='EID Back')
    statement_person_company = fields.Char(string='Company')
    statement_person_department = fields.Char(string='Department')
    statement_person_designation = fields.Char(string='Designation')
    statement_text = fields.Html(string='Statement Content')
    statement_person_signature = fields.Binary(string='Person Signature')
    security_officer_signature = fields.Binary(string='Security Officer Signature')
    
    # Fire Alarm Emergency Specific Fields
    fire_emergency_type = fields.Selection([
        ('fire_alarm', 'Fire Alarm'),
        ('smoke', 'Smoke'),
        ('emergency', 'Other Emergency')
    ], string='Type of Emergency')
    fire_alarm_specification = fields.Char(string='If your previous selection was related to an alarm, please specify?')
    fire_alarm_status = fields.Char(string='Alarm status')
    fire_law_enforcement_notified = fields.Selection([('YES', 'YES'), ('NO', 'NO')], string='Law Enforcement Notified', default='NO')
    fire_law_enforcement_details = fields.Text(string='Law enforcement arrival/departure time and plate number')
    
    fire_cctv_reviewed = fields.Selection([('YES', 'YES'), ('NO', 'NO')], string='CCTV Footage Review', default='NO')
    fire_cctv_reviewer_name = fields.Char(string='If your answer was yes to the CCTV footage review, kindly type the name of the person who reviewed the CCTV.')
    fire_cctv_reviewer_mobile = fields.Char(string='Reviewer Mobile Number')
    fire_cctv_handover = fields.Selection([('YES', 'YES'), ('NO', 'NO')], string='CCTV Footage handover', default='NO')
    fire_cctv_police_officer_name = fields.Char(string='Police officer name')
    fire_cctv_police_officer_mobile = fields.Char(string='Police officer mobile No.')
    
    fire_activation_time = fields.Char(string='Fire Alarm Activation Time')
    fire_reset_time = fields.Char(string='Reset Time')
    fire_sounder_status = fields.Char(string='Sounder')

    # Found Item Form Specific Fields
    found_item_time = fields.Char(string='When the Item is Found (Time)')
    found_item_date = fields.Date(string='When the Item is Found (Date)')
    found_person_name = fields.Char(string='Name of Person Who Found the Item')
    found_person_home_address = fields.Char(string='Finder Home Address')
    found_person_mobile = fields.Char(string='Finder Mobile Number')
    found_person_email = fields.Char(string='Finder Email Address')
    found_item_category = fields.Char(string='Category of Found Item')
    found_item_description = fields.Html(
        string='Item(s) Found - Full Description'
    )
    found_item_inspected = fields.Selection(
        [('yes', 'Yes'), ('no', 'No')],
        string='Did the security officer inspect the item in your presence?'
    )
    found_item_person_signature = fields.Binary(
        string='Signature of Person Who Found the Item'
    )
    found_item_supervisor_informed = fields.Selection(
        [('yes', 'Yes'), ('no', 'No')],
        string='Did you inform your Supervisor?'
    )
    found_item_handover = fields.Selection(
        [('yes', 'Yes'), ('no', 'No')],
        string='Did you handover the item to lost and found?'
    )
    found_item_security_name = fields.Char(string='Security Name (Office Use)')
    found_item_security_designation = fields.Char(
        string='Designation (Office Use)'
    )

    # Return Form Specific Fields
    return_recipient_name = fields.Char(string='Recipient Name')
    return_recipient_home_address = fields.Char(
        string='Recipient Home Address'
    )
    return_recipient_mobile = fields.Char(string='Recipient Mobile Number')
    return_recipient_email = fields.Char(string='Recipient Email Address')
    return_item_description = fields.Html(
        string='Item(s) Received - Full Description'
    )
    return_item_category = fields.Char(
        string='Category of Lost and Found Items'
    )
    return_recipient_signature = fields.Binary(string='Recipient Signature')
    return_security_name = fields.Char(string='Security Name (Office Use)')
    return_security_designation = fields.Char(string='Designation (Office Use)')

    # Community Violation Form Specific Fields
    violation_unit_number = fields.Char(string='Unit/Villa/Shop Number')
    violation_reported_by = fields.Char(string='Reported By')
    violation_observed_datetime = fields.Datetime(string='Observed Date/Time')
    violation_details = fields.Html(string='Violation Details')
    violation_action_taken = fields.Text(string='Immediate Action Taken')
    violation_notice_issued = fields.Boolean(string='Notice Issued')
    violation_repeat_offense = fields.Boolean(string='Repeat Offense')
    violation_fine_amount = fields.Float(string='Fine Amount', digits=(10, 2))
    
    # Door Lock Form Specific Fields
    door_lock_community_name = fields.Char(
        string='Community Name',
        help='Type the community name manually',
    )
    door_lock_unit_number = fields.Char(string='Unit Number')
    door_lock_incident_type = fields.Selection([
        ('break', 'Break'),
        ('replacement', 'Replacement'),
        ('new', 'New'),
    ], string='Incident Type')
    door_lock_location = fields.Selection([
        ('main_entrance', 'Main Entrance'),
        ('bedroom', 'Bedroom'),
        ('living_room', 'Living Room'),
        ('toilets', 'Toilets'),
        ('balcony', 'Balcony'),
        ('maid_room', 'Maid Room'),
        ('store_room', 'Store Room'),
        ('pump_room', 'Pump Room'),
        ('roof_access', 'Roof Access'),
        ('garden_gate', 'Garden Gate'),
        ('terrace_gate', 'Terrace Gate'),
    ], string='Location of the lock')
    door_lock_resident_eid_front = fields.Image(string='Resident EID front')
    door_lock_resident_eid_back = fields.Image(string='Resident EID back')
    door_lock_resident_ejari = fields.Binary(string='Resident Ejari/Title deed')
    door_lock_resident_dtcm = fields.Binary(string='Resident DTCM Permit (Holiday Homes)')
    door_lock_resident_signature = fields.Binary(string='Resident Signature')
    door_lock_locksmith_eid_front = fields.Image(string='Locksmith EID front')
    door_lock_locksmith_eid_back = fields.Image(string='Locksmith EID back')
    door_lock_locksmith_work_permit = fields.Binary(string='Locksmith Work Permit')
    door_lock_locksmith_signature = fields.Binary(string='Locksmith Signature')
    door_lock_local_authorities_reported = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Did the local authorities report the incident scene?')
    door_lock_made_by_designation = fields.Char(string='Designation')
    
    statement_expiry_date = fields.Date(
        string='Statement Expiry Date',
        compute='_compute_statement_expiry_date'
    )

    @api.depends('incident_datetime')
    def _compute_statement_expiry_date(self):
        """Compute the 5-year expiry date for the statement."""
        for record in self:
            if record.incident_datetime:
                record.statement_expiry_date = record.incident_datetime.date() + timedelta(days=365*5)
            else:
                record.statement_expiry_date = False

    # ============================================================
    # SLA COMPUTE METHODS
    # ============================================================
    
    @api.depends('severity', 'site_id', 'category_id')
    def _compute_sla_policy(self):
        """Determine applicable SLA policy"""
        for incident in self:
            policy = self.env['incident.sla.policy'].get_applicable_policy(incident)
            incident.sla_policy_id = policy.id if policy else False
    
    @api.depends('incident_datetime', 'sla_policy_id', 
                 'sla_policy_id.response_time_target',
                 'sla_policy_id.resolution_time_target')
    def _compute_sla_deadlines(self):
        """Calculate SLA deadline times"""
        from datetime import timedelta
        
        for incident in self:
            if incident.sla_policy_id and incident.incident_datetime:
                # Response deadline
                response_minutes = incident.sla_policy_id.response_time_target
                incident.sla_response_deadline = incident.incident_datetime + timedelta(
                    minutes=response_minutes
                )
                
                # Resolution deadline
                resolution_hours = incident.sla_policy_id.resolution_time_target
                incident.sla_resolution_deadline = incident.incident_datetime + timedelta(
                    hours=resolution_hours
                )
            else:
                incident.sla_response_deadline = False
                incident.sla_resolution_deadline = False
    
    @api.depends('incident_datetime', 'first_response_datetime')
    def _compute_response_time(self):
        """Calculate response time"""
        for incident in self:
            if incident.first_response_datetime and incident.incident_datetime:
                delta = incident.first_response_datetime - incident.incident_datetime
                incident.response_time_minutes = delta.total_seconds() / 60
            else:
                incident.response_time_minutes = 0.0
    
    @api.depends('incident_datetime', 'status')
    def _compute_resolution_time(self):
        """Calculate resolution time"""
        for incident in self:
            if incident.status in ['resolved', 'closed'] and incident.incident_datetime:
                # Use review_datetime as resolution time
                resolution_dt = incident.review_datetime or fields.Datetime.now()
                delta = resolution_dt - incident.incident_datetime
                incident.resolution_time_hours = delta.total_seconds() / 3600
            else:
                incident.resolution_time_hours = 0.0
    
    @api.depends('sla_response_deadline', 'response_time_minutes', 
                 'first_response_datetime', 'sla_policy_id')
    def _compute_sla_status(self):
        """Determine SLA compliance status"""
        for incident in self:
            if not incident.sla_policy_id or not incident.sla_response_deadline:
                incident.sla_status = 'on_track'
                incident.sla_breach = False
                continue
            
            now = fields.Datetime.now()
            deadline = incident.sla_response_deadline
            
            # If already responded
            if incident.first_response_datetime:
                if incident.first_response_datetime <= deadline:
                    incident.sla_status = 'on_track'
                    incident.sla_breach = False
                else:
                    incident.sla_status = 'breached'
                    incident.sla_breach = True
                continue
            
            # Calculate time remaining
            time_remaining = (deadline - now).total_seconds() / 60  # minutes
            
            # Calculate total SLA time
            total_sla_time = incident.sla_policy_id.response_time_target
            
            # Calculate percentage elapsed
            time_elapsed = total_sla_time - time_remaining
            percentage_elapsed = (time_elapsed / total_sla_time * 100) if total_sla_time > 0 else 0
            
            # Determine status based on thresholds
            if time_remaining <= 0:
                incident.sla_status = 'breached'
                incident.sla_breach = True
            elif percentage_elapsed >= incident.sla_policy_id.critical_threshold:
                incident.sla_status = 'critical'
                incident.sla_breach = False
            elif percentage_elapsed >= incident.sla_policy_id.warning_threshold:
                incident.sla_status = 'warning'
                incident.sla_breach = False
            else:
                incident.sla_status = 'on_track'
                incident.sla_breach = False
    
    @api.depends('sla_response_deadline', 'sla_resolution_deadline')
    def _compute_time_to_deadlines(self):
        """Calculate time remaining to deadlines"""
        now = fields.Datetime.now()
        
        for incident in self:
            # Time to response deadline
            if incident.sla_response_deadline:
                delta = incident.sla_response_deadline - now
                incident.time_to_response_deadline = delta.total_seconds() / 60
            else:
                incident.time_to_response_deadline = 0.0
            
            # Time to resolution deadline
            if incident.sla_resolution_deadline:
                delta = incident.sla_resolution_deadline - now
                incident.time_to_resolution_deadline = delta.total_seconds() / 3600
            else:
                incident.time_to_resolution_deadline = 0.0
    
    @api.depends('incident_datetime', 'sla_response_deadline', 'first_response_datetime')
    def _compute_sla_percentage(self):
        """Calculate SLA progress percentage"""
        for incident in self:
            if incident.sla_response_deadline and incident.incident_datetime:
                total_time = (incident.sla_response_deadline - incident.incident_datetime).total_seconds()
                
                if incident.first_response_datetime:
                    # Use actual response time
                    elapsed_time = (incident.first_response_datetime - incident.incident_datetime).total_seconds()
                else:
                    # Use current time
                    elapsed_time = (fields.Datetime.now() - incident.incident_datetime).total_seconds()
                
                if total_time > 0:
                    incident.response_sla_percentage = (elapsed_time / total_time) * 100
                else:
                    incident.response_sla_percentage = 0.0
            else:
                incident.response_sla_percentage = 0.0
    
    @api.depends('escalation_log_ids', 'escalation_log_ids.escalation_level')
    def _compute_escalation_stats(self):
        """Compute escalation statistics"""
        for incident in self:
            incident.escalation_count = len(incident.escalation_log_ids)
            
            if incident.escalation_log_ids:
                # Get highest escalation level
                incident.escalation_level = max(
                    incident.escalation_log_ids.mapped('escalation_level')
                )
            else:
                incident.escalation_level = 0

    @api.model_create_multi
    def create(self, vals_list):
        """Generate incident number sequence."""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'incident.report'
                ) or _('New')
        return super().create(vals_list)

    @api.onchange('checkpoint_id')
    def _onchange_checkpoint_id(self):
        """Update location details when a checkpoint is selected."""
        if self.checkpoint_id:
            self.location = self.checkpoint_id.name
            self.latitude = self.checkpoint_id.latitude
            self.longitude = self.checkpoint_id.longitude

    def get_static_map_url(self):
        """Generate Google Static Maps URL for the incident location."""
        self.ensure_one()
        if not self.latitude or not self.longitude:
            return False
            
        api_key = self.env['ir.config_parameter'].sudo().get_param('guardpro.google_maps_api_key')
        if not api_key:
            return False
            
        params = {
            'center': '%f,%f' % (self.latitude, self.longitude),
            'zoom': '16',
            'size': '600x300',
            'maptype': 'satellite',
            'markers': 'color:red|%f,%f' % (self.latitude, self.longitude),
            'key': api_key
        }
        import urllib.parse
        return "https://maps.googleapis.com/maps/api/staticmap?%s" % urllib.parse.urlencode(params)

    def get_google_maps_link(self):
        """Generate a clickable Google Maps link."""
        self.ensure_one()
        if not self.latitude or not self.longitude:
            return False
        return "https://www.google.com/maps/search/?api=1&query=%f,%f" % (self.latitude, self.longitude)

    def _compute_color(self):
        """Set color based on severity."""
        color_map = {
            'low': 3,       # Blue
            'medium': 9,    # Orange
            'high': 2,      # Red
            'critical': 1   # Dark Red
        }
        for record in self:
            record.color = color_map.get(record.severity, 0)
    
    @api.depends('category_id', 'category_id.code')
    def _compute_incident_type(self):
        """Compute incident type flags for dynamic form behavior."""
        for record in self:
            category_code = record.category_id.code if record.category_id else ''
            
            # Medical incidents
            record.is_medical_incident = category_code == 'MED'
            
            # Fire incidents
            record.is_fire_incident = category_code == 'FIRE'
            
            # Security incidents (multiple categories)
            record.is_security_incident = category_code in [
                'SEC', 'THEFT', 'TRESP', 'SUSP'
            ]
            
            # Vehicle incidents
            record.is_vehicle_incident = category_code == 'VEH'
            
            # Safety incidents
            record.is_safety_incident = category_code == 'SAFE'
            
            # Statement incidents (legacy STMT + live STATEMENT)
            record.is_statement_incident = category_code in ('STMT', 'STATEMENT')

            # Fire Emergency incidents
            record.is_fire_emergency_incident = category_code == 'FIRE_EMG'

            # Found Item incidents (legacy FOUND + live FOUND ITEM)
            record.is_found_item_incident = category_code in ('FOUND', 'FOUND ITEM')

            # Return Form incidents (legacy RETURN + live RETURN FORM)
            record.is_return_form_incident = category_code in ('RETURN', 'RETURN FORM')

            # Community violation incidents
            record.is_community_violation_incident = category_code in [
                'VAND', 'SHORT_LET', 'ILL_STAFF', 'MOVE_POL', 'SALE_POL',
                'ANIMAL', 'DMG_REC', 'DMG_COM', 'DMG_SPT', 'DMG_POOL',
                'DMG_PLNT', 'GARDEN', 'HOME_APP', 'EXT_MAJ', 'EXT_MIN',
                'SIGNAGE', 'TERRACE', 'PEST', 'GARAGE', 'RETAIL',
                'ACS', 'ABSCS', 'MIS-COMMON', 'VOSSP', 'VSSP',
            ]

            # Door Lock incidents
            record.is_door_lock_incident = category_code == 'DOOR_LOCK'

            # Facility / maintenance from patrol checkpoints
            record.is_facility_incident = category_code == 'FACILITY'

    @api.constrains('incident_datetime', 'reported_datetime')
    def _check_dates(self):
        """Validate incident dates."""
        for record in self:
            if not record.reported_datetime or not record.incident_datetime:
                continue
            if record.reported_datetime < record.incident_datetime:
                raise ValidationError(_(
                    'Reported date/time cannot be before incident date/time!'
                ))

    def action_submit(self):
        """Submit incident report for review."""
        for record in self:
            now = fields.Datetime.now()
            # Never set reported earlier than the incident time (constraint).
            reported = now
            if record.incident_datetime and reported < record.incident_datetime:
                reported = record.incident_datetime
            record.write({
                'status': 'submitted',
                'reported_datetime': reported,
            })
            record._send_incident_notification()
        return True

    def action_review(self):
        """Mark incident as under review."""
        vals = {
            'status': 'under_review',
            'reviewed_by': self.env.user.id,
            'review_datetime': fields.Datetime.now()
        }

        # Track first response
        if not self.first_response_datetime:
            vals['first_response_datetime'] = fields.Datetime.now()
            vals['responded_by'] = self.env.user.id

        self.write(vals)
        self._push_lifecycle_mobile_notification(
            _('Incident under review: %s') % self.name,
            _('%s marked your incident "%s" as under review.') % (
                self.env.user.name, self.name,
            ),
        )

    def action_investigate(self):
        """Mark incident for investigation."""
        self.write({'status': 'investigating'})
        self._push_lifecycle_mobile_notification(
            _('Incident investigation started: %s') % self.name,
            _('Your incident "%s" is now being formally investigated.') % self.name,
        )

    def action_resolve(self):
        """Mark incident as resolved."""
        self.write({'status': 'resolved'})
        self._push_lifecycle_mobile_notification(
            _('Incident resolved: %s') % self.name,
            _('Your incident "%s" has been resolved.') % self.name,
        )

    def action_close(self):
        """Close incident report."""
        self.write({'status': 'closed'})
        self._push_lifecycle_mobile_notification(
            _('Incident closed: %s') % self.name,
            _('Your incident "%s" is now closed.') % self.name,
        )

    def _push_lifecycle_mobile_notification(self, title, body):
        """Ping the reporting guard's phone when incident status changes."""
        for incident in self:
            if not incident.guard_id or not incident.guard_id.user_id:
                continue
            self.env['guardpro.mobile.outbox'].sudo().push(
                user=incident.guard_id.user_id,
                kind='incident_lifecycle',
                title=title,
                body=body,
                priority='normal',
                res_model='incident.report',
                res_id=incident.id,
                deep_link='/guardpro/mobile/incidents/%s' % incident.id,
                dedup_key='incident_lifecycle:%s:%s' % (incident.id, incident.status),
            )

    def action_panic(self):
        """Handle panic button activation."""
        self.ensure_one()
        self.write({
            'severity': 'critical',
            'priority': '3'
        })
        # Send emergency alerts
        self._send_panic_alert()
    
    def action_create_investigation(self):
        """Create formal investigation for incident"""
        self.ensure_one()
        
        if self.investigation_id:
            # Open existing investigation
            return {
                'type': 'ir.actions.act_window',
                'name': _('Investigation'),
                'res_model': 'incident.investigation',
                'res_id': self.investigation_id.id,
                'view_mode': 'form',
                'target': 'current'
            }
        
        # Create new investigation
        investigation = self.env['incident.investigation'].create({
            'incident_id': self.id,
            'title': _('Investigation: %s') % self.title,
            'investigation_type': 'detailed' if self.severity in ['high', 'critical'] else 'routine',
            'priority': self.priority,
            'lead_investigator_id': self.env.user.id,
        })
        
        self.write({
            'investigation_id': investigation.id,
            'investigation_required': True
        })
        
        self.message_post(
            body=_('Investigation %s created by %s') % (
                investigation.name,
                self.env.user.name
            ),
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Investigation'),
            'res_model': 'incident.investigation',
            'res_id': investigation.id,
            'view_mode': 'form',
            'target': 'current'
        }
    
    def action_view_investigation(self):
        """View related investigation"""
        self.ensure_one()
        
        if not self.investigation_id:
            return self.action_create_investigation()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Investigation'),
            'res_model': 'incident.investigation',
            'res_id': self.investigation_id.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def _parse_notification_emails(self, raw_emails):
        """Parse email strings accepting commas, semicolons, and new lines."""
        return [
            email.strip()
            for email in (raw_emails or '').replace(';', ',').replace('\n', ',').split(',')
            if email.strip()
        ]

    def _send_incident_notification(self):
        """Send category and high-priority incident submission notifications."""
        default_template = self.env.ref(
            'guardpro.incident_category_submit_email_template',
            raise_if_not_found=False,
        )
        Attachment = self.env['ir.attachment'].sudo()

        for incident in self:
            category = incident.category_id
            if not category:
                continue

            recipients = self._parse_notification_emails(category.notification_emails)
            is_high_priority = incident.priority in ('2', '3')
            if is_high_priority and category.high_priority_notification_enabled:
                high_priority_emails = self._parse_notification_emails(
                    category.high_priority_notification_emails
                )
                if high_priority_emails:
                    recipients = list(dict.fromkeys(recipients + high_priority_emails))
            if not recipients:
                _logger.info(
                    'Incident %s: no recipients configured for category/high-priority notifications',
                    incident.name,
                )
                continue

            template = default_template
            if not template:
                _logger.warning(
                    'Incident %s: no notification template found for category %s',
                    incident.name,
                    category.name,
                )
                continue

            email_values = {
                'email_to': ','.join(recipients),
            }

            if category.attach_report_to_notification:
                try:
                    report = incident.get_recommended_report() or self.env.ref(
                        'guardpro.action_report_incident',
                        raise_if_not_found=False,
                    )
                    if report:
                        pdf_content, _content_type = report._render_qweb_pdf(incident.ids)
                        attachment = Attachment.create({
                            'name': '%s.pdf' % (incident.name or 'incident_report'),
                            'type': 'binary',
                            'datas': base64.b64encode(pdf_content),
                            'res_model': 'incident.report',
                            'res_id': incident.id,
                            'mimetype': 'application/pdf',
                        })
                        email_values['attachment_ids'] = [(4, attachment.id)]
                except Exception as err:
                    _logger.exception(
                        'Incident %s: failed to generate PDF attachment: %s',
                        incident.name,
                        err,
                    )

            try:
                template.send_mail(
                    incident.id,
                    force_send=True,
                    email_values=email_values,
                )
            except Exception as err:
                _logger.exception(
                    'Incident %s: failed to send notification email: %s',
                    incident.name,
                    err,
                )

    def _send_panic_alert(self):
        """Fire the highest-priority mobile notification to every
        supervisor/manager covering this site, plus any user explicitly
        flagged on the site as emergency contact."""
        self.ensure_one()

        recipients = self.env['res.users']

        # 1. Site-scoped supervisors + managers
        try:
            supervisor_group = self.env.ref(
                'guardpro.group_guardpro_supervisor', raise_if_not_found=False
            )
            manager_group = self.env.ref(
                'guardpro.group_guardpro_manager', raise_if_not_found=False
            )
            groups = self.env['res.groups']
            if supervisor_group:
                groups |= supervisor_group
            if manager_group:
                groups |= manager_group
            if groups:
                candidate_users = self.env['res.users'].sudo().search([
                    ('groups_id', 'in', groups.ids),
                    ('active', '=', True),
                ])
                for user in candidate_users:
                    # site_ids is the record-rule field used elsewhere;
                    # empty set means "all sites".
                    user_sites = getattr(user, 'site_ids', None)
                    if user_sites is None or not user_sites or (
                        self.site_id and self.site_id.id in user_sites.ids
                    ):
                        recipients |= user
        except Exception as e:
            _logger.warning('panic recipients resolution failed: %s', e)

        # 2. Site emergency contact user (if configured)
        site = self.site_id
        if site:
            for attr in ('supervisor_id', 'emergency_contact_user_id',
                         'site_manager_id', 'account_manager_id'):
                candidate = getattr(site, attr, False)
                if candidate and candidate._name == 'res.users':
                    recipients |= candidate

        # 3. The reporting guard gets a confirmation ping so they see
        # their panic was received.
        if self.guard_id and self.guard_id.user_id:
            recipients |= self.guard_id.user_id

        _logger.warning(
            'PANIC ALERT: Incident %s at site %s -> notifying users %s',
            self.name, site.name if site else '-', recipients.ids,
        )

        if recipients:
            self.env['guardpro.mobile.outbox'].sudo().push(
                user=recipients,
                kind='incident_panic',
                title=_('PANIC / SOS: %s') % (
                    self.guard_id.name if self.guard_id else self.name,
                ),
                body=_('Site: %s\nIncident: %s\nCategory: %s\nSeverity: %s') % (
                    site.name if site else '-',
                    self.name,
                    self.category_id.name if self.category_id else '-',
                    dict(self._fields['severity'].selection).get(
                        self.severity, self.severity or ''
                    ) if 'severity' in self._fields else '-',
                ),
                priority='urgent',
                res_model='incident.report',
                res_id=self.id,
                deep_link='/guardpro/mobile/incidents/%s' % self.id,
                dedup_key='incident_panic:%s' % self.id,
                # Panic alerts never auto-expire quietly.
                expires_in_hours=24,
            )
    
    def get_recommended_report(self):
        """Get recommended report template based on incident category.
        
        Returns the appropriate report action based on the incident category.
        This helps users select the most suitable report format.
        """
        self.ensure_one()
        
        # Map category codes to report actions
        report_mapping = {
            'MED': 'guardpro.action_report_incident_medical',
            'FIRE': 'guardpro.action_report_incident_fire',
            'SEC': 'guardpro.action_report_incident_security',
            'THEFT': 'guardpro.action_report_incident_security',
            'TRESP': 'guardpro.action_report_incident_security',
            'SUSP': 'guardpro.action_report_incident_security',
            'VEH': 'guardpro.action_report_incident_vehicle',
            'ABND_VEH': 'guardpro.action_report_incident_abandoned_vehicle',
            'LT_PARK': 'guardpro.action_report_incident_long_term_parked_vehicle',
            'EQ_HO': 'guardpro.action_report_incident_equipment_handover',
            'CCTV_HO': 'guardpro.action_report_incident_cctv_handover',
            'AUTH_VISIT': 'guardpro.action_report_incident_local_authority_visit',
            'SAFE': 'guardpro.action_report_incident_safety',
            'STMT': 'guardpro.action_report_incident_statement',
            'STATEMENT': 'guardpro.action_report_incident_statement',
            'FOUND': 'guardpro.action_report_incident_found_item',
            'FOUND ITEM': 'guardpro.action_report_incident_found_item',
            'RETURN': 'guardpro.action_report_incident_return_form',
            'RETURN FORM': 'guardpro.action_report_incident_return_form',
            'VAND': 'guardpro.action_report_incident_community_violation',
            'SHORT_LET': 'guardpro.action_report_incident_community_violation',
            'ILL_STAFF': 'guardpro.action_report_incident_community_violation',
            'MOVE_POL': 'guardpro.action_report_incident_community_violation',
            'SALE_POL': 'guardpro.action_report_incident_community_violation',
            'ANIMAL': 'guardpro.action_report_incident_community_violation',
            'DMG_REC': 'guardpro.action_report_incident_community_violation',
            'DMG_COM': 'guardpro.action_report_incident_community_violation',
            'DMG_SPT': 'guardpro.action_report_incident_community_violation',
            'DMG_POOL': 'guardpro.action_report_incident_community_violation',
            'DMG_PLNT': 'guardpro.action_report_incident_community_violation',
            'GARDEN': 'guardpro.action_report_incident_community_violation',
            'HOME_APP': 'guardpro.action_report_incident_community_violation',
            'EXT_MAJ': 'guardpro.action_report_incident_community_violation',
            'EXT_MIN': 'guardpro.action_report_incident_community_violation',
            'SIGNAGE': 'guardpro.action_report_incident_community_violation',
            'TERRACE': 'guardpro.action_report_incident_community_violation',
            'PEST': 'guardpro.action_report_incident_community_violation',
            'GARAGE': 'guardpro.action_report_incident_community_violation',
            'RETAIL': 'guardpro.action_report_incident_community_violation',
        }
        
        category_code = self.category_id.code if self.category_id else ''
        report_action = report_mapping.get(
            category_code,
            'guardpro.action_report_incident'  # Default general report
        )
        
        return self.env.ref(report_action, raise_if_not_found=False)
    
    def action_print_recommended_report(self):
        """Print the recommended report for this incident category."""
        self.ensure_one()
        report = self.get_recommended_report()
        if report:
            return report.report_action(self.id)
        # Fallback to general report if recommended not found
        return self.env.ref('guardpro.action_report_incident').report_action(
            self.id
        )
    
    # ====================================================
    # SCHEDULED ACTIONS (CRON JOBS)
    # ====================================================
    
    # ============================================================
    # SLA-BASED ESCALATION METHODS
    # ============================================================
    
    @api.model
    def check_sla_breaches(self):
        """Check for SLA breaches and trigger appropriate actions.
        
        Called by scheduled action every 5 minutes.
        Monitors all open incidents for SLA compliance.
        """
        now = fields.Datetime.now()
        
        # Find incidents that need SLA monitoring
        open_incidents = self.search([
            ('status', 'in', ['draft', 'submitted', 'under_review', 'investigating']),
            ('sla_policy_id', '!=', False),
            ('first_response_datetime', '=', False)  # Not yet responded
        ])
        
        escalations_created = 0
        warnings_sent = 0
        
        for incident in open_incidents:
            try:
                policy = incident.sla_policy_id
                if not policy or not policy.auto_escalate:
                    continue
                
                # Calculate time elapsed
                time_elapsed = (now - incident.incident_datetime).total_seconds() / 60
                target_time = policy.response_time_target
                
                # Calculate percentage of SLA elapsed
                sla_percentage = (time_elapsed / target_time * 100) if target_time > 0 else 0
                
                # Check for warning threshold
                if (sla_percentage >= policy.warning_threshold and 
                    sla_percentage < policy.critical_threshold):
                    # Send warning if not already sent
                    if not incident.escalation_log_ids.filtered(
                        lambda e: e.escalation_type == 'warning_threshold'
                    ):
                        incident._create_escalation_log(
                            escalation_type='warning_threshold',
                            escalation_level=1,
                            reason=_(
                                'Incident has reached warning threshold (%.1f%% of SLA time elapsed).\n'
                                'Target response time: %d minutes\n'
                                'Time elapsed: %.1f minutes'
                            ) % (sla_percentage, target_time, time_elapsed),
                            user_ids=policy.escalation_level_1_user_ids
                        )
                        warnings_sent += 1
                
                # Check for critical threshold
                elif (sla_percentage >= policy.critical_threshold and
                      time_elapsed < target_time):
                    # Send critical warning if not already sent
                    if not incident.escalation_log_ids.filtered(
                        lambda e: e.escalation_type == 'critical_threshold'
                    ):
                        incident._create_escalation_log(
                            escalation_type='critical_threshold',
                            escalation_level=2,
                            reason=_(
                                'CRITICAL: Incident has reached critical threshold (%.1f%% of SLA time elapsed).\n'
                                'Target response time: %d minutes\n'
                                'Time elapsed: %.1f minutes\n'
                                'Immediate action required!'
                            ) % (sla_percentage, target_time, time_elapsed),
                            user_ids=policy.escalation_level_2_user_ids
                        )
                        warnings_sent += 1
                
                # Check for SLA breach
                elif time_elapsed >= target_time:
                    # Check if already escalated for breach
                    if not incident.escalation_log_ids.filtered(
                        lambda e: e.escalation_type == 'response_sla_breach'
                    ):
                        breach_time = time_elapsed - target_time
                        
                        # Update incident
                        incident.write({
                            'escalated': True,
                            'sla_breach_time': breach_time
                        })
                        
                        # Create escalation log
                        incident._create_escalation_log(
                            escalation_type='response_sla_breach',
                            escalation_level=3,
                            reason=_(
                                'SLA BREACH: Response SLA has been breached!\n'
                                'Target response time: %d minutes\n'
                                'Actual time elapsed: %.1f minutes\n'
                                'Breach by: %.1f minutes\n\n'
                                'Immediate escalation required.'
                            ) % (target_time, time_elapsed, breach_time),
                            user_ids=policy.escalation_level_3_user_ids,
                            sla_breach_time=breach_time
                        )
                        
                        escalations_created += 1
                        
                        _logger.warning(
                            'SLA breach for incident %s: %.1f minutes over target of %d minutes',
                            incident.name, breach_time, target_time
                        )
                
            except Exception as e:
                _logger.error('Error checking SLA for incident %s: %s', 
                            incident.id, str(e))
        
        if escalations_created > 0 or warnings_sent > 0:
            _logger.info(
                'SLA check complete: %d escalations created, %d warnings sent',
                escalations_created, warnings_sent
            )
        
        return True
    
    @api.model
    def check_progressive_escalation(self):
        """Check for progressive escalations based on time since breach.
        
        Called by scheduled action every 15 minutes.
        Escalates breached incidents to higher levels over time.
        """
        now = fields.Datetime.now()
        
        # Find incidents with SLA breaches
        breached_incidents = self.search([
            ('sla_breach', '=', True),
            ('status', 'not in', ['resolved', 'closed']),
            ('sla_policy_id', '!=', False)
        ])
        
        progressive_escalations = 0
        
        for incident in breached_incidents:
            try:
                policy = incident.sla_policy_id
                if not policy or not policy.auto_escalate:
                    continue
                
                # Get time since incident
                time_since_incident = (now - incident.incident_datetime).total_seconds() / 60
                
                # Calculate breach time
                breach_time = time_since_incident - policy.response_time_target
                
                # Check for level 3 escalation (management)
                if (breach_time >= policy.level_3_escalation_time and
                    not incident.escalation_log_ids.filtered(
                        lambda e: e.escalation_type == 'progressive_level_3'
                    )):
                    incident._create_escalation_log(
                        escalation_type='progressive_level_3',
                        escalation_level=3,
                        reason=_(
                            'MANAGEMENT ESCALATION: SLA breach persists after %d minutes.\n'
                            'Original SLA target: %d minutes\n'
                            'Time since incident: %.1f minutes\n'
                            'Breach duration: %.1f minutes\n\n'
                            'Senior management intervention required.'
                        ) % (
                            policy.level_3_escalation_time,
                            policy.response_time_target,
                            time_since_incident,
                            breach_time
                        ),
                        user_ids=policy.escalation_level_3_user_ids
                    )
                    progressive_escalations += 1
                
                # Check for level 2 escalation
                elif (breach_time >= policy.level_2_escalation_time and
                      not incident.escalation_log_ids.filtered(
                          lambda e: e.escalation_type == 'progressive_level_2'
                      )):
                    incident._create_escalation_log(
                        escalation_type='progressive_level_2',
                        escalation_level=2,
                        reason=_(
                            'Level 2 Escalation: SLA breach persists after %d minutes.\n'
                            'Original SLA target: %d minutes\n'
                            'Time since incident: %.1f minutes\n'
                            'Breach duration: %.1f minutes'
                        ) % (
                            policy.level_2_escalation_time,
                            policy.response_time_target,
                            time_since_incident,
                            breach_time
                        ),
                        user_ids=policy.escalation_level_2_user_ids
                    )
                    progressive_escalations += 1
                
                # Check for level 1 escalation
                elif (breach_time >= policy.level_1_escalation_time and
                      not incident.escalation_log_ids.filtered(
                          lambda e: e.escalation_type == 'progressive_level_1'
                      )):
                    incident._create_escalation_log(
                        escalation_type='progressive_level_1',
                        escalation_level=1,
                        reason=_(
                            'Level 1 Escalation: SLA breach persists after %d minutes.\n'
                            'Original SLA target: %d minutes\n'
                            'Time since incident: %.1f minutes\n'
                            'Breach duration: %.1f minutes'
                        ) % (
                            policy.level_1_escalation_time,
                            policy.response_time_target,
                            time_since_incident,
                            breach_time
                        ),
                        user_ids=policy.escalation_level_1_user_ids
                    )
                    progressive_escalations += 1
                
            except Exception as e:
                _logger.error('Error in progressive escalation for incident %s: %s',
                            incident.id, str(e))
        
        if progressive_escalations > 0:
            _logger.info('Created %d progressive escalations', progressive_escalations)
        
        return True
    
    def _create_escalation_log(self, escalation_type, escalation_level, reason, 
                               user_ids=None, sla_breach_time=0.0):
        """Create escalation log entry
        
        Args:
            escalation_type: Type of escalation
            escalation_level: Escalation level (1, 2, 3)
            reason: Escalation reason text
            user_ids: Users to escalate to (recordset)
            sla_breach_time: Breach time in minutes
        """
        self.ensure_one()
        
        vals = {
            'incident_id': self.id,
            'sla_policy_id': self.sla_policy_id.id if self.sla_policy_id else False,
            'escalation_type': escalation_type,
            'escalation_level': escalation_level,
            'escalation_reason': reason,
            'escalated_by_user_id': self.env.user.id,
            'sla_target_time': self.sla_policy_id.response_time_target if self.sla_policy_id else 0,
            'sla_breach_time': sla_breach_time
        }
        
        if user_ids:
            vals['escalated_to_user_ids'] = [(6, 0, user_ids.ids)]
        
        # Create escalation log
        escalation = self.env['incident.escalation.log'].create(vals)
        
        _logger.info(
            'Created escalation log for incident %s: Type=%s, Level=%d',
            self.name, escalation_type, escalation_level
        )
        
        return escalation
    
    @api.model
    def escalate_critical_incidents(self):
        """Automatically escalate critical incidents not responded to within threshold.
        
        Called by scheduled action every 15 minutes.
        Escalates critical incidents that haven't received a response within the
        configured escalation time (default: 30 minutes).
        """
        from datetime import timedelta
        
        # Get escalation threshold from settings
        IrConfigParameter = self.env['ir.config_parameter'].sudo()
        escalation_minutes = int(IrConfigParameter.get_param(
            'guardpro.critical_incident_escalation', '30'
        ))
        
        # Calculate threshold time
        now = fields.Datetime.now()
        threshold = now - timedelta(minutes=escalation_minutes)
        
        # Find critical incidents needing escalation
        critical_incidents = self.search([
            ('severity', '=', 'critical'),
            ('status', 'in', ['draft', 'submitted']),
            ('incident_datetime', '<=', threshold),
            ('first_response_datetime', '=', False),
            ('escalated', '=', False)
        ])
        
        if not critical_incidents:
            _logger.info('No critical incidents requiring escalation')
            return True
        
        escalated_count = 0
        
        for incident in critical_incidents:
            try:
                # Mark as escalated
                incident.write({
                    'escalated': True,
                    'priority': '3'  # Set to urgent
                })
                
                # Create escalation log if SLA policy exists
                if incident.sla_policy_id:
                    time_elapsed = (now - incident.incident_datetime).total_seconds() / 60
                    incident._create_escalation_log(
                        escalation_type='critical_auto_escalation',
                        escalation_level=2,
                        reason=_(
                            'CRITICAL INCIDENT AUTO-ESCALATION\n\n'
                            'Critical incident has not received response within %d minutes.\n'
                            'Incident reported: %s\n'
                            'Time elapsed: %.1f minutes\n'
                            'Immediate management attention required!'
                        ) % (
                            escalation_minutes,
                            incident.incident_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                            time_elapsed
                        ),
                        user_ids=incident.sla_policy_id.escalation_level_2_user_ids
                    )
                
                # Post message on incident
                incident.message_post(
                    body=Markup(
                        '<p><strong>⚠️ CRITICAL INCIDENT AUTO-ESCALATED</strong></p>'
                        '<p>This critical incident has been automatically escalated '
                        'to the executive response team due to severity level.</p>'
                        '<p><strong>Escalated To:</strong> %s</p>'
                        '<p><strong>Escalation Time:</strong> %s</p>'
                        '<p style="margin-top: 16px; font-size: 12px; color: #888;">This is an automated escalation notification.</p>'
                    ) % (
                        self.env.user.name,
                        fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )
                
                escalated_count += 1
                
                _logger.warning(
                    'Auto-escalated critical incident %s (%.1f minutes without response)',
                    incident.name,
                    (now - incident.incident_datetime).total_seconds() / 60
                )
                
            except Exception as e:
                _logger.error(
                    'Error auto-escalating critical incident %s: %s',
                    incident.id, str(e)
                )
        
        if escalated_count > 0:
            _logger.info(
                'Auto-escalated %d critical incidents (threshold: %d minutes)',
                escalated_count, escalation_minutes
            )
        
        return True
    
    @api.model
    def generate_daily_sla_breach_report(self):
        """Generate daily report of SLA breaches and send to management.
        
        Called by scheduled action daily at 8 AM.
        Sends summary email of previous day's SLA breaches.
        """
        from datetime import datetime, timedelta
        
        # Get yesterday's date range
        today = fields.Date.today()
        yesterday = today - timedelta(days=1)
        yesterday_start = fields.Datetime.to_datetime(yesterday)
        yesterday_end = yesterday_start + timedelta(days=1)
        
        # Find SLA breaches from yesterday
        breached_incidents = self.search([
            ('sla_breach', '=', True),
            ('incident_datetime', '>=', yesterday_start),
            ('incident_datetime', '<', yesterday_end)
        ])
        
        if not breached_incidents:
            _logger.info('No SLA breaches to report for %s', yesterday)
            return True
        
        # Aggregate statistics
        total_breaches = len(breached_incidents)
        breaches_by_severity = {}
        breaches_by_site = {}
        
        for incident in breached_incidents:
            # By severity
            severity = incident.severity
            if severity not in breaches_by_severity:
                breaches_by_severity[severity] = []
            breaches_by_severity[severity].append(incident)
            
            # By site
            site_name = incident.site_id.name if incident.site_id else 'Unknown'
            if site_name not in breaches_by_site:
                breaches_by_site[site_name] = []
            breaches_by_site[site_name].append(incident)
        
        # Send email notification to management
        # Get management users
        manager_group = self.env.ref('guardpro.group_guardpro_manager', 
                                     raise_if_not_found=False)
        if manager_group and manager_group.users:
            # Create email body
            body_html = _(
                '<h2>Daily SLA Breach Report - %s</h2>'
                '<p><strong>Total SLA Breaches:</strong> %d</p>'
                '<hr/>'
                '<h3>Breaches by Severity</h3>'
                '<ul>'
            ) % (yesterday.strftime('%Y-%m-%d'), total_breaches)
            
            for severity, incidents in breaches_by_severity.items():
                body_html += _('<li><strong>%s:</strong> %d incidents</li>') % (
                    severity.upper(), len(incidents)
                )
            
            body_html += _('</ul><hr/><h3>Breaches by Site</h3><ul>')
            
            for site_name, incidents in breaches_by_site.items():
                body_html += _('<li><strong>%s:</strong> %d incidents</li>') % (
                    site_name, len(incidents)
                )
            
            body_html += _(
                '</ul><hr/>'
                '<h3>Incident Details</h3>'
                '<table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">'
                '<thead>'
                '<tr style="background-color: #f0f0f0;">'
                '<th>Incident</th>'
                '<th>Title</th>'
                '<th>Severity</th>'
                '<th>Project</th>'
                '<th>Breach Time (min)</th>'
                '<th>Status</th>'
                '</tr>'
                '</thead>'
                '<tbody>'
            )
            
            for incident in breached_incidents:
                body_html += _(
                    '<tr>'
                    '<td>%s</td>'
                    '<td>%s</td>'
                    '<td>%s</td>'
                    '<td>%s</td>'
                    '<td>%.1f</td>'
                    '<td>%s</td>'
                    '</tr>'
                ) % (
                    incident.name,
                    incident.title,
                    incident.severity.upper(),
                    incident.site_id.name if incident.site_id else 'N/A',
                    incident.sla_breach_time or 0.0,
                    incident.status.replace('_', ' ').title()
                )
            
            body_html += _('</tbody></table>')
            
            # Email is disabled globally; push the SLA breach summary
            # into each manager's mobile outbox instead so it reaches
            # them on their phone.
            Outbox = self.env['guardpro.mobile.outbox'].sudo()
            short_body = _(
                '%(total)d SLA breach(es) recorded yesterday (%(date)s). '
                'Open the app for full details.'
            ) % {
                'total': total_breaches,
                'date': yesterday.strftime('%Y-%m-%d'),
            }
            # One dedup row per manager + date - re-running the cron
            # within the same day does not stack duplicate cards.
            dedup_base = 'sla_breach:%s' % yesterday.strftime('%Y%m%d')
            for user in manager_group.users:
                if not user.active:
                    continue
                try:
                    Outbox.push(
                        user=user,
                        kind='sla_breach',
                        title=_('SLA breaches: %d yesterday') % total_breaches,
                        body=short_body,
                        priority='high',
                        res_model='incident.report',
                        res_id=0,
                        deep_link='/guardpro/mobile/incidents?filter=sla_breach',
                        dedup_key='%s:%d' % (dedup_base, user.id),
                        # SLA reports age out quickly - a stale card at
                        # the top of the list helps nobody.
                        expires_in_hours=36,
                    )
                except Exception as e:  # pragma: no cover - defensive
                    _logger.warning(
                        'incident.report: SLA outbox push failed for '
                        'user %s: %s', user.login, e,
                    )
        
        _logger.info('Generated daily SLA breach report: %d breaches on %s',
                    total_breaches, yesterday)
        
        return True
    
    def init(self):
        """Create database indexes for performance optimization."""
        # Index for severity and date-based queries
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS incident_severity_date_idx 
            ON incident_report (severity, incident_datetime DESC);
        """)
        
        # Index for site and status-based queries
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS incident_site_status_idx 
            ON incident_report (site_id, status);
        """)
        
        # Index for critical incident escalation
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS incident_critical_unresponded_idx 
            ON incident_report (severity, status, incident_datetime) 
            WHERE severity = 'critical' AND status IN ('draft', 'in_progress');
        """)
        
        # Index for reporter-based queries
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS incident_reporter_date_idx 
            ON incident_report (guard_id, incident_datetime DESC);
        """)


class IncidentCategory(models.Model):
    """Incident Categories."""

    _name = 'incident.category'
    _description = 'Incident Category'
    _order = 'sequence, name'

    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True
    )
    code = fields.Char(
        string='Code',
        required=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    description = fields.Text(
        string='Description',
        translate=True
    )
    color = fields.Integer(
        string='Color Index'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    hide_from_guard_incidents = fields.Boolean(
        string='Hide from Guard Incident Reports',
        default=False,
        help='When set, guards cannot select this category when reporting incidents '
             'in the mobile app. Used for patrol-only categories (e.g. facility issues).',
    )
    notification_emails = fields.Text(
        string='Submission Notification Emails',
        help='Recipients notified when incidents in this category are submitted. Use comma, semicolon, or new line separators.',
    )
    high_priority_notification_enabled = fields.Boolean(
        string='High Priority Notifications',
        default=False,
        help='When enabled, incidents in this category with High priority also notify the high-priority recipient list.',
    )
    high_priority_notification_emails = fields.Text(
        string='High Priority Notification Emails',
        help='Recipients for high-priority incidents in this category. Use comma, semicolon, or new line separators.',
    )
    attach_report_to_notification = fields.Boolean(
        string='Attach Incident Report PDF',
        default=True,
        help='Attach the incident PDF report when sending submission notifications.',
    )
    
    _sql_constraints = [
        ('code_unique', 'unique(code)',
         'Category code must be unique!'),
    ]


class IncidentTag(models.Model):
    """Incident Tags."""

    _name = 'incident.tag'
    _description = 'Incident Tag'
    _order = 'name'

    name = fields.Char(
        string='Tag Name',
        required=True,
        translate=True
    )
    color = fields.Integer(
        string='Color Index'
    )

