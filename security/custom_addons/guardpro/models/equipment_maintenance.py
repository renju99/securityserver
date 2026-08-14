# -*- coding: utf-8 -*-
"""Guard Equipment Management - Using Native Maintenance Module."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class MaintenanceEquipment(models.Model):
    """Extend Odoo's native maintenance.equipment for guard equipment tracking."""

    _inherit = 'maintenance.equipment'

    # Guard-specific fields
    is_guard_equipment = fields.Boolean(
        string='Guard Equipment',
        default=False,
        help='Mark this as security guard equipment'
    )
    
    equipment_category = fields.Selection([
        ('radio', 'Radio/Communication'),
        ('weapon', 'Weapon'),
        ('vehicle', 'Vehicle'),
        ('flashlight', 'Flashlight'),
        ('uniform', 'Uniform'),
        ('badge', 'Badge/ID'),
        ('keys', 'Keys'),
        ('first_aid', 'First Aid Kit'),
        ('safety', 'Safety Equipment'),
        ('tech', 'Technology/Device'),
        ('body_camera', 'Body Camera'),
        ('metal_detector', 'Metal Detector'),
        ('x_ray', 'X-Ray Scanner'),
        ('other', 'Other')
    ], string='Equipment Category', help='Category of guard equipment')
    
    # Assignment (extends native maintenance)
    assigned_guard_id = fields.Many2one(
        'guard.profile',
        string='Assigned Guard',
        tracking=True,
        help='Guard currently using this equipment'
    )
    
    assigned_site_id = fields.Many2one(
        'client.site',
        string='Assigned Site',
        tracking=True,
        help='Site where this equipment is located'
    )
    
    assignment_date = fields.Date(
        string='Assignment Date',
        tracking=True,
        help='Date equipment was assigned to current guard/site'
    )
    
    # Additional tracking fields
    barcode = fields.Char(
        string='Barcode',
        help='Barcode for scanning equipment'
    )
    
    rfid_tag = fields.Char(
        string='RFID Tag',
        help='RFID tag identifier'
    )
    
    nfc_tag = fields.Char(
        string='NFC Tag',
        help='NFC tag identifier for mobile scanning'
    )
    
    # Condition (more detailed than native status)
    condition = fields.Selection([
        ('new', 'New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('needs_replacement', 'Needs Replacement')
    ], string='Physical Condition', default='good', tracking=True)
    
    # Calibration (for certain equipment types)
    requires_calibration = fields.Boolean(
        string='Requires Calibration',
        help='Equipment needs regular calibration (e.g., metal detectors)'
    )
    
    last_calibration_date = fields.Date(
        string='Last Calibration',
        tracking=True
    )
    
    next_calibration_date = fields.Date(
        string='Next Calibration',
        tracking=True
    )
    
    calibration_interval_days = fields.Integer(
        string='Calibration Interval (days)',
        default=90,
        help='Days between calibration checks'
    )
    
    # Assignment history
    assignment_history_ids = fields.One2many(
        'guard.equipment.assignment.history',
        'equipment_id',
        string='Assignment History',
        help='Historical record of guard assignments'
    )
    
    assignment_count = fields.Integer(
        string='Assignment Count',
        compute='_compute_assignment_count'
    )
    
    # Storage location
    storage_location = fields.Char(
        string='Storage Location',
        help='Physical storage location when not in use'
    )
    
    # Photo
    equipment_photo = fields.Binary(
        string='Equipment Photo',
        attachment=True
    )
    
    @api.depends('assignment_history_ids')
    def _compute_assignment_count(self):
        """Count assignment history records."""
        for record in self:
            record.assignment_count = len(record.assignment_history_ids)
    
    def action_assign_to_guard(self):
        """Open wizard to assign equipment to a guard."""
        self.ensure_one()
        
        return {
            'name': _('Assign Equipment to Guard'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.equipment.assignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_equipment_id': self.id,
                'default_current_guard_id': self.assigned_guard_id.id,
                'default_current_site_id': self.assigned_site_id.id,
            }
        }
    
    def action_return_equipment(self):
        """Return equipment from guard."""
        self.ensure_one()
        
        if not self.assigned_guard_id:
            raise ValidationError(_('Equipment is not currently assigned to a guard.'))
        
        # Create history record
        self.env['guard.equipment.assignment.history'].create({
            'equipment_id': self.id,
            'guard_id': self.assigned_guard_id.id,
            'site_id': self.assigned_site_id.id if self.assigned_site_id else False,
            'assignment_date': self.assignment_date or fields.Date.today(),
            'return_date': fields.Date.today(),
            'action_type': 'returned',
        })
        
        self.write({
            'assigned_guard_id': False,
            'assigned_site_id': False,
            'assignment_date': False,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Equipment returned successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_view_assignment_history(self):
        """View assignment history for this equipment."""
        self.ensure_one()
        
        return {
            'name': _('Assignment History: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'guard.equipment.assignment.history',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
            'context': {'default_equipment_id': self.id}
        }
    
    @api.constrains('next_calibration_date', 'last_calibration_date')
    def _check_calibration_dates(self):
        """Validate calibration dates."""
        for record in self:
            if (record.next_calibration_date and record.last_calibration_date and
                    record.next_calibration_date <= record.last_calibration_date):
                raise ValidationError(_(
                    'Next calibration date must be after last calibration date.'
                ))
    
    @api.model
    def _cron_check_calibration_due(self):
        """
        Scheduled action to check for equipment requiring calibration.
        Creates maintenance requests for overdue calibrations.
        """
        from datetime import timedelta
        
        today = fields.Date.today()
        warning_date = today + timedelta(days=7)
        
        # Find equipment needing calibration
        equipment_due = self.search([
            ('is_guard_equipment', '=', True),
            ('requires_calibration', '=', True),
            ('next_calibration_date', '!=', False),
            ('next_calibration_date', '<=', warning_date),
        ])
        
        for equipment in equipment_due:
            # Check if maintenance request already exists
            existing_request = self.env['maintenance.request'].search([
                ('equipment_id', '=', equipment.id),
                ('maintenance_type', '=', 'calibration'),
                ('stage_id.done', '=', False),
            ], limit=1)
            
            if not existing_request:
                days_until = (equipment.next_calibration_date - today).days
                
                # Create maintenance request
                self.env['maintenance.request'].create({
                    'name': _('Calibration Due: %s') % equipment.name,
                    'equipment_id': equipment.id,
                    'maintenance_type': 'corrective',
                    'description': _(
                        'Calibration is due for this equipment on %s (in %d days).\n\n'
                        'Equipment: %s\n'
                        'Category: %s\n'
                        'Last Calibration: %s\n\n'
                        'Please schedule calibration to ensure equipment accuracy.'
                    ) % (
                        equipment.next_calibration_date,
                        days_until,
                        equipment.name,
                        dict(equipment._fields['equipment_category'].selection).get(
                            equipment.equipment_category, 'Unknown'
                        ),
                        equipment.last_calibration_date or 'Never'
                    ),
                    'priority': '2' if days_until <= 3 else '1',
                    'schedule_date': equipment.next_calibration_date,
                })
                
                _logger.info(
                    'Created calibration maintenance request for equipment %s',
                    equipment.name
                )
        
        return True


class GuardEquipmentAssignmentHistory(models.Model):
    """Track historical equipment assignments to guards."""
    
    _name = 'guard.equipment.assignment.history'
    _description = 'Guard Equipment Assignment History'
    _order = 'assignment_date desc, id desc'
    
    equipment_id = fields.Many2one(
        'maintenance.equipment',
        string='Equipment',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='restrict'
    )
    
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        ondelete='set null'
    )
    
    assignment_date = fields.Date(
        string='Assignment Date',
        required=True,
        default=fields.Date.today
    )
    
    return_date = fields.Date(
        string='Return Date'
    )
    
    action_type = fields.Selection([
        ('assigned', 'Assigned'),
        ('returned', 'Returned'),
        ('transferred', 'Transferred'),
    ], string='Action', required=True, default='assigned')
    
    notes = fields.Text(
        string='Notes'
    )
    
    condition_at_assignment = fields.Selection([
        ('new', 'New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ], string='Condition at Assignment')
    
    condition_at_return = fields.Selection([
        ('new', 'New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ], string='Condition at Return')
    
    duration_days = fields.Integer(
        string='Duration (days)',
        compute='_compute_duration',
        store=True
    )
    
    @api.depends('assignment_date', 'return_date')
    def _compute_duration(self):
        """Calculate assignment duration."""
        for record in self:
            if record.assignment_date and record.return_date:
                delta = record.return_date - record.assignment_date
                record.duration_days = delta.days
            else:
                record.duration_days = 0


class MaintenanceRequest(models.Model):
    """Extend maintenance requests for guard-specific features."""
    
    _inherit = 'maintenance.request'
    
    # Link to guard if they reported the issue
    reported_by_guard_id = fields.Many2one(
        'guard.profile',
        string='Reported by Guard',
        help='Guard who reported this maintenance issue'
    )
    
    # Link to site if equipment is at a specific location
    site_id = fields.Many2one(
        'client.site',
        string='Site Location',
        help='Site where the equipment is located'
    )
    
    is_guard_equipment = fields.Boolean(
        string='Guard Equipment',
        related='equipment_id.is_guard_equipment',
        store=True
    )


class MaintenanceTeam(models.Model):
    """Extend maintenance teams for guard-specific teams."""
    
    _inherit = 'maintenance.team'
    
    is_guard_equipment_team = fields.Boolean(
        string='Guard Equipment Team',
        default=False,
        help='This team manages guard equipment'
    )
    
    responsible_sites = fields.Many2many(
        'client.site',
        string='Responsible for Sites',
        help='Sites this maintenance team is responsible for'
    )

