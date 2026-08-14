# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ComplianceAuditCreateWizard(models.TransientModel):
    """Wizard to create compliance audit from template"""
    _name = 'compliance.audit.create.wizard'
    _description = 'Create Audit from Template'

    template_id = fields.Many2one(
        'compliance.audit.template',
        string='Template',
        required=True,
        help='Audit template to use'
    )
    audit_type = fields.Selection([
        ('site', 'Project Audit'),
        ('guard', 'Guard Performance Audit'),
        ('equipment', 'Equipment Audit'),
        ('training', 'Training Compliance'),
        ('safety', 'Safety Audit'),
        ('security', 'Security Procedures'),
        ('operational', 'Operational Compliance'),
        ('regulatory', 'Regulatory Compliance'),
        ('quality', 'Quality Assurance')
    ], string='Audit Type', required=True)

    # Audit Target
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        help='Project to audit'
    )
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        help='Guard to audit'
    )
    equipment_id = fields.Many2one(
        'guardpro.equipment',
        string='Equipment',
        help='Equipment to audit'
    )

    # Audit Details
    audit_date = fields.Date(
        string='Audit Date',
        required=True,
        default=fields.Date.today
    )
    auditor_id = fields.Many2one(
        'res.users',
        string='Auditor',
        required=True,
        default=lambda self: self.env.user,
        help='Person conducting the audit'
    )
    auditor_team_ids = fields.Many2many(
        'res.users',
        string='Audit Team',
        help='Additional team members'
    )

    # Scheduling
    is_scheduled = fields.Boolean(
        string='Scheduled Audit',
        default=True,
        help='This is a pre-scheduled audit'
    )
    is_surprise = fields.Boolean(
        string='Surprise Audit',
        default=False,
        help='This is an unannounced audit'
    )
    frequency = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semiannual', 'Semi-Annual'),
        ('annual', 'Annual'),
        ('adhoc', 'Ad-hoc')
    ], string='Audit Frequency')

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Load template values"""
        if self.template_id:
            self.audit_type = self.template_id.audit_type
            self.frequency = self.template_id.frequency

    @api.onchange('audit_type')
    def _onchange_audit_type(self):
        """Clear incompatible targets when audit type changes"""
        if self.audit_type == 'site':
            self.guard_id = False
            self.equipment_id = False
        elif self.audit_type == 'guard':
            self.equipment_id = False
        elif self.audit_type == 'equipment':
            self.guard_id = False

    @api.constrains('site_id', 'guard_id', 'equipment_id', 'audit_type')
    def _check_audit_target(self):
        """Validate audit target matches audit type"""
        for wizard in self:
            if wizard.audit_type == 'site' and not wizard.site_id:
                raise ValidationError(_('Project audit requires a project to be selected.'))
            elif wizard.audit_type == 'guard' and not wizard.guard_id:
                raise ValidationError(_('Guard audit requires a guard to be selected.'))
            elif wizard.audit_type == 'equipment' and not wizard.equipment_id:
                raise ValidationError(_('Equipment audit requires equipment to be selected.'))

    def action_create_audit(self):
        """Create audit from wizard"""
        self.ensure_one()

        # Create audit
        audit_vals = {
            'audit_type': self.audit_type,
            'template_id': self.template_id.id,
            'site_id': self.site_id.id if self.site_id else False,
            'guard_id': self.guard_id.id if self.guard_id else False,
            'equipment_id': self.equipment_id.id if self.equipment_id else False,
            'audit_date': self.audit_date,
            'auditor_id': self.auditor_id.id,
            'auditor_team_ids': [(6, 0, self.auditor_team_ids.ids)],
            'is_scheduled': self.is_scheduled,
            'is_surprise': self.is_surprise,
            'frequency': self.frequency,
            'state': 'draft'
        }

        audit = self.env['compliance.audit'].create(audit_vals)
        
        _logger.info('Created audit %s from template %s', audit.name, self.template_id.name)

        # Create checklist items from template
        if self.template_id and self.template_id.item_ids:
            _logger.info('Template has %d items to copy', len(self.template_id.item_ids))
            checklist_items = []
            for item in self.template_id.item_ids:
                # Use description for name if name is not available (computed field)
                item_name = item.name if item.name else (item.description[:80] if item.description else 'Checkpoint')
                
                checklist_items.append({
                    'audit_id': audit.id,
                    'sequence': item.sequence,
                    'name': item_name,
                    'description': item.description,
                    'category': item.category,
                    'regulation_reference': item.regulation_reference
                })
            
            # Batch create for better performance
            if checklist_items:
                created_items = self.env['compliance.audit.item'].create(checklist_items)
                _logger.info('Created %d checklist items for audit %s', len(created_items), audit.name)
        else:
            _logger.warning('Template %s has no items to copy!', self.template_id.name if self.template_id else 'None')

        # Return action to open the created audit
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'compliance.audit',
            'res_id': audit.id,
            'view_mode': 'form',
            'target': 'current',
            'context': self.env.context
        }

