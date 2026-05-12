# -*- coding: utf-8 -*-
import json
import logging
import ssl
import xmlrpc.client
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class AttendanceOdooRemoteInstance(models.Model):
    """Destination Odoo database (receives copies of punches from *this* server via XML-RPC)."""

    _name = 'attendance.odoo.remote.instance'
    _description = 'Target Odoo (Odoo-to-Odoo replication)'
    _order = 'name'

    name = fields.Char(
        required=True,
        string='Label',
        help='Friendly name for this target Odoo (e.g. “Production HR”).',
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Source company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help='Company on *this* Odoo whose attendances may be replicated when routing rules match.',
    )
    code = fields.Char(
        string='Routing code',
        required=True,
        index=True,
        help='Short unique key per company. Employee routing rules point to this target.',
    )
    base_url = fields.Char(
        string='Target Odoo URL',
        required=True,
        help='Base URL of the other Odoo server, e.g. https://hr.other-company.com (no trailing slash).',
    )
    database = fields.Char(
        string='Target database',
        required=True,
        help='PostgreSQL database name on the target Odoo (same as the web login database selector).',
    )
    username = fields.Char(
        string='Target login',
        required=True,
        help='Odoo user on the *target* instance. Must be allowed to create/write hr.attendance (e.g. HR officer).',
    )
    password = fields.Char(
        string='Target password',
        required=True,
        groups='base.group_system',
        help='Password or API token accepted by the target Odoo user (stored encrypted for admins only).',
    )
    verify_ssl = fields.Boolean(
        string='Verify HTTPS certificate',
        default=True,
        help='Turn off only for lab / internal targets with self-signed TLS (less secure).',
    )
    employee_lookup_field = fields.Selection(
        [
            ('barcode', 'Employee barcode'),
            ('pin', 'PIN'),
        ],
        string='Match employee on target by',
        default='barcode',
        required=True,
        help='How to find the same person on the target Odoo: barcode or PIN must match between both databases.',
    )
    note = fields.Text(string='Internal notes')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'Routing code must be unique per source company.'),
    ]

    def _xmlrpc_ssl_context(self):
        self.ensure_one()
        if self.verify_ssl:
            return ssl.create_default_context()
        return ssl._create_unverified_context()

    def _xmlrpc_common(self):
        self.ensure_one()
        url = f'{self.base_url.rstrip("/")}/xmlrpc/2/common'
        return xmlrpc.client.ServerProxy(url, allow_none=True, context=self._xmlrpc_ssl_context())

    def _xmlrpc_object(self):
        self.ensure_one()
        url = f'{self.base_url.rstrip("/")}/xmlrpc/2/object'
        return xmlrpc.client.ServerProxy(url, allow_none=True, context=self._xmlrpc_ssl_context())

    def action_attendance_test_connection(self):
        for rec in self:
            try:
                common = rec._xmlrpc_common()
                uid = common.authenticate(rec.database, rec.username, rec.password, {})
                if not uid:
                    raise UserError(_('Authentication failed on the target Odoo. Check URL, database, login and password.'))
            except UserError:
                raise
            except Exception as e:  # noqa: BLE001
                raise UserError(_('Could not reach the target Odoo: %s') % str(e)) from e
        raise UserError(_('Target Odoo connection successful.'))


class AttendanceOdooSyncOutbox(models.Model):
    """Queued replication of hr.attendance from this DB to a target Odoo over XML-RPC."""

    _name = 'attendance.odoo.sync.outbox'
    _description = 'Odoo-to-Odoo attendance replication queue'
    _order = 'create_date desc'

    company_id = fields.Many2one(
        'res.company',
        string='Source company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    remote_id = fields.Many2one(
        'attendance.odoo.remote.instance',
        string='Target Odoo',
        required=True,
        ondelete='cascade',
    )
    attendance_id = fields.Many2one('hr.attendance', required=True, ondelete='cascade', index=True)
    event_type = fields.Selection([('check_in', 'Check in'), ('check_out', 'Check out')], required=True)
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('done', 'Done'),
            ('error', 'Error'),
        ],
        default='pending',
        index=True,
    )
    attempts = fields.Integer(default=0)
    last_error = fields.Text(readonly=True)
    remote_attendance_id = fields.Integer(string='Remote attendance id', readonly=True)
    payload_json = fields.Text(readonly=True, help='Snapshot of the replication payload sent to the target Odoo.')

    def _process_one(self):
        self.ensure_one()
        rec = self.sudo()
        remote = rec.remote_id
        att = rec.attendance_id
        emp = att.employee_id.sudo()
        if not remote.active:
            rec.write({'state': 'error', 'last_error': 'Target Odoo configuration is archived/inactive.'})
            return
        common = remote._xmlrpc_common()
        models_proxy = remote._xmlrpc_object()
        uid = common.authenticate(remote.database, remote.username, remote.password, {})
        if not uid:
            rec.write({'state': 'error', 'last_error': 'Target Odoo authentication failed.', 'attempts': rec.attempts + 1})
            return
        field = remote.employee_lookup_field
        val = emp.barcode if field == 'barcode' else (emp.pin or '')
        if not val:
            rec.write({
                'state': 'error',
                'last_error': 'Source employee has no barcode/PIN; cannot match a record on the target Odoo.',
                'attempts': rec.attempts + 1,
            })
            return
        domain = [(field, '=', val)]
        remote_emp_ids = models_proxy.execute_kw(
            remote.database,
            uid,
            remote.password,
            'hr.employee',
            'search',
            [domain],
            {'limit': 1},
        )
        if not remote_emp_ids:
            rec.write({
                'state': 'error',
                'last_error': _('No matching employee on the target Odoo (check barcode/PIN).'),
                'attempts': rec.attempts + 1,
            })
            return
        remote_emp_id = remote_emp_ids[0]
        payload = json.dumps({
            'event_type': rec.event_type,
            'remote_employee_id': remote_emp_id,
            'local_attendance_id': att.id,
        })
        rec.write({'payload_json': payload, 'attempts': rec.attempts + 1})
        try:
            if rec.event_type == 'check_in':
                create_vals = {'employee_id': remote_emp_id, 'check_in': att.check_in}
                if att.check_out:
                    create_vals['check_out'] = att.check_out
                new_id = models_proxy.execute_kw(
                    remote.database,
                    uid,
                    remote.password,
                    'hr.attendance',
                    'create',
                    [create_vals],
                )
                rec.write({'state': 'done', 'remote_attendance_id': new_id, 'last_error': ''})
            else:
                open_ids = models_proxy.execute_kw(
                    remote.database,
                    uid,
                    remote.password,
                    'hr.attendance',
                    'search',
                    [[('employee_id', '=', remote_emp_id), ('check_out', '=', False)]],
                    {'order': 'check_in desc', 'limit': 1},
                )
                if open_ids:
                    models_proxy.execute_kw(
                        remote.database,
                        uid,
                        remote.password,
                        'hr.attendance',
                        'write',
                        [open_ids, {'check_out': att.check_out}],
                    )
                    rec.write({'state': 'done', 'remote_attendance_id': open_ids[0], 'last_error': ''})
                else:
                    new_id = models_proxy.execute_kw(
                        remote.database,
                        uid,
                        remote.password,
                        'hr.attendance',
                        'create',
                        [{'employee_id': remote_emp_id, 'check_in': att.check_in, 'check_out': att.check_out}],
                    )
                    rec.write({'state': 'done', 'remote_attendance_id': new_id, 'last_error': ''})
        except Exception as e:  # noqa: BLE001
            _logger.exception('Odoo-to-Odoo replication failed')
            rec.write({'state': 'error', 'last_error': str(e)})

    @api.model
    def cron_process_pending(self):
        horizon = fields.Datetime.now() - timedelta(days=7)
        todo = self.search([
            ('state', '=', 'pending'),
            ('attempts', '<', 8),
            ('create_date', '>=', horizon),
        ], limit=50, order='create_date')
        for line in todo:
            line._process_one()


class AttendanceOdooEmployeeRouting(models.Model):
    """Map a source employee (this Odoo) to one target Odoo for punch replication."""

    _name = 'attendance.odoo.employee.routing'
    _description = 'Odoo-to-Odoo employee routing'
    _order = 'employee_id'

    company_id = fields.Many2one(
        'res.company',
        string='Source company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee (this Odoo)',
        required=True,
        ondelete='cascade',
        index=True,
        help='Employee whose punches originate on this database.',
    )
    remote_id = fields.Many2one(
        'attendance.odoo.remote.instance',
        string='Replicate to',
        required=True,
        ondelete='cascade',
        help='Target Odoo instance that will receive hr.attendance copies.',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('employee_company_uniq', 'unique(employee_id, company_id)', 'One replication target per employee per source company.'),
    ]
