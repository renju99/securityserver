# -*- coding: utf-8 -*-
"""Wizard for generating shifts from template with date range selection."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
from calendar import monthrange


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
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
    )
    preview_date_count = fields.Integer(
        string='Matching days',
        compute='_compute_preview',
    )
    preview_shift_count = fields.Integer(
        string='Shifts to create',
        compute='_compute_preview',
    )
    recurrence_summary = fields.Char(
        string='Pattern',
        compute='_compute_preview',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        template_id = (
            self.env.context.get('default_template_id')
            or self.env.context.get('active_id')
        )
        if template_id:
            template = self.env['shift.template'].browse(template_id)
            res['template_id'] = template_id
            res['start_date'] = template.generation_start_date or fields.Date.today()
            res['end_date'] = (
                template.generation_end_date
                or (fields.Date.today() + timedelta(days=13))
            )
        elif 'end_date' in fields_list and not res.get('end_date'):
            res['end_date'] = fields.Date.today() + timedelta(days=13)
        return res

    @api.depends('template_id', 'start_date', 'end_date')
    def _compute_preview(self):
        for wiz in self:
            template = wiz.template_id
            if not template or not wiz.start_date or not wiz.end_date or wiz.end_date < wiz.start_date:
                wiz.preview_date_count = 0
                wiz.preview_shift_count = 0
                wiz.recurrence_summary = ''
                continue
            dates = list(template._iter_matching_dates(wiz.start_date, wiz.end_date))
            guards = template._get_template_guards()
            wiz.preview_date_count = len(dates)
            wiz.preview_shift_count = len(dates) * len(guards) if guards else 0
            if template.recurrence_type == 'daily':
                wiz.recurrence_summary = _('Daily')
            elif template.recurrence_type == 'weekly':
                days = []
                labels = [
                    ('monday', _('Mon')), ('tuesday', _('Tue')),
                    ('wednesday', _('Wed')), ('thursday', _('Thu')),
                    ('friday', _('Fri')), ('saturday', _('Sat')),
                    ('sunday', _('Sun')),
                ]
                for field_name, label in labels:
                    if getattr(template, field_name):
                        days.append(label)
                wiz.recurrence_summary = _('Weekly: %s') % (', '.join(days) or _('none'))
            else:
                wiz.recurrence_summary = _('Monthly: day %s') % (template.day_of_month or 1)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.end_date < record.start_date:
                raise ValidationError(_('End date must be after start date.'))

    def action_preset_this_week(self):
        self.ensure_one()
        today = fields.Date.today()
        start = today - timedelta(days=today.weekday())
        self.start_date = start
        self.end_date = start + timedelta(days=6)
        return False

    def action_preset_next_14(self):
        self.ensure_one()
        today = fields.Date.today()
        self.start_date = today
        self.end_date = today + timedelta(days=13)
        return False

    def action_preset_next_month(self):
        self.ensure_one()
        today = fields.Date.today()
        if today.month == 12:
            first_next = today.replace(year=today.year + 1, month=1, day=1)
        else:
            first_next = today.replace(month=today.month + 1, day=1)
        last_day = monthrange(first_next.year, first_next.month)[1]
        self.start_date = first_next
        self.end_date = first_next.replace(day=last_day)
        return False

    def action_generate_shifts(self):
        """Generate shifts and open the resulting list."""
        self.ensure_one()
        template = self.template_id
        guards = template._get_template_guards()
        if not guards:
            raise ValidationError(_(
                'Please select at least one guard for template "%s" before generating shifts.'
            ) % template.name)

        # Persist chosen range on the template for next time
        template.write({
            'generation_start_date': self.start_date,
            'generation_end_date': self.end_date,
        })

        return template.action_generate_shifts(
            start_date=self.start_date,
            end_date=self.end_date,
            ignore_recurrence=False,
        )
