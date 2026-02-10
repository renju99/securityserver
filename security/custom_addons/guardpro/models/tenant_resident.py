# -*- coding: utf-8 -*-
"""Tenant/Resident Model for Community-Based Feedback."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TenantResident(models.Model):
    """Tenant/Resident for community sites - enables feedback from residents."""
    
    _name = 'tenant.resident'
    _description = 'Tenant/Resident'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'name'
    
    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
        index=True
    )
    
    email = fields.Char(
        string='Email',
        required=True,
        tracking=True,
        index=True
    )
    
    phone = fields.Char(
        string='Phone',
        tracking=True
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Portal User',
        tracking=False,  # Disabled to prevent automatic "assigned to" emails
        help='Portal user account for this resident'
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Related Partner',
        tracking=False,  # Disabled to prevent automatic notifications
        ondelete='cascade'
    )
    
    site_id = fields.Many2one(
        'client.site',
        string='Site/Community',
        required=True,
        tracking=True,
        index=True,
        ondelete='cascade'
    )
    
    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        related='site_id.client_id',
        store=True,
        readonly=True
    )
    
    unit_number = fields.Char(
        string='Unit/Apartment Number',
        tracking=True
    )
    
    building = fields.Char(
        string='Building',
        help='Building name or number'
    )
    
    # Status
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('moved_out', 'Moved Out')
    ], string='Status', default='active', required=True, tracking=True)
    
    # Dates
    move_in_date = fields.Date(
        string='Move-In Date',
        tracking=True
    )
    
    move_out_date = fields.Date(
        string='Move-Out Date',
        tracking=True
    )
    
    # Portal Access
    portal_access = fields.Boolean(
        string='Portal Access',
        default=True,
        tracking=True,
        help='Enable portal access for this resident'
    )
    
    # Feedback Stats
    feedback_count = fields.Integer(
        string='Feedback Count',
        compute='_compute_feedback_count'
    )
    
    # Emergency Contact
    emergency_contact_name = fields.Char(
        string='Emergency Contact Name'
    )
    
    emergency_contact_phone = fields.Char(
        string='Emergency Contact Phone'
    )
    
    # Notes
    notes = fields.Text(
        string='Notes'
    )
    
    @api.depends('email')
    def _compute_feedback_count(self):
        """Compute feedback count."""
        for record in self:
            record.feedback_count = self.env['client.feedback'].search_count([
                ('resident_id', '=', record.id)
            ])
    
    @api.constrains('email')
    def _check_email(self):
        """Validate email format."""
        for record in self:
            if record.email and '@' not in record.email:
                raise ValidationError(_('Please provide a valid email address.'))
    
    @api.constrains('move_in_date', 'move_out_date')
    def _check_dates(self):
        """Validate move-in and move-out dates."""
        for record in self:
            if record.move_in_date and record.move_out_date:
                if record.move_out_date < record.move_in_date:
                    raise ValidationError(_('Move-out date cannot be before move-in date.'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create resident and optionally create portal user."""
        # Create records without sending mail notifications yet
        records = super(TenantResident, self.with_context(mail_create_notrack=True)).create(vals_list)
        
        for record in records:
            if record.portal_access and not record.user_id:
                # This will send the proper welcome email
                record._create_portal_user()
        
        return records
    
    def write(self, vals):
        """Update portal user when email changes."""
        result = super().write(vals)
        
        if 'email' in vals:
            for record in self:
                if record.user_id:
                    record.user_id.login = vals['email']
        
        if 'portal_access' in vals:
            for record in self:
                if vals['portal_access'] and not record.user_id:
                    record._create_portal_user()
                elif not vals['portal_access'] and record.user_id:
                    record.user_id.active = False
        
        return result
    
    def _create_portal_user(self):
        """Create portal user for resident."""
        self.ensure_one()
        
        if self.user_id:
            return
        
        # Create partner if not exists
        if not self.partner_id:
            partner = self.env['res.partner'].create({
                'name': self.name,
                'email': self.email,
                'phone': self.phone,
                'type': 'contact',
                'is_company': False
            })
            # Set partner without triggering notifications
            self.with_context(mail_notrack=True).write({'partner_id': partner.id})
        
        # Create portal user with signup capability
        portal_group = self.env.ref('base.group_portal')
        resident_group = self.env.ref('guardpro.group_guardpro_resident_user')
        
        user_vals = {
            'name': self.name,
            'login': self.email,
            'partner_id': self.partner_id.id,
            'groups_id': [(6, 0, [portal_group.id, resident_group.id])],
            'site_ids': [(6, 0, [self.site_id.id])],
        }
        
        user = self.env['res.users'].with_context(no_reset_password=True).create(user_vals)
        
        # Set user_id without triggering mail notifications
        self.with_context(mail_notrack=True, mail_create_nolog=True).write({'user_id': user.id})
        
        # Generate signup token for first-time password setup
        # Use signup_type='signup' to indicate this is for new user account creation
        # This sets the signup_type field on the partner, which is used by _get_signup_url()
        user.partner_id.signup_prepare(signup_type='signup')
        
        # Send portal access email
        if user:
            try:
                # Determine the 'from' email address
                email_from = self.env.user.email or 'noreply@example.com'
                if self.site_id and self.site_id.client_id and self.site_id.client_id.email:
                    email_from = self.site_id.client_id.email
                
                # Create the email with rendered values
                mail_values = {
                    'subject': f'Welcome to {self.site_id.name} - Portal Access',
                    'email_from': email_from,
                    'email_to': self.email,
                    'body_html': self._render_portal_invitation_body(),
                }
                
                if self.partner_id:
                    mail_values['partner_ids'] = [(4, self.partner_id.id)]
                
                mail = self.env['mail.mail'].create(mail_values)
                mail.send()
            except Exception as e:
                _logger.warning('Could not send portal access email: %s', str(e))
    
    def action_grant_portal_access(self):
        """Grant portal access to resident."""
        self.ensure_one()
        
        if not self.user_id:
            self._create_portal_user()
        else:
            self.user_id.active = True
        
        self.portal_access = True
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Granted'),
                'message': _('Portal access has been granted to %s') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_revoke_portal_access(self):
        """Revoke portal access."""
        self.ensure_one()
        
        if self.user_id:
            self.user_id.active = False
        
        self.portal_access = False
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Revoked'),
                'message': _('Portal access has been revoked for %s') % self.name,
                'type': 'warning',
                'sticky': False,
            }
        }
    
    def action_view_feedback(self):
        """View feedback submitted by this resident."""
        self.ensure_one()
        
        return {
            'name': _('Feedback: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'client.feedback',
            'view_mode': 'list,form',
            'domain': [('resident_id', '=', self.id)],
            'context': {'default_resident_id': self.id, 'default_site_id': self.site_id.id}
        }
    
    def action_send_invitation_email(self):
        """Send portal invitation email."""
        self.ensure_one()
        
        if not self.user_id:
            self._create_portal_user()
        else:
            # Ensure signup type is set for existing users (for password reset)
            partner = self.user_id.partner_id
            if not partner.signup_type:
                # Set signup_type so the user can set/reset their password
                partner.signup_prepare(signup_type='signup')
        
        try:
            # Determine the 'from' email address
            email_from = self.env.user.email or 'noreply@example.com'
            if self.site_id and self.site_id.client_id and self.site_id.client_id.email:
                email_from = self.site_id.client_id.email
            
            # Create the email directly with rendered values
            mail_values = {
                'subject': f'Welcome to {self.site_id.name} - Portal Access',
                'email_from': email_from,
                'email_to': self.email,
                'body_html': self._render_portal_invitation_body(),
            }
            
            # Add partner for tracking
            if self.partner_id:
                mail_values['partner_ids'] = [(4, self.partner_id.id)]
            
            # Create and send the email
            mail = self.env['mail.mail'].create(mail_values)
            mail.send()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Invitation Sent'),
                    'message': _('Portal invitation email has been sent to %s') % self.email,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def _render_portal_invitation_body(self):
        """Render the portal invitation email body."""
        self.ensure_one()
        
        # Determine portal link based on signup token availability
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        
        portal_link = f'{base_url}/web/login'
        portal_button_text = 'Access Portal'
        instruction_text = 'If this is your first time logging in, please use the "Reset Password" link on the login page to set your password.'
        
        # Check if user has signup type set (indicating password setup is needed)
        if self.user_id and self.user_id.partner_id:
            partner = self.user_id.partner_id.sudo()
            
            # Check for signup type and generate URL
            try:
                # signup_type is set by signup_prepare() - 'signup' for new users, 'reset' for password reset
                if partner.signup_type:
                    # Call the method to generate the signup URL
                    signup_url = partner._get_signup_url()
                    if signup_url:
                        portal_link = signup_url
                        portal_button_text = 'Set Your Password & Access Portal'
                        instruction_text = 'Click the button below to set your password and access the portal for the first time.'
                        _logger.info('Resident %s: Using signup URL for portal invitation: %s', self.name, signup_url)
                    else:
                        _logger.warning('Resident %s: signup_type is set but _get_signup_url() returned None', self.name)
                else:
                    _logger.warning('Resident %s: No signup_type found, using fallback login link', self.name)
            except Exception as e:
                _logger.warning('Resident %s: Error generating signup URL: %s', self.name, str(e))
        
        # Build the HTML body
        building_info = ''
        if self.building:
            building_info = f'<br/>Building: <strong>{self.building}</strong>'
        
        body_html = f'''
<div style="margin: 0px; padding: 0px; font-family: 'Lucida Grande', Ubuntu, Arial, Verdana, sans-serif; font-size: 13px; color: rgb(34, 34, 34);">
    <p>Dear {self.name},</p>
    
    <p>
        Welcome to <strong>{self.site_id.name}</strong>! We are pleased to provide you with access to our resident portal.
    </p>
    
    <p>
        Through the portal, you can:
    </p>
    <ul>
        <li>View real-time guard locations and activity</li>
        <li>Monitor incident reports and status updates</li>
        <li>Submit feedback and rate security services</li>
        <li>View scheduled guard shifts</li>
        <li>Access important security information</li>
    </ul>
    
    <p style="margin: 20px 0px;">
        <strong>Your Portal Access Details:</strong><br/>
        Login Email: <strong>{self.email}</strong><br/>
        Unit: <strong>{self.unit_number or 'N/A'}</strong>
        {building_info}
    </p>
    
    <div style="margin: 20px 0px;">
        <a href="{portal_link}" 
           style="background-color: #875A7B; padding: 10px 20px; text-decoration: none; color: #fff; border-radius: 5px; display: inline-block;">
            {portal_button_text}
        </a>
    </div>
    
    <p>
        {instruction_text}
    </p>
    
    <p>
        If you have any questions or need assistance, please contact our management team.
    </p>
    
    <p>
        Best regards,<br/>
        <strong>{self.site_id.client_id.name if self.site_id.client_id else 'Management'}</strong><br/>
        Security Management Team
    </p>
    
    <hr style="margin: 20px 0px; border: 1px solid #eee;"/>
    
    <p style="font-size: 11px; color: #999;">
        This is an automated message from {self.site_id.name} Security Portal. 
        Please do not reply to this email.
    </p>
</div>
'''
        return body_html
    
    def _compute_access_url(self):
        """Compute portal access URL."""
        super()._compute_access_url()
        for record in self:
            record.access_url = '/my/resident/%s' % record.id


class ClientSite(models.Model):
    """Extend client site with resident management."""
    
    _inherit = 'client.site'
    
    is_community = fields.Boolean(
        string='Is Community/Residential',
        default=False,
        help='Enable if this site has multiple tenants/residents'
    )
    
    resident_ids = fields.One2many(
        'tenant.resident',
        'site_id',
        string='Residents/Tenants'
    )
    
    resident_count = fields.Integer(
        string='Resident Count',
        compute='_compute_resident_count'
    )
    
    active_resident_count = fields.Integer(
        string='Active Residents',
        compute='_compute_resident_count'
    )
    
    @api.depends('resident_ids', 'resident_ids.status')
    def _compute_resident_count(self):
        """Compute resident counts."""
        for record in self:
            record.resident_count = len(record.resident_ids)
            record.active_resident_count = len(
                record.resident_ids.filtered(lambda r: r.status == 'active')
            )
    
    def action_view_residents(self):
        """View residents for this site."""
        self.ensure_one()
        
        return {
            'name': _('Residents: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'tenant.resident',
            'view_mode': 'list,form',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id}
        }

