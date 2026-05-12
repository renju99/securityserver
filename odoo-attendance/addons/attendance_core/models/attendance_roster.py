# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AttendanceRosterTemplate(models.Model):
    _name = 'attendance.roster.template'
    _description = 'Roster template (weekly pattern)'
    _order = 'name'

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    work_location_id = fields.Many2one('hr.work.location', string='Work location')
    line_ids = fields.One2many('attendance.roster.template.line', 'template_id', string='Lines')
    active = fields.Boolean(default=True)


class AttendanceRosterTemplateLine(models.Model):
    _name = 'attendance.roster.template.line'
    _description = 'Roster template weekday line'
    _order = 'weekday, time_from'

    template_id = fields.Many2one(
        'attendance.roster.template',
        required=True,
        ondelete='cascade',
    )
    weekday = fields.Selection(
        [
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
        ],
        string='Day',
        required=True,
    )
    time_from = fields.Float(string='From', required=True, help='Decimal hours, e.g. 8.5 = 08:30')
    time_to = fields.Float(string='To', required=True)
    resource_calendar_id = fields.Many2one('resource.calendar', string='Working schedule')


class AttendanceRosterAssignment(models.Model):
    _name = 'attendance.roster.assignment'
    _description = 'Planned roster assignment'
    _order = 'date_start desc, employee_id'

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    employee_id = fields.Many2one('hr.employee', required=True, ondelete='cascade')
    template_id = fields.Many2one('attendance.roster.template', required=True, ondelete='cascade')
    date_start = fields.Date(required=True)
    date_end = fields.Date(help='Optional end date for this assignment block.')
    date_stop = fields.Date(compute='_compute_date_stop', string='End (calendar)')

    @api.depends('employee_id', 'template_id')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s — %s' % (
                rec.employee_id.display_name if rec.employee_id else '',
                rec.template_id.display_name if rec.template_id else '',
            )

    @api.depends('date_start', 'date_end')
    def _compute_date_stop(self):
        for rec in self:
            rec.date_stop = rec.date_end or rec.date_start
