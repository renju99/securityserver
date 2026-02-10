# -*- coding: utf-8 -*-
"""Equipment Model - Asset Tracking."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class Equipment(models.Model):
    """Security Equipment and Asset Tracking."""

    _name = 'guardpro.equipment'
    _description = 'Security Equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # Basic Information
    name = fields.Char(
        string='Equipment Name',
        required=True,
        tracking=True,
        index=True
    )
    code = fields.Char(
        string='Equipment Code',
        required=True,
        copy=False,
        tracking=True,
        index=True
    )
    serial_number = fields.Char(
        string='Serial Number',
        copy=False,
        tracking=True
    )
    
    # Category
    category = fields.Selection([
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
        ('other', 'Other')
    ], string='Category', required=True, tracking=True)
    
    # Description
    description = fields.Text(
        string='Description'
    )
    manufacturer = fields.Char(
        string='Manufacturer'
    )
    model = fields.Char(
        string='Model'
    )
    
    # Status
    status = fields.Selection([
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('maintenance', 'Under Maintenance'),
        ('damaged', 'Damaged'),
        ('lost', 'Lost'),
        ('retired', 'Retired')
    ], string='Status', default='available', required=True, tracking=True)
    
    # Assignment
    assigned_to = fields.Many2one(
        'guard.profile',
        string='Assigned To',
        tracking=True
    )
    assignment_date = fields.Date(
        string='Assignment Date',
        tracking=True
    )
    assigned_site = fields.Many2one(
        'client.site',
        string='Assigned Site',
        tracking=True
    )
    
    # Purchase Information
    purchase_date = fields.Date(
        string='Purchase Date'
    )
    purchase_cost = fields.Float(
        string='Purchase Cost',
        digits=(10, 2)
    )
    supplier = fields.Many2one(
        'res.partner',
        string='Supplier'
    )
    warranty_expiry = fields.Date(
        string='Warranty Expiry Date'
    )
    
    # Maintenance
    last_maintenance = fields.Date(
        string='Last Maintenance Date'
    )
    next_maintenance = fields.Date(
        string='Next Maintenance Date',
        tracking=True
    )
    maintenance_interval = fields.Integer(
        string='Maintenance Interval (days)',
        default=90
    )
    maintenance_notes = fields.Text(
        string='Maintenance Notes'
    )
    
    # Tracking
    barcode = fields.Char(
        string='Barcode'
    )
    rfid_tag = fields.Char(
        string='RFID Tag'
    )
    
    # Condition
    condition = fields.Selection([
        ('new', 'New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor')
    ], string='Condition', default='new', tracking=True)
    
    # Location
    current_location = fields.Char(
        string='Current Location'
    )
    storage_location = fields.Char(
        string='Storage Location'
    )
    
    # Notes
    notes = fields.Text(
        string='Notes'
    )
    
    # History
    assignment_log_ids = fields.One2many(
        'equipment.assignment.log',
        'equipment_id',
        string='Assignment History'
    )
    maintenance_log_ids = fields.One2many(
        'equipment.maintenance.log',
        'equipment_id',
        string='Maintenance History'
    )
    
    # Attachments
    photo = fields.Binary(
        string='Equipment Photo',
        attachment=True
    )
    documents = fields.Many2many(
        'ir.attachment',
        string='Related Documents'
    )
    
    _sql_constraints = [
        ('code_unique', 'unique(code)',
         'Equipment code must be unique!'),
        ('serial_unique', 'unique(serial_number)',
         'Serial number must be unique!'),
    ]

    @api.constrains('warranty_expiry')
    def _check_warranty(self):
        """Warn if warranty is expiring soon."""
        for record in self:
            if record.warranty_expiry:
                days_to_expiry = (record.warranty_expiry - fields.Date.today()).days
                if 0 < days_to_expiry <= 30:
                    _logger.warning('Equipment %s warranty expiring in %d days',
                                    record.name, days_to_expiry)

    def action_assign(self, guard_id, site_id=None):
        """
        Assign equipment to a guard.
        
        Args:
            guard_id (int): ID of guard to assign to
            site_id (int): Optional site ID
        """
        self.ensure_one()
        
        if self.status != 'available':
            raise ValidationError(_(
                'Equipment is not available for assignment!'
            ))
        
        # Create assignment log
        self.env['equipment.assignment.log'].create({
            'equipment_id': self.id,
            'guard_id': guard_id,
            'site_id': site_id,
            'assignment_date': fields.Date.today(),
            'action_type': 'assigned'
        })
        
        self.write({
            'status': 'assigned',
            'assigned_to': guard_id,
            'assigned_site': site_id,
            'assignment_date': fields.Date.today()
        })

    def action_return(self):
        """Return equipment from guard."""
        self.ensure_one()
        
        if not self.assigned_to:
            raise ValidationError(_('Equipment is not assigned!'))
        
        # Create return log
        self.env['equipment.assignment.log'].create({
            'equipment_id': self.id,
            'guard_id': self.assigned_to.id,
            'site_id': self.assigned_site.id if self.assigned_site else None,
            'return_date': fields.Date.today(),
            'action_type': 'returned'
        })
        
        self.write({
            'status': 'available',
            'assigned_to': False,
            'assigned_site': False
        })

    def action_maintenance(self):
        """Mark equipment for maintenance."""
        self.write({'status': 'maintenance'})

    def action_complete_maintenance(self):
        """Complete maintenance and mark as available."""
        self.ensure_one()
        
        # Create maintenance log
        self.env['equipment.maintenance.log'].create({
            'equipment_id': self.id,
            'maintenance_date': fields.Date.today(),
            'notes': 'Maintenance completed'
        })
        
        # Calculate next maintenance
        next_date = fields.Date.today() + timedelta(
            days=self.maintenance_interval
        )
        
        self.write({
            'status': 'available',
            'last_maintenance': fields.Date.today(),
            'next_maintenance': next_date
        })
    
    # ====================================================
    # SCHEDULED ACTIONS (CRON JOBS)
    # ====================================================
    
    @api.model
    def send_maintenance_reminders(self):
        """Send reminders for equipment maintenance due soon.
        
        Called by scheduled action daily at 9 AM.
        Sends alerts for equipment maintenance due within 7 days.
        """
        from datetime import datetime, timedelta
        
        today = fields.Date.today()
        warning_date = today + timedelta(days=7)
        critical_date = today + timedelta(days=3)
        
        # Find equipment needing maintenance
        equipment_due = self.search([
            ('next_maintenance', '!=', False),
            ('next_maintenance', '<=', warning_date),
            ('next_maintenance', '>=', today),
            ('status', 'in', ['available', 'in_use'])
        ])
        
        if equipment_due:
            _logger.info('Found %d equipment items needing maintenance', len(equipment_due))
        
        for equipment in equipment_due:
            days_until = (equipment.next_maintenance - today).days
            
            # Determine urgency
            if days_until <= 3:
                priority = 'urgent'
                activity_type = 'mail.mail_activity_data_urgent'
            else:
                priority = 'normal'
                activity_type = 'mail.mail_activity_data_todo'
            
            try:
                # Create activity for equipment manager
                equipment.activity_schedule(
                    activity_type,
                    summary=_('Equipment Maintenance Due: %s') % equipment.name,
                    note=_(
                        'Equipment %s (%s) is due for maintenance in %d days on %s.\n\n'
                        'Type: %s\n'
                        'Serial Number: %s\n'
                        'Status: %s\n\n'
                        'Please schedule maintenance to avoid equipment downtime.'
                    ) % (
                        equipment.name,
                        equipment.equipment_code,
                        days_until,
                        equipment.next_maintenance,
                        equipment.equipment_type,
                        equipment.serial_number or 'N/A',
                        equipment.status
                    ),
                    user_id=self.env.ref('base.group_system').users[0].id if self.env.ref('base.group_system').users else self.env.user.id
                )
                
                _logger.info('Created maintenance reminder for equipment %s (due in %d days)',
                           equipment.name, days_until)
                           
            except Exception as e:
                _logger.error('Error creating maintenance reminder for equipment %s: %s',
                            equipment.id, str(e))
        
        # Check for overdue maintenance
        overdue_equipment = self.search([
            ('next_maintenance', '<', today),
            ('status', 'in', ['available', 'in_use'])
        ])
        
        if overdue_equipment:
            _logger.warning('Found %d equipment items with overdue maintenance', len(overdue_equipment))
            
            for equipment in overdue_equipment:
                equipment.write({'status': 'maintenance_due'})
        
        return True


class EquipmentAssignmentLog(models.Model):
    """Equipment Assignment History."""

    _name = 'equipment.assignment.log'
    _description = 'Equipment Assignment Log'
    _order = 'assignment_date desc'

    equipment_id = fields.Many2one(
        'guardpro.equipment',
        string='Equipment',
        required=True,
        ondelete='cascade'
    )
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True
    )
    site_id = fields.Many2one(
        'client.site',
        string='Site'
    )
    assignment_date = fields.Date(
        string='Assignment Date',
        default=fields.Date.today
    )
    return_date = fields.Date(
        string='Return Date'
    )
    action_type = fields.Selection([
        ('assigned', 'Assigned'),
        ('returned', 'Returned'),
        ('transferred', 'Transferred')
    ], string='Action Type', required=True)
    notes = fields.Text(
        string='Notes'
    )


class EquipmentMaintenanceLog(models.Model):
    """Equipment Maintenance History."""

    _name = 'equipment.maintenance.log'
    _description = 'Equipment Maintenance Log'
    _order = 'maintenance_date desc'

    equipment_id = fields.Many2one(
        'guardpro.equipment',
        string='Equipment',
        required=True,
        ondelete='cascade'
    )
    maintenance_date = fields.Date(
        string='Maintenance Date',
        required=True,
        default=fields.Date.today
    )
    maintenance_type = fields.Selection([
        ('routine', 'Routine Maintenance'),
        ('repair', 'Repair'),
        ('inspection', 'Inspection'),
        ('calibration', 'Calibration')
    ], string='Type', default='routine')
    technician = fields.Char(
        string='Technician'
    )
    cost = fields.Float(
        string='Maintenance Cost',
        digits=(10, 2)
    )
    notes = fields.Text(
        string='Maintenance Notes'
    )


