# -*- coding: utf-8 -*-
"""Investigation Checklist Model - Interactive checklist items for investigations."""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class IncidentInvestigationChecklistItem(models.Model):
    """Investigation Checklist Items"""
    
    _name = 'incident.investigation.checklist.item'
    _description = 'Investigation Checklist Item'
    _order = 'sequence, id'
    
    name = fields.Char(
        string='Checklist Item',
        required=True,
        translate=True
    )
    
    description = fields.Text(
        string='Description',
        help='Detailed description or instructions for this item'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of checklist items'
    )
    
    template_id = fields.Many2one(
        'incident.investigation.template',
        string='Template',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    category = fields.Selection([
        ('initial', 'Initial Response'),
        ('evidence', 'Evidence Collection'),
        ('witness', 'Witness Interviews'),
        ('analysis', 'Analysis'),
        ('documentation', 'Documentation'),
        ('review', 'Review & Approval'),
        ('followup', 'Follow-up Actions')
    ], string='Category', default='initial', help='Category of checklist item')
    
    is_mandatory = fields.Boolean(
        string='Mandatory',
        default=False,
        help='Must be completed before investigation can be closed'
    )
    
    icon = fields.Char(
        string='Icon',
        default='fa-check-square',
        help='FontAwesome icon class'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )


class IncidentInvestigationChecklist(models.Model):
    """Investigation Checklist Progress Tracking"""
    
    _name = 'incident.investigation.checklist'
    _inherit = ['photo.attachment.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Investigation Checklist'
    _order = 'sequence, id'
    
    investigation_id = fields.Many2one(
        'incident.investigation',
        string='Investigation',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    checklist_item_id = fields.Many2one(
        'incident.investigation.checklist.item',
        string='Checklist Item',
        required=True,
        ondelete='cascade'
    )
    
    # Override photo_ids from mixin with explicit relation
    photo_ids = fields.Many2many(
        'ir.attachment',
        'investigation_checklist_photo_rel',
        'checklist_id',
        'attachment_id',
        string='Evidence Photos',
        help='Attach photos as evidence for this checklist item'
    )
    
    name = fields.Char(
        related='checklist_item_id.name',
        string='Item',
        store=True
    )
    
    description = fields.Text(
        related='checklist_item_id.description',
        string='Description'
    )
    
    sequence = fields.Integer(
        related='checklist_item_id.sequence',
        string='Sequence',
        store=True
    )
    
    category = fields.Selection(
        related='checklist_item_id.category',
        string='Category',
        store=True
    )
    
    is_mandatory = fields.Boolean(
        related='checklist_item_id.is_mandatory',
        string='Mandatory',
        store=True
    )
    
    icon = fields.Char(
        related='checklist_item_id.icon',
        string='Icon'
    )
    
    completed = fields.Boolean(
        string='Completed',
        default=False,
        tracking=True
    )
    
    completed_by = fields.Many2one(
        'res.users',
        string='Completed By',
        readonly=True
    )
    
    completed_date = fields.Datetime(
        string='Completed Date',
        readonly=True
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes or comments for this item'
    )
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'investigation_checklist_attachment_rel',
        'checklist_id',
        'attachment_id',
        string='Attachments',
        help='Supporting documents or evidence for this checklist item'
    )
    
    attachment_count = fields.Integer(
        string='Attachments',
        compute='_compute_attachment_count'
    )
    
    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Count attachments"""
        for record in self:
            record.attachment_count = len(record.attachment_ids)
    
    def action_toggle_complete(self):
        """Toggle completion status"""
        for record in self:
            if record.completed:
                record.write({
                    'completed': False,
                    'completed_by': False,
                    'completed_date': False
                })
            else:
                record.write({
                    'completed': True,
                    'completed_by': self.env.user.id,
                    'completed_date': fields.Datetime.now()
                })
        
        # Update investigation progress
        if self.investigation_id:
            self.investigation_id._compute_checklist_progress()
        
        return True
    
    def action_mark_complete(self):
        """Mark item as complete"""
        self.write({
            'completed': True,
            'completed_by': self.env.user.id,
            'completed_date': fields.Datetime.now()
        })
        
        # Update investigation progress
        if self.investigation_id:
            self.investigation_id._compute_checklist_progress()
        
        return True
    
    def action_mark_incomplete(self):
        """Mark item as incomplete"""
        self.write({
            'completed': False,
            'completed_by': False,
            'completed_date': False
        })
        
        # Update investigation progress
        if self.investigation_id:
            self.investigation_id._compute_checklist_progress()
        
        return True

    def action_open_item(self):
        """Open checklist item in a popup for photo/note management"""
        self.ensure_one()
        return {
            'name': _('Checklist Item: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'incident.investigation.checklist',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
