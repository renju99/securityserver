# -*- coding: utf-8 -*-
import base64
import logging
import csv
import io
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AttendanceScheduledExport(models.Model):
    _name = 'attendance.scheduled.export'
    _description = 'Scheduled attendance CSV export by email'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    preset_id = fields.Many2one(
        'attendance.report.preset',
        string='Report preset',
        required=True,
        ondelete='cascade',
    )
    partner_ids = fields.Many2many(
        'res.partner',
        string='Email recipients',
        help='Partners with an email receive the CSV.',
    )
    interval_number = fields.Integer(default=1, required=True)
    interval_type = fields.Selection(
        [('days', 'Days'), ('weeks', 'Weeks')],
        default='weeks',
        required=True,
    )
    next_run = fields.Datetime(string='Next run', default=fields.Datetime.now)
    last_run = fields.Datetime(readonly=True)

    def _build_csv(self):
        self.ensure_one()
        Attendance = self.env['hr.attendance'].sudo()
        domain = self.preset_id.sudo()._get_domain()
        domain = [('employee_id.company_id', 'child_of', self.company_id.id)] + list(domain)
        rows = Attendance.search_read(
            domain,
            [
                'employee_id',
                'check_in',
                'check_out',
                'worked_hours',
                'check_work_location_id',
                'in_mode',
                'out_mode',
                'review_status',
            ],
            limit=50000,
            order='check_in desc',
        )
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                'employee',
                'check_in',
                'check_out',
                'worked_hours',
                'work_location',
                'in_mode',
                'out_mode',
                'review_status',
            ]
        )
        for r in rows:
            emp = r.get('employee_id') and r['employee_id'][1]
            wl = r.get('check_work_location_id') and r['check_work_location_id'][1]
            writer.writerow(
                [
                    emp,
                    r.get('check_in') or '',
                    r.get('check_out') or '',
                    r.get('worked_hours') or '',
                    wl,
                    r.get('in_mode') or '',
                    r.get('out_mode') or '',
                    r.get('review_status') or '',
                ]
            )
        return buf.getvalue().encode('utf-8')

    def _send_export(self):
        self.ensure_one()
        if not self.partner_ids:
            return
        csv_bytes = self._build_csv()
        fname = 'attendance_export_%s.csv' % fields.Date.context_today(self).strftime('%Y%m%d')
        attachment = self.env['ir.attachment'].sudo().create(
            {
                'name': fname,
                'type': 'binary',
                'datas': base64.b64encode(csv_bytes).decode(),
                'mimetype': 'text/csv',
                'res_model': self._name,
                'res_id': self.id,
            }
        )
        emails = [p.email for p in self.partner_ids if p.email]
        if not emails:
            return
        self.env['mail.mail'].sudo().create(
            {
                'subject': self.name,
                'body_html': '<p>Scheduled attendance export (CSV attached).</p>',
                'email_to': ','.join(emails),
                'attachment_ids': [(6, 0, [attachment.id])],
            }
        ).send()
        self.last_run = fields.Datetime.now()
        self._upload_csv_to_s3_if_configured(csv_bytes, fname)

    def _upload_csv_to_s3_if_configured(self, csv_bytes, fname):
        self.ensure_one()
        company = self.company_id.sudo()
        if not company.attendance_export_s3_bucket or not company.attendance_export_s3_access_key:
            return
        try:
            import boto3  # noqa: PLC0415
        except ImportError:
            _logger.warning('boto3 is not installed; skipping S3 upload for scheduled export %s', self.name)
            return
        try:
            client = boto3.client(
                's3',
                region_name=company.attendance_export_s3_region or 'eu-west-1',
                aws_access_key_id=company.attendance_export_s3_access_key,
                aws_secret_access_key=company.attendance_export_s3_secret_key or '',
            )
            key = 'berkeley-workforce/exports/%s' % fname
            client.put_object(
                Bucket=company.attendance_export_s3_bucket,
                Key=key,
                Body=csv_bytes,
                ContentType='text/csv; charset=utf-8',
            )
        except Exception:  # noqa: BLE001
            _logger.exception('S3 upload failed for export %s', self.name)

    def _advance_next_run(self):
        for rec in self:
            if rec.interval_type == 'days':
                delta = timedelta(days=max(rec.interval_number, 1))
            else:
                delta = timedelta(weeks=max(rec.interval_number, 1))
            rec.next_run = fields.Datetime.now() + delta

    @api.model
    def cron_run_due_exports(self):
        now = fields.Datetime.now()
        due = self.search([('active', '=', True), ('next_run', '<=', now)])
        for rec in due:
            try:
                rec._send_export()
            except Exception:
                _logger.exception('Scheduled export failed for %s', rec.name)
            rec._advance_next_run()
