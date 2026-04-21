# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class GuardCredential(models.Model):
    """Guard credentials, licenses, and certifications"""
    _name = 'guard.credential'
    _description = 'Guard Credential'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date asc, guard_id'
    _rec_name = 'display_name'

    # Basic Information
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        # Credentials are compliance artefacts (licences, clearances,
        # medicals). Force the operator to archive the guard explicitly
        # rather than vaporise their credential history via a cascade.
        ondelete='restrict',
        tracking=True
    )
    
    credential_type_id = fields.Many2one(
        'guard.credential.type',
        string='Credential Type',
        required=True,
        tracking=True
    )
    
    credential_number = fields.Char(
        string='Credential/License Number',
        required=True,
        tracking=True
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    # Dates
    issue_date = fields.Date(
        string='Issue Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    
    expiry_date = fields.Date(
        string='Expiry Date',
        tracking=True,
        help='Leave empty if no expiry'
    )
    
    verification_date = fields.Date(
        string='Verified On',
        tracking=True
    )
    
    # Issuing Information
    issuing_authority = fields.Char(
        string='Issuing Authority',
        required=True,
        tracking=True
    )
    
    issuing_country = fields.Many2one(
        'res.country',
        string='Issuing Country',
        tracking=True
    )
    
    issuing_state = fields.Char(
        string='Issuing State/Province',
        tracking=True
    )
    
    # Status and Compliance
    state = fields.Selection([
        ('pending', 'Pending Verification'),
        ('valid', 'Valid'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('suspended', 'Suspended'),
        ('revoked', 'Revoked')
    ], string='Status', default='pending', required=True, tracking=True)
    
    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_days_until_expiry',
        store=True
    )
    
    compliance_status = fields.Selection([
        ('compliant', 'Compliant'),
        ('warning', 'Warning - Expiring Soon'),
        ('non_compliant', 'Non-Compliant')
    ], string='Compliance', compute='_compute_compliance_status', store=True)
    
    # Verification
    verified_by_id = fields.Many2one(
        'res.users',
        string='Verified By',
        tracking=True
    )
    
    verification_notes = fields.Text(string='Verification Notes')
    
    # Additional Information
    notes = fields.Text(string='Notes')
    
    # Attachments (handled by mail.thread)
    attachment_count = fields.Integer(
        string='Attachments',
        compute='_compute_attachment_count'
    )
    
    # Related fields for easy access
    guard_name = fields.Char(
        related='guard_id.name',
        string='Guard Name',
        store=True,
        readonly=True
    )
    
    guard_employee_number = fields.Char(
        related='guard_id.badge_number',
        string='Badge Number',
        readonly=True
    )
    
    credential_category = fields.Selection(
        related='credential_type_id.category',
        string='Category',
        store=True,
        readonly=True
    )
    
    is_mandatory = fields.Boolean(
        related='credential_type_id.is_mandatory',
        string='Mandatory',
        readonly=True
    )
    
    active = fields.Boolean(default=True)
    
    @api.depends('guard_id', 'credential_type_id', 'credential_number')
    def _compute_display_name(self):
        """Compute display name for credential"""
        for record in self:
            if record.guard_id and record.credential_type_id:
                record.display_name = f"{record.guard_id.name} - {record.credential_type_id.name}"
            else:
                record.display_name = record.credential_number or 'New Credential'
    
    @api.depends('expiry_date')
    def _compute_days_until_expiry(self):
        """Calculate days until credential expires"""
        today = date.today()
        for record in self:
            if record.expiry_date:
                delta = (record.expiry_date - today).days
                record.days_until_expiry = delta
            else:
                record.days_until_expiry = 9999  # No expiry
    
    @api.depends('expiry_date', 'state', 'days_until_expiry')
    def _compute_compliance_status(self):
        """Determine compliance status based on expiry"""
        for record in self:
            if record.state in ['suspended', 'revoked', 'expired']:
                record.compliance_status = 'non_compliant'
            elif record.state == 'expiring_soon':
                record.compliance_status = 'warning'
            elif record.state == 'valid':
                record.compliance_status = 'compliant'
            else:
                record.compliance_status = 'warning'  # Pending verification
    
    def _compute_attachment_count(self):
        """Count attachments for this credential"""
        for record in self:
            record.attachment_count = self.env['ir.attachment'].search_count([
                ('res_model', '=', self._name),
                ('res_id', '=', record.id)
            ])
    
    @api.constrains('issue_date', 'expiry_date')
    def _check_dates(self):
        """Validate that expiry date is after issue date"""
        for record in self:
            if record.expiry_date and record.issue_date:
                if record.expiry_date <= record.issue_date:
                    raise ValidationError(_('Expiry date must be after issue date!'))
    
    @api.onchange('credential_type_id', 'issue_date')
    def _onchange_credential_type(self):
        """Auto-populate expiry date based on credential type validity period"""
        if self.credential_type_id and self.issue_date:
            if self.credential_type_id.validity_period > 0:
                self.expiry_date = self.issue_date + timedelta(
                    days=self.credential_type_id.validity_period
                )
            if self.credential_type_id.issuing_authority:
                self.issuing_authority = self.credential_type_id.issuing_authority
    
    def action_verify(self):
        """Mark credential as verified"""
        self.ensure_one()
        self.write({
            'state': 'valid',
            'verified_by_id': self.env.user.id,
            'verification_date': fields.Date.today()
        })
        self.message_post(
            body=_('Credential verified by %s') % self.env.user.name,
            subtype_xmlid='mail.mt_note'
        )
    
    def action_suspend(self):
        """Suspend credential"""
        self.ensure_one()
        self.state = 'suspended'
        self.message_post(
            body=_('Credential suspended'),
            subtype_xmlid='mail.mt_note'
        )
    
    def action_revoke(self):
        """Revoke credential"""
        self.ensure_one()
        self.state = 'revoked'
        self.message_post(
            body=_('Credential revoked'),
            subtype_xmlid='mail.mt_note'
        )
    
    def action_reactivate(self):
        """Reactivate suspended credential"""
        self.ensure_one()
        if self.expiry_date and self.expiry_date < date.today():
            self.state = 'expired'
        else:
            self.state = 'valid'
        self.message_post(
            body=_('Credential reactivated'),
            subtype_xmlid='mail.mt_note'
        )
    
    def action_view_attachments(self):
        """Open attachment view for this credential"""
        self.ensure_one()
        return {
            'name': _('Credential Documents'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id
            }
        }
    
    @api.model
    def _cron_check_expiring_credentials(self):
        """Cron job to check for expiring credentials and update states"""
        today = date.today()
        
        # Find credentials expiring soon
        credentials = self.search([
            ('state', '=', 'valid'),
            ('expiry_date', '!=', False)
        ])
        
        Outbox = self.env['guardpro.mobile.outbox'].sudo()
        for credential in credentials:
            days_until = (credential.expiry_date - today).days
            renewal_days = credential.credential_type_id.renewal_notice_days or 30
            guard_user = credential.guard_id.user_id if credential.guard_id else False

            if days_until <= 0:
                # Expired
                credential.state = 'expired'
                credential.message_post(
                    body=_('Credential has expired!'),
                    subtype_xmlid='mail.mt_comment'
                )
                if guard_user:
                    Outbox.push(
                        user=guard_user,
                        kind='credential_expiring',
                        title=_('Credential expired: %s') % (
                            credential.credential_type_id.name or ''
                        ),
                        body=_('Your "%s" credential expired on %s. '
                               'Submit a renewal to remain on-duty.') % (
                            credential.credential_type_id.name or '-',
                            credential.expiry_date,
                        ),
                        priority='urgent',
                        res_model='guard.credential',
                        res_id=credential.id,
                        dedup_key='credential_expired:%s' % credential.id,
                    )
            elif days_until <= renewal_days:
                # Expiring soon
                if credential.state != 'expiring_soon':
                    credential.state = 'expiring_soon'
                    credential.message_post(
                        body=_('Credential expiring in %d days') % days_until,
                        subtype_xmlid='mail.mt_comment'
                    )
                if guard_user:
                    # Re-arm the ping at each of the well-known cliffs
                    # (30/14/7/3/1 days) so guards get a fresh
                    # notification as the deadline tightens.
                    cliffs = [days for days in (30, 14, 7, 3, 1)
                              if days <= renewal_days]
                    for cliff in cliffs:
                        if days_until == cliff:
                            Outbox.push(
                                user=guard_user,
                                kind='credential_expiring',
                                title=_('Credential expiring in %d day(s)') % days_until,
                                body=_('Your "%s" credential expires on %s.') % (
                                    credential.credential_type_id.name or '-',
                                    credential.expiry_date,
                                ),
                                priority='high' if days_until <= 7 else 'normal',
                                res_model='guard.credential',
                                res_id=credential.id,
                                dedup_key='credential_expiring:%s:%s' % (
                                    credential.id, days_until,
                                ),
                            )
                            break

        return True
    
    @api.model
    def _cron_send_compliance_report(self):
        """Generate and send compliance report to managers"""
        # Get all expired or expiring credentials
        non_compliant = self.search([
            ('state', 'in', ['expired', 'expiring_soon', 'suspended', 'revoked'])
        ])
        
        if non_compliant:
            # Get manager users
            manager_group = self.env.ref('guardpro.group_guardpro_manager', raise_if_not_found=False)
            if manager_group:
                managers = manager_group.users
                
                # Email notifications are disabled globally.
        
        return True

