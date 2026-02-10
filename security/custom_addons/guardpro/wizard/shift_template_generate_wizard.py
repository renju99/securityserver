# -*- coding: utf-8 -*-
"""Wizard for generating shifts from template with date range selection."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class ShiftTemplateGenerateWizard(models.TransientModel):
    """Wizard for generating shifts from template with date range."""

    _name = 'shift.template.generate.wizard'
    _description = 'Generate Shifts from Template Wizard'

    template_id = fields.Many2one(
        'shift.template',
        string='Template',
        required=True,
        readonly=True
    )
    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.today,
        help='First date to generate shifts from'
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
        help='Last date to generate shifts to'
    )

    @api.model
    def default_get(self, fields_list):
        """Set default values."""
        res = super().default_get(fields_list)
        
        # Get template from context
        template_id = self.env.context.get('active_id')
        if template_id:
            template = self.env['shift.template'].browse(template_id)
            res['template_id'] = template_id
            res['start_date'] = template.generation_start_date or fields.Date.today()
            res['end_date'] = template.generation_end_date or (fields.Date.today() + timedelta(days=30))
        
        return res

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        """Validate date range."""
        for record in self:
            if record.end_date < record.start_date:
                raise ValidationError(_('End date must be after start date.'))

    def action_generate_shifts(self):
        """Generate shifts from template for the selected date range."""
        self.ensure_one()
        
        # Support both old guard_id field and new guard_ids field
        guards = self.template_id.guard_ids if self.template_id.guard_ids else (
            self.template_id.guard_id if self.template_id.guard_id else self.env['guard.profile']
        )
        
        if not guards:
            raise ValidationError(_(
                'Please select at least one guard for template "%s" before generating shifts.'
            ) % self.template_id.name)
        
        # Generate shifts using the template's method
        # Set ignore_recurrence=False to respect the recurrence pattern
        # Daily: creates for all days, Weekly/Monthly: creates only 1 shift
        result = self.template_id.action_generate_shifts(
            start_date=self.start_date,
            end_date=self.end_date,
            ignore_recurrence=False  # Respect recurrence pattern
        )
        
        return result

