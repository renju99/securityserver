# -*- coding: utf-8 -*-
"""Wizard for creating guard users with portal access."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
import re

_logger = logging.getLogger(__name__)


class GuardUserWizard(models.TransientModel):
    """Wizard to create a guard profile with associated portal user."""

    _name = 'guard.user.wizard'
    _description = 'Create Guard User (Portal)'

    # Required basics
    name = fields.Char(
        string='Guard Name',
        required=True,
        help='Full name of the guard',
    )
    email = fields.Char(
        string='Email / Login',
        required=True,
        help='Email address used as the portal login',
    )
    phone = fields.Char(
        string='Phone Number',
    )

    # Access scope — projects / sites on the portal user
    site_ids = fields.Many2many(
        'client.site',
        string='Projects',
        required=True,
        help='Projects this guard can access (e.g. NSHAMA).',
    )
    guard_site_ids = fields.Many2many(
        'guard.site',
        string='Sites',
        domain="[('project_id', 'in', site_ids)]",
        help='Optional. Leave empty to grant all sites under the selected project(s).',
    )

    # Portal account
    create_user = fields.Boolean(
        string='Create Portal User Account',
        default=True,
        help='Create a portal user account for mobile / portal access',
    )
    send_invite = fields.Boolean(
        string='Send Portal Invitation Email',
        default=False,
        help='Send an email invitation (requires a configured mail server)',
    )

    # Optional extras (collapsed in the form)
    badge_number = fields.Char(
        string='Badge Number',
        help='Leave empty to auto-generate (GRD-####)',
    )
    hire_date = fields.Date(
        string='Hire Date',
        default=fields.Date.today,
    )
    status = fields.Selection([
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
    ], string='Status', default='active')
    photo = fields.Binary(string='Photo', attachment=True)
    availability = fields.Selection([
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('on_call', 'On Call'),
    ], string='Availability', default='full_time')

    @api.constrains('email')
    def _check_email(self):
        for record in self:
            if record.email and not re.match(
                r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
                record.email,
            ):
                raise ValidationError(_('Invalid email format!'))

    @api.constrains('badge_number')
    def _check_badge_unique(self):
        for record in self:
            if not record.badge_number:
                continue
            existing = self.env['guard.profile'].search([
                ('badge_number', '=', record.badge_number),
            ], limit=1)
            if existing:
                raise ValidationError(_(
                    'Badge number %s is already assigned to guard %s!'
                ) % (record.badge_number, existing.name))

    @api.constrains('email')
    def _check_email_unique(self):
        for record in self:
            if record.create_user and record.email:
                existing_user = self.env['res.users'].search([
                    ('login', '=', record.email),
                ], limit=1)
                if existing_user:
                    raise ValidationError(_(
                        'Email %s is already used by user %s!'
                    ) % (record.email, existing_user.name))

    @api.constrains('site_ids')
    def _check_projects(self):
        for record in self:
            if not record.site_ids:
                raise ValidationError(_('Select at least one project for this guard.'))

    def action_create_guard(self):
        """Create guard profile and optionally create portal user."""
        self.ensure_one()

        user = None
        if self.create_user:
            try:
                user = self._create_portal_user()
            except (UserError, Exception) as e:
                error_msg = str(e).lower()
                if isinstance(e, UserError) or any(
                    token in error_msg
                    for token in ('email', 'mail', 'sender', 'unable to send', 'configure')
                ):
                    _logger.warning('Mail-related error during user creation (suppressed): %s', e)
                    try:
                        user = self._create_portal_user()
                    except Exception as e2:
                        _logger.error('Failed to create user even with mail suppression: %s', e2)
                        user = None
                else:
                    raise

        badge = (self.badge_number or '').strip() or False
        guard_vals = {
            'name': self.name,
            'user_id': user.id if user else False,
            'badge_number': badge,
            'phone': self.phone or False,
            'photo': self.photo,
            'hire_date': self.hire_date or fields.Date.today(),
            'status': self.status or 'active',
            'availability': self.availability or 'full_time',
        }

        try:
            guard = self.env['guard.profile'].with_context(
                mail_notrack=True,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                mail_auto_subscribe_no_notify=True,
                mail_create_nosubscribe_list=True,
            ).create(guard_vals)
        except (UserError, Exception) as e:
            error_msg = str(e).lower()
            if isinstance(e, UserError) or any(
                token in error_msg
                for token in ('email', 'mail', 'sender', 'unable to send', 'configure')
            ):
                _logger.warning('Email error during guard creation, retrying: %s', e)
                guard = self.env['guard.profile'].with_context(
                    mail_notrack=True,
                    mail_create_nolog=True,
                    mail_create_nosubscribe=True,
                    mail_auto_subscribe_no_notify=True,
                    mail_create_nosubscribe_list=True,
                    mail_create_nosubscribe_partner=True,
                    default_email_from=False,
                    default_email_to=False,
                    mail_notify_force_send=False,
                ).create(guard_vals)
            else:
                raise

        if user and self.send_invite:
            self._send_portal_invitation(user, guard)

        _logger.info('Guard profile created: %s (Badge: %s)', guard.name, guard.badge_number)

        # Close the wizard and refresh the current list without stacking
        # another "Guard Portal Users" breadcrumb entry.
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Guard Created'),
                'message': _('Created %s (Badge: %s)') % (
                    guard.name, guard.badge_number or '—',
                ),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'soft_reload',
                },
            },
        }

    def _create_portal_user(self):
        """Create a portal user account for the guard with project/site access."""
        portal_group = self.env.ref('guardpro.group_guardpro_guard_portal')
        user_vals = {
            'name': self.name,
            'login': self.email,
            'email': self.email,
            'share': True,
            'groups_id': [(6, 0, [portal_group.id])],
            'active': True,
            'site_ids': [(6, 0, self.site_ids.ids)],
            'guard_site_ids': [(6, 0, self.guard_site_ids.ids)],
        }
        user = self.env['res.users'].with_context(
            no_reset_password=True,
            mail_notrack=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
        ).create(user_vals)
        _logger.info('Portal user created: %s (Login: %s)', user.name, user.login)
        return user

    def _send_portal_invitation(self, user, guard):
        """Send portal access invitation email to the guard."""
        try:
            if not self.env['ir.mail_server'].search([], limit=1):
                _logger.warning('No mail server configured. Skipping portal invitation email.')
                return
            wizard = self.env['portal.wizard'].create({
                'user_ids': [(0, 0, {
                    'partner_id': user.partner_id.id,
                    'email': user.email,
                    'in_portal': True,
                })]
            })
            wizard.user_ids.action_grant_access()
            _logger.info('Portal invitation sent to %s', user.email)
        except Exception as e:
            _logger.warning('Failed to send portal invitation: %s', e)
