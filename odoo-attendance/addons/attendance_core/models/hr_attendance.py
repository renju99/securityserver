# -*- coding: utf-8 -*-
import json
import logging
import math
from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def _point_in_polygon(lat: float, lng: float, rings: list[tuple[float, float]]) -> bool:
    """Ray casting; rings as list of (lat, lng)."""
    inside = False
    n = len(rings)
    if n < 3:
        return False
    y, x = lat, lng
    j = n - 1
    for i in range(n):
        yi, xi = rings[i][0], rings[i][1]
        yj, xj = rings[j][0], rings[j][1]
        intersect = (yi > y) != (yj > y) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside


def _parse_polygon_json(raw: str | bool | None) -> list[tuple[float, float]] | None:
    if not raw or not isinstance(raw, str):
        return None
    try:
        data = json.loads(raw.strip())
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, list) or len(data) < 3:
        return None
    out: list[tuple[float, float]] = []
    for item in data:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append((float(item[0]), float(item[1])))
        elif isinstance(item, dict):
            lat = item.get('lat', item.get('latitude'))
            lng = item.get('lng', item.get('lon'), item.get('longitude'))
            if lat is not None and lng is not None:
                out.append((float(lat), float(lng)))
    return out if len(out) >= 3 else None


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    check_work_location_id = fields.Many2one(
        'hr.work.location',
        string='Punch work location',
        index=True,
        help='Optional. When set, documents which work location applies to this punch '
             '(for example kiosk or biometric device site). Defaults from the employee if empty.',
    )
    review_status = fields.Selection(
        selection=[
            ('none', 'No review'),
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Manual review',
        default='none',
        tracking=True,
    )
    review_reason = fields.Text(string='Review notes', tracking=True)
    attendance_job_code_id = fields.Many2one(
        'attendance.job.code',
        string='Job / activity code',
        index=True,
    )
    break_minutes = fields.Integer(string='Break minutes', default=0)
    work_context_note = fields.Text(string='Work context / notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('check_work_location_id'):
                emp_id = vals.get('employee_id')
                if emp_id:
                    emp = self.env['hr.employee'].browse(emp_id)
                    wl = emp.work_location_id
                    if wl:
                        vals['check_work_location_id'] = wl.id
            self._attendance_core_apply_policy_vals(vals)
        records = super().create(vals_list)
        for attendance, vals in zip(records, vals_list):
            attendance._attendance_core_geofence_maybe_alert(vals)
        records._bw_bus_notify_created()
        records._bw_odoo_sync_enqueue('check_in')
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('in_latitude', 'in_longitude', 'check_work_location_id')):
            for att in self:
                att._attendance_core_geofence_maybe_alert(vals, on_write=True)
        if 'check_out' in vals and vals.get('check_out'):
            self._bw_bus_notify_checkout()
            self._bw_odoo_sync_enqueue('check_out')
        return res

    def _bw_odoo_sync_enqueue(self, event_type):
        """Queue replication of punches to another Odoo (XML-RPC) when enabled on the company and employee is routed."""
        Outbox = self.env['attendance.odoo.sync.outbox'].sudo()
        for att in self:
            company = att.employee_id.company_id
            if not company.attendance_odoo_sync_enabled:
                continue
            route = self.env['attendance.odoo.employee.routing'].sudo().search([
                ('employee_id', '=', att.employee_id.id),
                ('company_id', '=', company.id),
                ('active', '=', True),
            ], limit=1)
            if not route:
                continue
            if Outbox.search_count([
                ('attendance_id', '=', att.id),
                ('remote_id', '=', route.remote_id.id),
                ('event_type', '=', event_type),
                ('state', '=', 'pending'),
            ]):
                continue
            Outbox.create({
                'company_id': company.id,
                'remote_id': route.remote_id.id,
                'attendance_id': att.id,
                'event_type': event_type,
            })

    @api.model
    def _attendance_core_apply_policy_vals(self, vals):
        emp_id = vals.get('employee_id')
        if not emp_id:
            return
        emp = self.env['hr.employee'].browse(emp_id)
        wl = self.env['hr.work.location'].browse(vals['check_work_location_id']) if vals.get('check_work_location_id') else emp.work_location_id
        policy = self.env['attendance.policy.rule'].get_policy_for_employee(emp, wl)
        if not policy:
            return
        in_mode = vals.get('in_mode') or 'manual'
        need = False
        if in_mode == 'manual' and policy.require_approval_manual:
            need = True
        elif in_mode == 'systray' and policy.require_approval_offline:
            need = True
        elif in_mode == 'kiosk' and policy.require_approval_kiosk:
            need = True
        if need:
            vals['review_status'] = 'pending'

    def _geofence_outside(self, lat: float, lon: float, loc):
        poly = _parse_polygon_json(loc.attendance_geofence_polygon_json)
        if poly:
            inside = _point_in_polygon(lat, lon, poly)
            if inside:
                return False, None, ''
            return True, None, _('Outside configured polygon for %s', loc.display_name)
        if loc.attendance_geofence_radius_meters and loc.attendance_geofence_radius_meters > 0:
            ref_lat = loc.attendance_geofence_latitude
            ref_lon = loc.attendance_geofence_longitude
            if not ref_lat or not ref_lon:
                return False, None, ''
            distance = _haversine_m(float(lat), float(lon), ref_lat, ref_lon)
            if distance <= loc.attendance_geofence_radius_meters:
                return False, None, ''
            return True, distance, _(
                'GPS is about %(dist).0f m from the center of %(loc)s (allowed %(rad).0f m).',
                dist=distance,
                loc=loc.display_name,
                rad=loc.attendance_geofence_radius_meters,
            )
        return False, None, ''

    def _attendance_core_geofence_maybe_alert(self, vals, on_write=False):
        self.ensure_one()
        company = self.employee_id.company_id
        if not company or not company.attendance_geofence_alerts:
            return
        loc = self.check_work_location_id or self.employee_id.work_location_id
        if not loc:
            return
        lat = self.in_latitude
        lon = self.in_longitude
        if lat is False or lat is None or lon is False or lon is None:
            return
        latf, lonf = float(lat), float(lon)
        outside, distance, message = self._geofence_outside(latf, lonf, loc)
        if not outside:
            return
        Alert = self.env['attendance.geofence.alert'].sudo()
        dup_domain = [
            ('attendance_id', '=', self.id),
            ('state', '=', 'open'),
        ]
        if Alert.search_count(dup_domain):
            return
        Alert.create({
            'name': _('%s — outside geofence', self.employee_id.display_name or ''),
            'employee_id': self.employee_id.id,
            'work_location_id': loc.id,
            'attendance_id': self.id,
            'latitude': latf,
            'longitude': lonf,
            'distance_meters': distance or 0.0,
            'message': message,
            'company_id': company.id,
        })

    def action_attendance_core_approve(self):
        self.filtered(lambda a: a.review_status == 'pending').write({'review_status': 'approved'})

    def action_attendance_core_reject(self):
        self.filtered(lambda a: a.review_status == 'pending').write({'review_status': 'rejected'})

    def _bw_bus_notify_managers(self, message):
        if self.env.context.get('berkeley_workforce_disable_bus') or not message:
            return
        Bus = self.env['bus.bus'].sudo()
        group = self.env.ref('hr_attendance.group_hr_attendance_manager', raise_if_not_found=False)
        if not group:
            return
        users = self.env['res.users'].search([('groups_id', 'in', [group.id]), ('active', '=', True), ('share', '=', False)])
        partners = users.mapped('partner_id').filtered(lambda p: p)
        if not partners:
            return
        payload = {'title': _('Berkeley Workforce'), 'message': message, 'sticky': False}
        for partner in partners:
            try:
                Bus._sendone(partner, 'simple_notification', payload)
            except Exception:
                _logger.warning('bus notify failed for partner %s', partner.id, exc_info=True)

    def _bw_bus_broadcast_live(self, event_type):
        """Push structured payload to websocket subscribers (HR live dashboard)."""
        if self.env.context.get('berkeley_workforce_disable_bus') or not self:
            return
        Bus = self.env['bus.bus'].sudo()
        lines = []
        for att in self[:50]:
            lines.append({
                'id': att.id,
                'employee': att.employee_id.name,
                'check_in': att.check_in.isoformat() if att.check_in else None,
                'check_out': att.check_out.isoformat() if att.check_out else None,
            })
        payload = {
            'event': event_type,
            'attendance_ids': self.ids,
            'lines': lines,
        }
        try:
            Bus._sendone('bw_attendance_hr_live', 'berkeley_workforce/live', payload)
        except Exception:
            _logger.warning('live HR bus broadcast failed', exc_info=True)

    def _bw_bus_notify_created(self):
        if not self or self.env.context.get('berkeley_workforce_disable_bus'):
            return
        names = self.mapped('employee_id.name')
        msg = _('Check-in: %s') % ', '.join(names[:10])
        if len(names) > 10:
            msg += '…'
        self[:1]._bw_bus_notify_managers(msg)
        self._bw_bus_broadcast_live('check_in')

    def _bw_bus_notify_checkout(self):
        if not self or self.env.context.get('berkeley_workforce_disable_bus'):
            return
        names = self.mapped('employee_id.name')
        msg = _('Check-out: %s') % ', '.join(names[:10])
        if len(names) > 10:
            msg += '…'
        self[:1]._bw_bus_notify_managers(msg)
        self._bw_bus_broadcast_live('check_out')
