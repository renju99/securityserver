# -*- coding: utf-8 -*-
"""
Example: Customizing and Overriding GuardLink Workflows

This example shows how to extend GuardLink workflows, add custom
state transitions, and override existing business logic.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class GuardShiftWorkflowCustom(models.Model):
    """Customize Guard Shift workflow."""
    
    _inherit = 'guard.shift'
    
    # ========================================
    # Example 1: Add Custom State
    # ========================================
    
    # Note: To add a state, you would typically extend the selection field
    # For this example, we'll add custom workflow methods
    
    # Add custom field to track approval
    requires_approval = fields.Boolean(
        string='Requires Manager Approval',
        default=False,
        help='Set to True for overtime shifts requiring approval'
    )
    
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True
    )
    
    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True
    )
    
    # ========================================
    # Example 2: Override Existing Method
    # ========================================
    
    def action_confirm(self):
        """
        Override the confirm method to add custom logic.
        
        Original method confirms the shift.
        Our customization adds approval check for overtime shifts.
        """
        # Check if any shift requires approval
        for shift in self:
            if shift.requires_approval and not shift.approved_by_id:
                raise UserError(_(
                    'Shift requires manager approval before confirmation.\n'
                    'Please request approval first.'
                ))
        
        # Call original method using super()
        res = super(GuardShiftWorkflowCustom, self).action_confirm()
        
        # Add custom logic after confirmation
        for shift in self:
            # Send notification to guard
            shift.guard_id.user_id.notify_warning(
                message=_('You have been assigned to shift at %s') % shift.site_id.name,
                title=_('New Shift Assignment'),
            )
            
            # Log the confirmation
            shift.message_post(
                body=_('Shift confirmed by %s') % self.env.user.name,
                subject='Shift Confirmed',
            )
        
        return res
    
    # ========================================
    # Example 3: Add Custom Workflow Action
    # ========================================
    
    def action_request_approval(self):
        """Request manager approval for this shift."""
        self.ensure_one()  # Only works on single record
        
        if not self.requires_approval:
            raise UserError(_('This shift does not require approval.'))
        
        if self.approved_by_id:
            raise UserError(_('This shift has already been approved.'))
        
        # Find managers
        manager_group = self.env.ref('guardpro.group_guardpro_manager')
        managers = self.env['res.users'].search([
            ('groups_id', 'in', manager_group.id)
        ])
        
        if not managers:
            raise UserError(_('No managers found to approve this shift.'))
        
        # Create activity for managers
        for manager in managers:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=manager.id,
                summary=_('Approve Overtime Shift'),
                note=_(
                    'Please approve overtime shift for %s at %s\n'
                    'Duration: %.1f hours\n'
                    'Reason: Overtime coverage required'
                ) % (
                    self.guard_id.name,
                    self.site_id.name,
                    self.duration_hours
                )
            )
        
        # Log the request
        self.message_post(
            body=_('Approval requested by %s') % self.env.user.name,
            subject='Approval Requested',
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Approval Requested'),
                'message': _('Managers have been notified to approve this shift.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_approve(self):
        """Approve the shift (manager action)."""
        self.ensure_one()
        
        # Check user has manager rights
        if not self.env.user.has_group('guardpro.group_guardpro_manager'):
            raise UserError(_('Only managers can approve shifts.'))
        
        if not self.requires_approval:
            raise UserError(_('This shift does not require approval.'))
        
        if self.approved_by_id:
            raise UserError(_(
                'This shift was already approved by %s on %s'
            ) % (self.approved_by_id.name, self.approval_date))
        
        # Approve the shift
        self.write({
            'approved_by_id': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })
        
        # Mark activity as done
        self.activity_feedback(['mail.mail_activity_data_todo'])
        
        # Notify requester
        self.message_post(
            body=_('Shift approved by %s') % self.env.user.name,
            subject='Shift Approved',
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shift Approved'),
                'message': _('The shift has been approved and can now be confirmed.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_reject(self):
        """Reject the shift approval request."""
        self.ensure_one()
        
        # Check user has manager rights
        if not self.env.user.has_group('guardpro.group_guardpro_manager'):
            raise UserError(_('Only managers can reject shifts.'))
        
        # Cancel the shift
        self.action_cancel()
        
        # Mark activity as done
        self.activity_feedback(['mail.mail_activity_data_todo'])
        
        # Notify requester
        self.message_post(
            body=_('Shift rejected by %s') % self.env.user.name,
            subject='Shift Rejected',
        )
        
        return True
    
    # ========================================
    # Example 4: Add Automated Actions on State Change
    # ========================================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to add custom logic when shift is created."""
        shifts = super(GuardShiftWorkflowCustom, self).create(vals_list)
        
        for shift in shifts:
            # Check if shift is overtime (>8 hours)
            if shift.duration_hours > 8:
                shift.requires_approval = True
                _logger.info(
                    'Shift %s marked as requiring approval (overtime: %.1f hours)',
                    shift.id,
                    shift.duration_hours
                )
        
        return shifts
    
    def write(self, vals):
        """Override write to add custom logic when shift is updated."""
        # Store old states before update
        old_states = {shift.id: shift.state for shift in self}
        
        res = super(GuardShiftWorkflowCustom, self).write(vals)
        
        # Check for state transitions
        for shift in self:
            old_state = old_states.get(shift.id)
            if old_state and old_state != shift.state:
                shift._handle_state_transition(old_state, shift.state)
        
        return res
    
    def _handle_state_transition(self, old_state, new_state):
        """Handle custom logic for state transitions."""
        self.ensure_one()
        
        _logger.info(
            'Shift %s state changed: %s -> %s',
            self.id,
            old_state,
            new_state
        )
        
        # Confirmed -> In Progress
        if old_state == 'confirmed' and new_state == 'in_progress':
            # Send start notification
            if self.guard_id.user_id:
                self.guard_id.user_id.notify_info(
                    message=_('Your shift has started at %s') % self.site_id.name,
                    title=_('Shift Started'),
                )
        
        # In Progress -> Completed
        elif old_state == 'in_progress' and new_state == 'completed':
            # Auto-generate DAR if configured
            if self.site_id.auto_generate_dar:
                self._generate_daily_activity_report()
            
            # Calculate performance metrics
            self._calculate_shift_performance()
        
        # Any -> Cancelled
        elif new_state == 'cancelled':
            # Notify relevant parties
            self._notify_shift_cancelled()


class IncidentReportWorkflowCustom(models.Model):
    """Customize Incident Report workflow."""
    
    _inherit = 'incident.report'
    
    # ========================================
    # Example 5: Add Escalation Workflow
    # ========================================
    
    escalation_level = fields.Integer(
        string='Escalation Level',
        default=0,
        help='0=Normal, 1=Escalated to Supervisor, 2=Escalated to Manager, 3=Critical Escalation'
    )
    
    escalated_date = fields.Datetime(
        string='Last Escalation Date',
        readonly=True
    )
    
    def action_escalate(self):
        """Escalate incident to next level."""
        for incident in self:
            if incident.escalation_level >= 3:
                raise UserError(_('Incident is already at maximum escalation level.'))
            
            # Increment escalation level
            new_level = incident.escalation_level + 1
            incident.write({
                'escalation_level': new_level,
                'escalated_date': fields.Datetime.now(),
            })
            
            # Determine who to notify
            if new_level == 1:
                # Escalate to supervisor
                group = self.env.ref('guardpro.group_guard_supervisor')
                title = 'Incident Escalated to Supervisors'
            elif new_level == 2:
                # Escalate to manager
                group = self.env.ref('guardpro.group_guard_manager')
                title = 'Incident Escalated to Managers'
            else:
                # Critical escalation to admin
                group = self.env.ref('guardpro.group_guard_admin')
                title = 'CRITICAL: Incident Escalated to Administrators'
            
            # Notify relevant users
            users = self.env['res.users'].search([
                ('groups_id', 'in', group.id)
            ])
            
            for user in users:
                incident.message_notify(
                    subject=title,
                    body=_(
                        'Incident #%s has been escalated (Level %s):\n\n'
                        'Type: %s\n'
                        'Priority: %s\n'
                        'Location: %s\n'
                        'Description: %s'
                    ) % (
                        incident.id,
                        new_level,
                        incident.incident_type_id.name,
                        incident.priority,
                        incident.location,
                        incident.description
                    ),
                    partner_ids=[user.partner_id.id],
                )
            
            # Log escalation
            incident.message_post(
                body=_('Incident escalated to level %s by %s') % (new_level, self.env.user.name),
                subject='Incident Escalated',
            )
    
    # ========================================
    # Example 6: Auto-Escalation based on Time
    # ========================================
    
    @api.model
    def _cron_auto_escalate_incidents(self):
        """
        Cron job to auto-escalate unresolved critical incidents.
        
        Add to data/ir_cron.xml:
        <record id="ir_cron_auto_escalate_incidents" model="ir.cron">
            <field name="name">Auto-Escalate Critical Incidents</field>
            <field name="model_id" ref="model_incident_report"/>
            <field name="state">code</field>
            <field name="code">model._cron_auto_escalate_incidents()</field>
            <field name="interval_number">1</field>
            <field name="interval_type">hours</field>
            <field name="numbercall">-1</field>
        </record>
        """
        from datetime import datetime, timedelta
        
        # Find critical incidents older than 30 minutes without response
        threshold = datetime.now() - timedelta(minutes=30)
        
        incidents = self.search([
            ('priority', '=', 'critical'),
            ('state', 'in', ['draft', 'submitted']),
            ('create_date', '<=', threshold),
            ('escalation_level', '<', 2),
        ])
        
        _logger.info('Auto-escalating %s critical incidents', len(incidents))
        
        for incident in incidents:
            incident.action_escalate()
    
    # ========================================
    # Example 7: Custom Workflow with Conditions
    # ========================================
    
    def action_submit(self):
        """Override submit to add conditional logic."""
        for incident in self:
            # Auto-escalate if critical
            if incident.priority == 'critical':
                incident.write({'escalation_level': 1})
                _logger.info('Critical incident %s auto-escalated on submit', incident.id)
            
            # Require photos for certain incident types
            if incident.incident_type_id.requires_photo and not incident.photo_ids:
                raise ValidationError(_(
                    'Incident type "%s" requires photo evidence.\n'
                    'Please attach photos before submitting.'
                ) % incident.incident_type_id.name)
        
        # Call original submit method
        return super(IncidentReportWorkflowCustom, self).action_submit()


class VisitorManagementWorkflowCustom(models.Model):
    """Customize Visitor Management workflow."""
    
    _inherit = 'visitor.management'
    
    # ========================================
    # Example 8: Add Custom Check-in Workflow
    # ========================================
    
    def action_checkin(self):
        """Override check-in to add custom validations."""
        for visitor in self:
            # Check if visitor is on watchlist
            if visitor.is_blocked:
                raise UserError(_(
                    'ALERT: Visitor %s is on the watchlist!\n'
                    'Reason: %s\n\n'
                    'Contact security supervisor immediately.'
                ) % (visitor.name, visitor.watchlist_reason or 'No reason specified'))
            
            # Check if visitor has required documents
            if visitor.requires_id_verification and not visitor.id_number:
                raise UserError(_(
                    'ID verification is required for %s.\n'
                    'Please verify and enter ID number before check-in.'
                ) % visitor.name)
            
            # Notify host of visitor arrival
            if visitor.host_id and visitor.host_id.email:
                visitor.message_post_with_view(
                    'guardpro.visitor_arrival_email',
                    values={'visitor': visitor},
                    subject=_('Your visitor %s has arrived') % visitor.name,
                    partner_ids=[visitor.host_id.id],
                    email_layout_xmlid='mail.mail_notification_light',
                )
        
        # Call original check-in
        return super(VisitorManagementWorkflowCustom, self).action_checkin()
    
    # ========================================
    # Example 9: Scheduled Workflow Actions
    # ========================================
    
    @api.model
    def _cron_check_overdue_visitors(self):
        """Cron to check for visitors who haven't checked out."""
        from datetime import datetime, timedelta
        
        # Find visitors checked in for more than max duration
        max_duration_hours = 12
        threshold = datetime.now() - timedelta(hours=max_duration_hours)
        
        overdue_visitors = self.search([
            ('state', '=', 'checked_in'),
            ('checkin_time', '<=', threshold),
        ])
        
        for visitor in overdue_visitors:
            # Notify security
            visitor.message_post(
                body=_(
                    'Visitor %s has been on-site for more than %s hours.\n'
                    'Check-in time: %s\n'
                    'Please verify visitor status.'
                ) % (visitor.name, max_duration_hours, visitor.checkin_time),
                subject='Overdue Visitor Alert',
                partner_ids=visitor.site_id.security_contact_ids.ids,
            )


# ========================================
# TIPS FOR WORKFLOW CUSTOMIZATION
# ========================================

"""
1. Using super() to Extend Methods:
   - Always call super() to preserve original functionality
   - Place super() call strategically (before/after custom logic)
   - Use super(ClassName, self).method() syntax

2. State Transitions:
   - Override write() to detect state changes
   - Use _handle_state_transition() pattern
   - Log all important state changes

3. Validation in Workflows:
   - Use UserError for blocking user actions
   - Use ValidationError for data validation
   - Provide clear, actionable error messages

4. Notifications:
   - Use message_post() for chatter messages
   - Use message_notify() for email notifications
   - Use notify_info/warning/success for UI notifications

5. Activities:
   - Use activity_schedule() for tasks
   - Use activity_feedback() to mark done
   - Link activities to workflow steps

6. Cron Jobs for Automation:
   - Create model methods for cron actions
   - Use @api.model decorator
   - Log all automated actions
   - Handle errors gracefully

7. Performance:
   - Batch process records when possible
   - Avoid N+1 queries
   - Use sudo() sparingly and carefully
   - Cache frequently accessed data

8. Testing Workflows:
   # Test state transitions
   shift = self.env['guard.shift'].create({...})
   shift.action_confirm()
   self.assertEqual(shift.state, 'confirmed')
   
   # Test custom methods
   result = shift.action_request_approval()
   self.assertIn('Approval Requested', result['params']['message'])

9. Security:
   - Check user permissions before sensitive operations
   - Use has_group() to check access
   - Never bypass security without good reason
   - Log security-sensitive actions

10. Common Patterns:
    - Approval workflows: Draft → Pending → Approved → Confirmed
    - Escalation workflows: Level 0 → Level 1 → Level 2 → Critical
    - Time-based actions: Use cron jobs + threshold checks
    - Conditional routing: Check fields/conditions in workflow methods

"""

