# -*- coding: utf-8 -*-
from odoo import fields, models


class HrWorkLocation(models.Model):
    _inherit = 'hr.work.location'

    attendance_nfc_payload = fields.Char(
        string='NFC verification token',
        groups='hr.group_hr_user',
        help='Optional secret compared against kiosk/mobile NFC payloads for this site.',
    )
    attendance_geofence_latitude = fields.Float(string='Geofence latitude', digits=(10, 7))
    attendance_geofence_longitude = fields.Float(string='Geofence longitude', digits=(10, 7))
    attendance_geofence_radius_meters = fields.Float(
        string='Geofence radius (m)',
        default=0.0,
        help='If greater than zero, GPS check-ins farther than this distance from the center create an alert (never blocks check-in).',
    )
    attendance_geofence_polygon_json = fields.Char(
        string='Geofence polygon (JSON)',
        help='Optional JSON array of points: [{"lat":25.0,"lng":55.0}, ...] or [[lat,lng], ...]. '
             'When set (3+ points), radius geofence is ignored for alerting.',
    )
