# -*- coding: utf-8 -*-
"""Key Issue Wizard for issuing keys to guards, contractors, residents, etc."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class KeyIssueWizard(models.TransientModel):
    """Wizard for issuing keys with proper documentation."""
    
    _name = 'key.issue.wizard'
    _description = 'Key Issue Wizard'
    
    key_id = fields.Many2one(
        'key.register',
        string='Key',
        required=True,
        readonly=True
    )
    
    # Key Information (Read-only for reference)
    key_name = fields.Char(
        related='key_id.name',
        string='Key Name',
        readonly=True
    )
    key_type = fields.Selection(
        related='key_id.key_type',
        string='Key Type',
        readonly=True
    )
    location = fields.Char(
        related='key_id.location',
        string='Location',
        readonly=True
    )
    
    # Issuance Details
    issued_to_type = fields.Selection([
        ('guard', 'Guard'),
        ('contractor', 'Contractor'),
        ('resident', 'Resident'),
        ('visitor', 'Visitor'),
        ('employee', 'Employee'),
        ('maintenance', 'Maintenance Staff'),
        ('other', 'Other')
    ], string='Issued To Type', required=True, default='guard')
    
    issued_to_name = fields.Char(
        string='Issued To',
        required=True,
        help='Name of person receiving the key'
    )
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        help='Select guard if issuing to a guard'
    )
    
    issued_to_phone = fields.Char(
        string='Phone Number',
        help='Contact number of key holder'
    )
    
    issued_to_id_number = fields.Char(
        string='ID Number',
        help='Identification number (Emirates ID, Passport, etc.)'
    )
    
    issue_date = fields.Datetime(
        string='Issue Date',
        required=True,
        default=fields.Datetime.now
    )
    
    expected_return = fields.Datetime(
        string='Expected Return',
        help='Expected return date and time'
    )
    
    purpose = fields.Text(
        string='Purpose',
        required=True,
        help='Reason for key issuance'
    )
    
    # Signature
    signature = fields.Binary(
        string='Signature',
        required=True,
        help='Signature of person receiving key'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this key issuance'
    )
    
    @api.onchange('issued_to_type')
    def _onchange_issued_to_type(self):
        """Clear guard selection if not issuing to guard."""
        if self.issued_to_type != 'guard':
            self.guard_id = False
    
    @api.onchange('guard_id')
    def _onchange_guard_id(self):
        """Auto-fill details from guard profile."""
        if self.guard_id:
            self.issued_to_name = self.guard_id.name
            self.issued_to_phone = self.guard_id.phone
            self.issued_to_id_number = self.guard_id.badge_number
    
    @api.constrains('expected_return', 'issue_date')
    def _check_dates(self):
        """Validate that expected return is after issue date."""
        for record in self:
            if record.expected_return and record.expected_return < record.issue_date:
                raise ValidationError(
                    _('Expected return date must be after issue date.')
                )
    
    def action_issue_key(self):
        """Process key issuance."""
        self.ensure_one()
        
        # Validate
        if not self.signature:
            raise UserError(_('Signature is required to issue the key.'))
        
        if self.key_id.status != 'available':
            raise UserError(
                _('This key is not available. Current status: %s') % 
                dict(self.key_id._fields['status'].selection).get(self.key_id.status)
            )
        
        # Create transaction
        transaction_vals = {
            'key_id': self.key_id.id,
            'issued_to_type': self.issued_to_type,
            'issued_to_name': self.issued_to_name,
            'guard_id': self.guard_id.id if self.guard_id else False,
            'issued_to_phone': self.issued_to_phone,
            'issued_to_id_number': self.issued_to_id_number,
            'issue_date': self.issue_date,
            'expected_return': self.expected_return,
            'purpose': self.purpose,
            'signature': self.signature,
            'notes': self.notes,
            'state': 'active'
        }
        
        transaction = self.env['key.transaction'].create(transaction_vals)
        
        # Post message to key chatter
        message = Markup(
            '<strong>Key Issued</strong><br/>'
            '<b>Issued To:</b> %s (%s)<br/>'
            '<b>Purpose:</b> %s<br/>'
            '<b>Expected Return:</b> %s<br/>'
            '<b>Issue Date:</b> %s'
        ) % (
            self.issued_to_name,
            dict(self._fields['issued_to_type'].selection).get(self.issued_to_type),
            self.purpose,
            self.expected_return.strftime('%Y-%m-%d %H:%M') if self.expected_return else 'Not specified',
            self.issue_date.strftime('%Y-%m-%d %H:%M')
        )
        
        self.key_id.message_post(
            body=message,
            subject=_('Key Issued to %s') % self.issued_to_name,
            message_type='notification'
        )
        
        # Attach signature
        if self.signature:
            self.env['ir.attachment'].create({
                'name': f'Signature_{self.issued_to_name}_{self.issue_date.strftime("%Y%m%d_%H%M")}.jpg',
                'datas': self.signature,
                'res_model': 'key.transaction',
                'res_id': transaction.id,
                'mimetype': 'image/jpeg',
                'description': f'Signature for key issuance to {self.issued_to_name}'
            })
        
        _logger.info(
            'Key %s issued to %s (%s) - Transaction ID: %s',
            self.key_id.name,
            self.issued_to_name,
            self.issued_to_type,
            transaction.id
        )
        
        # Show success notification and close
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Key %s successfully issued to %s') % (
                    self.key_id.name,
                    self.issued_to_name
                ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


