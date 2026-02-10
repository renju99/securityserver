# GuardPro Business Logic

## Overview

GuardPro's business logic layer implements the core security management workflows, automated processes, and business rules that drive the system's operations. This layer ensures data integrity, enforces business policies, and automates routine tasks.

## Business Logic Architecture

### Core Components

```
Business Logic Layer
├── Workflow Engines
│   ├── Shift Management Workflow
│   ├── Incident Response Workflow
│   ├── Task Assignment Workflow
│   └── Audit Workflow
├── Business Rules Engine
│   ├── Validation Rules
│   ├── Authorization Rules
│   ├── Data Integrity Rules
│   └── Compliance Rules
├── Automation Services
│   ├── Scheduled Tasks
│   ├── Event Handlers
│   ├── Notification Services
│   └── Integration Services
└── Business Services
    ├── Shift Management Service
    ├── Incident Management Service
    ├── Performance Analytics Service
    └── Compliance Service
```

## Workflow Management

### Shift Management Workflow

```python
# Shift Management Workflow
class ShiftWorkflowManager:
    def __init__(self, env):
        self.env = env
        self.workflow_states = {
            'scheduled': 'Scheduled',
            'in_progress': 'In Progress',
            'completed': 'Completed',
            'cancelled': 'Cancelled',
            'no_show': 'No Show'
        }
    
    def create_shift(self, shift_data):
        """Create new shift with validation"""
        # Validate shift data
        self._validate_shift_data(shift_data)
        
        # Check guard availability
        if not self._check_guard_availability(shift_data['guard_id'], shift_data['start_time']):
            raise UserError(_("Guard is not available for the selected time"))
        
        # Check site requirements
        if not self._check_site_requirements(shift_data['site_id'], shift_data['start_time']):
            raise UserError(_("Site requirements not met for the selected time"))
        
        # Create shift
        shift = self.env['guard.shift'].create(shift_data)
        
        # Initialize workflow
        self._initialize_shift_workflow(shift)
        
        # Send notifications
        self._send_shift_notifications(shift)
        
        return shift
    
    def process_check_in(self, shift_id, check_in_data):
        """Process guard check-in"""
        shift = self.env['guard.shift'].browse(shift_id)
        
        # Validate check-in
        if not self._validate_check_in(shift, check_in_data):
            raise UserError(_("Invalid check-in data"))
        
        # Update shift status
        shift.write({
            'status': 'in_progress',
            'check_in_time': fields.Datetime.now(),
            'check_in_location': check_in_data.get('location'),
            'check_in_photo': check_in_data.get('photo')
        })
        
        # Create tasks
        self._create_shift_tasks(shift)
        
        # Start monitoring
        self._start_shift_monitoring(shift)
        
        # Send notifications
        self._send_check_in_notifications(shift)
        
        return shift
    
    def process_check_out(self, shift_id, check_out_data):
        """Process guard check-out"""
        shift = self.env['guard.shift'].browse(shift_id)
        
        # Validate check-out
        if not self._validate_check_out(shift, check_out_data):
            raise UserError(_("Invalid check-out data"))
        
        # Complete pending tasks
        self._complete_pending_tasks(shift)
        
        # Update shift status
        shift.write({
            'status': 'completed',
            'check_out_time': fields.Datetime.now(),
            'check_out_location': check_out_data.get('location'),
            'check_out_photo': check_out_data.get('photo')
        })
        
        # Generate shift report
        self._generate_shift_report(shift)
        
        # Update performance metrics
        self._update_performance_metrics(shift)
        
        # Send notifications
        self._send_check_out_notifications(shift)
        
        return shift
    
    def _validate_shift_data(self, shift_data):
        """Validate shift creation data"""
        required_fields = ['guard_id', 'site_id', 'start_time', 'end_time']
        for field in required_fields:
            if field not in shift_data:
                raise ValidationError(_("Missing required field: %s") % field)
        
        if shift_data['start_time'] >= shift_data['end_time']:
            raise ValidationError(_("Start time must be before end time"))
    
    def _check_guard_availability(self, guard_id, start_time):
        """Check if guard is available for shift"""
        # Check for overlapping shifts
        overlapping_shifts = self.env['guard.shift'].search([
            ('guard_id', '=', guard_id),
            ('status', 'in', ['scheduled', 'in_progress']),
            ('start_time', '<=', start_time),
            ('end_time', '>', start_time)
        ])
        
        return len(overlapping_shifts) == 0
    
    def _check_site_requirements(self, site_id, start_time):
        """Check if site requirements are met"""
        site = self.env['guard.site'].browse(site_id)
        
        # Check security level requirements
        if site.security_level == 'critical':
            # Ensure experienced guard is assigned
            guard = self.env['guard.profile'].browse(site.guard_ids[0].id)
            if guard.performance_score < 80:
                return False
        
        return True
    
    def _initialize_shift_workflow(self, shift):
        """Initialize shift workflow"""
        # Create workflow instance
        workflow = self.env['guard.workflow'].create({
            'name': f"Shift Workflow - {shift.name}",
            'workflow_type': 'shift',
            'related_record_id': shift.id,
            'status': 'active'
        })
        
        # Create workflow steps
        steps = [
            {'name': 'Pre-shift Preparation', 'order': 1, 'status': 'pending'},
            {'name': 'Check-in', 'order': 2, 'status': 'pending'},
            {'name': 'Task Execution', 'order': 3, 'status': 'pending'},
            {'name': 'Patrol Activities', 'order': 4, 'status': 'pending'},
            {'name': 'Check-out', 'order': 5, 'status': 'pending'},
            {'name': 'Report Generation', 'order': 6, 'status': 'pending'}
        ]
        
        for step_data in steps:
            self.env['guard.workflow.step'].create({
                'workflow_id': workflow.id,
                **step_data
            })
    
    def _create_shift_tasks(self, shift):
        """Create tasks for shift"""
        # Get site-specific tasks
        site_tasks = self.env['guard.task.template'].search([
            ('site_id', '=', shift.site_id.id),
            ('is_active', '=', True)
        ])
        
        for template in site_tasks:
            task = self.env['guard.task'].create({
                'name': template.name,
                'description': template.description,
                'task_type': template.task_type,
                'priority': template.priority,
                'shift_id': shift.id,
                'site_id': shift.site_id.id,
                'scheduled_time': shift.start_time,
                'due_time': shift.start_time + timedelta(minutes=template.estimated_duration),
                'estimated_duration': template.estimated_duration,
                'required_actions': template.required_actions
            })
            
            # Create checklist items
            for item_template in template.checklist_ids:
                self.env['guard.task.checklist'].create({
                    'task_id': task.id,
                    'name': item_template.name,
                    'description': item_template.description,
                    'is_required': item_template.is_required
                })
    
    def _start_shift_monitoring(self, shift):
        """Start monitoring shift activities"""
        # Create monitoring record
        monitoring = self.env['guard.shift.monitoring'].create({
            'shift_id': shift.id,
            'start_time': fields.Datetime.now(),
            'status': 'active'
        })
        
        # Schedule monitoring tasks
        self.env['ir.cron'].create({
            'name': f"Monitor Shift {shift.id}",
            'model_id': self.env.ref('guardpro.model_guard_shift').id,
            'state': 'code',
            'code': f'model._monitor_shift({shift.id})',
            'interval_number': 15,
            'interval_type': 'minutes',
            'numbercall': -1,
            'active': True
        })
    
    def _generate_shift_report(self, shift):
        """Generate shift report"""
        report_data = {
            'shift_id': shift.id,
            'guard_name': shift.guard_id.name,
            'site_name': shift.site_id.name,
            'start_time': shift.start_time,
            'end_time': shift.end_time,
            'duration': shift.duration,
            'tasks_completed': shift.tasks_completed,
            'patrols_completed': shift.patrols_completed,
            'incidents_reported': shift.incidents_reported,
            'performance_score': self._calculate_shift_performance(shift)
        }
        
        # Create report
        report = self.env['guard.shift.report'].create(report_data)
        
        # Generate PDF
        pdf_report = self.env['report'].get_pdf([report.id], 'guardpro.shift_report_template')
        
        # Store report
        report.write({'pdf_report': pdf_report})
        
        return report
    
    def _calculate_shift_performance(self, shift):
        """Calculate shift performance score"""
        score = 100  # Base score
        
        # Deduct for late check-in
        if shift.check_in_time > shift.start_time:
            delay_minutes = (shift.check_in_time - shift.start_time).total_seconds() / 60
            if delay_minutes > 15:
                score -= min(delay_minutes * 0.5, 20)  # Max 20 point deduction
        
        # Deduct for incomplete tasks
        total_tasks = len(shift.task_ids)
        if total_tasks > 0:
            completed_tasks = len(shift.task_ids.filtered(lambda t: t.status == 'completed'))
            completion_rate = completed_tasks / total_tasks
            score -= (1 - completion_rate) * 30  # Max 30 point deduction
        
        # Deduct for missed patrols
        total_patrols = len(shift.patrol_ids)
        if total_patrols > 0:
            completed_patrols = len(shift.patrol_ids.filtered(lambda p: p.status == 'completed'))
            patrol_rate = completed_patrols / total_patrols
            score -= (1 - patrol_rate) * 25  # Max 25 point deduction
        
        # Bonus for early completion
        if shift.check_out_time and shift.check_out_time < shift.end_time:
            early_minutes = (shift.end_time - shift.check_out_time).total_seconds() / 60
            if early_minutes > 30:
                score += min(early_minutes * 0.1, 10)  # Max 10 point bonus
        
        return max(score, 0)  # Ensure score doesn't go below 0
```

### Incident Response Workflow

```python
# Incident Response Workflow
class IncidentWorkflowManager:
    def __init__(self, env):
        self.env = env
        self.workflow_states = {
            'reported': 'Reported',
            'investigating': 'Under Investigation',
            'resolved': 'Resolved',
            'closed': 'Closed',
            'escalated': 'Escalated'
        }
    
    def create_incident(self, incident_data):
        """Create new incident with workflow"""
        # Validate incident data
        self._validate_incident_data(incident_data)
        
        # Create incident
        incident = self.env['guard.incident'].create(incident_data)
        
        # Initialize workflow
        self._initialize_incident_workflow(incident)
        
        # Assess severity and priority
        self._assess_incident_severity(incident)
        
        # Send notifications
        self._send_incident_notifications(incident)
        
        # Auto-assign if possible
        self._auto_assign_investigator(incident)
        
        return incident
    
    def process_incident_response(self, incident_id, response_data):
        """Process incident response"""
        incident = self.env['guard.incident'].browse(incident_id)
        
        # Update incident with response data
        incident.write({
            'status': 'investigating',
            'assigned_to': response_data.get('assigned_to'),
            'actions_taken': response_data.get('actions_taken')
        })
        
        # Create investigation tasks
        self._create_investigation_tasks(incident)
        
        # Update workflow
        self._update_incident_workflow(incident, 'investigating')
        
        # Send notifications
        self._send_investigation_notifications(incident)
        
        return incident
    
    def resolve_incident(self, incident_id, resolution_data):
        """Resolve incident"""
        incident = self.env['guard.incident'].browse(incident_id)
        
        # Validate resolution
        if not self._validate_resolution(incident, resolution_data):
            raise UserError(_("Invalid resolution data"))
        
        # Update incident
        incident.write({
            'status': 'resolved',
            'resolution_notes': resolution_data.get('resolution_notes'),
            'actions_taken': resolution_data.get('actions_taken')
        })
        
        # Complete investigation tasks
        self._complete_investigation_tasks(incident)
        
        # Update workflow
        self._update_incident_workflow(incident, 'resolved')
        
        # Generate resolution report
        self._generate_resolution_report(incident)
        
        # Send notifications
        self._send_resolution_notifications(incident)
        
        return incident
    
    def escalate_incident(self, incident_id, escalation_data):
        """Escalate incident"""
        incident = self.env['guard.incident'].browse(incident_id)
        
        # Update incident
        incident.write({
            'status': 'escalated',
            'escalation_reason': escalation_data.get('reason')
        })
        
        # Update workflow
        self._update_incident_workflow(incident, 'escalated')
        
        # Notify management
        self._notify_management(incident)
        
        # Create escalation tasks
        self._create_escalation_tasks(incident)
        
        return incident
    
    def _validate_incident_data(self, incident_data):
        """Validate incident creation data"""
        required_fields = ['name', 'site_id', 'incident_type', 'description', 'reported_by']
        for field in required_fields:
            if field not in incident_data:
                raise ValidationError(_("Missing required field: %s") % field)
    
    def _assess_incident_severity(self, incident):
        """Assess incident severity and priority"""
        severity_score = 0
        
        # Base severity by type
        type_severity = {
            'security_breach': 4,
            'theft': 3,
            'vandalism': 2,
            'medical': 5,
            'fire': 5,
            'equipment_failure': 2,
            'unauthorized_access': 3,
            'suspicious_activity': 2,
            'other': 1
        }
        
        severity_score += type_severity.get(incident.incident_type, 1)
        
        # Adjust based on site security level
        site_severity = {
            'low': 0,
            'medium': 1,
            'high': 2,
            'critical': 3
        }
        
        severity_score += site_severity.get(incident.site_id.security_level, 0)
        
        # Adjust based on time of day
        incident_hour = incident.incident_time.hour
        if incident_hour < 6 or incident_hour > 22:  # Night time
            severity_score += 1
        
        # Determine severity level
        if severity_score >= 6:
            incident.severity = 'critical'
        elif severity_score >= 4:
            incident.severity = 'high'
        elif severity_score >= 2:
            incident.severity = 'medium'
        else:
            incident.severity = 'low'
    
    def _auto_assign_investigator(self, incident):
        """Auto-assign investigator based on rules"""
        # Get available supervisors
        supervisors = self.env['res.users'].search([
            ('groups_id', 'in', self.env.ref('guardpro.group_guardpro_supervisor').id),
            ('active', '=', True)
        ])
        
        # Filter by site assignment
        site_supervisors = supervisors.filtered(
            lambda s: incident.site_id.id in s.site_ids.ids
        )
        
        if site_supervisors:
            # Assign to supervisor with least active incidents
            assigned_to = min(site_supervisors, key=lambda s: s.active_incident_count)
            incident.write({
                'assigned_to': assigned_to.id,
                'status': 'investigating'
            })
            
            # Create assignment notification
            self._create_assignment_notification(incident, assigned_to)
    
    def _create_investigation_tasks(self, incident):
        """Create investigation tasks"""
        task_templates = self.env['guard.investigation.task.template'].search([
            ('incident_type', '=', incident.incident_type),
            ('severity', '=', incident.severity),
            ('is_active', '=', True)
        ])
        
        for template in task_templates:
            task = self.env['guard.investigation.task'].create({
                'name': template.name,
                'description': template.description,
                'incident_id': incident.id,
                'assigned_to': incident.assigned_to.id,
                'due_date': fields.Date.today() + timedelta(days=template.due_days),
                'priority': template.priority
            })
            
            # Create checklist items
            for item_template in template.checklist_ids:
                self.env['guard.investigation.task.checklist'].create({
                    'task_id': task.id,
                    'name': item_template.name,
                    'description': item_template.description,
                    'is_required': item_template.is_required
                })
    
    def _generate_resolution_report(self, incident):
        """Generate incident resolution report"""
        report_data = {
            'incident_id': incident.id,
            'incident_number': incident.incident_number,
            'incident_type': incident.incident_type,
            'severity': incident.severity,
            'site_name': incident.site_id.name,
            'reported_by': incident.reported_by.name,
            'assigned_to': incident.assigned_to.name,
            'incident_time': incident.incident_time,
            'resolution_time': incident.resolution_time,
            'actions_taken': incident.actions_taken,
            'resolution_notes': incident.resolution_notes
        }
        
        # Create report
        report = self.env['guard.incident.resolution.report'].create(report_data)
        
        # Generate PDF
        pdf_report = self.env['report'].get_pdf([report.id], 'guardpro.incident_resolution_report_template')
        
        # Store report
        report.write({'pdf_report': pdf_report})
        
        return report
```

### Task Assignment Workflow

```python
# Task Assignment Workflow
class TaskWorkflowManager:
    def __init__(self, env):
        self.env = env
    
    def assign_tasks_to_shift(self, shift_id, task_templates):
        """Assign tasks to shift based on templates"""
        shift = self.env['guard.shift'].browse(shift_id)
        
        assigned_tasks = []
        
        for template in task_templates:
            # Create task from template
            task = self.env['guard.task'].create({
                'name': template.name,
                'description': template.description,
                'task_type': template.task_type,
                'priority': template.priority,
                'shift_id': shift.id,
                'site_id': shift.site_id.id,
                'scheduled_time': self._calculate_scheduled_time(shift, template),
                'due_time': self._calculate_due_time(shift, template),
                'estimated_duration': template.estimated_duration,
                'required_actions': template.required_actions,
                'location': template.location
            })
            
            # Create checklist items
            for item_template in template.checklist_ids:
                self.env['guard.task.checklist'].create({
                    'task_id': task.id,
                    'name': item_template.name,
                    'description': item_template.description,
                    'is_required': item_template.is_required,
                    'order': item_template.order
                })
            
            assigned_tasks.append(task)
        
        # Send task assignment notifications
        self._send_task_assignment_notifications(shift, assigned_tasks)
        
        return assigned_tasks
    
    def auto_assign_tasks(self, shift_id):
        """Automatically assign tasks based on site requirements"""
        shift = self.env['guard.shift'].browse(shift_id)
        
        # Get site-specific task templates
        site_templates = self.env['guard.task.template'].search([
            ('site_id', '=', shift.site_id.id),
            ('is_active', '=', True),
            ('auto_assign', '=', True)
        ])
        
        # Filter by shift time and requirements
        applicable_templates = self._filter_applicable_templates(site_templates, shift)
        
        # Assign tasks
        assigned_tasks = self.assign_tasks_to_shift(shift_id, applicable_templates)
        
        return assigned_tasks
    
    def _calculate_scheduled_time(self, shift, template):
        """Calculate scheduled time for task"""
        if template.scheduled_time_offset:
            return shift.start_time + timedelta(minutes=template.scheduled_time_offset)
        else:
            return shift.start_time
    
    def _calculate_due_time(self, shift, template):
        """Calculate due time for task"""
        if template.due_time_offset:
            return shift.start_time + timedelta(minutes=template.due_time_offset)
        else:
            return shift.start_time + timedelta(minutes=template.estimated_duration)
    
    def _filter_applicable_templates(self, templates, shift):
        """Filter templates applicable to shift"""
        applicable = []
        
        for template in templates:
            # Check time requirements
            if template.required_time_start and template.required_time_end:
                shift_hour = shift.start_time.hour
                if not (template.required_time_start <= shift_hour <= template.required_time_end):
                    continue
            
            # Check day requirements
            if template.required_days:
                shift_day = shift.start_time.weekday()
                if shift_day not in template.required_days:
                    continue
            
            # Check frequency requirements
            if template.frequency == 'daily':
                applicable.append(template)
            elif template.frequency == 'weekly':
                if shift.start_time.weekday() == template.weekly_day:
                    applicable.append(template)
            elif template.frequency == 'monthly':
                if shift.start_time.day == template.monthly_day:
                    applicable.append(template)
        
        return applicable
    
    def _send_task_assignment_notifications(self, shift, tasks):
        """Send task assignment notifications"""
        # Notify guard
        if shift.guard_id.user_id:
            self.env['mail.message'].create({
                'model': 'guard.shift',
                'res_id': shift.id,
                'subject': _('Tasks Assigned for Shift'),
                'body': _('You have been assigned %d tasks for your shift.') % len(tasks),
                'partner_ids': [(4, shift.guard_id.user_id.partner_id.id)],
                'message_type': 'notification'
            })
        
        # Notify supervisor
        supervisors = shift.site_id.supervisor_ids
        for supervisor in supervisors:
            self.env['mail.message'].create({
                'model': 'guard.shift',
                'res_id': shift.id,
                'subject': _('Tasks Assigned to Guard'),
                'body': _('Tasks have been assigned to guard %s for shift.') % shift.guard_id.name,
                'partner_ids': [(4, supervisor.partner_id.id)],
                'message_type': 'notification'
            })
```

## Business Rules Engine

### Validation Rules

```python
# Business Validation Rules
class BusinessValidationRules:
    def __init__(self, env):
        self.env = env
    
    def validate_guard_assignment(self, guard_id, site_id, start_time):
        """Validate guard assignment to site"""
        # Check guard availability
        if not self._check_guard_availability(guard_id, start_time):
            raise ValidationError(_("Guard is not available for the selected time"))
        
        # Check site requirements
        if not self._check_site_requirements(guard_id, site_id):
            raise ValidationError(_("Guard does not meet site requirements"))
        
        # Check guard skills
        if not self._check_guard_skills(guard_id, site_id):
            raise ValidationError(_("Guard does not have required skills for this site"))
        
        return True
    
    def validate_incident_severity(self, incident_data):
        """Validate incident severity assignment"""
        severity = incident_data.get('severity')
        incident_type = incident_data.get('incident_type')
        
        # Critical incidents must be certain types
        if severity == 'critical':
            critical_types = ['security_breach', 'medical', 'fire']
            if incident_type not in critical_types:
                raise ValidationError(_("Only certain incident types can be marked as critical"))
        
        # Medical incidents must be high or critical
        if incident_type == 'medical' and severity not in ['high', 'critical']:
            raise ValidationError(_("Medical incidents must be marked as high or critical severity"))
        
        return True
    
    def validate_shift_schedule(self, shift_data):
        """Validate shift scheduling"""
        start_time = shift_data.get('start_time')
        end_time = shift_data.get('end_time')
        
        # Check shift duration
        if start_time and end_time:
            duration = (end_time - start_time).total_seconds() / 3600
            if duration > 12:
                raise ValidationError(_("Shift duration cannot exceed 12 hours"))
            if duration < 1:
                raise ValidationError(_("Shift duration must be at least 1 hour"))
        
        # Check for overlapping shifts
        if not self._check_shift_overlap(shift_data):
            raise ValidationError(_("Shift overlaps with existing shift"))
        
        return True
    
    def _check_guard_availability(self, guard_id, start_time):
        """Check guard availability"""
        # Check for overlapping shifts
        overlapping = self.env['guard.shift'].search([
            ('guard_id', '=', guard_id),
            ('status', 'in', ['scheduled', 'in_progress']),
            ('start_time', '<=', start_time),
            ('end_time', '>', start_time)
        ])
        
        return len(overlapping) == 0
    
    def _check_site_requirements(self, guard_id, site_id):
        """Check site requirements"""
        site = self.env['guard.site'].browse(site_id)
        guard = self.env['guard.profile'].browse(guard_id)
        
        # Check security level requirements
        if site.security_level == 'critical':
            if guard.performance_score < 85:
                return False
        
        # Check certification requirements
        required_certifications = site.required_certifications
        if required_certifications:
            guard_certifications = guard.certifications_ids.mapped('name')
            for cert in required_certifications:
                if cert not in guard_certifications:
                    return False
        
        return True
    
    def _check_guard_skills(self, guard_id, site_id):
        """Check guard skills"""
        site = self.env['guard.site'].browse(site_id)
        guard = self.env['guard.profile'].browse(guard_id)
        
        # Check required skills
        required_skills = site.required_skills
        if required_skills:
            guard_skills = guard.skills_ids.mapped('name')
            for skill in required_skills:
                if skill not in guard_skills:
                    return False
        
        return True
    
    def _check_shift_overlap(self, shift_data):
        """Check for shift overlap"""
        guard_id = shift_data.get('guard_id')
        start_time = shift_data.get('start_time')
        end_time = shift_data.get('end_time')
        
        if not all([guard_id, start_time, end_time]):
            return True
        
        # Check for overlapping shifts
        overlapping = self.env['guard.shift'].search([
            ('guard_id', '=', guard_id),
            ('status', 'in', ['scheduled', 'in_progress']),
            ('id', '!=', shift_data.get('id', 0)),
            '|',
            ('start_time', '<=', start_time, 'end_time', '>', start_time),
            ('start_time', '<', end_time, 'end_time', '>=', end_time)
        ])
        
        return len(overlapping) == 0
```

### Authorization Rules

```python
# Authorization Rules
class AuthorizationRules:
    def __init__(self, env):
        self.env = env
    
    def check_guard_access(self, user_id, guard_id):
        """Check if user can access guard record"""
        user = self.env['res.users'].browse(user_id)
        guard = self.env['guard.profile'].browse(guard_id)
        
        # Admin can access all guards
        if user.has_group('guardpro.group_guardpro_admin'):
            return True
        
        # Manager can access guards at their sites
        if user.has_group('guardpro.group_guardpro_manager'):
            manager_sites = user.site_ids.ids
            guard_sites = guard.site_ids.ids
            return bool(set(manager_sites) & set(guard_sites))
        
        # Supervisor can access guards at their sites
        if user.has_group('guardpro.group_guardpro_supervisor'):
            supervisor_sites = user.site_ids.ids
            guard_sites = guard.site_ids.ids
            return bool(set(supervisor_sites) & set(guard_sites))
        
        # Guard can only access their own record
        if user.has_group('guardpro.group_guardpro_guard'):
            return guard.user_id.id == user_id
        
        return False
    
    def check_incident_access(self, user_id, incident_id):
        """Check if user can access incident record"""
        user = self.env['res.users'].browse(user_id)
        incident = self.env['guard.incident'].browse(incident_id)
        
        # Admin can access all incidents
        if user.has_group('guardpro.group_guardpro_admin'):
            return True
        
        # Manager can access incidents at their sites
        if user.has_group('guardpro.group_guardpro_manager'):
            manager_sites = user.site_ids.ids
            return incident.site_id.id in manager_sites
        
        # Supervisor can access incidents at their sites
        if user.has_group('guardpro.group_guardpro_supervisor'):
            supervisor_sites = user.site_ids.ids
            return incident.site_id.id in supervisor_sites
        
        # Guard can access incidents they reported
        if user.has_group('guardpro.group_guardpro_guard'):
            return incident.reported_by.user_id.id == user_id
        
        # Client can access incidents at their sites
        if user.has_group('guardpro.group_guardpro_client'):
            client_sites = user.client_site_ids.ids
            return incident.site_id.id in client_sites
        
        return False
    
    def check_shift_access(self, user_id, shift_id):
        """Check if user can access shift record"""
        user = self.env['res.users'].browse(user_id)
        shift = self.env['guard.shift'].browse(shift_id)
        
        # Admin can access all shifts
        if user.has_group('guardpro.group_guardpro_admin'):
            return True
        
        # Manager can access shifts at their sites
        if user.has_group('guardpro.group_guardpro_manager'):
            manager_sites = user.site_ids.ids
            return shift.site_id.id in manager_sites
        
        # Supervisor can access shifts at their sites
        if user.has_group('guardpro.group_guardpro_supervisor'):
            supervisor_sites = user.site_ids.ids
            return shift.site_id.id in supervisor_sites
        
        # Guard can access their own shifts
        if user.has_group('guardpro.group_guardpro_guard'):
            return shift.guard_id.user_id.id == user_id
        
        return False
```

## Automation Services

### Scheduled Tasks

```python
# Scheduled Task Manager
class ScheduledTaskManager:
    def __init__(self, env):
        self.env = env
    
    def create_scheduled_tasks(self):
        """Create all scheduled tasks"""
        tasks = [
            {
                'name': 'Check Overdue Tasks',
                'model_id': self.env.ref('guardpro.model_guard_task').id,
                'state': 'code',
                'code': 'model._check_overdue_tasks()',
                'interval_number': 15,
                'interval_type': 'minutes',
                'active': True
            },
            {
                'name': 'Generate Daily Reports',
                'model_id': self.env.ref('guardpro.model_guard_daily_report').id,
                'state': 'code',
                'code': 'model._generate_daily_reports()',
                'interval_number': 1,
                'interval_type': 'days',
                'active': True
            },
            {
                'name': 'Update Performance Metrics',
                'model_id': self.env.ref('guardpro.model_guard_performance').id,
                'state': 'code',
                'code': 'model._update_performance_metrics()',
                'interval_number': 1,
                'interval_type': 'hours',
                'active': True
            },
            {
                'name': 'Send Shift Reminders',
                'model_id': self.env.ref('guardpro.model_guard_shift').id,
                'state': 'code',
                'code': 'model._send_shift_reminders()',
                'interval_number': 30,
                'interval_type': 'minutes',
                'active': True
            }
        ]
        
        for task_data in tasks:
            self.env['ir.cron'].create(task_data)
    
    def _check_overdue_tasks(self):
        """Check for overdue tasks"""
        overdue_tasks = self.env['guard.task'].search([
            ('status', 'in', ['pending', 'in_progress']),
            ('due_time', '<', fields.Datetime.now())
        ])
        
        for task in overdue_tasks:
            task.write({'status': 'overdue'})
            
            # Create overdue notification
            self.env['mail.message'].create({
                'model': 'guard.task',
                'res_id': task.id,
                'subject': _('Task Overdue'),
                'body': _('Task "%s" is overdue.') % task.name,
                'partner_ids': [(4, task.guard_id.user_id.partner_id.id)],
                'message_type': 'notification'
            })
    
    def _generate_daily_reports(self):
        """Generate daily reports"""
        yesterday = fields.Date.today() - timedelta(days=1)
        
        # Get all active sites
        sites = self.env['guard.site'].search([('active', '=', True)])
        
    for site in sites:
            # Generate site daily report
            report = self.env['guard.daily.report'].create({
                'site_id': site.id,
                'report_date': yesterday,
                'status': 'draft'
            })
            
            # Generate report content
            report._generate_report_content()
            
            # Send to stakeholders
            report._send_report()
    
    def _update_performance_metrics(self):
        """Update performance metrics"""
        # Update guard performance
        guards = self.env['guard.profile'].search([('active', '=', True)])
        
        for guard in guards:
            # Calculate performance score
            performance_score = self._calculate_guard_performance(guard)
            guard.write({'performance_score': performance_score})
            
            # Calculate attendance rate
            attendance_rate = self._calculate_attendance_rate(guard)
            guard.write({'attendance_rate': attendance_rate})
    
    def _send_shift_reminders(self):
        """Send shift reminders"""
        # Get shifts starting in next 30 minutes
        reminder_time = fields.Datetime.now() + timedelta(minutes=30)
        
        upcoming_shifts = self.env['guard.shift'].search([
            ('status', '=', 'scheduled'),
            ('start_time', '<=', reminder_time),
            ('start_time', '>', fields.Datetime.now())
        ])
        
        for shift in upcoming_shifts:
            # Send reminder to guard
            if shift.guard_id.user_id:
                self.env['mail.message'].create({
                    'model': 'guard.shift',
                    'res_id': shift.id,
                    'subject': _('Shift Reminder'),
                    'body': _('Your shift starts in 30 minutes at %s.') % shift.site_id.name,
                    'partner_ids': [(4, shift.guard_id.user_id.partner_id.id)],
                    'message_type': 'notification'
                })
```

### Event Handlers

```python
# Event Handler Manager
class EventHandlerManager:
    def __init__(self, env):
        self.env = env
    
    def register_event_handlers(self):
        """Register event handlers"""
        handlers = [
            {
                'event_type': 'guard.checkin',
                'handler': self._handle_guard_checkin
            },
            {
                'event_type': 'guard.checkout',
                'handler': self._handle_guard_checkout
            },
            {
                'event_type': 'incident.reported',
                'handler': self._handle_incident_reported
            },
            {
                'event_type': 'task.completed',
                'handler': self._handle_task_completed
            }
        ]
        
        for handler_data in handlers:
            self.env['guard.event.handler'].create(handler_data)
    
    def _handle_guard_checkin(self, event_data):
        """Handle guard check-in event"""
        shift_id = event_data.get('shift_id')
        check_in_data = event_data.get('check_in_data')
        
        # Update shift status
        shift = self.env['guard.shift'].browse(shift_id)
        shift.write({
            'status': 'in_progress',
            'check_in_time': fields.Datetime.now(),
            'check_in_location': check_in_data.get('location'),
            'check_in_photo': check_in_data.get('photo')
        })
        
        # Create tasks
        self.env['guard.shift.workflow'].browse(shift_id)._create_shift_tasks()
        
        # Send notifications
        self._send_checkin_notifications(shift)
    
    def _handle_guard_checkout(self, event_data):
        """Handle guard check-out event"""
        shift_id = event_data.get('shift_id')
        check_out_data = event_data.get('check_out_data')
        
        # Update shift status
        shift = self.env['guard.shift'].browse(shift_id)
        shift.write({
            'status': 'completed',
            'check_out_time': fields.Datetime.now(),
            'check_out_location': check_out_data.get('location'),
            'check_out_photo': check_out_data.get('photo')
        })
        
        # Generate shift report
        self.env['guard.shift.workflow'].browse(shift_id)._generate_shift_report()
        
        # Send notifications
        self._send_checkout_notifications(shift)
    
    def _handle_incident_reported(self, event_data):
        """Handle incident reported event"""
        incident_id = event_data.get('incident_id')
        
        # Update incident status
        incident = self.env['guard.incident'].browse(incident_id)
        
        # Assess severity
        self.env['guard.incident.workflow'].browse(incident_id)._assess_incident_severity()
        
        # Auto-assign investigator
        self.env['guard.incident.workflow'].browse(incident_id)._auto_assign_investigator()
        
        # Send notifications
        self._send_incident_notifications(incident)
    
    def _handle_task_completed(self, event_data):
        """Handle task completed event"""
        task_id = event_data.get('task_id')
        
        # Update task status
        task = self.env['guard.task'].browse(task_id)
        task.write({'status': 'completed'})
        
        # Update shift progress
        if task.shift_id:
            self._update_shift_progress(task.shift_id)
        
        # Send notifications
        self._send_task_completion_notifications(task)
```

## Best Practices

### Business Logic Best Practices

1. **Separation of Concerns**
   - Keep business logic separate from views
   - Use service classes for complex operations
   - Implement proper error handling
   - Maintain clear interfaces

2. **Workflow Design**
   - Design clear workflow states
   - Implement proper state transitions
   - Add validation at each step
   - Provide rollback mechanisms

3. **Performance Optimization**
   - Use bulk operations where possible
   - Implement proper caching
   - Optimize database queries
   - Monitor performance metrics

4. **Error Handling**
   - Implement comprehensive error handling
   - Provide meaningful error messages
   - Log errors for debugging
   - Implement retry mechanisms

### Code Organization

1. **Modular Design**
   - Use clear class hierarchies
   - Implement proper inheritance
   - Maintain consistent naming
   - Document complex logic

2. **Testing**
   - Write unit tests for business logic
   - Implement integration tests
   - Use test fixtures
   - Maintain test coverage

3. **Documentation**
   - Document business rules
   - Explain workflow logic
   - Provide usage examples
   - Maintain API documentation

---

*GuardPro Business Logic: Robust Workflow Management for Security Operations*