# -*- coding: utf-8 -*-
"""Shift Assignment Wizard."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class ShiftAssignmentWizard(models.TransientModel):
    """Wizard for bulk shift assignment."""

    _name = 'shift.assignment.wizard'
    _description = 'Shift Assignment Wizard'

    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True
    )
    guard_ids = fields.Many2many(
        'guard.profile',
        string='Guards',
        required=True
    )
    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.today
    )
    end_date = fields.Date(
        string='End Date',
        required=True
    )
    shift_type = fields.Selection([
        ('day', 'Day Shift (8:00-16:00)'),
        ('evening', 'Evening Shift (16:00-00:00)'),
        ('night', 'Night Shift (00:00-08:00)'),
        ('custom', 'Custom')
    ], string='Shift Type', default='day', required=True)
    
    custom_start_time = fields.Float(
        string='Start Time (Hour)',
        default=8.0
    )
    custom_end_time = fields.Float(
        string='End Time (Hour)',
        default=16.0
    )
    
    assignment_type = fields.Selection([
        ('patrol', 'Patrol'),
        ('static', 'Static Post'),
        ('event', 'Special Event')
    ], string='Assignment Type', default='patrol')

    def action_create_shifts(self):
        """Create shifts based on wizard parameters."""
        self.ensure_one()
        
        shift_times = {
            'day': (8, 16),
            'evening': (16, 24),
            'night': (0, 8),
            'custom': (self.custom_start_time, self.custom_end_time)
        }
        
        start_hour, end_hour = shift_times[self.shift_type]
        
        shifts = self.env['guard.shift']
        current_date = self.start_date
        
        while current_date <= self.end_date:
            for guard in self.guard_ids:
                start_dt = fields.Datetime.from_string(
                    f"{current_date} {int(start_hour):02d}:00:00"
                )
                end_dt = fields.Datetime.from_string(
                    f"{current_date} {int(end_hour):02d}:00:00"
                )
                
                shifts |= self.env['guard.shift'].create({
                    'guard_id': guard.id,
                    'site_id': self.site_id.id,
                    'start_datetime': start_dt,
                    'end_datetime': end_dt,
                    'assignment_type': self.assignment_type,
                    'status': 'scheduled'
                })
            
            current_date = current_date + timedelta(days=1)
        
        return {
            'name': _('Created Shifts'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.shift',
            'view_mode': 'calendar,list,form',
            'domain': [('id', 'in', shifts.ids)],
        }


