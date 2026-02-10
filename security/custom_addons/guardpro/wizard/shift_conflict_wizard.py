# -*- coding: utf-8 -*-
"""Shift Conflict Resolution Wizard."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class GuardShiftConflictWizard(models.TransientModel):
    """Wizard for handling shift conflicts and suggesting alternatives."""
    
    _name = 'guard.shift.conflict.wizard'
    _description = 'Shift Conflict Resolution Wizard'
    
    shift_id = fields.Many2one(
        'guard.shift',
        string='Shift',
        required=True,
        readonly=True
    )
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Current Guard',
        related='shift_id.guard_id',
        readonly=True
    )
    
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        related='shift_id.site_id',
        readonly=True
    )
    
    start_datetime = fields.Datetime(
        string='Shift Start',
        related='shift_id.start_datetime',
        readonly=True
    )
    
    end_datetime = fields.Datetime(
        string='Shift End',
        related='shift_id.end_datetime',
        readonly=True
    )
    
    has_overlap = fields.Boolean(
        string='Has Overlapping Shifts',
        default=False
    )
    
    has_rest_violation = fields.Boolean(
        string='Has Rest Period Violation',
        default=False
    )
    
    conflict_details = fields.Text(
        string='Conflict Details',
        readonly=True
    )
    
    # Resolution options
    action = fields.Selection([
        ('override', 'Override Conflict (Approve Anyway)'),
        ('reassign', 'Reassign to Alternative Guard'),
        ('cancel', 'Cancel Operation')
    ], string='Resolution Action', default='cancel', required=True)
    
    override_reason = fields.Text(
        string='Override Reason',
        help='Required if overriding the conflict'
    )
    
    # Alternative guards
    alternative_guard_ids = fields.Many2many(
        'guard.profile',
        string='Available Alternative Guards',
        compute='_compute_alternative_guards',
        help='Guards who are available for this shift'
    )
    
    selected_guard_id = fields.Many2one(
        'guard.profile',
        string='Reassign to Guard',
        domain="[('id', 'in', alternative_guard_ids)]"
    )
    
    alternative_count = fields.Integer(
        string='Available Guards',
        compute='_compute_alternative_guards'
    )
    
    show_warning_message = fields.Boolean(
        string='Show Warning',
        compute='_compute_show_warning'
    )
    
    warning_message = fields.Html(
        string='Warning Message',
        compute='_compute_warning_message'
    )
    
    @api.depends('shift_id')
    def _compute_alternative_guards(self):
        """Find alternative guards who can take this shift."""
        for wizard in self:
            if wizard.shift_id:
                alternatives = wizard.shift_id.find_alternative_guards()
                wizard.alternative_guard_ids = alternatives
                wizard.alternative_count = len(alternatives)
            else:
                wizard.alternative_guard_ids = False
                wizard.alternative_count = 0
    
    @api.depends('has_overlap', 'has_rest_violation', 'alternative_count')
    def _compute_show_warning(self):
        """Determine if warning should be shown."""
        for wizard in self:
            wizard.show_warning_message = (
                wizard.has_overlap or 
                wizard.has_rest_violation or 
                wizard.alternative_count == 0
            )
    
    @api.depends('has_overlap', 'has_rest_violation', 'conflict_details', 
                 'alternative_count', 'guard_id')
    def _compute_warning_message(self):
        """Generate formatted warning message."""
        for wizard in self:
            messages = []
            
            # Conflict type warnings
            if wizard.has_overlap:
                messages.append(
                    '<div class="alert alert-danger" role="alert">'
                    '<h4 class="alert-heading">'
                    '<i class="fa fa-exclamation-triangle"></i> '
                    'CRITICAL: Overlapping Shifts Detected!'
                    '</h4>'
                    '<p>Guard <strong>%s</strong> is already scheduled for '
                    'another shift during this time period.</p>'
                    '<p><strong>This creates a direct schedule conflict.</strong></p>'
                    '</div>' % (wizard.guard_id.name or 'Unknown')
                )
            
            if wizard.has_rest_violation:
                messages.append(
                    '<div class="alert alert-warning" role="alert">'
                    '<h4 class="alert-heading">'
                    '<i class="fa fa-exclamation-circle"></i> '
                    'WARNING: Insufficient Rest Period!'
                    '</h4>'
                    '<p>Guard <strong>%s</strong> does not have sufficient '
                    'rest time between shifts.</p>'
                    '<p>This may violate labor regulations and affect guard performance.</p>'
                    '</div>' % (wizard.guard_id.name or 'Unknown')
                )
            
            # Conflict details
            if wizard.conflict_details:
                messages.append(
                    '<div class="alert alert-info" role="alert">'
                    '<h5>Conflict Details:</h5>'
                    '<pre>%s</pre>'
                    '</div>' % wizard.conflict_details
                )
            
            # Alternative guards info
            if wizard.alternative_count > 0:
                messages.append(
                    '<div class="alert alert-success" role="alert">'
                    '<h5><i class="fa fa-users"></i> '
                    '%d Alternative Guard(s) Available</h5>'
                    '<p>The following guards are available and can be assigned to this shift:</p>'
                    '<ul>%s</ul>'
                    '</div>' % (
                        wizard.alternative_count,
                        ''.join([
                            '<li><strong>%s</strong>%s</li>' % (
                                guard.name,
                                ' <span class="badge badge-primary">Site Experience</span>' 
                                if wizard.site_id.id in guard.assigned_site_ids.ids 
                                else ''
                            )
                            for guard in wizard.alternative_guard_ids[:5]
                        ])
                    )
                )
                if wizard.alternative_count > 5:
                    messages.append(
                        '<p><em>... and %d more guards</em></p>' % 
                        (wizard.alternative_count - 5)
                    )
            else:
                messages.append(
                    '<div class="alert alert-danger" role="alert">'
                    '<h5><i class="fa fa-times-circle"></i> '
                    'No Alternative Guards Available</h5>'
                    '<p>No other guards are available for this time slot.</p>'
                    '<p>You may need to:</p>'
                    '<ul>'
                    '<li>Override this conflict with supervisor approval</li>'
                    '<li>Reschedule the shift to a different time</li>'
                    '<li>Cancel one of the conflicting shifts</li>'
                    '</ul>'
                    '</div>'
                )
            
            wizard.warning_message = ''.join(messages)
    
    @api.onchange('action')
    def _onchange_action(self):
        """Handle action change."""
        if self.action == 'reassign':
            # Auto-select first alternative if available
            if self.alternative_guard_ids and not self.selected_guard_id:
                # Prefer guards with site experience
                site_experienced = self.alternative_guard_ids.filtered(
                    lambda g: self.site_id.id in g.assigned_site_ids.ids
                )
                if site_experienced:
                    self.selected_guard_id = site_experienced[0]
                else:
                    self.selected_guard_id = self.alternative_guard_ids[0]
    
    def action_apply(self):
        """Apply the selected resolution action."""
        self.ensure_one()
        
        if self.action == 'cancel':
            # Just close the wizard without making changes
            return {'type': 'ir.actions.act_window_close'}
        
        elif self.action == 'override':
            # Validate override reason for overlaps
            if self.has_overlap and not self.override_reason:
                raise ValidationError(_(
                    'You must provide a reason for overriding an overlapping shift conflict.'
                ))
            
            # Check supervisor permission
            supervisor_group = self.env.ref(
                'guardpro.group_guardpro_supervisor', 
                raise_if_not_found=False
            )
            if not supervisor_group or self.env.user not in supervisor_group.users:
                raise ValidationError(_(
                    'Only supervisors can override shift conflicts.'
                ))
            
            # Apply override
            self.shift_id.action_override_conflict(
                self.override_reason or _('Approved by supervisor')
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Conflict Override Applied'),
                    'message': _('Shift conflict has been overridden. The shift is now approved.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        
        elif self.action == 'reassign':
            # Validate guard selection
            if not self.selected_guard_id:
                raise ValidationError(_(
                    'Please select a guard to reassign this shift to.'
                ))
            
            # Check if selected guard is actually available
            if self.selected_guard_id not in self.alternative_guard_ids:
                raise ValidationError(_(
                    'The selected guard is not available for this shift.'
                ))
            
            old_guard_name = self.guard_id.name if self.guard_id else 'Unassigned'
            
            # Reassign the shift
            self.shift_id.write({
                'guard_id': self.selected_guard_id.id
            })
            
            # Log the reassignment
            self.shift_id.message_post(
                body=Markup(
                    '<p><strong>Shift Reassigned</strong></p>'
                    '<p>Shift reassigned from <strong>%s</strong> to '
                    '<strong>%s</strong> by %s.</p>'
                    '<p><strong>Reason:</strong> %s</p>'
                    '<p style="margin-top: 16px; font-size: 12px; color: #888;">This change was made using the Shift Conflict Wizard.</p>'
                ) % (
                    old_guard_name,
                    self.selected_guard_id.name,
                    self.env.user.name,
                    'Scheduling conflict resolution'
                ),
                subject=_('Shift Reassigned'),
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
            
            _logger.info(
                'Shift %s reassigned from %s to %s due to conflict',
                self.shift_id.name,
                old_guard_name,
                self.selected_guard_id.name
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Shift Reassigned'),
                    'message': _('Shift has been reassigned to %s successfully.') % 
                              self.selected_guard_id.name,
                    'type': 'success',
                    'sticky': False,
                }
            }
        
        return {'type': 'ir.actions.act_window_close'}

