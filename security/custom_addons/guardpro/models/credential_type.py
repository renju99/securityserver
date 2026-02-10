# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CredentialType(models.Model):
    """Master data for credential types (licenses, certifications, etc.)"""
    _name = 'guard.credential.type'
    _description = 'Credential Type'
    _order = 'category, name'

    name = fields.Char(
        string='Credential Name',
        required=True,
        help='Name of the credential type (e.g., Security License, First Aid)'
    )
    code = fields.Char(
        string='Code',
        required=True,
        help='Unique code for this credential type'
    )
    category = fields.Selection([
        ('license', 'Security License'),
        ('certification', 'Certification'),
        ('permit', 'Work Permit/Visa'),
        ('training', 'Training'),
        ('other', 'Other')
    ], string='Category', required=True, default='license')
    
    description = fields.Text(string='Description')
    
    validity_period = fields.Integer(
        string='Validity Period (Days)',
        help='Default validity period in days. 0 = No expiry',
        default=365
    )
    
    renewal_notice_days = fields.Integer(
        string='Renewal Notice (Days Before Expiry)',
        default=30,
        help='Send alert this many days before expiry'
    )
    
    is_mandatory = fields.Boolean(
        string='Mandatory',
        default=False,
        help='Is this credential mandatory for all guards?'
    )
    
    requires_verification = fields.Boolean(
        string='Requires Verification',
        default=True,
        help='Does this credential need supervisor verification?'
    )
    
    issuing_authority = fields.Char(
        string='Typical Issuing Authority',
        help='Common issuing authority (e.g., State Police, Red Cross)'
    )
    
    active = fields.Boolean(default=True)
    
    # Statistics
    credential_count = fields.Integer(
        string='Active Credentials',
        compute='_compute_credential_count',
        store=False
    )
    
    @api.depends()
    def _compute_credential_count(self):
        """Count active credentials of this type"""
        for record in self:
            record.credential_count = self.env['guard.credential'].search_count([
                ('credential_type_id', '=', record.id),
                ('state', 'in', ['valid', 'expiring_soon'])
            ])
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Credential code must be unique!')
    ]

