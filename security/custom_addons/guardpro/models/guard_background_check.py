# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GuardBackgroundCheck(models.Model):
    """Background check tracking and renewals"""
    _name = 'guard.background.check'
    _description = 'Guard Background Check'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'check_date desc, guard_id'
    _rec_name = 'display_name'

    # Basic Information
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    reference_number = fields.Char(
        string='Reference Number',
        required=True,
        copy=False,
        default=lambda self: _('New'),
        tracking=True
    )
    
    # Check Details
    check_type = fields.Selection([
        ('criminal', 'Criminal Record Check'),
        ('employment', 'Employment History'),
        ('education', 'Education Verification'),
        ('credit', 'Credit Check'),
        ('reference', 'Reference Check'),
        ('comprehensive', 'Comprehensive Background Check'),
        ('other', 'Other')
    ], string='Check Type', required=True, default='criminal', tracking=True)
    
    check_date = fields.Date(
        string='Check Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    
    expiry_date = fields.Date(
        string='Valid Until',
        help='Background check validity expiry',
        tracking=True
    )
    
    # Provider Information
    provider_name = fields.Char(
        string='Background Check Provider',
        required=True,
        tracking=True
    )
    
    provider_contact = fields.Char(string='Provider Contact')
    
    # Results
    status = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('clear', 'Clear'),
        ('flagged', 'Flagged - Review Required'),
        ('failed', 'Failed'),
        ('expired', 'Expired')
    ], string='Status', default='pending', required=True, tracking=True)
    
    result = fields.Text(
        string='Check Results',
        help='Summary of background check results'
    )
    
    flags = fields.Text(
        string='Flags/Issues',
        help='Any concerns or issues identified'
    )
    
    # Review and Approval
    reviewed_by_id = fields.Many2one(
        'res.users',
        string='Reviewed By',
        tracking=True
    )
    
    review_date = fields.Date(string='Review Date')
    
    review_notes = fields.Text(string='Review Notes')
    
    approved = fields.Boolean(
        string='Approved for Employment',
        tracking=True,
        help='Check if guard is approved based on background check results'
    )
    
    # Cost
    cost = fields.Monetary(
        string='Cost',
        currency_field='currency_id',
        help='Cost of background check'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # Related Fields
    guard_name = fields.Char(
        related='guard_id.name',
        string='Guard Name',
        store=True,
        readonly=True
    )
    
    guard_employee_number = fields.Char(
        related='guard_id.badge_number',
        string='Employee Number',
        readonly=True
    )
    
    # Attachments
    attachment_count = fields.Integer(
        string='Attachments',
        compute='_compute_attachment_count'
    )
    
    active = fields.Boolean(default=True)
    
    @api.depends('guard_id', 'check_type', 'check_date')
    def _compute_display_name(self):
        """Compute display name"""
        for record in self:
            if record.guard_id:
                check_type_name = dict(self._fields['check_type'].selection).get(record.check_type, '')
                record.display_name = f"{record.guard_id.name} - {check_type_name} ({record.check_date})"
            else:
                record.display_name = record.reference_number or 'New Background Check'
    
    def _compute_attachment_count(self):
        """Count attachments"""
        for record in self:
            record.attachment_count = self.env['ir.attachment'].search_count([
                ('res_model', '=', self._name),
                ('res_id', '=', record.id)
            ])
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate reference number on create"""
        for vals in vals_list:
            if vals.get('reference_number', _('New')) == _('New'):
                vals['reference_number'] = self.env['ir.sequence'].next_by_code(
                    'guard.background.check'
                ) or _('New')
        return super().create(vals_list)
    
    @api.constrains('check_date', 'expiry_date')
    def _check_dates(self):
        """Validate dates"""
        for record in self:
            if record.expiry_date and record.check_date:
                if record.expiry_date <= record.check_date:
                    raise ValidationError(_('Expiry date must be after check date!'))
    
    def action_approve(self):
        """Approve background check"""
        self.ensure_one()
        self.write({
            'status': 'clear',
            'approved': True,
            'reviewed_by_id': self.env.user.id,
            'review_date': fields.Date.today()
        })
        self.message_post(
            body=_('Background check approved by %s') % self.env.user.name,
            subtype_xmlid='mail.mt_note'
        )
    
    def action_flag(self):
        """Flag background check for review"""
        self.ensure_one()
        self.status = 'flagged'
        self.message_post(
            body=_('Background check flagged for review'),
            subtype_xmlid='mail.mt_comment'
        )
    
    def action_fail(self):
        """Mark background check as failed"""
        self.ensure_one()
        self.write({
            'status': 'failed',
            'approved': False,
            'reviewed_by_id': self.env.user.id,
            'review_date': fields.Date.today()
        })
        self.message_post(
            body=_('Background check failed'),
            subtype_xmlid='mail.mt_comment'
        )
    
    def action_view_attachments(self):
        """View attachments"""
        self.ensure_one()
        return {
            'name': _('Background Check Documents'),
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
    def _cron_check_expiring_background_checks(self):
        """Check for expiring background checks"""
        today = fields.Date.today()
        
        # Find checks expiring in 30 days
        checks = self.search([
            ('status', '=', 'clear'),
            ('expiry_date', '!=', False),
            ('expiry_date', '<=', fields.Date.add(today, days=30)),
            ('expiry_date', '>=', today)
        ])
        
        for check in checks:
            check.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Background Check Expiring'),
                note=_('Background check expires on %s. Schedule renewal.') % check.expiry_date,
                user_id=check.guard_id.supervisor_id.id if check.guard_id.supervisor_id else self.env.user.id
            )
        
        # Mark expired checks
        expired_checks = self.search([
            ('status', '=', 'clear'),
            ('expiry_date', '<', today)
        ])
        
        for check in expired_checks:
            check.status = 'expired'
            check.message_post(
                body=_('Background check has expired!'),
                subtype_xmlid='mail.mt_comment'
            )
        
        return True

