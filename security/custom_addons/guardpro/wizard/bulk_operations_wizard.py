# -*- coding: utf-8 -*-
"""Bulk Operations Wizards for Mass Actions."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class BulkShiftOperationWizard(models.TransientModel):
    """Wizard for bulk shift operations."""
    
    _name = 'bulk.shift.operation.wizard'
    _description = 'Bulk Shift Operations'
    
    operation_type = fields.Selection([
        ('reschedule', 'Reschedule Shifts'),
        ('cancel', 'Cancel Shifts'),
        ('assign', 'Assign Guards'),
        ('unassign', 'Unassign Guards'),
        ('copy', 'Duplicate Shifts')
    ], string='Operation', required=True, default='reschedule')
    
    shift_ids = fields.Many2many(
        'guard.shift',
        string='Shifts',
        required=True
    )
    
    shift_count = fields.Integer(
        compute='_compute_shift_count',
        string='Number of Shifts'
    )
    
    # Reschedule fields
    date_offset_days = fields.Integer(
        string='Days to Add/Subtract',
        help='Positive to move forward, negative to move backward'
    )
    
    # Assignment fields
    guard_id = fields.Many2one(
        'guard.profile',
        string='Assign to Guard'
    )
    
    # Cancellation fields
    cancellation_reason = fields.Text(
        string='Cancellation Reason'
    )
    
    send_notifications = fields.Boolean(
        string='Send Notifications',
        default=True,
        help='Send email/SMS notifications to affected guards'
    )
    
    # Copy fields
    copy_start_date = fields.Date(
        string='Start Date for Copies'
    )
    
    @api.depends('shift_ids')
    def _compute_shift_count(self):
        """Compute number of selected shifts."""
        for record in self:
            record.shift_count = len(record.shift_ids)
    
    def action_execute(self):
        """Execute the bulk operation."""
        self.ensure_one()
        
        if not self.shift_ids:
            raise UserError(_('Please select at least one shift.'))
        
        if self.operation_type == 'reschedule':
            return self._reschedule_shifts()
        elif self.operation_type == 'cancel':
            return self._cancel_shifts()
        elif self.operation_type == 'assign':
            return self._assign_guards()
        elif self.operation_type == 'unassign':
            return self._unassign_guards()
        elif self.operation_type == 'copy':
            return self._copy_shifts()
    
    def _reschedule_shifts(self):
        """Reschedule multiple shifts."""
        if not self.date_offset_days:
            raise UserError(_('Please specify the number of days to offset.'))
        
        offset = timedelta(days=self.date_offset_days)
        updated_count = 0
        
        for shift in self.shift_ids:
            if shift.status not in ['scheduled', 'confirmed']:
                _logger.warning('Skipping shift %s - cannot reschedule (status: %s)', shift.id, shift.status)
                continue
            
            new_start = shift.start_datetime + offset
            new_end = shift.end_datetime + offset
            
            shift.write({
                'start_datetime': new_start,
                'end_datetime': new_end
            })
            
            # Notify guard if enabled
            if self.send_notifications and shift.guard_id and shift.guard_id.user_id:
                shift.message_post(
                    body=_('Your shift has been rescheduled to %s - %s') % (
                        new_start.strftime('%Y-%m-%d %H:%M'),
                        new_end.strftime('%Y-%m-%d %H:%M')
                    ),
                    partner_ids=shift.guard_id.user_id.partner_id.ids,
                    message_type='notification'
                )
            
            updated_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d shifts rescheduled successfully.') % updated_count,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _cancel_shifts(self):
        """Cancel multiple shifts."""
        if not self.cancellation_reason:
            raise UserError(_('Please provide a cancellation reason.'))
        
        cancelled_count = 0
        affected_guards = []
        
        for shift in self.shift_ids:
            if shift.status in ['completed', 'cancelled']:
                _logger.warning('Skipping shift %s - already completed or cancelled', shift.id)
                continue
            
            if shift.guard_id:
                affected_guards.append(shift.guard_id)
            
            shift.write({
                'status': 'cancelled',
                'notes': (shift.notes or '') + '\n\nCancellation reason: ' + self.cancellation_reason
            })
            
            cancelled_count += 1
        
        # Send notifications
        if self.send_notifications and affected_guards:
            unique_guards = list(set(affected_guards))
            for guard in unique_guards:
                if guard.user_id:
                    guard.user_id.partner_id.message_post(
                        body=Markup('One or more of your shifts have been cancelled.<br/>Reason: %s') % Markup.escape(self.cancellation_reason),
                        message_type='notification'
                    )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d shifts cancelled successfully.') % cancelled_count,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _assign_guards(self):
        """Assign guard to multiple shifts."""
        if not self.guard_id:
            raise UserError(_('Please select a guard to assign.'))
        
        assigned_count = 0
        conflicts = []
        
        for shift in self.shift_ids:
            # Check for conflicts
            conflicting = self.env['guard.shift'].search([
                ('guard_id', '=', self.guard_id.id),
                ('id', '!=', shift.id),
                ('status', 'in', ['scheduled', 'confirmed', 'in_progress']),
                '|',
                '&', ('start_datetime', '<=', shift.start_datetime), ('end_datetime', '>', shift.start_datetime),
                '&', ('start_datetime', '<', shift.end_datetime), ('end_datetime', '>=', shift.end_datetime)
            ])
            
            if conflicting:
                conflicts.append(shift.id)
                _logger.warning('Skipping shift %s - guard has conflicting shift', shift.id)
                continue
            
            old_guard = shift.guard_id
            shift.write({'guard_id': self.guard_id.id})
            
            # Notify both guards
            if self.send_notifications:
                if old_guard and old_guard.user_id:
                    shift.message_post(
                        body=_('You have been unassigned from this shift.'),
                        partner_ids=old_guard.user_id.partner_id.ids,
                        message_type='notification'
                    )
                
                if self.guard_id.user_id:
                    shift.message_post(
                        body=_('You have been assigned to a shift on %s at %s') % (
                            shift.start_datetime.strftime('%Y-%m-%d'),
                            shift.site_id.name
                        ),
                        partner_ids=self.guard_id.user_id.partner_id.ids,
                        message_type='notification'
                    )
            
            assigned_count += 1
        
        message = _('%d shifts assigned to %s.') % (assigned_count, self.guard_id.name)
        if conflicts:
            message += _('\n%d shifts skipped due to schedule conflicts.') % len(conflicts)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': message,
                'type': 'success' if not conflicts else 'warning',
                'sticky': bool(conflicts),
            }
        }
    
    def _unassign_guards(self):
        """Unassign guards from multiple shifts."""
        unassigned_count = 0
        affected_guards = []
        
        for shift in self.shift_ids:
            if not shift.guard_id:
                continue
            
            affected_guards.append(shift.guard_id)
            
            if self.send_notifications and shift.guard_id.user_id:
                shift.message_post(
                    body=_('You have been unassigned from this shift on %s.') % shift.start_datetime.strftime('%Y-%m-%d'),
                    partner_ids=shift.guard_id.user_id.partner_id.ids,
                    message_type='notification'
                )
            
            shift.write({'guard_id': False})
            unassigned_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d guards unassigned from shifts.') % unassigned_count,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _copy_shifts(self):
        """Duplicate shifts to a new date."""
        if not self.copy_start_date:
            raise UserError(_('Please specify the start date for copied shifts.'))
        
        copied_count = 0
        
        # Calculate date difference
        if self.shift_ids:
            first_shift = self.shift_ids[0]
            original_date = first_shift.start_datetime.date()
            date_diff = (self.copy_start_date - original_date).days
            
            for shift in self.shift_ids:
                new_start = shift.start_datetime + timedelta(days=date_diff)
                new_end = shift.end_datetime + timedelta(days=date_diff)
                
                # Check if shift already exists
                existing = self.env['guard.shift'].search([
                    ('site_id', '=', shift.site_id.id),
                    ('start_datetime', '=', new_start),
                    ('end_datetime', '=', new_end)
                ])
                
                if existing:
                    _logger.warning('Skipping copy - shift already exists for %s at %s', new_start, shift.site_id.name)
                    continue
                
                # Create copy
                self.env['guard.shift'].create({
                    'site_id': shift.site_id.id,
                    'guard_id': shift.guard_id.id if shift.guard_id else False,
                    'start_datetime': new_start,
                    'end_datetime': new_end,
                    'shift_type': shift.shift_type,
                    'tour_id': shift.tour_id.id if shift.tour_id else False,
                    'notes': shift.notes,
                    'status': 'scheduled'
                })
                
                copied_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d shifts copied successfully.') % copied_count,
                'type': 'success',
                'sticky': False,
            }
        }


class BulkEquipmentOperationWizard(models.TransientModel):
    """Wizard for bulk equipment operations."""
    
    _name = 'bulk.equipment.operation.wizard'
    _description = 'Bulk Equipment Operations'
    
    operation_type = fields.Selection([
        ('assign', 'Assign Equipment'),
        ('return', 'Return Equipment'),
        ('maintenance', 'Schedule Maintenance')
    ], string='Operation', required=True, default='assign')
    
    equipment_ids = fields.Many2many(
        'guardpro.equipment',
        string='Equipment',
        required=True
    )
    
    equipment_count = fields.Integer(
        compute='_compute_equipment_count',
        string='Number of Items'
    )
    
    # Assignment fields
    guard_id = fields.Many2one(
        'guard.profile',
        string='Assign to Guard'
    )
    
    # Maintenance fields
    maintenance_date = fields.Date(
        string='Maintenance Date'
    )
    
    maintenance_notes = fields.Text(
        string='Maintenance Notes'
    )
    
    @api.depends('equipment_ids')
    def _compute_equipment_count(self):
        """Compute number of selected equipment."""
        for record in self:
            record.equipment_count = len(record.equipment_ids)
    
    def action_execute(self):
        """Execute the bulk operation."""
        self.ensure_one()
        
        if not self.equipment_ids:
            raise UserError(_('Please select at least one equipment item.'))
        
        if self.operation_type == 'assign':
            return self._assign_equipment()
        elif self.operation_type == 'return':
            return self._return_equipment()
        elif self.operation_type == 'maintenance':
            return self._schedule_maintenance()
    
    def _assign_equipment(self):
        """Assign equipment to guard."""
        if not self.guard_id:
            raise UserError(_('Please select a guard.'))
        
        assigned_count = 0
        
        for equipment in self.equipment_ids:
            if equipment.status != 'available':
                _logger.warning('Skipping equipment %s - not available (status: %s)', equipment.id, equipment.status)
                continue
            
            # Create assignment log
            self.env['equipment.assignment.log'].create({
                'equipment_id': equipment.id,
                'guard_id': self.guard_id.id,
                'assigned_date': fields.Date.today(),
                'status': 'assigned'
            })
            
            equipment.write({
                'current_guard_id': self.guard_id.id,
                'status': 'assigned'
            })
            
            assigned_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d equipment items assigned to %s.') % (assigned_count, self.guard_id.name),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _return_equipment(self):
        """Return equipment from guards."""
        returned_count = 0
        
        for equipment in self.equipment_ids:
            if equipment.status != 'assigned':
                continue
            
            # Update assignment log
            assignment = self.env['equipment.assignment.log'].search([
                ('equipment_id', '=', equipment.id),
                ('status', '=', 'assigned')
            ], limit=1)
            
            if assignment:
                assignment.write({
                    'returned_date': fields.Date.today(),
                    'status': 'returned'
                })
            
            equipment.write({
                'current_guard_id': False,
                'status': 'available'
            })
            
            returned_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d equipment items returned.') % returned_count,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _schedule_maintenance(self):
        """Schedule maintenance for equipment."""
        if not self.maintenance_date:
            raise UserError(_('Please specify the maintenance date.'))
        
        scheduled_count = 0
        
        for equipment in self.equipment_ids:
            # Create maintenance log
            self.env['equipment.maintenance.log'].create({
                'equipment_id': equipment.id,
                'maintenance_date': self.maintenance_date,
                'maintenance_type': 'scheduled',
                'notes': self.maintenance_notes,
                'status': 'scheduled'
            })
            
            scheduled_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Maintenance scheduled for %d equipment items.') % scheduled_count,
                'type': 'success',
                'sticky': False,
            }
        }


class BulkVisitorOperationWizard(models.TransientModel):
    """Wizard for bulk visitor operations."""
    
    _name = 'bulk.visitor.operation.wizard'
    _description = 'Bulk Visitor Operations'
    
    operation_type = fields.Selection([
        ('checkin', 'Check In Visitors'),
        ('checkout', 'Check Out Visitors'),
        ('deny', 'Deny Access'),
        ('cancel', 'Cancel Registrations'),
        ('notify_host', 'Notify Hosts'),
        ('return_badge', 'Mark Badges Returned')
    ], string='Operation', required=True, default='checkin')
    
    visitor_ids = fields.Many2many(
        'visitor.management',
        string='Visitors',
        required=True
    )
    
    visitor_count = fields.Integer(
        compute='_compute_visitor_count',
        string='Number of Visitors'
    )
    
    denial_reason = fields.Text(
        string='Denial Reason'
    )
    
    @api.depends('visitor_ids')
    def _compute_visitor_count(self):
        """Compute number of selected visitors."""
        for record in self:
            record.visitor_count = len(record.visitor_ids)
    
    def action_execute(self):
        """Execute the bulk operation."""
        self.ensure_one()
        
        if not self.visitor_ids:
            raise UserError(_('Please select at least one visitor.'))
        
        if self.operation_type == 'checkin':
            return self._checkin_visitors()
        elif self.operation_type == 'checkout':
            return self._checkout_visitors()
        elif self.operation_type == 'deny':
            return self._deny_visitors()
        elif self.operation_type == 'cancel':
            return self._cancel_visitors()
        elif self.operation_type == 'notify_host':
            return self._notify_hosts()
        elif self.operation_type == 'return_badge':
            return self._return_badges()
    
    def _checkin_visitors(self):
        """Check in multiple visitors."""
        checked_in = 0
        guard = self.env['guard.profile'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        
        for visitor in self.visitor_ids:
            if visitor.state in ['pre_registered']:
                visitor.write({
                    'state': 'checked_in',
                    'checkin_time': fields.Datetime.now(),
                    'guard_checkin_id': guard.id if guard else False
                })
                checked_in += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d visitors checked in successfully.') % checked_in,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _checkout_visitors(self):
        """Check out multiple visitors."""
        checked_out = 0
        guard = self.env['guard.profile'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        
        for visitor in self.visitor_ids:
            if visitor.state == 'checked_in':
                visitor.write({
                    'state': 'checked_out',
                    'checkout_time': fields.Datetime.now(),
                    'guard_checkout_id': guard.id if guard else False
                })
                checked_out += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d visitors checked out successfully.') % checked_out,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _deny_visitors(self):
        """Deny access to multiple visitors."""
        if not self.denial_reason:
            raise UserError(_('Please provide a denial reason.'))
        
        denied = 0
        for visitor in self.visitor_ids:
            if visitor.state in ['pre_registered']:
                visitor.write({
                    'state': 'denied',
                    'denied_reason': self.denial_reason
                })
                denied += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d visitors denied access.') % denied,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _cancel_visitors(self):
        """Cancel multiple visitor registrations."""
        cancelled = 0
        for visitor in self.visitor_ids:
            if visitor.state not in ['checked_in']:
                visitor.write({'state': 'cancelled'})
                cancelled += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d visitor registrations cancelled.') % cancelled,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _notify_hosts(self):
        """Notify hosts of visitor arrivals."""
        notified = 0
        for visitor in self.visitor_ids:
            if visitor.host_email and not visitor.host_notified:
                try:
                    visitor.action_notify_host()
                    notified += 1
                except Exception as e:
                    _logger.warning('Failed to notify host for visitor %s: %s', visitor.id, str(e))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d hosts notified successfully.') % notified,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _return_badges(self):
        """Mark badges as returned for multiple visitors."""
        returned = 0
        for visitor in self.visitor_ids:
            if visitor.badge_number and not visitor.badge_returned:
                visitor.write({
                    'badge_returned': True,
                    'badge_return_date': fields.Datetime.now()
                })
                returned += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d badges marked as returned.') % returned,
                'type': 'success',
                'sticky': False,
            }
        }


class BulkPackageOperationWizard(models.TransientModel):
    """Wizard for bulk package operations."""
    
    _name = 'bulk.package.operation.wizard'
    _description = 'Bulk Package Operations'
    
    operation_type = fields.Selection([
        ('notify', 'Notify Recipients'),
        ('return_sender', 'Return to Sender'),
        ('mark_unclaimed', 'Mark as Unclaimed'),
        ('update_location', 'Update Storage Location')
    ], string='Operation', required=True, default='notify')
    
    package_ids = fields.Many2many(
        'package.management',
        string='Packages',
        required=True
    )
    
    package_count = fields.Integer(
        compute='_compute_package_count',
        string='Number of Packages'
    )
    
    new_storage_location = fields.Char(
        string='New Storage Location'
    )
    
    return_reason = fields.Text(
        string='Return Reason'
    )
    
    @api.depends('package_ids')
    def _compute_package_count(self):
        """Compute number of selected packages."""
        for record in self:
            record.package_count = len(record.package_ids)
    
    def action_execute(self):
        """Execute the bulk operation."""
        self.ensure_one()
        
        if not self.package_ids:
            raise UserError(_('Please select at least one package.'))
        
        if self.operation_type == 'notify':
            return self._notify_recipients()
        elif self.operation_type == 'return_sender':
            return self._return_to_sender()
        elif self.operation_type == 'mark_unclaimed':
            return self._mark_unclaimed()
        elif self.operation_type == 'update_location':
            return self._update_location()
    
    def _notify_recipients(self):
        """Notify recipients of package arrivals."""
        return self.package_ids.action_bulk_notify()
    
    def _return_to_sender(self):
        """Return packages to sender."""
        if not self.return_reason:
            raise UserError(_('Please provide a return reason.'))
        
        returned = 0
        for package in self.package_ids:
            if package.state in ['received', 'notified']:
                package.write({
                    'state': 'returned',
                    'notes': (package.notes or '') + _('\n\nReturned to sender: %s') % self.return_reason
                })
                returned += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d packages marked for return to sender.') % returned,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _mark_unclaimed(self):
        """Mark packages as unclaimed."""
        unclaimed = 0
        for package in self.package_ids:
            if package.state in ['received', 'notified']:
                package.write({'state': 'unclaimed'})
                unclaimed += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d packages marked as unclaimed.') % unclaimed,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _update_location(self):
        """Update storage location for packages."""
        if not self.new_storage_location:
            raise UserError(_('Please provide a storage location.'))
        
        self.package_ids.write({'storage_location': self.new_storage_location})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d packages moved to: %s') % (len(self.package_ids), self.new_storage_location),
                'type': 'success',
                'sticky': False,
            }
        }


class BulkTaskOperationWizard(models.TransientModel):
    """Wizard for bulk task operations."""
    
    _name = 'bulk.task.operation.wizard'
    _description = 'Bulk Task Operations'
    
    operation_type = fields.Selection([
        ('assign', 'Assign to Guard'),
        ('change_priority', 'Change Priority'),
        ('change_due_date', 'Change Due Date'),
        ('mark_completed', 'Mark as Completed'),
        ('cancel', 'Cancel Tasks')
    ], string='Operation', required=True, default='assign')
    
    task_ids = fields.Many2many(
        'guard.task',
        string='Tasks',
        required=True
    )
    
    task_count = fields.Integer(
        compute='_compute_task_count',
        string='Number of Tasks'
    )
    
    assigned_to = fields.Many2one(
        'guard.profile',
        string='Assign to Guard'
    )
    
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Priority')
    
    new_due_date = fields.Date(
        string='New Due Date'
    )
    
    cancellation_reason = fields.Text(
        string='Cancellation Reason'
    )
    
    @api.depends('task_ids')
    def _compute_task_count(self):
        """Compute number of selected tasks."""
        for record in self:
            record.task_count = len(record.task_ids)
    
    def action_execute(self):
        """Execute the bulk operation."""
        self.ensure_one()
        
        if not self.task_ids:
            raise UserError(_('Please select at least one task.'))
        
        if self.operation_type == 'assign':
            return self._assign_tasks()
        elif self.operation_type == 'change_priority':
            return self._change_priority()
        elif self.operation_type == 'change_due_date':
            return self._change_due_date()
        elif self.operation_type == 'mark_completed':
            return self._mark_completed()
        elif self.operation_type == 'cancel':
            return self._cancel_tasks()
    
    def _assign_tasks(self):
        """Assign tasks to guard."""
        if not self.assigned_to:
            raise UserError(_('Please select a guard.'))
        
        assigned = 0
        for task in self.task_ids:
            if task.state in ['assigned', 'in_progress', 'pending']:
                task.write({'assigned_to': self.assigned_to.id})
                assigned += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d tasks assigned to %s.') % (assigned, self.assigned_to.name),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _change_priority(self):
        """Change task priority."""
        if not self.priority:
            raise UserError(_('Please select a priority level.'))
        
        self.task_ids.write({'priority': self.priority})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d tasks updated to %s priority.') % (
                    len(self.task_ids),
                    dict(self._fields['priority'].selection).get(self.priority)
                ),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _change_due_date(self):
        """Change task due date."""
        if not self.new_due_date:
            raise UserError(_('Please select a due date.'))
        
        self.task_ids.write({'due_date': self.new_due_date})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d tasks due date changed to %s.') % (
                    len(self.task_ids),
                    self.new_due_date.strftime('%d/%m/%Y')
                ),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _mark_completed(self):
        """Mark tasks as completed."""
        completed = 0
        for task in self.task_ids:
            if task.state not in ['completed', 'cancelled']:
                task.write({
                    'state': 'completed',
                    'completed_date': fields.Date.today()
                })
                completed += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d tasks marked as completed.') % completed,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _cancel_tasks(self):
        """Cancel tasks."""
        if not self.cancellation_reason:
            raise UserError(_('Please provide a cancellation reason.'))
        
        cancelled = 0
        for task in self.task_ids:
            if task.state not in ['completed', 'cancelled']:
                task.write({
                    'state': 'cancelled',
                    'notes': (task.notes or '') + _('\n\nCancelled: %s') % self.cancellation_reason
                })
                cancelled += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d tasks cancelled.') % cancelled,
                'type': 'success',
                'sticky': False,
            }
        }

