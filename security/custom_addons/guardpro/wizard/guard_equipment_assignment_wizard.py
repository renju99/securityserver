# -*- coding: utf-8 -*-
"""Guard Equipment Assignment Wizard."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GuardEquipmentAssignmentWizard(models.TransientModel):
    """Wizard to assign equipment to guards."""
    
    _name = 'guard.equipment.assignment.wizard'
    _description = 'Guard Equipment Assignment Wizard'
    
    equipment_id = fields.Many2one(
        'maintenance.equipment',
        string='Equipment',
        required=True,
        readonly=True
    )
    
    current_guard_id = fields.Many2one(
        'guard.profile',
        string='Currently Assigned To',
        readonly=True
    )
    
    current_site_id = fields.Many2one(
        'client.site',
        string='Current Project',
        readonly=True
    )
    
    new_guard_id = fields.Many2one(
        'guard.profile',
        string='Assign To Guard',
        required=True
    )
    
    new_site_id = fields.Many2one(
        'client.site',
        string='Assign To Site'
    )
    
    assignment_date = fields.Date(
        string='Assignment Date',
        required=True,
        default=fields.Date.today
    )
    
    condition = fields.Selection([
        ('new', 'New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ], string='Equipment Condition', required=True, default='good')
    
    notes = fields.Text(
        string='Notes'
    )
    
    action_type = fields.Selection([
        ('new_assignment', 'New Assignment'),
        ('transfer', 'Transfer to Another Guard'),
    ], string='Action Type', compute='_compute_action_type')
    
    @api.depends('current_guard_id')
    def _compute_action_type(self):
        """Determine if this is a new assignment or transfer."""
        for record in self:
            record.action_type = 'transfer' if record.current_guard_id else 'new_assignment'
    
    def action_confirm_assignment(self):
        """Confirm the equipment assignment."""
        self.ensure_one()
        
        # If transferring from another guard, return first
        if self.current_guard_id:
            # Create return history
            self.env['guard.equipment.assignment.history'].create({
                'equipment_id': self.equipment_id.id,
                'guard_id': self.current_guard_id.id,
                'site_id': self.current_site_id.id if self.current_site_id else False,
                'assignment_date': self.equipment_id.assignment_date or fields.Date.today(),
                'return_date': fields.Date.today(),
                'action_type': 'returned',
                'condition_at_return': self.condition,
            })
        
        # Create new assignment history
        self.env['guard.equipment.assignment.history'].create({
            'equipment_id': self.equipment_id.id,
            'guard_id': self.new_guard_id.id,
            'site_id': self.new_site_id.id if self.new_site_id else False,
            'assignment_date': self.assignment_date,
            'action_type': 'transferred' if self.current_guard_id else 'assigned',
            'condition_at_assignment': self.condition,
            'notes': self.notes,
        })
        
        # Update equipment record
        self.equipment_id.write({
            'assigned_guard_id': self.new_guard_id.id,
            'assigned_site_id': self.new_site_id.id if self.new_site_id else False,
            'assignment_date': self.assignment_date,
            'condition': self.condition,
        })
        
        # Post message to equipment
        message = _('Equipment assigned to <b>%s</b>') % self.new_guard_id.name
        if self.new_site_id:
            message += _(' at site <b>%s</b>') % self.new_site_id.name
        
        self.equipment_id.message_post(
            body=message,
            subject=_('Equipment Assignment'),
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Equipment assigned to %s successfully.') % self.new_guard_id.name,
                'type': 'success',
                'sticky': False,
            }
        }

