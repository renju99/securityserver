# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AttendancePolicyRule(models.Model):
    _name = 'attendance.policy.rule'
    _description = 'Attendance policy rule'
    _order = 'company_id, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    work_location_id = fields.Many2one('hr.work.location', string='Work location', ondelete='cascade')
    resource_calendar_id = fields.Many2one(
        'resource.calendar',
        string='Working schedule (shift)',
        help='Optional: tie this policy to a specific working schedule.',
    )
    overtime_after_minutes = fields.Integer(string='Overtime after (minutes)', default=480)
    paid_break_minutes = fields.Integer(default=0)
    unpaid_break_minutes = fields.Integer(default=0)
    max_shift_minutes = fields.Integer(string='Max shift (minutes)')
    require_approval_manual = fields.Boolean(string='Require approval (manual punches)', default=False)
    require_approval_offline = fields.Boolean(
        string='Require approval (mobile / systray)',
        default=False,
        help='When enabled, check-ins created with systray/mobile mode can be set to pending review.',
    )
    require_approval_kiosk = fields.Boolean(
        string='Require approval (kiosk / biometric)',
        default=False,
    )
    active = fields.Boolean(default=True)

    @api.depends('work_location_id', 'resource_calendar_id')
    def _compute_name(self):
        for rec in self:
            parts = []
            if rec.work_location_id:
                parts.append(rec.work_location_id.display_name)
            if rec.resource_calendar_id:
                parts.append(rec.resource_calendar_id.display_name)
            rec.name = ' / '.join(parts) if parts else 'Global policy'

    @api.model
    def get_policy_for_employee(self, employee, work_location):
        if not employee:
            return self.browse()
        company = employee.company_id
        if not company:
            return self.browse()
        base = [('company_id', '=', company.id), ('active', '=', True)]
        cal = employee.resource_calendar_id
        def _match_cal(rec):
            if not rec.resource_calendar_id:
                return True
            return rec.resource_calendar_id == cal

        if work_location:
            found = self.search(base + [('work_location_id', '=', work_location.id)])
            found = found.filtered(_match_cal)
            if found[:1]:
                return found[:1]
        found = self.search(base + [('work_location_id', '=', False)])
        found = found.filtered(_match_cal)
        return found[:1]
