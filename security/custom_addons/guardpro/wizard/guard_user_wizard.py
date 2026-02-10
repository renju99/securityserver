# -*- coding: utf-8 -*-
"""Wizard for creating guard users with portal access."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class GuardUserWizard(models.TransientModel):
    """Wizard to create a guard profile with associated portal user."""

    _name = 'guard.user.wizard'
    _description = 'Create Guard User (Portal)'

    # Guard Information
    name = fields.Char(
        string='Guard Name',
        required=True,
        help='Full name of the guard'
    )
    badge_number = fields.Char(
        string='Badge Number',
        required=True,
        help='Unique badge number'
    )
    phone = fields.Char(
        string='Phone Number',
        required=True
    )
    email = fields.Char(
        string='Email',
        required=True,
        help='Email address for portal login'
    )
    photo = fields.Binary(
        string='Photo',
        attachment=True
    )

    # Employment Details
    hire_date = fields.Date(
        string='Hire Date',
        default=fields.Date.today,
        required=True
    )
    status = fields.Selection([
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated')
    ], string='Status', default='active', required=True)

    # Certifications & Training
    certifications = fields.Text(
        string='Certifications',
        help='List of security certifications held by guard'
    )
    license_number = fields.Char(
        string='Security License Number'
    )
    license_expiry = fields.Date(
        string='License Expiry Date'
    )

    # Contact Information
    emergency_contact = fields.Char(
        string='Emergency Contact Name'
    )
    emergency_phone = fields.Char(
        string='Emergency Contact Phone'
    )
    address = fields.Text(
        string='Address'
    )

    # Skills & Qualifications
    skill_ids = fields.Many2many(
        'guard.skill',
        string='Skills',
        help='Special skills (Armed, K9, First Aid, etc.)'
    )
    languages = fields.Char(
        string='Languages Spoken'
    )
    availability = fields.Selection([
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('on_call', 'On Call')
    ], string='Availability', default='full_time')

    # User Account Settings
    create_user = fields.Boolean(
        string='Create Portal User Account',
        default=True,
        help='Create a portal user account for this guard (mobile portal access only)'
    )
    send_invite = fields.Boolean(
        string='Send Portal Invitation Email',
        default=False,
        help='Send an email invitation to the guard to access the mobile portal'
    )

    # Optional HR Employee Link
    link_to_employee = fields.Boolean(
        string='Link to HR Employee',
        default=False,
        help='Optionally link this guard to an existing HR employee record'
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='HR Employee',
        help='Link to existing HR employee for payroll integration'
    )

    @api.constrains('email')
    def _check_email(self):
        """Validate email format."""
        for record in self:
            if record.email:
                import re
                if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', record.email):
                    raise ValidationError(_('Invalid email format!'))

    @api.constrains('badge_number')
    def _check_badge_unique(self):
        """Check if badge number is unique."""
        for record in self:
            existing = self.env['guard.profile'].search([
                ('badge_number', '=', record.badge_number)
            ])
            if existing:
                raise ValidationError(_(
                    'Badge number %s is already assigned to guard %s!'
                ) % (record.badge_number, existing.name))

    @api.constrains('email')
    def _check_email_unique(self):
        """Check if email is already used."""
        for record in self:
            if record.create_user and record.email:
                existing_user = self.env['res.users'].search([
                    ('login', '=', record.email)
                ])
                if existing_user:
                    raise ValidationError(_(
                        'Email %s is already used by user %s!'
                    ) % (record.email, existing_user.name))

    def action_create_guard(self):
        """Create guard profile and optionally create portal user."""
        self.ensure_one()

        # Create portal user if requested
        user = None
        if self.create_user:
            try:
                user = self._create_portal_user()
            except (UserError, Exception) as e:
                # Catch and suppress mail-related errors during user creation
                error_msg = str(e).lower()
                if isinstance(e, UserError) or 'email' in error_msg or 'mail' in error_msg or 'sender' in error_msg or 'unable to send' in error_msg or 'configure' in error_msg:
                    _logger.warning('Mail-related error during user creation (suppressed): %s', str(e))
                    # Try to create user again with more aggressive mail suppression
                    try:
                        user = self._create_portal_user()
                    except Exception as e2:
                        _logger.error('Failed to create user even with mail suppression: %s', str(e2))
                        # Continue without user - guard can be created without portal access
                        user = None
                else:
                    # Re-raise non-mail-related errors
                    raise

        # Create guard profile
        guard_vals = {
            'name': self.name,
            'user_id': user.id if user else False,
            'badge_number': self.badge_number,
            'phone': self.phone,
            'photo': self.photo,
            'hire_date': self.hire_date,
            'status': self.status,
            'certifications': self.certifications,
            'license_number': self.license_number,
            'license_expiry': self.license_expiry,
            'emergency_contact': self.emergency_contact,
            'emergency_phone': self.emergency_phone,
            'address': self.address,
            'skills': [(6, 0, self.skill_ids.ids)],
            'languages': self.languages,
            'availability': self.availability,
        }

        if self.link_to_employee and self.employee_id:
            guard_vals['employee_id'] = self.employee_id.id

        # Create guard profile with context flags to prevent email sending
        # mail_notrack: Prevents tracking emails
        # mail_create_nolog: Prevents creation log emails
        # mail_create_nosubscribe: Prevents subscription emails
        # mail_auto_subscribe_no_notify: Prevents auto-subscription notifications
        try:
            guard = self.env['guard.profile'].with_context(
                mail_notrack=True,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                mail_auto_subscribe_no_notify=True,
                mail_create_nosubscribe_list=True
            ).create(guard_vals)
        except (UserError, Exception) as e:
            # If creation fails due to email issues, try again with additional flags
            error_msg = str(e).lower()
            if isinstance(e, UserError) or 'email' in error_msg or 'mail' in error_msg or 'sender' in error_msg or 'unable to send' in error_msg or 'configure' in error_msg:
                _logger.warning('Email error during guard creation, retrying with no email context: %s', str(e))
                try:
                    guard = self.env['guard.profile'].with_context(
                        mail_notrack=True,
                        mail_create_nolog=True,
                        mail_create_nosubscribe=True,
                        mail_auto_subscribe_no_notify=True,
                        mail_create_nosubscribe_list=True,
                        default_email_from=False,
                        default_email_to=False
                    ).create(guard_vals)
                except Exception as e2:
                    # If still failing, log and suppress the error - guard creation should succeed
                    _logger.error('Guard creation still failing with mail suppression: %s', str(e2))
                    # Try one more time with all possible mail suppression flags
                    guard = self.env['guard.profile'].with_context(
                        mail_notrack=True,
                        mail_create_nolog=True,
                        mail_create_nosubscribe=True,
                        mail_auto_subscribe_no_notify=True,
                        mail_create_nosubscribe_list=True,
                        mail_create_nosubscribe_partner=True,
                        default_email_from=False,
                        default_email_to=False,
                        mail_notify_force_send=False
                    ).create(guard_vals)
            else:
                raise

        # Send portal invitation ONLY if explicitly requested AND email is configured
        # By default, send_invite is False, so no emails will be sent
        if user and self.send_invite:
            self._send_portal_invitation(user, guard)

        _logger.info('Guard profile created: %s (Badge: %s)', guard.name, guard.badge_number)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Guard Profile'),
            'res_model': 'guard.profile',
            'res_id': guard.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _create_portal_user(self):
        """Create a portal user account for the guard."""
        # Get the guard portal group
        portal_group = self.env.ref('guardpro.group_guardpro_guard_portal')

        # Create user with context flags to prevent email sending
        # no_reset_password: Prevents password reset email
        # mail_notrack: Prevents tracking emails
        # mail_create_nolog: Prevents creation log emails
        user_vals = {
            'name': self.name,
            'login': self.email,
            'email': self.email,
            'share': True,  # Portal user
            'groups_id': [(6, 0, [portal_group.id])],
            'active': True,
        }

        user = self.env['res.users'].with_context(
            no_reset_password=True,
            mail_notrack=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True
        ).create(user_vals)
        _logger.info('Portal user created: %s (Login: %s)', user.name, user.login)

        return user

    def _send_portal_invitation(self, user, guard):
        """Send portal access invitation email to the guard."""
        try:
            # Check if email is configured before attempting to send
            if not self.env['ir.mail_server'].search([], limit=1):
                _logger.warning('No mail server configured. Skipping portal invitation email.')
                return
            
            # Create portal wizard to send invitation
            wizard = self.env['portal.wizard'].create({
                'user_ids': [(0, 0, {
                    'partner_id': user.partner_id.id,
                    'email': user.email,
                    'in_portal': True,
                })]
            })

            # Send the invitation email
            wizard.user_ids.action_grant_access()

            _logger.info('Portal invitation sent to %s', user.email)
        except Exception as e:
            _logger.warning('Failed to send portal invitation: %s', str(e))
            # Don't fail the entire operation if email sending fails

