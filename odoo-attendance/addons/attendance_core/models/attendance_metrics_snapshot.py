# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AttendanceMetricsSnapshot(models.Model):
    _name = 'attendance.metrics.snapshot'
    _description = 'Berkeley Workforce HR metrics snapshot'
    _order = 'snapshot_time desc'

    name = fields.Char(default='Snapshot', required=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    snapshot_time = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    open_attendance_count = fields.Integer(string='Open attendances')
    pending_review_count = fields.Integer(string='Pending reviews')
    biometric_pending_count = fields.Integer(string='Biometric events pending')
    geofence_open_alert_count = fields.Integer(string='Open geofence alerts')

    @api.model
    def cron_collect_metrics(self):
        Attendance = self.env['hr.attendance'].sudo()
        Event = self.env['attendance.biometric.event'].sudo()
        Alert = self.env['attendance.geofence.alert'].sudo()
        for company in self.env['res.company'].search([]):
            open_cnt = Attendance.search_count(
                [('employee_id.company_id', 'child_of', company.id), ('check_out', '=', False)]
            )
            pending_cnt = Attendance.search_count(
                [
                    ('employee_id.company_id', 'child_of', company.id),
                    ('review_status', '=', 'pending'),
                ]
            )
            bio_cnt = Event.search_count(
                [('company_id', '=', company.id), ('state', '=', 'pending')]
            )
            alert_cnt = Alert.search_count(
                [('company_id', '=', company.id), ('state', '=', 'open')]
            )
            self.create(
                {
                    'company_id': company.id,
                    'open_attendance_count': open_cnt,
                    'pending_review_count': pending_cnt,
                    'biometric_pending_count': bio_cnt,
                    'geofence_open_alert_count': alert_cnt,
                }
            )

    @api.model
    def cron_cleanup_retention(self):
        """Delete old location logs / processed biometric rows per company retention."""
        Log = self.env['attendance.location.log'].sudo()
        Bio = self.env['attendance.biometric.event'].sudo()
        Snap = self.env['attendance.metrics.snapshot'].sudo()
        now = fields.Datetime.now()
        for company in self.env['res.company'].search([]):
            loc_days = int(company.attendance_location_log_retention_days or 90)
            bio_days = int(company.attendance_biometric_event_retention_days or 180)
            horizon_loc = now - timedelta(days=loc_days)
            horizon_bio = now - timedelta(days=bio_days)
            try:
                Log.search([('create_date', '<', horizon_loc), ('company_id', '=', company.id)]).unlink()
                Bio.search(
                    [
                        ('create_date', '<', horizon_bio),
                        ('company_id', '=', company.id),
                        ('state', 'in', ('done', 'error')),
                    ]
                ).unlink()
            except Exception:
                _logger.exception('Retention cleanup failed for company %s', company.id)
        old_snaps = now - timedelta(days=400)
        Snap.search([('snapshot_time', '<', old_snaps)]).unlink()
