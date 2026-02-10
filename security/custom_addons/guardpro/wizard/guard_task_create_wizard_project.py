# -*- coding: utf-8 -*-
"""Guard Task Creation Wizard - Using Native Project Module."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GuardTaskCreateWizard(models.TransientModel):
    """Wizard to create guard tasks (project.task) from templates."""
    
    _name = 'guard.task.create.wizard.project'
    _description = 'Create Guard Task from Template (Project)'

    template_id = fields.Many2one(
        'guard.task.template',
        string='Template',
        help='Task template to use'
    )
    
    name = fields.Char(
        string='Task Name',
        required=True
    )
    
    description = fields.Html(
        string='Description'
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
    
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True
    )
    
    assigned_guard_id = fields.Many2one(
        'guard.profile',
        string='Assigned Guard'
    )
    
    shift_id = fields.Many2one(
        'guard.shift',
        string='Related Shift'
    )
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Priority', default='1')
    
    date_deadline = fields.Datetime(
        string='Deadline',
        required=True,
        default=fields.Datetime.now
    )
    
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        default=lambda self: self._default_project(),
        required=True
    )
    
    create_checklist = fields.Boolean(
        string='Create Checklist Items',
        default=True,
        help='Create checklist items from template'
    )
    
    @api.model
    def _default_project(self):
        """Get or create Guard Operations project."""
        guard_project = self.env['project.project'].search([
            ('is_guard_operations', '=', True)
        ], limit=1)
        
        if not guard_project:
            guard_project = self.env['project.project'].create({
                'name': 'Guard Operations',
                'is_guard_operations': True,
                'privacy_visibility': 'employees',
            })
        
        return guard_project
    
    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Load template values."""
        if self.template_id:
            self.name = self.template_id.name
            self.description = self.template_id.description
            self.task_type = self.template_id.task_type
            self.priority = self.template_id.priority
    
    @api.onchange('shift_id')
    def _onchange_shift_id(self):
        """Auto-fill from shift."""
        if self.shift_id:
            self.site_id = self.shift_id.site_id
            self.assigned_guard_id = self.shift_id.guard_id
            # Set deadline to middle of shift
            if self.shift_id.start_datetime and self.shift_id.end_datetime:
                duration = (self.shift_id.end_datetime - self.shift_id.start_datetime) / 2
                self.date_deadline = self.shift_id.start_datetime + duration
    
    def action_create_task(self):
        """Create guard task from wizard."""
        self.ensure_one()
        
        # Prepare task values
        task_vals = {
            'name': self.name,
            'description': self.description,
            'is_guard_task': True,
            'task_type': self.task_type,
            'site_id': self.site_id.id,
            'assigned_guard_id': self.assigned_guard_id.id if self.assigned_guard_id else False,
            'shift_id': self.shift_id.id if self.shift_id else False,
            'priority': self.priority,
            'date_deadline': self.date_deadline,
            'project_id': self.project_id.id,
            'task_template_id': self.template_id.id if self.template_id else False,
        }
        
        # Set user_ids (assigned users) for project.task
        if self.assigned_guard_id and self.assigned_guard_id.user_id:
            task_vals['user_ids'] = [(4, self.assigned_guard_id.user_id.id)]
        
        # Create task
        task = self.env['project.task'].create(task_vals)
        
        # Create checklist items from template
        if self.create_checklist and self.template_id and self.template_id.checklist_template_ids:
            for item in self.template_id.checklist_template_ids:
                self.env['guard.task.checklist'].create({
                    'task_id': task.id,
                    'sequence': item.sequence,
                    'name': item.name,
                    'mandatory': item.mandatory
                })
        
        # Post creation message
        task.message_post(
            body=_('Guard task created from template: %s') % (
                self.template_id.name if self.template_id else 'Manual'
            ),
            subject=_('Task Created'),
            message_type='notification'
        )
        
        # Return action to view created task
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': task.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_ref': 'guardpro.view_guard_task_form'}
        }
    
    def action_create_and_new(self):
        """Create task and open wizard again."""
        self.action_create_task()
        
        # Return wizard again
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'guard.task.create.wizard.project',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_site_id': self.site_id.id,
                'default_shift_id': self.shift_id.id if self.shift_id else False,
            }
        }


class GuardTaskBulkCreateWizard(models.TransientModel):
    """Wizard to bulk create guard tasks for multiple guards/sites."""
    
    _name = 'guard.task.bulk.create.wizard'
    _description = 'Bulk Create Guard Tasks'
    
    template_id = fields.Many2one(
        'guard.task.template',
        string='Template',
        required=True
    )
    
    site_ids = fields.Many2many(
        'client.site',
        string='Sites',
        required=True
    )
    
    guard_ids = fields.Many2many(
        'guard.profile',
        string='Assigned Guards'
    )
    
    date_deadline = fields.Datetime(
        string='Deadline',
        required=True
    )
    
    create_per_site = fields.Boolean(
        string='One Task Per Site',
        default=True,
        help='Create one task for each site'
    )
    
    create_per_guard = fields.Boolean(
        string='One Task Per Guard',
        default=False,
        help='Create one task for each guard'
    )
    
    def action_create_tasks(self):
        """Bulk create tasks."""
        self.ensure_one()
        
        tasks_created = []
        
        if self.create_per_site:
            # Create one task per site
            for site in self.site_ids:
                task = self._create_task_from_template(site=site)
                tasks_created.append(task)
        
        elif self.create_per_guard:
            # Create one task per guard
            for guard in self.guard_ids:
                for site in self.site_ids:
                    task = self._create_task_from_template(site=site, guard=guard)
                    tasks_created.append(task)
        
        else:
            # Create one task for all
            task = self._create_task_from_template(
                site=self.site_ids[0] if self.site_ids else False
            )
            tasks_created.append(task)
        
        # Return action to view created tasks
        return {
            'type': 'ir.actions.act_window',
            'name': _('Created Guard Tasks'),
            'res_model': 'project.task',
            'view_mode': 'list,kanban,form',
            'domain': [('id', 'in', [t.id for t in tasks_created])],
            'context': {'is_guard_task': True}
        }
    
    def _create_task_from_template(self, site=None, guard=None):
        """Helper to create a single task from template."""
        task_vals = {
            'name': self.template_id.name,
            'description': self.template_id.description,
            'is_guard_task': True,
            'task_type': self.template_id.task_type,
            'site_id': site.id if site else False,
            'assigned_guard_id': guard.id if guard else False,
            'priority': self.template_id.priority,
            'date_deadline': self.date_deadline,
            'task_template_id': self.template_id.id,
        }
        
        # Get guard operations project
        guard_project = self.env['project.project'].search([
            ('is_guard_operations', '=', True)
        ], limit=1)
        
        if guard_project:
            task_vals['project_id'] = guard_project.id
        
        # Set user if guard has user
        if guard and guard.user_id:
            task_vals['user_ids'] = [(4, guard.user_id.id)]
        
        # Create task
        task = self.env['project.task'].create(task_vals)
        
        # Create checklist items
        if self.template_id.checklist_template_ids:
            for item in self.template_id.checklist_template_ids:
                self.env['guard.task.checklist'].create({
                    'task_id': task.id,
                    'sequence': item.sequence,
                    'name': item.name,
                    'mandatory': item.mandatory
                })
        
        return task

