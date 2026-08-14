# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, Command
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class GuardTaskCreateWizard(models.TransientModel):
    """Wizard to create tasks from templates"""
    _name = 'guard.task.create.wizard'
    _description = 'Create Task from Template'

    template_id = fields.Many2one(
        'guard.task.template',
        string='Template',
        required=True,
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
        ('inspection', 'Inspection'),
        ('maintenance_check', 'Maintenance Check'),
        ('safety_check', 'Safety Check'),
        ('visitor_log', 'Visitor Log'),
        ('equipment_check', 'Equipment Check'),
        ('incident_followup', 'Incident Follow-up'),
        ('training', 'Training Task'),
        ('documentation', 'Documentation'),
        ('other', 'Other')
    ], string='Task Type', required=True)
    
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True
    )
    assigned_to = fields.Many2one(
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
    
    due_date = fields.Datetime(
        string='Due Date',
        required=True
    )

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Load template values"""
        if self.template_id:
            self.name = self.template_id.name
            self.description = self.template_id.description
            self.task_type = self.template_id.task_type
            self.priority = self.template_id.priority

    def action_create_task(self):
        """Create task from wizard"""
        self.ensure_one()
        
        # Create task
        task_vals = {
            'name': self.name,
            'description': self.description,
            'task_type': self.task_type,
            'site_id': self.site_id.id,
            'assigned_to': self.assigned_to.id if self.assigned_to else False,
            'shift_id': self.shift_id.id if self.shift_id else False,
            'priority': self.priority,
            'due_date': self.due_date,
            'state': 'assigned' if self.assigned_to else 'draft',
            'template_id': self.template_id.id
        }
        
        task = self.env['guard.task'].create(task_vals)
        _logger.error(f"DEBUG: Wizard creating task ID {task.id} from template: {self.template_id.name}")
        
        # Create checklist items from template
        new_items = []
        
        # 1. Try checklist_template_ids (UAE templates)
        items = getattr(self.template_id, 'checklist_template_ids', [])
        if items:
            _logger.error(f"DEBUG: Wizard found {len(items)} items in checklist_template_ids")
            for item in items:
                new_items.append({
                    'task_id': task.id,
                    'sequence': item.sequence,
                    'name': item.name,
                    'mandatory': item.mandatory
                })
        
        # 2. Try checklist_ids (Alternative templates) if empty
        if not new_items:
            items = getattr(self.template_id, 'checklist_ids', [])
            if items:
                _logger.error(f"DEBUG: Wizard found {len(items)} items in checklist_ids")
                for item in items:
                    new_items.append({
                        'task_id': task.id,
                        'sequence': getattr(item, 'sequence', 10),
                        'name': item.name,
                        'mandatory': getattr(item, 'is_mandatory', True)
                    })
        
        if not new_items:
            _logger.error(f"DEBUG: Wizard found NO checklist items for template {self.template_id.name}!")
        
        for vals in new_items:
            self.env['guard.task.checklist'].create(vals)
            _logger.error(f"DEBUG: Wizard created checklist item: {vals['name']}")
        
        _logger.error(f"DEBUG: Wizard task creation complete.")
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'guard.task',
            'res_id': task.id,
            'view_mode': 'form',
            'target': 'current'
        }

