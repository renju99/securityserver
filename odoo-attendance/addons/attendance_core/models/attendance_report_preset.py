# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


class AttendanceReportPreset(models.Model):
    _name = 'attendance.report.preset'
    _description = 'Saved attendance report filter'
    _order = 'name'

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    user_id = fields.Many2one('res.users', string='Owner', default=lambda self: self.env.user)
    domain_char = fields.Text(
        string='Domain (Python list)',
        default='[]',
        help='Odoo domain on hr.attendance, e.g. [(\"employee_id\",\"=\",1)]',
    )

    def _get_domain(self):
        self.ensure_one()
        try:
            dom = safe_eval(self.domain_char.strip() or '[]', {'context': self.env.context})
        except (SyntaxError, ValueError, TypeError) as err:
            raise UserError(_('Invalid domain: %s') % err) from err
        if not isinstance(dom, (list, tuple)):
            raise UserError(_('Domain must evaluate to a list or tuple.'))
        return list(dom)

    def action_open_attendances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'hr.attendance',
            'view_mode': 'list,pivot,graph,form',
            'domain': self._get_domain(),
            'context': dict(self.env.context),
        }
