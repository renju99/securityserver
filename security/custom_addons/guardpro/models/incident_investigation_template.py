# -*- coding: utf-8 -*-
"""Incident Investigation Template Model - Report templates for investigations."""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class IncidentInvestigationTemplate(models.Model):
    """Investigation Report Templates"""
    
    _name = 'incident.investigation.template'
    _description = 'Investigation Report Template'
    _order = 'name'
    
    name = fields.Char(
        string='Template Name',
        required=True,
        translate=True
    )
    
    investigation_type = fields.Selection([
        ('routine', 'Routine Investigation'),
        ('detailed', 'Detailed Investigation'),
        ('formal', 'Formal Investigation'),
        ('root_cause', 'Root Cause Analysis'),
        ('compliance', 'Compliance Investigation'),
        ('internal', 'Internal Investigation'),
        ('external', 'External Investigation')
    ], string='Investigation Type', help='Type of investigation this template is for')
    
    description = fields.Text(
        string='Description',
        help='Description of when to use this template'
    )
    
    # Template Sections
    executive_summary_template = fields.Html(
        string='Executive Summary Template',
        help='Template for executive summary section'
    )
    
    findings_template = fields.Html(
        string='Findings Template',
        help='Template for detailed findings section'
    )
    
    root_cause_template = fields.Html(
        string='Root Cause Template',
        help='Template for root cause analysis section'
    )
    
    recommendations_template = fields.Html(
        string='Recommendations Template',
        help='Template for recommendations section'
    )
    
    corrective_actions_template = fields.Html(
        string='Corrective Actions Template',
        help='Template for corrective actions section'
    )
    
    preventive_actions_template = fields.Html(
        string='Preventive Actions Template',
        help='Template for preventive actions section'
    )
    
    # Report Structure
    include_timeline = fields.Boolean(
        string='Include Timeline',
        default=True,
        help='Include investigation timeline in report'
    )
    
    include_evidence_list = fields.Boolean(
        string='Include Evidence List',
        default=True,
        help='Include list of evidence in report'
    )
    
    include_witness_statements = fields.Boolean(
        string='Include Witness Statements',
        default=True,
        help='Include witness statements in report'
    )
    
    include_findings_detail = fields.Boolean(
        string='Include Findings Detail',
        default=True,
        help='Include detailed findings in report'
    )
    
    # Usage
    usage_count = fields.Integer(
        string='Usage Count',
        compute='_compute_usage_count',
        help='Number of times this template has been used'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    notes = fields.Text(
        string='Notes'
    )
    
    # Checklist Items
    checklist_item_ids = fields.One2many(
        'incident.investigation.checklist.item',
        'template_id',
        string='Checklist Items',
        help='Checklist items for this template'
    )
    
    checklist_item_count = fields.Integer(
        string='Checklist Items',
        compute='_compute_checklist_item_count',
        help='Number of checklist items'
    )
    
    # Visual
    icon = fields.Char(
        string='Icon',
        default='fa-file-text',
        help='FontAwesome icon class for this template'
    )
    
    color = fields.Integer(
        string='Color Index',
        default=0,
        help='Color for kanban view'
    )
    
    image = fields.Image(
        string='Template Image',
        help='Visual representation of this template'
    )
    
    @api.depends('checklist_item_ids')
    def _compute_checklist_item_count(self):
        """Count checklist items"""
        for template in self:
            template.checklist_item_count = len(template.checklist_item_ids)
    
    @api.depends()
    def _compute_usage_count(self):
        """Count investigations using this template"""
        for template in self:
            template.usage_count = self.env['incident.investigation'].search_count([
                ('template_id', '=', template.id)
            ])
    
    def action_view_investigations(self):
        """View investigations using this template"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Investigations'),
            'res_model': 'incident.investigation',
            'view_mode': 'list,form',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id}
        }

