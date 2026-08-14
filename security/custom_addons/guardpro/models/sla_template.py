# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class SLATemplate(models.Model):
    """Pre-configured SLA Templates for Quick Setup"""
    _name = 'sla.template'
    _description = 'SLA Template'
    _order = 'sequence, name'

    name = fields.Char(
        string='Template Name',
        required=True,
        help='Name of this SLA template'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order'
    )
    description = fields.Html(
        string='Description',
        help='Describe what this template covers'
    )
    
    # Industry/Type
    industry = fields.Selection([
        ('commercial', 'Commercial Buildings'),
        ('residential', 'Residential Communities'),
        ('industrial', 'Industrial Facilities'),
        ('retail', 'Retail & Shopping'),
        ('healthcare', 'Healthcare Facilities'),
        ('education', 'Educational Institutions'),
        ('government', 'Government Buildings'),
        ('mixed', 'Mixed Use'),
        ('custom', 'Custom')
    ], string='Industry Type', help='Industry this template is designed for')
    
    service_level = fields.Selection([
        ('basic', 'Basic Service'),
        ('standard', 'Standard Service'),
        ('premium', 'Premium Service'),
        ('enterprise', 'Enterprise Service')
    ], string='Service Level', default='standard', required=True,
       help='Level of service this template provides')
    
    # KPI Template Items
    kpi_template_ids = fields.One2many(
        'sla.kpi.template',
        'sla_template_id',
        string='KPI Templates'
    )
    kpi_count = fields.Integer(
        string='KPI Count',
        compute='_compute_kpi_count'
    )
    
    # Default values for SLA
    default_contract_duration = fields.Integer(
        string='Default Contract Duration (months)',
        default=12,
        help='Typical contract duration in months'
    )
    penalty_applicable = fields.Boolean(
        string='Penalties Applicable',
        default=False
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    notes = fields.Text(
        string='Implementation Notes',
        help='Notes for implementing this SLA template'
    )

    @api.depends('kpi_template_ids')
    def _compute_kpi_count(self):
        """Count KPI templates"""
        for template in self:
            template.kpi_count = len(template.kpi_template_ids)

    def action_create_sla_from_template(self):
        """Open wizard to create SLA from this template"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sla.setup.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
                'default_penalty_applicable': self.penalty_applicable
            },
            'name': _('Create SLA from Template')
        }


class SLAKPITemplate(models.Model):
    """KPI Template Items for SLA Templates"""
    _name = 'sla.kpi.template'
    _description = 'SLA KPI Template'
    _order = 'sequence, name'

    sla_template_id = fields.Many2one(
        'sla.template',
        string='SLA Template',
        required=True,
        ondelete='cascade',
        index=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    name = fields.Char(
        string='KPI Name',
        required=True,
        help='Name of the KPI'
    )
    kpi_type = fields.Selection([
        ('incident_response', 'Incident Response Time'),
        ('incident_closure', 'Incident Closure Time'),
        ('patrol_completion', 'Patrol Completion Rate'),
        ('guard_punctuality', 'Guard Punctuality'),
        ('checkpoint_compliance', 'Checkpoint Compliance'),
        ('visitor_processing', 'Visitor Processing Time'),
        ('task_completion', 'Task Completion Rate'),
        ('equipment_uptime', 'Equipment Uptime'),
        ('training_compliance', 'Training Compliance'),
        ('audit_score', 'Audit Compliance Score'),
        ('custom', 'Custom KPI')
    ], string='KPI Type', required=True)
    
    description = fields.Text(
        string='Description',
        help='How this KPI is measured'
    )
    
    # Default Target Values
    target_value = fields.Float(
        string='Default Target Value',
        required=True,
        help='Default target value for this KPI'
    )
    unit = fields.Selection([
        ('minutes', 'Minutes'),
        ('hours', 'Hours'),
        ('days', 'Days'),
        ('percentage', 'Percentage'),
        ('count', 'Count')
    ], string='Unit', required=True)
    
    target_direction = fields.Selection([
        ('maximize', 'Higher is Better'),
        ('minimize', 'Lower is Better')
    ], string='Target Direction', default='maximize', required=True)
    
    measurement_period = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly')
    ], string='Measurement Period', default='monthly', required=True)
    
    # Thresholds
    warning_threshold = fields.Float(
        string='Warning Threshold (%)',
        default=90.0
    )
    critical_threshold = fields.Float(
        string='Critical Threshold (%)',
        default=80.0
    )
    
    # Weight
    weight = fields.Float(
        string='Weight (%)',
        default=1.0,
        help='Weight of this KPI in overall SLA score'
    )
    
    # Penalty
    penalty_applicable = fields.Boolean(
        string='Penalty Applicable',
        default=False
    )
    penalty_amount = fields.Float(
        string='Default Penalty Amount',
        help='Default penalty amount for missing this KPI'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )


class SLADefinition(models.Model):
    """Extend SLA Definition with template support"""
    _inherit = 'sla.definition'

    template_id = fields.Many2one(
        'sla.template',
        string='Based on Template',
        help='Template this SLA was created from',
        readonly=True
    )
    
    # Link to compliance audits
    audit_ids = fields.Many2many(
        'compliance.audit',
        'sla_compliance_audit_rel',
        'sla_id',
        'audit_id',
        string='Related Audits',
        help='Compliance audits linked to this SLA'
    )
    audit_count = fields.Integer(
        string='Audit Count',
        compute='_compute_audit_count'
    )
    avg_audit_score = fields.Float(
        string='Average Audit Score',
        compute='_compute_audit_metrics',
        store=True,
        help='Average compliance audit score'
    )

    @api.depends('audit_ids')
    def _compute_audit_count(self):
        """Count linked audits"""
        for sla in self:
            sla.audit_count = len(sla.audit_ids)

    @api.depends('audit_ids', 'audit_ids.compliance_score', 'audit_ids.state')
    def _compute_audit_metrics(self):
        """Calculate audit metrics"""
        for sla in self:
            completed_audits = sla.audit_ids.filtered(
                lambda a: a.state in ['completed', 'requires_action', 'closed']
            )
            if completed_audits:
                sla.avg_audit_score = sum(completed_audits.mapped('compliance_score')) / len(completed_audits)
            else:
                sla.avg_audit_score = 0.0

    def action_view_audits(self):
        """View related compliance audits"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'compliance.audit',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.audit_ids.ids)],
            'context': {'default_audit_type': 'quality'},
            'name': _('Compliance Audits for %s') % self.name
        }

    def action_quick_add_kpi(self):
        """Open wizard to quickly add KPI from preset"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sla.kpi.quick.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sla_id': self.id},
            'name': _('Quick Add KPI')
        }


class SLAKPI(models.Model):
    """Extend SLA KPI with audit type"""
    _inherit = 'sla.kpi'
    
    # Link audit score to KPI
    audit_score_based = fields.Boolean(
        string='Based on Audit Score',
        default=False,
        help='This KPI is automatically calculated from compliance audit scores'
    )
    linked_audit_type = fields.Selection([
        ('site', 'Project Audit'),
        ('guard', 'Guard Performance Audit'),
        ('equipment', 'Equipment Audit'),
        ('training', 'Training Compliance'),
        ('safety', 'Safety Audit'),
        ('security', 'Security Procedures'),
        ('operational', 'Operational Compliance'),
        ('regulatory', 'Regulatory Compliance'),
        ('quality', 'Quality Assurance')
    ], string='Linked Audit Type',
       help='Type of audit that feeds this KPI')


class SLAPerformance(models.Model):
    """Extend SLA Performance with audit linking"""
    _inherit = 'sla.performance'
    
    # Link to specific audit if applicable
    audit_id = fields.Many2one(
        'compliance.audit',
        string='Related Audit',
        help='Compliance audit that generated this performance data',
        ondelete='set null'
    )

    @api.model
    def _calculate_kpi_value(self, kpi, start_date, end_date, sites):
        """Override to include audit-based KPIs"""
        
        # Check if this is an audit-based KPI
        if kpi.kpi_type == 'audit_score' or kpi.audit_score_based:
            return self._calculate_audit_score_kpi(kpi, start_date, end_date, sites)
        
        # Call parent method for other KPI types
        return super()._calculate_kpi_value(kpi, start_date, end_date, sites)

    def _calculate_audit_score_kpi(self, kpi, start_date, end_date, sites):
        """Calculate KPI value from compliance audits"""
        start_dt = fields.Datetime.to_datetime(start_date)
        end_dt = fields.Datetime.to_datetime(end_date)
        
        # Search for audits in the period
        domain = [
            ('audit_date', '>=', start_date),
            ('audit_date', '<=', end_date),
            ('state', 'in', ['completed', 'requires_action', 'closed'])
        ]
        
        if sites:
            domain.append(('site_id', 'in', sites.ids))
        
        if kpi.linked_audit_type:
            domain.append(('audit_type', '=', kpi.linked_audit_type))
        
        audits = self.env['compliance.audit'].search(domain)
        
        if audits:
            # Return average compliance score
            avg_score = sum(audits.mapped('compliance_score')) / len(audits)
            _logger.info(
                'Calculated audit-based KPI: %s audits, avg score: %.2f',
                len(audits),
                avg_score
            )
            return avg_score
        
        return 0.0






