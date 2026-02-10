# GuardPro Models

## Overview

GuardPro's data models are built using Odoo's Object-Relational Mapping (ORM) system, providing a robust foundation for security management operations. The models follow Odoo best practices and implement comprehensive business logic, validation, and security controls.

## Core Models

### Guard Profile Model

```python
# Guard profile management
class GuardProfile(models.Model):
    _name = 'guard.profile'
    _description = 'Security Guard Profile'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    
    # Basic Information
    name = fields.Char(string='Full Name', required=True, tracking=True)
    employee_id = fields.Char(string='Employee ID', required=True, unique=True, tracking=True)
    email = fields.Char(string='Email', tracking=True)
    phone = fields.Char(string='Phone Number', tracking=True)
    mobile = fields.Char(string='Mobile Number', tracking=True)
    
    # Personal Information
    date_of_birth = fields.Date(string='Date of Birth')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender')
    nationality = fields.Char(string='Nationality')
    address = fields.Text(string='Address')
    
    # Employment Information
    hire_date = fields.Date(string='Hire Date', required=True, tracking=True)
    employment_status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('terminated', 'Terminated'),
        ('suspended', 'Suspended')
    ], string='Employment Status', default='active', tracking=True)
    
    # Skills and Certifications
    skills_ids = fields.Many2many(
        'guard.skill',
        'guard_profile_skill_rel',
        'guard_id', 'skill_id',
        string='Skills'
    )
    certifications_ids = fields.One2many(
        'guard.certification',
        'guard_id',
        string='Certifications'
    )
    
    # Site Assignments
    site_ids = fields.Many2many(
        'guard.site',
        'guard_site_rel',
        'guard_id', 'site_id',
        string='Assigned Sites'
    )
    
    # Performance Metrics
    performance_score = fields.Float(string='Performance Score', digits=(5, 2))
    attendance_rate = fields.Float(string='Attendance Rate', digits=(5, 2))
    incident_count = fields.Integer(string='Incident Count', compute='_compute_incident_count')
    
    # System Fields
    user_id = fields.Many2one('res.users', string='System User', tracking=True)
    active = fields.Boolean(string='Active', default=True)
    
    # Computed Fields
    @api.depends('site_ids')
    def _compute_incident_count(self):
        for record in self:
            incidents = self.env['guard.incident'].search([
                ('reported_by', '=', record.id)
            ])
            record.incident_count = len(incidents)
    
    # Constraints
    @api.constrains('email')
    def _check_email(self):
        for record in self:
            if record.email and not self._is_valid_email(record.email):
                raise ValidationError(_("Invalid email address"))
    
    @api.constrains('phone', 'mobile')
    def _check_phone(self):
        for record in self:
            if record.phone and not self._is_valid_phone(record.phone):
                raise ValidationError(_("Invalid phone number"))
            if record.mobile and not self._is_valid_phone(record.mobile):
                raise ValidationError(_("Invalid mobile number"))
    
    # Business Methods
    def action_assign_to_site(self, site_id):
        """Assign guard to a site"""
        self.site_ids = [(4, site_id)]
        self.message_post(
            body=_("Guard assigned to site: %s") % self.env['guard.site'].browse(site_id).name
        )
    
    def action_remove_from_site(self, site_id):
        """Remove guard from a site"""
        self.site_ids = [(3, site_id)]
        self.message_post(
            body=_("Guard removed from site: %s") % self.env['guard.site'].browse(site_id).name
        )
    
    def action_update_performance(self, score):
        """Update guard performance score"""
        self.performance_score = score
        self.message_post(
            body=_("Performance score updated to: %s") % score
        )
    
    # Utility Methods
    def _is_valid_email(self, email):
        """Validate email format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _is_valid_phone(self, phone):
        """Validate phone number format"""
        import re
        pattern = r'^\+?1?-?\.?\s?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})$'
        return re.match(pattern, phone) is not None
```

### Site Management Model

```python
# Site management
class GuardSite(models.Model):
    _name = 'guard.site'
    _description = 'Security Site'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    
    # Basic Information
    name = fields.Char(string='Site Name', required=True, tracking=True)
    code = fields.Char(string='Site Code', required=True, unique=True, tracking=True)
    client_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    
    # Location Information
    address = fields.Text(string='Address', required=True)
    city = fields.Char(string='City')
    state = fields.Char(string='State/Province')
    country_id = fields.Many2one('res.country', string='Country')
    zip_code = fields.Char(string='ZIP Code')
    
    # GPS Coordinates
    latitude = fields.Float(string='Latitude', digits=(10, 6))
    longitude = fields.Float(string='Longitude', digits=(10, 6))
    geofence_radius = fields.Float(string='Geofence Radius (meters)', default=100)
    
    # Site Configuration
    site_type = fields.Selection([
        ('office', 'Office Building'),
        ('retail', 'Retail Store'),
        ('industrial', 'Industrial Facility'),
        ('healthcare', 'Healthcare Facility'),
        ('educational', 'Educational Institution'),
        ('residential', 'Residential Complex'),
        ('other', 'Other')
    ], string='Site Type', required=True, tracking=True)
    
    security_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Security Level', default='medium', tracking=True)
    
    # Operating Information
    operating_hours = fields.Text(string='Operating Hours')
    access_points = fields.Integer(string='Number of Access Points', default=1)
    emergency_contacts = fields.Text(string='Emergency Contacts')
    
    # Personnel Assignment
    manager_ids = fields.Many2many(
        'res.users',
        'site_manager_rel',
        'site_id', 'user_id',
        string='Site Managers'
    )
    supervisor_ids = fields.Many2many(
        'res.users',
        'site_supervisor_rel',
        'site_id', 'user_id',
        string='Site Supervisors'
    )
    guard_ids = fields.Many2many(
        'guard.profile',
        'guard_site_rel',
        'site_id', 'guard_id',
        string='Assigned Guards'
    )
    
    # Equipment and Systems
    equipment_ids = fields.One2many(
        'guard.equipment',
        'site_id',
        string='Security Equipment'
    )
    access_control_systems = fields.One2many(
        'guard.access.control',
        'site_id',
        string='Access Control Systems'
    )
    
    # Performance Metrics
    incident_count = fields.Integer(string='Total Incidents', compute='_compute_incident_count')
    current_shift_count = fields.Integer(string='Current Shifts', compute='_compute_current_shifts')
    compliance_score = fields.Float(string='Compliance Score', digits=(5, 2))
    
    # System Fields
    active = fields.Boolean(string='Active', default=True)
    
    # Computed Fields
    @api.depends('incident_ids')
    def _compute_incident_count(self):
        for record in self:
            record.incident_count = len(record.incident_ids)
    
    @api.depends('shift_ids')
    def _compute_current_shifts(self):
        for record in self:
            current_shifts = self.env['guard.shift'].search([
                ('site_id', '=', record.id),
                ('status', 'in', ['in_progress', 'scheduled'])
            ])
            record.current_shift_count = len(current_shifts)
    
    # Related Fields
    incident_ids = fields.One2many('guard.incident', 'site_id', string='Incidents')
    shift_ids = fields.One2many('guard.shift', 'site_id', string='Shifts')
    task_ids = fields.One2many('guard.task', 'site_id', string='Tasks')
    
    # Business Methods
    def action_create_shift(self):
        """Create new shift for this site"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Shift'),
            'res_model': 'guard.shift',
            'view_mode': 'form',
            'context': {
                'default_site_id': self.id,
                'default_client_id': self.client_id.id
            }
        }
    
    def action_view_incidents(self):
        """View incidents for this site"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Site Incidents'),
            'res_model': 'guard.incident',
            'view_mode': 'tree,form',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id}
        }
    
    def action_update_geofence(self, latitude, longitude, radius):
        """Update site geofence coordinates"""
        self.write({
            'latitude': latitude,
            'longitude': longitude,
            'geofence_radius': radius
        })
        self.message_post(
            body=_("Geofence updated: Lat: %s, Lng: %s, Radius: %s meters") % (latitude, longitude, radius)
        )
    
    # Constraints
    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        for record in self:
            if record.latitude and (record.latitude < -90 or record.latitude > 90):
                raise ValidationError(_("Latitude must be between -90 and 90"))
            if record.longitude and (record.longitude < -180 or record.longitude > 180):
                raise ValidationError(_("Longitude must be between -180 and 180"))
```

### Shift Management Model

```python
# Shift management
class GuardShift(models.Model):
    _name = 'guard.shift'
    _description = 'Security Guard Shift'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_date desc, start_time'
    
    # Basic Information
    name = fields.Char(string='Shift Name', compute='_compute_name', store=True)
    shift_number = fields.Char(string='Shift Number', required=True, unique=True)
    
    # Assignment Information
    guard_id = fields.Many2one('guard.profile', string='Guard', required=True, tracking=True)
    site_id = fields.Many2one('guard.site', string='Site', required=True, tracking=True)
    client_id = fields.Many2one('res.partner', string='Client', related='site_id.client_id', store=True)
    
    # Schedule Information
    scheduled_date = fields.Date(string='Scheduled Date', required=True, tracking=True)
    start_time = fields.Datetime(string='Start Time', required=True, tracking=True)
    end_time = fields.Datetime(string='End Time', required=True, tracking=True)
    duration = fields.Float(string='Duration (hours)', compute='_compute_duration', store=True)
    
    # Status Information
    status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show')
    ], string='Status', default='scheduled', tracking=True)
    
    # Check-in/Check-out Information
    check_in_time = fields.Datetime(string='Check-in Time', tracking=True)
    check_out_time = fields.Datetime(string='Check-out Time', tracking=True)
    check_in_location = fields.Char(string='Check-in Location')
    check_out_location = fields.Char(string='Check-out Location')
    check_in_photo = fields.Binary(string='Check-in Photo')
    check_out_photo = fields.Binary(string='Check-out Photo')
    
    # Performance Information
    tasks_completed = fields.Integer(string='Tasks Completed', compute='_compute_tasks_completed')
    patrols_completed = fields.Integer(string='Patrols Completed', compute='_compute_patrols_completed')
    incidents_reported = fields.Integer(string='Incidents Reported', compute='_compute_incidents_reported')
    
    # Related Records
    task_ids = fields.One2many('guard.task', 'shift_id', string='Tasks')
    patrol_ids = fields.One2many('guard.patrol', 'shift_id', string='Patrols')
    incident_ids = fields.One2many('guard.incident', 'shift_id', string='Incidents')
    
    # System Fields
    active = fields.Boolean(string='Active', default=True)
    
    # Computed Fields
    @api.depends('guard_id', 'site_id', 'scheduled_date', 'start_time')
    def _compute_name(self):
        for record in self:
            if record.guard_id and record.site_id and record.scheduled_date:
                record.name = f"{record.guard_id.name} - {record.site_id.name} - {record.scheduled_date}"
            else:
                record.name = "New Shift"
    
    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for record in self:
            if record.start_time and record.end_time:
                delta = record.end_time - record.start_time
                record.duration = delta.total_seconds() / 3600  # Convert to hours
            else:
                record.duration = 0.0
    
    @api.depends('task_ids')
    def _compute_tasks_completed(self):
        for record in self:
            record.tasks_completed = len(record.task_ids.filtered(lambda t: t.status == 'completed'))
    
    @api.depends('patrol_ids')
    def _compute_patrols_completed(self):
        for record in self:
            record.patrols_completed = len(record.patrol_ids.filtered(lambda p: p.status == 'completed'))
    
    @api.depends('incident_ids')
    def _compute_incidents_reported(self):
        for record in self:
            record.incidents_reported = len(record.incident_ids)
    
    # Business Methods
    def action_check_in(self, location=None, photo=None):
        """Process guard check-in"""
        if self.status != 'scheduled':
            raise UserError(_("Cannot check in. Shift status is %s") % self.status)
        
        self.write({
            'status': 'in_progress',
            'check_in_time': fields.Datetime.now(),
            'check_in_location': location,
            'check_in_photo': photo
        })
        
        self.message_post(
            body=_("Guard checked in at %s") % location or "Unknown location"
        )
        
        # Create check-in activity
        self.activity_schedule(
            'guardpro.mail_activity_checkout_reminder',
            date_deadline=self.end_time,
            user_id=self.guard_id.user_id.id if self.guard_id.user_id else False,
            summary=_("Shift Check-out Reminder")
        )
    
    def action_check_out(self, location=None, photo=None):
        """Process guard check-out"""
        if self.status != 'in_progress':
            raise UserError(_("Cannot check out. Shift status is %s") % self.status)
        
        self.write({
            'status': 'completed',
            'check_out_time': fields.Datetime.now(),
            'check_out_location': location,
            'check_out_photo': photo
        })
        
        self.message_post(
            body=_("Guard checked out at %s") % location or "Unknown location"
        )
        
        # Mark activities as done
        self.activity_ids.filtered(
            lambda a: a.activity_type_id.name == 'Check-out Reminder'
        ).write({'state': 'done'})
    
    def action_cancel_shift(self, reason=None):
        """Cancel shift"""
        self.write({'status': 'cancelled'})
        
        self.message_post(
            body=_("Shift cancelled. Reason: %s") % reason or "No reason provided"
        )
        
        # Cancel related activities
        self.activity_ids.write({'state': 'cancelled'})
    
    # Constraints
    @api.constrains('start_time', 'end_time')
    def _check_time_consistency(self):
        for record in self:
            if record.start_time and record.end_time and record.start_time >= record.end_time:
                raise ValidationError(_("Start time must be before end time"))
    
    @api.constrains('scheduled_date', 'start_time')
    def _check_date_consistency(self):
        for record in self:
            if record.scheduled_date and record.start_time:
                if record.scheduled_date != record.start_time.date():
                    raise ValidationError(_("Scheduled date must match start time date"))
    
    # API Methods
    @api.model
    def create_shift_from_mobile(self, vals):
        """Create shift from mobile app"""
        # Validate mobile data
        required_fields = ['guard_id', 'site_id', 'start_time', 'end_time']
        for field in required_fields:
            if field not in vals:
                raise ValidationError(_("Missing required field: %s") % field)
        
        # Generate shift number
        if 'shift_number' not in vals:
            vals['shift_number'] = self._generate_shift_number()
        
        return self.create(vals)
    
    def _generate_shift_number(self):
        """Generate unique shift number"""
        today = fields.Date.today()
        count = self.search_count([
            ('scheduled_date', '=', today)
        ])
        return f"SH{today.strftime('%Y%m%d')}{count + 1:04d}"
```

### Incident Management Model

```python
# Incident management
class GuardIncident(models.Model):
    _name = 'guard.incident'
    _description = 'Security Incident'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'incident_date desc, incident_time desc'
    
    # Basic Information
    name = fields.Char(string='Incident Title', required=True, tracking=True)
    incident_number = fields.Char(string='Incident Number', required=True, unique=True, tracking=True)
    
    # Location and Assignment
    site_id = fields.Many2one('guard.site', string='Site', required=True, tracking=True)
    shift_id = fields.Many2one('guard.shift', string='Related Shift')
    client_id = fields.Many2one('res.partner', string='Client', related='site_id.client_id', store=True)
    
    # Incident Details
    incident_type = fields.Selection([
        ('security_breach', 'Security Breach'),
        ('theft', 'Theft'),
        ('vandalism', 'Vandalism'),
        ('medical', 'Medical Emergency'),
        ('fire', 'Fire/Safety'),
        ('equipment_failure', 'Equipment Failure'),
        ('unauthorized_access', 'Unauthorized Access'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('other', 'Other')
    ], string='Incident Type', required=True, tracking=True)
    
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Severity', default='medium', tracking=True)
    
    # Reporting Information
    reported_by = fields.Many2one('guard.profile', string='Reported By', required=True, tracking=True)
    reported_at = fields.Datetime(string='Reported At', default=fields.Datetime.now, tracking=True)
    incident_date = fields.Date(string='Incident Date', required=True, tracking=True)
    incident_time = fields.Datetime(string='Incident Time', required=True, tracking=True)
    
    # Description and Details
    description = fields.Text(string='Description', required=True, tracking=True)
    location_details = fields.Char(string='Location Details')
    weather_conditions = fields.Char(string='Weather Conditions')
    witnesses = fields.Text(string='Witnesses')
    
    # Evidence and Documentation
    photo_ids = fields.One2many('guard.incident.photo', 'incident_id', string='Photos')
    document_ids = fields.One2many('guard.incident.document', 'incident_id', string='Documents')
    video_ids = fields.One2many('guard.incident.video', 'incident_id', string='Videos')
    
    # Response and Resolution
    status = fields.Selection([
        ('reported', 'Reported'),
        ('investigating', 'Under Investigation'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('escalated', 'Escalated')
    ], string='Status', default='reported', tracking=True)
    
    assigned_to = fields.Many2one('res.users', string='Assigned To', tracking=True)
    response_time = fields.Float(string='Response Time (minutes)', compute='_compute_response_time')
    resolution_time = fields.Float(string='Resolution Time (hours)', compute='_compute_resolution_time')
    
    # Actions and Follow-up
    actions_taken = fields.Text(string='Actions Taken')
    resolution_notes = fields.Text(string='Resolution Notes')
    follow_up_required = fields.Boolean(string='Follow-up Required', default=False)
    follow_up_date = fields.Date(string='Follow-up Date')
    
    # External Notifications
    police_notified = fields.Boolean(string='Police Notified', default=False)
    emergency_services_called = fields.Boolean(string='Emergency Services Called', default=False)
    client_notified = fields.Boolean(string='Client Notified', default=False)
    
    # System Fields
    active = fields.Boolean(string='Active', default=True)
    
    # Computed Fields
    @api.depends('reported_at', 'assigned_to')
    def _compute_response_time(self):
        for record in self:
            if record.reported_at and record.assigned_to:
                # Calculate response time based on assignment
                assignment_time = record.write_date
                if assignment_time:
                    delta = assignment_time - record.reported_at
                    record.response_time = delta.total_seconds() / 60  # Convert to minutes
                else:
                    record.response_time = 0
            else:
                record.response_time = 0
    
    @api.depends('incident_time', 'status')
    def _compute_resolution_time(self):
        for record in self:
            if record.incident_time and record.status in ['resolved', 'closed']:
                resolution_time = record.write_date
                if resolution_time:
                    delta = resolution_time - record.incident_time
                    record.resolution_time = delta.total_seconds() / 3600  # Convert to hours
                else:
                    record.resolution_time = 0
            else:
                record.resolution_time = 0
    
    # Business Methods
    def action_assign_investigator(self, user_id):
        """Assign incident to investigator"""
        self.write({
            'assigned_to': user_id,
            'status': 'investigating'
        })
        
        self.message_post(
            body=_("Incident assigned to investigator: %s") % self.env['res.users'].browse(user_id).name
        )
        
        # Create investigation activity
        self.activity_schedule(
            'guardpro.mail_activity_investigation',
            date_deadline=fields.Date.today() + timedelta(days=3),
            user_id=user_id,
            summary=_("Investigate Incident: %s") % self.name
        )
    
    def action_resolve_incident(self, resolution_notes=None):
        """Mark incident as resolved"""
        self.write({
            'status': 'resolved',
            'resolution_notes': resolution_notes
        })
        
        self.message_post(
            body=_("Incident resolved. Resolution: %s") % resolution_notes or "No notes provided"
        )
        
        # Mark activities as done
        self.activity_ids.filtered(
            lambda a: a.activity_type_id.name == 'Investigation'
        ).write({'state': 'done'})
    
    def action_escalate_incident(self, reason=None):
        """Escalate incident"""
        self.write({'status': 'escalated'})
        
        self.message_post(
            body=_("Incident escalated. Reason: %s") % reason or "No reason provided"
        )
        
        # Notify management
        managers = self.env['res.users'].search([
            ('groups_id', 'in', self.env.ref('guardpro.group_guardpro_manager').id)
        ])
        
        for manager in managers:
            self.activity_schedule(
                'guardpro.mail_activity_escalation',
                date_deadline=fields.Date.today() + timedelta(days=1),
                user_id=manager.id,
                summary=_("Escalated Incident: %s") % self.name
            )
    
    # Constraints
    @api.constrains('incident_time', 'incident_date')
    def _check_incident_time(self):
        for record in self:
            if record.incident_time and record.incident_date:
                if record.incident_time.date() != record.incident_date:
                    raise ValidationError(_("Incident time date must match incident date"))
    
    @api.constrains('reported_at', 'incident_time')
    def _check_reporting_time(self):
        for record in self:
            if record.reported_at and record.incident_time:
                if record.reported_at < record.incident_time:
                    raise ValidationError(_("Report time cannot be before incident time"))
    
    # API Methods
    @api.model
    def create_incident_from_mobile(self, vals):
        """Create incident from mobile app"""
        # Validate mobile data
        required_fields = ['name', 'site_id', 'incident_type', 'description', 'reported_by']
        for field in required_fields:
            if field not in vals:
                raise ValidationError(_("Missing required field: %s") % field)
        
        # Generate incident number
        if 'incident_number' not in vals:
            vals['incident_number'] = self._generate_incident_number()
        
        # Set default values
        if 'incident_date' not in vals:
            vals['incident_date'] = fields.Date.today()
        if 'incident_time' not in vals:
            vals['incident_time'] = fields.Datetime.now()
        
        incident = self.create(vals)
        
        # Send notifications
        incident._send_incident_notifications()
        
        return incident
    
    def _generate_incident_number(self):
        """Generate unique incident number"""
        today = fields.Date.today()
        count = self.search_count([
            ('incident_date', '=', today)
        ])
        return f"INC{today.strftime('%Y%m%d')}{count + 1:04d}"
    
    def _send_incident_notifications(self):
        """Send incident notifications"""
        # Notify supervisors
        supervisors = self.site_id.supervisor_ids
        for supervisor in supervisors:
            self.activity_schedule(
                'guardpro.mail_activity_incident_notification',
                date_deadline=fields.Date.today() + timedelta(days=1),
                user_id=supervisor.id,
                summary=_("New Incident: %s") % self.name
            )
        
        # Send email notifications
        template = self.env.ref('guardpro.email_template_incident_notification')
        template.send_mail(self.id, force_send=True)
```

### Task Management Model

```python
# Task management
class GuardTask(models.Model):
    _name = 'guard.task'
    _description = 'Security Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, due_time'
    
    # Basic Information
    name = fields.Char(string='Task Name', required=True, tracking=True)
    description = fields.Text(string='Description', tracking=True)
    
    # Assignment Information
    shift_id = fields.Many2one('guard.shift', string='Related Shift', tracking=True)
    guard_id = fields.Many2one('guard.profile', string='Assigned Guard', related='shift_id.guard_id', store=True)
    site_id = fields.Many2one('guard.site', string='Site', related='shift_id.site_id', store=True)
    
    # Task Details
    task_type = fields.Selection([
        ('patrol', 'Patrol'),
        ('checkpoint', 'Checkpoint'),
        ('equipment_check', 'Equipment Check'),
        ('access_control', 'Access Control'),
        ('incident_response', 'Incident Response'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other')
    ], string='Task Type', required=True, tracking=True)
    
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string='Priority', default='medium', tracking=True)
    
    # Schedule Information
    scheduled_time = fields.Datetime(string='Scheduled Time', tracking=True)
    due_time = fields.Datetime(string='Due Time', tracking=True)
    estimated_duration = fields.Float(string='Estimated Duration (minutes)', tracking=True)
    
    # Status Information
    status = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('overdue', 'Overdue')
    ], string='Status', default='pending', tracking=True)
    
    # Completion Information
    started_at = fields.Datetime(string='Started At', tracking=True)
    completed_at = fields.Datetime(string='Completed At', tracking=True)
    completion_notes = fields.Text(string='Completion Notes')
    completion_photo = fields.Binary(string='Completion Photo')
    
    # Location Information
    location = fields.Char(string='Location')
    gps_coordinates = fields.Char(string='GPS Coordinates')
    
    # Checklist and Requirements
    checklist_ids = fields.One2many('guard.task.checklist', 'task_id', string='Checklist Items')
    required_actions = fields.Text(string='Required Actions')
    
    # System Fields
    active = fields.Boolean(string='Active', default=True)
    
    # Business Methods
    def action_start_task(self):
        """Start task execution"""
        if self.status != 'pending':
            raise UserError(_("Cannot start task. Current status is %s") % self.status)
        
        self.write({
            'status': 'in_progress',
            'started_at': fields.Datetime.now()
        })
        
        self.message_post(
            body=_("Task started")
        )
    
    def action_complete_task(self, notes=None, photo=None):
        """Complete task execution"""
        if self.status != 'in_progress':
            raise UserError(_("Cannot complete task. Current status is %s") % self.status)
        
        self.write({
            'status': 'completed',
            'completed_at': fields.Datetime.now(),
            'completion_notes': notes,
            'completion_photo': photo
        })
        
        self.message_post(
            body=_("Task completed. Notes: %s") % notes or "No notes provided"
        )
        
        # Mark activities as done
        self.activity_ids.write({'state': 'done'})
    
    def action_cancel_task(self, reason=None):
        """Cancel task"""
        self.write({'status': 'cancelled'})
        
        self.message_post(
            body=_("Task cancelled. Reason: %s") % reason or "No reason provided"
        )
        
        # Cancel related activities
        self.activity_ids.write({'state': 'cancelled'})
    
    # Constraints
    @api.constrains('scheduled_time', 'due_time')
    def _check_time_consistency(self):
        for record in self:
            if record.scheduled_time and record.due_time and record.scheduled_time > record.due_time:
                raise ValidationError(_("Scheduled time cannot be after due time"))
    
    # Cron Jobs
    @api.model
    def _check_overdue_tasks(self):
        """Check for overdue tasks"""
        overdue_tasks = self.search([
            ('status', 'in', ['pending', 'in_progress']),
            ('due_time', '<', fields.Datetime.now())
        ])
        
        for task in overdue_tasks:
            task.write({'status': 'overdue'})
            task.message_post(
                body=_("Task marked as overdue")
            )
            
            # Create overdue activity
            task.activity_schedule(
                'guardpro.mail_activity_overdue_task',
                date_deadline=fields.Date.today(),
                user_id=task.guard_id.user_id.id if task.guard_id.user_id else False,
                summary=_("Overdue Task: %s") % task.name
            )
```

## Model Relationships

### Entity Relationship Summary

```
GuardProfile (1) ←→ (M) GuardSite
    │                      │
    │                      │
    ▼                      ▼
GuardShift (1) ←→ (M) GuardTask
    │                      │
    │                      │
    ▼                      ▼
GuardIncident (M) ←→ (1) GuardSite
    │
    │
    ▼
GuardIncidentPhoto
GuardIncidentDocument
GuardIncidentVideo
```

### Key Relationships

1. **Guard-Site**: Many-to-many relationship allowing guards to work at multiple sites
2. **Shift-Task**: One-to-many relationship where each shift can have multiple tasks
3. **Site-Incident**: One-to-many relationship where each site can have multiple incidents
4. **Incident-Evidence**: One-to-many relationship for photos, documents, and videos

## Best Practices

### Model Design Best Practices

1. **Naming Conventions**
   - Use clear, descriptive model names
   - Follow Odoo naming conventions
   - Use consistent field naming patterns
   - Implement proper model descriptions

2. **Field Design**
   - Use appropriate field types for data
   - Implement proper constraints and validation
   - Add tracking for important fields
   - Use computed fields for derived data

3. **Security Implementation**
   - Implement proper access controls
   - Use record rules for data filtering
   - Add audit trails for sensitive operations
   - Validate user inputs

4. **Performance Optimization**
   - Use database indexes appropriately
   - Optimize computed field dependencies
   - Implement efficient search domains
   - Use proper field selection in queries

### Business Logic Best Practices

1. **Method Organization**
   - Group related methods together
   - Use clear, descriptive method names
   - Implement proper error handling
   - Add comprehensive documentation

2. **Validation and Constraints**
   - Implement field-level validation
   - Add model-level constraints
   - Validate business rules
   - Provide clear error messages

3. **Workflow Implementation**
   - Use status fields for state management
   - Implement proper state transitions
   - Add workflow validation
   - Create audit trails

4. **Integration Points**
   - Design for API integration
   - Implement webhook support
   - Add mobile app support
   - Create extensible interfaces

---

*GuardPro Models: Robust Data Foundation for Security Management*