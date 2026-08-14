# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, Command
from odoo.exceptions import ValidationError, UserError
from ..common.image_optimizer import ImageOptimizer
import logging

_logger = logging.getLogger(__name__)


class GuardTask(models.Model):
    """Guard Task/Post Order Management"""
    _name = 'guard.task'
    _description = 'Guard Task/Post Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'due_date, priority desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Task Name',
        required=True,
        tracking=True,
        help='Brief name of the task or post order'
    )
    description = fields.Html(
        string='Task Description',
        help='Detailed description of the task requirements'
    )
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True,
        tracking=True,
        index=True,
        # Completed tasks are an auditable record of what was inspected
        # at a site. Block site deletion while tasks exist.
        ondelete='restrict',
        help='Site where the task should be performed'
    )
    zone_id = fields.Many2one(
        'site.zone',
        string='Zone',
        domain="[('site_id', '=', site_id)]",
        ondelete='set null',
        tracking=True,
        index=True,
    )
    task_type = fields.Selection([
        ('patrol', 'Patrol'),
        ('inspection', 'Inspection'),
        ('maintenance_check', 'Maintenance Check'),
        ('safety_check', 'Safety Check'),
        ('visitor_log', 'Visitor Log'),
        ('equipment_check', 'Equipment Check'),
        ('incident_followup', 'Incident Follow-up'),
        ('training', 'Training Task'),
        ('documentation', 'Documentation'),
        ('other', 'Other')
    ], string='Task Type', required=True, default='other', tracking=True)

    assigned_to = fields.Many2one(
        'guard.profile',
        string='Assigned Guard',
        tracking=True,
        index=True,
        ondelete='set null',
        help='Guard responsible for completing this task'
    )
    shift_id = fields.Many2one(
        'guard.shift',
        string='Related Shift',
        tracking=True,
        # A task's shift can rotate; we still want to keep the task
        # history if the shift record is later deleted.
        ondelete='set null',
        help='Shift during which this task should be completed'
    )
    tour_log_ids = fields.Many2many(
        'tour.log',
        'tour_log_task_rel',
        'task_id',
        'tour_log_id',
        string='Related Tours',
        help='Tours that include this task'
    )

    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Priority', default='1', tracking=True)

    due_date = fields.Datetime(
        string='Due Date',
        tracking=True,
        index=True,
        help='Date and time by which the task should be completed'
    )
    completed_date = fields.Datetime(
        string='Completed Date',
        readonly=True,
        tracking=True,
        help='Actual date and time when the task was completed'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True, required=True)

    completion_notes = fields.Text(
        string='Completion Notes',
        help='Notes added by the guard upon task completion'
    )
    completion_photo = fields.Image(
        string='Completion Photo',
        help='Photo evidence of task completion'
    )
    
    photo_ids = fields.Many2many(
        'ir.attachment',
        'guard_task_photo_rel',
        'task_id',
        'attachment_id',
        string='Additional Photos',
        help='Multiple photos for task documentation (automatically optimized)'
    )
    
    photo_count = fields.Integer(
        string='Photo Count',
        compute='_compute_photo_count',
        store=True
    )
    
    template_id = fields.Many2one(
        'guard.task.template',
        string='Task Template',
        help='Select a template to auto-populate task details and checklist'
    )

    checklist_ids = fields.One2many(
        'guard.task.checklist',
        'task_id',
        string='Checklist Items',
        help='Checklist items for this task'
    )
    
    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Auto-populate task from template"""
        if self.template_id:
            _logger.error(f"DEBUG: Template selected: {self.template_id.name} (ID: {self.template_id.id})")
            
            # Update task fields
            self.name = self.template_id.name
            self.description = self.template_id.description
            self.task_type = self.template_id.task_type
            self.priority = self.template_id.priority
            
            # Add checklist items from template
            new_items = []
            
            # Check checklist_template_ids (UAE templates)
            items = getattr(self.template_id, 'checklist_template_ids', [])
            if items:
                _logger.error(f"DEBUG: Found {len(items)} items in checklist_template_ids")
                for item in items:
                    new_items.append(Command.create({
                        'sequence': item.sequence,
                        'name': item.name,
                        'mandatory': item.mandatory,
                    }))
            
            # Check checklist_ids (Alternative templates) if still empty
            if not new_items:
                items = getattr(self.template_id, 'checklist_ids', [])
                if items:
                    _logger.error(f"DEBUG: Found {len(items)} items in checklist_ids")
                    for item in items:
                        new_items.append(Command.create({
                            'sequence': getattr(item, 'sequence', 10),
                            'name': item.name,
                            'mandatory': getattr(item, 'is_mandatory', True),
                        }))
            
            if not new_items:
                _logger.error(f"DEBUG: No checklist items found for template {self.template_id.name}!")
            else:
                _logger.error(f"DEBUG: Setting {len(new_items)} items on checklist_ids")
            
            # Set items
            self.checklist_ids = [Command.clear()] + new_items




    # Computed fields
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        store=True,
        help='Task is past due date and not completed'
    )
    completion_percentage = fields.Float(
        string='Completion %',
        compute='_compute_completion_percentage',
        store=True,
        help='Percentage of checklist items completed'
    )
    total_checklist_items = fields.Integer(
        string='Total Checklist Items',
        compute='_compute_checklist_stats',
        store=True
    )
    completed_checklist_items = fields.Integer(
        string='Completed Checklist Items',
        compute='_compute_checklist_stats',
        store=True
    )

    # Audit fields
    created_by = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user,
        readonly=True
    )
    completed_by = fields.Many2one(
        'res.users',
        string='Completed By',
        readonly=True
    )

    # Mobile assignment notification tracking.
    #
    # When a supervisor assigns (or reassigns) a task, we flip
    # ``mobile_assignment_ack`` to False so the guard's mobile app / TWA
    # notification poller picks it up. The guard's acknowledge tap calls the
    # ack endpoint which flips it back to True, dismissing the notification.
    #
    # ``default=True`` makes sure existing tasks (loaded before this feature
    # shipped) do not retroactively flood every guard phone with alerts -
    # only newly-triggered assignments show up in the pending endpoint.
    mobile_assignment_ack = fields.Boolean(
        string='Assignment Acknowledged on Mobile',
        default=True,
        copy=False,
        index=True,
        help='Cleared when task is assigned to a guard so their mobile app '
             'can raise a notification; set back to True when the guard '
             'acknowledges the alert.'
    )
    mobile_assignment_notified_on = fields.Datetime(
        string='Assignment Notified On',
        readonly=True,
        copy=False,
        help='Timestamp when the mobile notification was armed for this task.'
    )
    mobile_assignment_acked_on = fields.Datetime(
        string='Assignment Acknowledged On',
        readonly=True,
        copy=False,
        help='When the assigned guard tapped "Acknowledge" on their phone.'
    )

    @api.depends('due_date', 'state')
    def _compute_is_overdue(self):
        """Check if task is overdue"""
        now = fields.Datetime.now()
        for task in self:
            if task.due_date and task.state not in ['completed', 'cancelled']:
                task.is_overdue = now > task.due_date
            else:
                task.is_overdue = False

    @api.depends('checklist_ids', 'checklist_ids.completed')
    def _compute_completion_percentage(self):
        """Calculate completion percentage based on checklist"""
        for task in self:
            total = len(task.checklist_ids)
            if total > 0:
                completed = len(task.checklist_ids.filtered(lambda x: x.completed))
                task.completion_percentage = (completed / total) * 100
            else:
                task.completion_percentage = 0.0

    @api.depends('photo_ids')
    def _compute_photo_count(self):
        """Compute number of photo attachments."""
        for record in self:
            record.photo_count = len(record.photo_ids)
    
    @api.depends('checklist_ids', 'checklist_ids.completed')
    def _compute_checklist_stats(self):
        """Calculate checklist statistics"""
        for task in self:
            task.total_checklist_items = len(task.checklist_ids)
            task.completed_checklist_items = len(
                task.checklist_ids.filtered(lambda x: x.completed)
            )

    @api.constrains('due_date', 'shift_id')
    def _check_due_date_shift(self):
        """Validate due date is within shift time"""
        for task in self:
            if task.due_date and task.shift_id:
                if not (task.shift_id.start_datetime <= task.due_date <= task.shift_id.end_datetime):
                    raise ValidationError(
                        _('Due date must be within the shift period (%s - %s)') % (
                            task.shift_id.start_datetime,
                            task.shift_id.end_datetime
                        )
                    )

    def _send_assignment_email(self):
        """Send email notification about task assignment."""
        self.ensure_one()
        _logger.info(
            'Email notifications are disabled: skipped task assignment email for task %s',
            self.id
        )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create task and optimize photos."""
        records = super().create(vals_list)
        for record in records:
            if record.photo_ids or record.completion_photo:
                record._optimize_photos()
            # Arm the mobile notification when the task is born already
            # assigned (e.g. via wizard, import, or API).
            if record.state == 'assigned' and record.assigned_to:
                record._arm_mobile_assignment_notification()
        return records

    def write(self, vals):
        """Override write to optimize photos and re-arm mobile notifications
        whenever an assignment is (re)made."""
        reassigned = self.env['guard.task']
        if vals.get('assigned_to') or vals.get('state') == 'assigned':
            # Any write that creates a fresh active assignment on the task
            # should (re)fire the mobile notification. We snapshot the
            # recordset here and react after the write commits.
            reassigned = self
        result = super().write(vals)
        if 'photo_ids' in vals or 'completion_photo' in vals:
            self._optimize_photos()
        if reassigned:
            for task in reassigned:
                if task.state == 'assigned' and task.assigned_to:
                    task._arm_mobile_assignment_notification()
        return result

    def _arm_mobile_assignment_notification(self):
        """Mark the task so the guard's mobile poller surfaces it.

        Kept as a tiny helper so future tweaks (e.g. supervisor opt-out,
        rate-limiting, push integration) can happen in one place.
        """
        self.ensure_one()
        if self.mobile_assignment_ack:
            self.sudo().write({
                'mobile_assignment_ack': False,
                'mobile_assignment_notified_on': fields.Datetime.now(),
                'mobile_assignment_acked_on': False,
            })
        else:
            # Already pending - just refresh the armed timestamp so the
            # guard knows this is a fresh assignment event.
            self.sudo().write({
                'mobile_assignment_notified_on': fields.Datetime.now(),
                'mobile_assignment_acked_on': False,
            })
    
    def _optimize_photos(self):
        """Optimize photo attachments for storage and PDF rendering."""
        for record in self:
            # Optimize Many2many photos
            for attachment in record.photo_ids.filtered(
                lambda a: a.mimetype and a.mimetype.startswith('image/')
            ):
                try:
                    if attachment.file_size and attachment.file_size < 300 * 1024:
                        continue
                    
                    original_data = attachment.datas
                    if not original_data:
                        continue
                    
                    optimized_data = ImageOptimizer.optimize_image(
                        original_data,
                        max_dimension=1200,
                        target_format='JPEG'
                    )
                    
                    if optimized_data != original_data:
                        attachment.write({
                            'datas': optimized_data,
                            'mimetype': 'image/jpeg',
                        })
                        _logger.info(
                            'Optimized photo %s for task %s',
                            attachment.name,
                            record.name
                        )
                except Exception as e:
                    _logger.error(
                        'Failed to optimize photo %s: %s',
                        attachment.id,
                        str(e)
                    )
            
            # Optimize Image field (completion_photo)
            if record.completion_photo:
                try:
                    optimized_data = ImageOptimizer.optimize_image(
                        record.completion_photo,
                        max_dimension=800,  # Smaller for single completion photo
                        target_format='JPEG'
                    )
                    if optimized_data != record.completion_photo:
                        record.completion_photo = optimized_data
                        _logger.info('Optimized completion photo for task %s', record.name)
                except Exception as e:
                    _logger.error(
                        'Failed to optimize completion photo: %s',
                        str(e)
                    )
    
    def action_assign(self):
        """Assign task to guard"""
        self.ensure_one()
        if not self.assigned_to:
            raise UserError(_('Please select a guard to assign this task.'))

        self.write({'state': 'assigned'})

        # Send email notification (currently a no-op).
        self._send_assignment_email()

        # Arm the mobile notification so the guard's phone rings even if the
        # write() hook above already did it - cheap idempotent call, and it
        # covers cases where the task was already in "assigned" state and the
        # write() branch skipped the arming.
        self._arm_mobile_assignment_notification()

        _logger.info(
            'Task %s assigned to guard %s (mobile notification armed)',
            self.name, self.assigned_to.name
        )
        return True

    def action_start(self):
        """Start task"""
        self.ensure_one()
        if self.state not in ['draft', 'assigned']:
            raise UserError(_('Only draft or assigned tasks can be started.'))
        
        self.write({'state': 'in_progress'})
        _logger.info('Task %s started by user %s', self.name, self.env.user.name)
        return True

    def action_complete(self):
        """Mark task as completed"""
        self.ensure_one()
        
        # Check if all mandatory checklist items are completed
        incomplete_items = self.checklist_ids.filtered(
            lambda x: x.mandatory and not x.completed
        )
        if incomplete_items:
            raise UserError(
                _('Please complete all mandatory checklist items before marking task as complete.')
            )
        
        self.write({
            'state': 'completed',
            'completed_date': fields.Datetime.now(),
            'completed_by': self.env.user.id
        })
        
        # Notify supervisor
        if self.assigned_to and self.assigned_to.user_id:
            self.message_post(
                body=_('Task completed by %s') % self.env.user.name,
                subject=_('Task Completed: %s') % self.name,
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        
        _logger.info('Task %s completed by user %s', self.name, self.env.user.name)
        return True

    def action_cancel(self):
        """Cancel task"""
        self.ensure_one()
        if self.state == 'completed':
            raise UserError(_('Completed tasks cannot be cancelled.'))
        
        self.write({'state': 'cancelled'})
        _logger.info('Task %s cancelled by user %s', self.name, self.env.user.name)
        return True

    def action_reopen(self):
        """Reopen cancelled task"""
        self.ensure_one()
        if self.state != 'cancelled':
            raise UserError(_('Only cancelled tasks can be reopened.'))
        
        self.write({'state': 'draft'})
        return True

    @api.model
    def send_overdue_task_alerts(self):
        """Cron job: Send alerts for overdue tasks"""
        overdue_tasks = self.search([
            ('state', 'in', ['assigned', 'in_progress']),
            ('due_date', '<', fields.Datetime.now())
        ])
        
        # Planned activities intentionally disabled for overdue tasks.
        
        _logger.info('Sent overdue alerts for %d tasks', len(overdue_tasks))
        return True


class GuardTaskChecklist(models.Model):
    """Task Checklist Item"""
    _name = 'guard.task.checklist'
    _description = 'Task Checklist Item'
    _order = 'sequence, id'

    task_id = fields.Many2one(
        'guard.task',
        string='Task',
        required=True,
        ondelete='cascade',
        index=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of checklist items'
    )
    name = fields.Char(
        string='Checklist Item',
        required=True,
        help='Description of the checklist item'
    )
    completed = fields.Boolean(
        string='Completed',
        default=False,
        help='Mark as completed'
    )
    mandatory = fields.Boolean(
        string='Mandatory',
        default=True,
        help='Must be completed before task can be marked as complete'
    )
    notes = fields.Text(
        string='Notes',
        help='Additional notes for this checklist item'
    )
    completed_date = fields.Datetime(
        string='Completed Date',
        readonly=True
    )
    completed_by = fields.Many2one(
        'res.users',
        string='Completed By',
        readonly=True
    )
    photo = fields.Image(
        string='Photo Evidence',
        max_width=1024,
        max_height=1024,
        help='Photo evidence for this checklist item'
    )

    def toggle_completed(self):
        """Toggle completion status"""
        for item in self:
            if item.completed:
                item.write({
                    'completed': False,
                    'completed_date': False,
                    'completed_by': False
                })
            else:
                item.write({
                    'completed': True,
                    'completed_date': fields.Datetime.now(),
                    'completed_by': self.env.user.id
                })
        return True


class GuardTaskTemplate(models.Model):
    """Task Template for recurring tasks"""
    _name = 'guard.task.template'
    _description = 'Guard Task Template'
    _order = 'name'

    name = fields.Char(
        string='Template Name',
        required=True,
        help='Name of the task template'
    )
    description = fields.Html(
        string='Description',
        help='Default description for tasks created from this template'
    )
    task_type = fields.Selection([
        ('patrol', 'Patrol'),
        ('inspection', 'Inspection'),
        ('maintenance_check', 'Maintenance Check'),
        ('safety_check', 'Safety Check'),
        ('visitor_log', 'Visitor Log'),
        ('equipment_check', 'Equipment Check'),
        ('incident_followup', 'Incident Follow-up'),
        ('training', 'Training Task'),
        ('documentation', 'Documentation'),
        ('other', 'Other')
    ], string='Task Type', required=True, default='other')
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Default Priority', default='1')
    
    checklist_template_ids = fields.One2many(
        'guard.task.checklist.template',
        'template_id',
        string='Checklist Template'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )

    def action_create_task(self):
        """Create task from template"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'guard.task.create.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
                'default_name': self.name,
                'default_description': self.description,
                'default_task_type': self.task_type,
                'default_priority': self.priority
            }
        }


class GuardTaskChecklistTemplate(models.Model):
    """Checklist Template for task templates"""
    _name = 'guard.task.checklist.template'
    _description = 'Task Checklist Template'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'guard.task.template',
        string='Task Template',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    name = fields.Char(
        string='Checklist Item',
        required=True
    )
    mandatory = fields.Boolean(
        string='Mandatory',
        default=True
    )

