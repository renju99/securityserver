# -*- coding: utf-8 -*-
"""Guard Task Management - Using Native Project Module."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    """Extend Odoo's native project.task for guard task/post order management."""

    _inherit = 'project.task'

    # Guard Task Identification
    is_guard_task = fields.Boolean(
        string='Guard Task/Post Order',
        default=False,
        help='Mark this as a security guard task or post order'
    )
    
    # Guard-Specific Fields
    task_type = fields.Selection([
        ('patrol', 'Patrol'),
        ('access_control', 'Access Control Check'),
        ('equipment_check', 'Equipment Check'),
        ('safety_inspection', 'Safety Inspection'),
        ('visitor_screening', 'Visitor Screening'),
        ('incident_response', 'Incident Response'),
        ('maintenance_check', 'Maintenance Check'),
        ('emergency_drill', 'Emergency Drill'),
        ('key_handover', 'Key Handover'),
        ('report_submission', 'Report Submission'),
        ('training_exercise', 'Training Exercise'),
        ('other', 'Other')
    ], string='Task Type', help='Type of guard duty or post order')
    
    # Site and Guard Assignment
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        tracking=True,
        index=True,
        help='Site where the task should be performed'
    )
    
    assigned_guard_id = fields.Many2one(
        'guard.profile',
        string='Assigned Guard',
        tracking=True,
        index=True,
        help='Guard responsible for completing this task'
    )
    
    shift_id = fields.Many2one(
        'guard.shift',
        string='Related Shift',
        tracking=True,
        help='Shift during which this task should be completed'
    )
    
    # Completion Fields
    completion_notes = fields.Text(
        string='Completion Notes',
        help='Notes added by the guard upon task completion'
    )
    
    completion_photo = fields.Image(
        string='Completion Photo',
        max_width=1024,
        max_height=1024,
        help='Photo evidence of task completion'
    )
    
    completion_photo_2 = fields.Image(
        string='Additional Photo 1',
        max_width=1024,
        max_height=1024,
        help='Additional photo evidence'
    )
    
    completion_photo_3 = fields.Image(
        string='Additional Photo 2',
        max_width=1024,
        max_height=1024,
        help='Additional photo evidence'
    )
    
    completed_date = fields.Datetime(
        string='Completed Date',
        readonly=True,
        tracking=True,
        help='Actual date and time when the task was completed'
    )
    
    completed_by_user = fields.Many2one(
        'res.users',
        string='Completed By',
        readonly=True
    )
    
    # Checklist (using native project.task subtasks or custom)
    checklist_ids = fields.One2many(
        'guard.task.checklist',
        'task_id',
        string='Guard Checklist Items',
        help='Checklist items specific to guard tasks'
    )
    
    checklist_completion_percentage = fields.Float(
        string='Checklist Completion %',
        compute='_compute_checklist_stats',
        store=True,
        help='Percentage of checklist items completed'
    )
    
    total_checklist_items = fields.Integer(
        string='Total Checklist',
        compute='_compute_checklist_stats',
        store=True
    )
    
    completed_checklist_items = fields.Integer(
        string='Completed Checklist',
        compute='_compute_checklist_stats',
        store=True
    )
    
    # Recurrence (use if creating from templates)
    task_template_id = fields.Many2one(
        'guard.task.template',
        string='Created from Template',
        readonly=True,
        help='Template used to create this task'
    )
    
    # Override/extend native fields defaults for guard tasks
    @api.model
    def default_get(self, fields_list):
        """Set defaults for guard tasks."""
        res = super().default_get(fields_list)
        
        # If creating from guard task context, set default project
        if self.env.context.get('default_is_guard_task'):
            # Try to find or create "Guard Operations" project
            guard_project = self.env['project.project'].search([
                ('name', '=', 'Guard Operations'),
                ('is_guard_operations', '=', True)
            ], limit=1)
            
            if not guard_project:
                # Auto-create guard operations project
                guard_project = self.env['project.project'].create({
                    'name': 'Guard Operations',
                    'is_guard_operations': True,
                    'privacy_visibility': 'employees',
                })
            
            res['project_id'] = guard_project.id
        
        return res
    
    @api.depends('checklist_ids', 'checklist_ids.completed')
    def _compute_checklist_stats(self):
        """Calculate checklist completion statistics."""
        for task in self:
            if task.is_guard_task:
                total = len(task.checklist_ids)
                if total > 0:
                    completed = len(task.checklist_ids.filtered(lambda x: x.completed))
                    task.total_checklist_items = total
                    task.completed_checklist_items = completed
                    task.checklist_completion_percentage = (completed / total) * 100
                else:
                    task.total_checklist_items = 0
                    task.completed_checklist_items = 0
                    task.checklist_completion_percentage = 0.0
            else:
                task.total_checklist_items = 0
                task.completed_checklist_items = 0
                task.checklist_completion_percentage = 0.0
    
    @api.constrains('date_deadline', 'shift_id')
    def _check_deadline_shift(self):
        """Validate deadline is within shift time."""
        for task in self:
            if task.is_guard_task and task.date_deadline and task.shift_id:
                deadline_datetime = fields.Datetime.from_string(task.date_deadline)
                if not (task.shift_id.start_datetime <= deadline_datetime <= task.shift_id.end_datetime):
                    raise ValidationError(
                        _('Task deadline must be within the shift period (%s - %s)') % (
                            task.shift_id.start_datetime,
                            task.shift_id.end_datetime
                        )
                    )
    
    def action_guard_task_complete(self):
        """Complete guard task with validation."""
        self.ensure_one()
        
        if not self.is_guard_task:
            return super().action_done() if hasattr(super(), 'action_done') else True
        
        # Check if all mandatory checklist items are completed
        incomplete_mandatory = self.checklist_ids.filtered(
            lambda x: x.mandatory and not x.completed
        )
        
        if incomplete_mandatory:
            raise UserError(
                _('Please complete all mandatory checklist items before marking task as complete:\n%s') % 
                '\n'.join(['- ' + item.name for item in incomplete_mandatory])
            )
        
        # Update task
        self.write({
            'completed_date': fields.Datetime.now(),
            'completed_by_user': self.env.user.id,
        })
        
        # Mark as done in project (native)
        if hasattr(self, 'action_done'):
            self.action_done()
        else:
            # Find "Done" stage
            done_stage = self.env['project.task.type'].search([
                ('project_ids', 'in', [self.project_id.id]),
                ('fold', '=', True)
            ], limit=1)
            if done_stage:
                self.stage_id = done_stage.id
        
        # Post completion message
        notes_section = Markup('')
        if self.completion_notes:
            notes_section = Markup('<p>Notes: %s</p>') % Markup.escape(self.completion_notes)
        message_body = Markup(
            '<p>✅ <strong>Task Completed</strong></p>'
            '<p>Completed by: %s<br/>'
            'Completed on: %s</p>%s'
        ) % (
            Markup.escape(self.env.user.name),
            fields.Datetime.now(),
            notes_section
        )
        self.message_post(
            body=message_body,
            subject=_('Guard Task Completed'),
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )
        
        _logger.info('Guard task %s completed by user %s', self.name, self.env.user.name)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Task marked as complete!'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_view_shift(self):
        """View related shift."""
        self.ensure_one()
        if not self.shift_id:
            raise UserError(_('No shift linked to this task.'))
        
        return {
            'name': _('Related Shift'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.shift',
            'view_mode': 'form',
            'res_id': self.shift_id.id,
            'target': 'current',
        }
    
    def action_view_site(self):
        """View related site."""
        self.ensure_one()
        if not self.site_id:
            raise UserError(_('No site linked to this task.'))
        
        return {
            'name': _('Site Details'),
            'type': 'ir.actions.act_window',
            'res_model': 'client.site',
            'view_mode': 'form',
            'res_id': self.site_id.id,
            'target': 'current',
        }
    
    @api.model
    def send_overdue_guard_task_alerts(self):
        """Cron job: Send alerts for overdue guard tasks."""
        overdue_tasks = self.search([
            ('is_guard_task', '=', True),
            ('date_deadline', '<', fields.Datetime.now()),
            ('stage_id.fold', '=', False),  # Not in "Done" stages
        ])
        
        for task in overdue_tasks:
            # Create activity for assigned user or supervisor
            activity_user = task.user_ids[0] if task.user_ids else self.env.user
            
            task.activity_schedule(
                'mail.mail_activity_data_warning',
                summary=_('⚠️ Overdue Guard Task: %s') % task.name,
                user_id=activity_user.id,
                note=_('Task assigned to %s is overdue.\n'
                       'Site: %s\n'
                       'Due date: %s\n'
                       'Task type: %s') % (
                    task.assigned_guard_id.name if task.assigned_guard_id else 'Unassigned',
                    task.site_id.name if task.site_id else 'N/A',
                    task.date_deadline,
                    dict(task._fields['task_type'].selection).get(task.task_type, 'N/A')
                )
            )
        
        _logger.info('Sent overdue alerts for %d guard tasks', len(overdue_tasks))
        return True


class GuardTaskChecklist(models.Model):
    """Task Checklist Item for Guard Tasks."""
    
    _name = 'guard.task.checklist'
    _description = 'Guard Task Checklist Item'
    _order = 'sequence, id'
    
    task_id = fields.Many2one(
        'project.task',
        string='Task',
        required=True,
        ondelete='cascade',
        index=True,
        domain=[('is_guard_task', '=', True)]
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of checklist items'
    )
    
    name = fields.Char(
        string='Checklist Item',
        required=True,
        help='Description of the checklist item'
    )
    
    completed = fields.Boolean(
        string='Completed',
        default=False,
        help='Mark as completed'
    )
    
    mandatory = fields.Boolean(
        string='Mandatory',
        default=True,
        help='Must be completed before task can be marked as complete'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes for this checklist item'
    )
    
    completed_date = fields.Datetime(
        string='Completed Date',
        readonly=True
    )
    
    completed_by = fields.Many2one(
        'res.users',
        string='Completed By',
        readonly=True
    )
    
    photo = fields.Image(
        string='Photo',
        max_width=512,
        max_height=512,
        help='Photo evidence for this checklist item'
    )
    
    def toggle_completed(self):
        """Toggle completion status."""
        for item in self:
            if item.completed:
                item.write({
                    'completed': False,
                    'completed_date': False,
                    'completed_by': False
                })
            else:
                item.write({
                    'completed': True,
                    'completed_date': fields.Datetime.now(),
                    'completed_by': self.env.user.id
                })
        
        # Refresh task completion percentage
        self.mapped('task_id')._compute_checklist_stats()
        
        return True
    
    def action_add_photo(self):
        """Action to add photo evidence."""
        self.ensure_one()
        return {
            'name': _('Add Photo Evidence'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.task.checklist',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


class GuardTaskTemplate(models.Model):
    """Task Template for recurring guard tasks."""
    
    _name = 'guard.task.template'
    _description = 'Guard Task Template'
    _order = 'name'
    
    name = fields.Char(
        string='Template Name',
        required=True,
        help='Name of the task template'
    )
    
    description = fields.Html(
        string='Description',
        help='Default description for tasks created from this template'
    )
    
    task_type = fields.Selection([
        ('patrol', 'Patrol'),
        ('access_control', 'Access Control Check'),
        ('equipment_check', 'Equipment Check'),
        ('safety_inspection', 'Safety Inspection'),
        ('visitor_screening', 'Visitor Screening'),
        ('incident_response', 'Incident Response'),
        ('maintenance_check', 'Maintenance Check'),
        ('emergency_drill', 'Emergency Drill'),
        ('key_handover', 'Key Handover'),
        ('report_submission', 'Report Submission'),
        ('training_exercise', 'Training Exercise'),
        ('other', 'Other')
    ], string='Task Type', required=True, default='other')
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Default Priority', default='1')
    
    site_ids = fields.Many2many(
        'client.site',
        string='Applicable Sites',
        help='Sites where this template is applicable'
    )
    
    checklist_template_ids = fields.One2many(
        'guard.task.checklist.template',
        'template_id',
        string='Checklist Template'
    )
    
    estimated_duration = fields.Float(
        string='Estimated Duration (hours)',
        help='Estimated time to complete this task'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    def action_create_task(self):
        """Create task from template."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'guard.task.create.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
                'default_name': self.name,
                'default_description': self.description,
                'default_task_type': self.task_type,
                'default_priority': self.priority
            }
        }


class GuardTaskChecklistTemplate(models.Model):
    """Checklist Template for task templates."""
    
    _name = 'guard.task.checklist.template'
    _description = 'Guard Task Checklist Template'
    _order = 'sequence, id'
    
    template_id = fields.Many2one(
        'guard.task.template',
        string='Task Template',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    name = fields.Char(
        string='Checklist Item',
        required=True
    )
    
    mandatory = fields.Boolean(
        string='Mandatory',
        default=True
    )


class ProjectProject(models.Model):
    """Extend project.project for guard operations."""
    
    _inherit = 'project.project'
    
    is_guard_operations = fields.Boolean(
        string='Guard Operations Project',
        default=False,
        help='This project is used for guard tasks and post orders'
    )
    
    responsible_sites = fields.Many2many(
        'client.site',
        string='Responsible Sites',
        help='Sites managed by this project'
    )

