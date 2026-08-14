# -*- coding: utf-8 -*-
"""Guard Activity Report (GAR) — per-guard daily activity snapshot for supervisors."""

from datetime import timedelta
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class GuardActivityReport(models.Model):
    """Per-guard daily activity report (supervisor/admin print-only)."""

    _name = 'guard.activity.report'
    _description = 'Guard Activity Report (GAR)'
    _inherit = ['mail.thread']
    _order = 'report_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Reference',
        required=True,
        default='New',
        copy=False,
        readonly=True,
        index=True,
    )
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        tracking=True,
        index=True,
        ondelete='restrict',
    )
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True,
        tracking=True,
        index=True,
        ondelete='restrict',
        help='Site to report activity for. Activities are filtered to this site.',
    )
    report_date = fields.Date(
        string='Report Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        index=True,
    )
    badge_number = fields.Char(
        related='guard_id.badge_number',
        string='Badge No.',
        readonly=True,
    )
    client_id = fields.Many2one(
        related='site_id.client_id',
        string='Client',
        readonly=True,
        store=True,
    )
    notes = fields.Html(
        string='Supervisor Notes',
        help='Optional notes for this end-of-day snapshot',
    )

    # Auto-populated activity links
    incident_ids = fields.Many2many(
        'incident.report',
        'gar_incident_rel',
        'gar_id',
        'incident_id',
        string='Incidents',
        compute='_compute_activities',
        store=True,
    )
    tour_log_ids = fields.Many2many(
        'tour.log',
        'gar_tour_log_rel',
        'gar_id',
        'tour_log_id',
        string='Patrol Logs',
        compute='_compute_activities',
        store=True,
    )
    visitor_ids = fields.Many2many(
        'visitor.management',
        'gar_visitor_rel',
        'gar_id',
        'visitor_id',
        string='Visitors',
        compute='_compute_activities',
        store=True,
    )
    attendance_ids = fields.Many2many(
        'guard.attendance',
        'gar_attendance_rel',
        'gar_id',
        'attendance_id',
        string='Attendance',
        compute='_compute_activities',
        store=True,
    )
    task_ids = fields.Many2many(
        'guard.task',
        'gar_task_rel',
        'gar_id',
        'task_id',
        string='Tasks',
        compute='_compute_activities',
        store=True,
    )
    package_ids = fields.Many2many(
        'package.management',
        'gar_package_rel',
        'gar_id',
        'package_id',
        string='Packages',
        compute='_compute_activities',
        store=True,
    )
    lost_found_ids = fields.Many2many(
        'lost.found.item',
        'gar_lost_found_rel',
        'gar_id',
        'lost_found_id',
        string='Lost & Found',
        compute='_compute_activities',
        store=True,
    )

    incident_count = fields.Integer(compute='_compute_counts', store=True)
    tour_count = fields.Integer(compute='_compute_counts', store=True)
    tours_completed = fields.Integer(compute='_compute_counts', store=True)
    visitor_count = fields.Integer(compute='_compute_counts', store=True)
    task_count = fields.Integer(compute='_compute_counts', store=True)
    task_completed_count = fields.Integer(compute='_compute_counts', store=True)
    package_count = fields.Integer(compute='_compute_counts', store=True)
    lost_found_count = fields.Integer(compute='_compute_counts', store=True)
    attendance_count = fields.Integer(compute='_compute_counts', store=True)
    hours_worked = fields.Float(
        string='Hours Worked',
        compute='_compute_counts',
        store=True,
        digits=(16, 2),
    )
    critical_incidents = fields.Integer(compute='_compute_counts', store=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'gar_guard_site_date_uniq',
            'unique(guard_id, site_id, report_date)',
            'A Guard Activity Report already exists for this guard, site, and date.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('guard.activity.report')
                    or 'New'
                )
        return super().create(vals_list)

    @api.constrains('guard_id', 'site_id', 'report_date')
    def _check_required_keys(self):
        for rec in self:
            if not rec.guard_id or not rec.site_id or not rec.report_date:
                raise ValidationError(
                    _('Guard, Site, and Report Date are required.')
                )

    def _date_window(self):
        self.ensure_one()
        date_start = fields.Datetime.to_datetime(self.report_date)
        return date_start, date_start + timedelta(days=1)

    @api.depends('guard_id', 'site_id', 'report_date')
    def _compute_activities(self):
        Incident = self.env['incident.report']
        TourLog = self.env['tour.log']
        Visitor = self.env['visitor.management']
        Attendance = self.env['guard.attendance']
        Task = self.env['guard.task']
        Package = self.env['package.management']
        LostFound = self.env['lost.found.item']

        for report in self:
            if not report.guard_id or not report.site_id or not report.report_date:
                report.incident_ids = False
                report.tour_log_ids = False
                report.visitor_ids = False
                report.attendance_ids = False
                report.task_ids = False
                report.package_ids = False
                report.lost_found_ids = False
                continue

            date_start, date_end = report._date_window()
            guard = report.guard_id.id
            site = report.site_id.id

            report.incident_ids = Incident.search([
                ('site_id', '=', site),
                ('guard_id', '=', guard),
                ('incident_datetime', '>=', date_start),
                ('incident_datetime', '<', date_end),
            ])
            report.tour_log_ids = TourLog.search([
                ('site_id', '=', site),
                ('guard_id', '=', guard),
                ('start_time', '>=', date_start),
                ('start_time', '<', date_end),
            ])
            report.visitor_ids = Visitor.search([
                ('site_id', '=', site),
                ('visit_date', '=', report.report_date),
                '|',
                ('guard_checkin_id', '=', guard),
                ('guard_checkout_id', '=', guard),
            ])
            report.attendance_ids = Attendance.search([
                ('site_id', '=', site),
                ('guard_id', '=', guard),
                ('checkin_time', '>=', date_start),
                ('checkin_time', '<', date_end),
            ])
            report.task_ids = Task.search([
                ('site_id', '=', site),
                ('assigned_to', '=', guard),
                '|',
                '&',
                ('due_date', '>=', date_start),
                ('due_date', '<', date_end),
                '&',
                ('completed_date', '>=', date_start),
                ('completed_date', '<', date_end),
            ])
            report.package_ids = Package.search([
                ('site_id', '=', site),
                ('received_by', '=', guard),
                ('received_date', '>=', date_start),
                ('received_date', '<', date_end),
            ])
            report.lost_found_ids = LostFound.search([
                ('site_id', '=', site),
                ('guard_logged_by', '=', guard),
                ('found_date', '>=', date_start),
                ('found_date', '<', date_end),
            ])

    @api.depends(
        'incident_ids', 'tour_log_ids', 'visitor_ids', 'attendance_ids',
        'task_ids', 'package_ids', 'lost_found_ids',
    )
    def _compute_counts(self):
        for report in self:
            report.incident_count = len(report.incident_ids)
            report.critical_incidents = len(
                report.incident_ids.filtered(lambda i: i.severity == 'critical')
            )
            report.tour_count = len(report.tour_log_ids)
            report.tours_completed = len(
                report.tour_log_ids.filtered(lambda t: t.status == 'completed')
            )
            report.visitor_count = len(report.visitor_ids)
            report.task_count = len(report.task_ids)
            report.task_completed_count = len(
                report.task_ids.filtered(lambda t: t.state == 'completed')
            )
            report.package_count = len(report.package_ids)
            report.lost_found_count = len(report.lost_found_ids)
            report.attendance_count = len(report.attendance_ids)
            report.hours_worked = sum(report.attendance_ids.mapped('hours_worked'))

    def action_refresh_data(self):
        """Recompute activity links from live records."""
        self.ensure_one()
        self._compute_activities()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Data Refreshed'),
                'message': _('Guard activity data has been refreshed.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            'guardpro.action_guard_activity_report_pdf'
        ).report_action(self)
