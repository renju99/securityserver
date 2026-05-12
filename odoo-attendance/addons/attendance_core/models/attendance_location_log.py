# -*- coding: utf-8 -*-
from datetime import datetime, timezone

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


class AttendanceLocationLog(models.Model):
    _name = 'attendance.location.log'
    _description = 'Employee GPS location log'
    _order = 'event_time desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    employee_id = fields.Many2one('hr.employee', required=True, ondelete='cascade', index=True)
    event_time = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    latitude = fields.Float(digits=(10, 7), required=True)
    longitude = fields.Float(digits=(10, 7), required=True)
    speed = fields.Float(string='Speed (m/s)', digits=(10, 2))
    raw_json = fields.Json(string='Raw payload')

    @api.depends('employee_id', 'event_time')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s @ %s' % (
                rec.employee_id.display_name if rec.employee_id else '',
                rec.event_time or '',
            )

    def _maps_user_ok(self):
        return self.env.user.has_group('hr.group_hr_user') or self.env.user.has_group(
            'hr_attendance.group_hr_attendance_officer'
        )

    @api.model
    def get_google_maps_api_key(self):
        if not self._maps_user_ok():
            raise AccessError(self.env._('Only HR users or attendance officers can load the map key.'))
        key = (self.env.company.sudo().attendance_google_maps_api_key or '').strip()
        if key:
            return key
        return self.env['ir.config_parameter'].sudo().get_param('attendance_core.google_maps_api_key', '')

    @api.model
    def get_map_points(self, ids):
        if not self._maps_user_ok():
            raise AccessError(self.env._('Only HR users or attendance officers can load map data.'))
        recs = self.browse(ids).filtered(lambda r: r.company_id in self.env.companies)
        return [
            {
                'id': r.id,
                'lat': r.latitude,
                'lng': r.longitude,
                'title': r.employee_id.display_name,
                'time': fields.Datetime.to_string(r.event_time),
            }
            for r in recs
        ]

    @api.model
    def get_live_employee_locations(self):
        """Latest GPS fix per employee (allowed companies), for live map."""
        if not self._maps_user_ok():
            raise AccessError(self.env._('Only HR users or attendance officers can view live locations.'))
        company_ids = tuple(self.env.companies.ids)
        if not company_ids:
            return {'success': True, 'locations': []}
        self.env.cr.execute(
            """
            SELECT DISTINCT ON (l.employee_id)
                l.employee_id,
                l.event_time,
                l.latitude,
                l.longitude
            FROM attendance_location_log l
            WHERE l.company_id IN %s
              AND l.latitude IS NOT NULL
              AND l.longitude IS NOT NULL
            ORDER BY l.employee_id, l.event_time DESC
            """,
            (company_ids,),
        )
        rows = self.env.cr.fetchall()
        emp_ids = [r[0] for r in rows]
        employees = self.env['hr.employee'].browse(emp_ids)
        name_by_id = {e.id: e.display_name for e in employees}
        badge_by_id = {e.id: (e.barcode or '') for e in employees}
        now = fields.Datetime.now()
        locations = []
        for emp_id, event_time, lat, lng in rows:
            delta_min = 0
            if event_time:
                delta_sec = (now - event_time).total_seconds()
                delta_min = int(max(0, delta_sec // 60))
            locations.append(
                {
                    'id': emp_id,
                    'employee_id': emp_id,
                    'name': name_by_id.get(emp_id, ''),
                    'badge_number': badge_by_id.get(emp_id, ''),
                    'latitude': lat,
                    'longitude': lng,
                    'event_time': fields.Datetime.to_string(event_time) if event_time else '',
                    'time_since_update': delta_min,
                }
            )
        return {'success': True, 'locations': locations}

    @api.model
    def get_employee_track(self, employee_id, time_from_ms, time_to_ms):
        """Ordered points for one employee between two instants (UTC ms from browser)."""
        if not self._maps_user_ok():
            raise AccessError(self.env._('Only HR users or attendance officers can load tracks.'))
        if not employee_id or time_from_ms is None or time_to_ms is None:
            raise UserError(self.env._('Employee and time range are required.'))
        emp = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not emp:
            raise UserError(self.env._('Employee not found or not in your allowed companies.'))
        comp_ok = (not emp.company_id) or (emp.company_id.id in self.env.companies.ids)
        if not comp_ok:
            raise UserError(self.env._('Employee not found or not in your allowed companies.'))
        try:
            tf = float(time_from_ms)
            tt = float(time_to_ms)
        except (TypeError, ValueError) as e:
            raise UserError(self.env._('Invalid time range.')) from e
        dt_from = datetime.fromtimestamp(tf / 1000.0, tz=timezone.utc).replace(tzinfo=None)
        dt_to = datetime.fromtimestamp(tt / 1000.0, tz=timezone.utc).replace(tzinfo=None)
        if dt_from > dt_to:
            raise UserError(self.env._('Start time must be before end time.'))
        max_span = 31 * 86400
        if (dt_to - dt_from).total_seconds() > max_span:
            raise UserError(self.env._('Time range cannot exceed 31 days.'))
        recs = self.search(
            [
                ('employee_id', '=', emp.id),
                ('company_id', 'in', self.env.companies.ids),
                ('event_time', '>=', dt_from),
                ('event_time', '<=', dt_to),
            ],
            order='event_time asc, id asc',
            limit=8000,
        )
        points = [
            {
                'id': r.id,
                'lat': r.latitude,
                'lng': r.longitude,
                'time': fields.Datetime.to_string(r.event_time),
            }
            for r in recs
        ]
        max_pts = 2000
        if len(points) > max_pts:
            step = max(1, len(points) // max_pts)
            points = points[::step]
        return {
            'employee_name': emp.display_name,
            'points': points,
        }
