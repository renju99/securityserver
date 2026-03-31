# -*- coding: utf-8 -*-
"""Incident Escalation Log Model - Track escalation history and SLA breaches."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class IncidentEscalationLog(models.Model):
    """Escalation Log for Incident Tracking"""
    
    _name = 'incident.escalation.log'
    _description = 'Incident Escalation Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'escalation_datetime desc, id desc'
    _rec_name = 'display_name'
    
    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True
    )
    
    # Incident Reference
    incident_id = fields.Many2one(
        'incident.report',
        string='Incident',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )
    incident_name = fields.Char(
        related='incident_id.name',
        string='Incident Number',
        store=True
    )
    incident_severity = fields.Selection(
        related='incident_id.severity',
        string='Severity',
        store=True
    )
    site_id = fields.Many2one(
        related='incident_id.site_id',
        string='Site',
        store=True,
        index=True
    )
    
    # SLA Policy
    sla_policy_id = fields.Many2one(
        'incident.sla.policy',
        string='SLA Policy',
        ondelete='restrict',
        tracking=True
    )
    
    # Escalation Details
    escalation_type = fields.Selection([
        ('sla_breach', 'SLA Breach'),
        ('warning_threshold', 'Warning Threshold Reached'),
        ('critical_threshold', 'Critical Threshold Reached'),
        ('response_sla_breach', 'Response SLA Breach'),
        ('resolution_sla_breach', 'Resolution SLA Breach'),
        ('progressive_level_1', 'Progressive Escalation - Level 1'),
        ('progressive_level_2', 'Progressive Escalation - Level 2'),
        ('progressive_level_3', 'Progressive Escalation - Level 3'),
        ('manual', 'Manual Escalation'),
        ('severity_increase', 'Severity Increased'),
        ('other', 'Other')
    ], string='Escalation Type', required=True, tracking=True, index=True)
    
    escalation_level = fields.Integer(
        string='Escalation Level',
        default=1,
        tracking=True,
        help='Progressive escalation level (1, 2, 3...)'
    )
    
    escalation_datetime = fields.Datetime(
        string='Escalation Date/Time',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        index=True
    )
    
    escalation_reason = fields.Text(
        string='Escalation Reason',
        required=True,
        tracking=True,
        help='Detailed reason for escalation'
    )
    
    # Time Tracking
    time_since_incident = fields.Float(
        string='Time Since Incident (minutes)',
        compute='_compute_time_metrics',
        store=True,
        help='Minutes elapsed from incident to escalation'
    )
    sla_target_time = fields.Integer(
        string='SLA Target (minutes)',
        help='Original SLA target time'
    )
    sla_breach_time = fields.Float(
        string='SLA Breach Time (minutes)',
        help='How much the SLA was breached by'
    )
    
    # Escalation Users
    escalated_to_user_ids = fields.Many2many(
        'res.users',
        'incident_escalation_user_rel',
        'escalation_id',
        'user_id',
        string='Escalated To',
        tracking=True,
        help='Users notified about this escalation'
    )
    escalated_by_user_id = fields.Many2one(
        'res.users',
        string='Escalated By',
        default=lambda self: self.env.user,
        tracking=True
    )
    
    # Status
    status = fields.Selection([
        ('open', 'Open'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='open', required=True, tracking=True, index=True)
    
    acknowledged_by_user_id = fields.Many2one(
        'res.users',
        string='Acknowledged By',
        tracking=True
    )
    acknowledged_datetime = fields.Datetime(
        string='Acknowledged Date/Time',
        tracking=True
    )
    
    resolved_by_user_id = fields.Many2one(
        'res.users',
        string='Resolved By',
        tracking=True
    )
    resolved_datetime = fields.Datetime(
        string='Resolved Date/Time',
        tracking=True
    )
    
    # Response Time
    response_time_minutes = fields.Float(
        string='Response Time (minutes)',
        compute='_compute_time_metrics',
        store=True,
        help='Time from escalation to acknowledgment'
    )
    resolution_time_minutes = fields.Float(
        string='Resolution Time (minutes)',
        compute='_compute_time_metrics',
        store=True,
        help='Time from escalation to resolution'
    )
    
    # Notification Tracking
    notification_sent = fields.Boolean(
        string='Notification Sent',
        default=False,
        help='Has escalation notification been sent'
    )
    notification_sent_datetime = fields.Datetime(
        string='Notification Sent Time'
    )
    
    # Notes
    action_taken = fields.Text(
        string='Action Taken',
        help='Actions taken to address the escalation'
    )
    notes = fields.Text(
        string='Additional Notes'
    )
    
    # Priority indicator
    is_critical = fields.Boolean(
        string='Critical',
        compute='_compute_is_critical',
        store=True,
        help='Is this a critical escalation'
    )
    
    # Color for kanban view
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color'
    )
    
    @api.depends('incident_id', 'escalation_type', 'escalation_level')
    def _compute_display_name(self):
        """Generate display name"""
        for record in self:
            if record.incident_id:
                record.display_name = _('%s - Escalation L%d (%s)') % (
                    record.incident_id.name,
                    record.escalation_level,
                    dict(record._fields['escalation_type'].selection).get(
                        record.escalation_type, 'Unknown'
                    )
                )
            else:
                record.display_name = _('New Escalation')
    
    @api.depends('incident_id.incident_datetime', 'escalation_datetime',
                 'acknowledged_datetime', 'resolved_datetime')
    def _compute_time_metrics(self):
        """Calculate time-based metrics"""
        for record in self:
            # Time since incident
            if record.incident_id and record.incident_id.incident_datetime:
                delta = record.escalation_datetime - record.incident_id.incident_datetime
                record.time_since_incident = delta.total_seconds() / 60
            else:
                record.time_since_incident = 0.0
            
            # Response time (escalation to acknowledgment)
            if record.acknowledged_datetime:
                delta = record.acknowledged_datetime - record.escalation_datetime
                record.response_time_minutes = delta.total_seconds() / 60
            else:
                record.response_time_minutes = 0.0
            
            # Resolution time (escalation to resolution)
            if record.resolved_datetime:
                delta = record.resolved_datetime - record.escalation_datetime
                record.resolution_time_minutes = delta.total_seconds() / 60
            else:
                record.resolution_time_minutes = 0.0
    
    @api.depends('escalation_type', 'incident_severity')
    def _compute_is_critical(self):
        """Determine if escalation is critical"""
        critical_types = ['sla_breach', 'critical_threshold', 'progressive_level_3']
        for record in self:
            record.is_critical = (
                record.escalation_type in critical_types or
                record.incident_severity == 'critical'
            )
    
    @api.depends('status', 'is_critical')
    def _compute_color(self):
        """Set color based on status and criticality"""
        for record in self:
            if record.status == 'resolved':
                record.color = 10  # Green
            elif record.status == 'cancelled':
                record.color = 8   # Grey
            elif record.is_critical:
                record.color = 1   # Dark Red
            elif record.status == 'acknowledged':
                record.color = 9   # Orange
            else:
                record.color = 2   # Red
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create escalation log and send notifications"""
        records = super().create(vals_list)
        
        for record in records:
            # Send escalation notifications
            if record.escalated_to_user_ids:
                record._send_escalation_notification()
            
            # Post message to incident
            if record.incident_id:
                record.incident_id.message_post(
                    body=Markup(
                        '<p><strong style="color: red;">INCIDENT ESCALATED</strong></p>'
                        '<p>Escalation Type: %s</p>'
                        '<p>Level: %d</p>'
                        '<p>Reason: %s</p>'
                    ) % (
                        Markup.escape(
                            dict(record._fields['escalation_type'].selection).get(
                                record.escalation_type, 'Unknown'
                            )
                        ),
                        record.escalation_level,
                        Markup.escape(record.escalation_reason or '')
                    ),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )
        
        return records
    
    def action_acknowledge(self):
        """Acknowledge escalation"""
        self.ensure_one()
        
        if self.status != 'open':
            raise ValidationError(_('Only open escalations can be acknowledged'))
        
        self.write({
            'status': 'acknowledged',
            'acknowledged_by_user_id': self.env.user.id,
            'acknowledged_datetime': fields.Datetime.now()
        })
        
        self.message_post(
            body=_('Escalation acknowledged by %s') % self.env.user.name,
            message_type='notification'
        )
        
        return True
    
    def action_resolve(self):
        """Mark escalation as resolved"""
        self.ensure_one()
        
        if not self.action_taken:
            raise ValidationError(_('Please provide details of the action taken before resolving'))
        
        self.write({
            'status': 'resolved',
            'resolved_by_user_id': self.env.user.id,
            'resolved_datetime': fields.Datetime.now()
        })
        
        self.message_post(
            body=_('Escalation resolved by %s\n\nAction taken: %s') % (
                self.env.user.name,
                self.action_taken
            ),
            message_type='notification'
        )
        
        return True
    
    def action_cancel(self):
        """Cancel escalation"""
        self.ensure_one()
        
        self.write({'status': 'cancelled'})
        
        self.message_post(
            body=_('Escalation cancelled by %s') % self.env.user.name,
            message_type='notification'
        )
        
        return True
    
    def _send_escalation_notification(self):
        """Send escalation notification to users"""
        self.ensure_one()
        
        if not self.escalated_to_user_ids:
            return
        
        # Create activity for each escalated user
        for user in self.escalated_to_user_ids:
            activity_type = self.env.ref('mail.mail_activity_data_urgent', 
                                        raise_if_not_found=False)
            if not activity_type:
                activity_type = self.env.ref('mail.mail_activity_data_todo',
                                            raise_if_not_found=False)
            
            if activity_type:
                # Planned activity intentionally disabled.
                continue
        
        # Mark notification as sent
        self.write({
            'notification_sent': True,
            'notification_sent_datetime': fields.Datetime.now()
        })
        
        # Email notifications are disabled globally.
        if self.escalated_to_user_ids:
            _logger.info(
                'Email notifications are disabled: skipped escalation emails for incident %s',
                self.incident_id.name
            )
        
        _logger.info(
            'Sent escalation notification for incident %s to %d users',
            self.incident_id.name,
            len(self.escalated_to_user_ids)
        )

