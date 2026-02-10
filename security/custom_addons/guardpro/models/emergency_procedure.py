# -*- coding: utf-8 -*-
"""Emergency Procedure Management."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class EmergencyProcedure(models.Model):
    """Emergency procedure templates."""
    
    _name = 'emergency.procedure'
    _description = 'Emergency Procedure'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Procedure Name',
        required=True,
        help='e.g., "Fire Emergency Protocol"'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order'
    )
    
    emergency_type = fields.Selection([
        ('fire', 'Fire'),
        ('medical', 'Medical Emergency'),
        ('security', 'Security Breach'),
        ('natural', 'Natural Disaster'),
        ('evacuation', 'Evacuation'),
        ('chemical', 'Chemical Spill'),
        ('power', 'Power Outage'),
        ('other', 'Other')
    ], string='Emergency Type', required=True)
    
    description = fields.Html(
        string='Description',
        help='Detailed description of when to use this procedure'
    )
    
    step_ids = fields.One2many(
        'emergency.procedure.step',
        'procedure_id',
        string='Steps',
        copy=True
    )
    
    step_count = fields.Integer(
        string='Total Steps',
        compute='_compute_step_count'
    )
    
    critical_step_count = fields.Integer(
        string='Critical Steps',
        compute='_compute_step_count'
    )
    
    site_ids = fields.Many2many(
        'client.site',
        string='Applicable Sites',
        help='Sites where this procedure applies. Leave empty for all sites.'
    )
    
    auto_notify_authorities = fields.Boolean(
        string='Auto-Notify Authorities',
        help='Automatically send notifications when this procedure is activated'
    )
    
    notify_phone = fields.Char(
        string='Emergency Phone',
        help='Phone number to notify (e.g., emergency services)'
    )
    
    notify_email = fields.Char(
        string='Emergency Email',
        help='Email address to notify'
    )
    
    notify_message = fields.Text(
        string='Notification Message Template',
        help='Message to send when notifying authorities'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    execution_count = fields.Integer(
        string='Times Executed',
        compute='_compute_execution_count',
        help='Number of times this procedure has been used'
    )
    
    @api.depends('step_ids')
    def _compute_step_count(self):
        """Compute step counts."""
        for record in self:
            record.step_count = len(record.step_ids)
            record.critical_step_count = len(record.step_ids.filtered('critical'))
    
    def _compute_execution_count(self):
        """Compute execution count."""
        for record in self:
            record.execution_count = self.env['emergency.checklist.execution'].search_count([
                ('procedure_id', '=', record.id)
            ])
    
    def action_view_executions(self):
        """View execution history."""
        self.ensure_one()
        return {
            'name': _('Execution History: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'emergency.checklist.execution',
            'view_mode': 'list,form',
            'domain': [('procedure_id', '=', self.id)],
            'context': {'default_procedure_id': self.id}
        }


class EmergencyProcedureStep(models.Model):
    """Individual steps in emergency procedure."""
    
    _name = 'emergency.procedure.step'
    _description = 'Emergency Procedure Step'
    _order = 'procedure_id, sequence'
    
    procedure_id = fields.Many2one(
        'emergency.procedure',
        string='Procedure',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    name = fields.Text(
        string='Step Description',
        required=True,
        help='Clear, actionable step instruction'
    )
    
    instruction_details = fields.Html(
        string='Detailed Instructions',
        help='Additional details, images, or diagrams'
    )
    
    requires_photo = fields.Boolean(
        string='Photo Required',
        help='Guard must take a photo to complete this step'
    )
    
    requires_confirmation = fields.Boolean(
        string='Confirmation Required',
        default=True,
        help='Guard must explicitly confirm this step'
    )
    
    requires_supervisor = fields.Boolean(
        string='Supervisor Approval Required',
        help='Supervisor must approve before proceeding'
    )
    
    critical = fields.Boolean(
        string='Critical Step',
        help='Cannot complete checklist without completing this step'
    )
    
    estimated_duration = fields.Integer(
        string='Estimated Duration (minutes)',
        help='Expected time to complete this step'
    )
    
    safety_warning = fields.Text(
        string='Safety Warning',
        help='Important safety information for this step'
    )


class EmergencyChecklistExecution(models.Model):
    """Track emergency procedure execution."""
    
    _name = 'emergency.checklist.execution'
    _description = 'Emergency Checklist Execution'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_time desc'
    
    name = fields.Char(
        string='Reference',
        required=True,
        default=lambda self: _('New'),
        copy=False,
        readonly=True,
        tracking=True
    )
    
    procedure_id = fields.Many2one(
        'emergency.procedure',
        string='Procedure',
        required=True,
        tracking=True
    )
    
    emergency_type = fields.Selection(
        related='procedure_id.emergency_type',
        string='Emergency Type',
        store=True
    )
    
    incident_id = fields.Many2one(
        'incident.report',
        string='Related Incident',
        required=True,
        tracking=True
    )
    
    site_id = fields.Many2one(
        related='incident_id.site_id',
        string='Site',
        store=True
    )
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Executing Guard',
        required=True,
        tracking=True
    )
    
    supervisor_id = fields.Many2one(
        'res.users',
        string='Supervising',
        tracking=True
    )
    
    start_time = fields.Datetime(
        string='Started',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        tracking=True
    )
    
    end_time = fields.Datetime(
        string='Completed',
        readonly=True,
        tracking=True
    )
    
    duration = fields.Integer(
        string='Duration (minutes)',
        compute='_compute_duration',
        store=True
    )
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('abandoned', 'Abandoned')
    ], string='Status', default='draft', required=True, tracking=True)
    
    step_execution_ids = fields.One2many(
        'emergency.checklist.step.execution',
        'execution_id',
        string='Step Executions'
    )
    
    completion_percentage = fields.Float(
        compute='_compute_completion',
        string='Completion %',
        store=True
    )
    
    notes = fields.Text(
        string='Notes',
        help='General notes about the execution'
    )
    
    outcome = fields.Text(
        string='Outcome',
        help='Final outcome and resolution'
    )
    
    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        """Compute duration."""
        for record in self:
            if record.start_time and record.end_time:
                delta = record.end_time - record.start_time
                record.duration = int(delta.total_seconds() / 60)
            else:
                record.duration = 0
    
    @api.depends('step_execution_ids.completed')
    def _compute_completion(self):
        """Compute completion percentage."""
        for record in self:
            total = len(record.step_execution_ids)
            if total > 0:
                completed = len(record.step_execution_ids.filtered('completed'))
                record.completion_percentage = (completed / total) * 100
            else:
                record.completion_percentage = 0.0
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence on create."""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('emergency.checklist.execution') or _('New')
        
        records = super().create(vals_list)
        
        # Auto-create step executions
        for record in records:
            record._create_step_executions()
        
        return records
    
    def _create_step_executions(self):
        """Create step execution records for each procedure step."""
        self.ensure_one()
        
        for step in self.procedure_id.step_ids:
            self.env['emergency.checklist.step.execution'].create({
                'execution_id': self.id,
                'step_id': step.id,
            })
    
    def action_start(self):
        """Start execution."""
        self.ensure_one()
        if self.status != 'draft':
            raise ValidationError(_('Only draft executions can be started.'))
        
        self.write({
            'status': 'in_progress',
            'start_time': fields.Datetime.now()
        })
        
        # Send notification
        if self.procedure_id.auto_notify_authorities:
            self._notify_authorities()
        
        # Post message to chatter
        self.message_post(
            body=_('Emergency procedure started. Follow each step carefully.'),
            subject=_('Procedure Started'),
            message_type='notification'
        )
        
        # Reload the form to show updated status
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def action_complete(self):
        """Mark checklist as completed."""
        self.ensure_one()
        
        # Verify all critical steps completed
        incomplete_critical = self.step_execution_ids.filtered(
            lambda s: s.step_id.critical and not s.completed
        )
        
        if incomplete_critical:
            raise ValidationError(_(
                'Cannot complete checklist. Critical steps not completed:\n%s'
            ) % '\n'.join(incomplete_critical.mapped('step_id.name')))
        
        self.write({
            'status': 'completed',
            'end_time': fields.Datetime.now()
        })
        
        # Update incident
        if self.incident_id:
            self.incident_id.message_post(
                body=_('Emergency procedure "%s" completed successfully.') % self.procedure_id.name
            )
        
        # Post message to chatter
        self.message_post(
            body=_('Emergency checklist completed successfully. Duration: %s minutes.') % self.duration,
            subject=_('Procedure Completed'),
            message_type='notification'
        )
        
        # Reload the form to show updated status
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def action_abandon(self):
        """Abandon the execution."""
        self.ensure_one()
        
        self.status = 'abandoned'
        
        # Log to incident
        if self.incident_id:
            self.incident_id.message_post(
                body=_('Emergency procedure "%s" was abandoned. Reason: %s') % (
                    self.procedure_id.name,
                    self.notes or _('No reason provided')
                )
            )
    
    def _notify_authorities(self):
        """Send notification to authorities."""
        self.ensure_one()
        
        # This would integrate with SMS/email services
        _logger.info(
            'Emergency notification for procedure %s at site %s',
            self.procedure_id.name,
            self.site_id.name
        )
        
        # TODO: Implement actual notification logic (SMS, email, etc.)


class EmergencyChecklistStepExecution(models.Model):
    """Track individual step completion."""
    
    _name = 'emergency.checklist.step.execution'
    _description = 'Emergency Checklist Step Execution'
    _order = 'execution_id, step_id'
    
    execution_id = fields.Many2one(
        'emergency.checklist.execution',
        string='Execution',
        required=True,
        ondelete='cascade'
    )
    
    step_id = fields.Many2one(
        'emergency.procedure.step',
        string='Step',
        required=True
    )
    
    sequence = fields.Integer(
        related='step_id.sequence',
        string='Sequence',
        store=True
    )
    
    step_name = fields.Text(
        related='step_id.name',
        string='Step Description'
    )
    
    critical = fields.Boolean(
        related='step_id.critical',
        string='Critical'
    )
    
    completed = fields.Boolean(
        string='Completed',
        default=False
    )
    
    completion_time = fields.Datetime(
        string='Completed At'
    )
    
    completed_by_id = fields.Many2one(
        'res.users',
        string='Completed By'
    )
    
    photo = fields.Binary(
        string='Photo',
        attachment=True
    )
    
    photo_filename = fields.Char(
        string='Photo Filename'
    )
    
    notes = fields.Text(
        string='Notes'
    )
    
    supervisor_approved = fields.Boolean(
        string='Supervisor Approved',
        default=False
    )
    
    supervisor_id = fields.Many2one(
        'res.users',
        string='Approved By'
    )
    
    approval_time = fields.Datetime(
        string='Approved At'
    )
    
    def action_complete_step(self):
        """Mark step as completed."""
        self.ensure_one()
        
        # Validate requirements
        if self.step_id.requires_photo and not self.photo:
            raise ValidationError(_('Photo is required for this step.'))
        
        if self.step_id.requires_supervisor and not self.supervisor_approved:
            raise ValidationError(_('Supervisor approval is required for this step.'))
        
        self.write({
            'completed': True,
            'completion_time': fields.Datetime.now(),
            'completed_by_id': self.env.user.id
        })
        
        # Update parent execution's completion percentage (will auto-compute)
        # Post notification to parent execution chatter
        if self.execution_id:
            self.execution_id.message_post(
                body=_('Step completed: %s') % self.step_name,
                message_type='notification'
            )
        
        # Reload to update completion percentage
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def action_supervisor_approve(self):
        """Supervisor approves the step."""
        self.ensure_one()
        
        self.write({
            'supervisor_approved': True,
            'supervisor_id': self.env.user.id,
            'approval_time': fields.Datetime.now()
        })
        
        # Post notification to parent execution
        if self.execution_id:
            self.execution_id.message_post(
                body=_('Step approved by supervisor: %s') % self.step_name,
                message_type='notification'
            )
        
        # Auto-complete if approved
        if not self.completed:
            return self.action_complete_step()
        
        # Reload to show approval
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

