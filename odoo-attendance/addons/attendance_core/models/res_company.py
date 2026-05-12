# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    attendance_geofence_alerts = fields.Boolean(
        string='Record geofence alerts',
        default=True,
        help='When enabled, Berkeley Workforce records geofence alerts when GPS check-ins are outside the configured area.',
    )
    attendance_location_log_retention_days = fields.Integer(
        string='Location log retention (days)',
        default=90,
        help='GPS location logs older than this are deleted by the nightly cleanup job.',
    )
    attendance_biometric_event_retention_days = fields.Integer(
        string='Biometric log retention (days)',
        default=180,
        help='Processed biometric events older than this may be deleted (done/error only).',
    )
    attendance_google_maps_api_key = fields.Char(
        string='Google Maps API key (Berkeley Workforce)',
        help='Browser key for the Location map client action. Restrict by HTTP referrer to your Odoo URL.',
    )
    attendance_twilio_account_sid = fields.Char(
        string='Twilio Account SID',
        help='Optional. Stored for future SMS integration; sending is not implemented in this module.',
    )
    attendance_twilio_auth_token = fields.Char(
        string='Twilio Auth Token',
        help='Optional. Keep secret.',
    )
    attendance_twilio_from_number = fields.Char(
        string='Twilio From (E.164)',
        help='Optional sender number, e.g. +15551234567',
    )
    attendance_odoo_sync_enabled = fields.Boolean(
        string='Replicate attendances to another Odoo',
        default=False,
        help='When enabled, each employee with an “Odoo → Odoo” routing rule will enqueue check-in/out copies '
             'on the configured target Odoo (XML-RPC, standard hr.attendance).',
    )
    attendance_export_s3_bucket = fields.Char(
        string='Scheduled export S3 bucket',
        groups='base.group_system',
        help='Optional. When set with keys, scheduled exports also upload CSV to S3 (requires boto3 on the server).',
    )
    attendance_export_s3_region = fields.Char(
        string='S3 region',
        default='eu-west-1',
        groups='base.group_system',
    )
    attendance_export_s3_access_key = fields.Char(string='S3 access key', groups='base.group_system')
    attendance_export_s3_secret_key = fields.Char(string='S3 secret key', groups='base.group_system')
