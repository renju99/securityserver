# -*- coding: utf-8 -*-
"""Smart Task Suggestion System for GuardLink."""

from odoo import models, fields, api, Command
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class GuardTaskTemplate(models.Model):
    """Task templates for recurring and common tasks."""
    
    _name = 'guard.task.template'
    _inherit = 'guard.task.template'
    _description = 'Guard Task Template'
    _order = 'sequence, name'

    name = fields.Char(
        string='Template Name',
        required=True,
        index=True
    )
    description = fields.Html(
        string='Description Template'
    )
    task_type = fields.Selection([
        ('patrol', 'Patrol'),
        ('inspection', 'Inspection'),
        ('maintenance_check', 'Maintenance Check'),
        ('safety_check', 'Safety Check'),
        ('visitor_log', 'Visitor Log'),
        ('equipment_check', 'Equipment Check'),
        ('incident_followup', 'Incident Follow-up'),
        ('training', 'Training Task'),
        ('documentation', 'Documentation'),
        ('other', 'Other')
    ], string='Task Type', required=True, default='patrol')
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Default Priority', default='1')
    
    estimated_duration = fields.Float(
        string='Estimated Duration (hours)',
        default=0.5
    )
    
    site_id = fields.Many2one(
        'client.site',
        string='Specific Project',
        help='Leave empty for all sites'
    )
    
    checklist_ids = fields.One2many(
        'guard.task.checklist.item',
        'template_id',
        string='Checklist Items'
    )
    
    is_recurring = fields.Boolean(
        string='Recurring Task',
        default=False
    )
    recurrence_type = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom')
    ], string='Recurrence Type')
    
    recurrence_hour = fields.Integer(
        string='Recurrence Hour (0-23)',
        default=8,
        help='Hour of day for task suggestion'
    )
    
    weekdays = fields.Selection([
        ('all', 'All Days'),
        ('weekdays', 'Weekdays Only'),
        ('weekends', 'Weekends Only'),
        ('custom', 'Custom')
    ], string='Days of Week', default='all')
    
    custom_weekdays = fields.Char(
        string='Custom Weekdays',
        help='Comma-separated: 0=Monday, 6=Sunday (e.g., "0,2,4" for Mon,Wed,Fri)'
    )
    
    context_triggers = fields.Selection([
        ('time', 'Time-Based'),
        ('location', 'Location-Based'),
        ('weather', 'Weather-Based'),
        ('event', 'Event-Based'),
        ('manual', 'Manual Only')
    ], string='Trigger Type', default='time')
    
    trigger_location_ids = fields.Many2many(
        'checkpoint',
        string='Trigger Locations',
        help='Suggest when guard is near these locations'
    )
    
    trigger_distance = fields.Integer(
        string='Trigger Distance (meters)',
        default=50,
        help='Suggest task when within this distance'
    )
    
    auto_assign = fields.Boolean(
        string='Auto-Assign',
        default=False,
        help='Automatically create and assign task (no suggestion)'
    )
    
    requires_photo = fields.Boolean(
        string='Requires Photo Evidence',
        default=False
    )
    
    requires_signature = fields.Boolean(
        string='Requires Signature',
        default=False
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    # Dependencies
    dependency_ids = fields.Many2many(
        'guard.task.template',
        'task_template_dependency_rel',
        'template_id',
        'dependency_id',
        string='Depends On Templates',
        help='Tasks that must be completed before this one'
    )
    
    @api.constrains('recurrence_hour')
    def _check_recurrence_hour(self):
        """Validate recurrence hour."""
        for record in self:
            if record.recurrence_hour and (record.recurrence_hour < 0 or record.recurrence_hour > 23):
                raise ValidationError('Recurrence hour must be between 0 and 23')


class GuardTaskChecklistItem(models.Model):
    """Checklist items for task templates."""
    
    _name = 'guard.task.checklist.item'
    _description = 'Task Checklist Item'
    _order = 'sequence, name'

    template_id = fields.Many2one(
        'guard.task.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char(
        string='Checklist Item',
        required=True
    )
    description = fields.Text(
        string='Description'
    )
    is_mandatory = fields.Boolean(
        string='Mandatory',
        default=True
    )
    requires_photo = fields.Boolean(
        string='Requires Photo',
        default=False
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )


class GuardTaskSuggestion(models.Model):
    """Task suggestions for guards based on context."""
    
    _name = 'guard.task.suggestion'
    _description = 'Guard Task Suggestion'
    _order = 'suggested_at desc'

    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade',
        index=True
    )
    template_id = fields.Many2one(
        'guard.task.template',
        string='Task Template',
        required=True,
        ondelete='cascade'
    )
    suggested_reason = fields.Text(
        string='Suggestion Reason',
        help='Why this task was suggested'
    )
    suggested_at = fields.Datetime(
        string='Suggested At',
        default=fields.Datetime.now,
        required=True
    )
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('dismissed', 'Dismissed'),
        ('snoozed', 'Snoozed'),
        ('expired', 'Expired')
    ], string='Status', default='pending', required=True, index=True)
    
    snoozed_until = fields.Datetime(
        string='Snoozed Until'
    )
    
    accepted_at = fields.Datetime(
        string='Accepted At'
    )
    dismissed_at = fields.Datetime(
        string='Dismissed At'
    )
    
    created_task_id = fields.Many2one(
        'guard.task',
        string='Created Task',
        help='Task created when suggestion was accepted'
    )
    
    # Context data
    current_location_lat = fields.Float(
        string='Location Latitude',
        digits=(10, 7)
    )
    current_location_lon = fields.Float(
        string='Location Longitude',
        digits=(10, 7)
    )
    current_site_id = fields.Many2one(
        'client.site',
        string='Current Project'
    )
    
    def accept_suggestion(self):
        """Accept suggestion and create task."""
        self.ensure_one()
        
        if self.status != 'pending':
            raise ValidationError('Can only accept pending suggestions')
        
        # Create task from template
        Task = self.env['guard.task']
        task = Task.create({
            'name': self.template_id.name,
            'description': self.template_id.description,
            'task_type': self.template_id.task_type,
            'priority': self.template_id.priority,
            'assigned_to': self.guard_id.id,
            'site_id': self.current_site_id.id if self.current_site_id else self.guard_id.current_site_id.id,
            'state': 'assigned',
            'due_date': fields.Date.today() + timedelta(days=1)
        })
        
        # Update suggestion
        self.write({
            'status': 'accepted',
            'accepted_at': fields.Datetime.now(),
            'created_task_id': task.id
        })
        
        return task
    
    def dismiss_suggestion(self):
        """Dismiss suggestion."""
        self.ensure_one()
        
        self.write({
            'status': 'dismissed',
            'dismissed_at': fields.Datetime.now()
        })
    
    def snooze_suggestion(self, hours=1):
        """Snooze suggestion for specified hours."""
        self.ensure_one()
        
        self.write({
            'status': 'snoozed',
            'snoozed_until': fields.Datetime.now() + timedelta(hours=hours)
        })
    
    @api.model
    def generate_suggestions(self, guard_id, context=None):
        """Generate task suggestions for a guard based on context."""
        guard = self.env['guard.profile'].browse(guard_id)
        if not guard.exists():
            return []
        
        context = context or {}
        current_time = fields.Datetime.now()
        current_hour = current_time.hour
        current_weekday = current_time.weekday()
        
        suggestions = []
        
        # Get applicable templates (site-scoped + intentional globals)
        Template = self.env['guard.task.template']
        allowed_sites = list(guard.user_id.site_ids.ids) if guard.user_id else []
        if guard.user_id and guard.user_id.has_group('guardpro.group_guardpro_admin'):
            template_domain = [('active', '=', True)]
        else:
            template_domain = [
                ('active', '=', True),
                '|',
                ('site_id', '=', False),
                ('site_id', 'in', allowed_sites),
            ]
        templates = Template.search(template_domain)
        
        for template in templates:
            # Check if already suggested recently
            existing = self.search([
                ('guard_id', '=', guard_id),
                ('template_id', '=', template.id),
                ('suggested_at', '>=', fields.Datetime.now() - timedelta(hours=24)),
                ('status', 'in', ['pending', 'snoozed'])
            ])
            if existing:
                continue
            
            # Time-based suggestions
            if template.context_triggers == 'time' and template.is_recurring:
                if current_hour == template.recurrence_hour:
                    # Check weekday match
                    if self._check_weekday_match(template, current_weekday):
                        reason = f"Scheduled for {template.recurrence_hour:02d}:00"
                        suggestions.append(self._create_suggestion(guard_id, template, reason, context))
            
            # Location-based suggestions
            elif template.context_triggers == 'location' and context.get('latitude') and context.get('longitude'):
                if template.trigger_location_ids:
                    for location in template.trigger_location_ids:
                        distance = self._calculate_distance(
                            context['latitude'], context['longitude'],
                            location.latitude, location.longitude
                        )
                        if distance <= template.trigger_distance:
                            reason = f"You're near {location.name}"
                            suggestions.append(self._create_suggestion(guard_id, template, reason, context))
                            break
        
        return suggestions
    
    def _check_weekday_match(self, template, weekday):
        """Check if current weekday matches template recurrence."""
        if template.weekdays == 'all':
            return True
        elif template.weekdays == 'weekdays':
            return weekday < 5  # Monday-Friday
        elif template.weekdays == 'weekends':
            return weekday >= 5  # Saturday-Sunday
        elif template.weekdays == 'custom' and template.custom_weekdays:
            custom_days = [int(d.strip()) for d in template.custom_weekdays.split(',')]
            return weekday in custom_days
        return False
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two coordinates in meters."""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371000  # Earth radius in meters
        
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)
        
        a = sin(delta_lat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    def _create_suggestion(self, guard_id, template, reason, context):
        """Create a suggestion record."""
        return self.create({
            'guard_id': guard_id,
            'template_id': template.id,
            'suggested_reason': reason,
            'current_location_lat': context.get('latitude'),
            'current_location_lon': context.get('longitude'),
            'current_site_id': context.get('site_id'),
            'status': 'pending'
        })
    
    @api.model
    def cleanup_expired_suggestions(self):
        """Cron job to mark old suggestions as expired."""
        cutoff_time = fields.Datetime.now() - timedelta(hours=24)
        
        expired = self.search([
            ('status', '=', 'pending'),
            ('suggested_at', '<', cutoff_time)
        ])
        
        expired.write({'status': 'expired'})
        
        _logger.info(f'Marked {len(expired)} suggestions as expired')


class GuardTaskDependency(models.Model):
    """Task dependencies - tasks that must be completed before others."""
    
    _name = 'guard.task.dependency'
    _description = 'Guard Task Dependency'

    task_id = fields.Many2one(
        'guard.task',
        string='Task',
        required=True,
        ondelete='cascade',
        index=True
    )
    depends_on_task_id = fields.Many2one(
        'guard.task',
        string='Depends On Task',
        required=True,
        ondelete='cascade'
    )
    dependency_type = fields.Selection([
        ('blocking', 'Blocking - Must complete first'),
        ('recommended', 'Recommended - Better to complete first'),
        ('related', 'Related - Good to know')
    ], string='Dependency Type', default='blocking', required=True)
    
    is_satisfied = fields.Boolean(
        string='Dependency Satisfied',
        compute='_compute_is_satisfied',
        store=True
    )
    
    @api.depends('depends_on_task_id.state')
    def _compute_is_satisfied(self):
        """Check if dependency is satisfied."""
        for record in self:
            record.is_satisfied = record.depends_on_task_id.state == 'completed'


# Extend guard.task model with new fields
class GuardTask(models.Model):
    """Extend guard.task with suggestion and template features."""
    
    _inherit = 'guard.task'

    template_id = fields.Many2one(
        'guard.task.template',
        string='Created from Template',
        help='Template used to create this task',
        ondelete='set null'
    )

    @api.onchange('template_id')
    def _onchange_template_id_suggestion(self):
        """Auto-populate task from template (In Suggestion Extension)"""
        if self.template_id:
            _logger.error(f"DEBUG_SUGGESTION: Template selected: {self.template_id.name}")
            
            # Update task fields
            self.name = self.template_id.name
            # Use getattr for description because the template model might have different field names
            self.description = getattr(self.template_id, 'description', self.name)
            self.task_type = self.template_id.task_type
            self.priority = self.template_id.priority
            
            # Add checklist items from template
            new_items = []
            
            # 1. Try checklist_template_ids (UAE templates)
            items = getattr(self.template_id, 'checklist_template_ids', [])
            if items:
                _logger.error(f"DEBUG_SUGGESTION: Found {len(items)} items in checklist_template_ids")
                for item in items:
                    new_items.append(Command.create({
                        'sequence': item.sequence,
                        'name': item.name,
                        'mandatory': item.mandatory,
                    }))
            
            # 2. Try checklist_ids (Alternative templates) if empty
            if not new_items:
                items = getattr(self.template_id, 'checklist_ids', [])
                if items:
                    _logger.error(f"DEBUG_SUGGESTION: Found {len(items)} items in checklist_ids")
                    for item in items:
                        new_items.append(Command.create({
                            'sequence': getattr(item, 'sequence', 10),
                            'name': item.name,
                            'mandatory': getattr(item, 'is_mandatory', True),
                        }))
            
            if not new_items:
                _logger.error(f"DEBUG_SUGGESTION: No checklist items found for {self.template_id.name}")
            
            # Set items
            self.checklist_ids = [Command.clear()] + new_items
    
    suggestion_id = fields.Many2one(
        'guard.task.suggestion',
        string='Created from Suggestion',
        help='Suggestion that created this task'
    )
    
    dependency_ids = fields.One2many(
        'guard.task.dependency',
        'task_id',
        string='Dependencies'
    )
    
    has_blocking_dependencies = fields.Boolean(
        string='Has Blocking Dependencies',
        compute='_compute_blocking_dependencies',
        store=True
    )
    
    can_start = fields.Boolean(
        string='Can Start Task',
        compute='_compute_can_start',
        store=True,
        help='All blocking dependencies are satisfied'
    )
    
    completion_notes_voice = fields.Binary(
        string='Voice Completion Notes',
        help='Voice recording for task completion'
    )
    
    voice_notes_text = fields.Text(
        string='Voice Notes Transcription',
        help='Transcribed text from voice notes'
    )
    
    @api.depends('dependency_ids', 'dependency_ids.dependency_type')
    def _compute_blocking_dependencies(self):
        """Check if task has blocking dependencies."""
        for record in self:
            record.has_blocking_dependencies = bool(
                record.dependency_ids.filtered(lambda d: d.dependency_type == 'blocking')
            )
    
    @api.depends('dependency_ids', 'dependency_ids.is_satisfied')
    def _compute_can_start(self):
        """Check if all blocking dependencies are satisfied."""
        for record in self:
            blocking_deps = record.dependency_ids.filtered(
                lambda d: d.dependency_type == 'blocking'
            )
            
            if not blocking_deps:
                record.can_start = True
            else:
                record.can_start = all(dep.is_satisfied for dep in blocking_deps)

