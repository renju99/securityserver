# -*- coding: utf-8 -*-
"""Incident SLA Policy Model - Define response time SLAs based on incident severity."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class IncidentSLAPolicy(models.Model):
    """SLA Policy for Incident Response Times"""
    
    _name = 'incident.sla.policy'
    _description = 'Incident SLA Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    _rec_name = 'name'
    
    # Basic Information
    name = fields.Char(
        string='Policy Name',
        required=True,
        tracking=True,
        help='Name of the SLA policy'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Determines priority when multiple policies match'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    description = fields.Text(
        string='Description',
        help='Policy description and applicability'
    )
    
    # Applicability Criteria
    site_ids = fields.Many2many(
        'client.site',
        string='Applicable Sites',
        help='Sites where this policy applies. Leave empty for all sites.'
    )
    category_ids = fields.Many2many(
        'incident.category',
        string='Applicable Categories',
        help='Incident categories this policy applies to. Leave empty for all categories.'
    )
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Severity', required=True, tracking=True,
       help='Incident severity this policy applies to')
    
    # SLA Targets (in minutes)
    response_time_target = fields.Integer(
        string='Response Time Target (minutes)',
        required=True,
        default=30,
        tracking=True,
        help='Target time for first response to incident'
    )
    acknowledgment_time_target = fields.Integer(
        string='Acknowledgment Time Target (minutes)',
        default=15,
        tracking=True,
        help='Target time for incident acknowledgment'
    )
    resolution_time_target = fields.Integer(
        string='Resolution Time Target (hours)',
        default=24,
        tracking=True,
        help='Target time for incident resolution'
    )
    
    # Warning Thresholds (percentage of target time)
    warning_threshold = fields.Float(
        string='Warning Threshold (%)',
        default=75.0,
        tracking=True,
        help='Send warning when this percentage of target time is reached'
    )
    critical_threshold = fields.Float(
        string='Critical Threshold (%)',
        default=90.0,
        tracking=True,
        help='Send critical alert when this percentage of target time is reached'
    )
    
    # Escalation Settings
    auto_escalate = fields.Boolean(
        string='Auto-Escalate on Breach',
        default=True,
        tracking=True,
        help='Automatically escalate incident when SLA is breached'
    )
    escalation_level_1_user_ids = fields.Many2many(
        'res.users',
        'incident_sla_escalation_level1_rel',
        'policy_id',
        'user_id',
        string='Level 1 Escalation Users',
        help='Users to notify on first escalation'
    )
    escalation_level_2_user_ids = fields.Many2many(
        'res.users',
        'incident_sla_escalation_level2_rel',
        'policy_id',
        'user_id',
        string='Level 2 Escalation Users',
        help='Users to notify on second escalation'
    )
    escalation_level_3_user_ids = fields.Many2many(
        'res.users',
        'incident_sla_escalation_level3_rel',
        'policy_id',
        'user_id',
        string='Level 3 Escalation Users',
        help='Users to notify on third escalation (management)'
    )
    
    # Progressive Escalation (escalate to next level after X minutes)
    level_1_escalation_time = fields.Integer(
        string='Level 1 Escalation Time (minutes)',
        default=30,
        help='Time after breach to escalate to level 1'
    )
    level_2_escalation_time = fields.Integer(
        string='Level 2 Escalation Time (minutes)',
        default=60,
        help='Time after breach to escalate to level 2'
    )
    level_3_escalation_time = fields.Integer(
        string='Level 3 Escalation Time (minutes)',
        default=120,
        help='Time after breach to escalate to level 3'
    )
    
    # Statistics
    incident_count = fields.Integer(
        string='Incidents',
        compute='_compute_statistics',
        help='Number of incidents under this policy'
    )
    breach_count = fields.Integer(
        string='SLA Breaches',
        compute='_compute_statistics',
        help='Number of SLA breaches'
    )
    compliance_rate = fields.Float(
        string='Compliance Rate (%)',
        compute='_compute_statistics',
        help='Percentage of incidents meeting SLA'
    )
    avg_response_time = fields.Float(
        string='Avg Response Time (minutes)',
        compute='_compute_statistics',
        help='Average response time for incidents'
    )
    
    # Color for kanban view
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color'
    )
    
    @api.depends('severity')
    def _compute_color(self):
        """Set color based on severity"""
        color_map = {
            'low': 3,       # Blue
            'medium': 9,    # Orange
            'high': 2,      # Red
            'critical': 1   # Dark Red
        }
        for record in self:
            record.color = color_map.get(record.severity, 0)
    
    def _compute_statistics(self):
        """Compute policy statistics"""
        for policy in self:
            # Find incidents that match this policy
            domain = [('severity', '=', policy.severity)]
            
            if policy.site_ids:
                domain.append(('site_id', 'in', policy.site_ids.ids))
            
            if policy.category_ids:
                domain.append(('category_id', 'in', policy.category_ids.ids))
            
            incidents = self.env['incident.report'].search(domain)
            
            policy.incident_count = len(incidents)
            
            # Count breaches
            breached = incidents.filtered(lambda i: i.sla_breach)
            policy.breach_count = len(breached)
            
            # Calculate compliance rate
            if policy.incident_count > 0:
                policy.compliance_rate = ((policy.incident_count - policy.breach_count) 
                                         / policy.incident_count * 100)
            else:
                policy.compliance_rate = 100.0
            
            # Calculate average response time
            responded = incidents.filtered(lambda i: i.response_time_minutes > 0)
            if responded:
                policy.avg_response_time = sum(responded.mapped('response_time_minutes')) / len(responded)
            else:
                policy.avg_response_time = 0.0
    
    @api.constrains('response_time_target', 'acknowledgment_time_target', 
                    'resolution_time_target')
    def _check_time_targets(self):
        """Validate time targets are positive"""
        for record in self:
            if record.response_time_target <= 0:
                raise ValidationError(_('Response time target must be greater than 0'))
            if record.acknowledgment_time_target <= 0:
                raise ValidationError(_('Acknowledgment time target must be greater than 0'))
            if record.resolution_time_target <= 0:
                raise ValidationError(_('Resolution time target must be greater than 0'))
    
    @api.constrains('warning_threshold', 'critical_threshold')
    def _check_thresholds(self):
        """Validate threshold percentages"""
        for record in self:
            if not (0 < record.warning_threshold <= 100):
                raise ValidationError(_('Warning threshold must be between 0 and 100'))
            if not (0 < record.critical_threshold <= 100):
                raise ValidationError(_('Critical threshold must be between 0 and 100'))
            if record.warning_threshold >= record.critical_threshold:
                raise ValidationError(_('Warning threshold must be less than critical threshold'))
    
    @api.model
    def get_applicable_policy(self, incident):
        """Get the applicable SLA policy for an incident
        
        Args:
            incident: incident.report record
            
        Returns:
            incident.sla.policy record or False
        """
        # Build domain to match policy
        domain = [
            ('active', '=', True),
            ('severity', '=', incident.severity)
        ]
        
        policies = self.search(domain, order='sequence')
        
        # Filter by site and category if specified
        for policy in policies:
            # Check site match
            if policy.site_ids and incident.site_id not in policy.site_ids:
                continue
            
            # Check category match
            if policy.category_ids and incident.category_id not in policy.category_ids:
                continue
            
            # Found matching policy
            return policy
        
        return False
    
    def action_view_incidents(self):
        """View incidents under this policy"""
        self.ensure_one()
        
        domain = [('severity', '=', self.severity)]
        
        if self.site_ids:
            domain.append(('site_id', 'in', self.site_ids.ids))
        
        if self.category_ids:
            domain.append(('category_id', 'in', self.category_ids.ids))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Incidents - %s') % self.name,
            'res_model': 'incident.report',
            'view_mode': 'list,form,kanban',
            'domain': domain,
            'context': {'default_severity': self.severity}
        }
    
    def action_view_breaches(self):
        """View SLA breaches for this policy"""
        self.ensure_one()
        
        domain = [
            ('severity', '=', self.severity),
            ('sla_breach', '=', True)
        ]
        
        if self.site_ids:
            domain.append(('site_id', 'in', self.site_ids.ids))
        
        if self.category_ids:
            domain.append(('category_id', 'in', self.category_ids.ids))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('SLA Breaches - %s') % self.name,
            'res_model': 'incident.report',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'default_severity': self.severity}
        }

