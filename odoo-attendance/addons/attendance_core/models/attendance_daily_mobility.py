# -*- coding: utf-8 -*-
"""Route distance and idle-gap analytics from attendance.location.log."""
import math
from datetime import date, datetime, timedelta

from odoo import api, fields, models


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


class AttendanceDailyMobility(models.Model):
    _name = 'attendance.daily.mobility'
    _description = 'Daily route distance & idle gaps (from GPS logs)'
    _order = 'day desc, employee_id'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    employee_id = fields.Many2one('hr.employee', required=True, ondelete='cascade', index=True)
    day = fields.Date(required=True, index=True)
    route_distance_km = fields.Float(string='Route distance (km)', digits=(16, 3))
    idle_gap_minutes = fields.Float(
        string='Idle gap (min)',
        digits=(16, 2),
        help='Sum of gaps between GPS points when movement was under 50 m/h and gap exceeded the threshold.',
    )
    point_count = fields.Integer(string='GPS points')

    _sql_constraints = [
        ('uniq_employee_day_company', 'unique(employee_id, day, company_id)', 'One mobility row per employee per day.'),
    ]

    @api.model
    def cron_rebuild_mobility(self, days_back=1):
        Log = self.env['attendance.location.log'].sudo()
        idle_gap_min = float(
            self.env['ir.config_parameter'].sudo().get_param('attendance_core.idle_gap_minutes', '20')
        )
        for delta in range(days_back, 0, -1):
            day = date.today() - timedelta(days=delta)
            start_dt = datetime.combine(day, datetime.min.time())
            end_dt = start_dt + timedelta(days=1)
            companies = self.env['res.company'].search([])
            for company in companies:
                employees = self.env['hr.employee'].sudo().search([('company_id', 'child_of', company.id)])
                for emp in employees:
                    logs = Log.search(
                        [
                            ('employee_id', '=', emp.id),
                            ('company_id', '=', company.id),
                            ('event_time', '>=', start_dt),
                            ('event_time', '<', end_dt),
                        ],
                        order='event_time asc, id asc',
                    )
                    if not logs:
                        self.search(
                            [('employee_id', '=', emp.id), ('day', '=', day), ('company_id', '=', company.id)]
                        ).unlink()
                        continue
                    dist_km = 0.0
                    idle_min = 0.0
                    prev = None
                    for lg in logs:
                        if prev:
                            dt_min = (lg.event_time - prev.event_time).total_seconds() / 60.0
                            dk = _haversine_km(prev.latitude, prev.longitude, lg.latitude, lg.longitude)
                            dist_km += dk
                            implied_kmh = (dk / (dt_min / 60.0)) if dt_min > 1e-3 else 999.0
                            if dt_min >= idle_gap_min and implied_kmh < 0.05:
                                idle_min += max(0.0, dt_min - 5.0)
                        prev = lg
                    vals = {
                        'company_id': company.id,
                        'employee_id': emp.id,
                        'day': day,
                        'route_distance_km': dist_km,
                        'idle_gap_minutes': idle_min,
                        'point_count': len(logs),
                    }
                    row = self.search(
                        [('employee_id', '=', emp.id), ('day', '=', day), ('company_id', '=', company.id)],
                        limit=1,
                    )
                    if row:
                        row.write(vals)
                    else:
                        self.create(vals)
