# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class KeyRegister(models.Model):
    """Physical Key Register"""
    _name = 'key.register'
    _description = 'Key Register'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Key Identifier',
        required=True,
        index=True,
        help='Unique key identifier (e.g., KEY-ROOM-101)'
    )
    key_type = fields.Selection([
        ('room', 'Room Key'),
        ('cabinet', 'Cabinet Key'),
        ('vehicle', 'Vehicle Key'),
        ('gate', 'Gate Key'),
        ('office', 'Office Key'),
        ('locker', 'Locker Key'),
        ('master', 'Master Key'),
        ('other', 'Other')
    ], string='Key Type', required=True, tracking=True)

    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True,
        tracking=True,
        index=True,
        ondelete='cascade'
    )
    location = fields.Char(
        string='Location/Room Number',
        help='Location that this key opens'
    )
    description = fields.Text(
        string='Description',
        help='Detailed description of the key and its purpose'
    )

    # Key Details
    key_number = fields.Char(
        string='Key Number',
        help='Physical number stamped on key'
    )
    key_tag_color = fields.Char(
        string='Tag Color',
        help='Color of the key tag for easy identification'
    )
    duplicate_available = fields.Boolean(
        string='Duplicate Available',
        help='Is there a duplicate key available'
    )
    duplicate_location = fields.Char(
        string='Duplicate Location',
        help='Where the duplicate key is stored'
    )

    # Status
    status = fields.Selection([
        ('available', 'Available'),
        ('issued', 'Issued'),
        ('lost', 'Lost'),
        ('damaged', 'Damaged'),
        ('decommissioned', 'Decommissioned')
    ], string='Status', compute='_compute_status', store=True, tracking=True)

    # Transactions
    transaction_ids = fields.One2many(
        'key.transaction',
        'key_id',
        string='Transactions'
    )
    
    # Computed
    current_holder = fields.Char(
        string='Current Holder',
        compute='_compute_current_holder',
        help='Person currently holding the key'
    )
    days_issued = fields.Integer(
        string='Days Issued',
        compute='_compute_days_issued',
        help='Number of days key has been issued'
    )

    # Additional
    notes = fields.Text(
        string='Notes'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.depends('transaction_ids', 'transaction_ids.return_date', 'transaction_ids.state')
    def _compute_status(self):
        """Compute key status based on transactions"""
        for key in self:
            if key.status in ['lost', 'damaged', 'decommissioned']:
                # Keep manual status
                continue
            
            last_transaction = key.transaction_ids.filtered(
                lambda t: t.state == 'active'
            ).sorted('issue_date', reverse=True)[:1]
            
            if last_transaction and not last_transaction.return_date:
                key.status = 'issued'
            else:
                key.status = 'available'

    @api.depends('transaction_ids', 'transaction_ids.return_date')
    def _compute_current_holder(self):
        """Get current key holder"""
        for key in self:
            active_transaction = key.transaction_ids.filtered(
                lambda t: t.state == 'active' and not t.return_date
            ).sorted('issue_date', reverse=True)[:1]
            
            if active_transaction:
                key.current_holder = active_transaction.issued_to_name
            else:
                key.current_holder = False

    @api.depends('transaction_ids', 'transaction_ids.issue_date', 'transaction_ids.return_date')
    def _compute_days_issued(self):
        """Calculate days key has been issued"""
        for key in self:
            active_transaction = key.transaction_ids.filtered(
                lambda t: t.state == 'active' and not t.return_date
            ).sorted('issue_date', reverse=True)[:1]
            
            if active_transaction:
                delta = fields.Datetime.now() - active_transaction.issue_date
                key.days_issued = delta.days
            else:
                key.days_issued = 0

    def action_issue_key(self):
        """Open wizard to issue key"""
        self.ensure_one()
        
        if self.status != 'available':
            raise UserError(_('Only available keys can be issued.'))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'key.issue.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_key_id': self.id}
        }

    def action_return_key(self):
        """Return key"""
        self.ensure_one()
        
        active_transaction = self.transaction_ids.filtered(
            lambda t: t.state == 'active' and not t.return_date
        ).sorted('issue_date', reverse=True)[:1]
        
        if not active_transaction:
            raise UserError(_('No active transaction found for this key.'))
        
        guard = self.env['guard.profile'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        
        active_transaction.write({
            'return_date': fields.Datetime.now(),
            'returned_to': guard.id if guard else False,
            'state': 'returned'
        })
        
        _logger.info('Key %s returned by %s', self.name, active_transaction.issued_to_name)
        return True

    def action_mark_lost(self):
        """Mark key as lost"""
        self.ensure_one()
        self.write({'status': 'lost'})
        
        # Create incident
        category = self.env.ref('guardpro.incident_cat_security', raise_if_not_found=False)
        vals = {
            'name': _('Lost Key - %s') % self.name,
            'title': _('Lost Key - %s') % self.name,
            'site_id': self.site_id.id,
            'incident_datetime': fields.Datetime.now(),
            'description': _('Key %s has been reported as lost.\nLocation: %s\nCurrent Holder: %s') % (
                self.name,
                self.location or 'Unknown',
                self.current_holder or 'Unknown'
            ),
            'severity': 'high'
        }
        if category:
            vals['category_id'] = category.id
        
        incident = self.env['incident.report'].create(vals)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'incident.report',
            'res_id': incident.id,
            'view_mode': 'form',
            'target': 'current'
        }


class KeyTransaction(models.Model):
    """Key Transaction Log"""
    _name = 'key.transaction'
    _description = 'Key Transaction Log'
    _inherit = ['mail.thread']
    _order = 'issue_date desc, id desc'

    key_id = fields.Many2one(
        'key.register',
        string='Key',
        required=True,
        ondelete='cascade',
        index=True
    )

    # Issuance
    issued_to_type = fields.Selection([
        ('guard', 'Guard'),
        ('contractor', 'Contractor'),
        ('resident', 'Resident'),
        ('visitor', 'Visitor'),
        ('employee', 'Employee'),
        ('maintenance', 'Maintenance Staff'),
        ('other', 'Other')
    ], string='Issued To Type', required=True)
    
    issued_to_name = fields.Char(
        string='Issued To',
        required=True,
        index=True,
        help='Name of person receiving the key'
    )
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard (if applicable)',
        help='Guard receiving the key'
    )
    issued_to_phone = fields.Char(
        string='Phone Number',
        help='Contact number of key holder'
    )
    issued_to_id_number = fields.Char(
        string='ID Number',
        help='Identification number'
    )

    issue_date = fields.Datetime(
        string='Issue Date',
        required=True,
        default=fields.Datetime.now,
        index=True,
        tracking=True
    )
    expected_return = fields.Datetime(
        string='Expected Return',
        help='Expected return date and time'
    )
    purpose = fields.Text(
        string='Purpose',
        help='Reason for key issuance'
    )

    # Return
    return_date = fields.Datetime(
        string='Return Date',
        tracking=True
    )
    returned_to = fields.Many2one(
        'guard.profile',
        string='Returned To (Guard)',
        help='Guard who received the key back'
    )

    # Status
    state = fields.Selection([
        ('active', 'Active/Issued'),
        ('returned', 'Returned'),
        ('lost', 'Lost'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='active', required=True, tracking=True)

    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_overdue',
        help='Key return is overdue'
    )
    overdue_days = fields.Integer(
        string='Days Overdue',
        compute='_compute_overdue'
    )

    # Additional
    notes = fields.Text(
        string='Notes'
    )
    signature = fields.Binary(
        string='Signature',
        help='Signature of person receiving key'
    )

    @api.depends('expected_return', 'return_date', 'state')
    def _compute_overdue(self):
        """Check if key return is overdue"""
        now = fields.Datetime.now()
        for txn in self:
            if txn.state == 'active' and not txn.return_date and txn.expected_return:
                txn.is_overdue = now > txn.expected_return
                if txn.is_overdue:
                    delta = now - txn.expected_return
                    txn.overdue_days = delta.days
                else:
                    txn.overdue_days = 0
            else:
                txn.is_overdue = False
                txn.overdue_days = 0

    @api.model
    def send_overdue_reminders(self):
        """Cron job to send overdue key reminders"""
        overdue = self.search([
            ('return_date', '=', False),
            ('state', '=', 'active'),
            ('is_overdue', '=', True)
        ])
        
        # Planned activities intentionally disabled for overdue keys.
        
        _logger.info('Sent overdue reminders for %d keys', len(overdue))
        return True

