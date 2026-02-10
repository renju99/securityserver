# -*- coding: utf-8 -*-
"""Incident Investigation Finding Model - Investigation findings and conclusions."""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class IncidentInvestigationFinding(models.Model):
    """Investigation Findings"""
    
    _name = 'incident.investigation.finding'
    _description = 'Investigation Finding'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'
    _rec_name = 'title'
    
    investigation_id = fields.Many2one(
        'incident.investigation',
        string='Investigation',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of findings in report'
    )
    
    # Finding Details
    title = fields.Char(
        string='Finding Title',
        required=True,
        tracking=True
    )
    
    finding_type = fields.Selection([
        ('fact', 'Factual Finding'),
        ('root_cause', 'Root Cause'),
        ('contributing_factor', 'Contributing Factor'),
        ('policy_violation', 'Policy Violation'),
        ('procedure_gap', 'Procedure Gap'),
        ('training_deficiency', 'Training Deficiency'),
        ('equipment_failure', 'Equipment Failure'),
        ('human_error', 'Human Error'),
        ('system_failure', 'System Failure'),
        ('observation', 'General Observation'),
        ('other', 'Other')
    ], string='Finding Type', required=True, tracking=True)
    
    description = fields.Html(
        string='Description',
        required=True,
        help='Detailed description of finding'
    )
    
    # Severity/Impact
    severity = fields.Selection([
        ('critical', 'Critical'),
        ('major', 'Major'),
        ('moderate', 'Moderate'),
        ('minor', 'Minor')
    ], string='Severity', default='moderate', tracking=True)
    
    impact_description = fields.Text(
        string='Impact Description',
        help='Description of impact or consequences'
    )
    
    # Supporting Evidence
    evidence_ids = fields.Many2many(
        'incident.investigation.evidence',
        'finding_evidence_rel',
        'finding_id',
        'evidence_id',
        string='Supporting Evidence',
        help='Evidence that supports this finding'
    )
    
    witness_ids = fields.Many2many(
        'incident.investigation.witness',
        'finding_witness_rel',
        'finding_id',
        'witness_id',
        string='Related Witnesses',
        help='Witnesses whose statements support this finding'
    )
    
    # Analysis
    analysis = fields.Html(
        string='Analysis',
        help='Detailed analysis of the finding'
    )
    
    # Recommendations
    recommendation = fields.Html(
        string='Recommendation',
        help='Recommended corrective or preventive action'
    )
    
    action_required = fields.Boolean(
        string='Action Required',
        default=False,
        tracking=True,
        help='Does this finding require action?'
    )
    
    responsible_party = fields.Char(
        string='Responsible Party',
        help='Who is responsible for addressing this finding'
    )
    
    target_date = fields.Date(
        string='Target Date',
        help='Target date for implementing recommendation'
    )
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('action_pending', 'Action Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved')
    ], string='Status', default='draft', tracking=True)
    
    resolution_notes = fields.Text(
        string='Resolution Notes',
        help='How the finding was addressed'
    )
    
    # Tags
    tag_ids = fields.Many2many(
        'incident.investigation.finding.tag',
        'inv_finding_tag_rel',
        'finding_id',
        'tag_id',
        string='Tags'
    )
    
    notes = fields.Text(
        string='Additional Notes'
    )
    
    # Color for kanban
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color'
    )
    
    @api.depends('severity', 'status')
    def _compute_color(self):
        """Set color based on severity and status"""
        for record in self:
            if record.status == 'resolved':
                record.color = 10  # Green
            elif record.severity == 'critical':
                record.color = 1  # Dark red
            elif record.severity == 'major':
                record.color = 2  # Red
            elif record.severity == 'moderate':
                record.color = 9  # Orange
            else:
                record.color = 3  # Yellow
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create finding and timeline entry"""
        records = super().create(vals_list)
        
        for record in records:
            # Add timeline entry to investigation
            if record.investigation_id:
                record.investigation_id._create_timeline_entry(
                    'finding_added',
                    _('Finding added: %s') % record.title
                )
        
        return records
    
    def action_confirm(self):
        """Confirm finding"""
        self.ensure_one()
        self.write({'status': 'confirmed'})
        return True
    
    def action_resolve(self):
        """Mark finding as resolved"""
        self.ensure_one()
        
        if not self.resolution_notes:
            from odoo.exceptions import ValidationError
            raise ValidationError(_('Please provide resolution notes'))
        
        self.write({'status': 'resolved'})
        
        self.message_post(
            body=_('Finding resolved by %s') % self.env.user.name,
            message_type='notification'
        )
        
        return True


class IncidentInvestigationFindingTag(models.Model):
    """Finding Tags"""
    
    _name = 'incident.investigation.finding.tag'
    _description = 'Finding Tag'
    _order = 'name'
    
    name = fields.Char(
        string='Tag Name',
        required=True,
        translate=True
    )
    color = fields.Integer(
        string='Color Index'
    )

