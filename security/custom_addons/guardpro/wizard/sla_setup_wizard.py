# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class SLASetupWizard(models.TransientModel):
    """Wizard to quickly create SLA from template"""
    _name = 'sla.setup.wizard'
    _description = 'SLA Setup Wizard'

    # Template Selection
    template_id = fields.Many2one(
        'sla.template',
        string='SLA Template',
        required=True,
        help='Select a pre-configured SLA template'
    )
    template_description = fields.Html(
        string='Template Description',
        related='template_id.description',
        readonly=True
    )
    template_kpi_count = fields.Integer(
        string='Included KPIs',
        related='template_id.kpi_count',
        readonly=True
    )
    
    # Basic SLA Info
    name = fields.Char(
        string='SLA Name',
        required=True,
        help='Name for this SLA'
    )
    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        domain=[('is_company', '=', True)],
        help='Client for this SLA'
    )
    site_ids = fields.Many2many(
        'client.site',
        string='Projects',
        help='Projects covered by this SLA'
    )
    
    # Contract Details
    contract_reference = fields.Char(
        string='Contract Reference',
        help='Contract or agreement number'
    )
    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.today,
        help='SLA effective start date'
    )
    contract_duration = fields.Integer(
        string='Contract Duration (months)',
        default=12,
        required=True,
        help='Duration of the contract in months'
    )
    end_date = fields.Date(
        string='End Date',
        compute='_compute_end_date',
        store=True,
        readonly=False,
        help='SLA expiration date'
    )
    
    # Customization
    customize_kpis = fields.Boolean(
        string='Customize KPIs',
        default=False,
        help='Check to modify KPI targets before creating'
    )
    penalty_applicable = fields.Boolean(
        string='Penalties Applicable',
        default=False
    )
    penalty_notes = fields.Text(
        string='Penalty Terms',
        help='Details of penalty structure'
    )
    
    # KPI Preview
    kpi_preview_ids = fields.One2many(
        'sla.setup.wizard.kpi',
        'wizard_id',
        string='KPI Preview'
    )
    
    auto_activate = fields.Boolean(
        string='Activate Immediately',
        default=True,
        help='Activate the SLA immediately after creation'
    )

    @api.depends('start_date', 'contract_duration')
    def _compute_end_date(self):
        """Calculate end date based on duration"""
        for wizard in self:
            if wizard.start_date and wizard.contract_duration:
                wizard.end_date = wizard.start_date + relativedelta(months=wizard.contract_duration)
            else:
                wizard.end_date = False

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Load KPI preview from template"""
        if self.template_id:
            # Load contract duration from template
            if self.template_id.default_contract_duration:
                self.contract_duration = self.template_id.default_contract_duration
            
            # Load KPI previews
            kpi_lines = []
            for kpi_template in self.template_id.kpi_template_ids:
                kpi_lines.append((0, 0, {
                    'kpi_template_id': kpi_template.id,
                    'name': kpi_template.name,
                    'kpi_type': kpi_template.kpi_type,
                    'target_value': kpi_template.target_value,
                    'unit': kpi_template.unit,
                    'target_direction': kpi_template.target_direction,
                    'measurement_period': kpi_template.measurement_period,
                    'warning_threshold': kpi_template.warning_threshold,
                    'critical_threshold': kpi_template.critical_threshold,
                    'weight': kpi_template.weight,
                    'penalty_applicable': kpi_template.penalty_applicable,
                    'penalty_amount': kpi_template.penalty_amount,
                    'include': True
                }))
            
            self.kpi_preview_ids = [(5, 0, 0)] + kpi_lines

    @api.onchange('client_id')
    def _onchange_client_id(self):
        """Suggest name based on client"""
        if self.client_id and self.template_id:
            self.name = f"{self.client_id.name} - {self.template_id.name}"

    def action_create_sla(self):
        """Create SLA from wizard"""
        self.ensure_one()
        
        # Validate
        if not self.kpi_preview_ids.filtered(lambda k: k.include):
            raise UserError(_('Please select at least one KPI to include in the SLA.'))
        
        # Create SLA Definition
        sla_vals = {
            'name': self.name,
            'client_id': self.client_id.id,
            'site_ids': [(6, 0, self.site_ids.ids)],
            'contract_reference': self.contract_reference,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'penalty_applicable': self.penalty_applicable,
            'penalty_notes': self.penalty_notes,
            'template_id': self.template_id.id,
            'state': 'active' if self.auto_activate else 'draft'
        }
        
        sla = self.env['sla.definition'].create(sla_vals)
        
        # Create KPIs
        for kpi_preview in self.kpi_preview_ids.filtered(lambda k: k.include):
            self.env['sla.kpi'].create({
                'sla_id': sla.id,
                'sequence': kpi_preview.sequence,
                'name': kpi_preview.name,
                'kpi_type': kpi_preview.kpi_type,
                'description': kpi_preview.description,
                'target_value': kpi_preview.target_value,
                'unit': kpi_preview.unit,
                'target_direction': kpi_preview.target_direction,
                'measurement_period': kpi_preview.measurement_period,
                'warning_threshold': kpi_preview.warning_threshold,
                'critical_threshold': kpi_preview.critical_threshold,
                'weight': kpi_preview.weight,
                'penalty_applicable': kpi_preview.penalty_applicable,
                'penalty_amount': kpi_preview.penalty_amount,
                'audit_score_based': kpi_preview.audit_score_based,
                'linked_audit_type': kpi_preview.linked_audit_type
            })
        
        _logger.info(
            'Created SLA "%s" from template "%s" with %d KPIs',
            sla.name,
            self.template_id.name,
            len(self.kpi_preview_ids.filtered(lambda k: k.include))
        )
        
        # Return action to open the created SLA
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sla.definition',
            'res_id': sla.id,
            'view_mode': 'form',
            'target': 'current',
            'name': _('SLA: %s') % sla.name
        }


class SLASetupWizardKPI(models.TransientModel):
    """KPI Preview in Setup Wizard"""
    _name = 'sla.setup.wizard.kpi'
    _description = 'SLA Setup Wizard KPI'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'sla.setup.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    kpi_template_id = fields.Many2one(
        'sla.kpi.template',
        string='KPI Template',
        ondelete='set null'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    include = fields.Boolean(
        string='Include',
        default=True,
        help='Include this KPI in the SLA'
    )
    
    name = fields.Char(
        string='KPI Name',
        required=True
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
        string='Description'
    )
    
    target_value = fields.Float(
        string='Target Value',
        required=True
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
    ], string='Target Direction', required=True)
    
    measurement_period = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly')
    ], string='Measurement Period', required=True)
    
    warning_threshold = fields.Float(
        string='Warning Threshold (%)',
        default=90.0
    )
    critical_threshold = fields.Float(
        string='Critical Threshold (%)',
        default=80.0
    )
    
    weight = fields.Float(
        string='Weight',
        default=1.0
    )
    
    penalty_applicable = fields.Boolean(
        string='Penalty Applicable',
        default=False
    )
    penalty_amount = fields.Float(
        string='Penalty Amount'
    )
    
    # Audit linking
    audit_score_based = fields.Boolean(
        string='Audit Score Based',
        default=False,
        help='Calculate from audit scores'
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
    ], string='Linked Audit Type')


class SLAKPIQuickWizard(models.TransientModel):
    """Quick wizard to add KPI from preset"""
    _name = 'sla.kpi.quick.wizard'
    _description = 'Quick Add KPI Wizard'

    sla_id = fields.Many2one(
        'sla.definition',
        string='SLA',
        required=True,
        ondelete='cascade'
    )
    
    # Quick preset selection
    preset_type = fields.Selection([
        ('template', 'From Template'),
        ('preset', 'From Preset'),
        ('custom', 'Custom KPI')
    ], string='Add From', default='preset', required=True)
    
    # Template selection
    kpi_template_id = fields.Many2one(
        'sla.kpi.template',
        string='KPI Template',
        help='Select a KPI template'
    )
    
    # Preset selection
    kpi_preset = fields.Selection([
        ('incident_response_15min', 'Incident Response < 15 min'),
        ('incident_response_30min', 'Incident Response < 30 min'),
        ('patrol_95', 'Patrol Completion 95%'),
        ('patrol_100', 'Patrol Completion 100%'),
        ('punctuality_90', 'Guard Punctuality 90%'),
        ('checkpoint_95', 'Checkpoint Compliance 95%'),
        ('task_completion_90', 'Task Completion 90%'),
        ('audit_score_80', 'Audit Score > 80%'),
        ('audit_score_90', 'Audit Score > 90%'),
    ], string='Quick Preset')
    
    # KPI Details (populated from preset or template)
    name = fields.Char(
        string='KPI Name',
        required=True
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
        string='Description'
    )
    
    target_value = fields.Float(
        string='Target Value',
        required=True
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
    
    warning_threshold = fields.Float(
        string='Warning Threshold (%)',
        default=90.0
    )
    critical_threshold = fields.Float(
        string='Critical Threshold (%)',
        default=80.0
    )
    
    weight = fields.Float(
        string='Weight',
        default=1.0
    )
    
    penalty_applicable = fields.Boolean(
        string='Penalty Applicable',
        default=False
    )
    penalty_amount = fields.Monetary(
        string='Penalty Amount',
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # Audit linking
    audit_score_based = fields.Boolean(
        string='Based on Audit Score',
        default=False
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
    ], string='Linked Audit Type')

    @api.onchange('kpi_template_id')
    def _onchange_kpi_template(self):
        """Load values from template"""
        if self.kpi_template_id:
            template = self.kpi_template_id
            self.name = template.name
            self.kpi_type = template.kpi_type
            self.description = template.description
            self.target_value = template.target_value
            self.unit = template.unit
            self.target_direction = template.target_direction
            self.measurement_period = template.measurement_period
            self.warning_threshold = template.warning_threshold
            self.critical_threshold = template.critical_threshold
            self.weight = template.weight
            self.penalty_applicable = template.penalty_applicable
            self.penalty_amount = template.penalty_amount

    @api.onchange('kpi_preset')
    def _onchange_kpi_preset(self):
        """Load values from preset"""
        presets = {
            'incident_response_15min': {
                'name': 'Incident Response Time < 15 minutes',
                'kpi_type': 'incident_response',
                'target_value': 15.0,
                'unit': 'minutes',
                'target_direction': 'minimize',
                'description': 'Maximum time to respond to any incident'
            },
            'incident_response_30min': {
                'name': 'Incident Response Time < 30 minutes',
                'kpi_type': 'incident_response',
                'target_value': 30.0,
                'unit': 'minutes',
                'target_direction': 'minimize',
                'description': 'Maximum time to respond to any incident'
            },
            'patrol_95': {
                'name': 'Patrol Completion Rate 95%',
                'kpi_type': 'patrol_completion',
                'target_value': 95.0,
                'unit': 'percentage',
                'target_direction': 'maximize',
                'description': 'Percentage of scheduled patrols completed'
            },
            'patrol_100': {
                'name': 'Patrol Completion Rate 100%',
                'kpi_type': 'patrol_completion',
                'target_value': 100.0,
                'unit': 'percentage',
                'target_direction': 'maximize',
                'description': 'All scheduled patrols must be completed'
            },
            'punctuality_90': {
                'name': 'Guard Punctuality 90%',
                'kpi_type': 'guard_punctuality',
                'target_value': 90.0,
                'unit': 'percentage',
                'target_direction': 'maximize',
                'description': 'Percentage of on-time guard check-ins'
            },
            'checkpoint_95': {
                'name': 'Checkpoint Compliance 95%',
                'kpi_type': 'checkpoint_compliance',
                'target_value': 95.0,
                'unit': 'percentage',
                'target_direction': 'maximize',
                'description': 'Percentage of checkpoints scanned during patrols'
            },
            'task_completion_90': {
                'name': 'Task Completion Rate 90%',
                'kpi_type': 'task_completion',
                'target_value': 90.0,
                'unit': 'percentage',
                'target_direction': 'maximize',
                'description': 'Percentage of tasks completed on time'
            },
            'audit_score_80': {
                'name': 'Audit Compliance Score > 80%',
                'kpi_type': 'audit_score',
                'target_value': 80.0,
                'unit': 'percentage',
                'target_direction': 'maximize',
                'description': 'Average compliance audit score',
                'audit_score_based': True
            },
            'audit_score_90': {
                'name': 'Audit Compliance Score > 90%',
                'kpi_type': 'audit_score',
                'target_value': 90.0,
                'unit': 'percentage',
                'target_direction': 'maximize',
                'description': 'Average compliance audit score (premium)',
                'audit_score_based': True
            },
        }
        
        if self.kpi_preset and self.kpi_preset in presets:
            preset = presets[self.kpi_preset]
            self.name = preset['name']
            self.kpi_type = preset['kpi_type']
            self.target_value = preset['target_value']
            self.unit = preset['unit']
            self.target_direction = preset['target_direction']
            self.description = preset['description']
            self.audit_score_based = preset.get('audit_score_based', False)

    def action_add_kpi(self):
        """Add KPI to SLA"""
        self.ensure_one()
        
        # Create KPI
        kpi_vals = {
            'sla_id': self.sla_id.id,
            'name': self.name,
            'kpi_type': self.kpi_type,
            'description': self.description,
            'target_value': self.target_value,
            'unit': self.unit,
            'target_direction': self.target_direction,
            'measurement_period': self.measurement_period,
            'warning_threshold': self.warning_threshold,
            'critical_threshold': self.critical_threshold,
            'weight': self.weight,
            'penalty_applicable': self.penalty_applicable,
            'penalty_amount': self.penalty_amount,
            'audit_score_based': self.audit_score_based,
            'linked_audit_type': self.linked_audit_type
        }
        
        kpi = self.env['sla.kpi'].create(kpi_vals)
        
        _logger.info('Quick-added KPI "%s" to SLA "%s"', kpi.name, self.sla_id.name)
        
        # Return to SLA form
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sla.definition',
            'res_id': self.sla_id.id,
            'view_mode': 'form',
            'target': 'current'
        }






