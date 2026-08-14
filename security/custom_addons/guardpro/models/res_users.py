# -*- coding: utf-8 -*-
"""User Extension for Site and Zone Based Access Control."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    """Extend res.users to add site and zone assignment for access control."""

    _inherit = 'res.users'

    site_ids = fields.Many2many(
        'client.site',
        'guardpro_user_site_rel',
        'user_id',
        'site_id',
        string='Assigned Projects',
        help='Projects this user can access. '
             'If no Sites are selected below for a project, the user gets all sites under that project. '
             'Administrators see everything regardless of this field.',
    )
    guard_site_ids = fields.Many2many(
        'guard.site',
        'guardpro_user_guard_site_rel',
        'user_id',
        'guard_site_id',
        string='Assigned Sites',
        help='Optional. When set for a project, the user only sees those sites '
             '(not every site under the project). Leave empty to grant all sites '
             'under the assigned project(s).',
    )
    zone_ids = fields.Many2many(
        'site.zone',
        'guardpro_user_zone_rel',
        'user_id',
        'zone_id',
        string='Assigned Zones',
        help='When set, the user only sees incidents, tours, checkpoints, shifts, '
             'and other records tagged with these zones. Projects must be selected first.',
    )

    guard_profile_id = fields.One2many(
        'guard.profile',
        'user_id',
        string='Guard Profile',
        help='Guard profile associated with this user',
    )

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        for user in users:
            if user.has_group('guardpro.group_guardpro_client_user') and user.partner_id:
                user._auto_assign_client_sites()
            user._sync_zone_access_group()
        return users

    def write(self, vals):
        result = super().write(vals)
        if 'groups_id' in vals or 'partner_id' in vals:
            for user in self:
                if user.has_group('guardpro.group_guardpro_client_user') and user.partner_id:
                    user._auto_assign_client_sites()
        if 'zone_ids' in vals or 'site_ids' in vals or 'guard_site_ids' in vals:
            for user in self:
                user._sync_zone_access_group()
        return result

    @api.constrains('groups_id')
    def _check_client_user_not_for_residents(self):
        """Client User implies Internal User — never on residents/tenants."""
        client_group = self.env.ref(
            'guardpro.group_guardpro_client_user', raise_if_not_found=False
        )
        resident_group = self.env.ref(
            'guardpro.group_guardpro_resident_user', raise_if_not_found=False
        )
        if not client_group:
            return
        Resident = self.env['tenant.resident'].sudo()
        for user in self:
            if not user.active:
                continue
            if getattr(user, 'share', None) and not (client_group in user.groups_id):
                continue
            try:
                if user._is_public():
                    continue
            except Exception:
                pass
            has_client = client_group in user.groups_id
            if not has_client:
                continue
            if resident_group and resident_group in user.groups_id:
                raise ValidationError(_(
                    'User "%s" cannot have both Client User (internal/backend) '
                    'and Resident/Tenant User (portal). Residents must use only '
                    'Resident/Tenant User.'
                ) % user.display_name)
            if Resident.search_count([('user_id', '=', user.id)], limit=1):
                raise ValidationError(_(
                    'User "%s" is linked to a resident/tenant record and must '
                    'not be assigned Client User (Internal User). Use '
                    'Resident/Tenant User for portal access instead.'
                ) % user.display_name)

    @api.constrains('zone_ids', 'site_ids', 'guard_site_ids')
    def _check_zone_site_consistency(self):
        for user in self:
            if user.guard_site_ids:
                if not user.site_ids:
                    raise ValidationError(_(
                        'Assign at least one project before selecting sites for user "%s".'
                    ) % user.name)
                invalid_sites = user.guard_site_ids.filtered(
                    lambda s: s.project_id not in user.site_ids
                )
                if invalid_sites:
                    raise ValidationError(_(
                        'Sites must belong to assigned projects. Invalid sites for user "%s": %s'
                    ) % (
                        user.name,
                        ', '.join(invalid_sites.mapped('display_name')),
                    ))
            if not user.zone_ids:
                continue
            if not user.site_ids:
                raise ValidationError(_(
                    'Assign at least one project before selecting zones for user "%s".'
                ) % user.name)
            invalid = user.zone_ids.filtered(
                lambda z: z.site_id not in user.site_ids
            )
            if invalid:
                raise ValidationError(_(
                    'Zones must belong to assigned projects. Invalid zones for user "%s": %s'
                ) % (
                    user.name,
                    ', '.join(invalid.mapped('display_name')),
                ))

    @api.onchange('site_ids')
    def _onchange_site_ids(self):
        if self.guard_site_ids:
            self.guard_site_ids = self.guard_site_ids.filtered(
                lambda s: s.project_id in self.site_ids
            )
        if self.zone_ids:
            self.zone_ids = self.zone_ids.filtered(
                lambda z: z.site_id in self.site_ids
            )

    @api.onchange('guard_site_ids')
    def _onchange_guard_site_ids(self):
        if self.guard_site_ids:
            self.site_ids = self.site_ids | self.guard_site_ids.mapped('project_id')

    @api.onchange('zone_ids')
    def _onchange_zone_ids(self):
        if self.zone_ids:
            self.site_ids = self.site_ids | self.zone_ids.mapped('site_id')

    def _sync_zone_access_group(self):
        """Add/remove zone-restricted group based on zone assignments."""
        zone_group = self.env.ref(
            'guardpro.group_guardpro_zone_restricted',
            raise_if_not_found=False,
        )
        if not zone_group:
            return
        for user in self:
            if user.has_group('guardpro.group_guardpro_admin'):
                if zone_group in user.groups_id:
                    user.write({'groups_id': [(3, zone_group.id)]})
                continue
            if user.zone_ids:
                if zone_group not in user.groups_id:
                    user.write({'groups_id': [(4, zone_group.id)]})
            elif zone_group in user.groups_id:
                user.write({'groups_id': [(3, zone_group.id)]})

    def guardpro_has_zone_restrictions(self):
        """True when user access is limited to specific zones (not admin)."""
        self.ensure_one()
        return bool(
            self.zone_ids
            and not self.has_group('guardpro.group_guardpro_admin')
        )

    def guardpro_allowed_guard_site_ids(self):
        """Physical site IDs this user may access.

        - Project only → all sites under that project
        - Specific sites set for a project → only those sites
        - Admin → all sites (returns None)
        """
        self.ensure_one()
        if self.has_group('guardpro.group_guardpro_admin'):
            return None
        assigned = self.guard_site_ids
        projects_with_sites = assigned.mapped('project_id')
        project_only = self.site_ids - projects_with_sites
        sites = assigned
        if project_only:
            sites |= self.env['guard.site'].sudo().search([
                ('project_id', 'in', project_only.ids),
            ])
        return sites.ids

    def guardpro_guard_site_access_domain(self):
        """Domain for guard.site records matching assignment rules."""
        self.ensure_one()
        if self.has_group('guardpro.group_guardpro_admin'):
            return []
        allowed = self.guardpro_allowed_guard_site_ids()
        if not allowed:
            return [('id', '=', False)]
        return [('id', 'in', allowed)]

    def guardpro_mobile_locations(self):
        """Selectable mobile locations: project (all assigned sites) plus each site."""
        self.ensure_one()
        GuardSite = self.env['guard.site'].sudo()
        Project = self.env['client.site'].sudo()
        allowed_ids = self.guardpro_allowed_guard_site_ids()
        if allowed_ids is None:
            sites = GuardSite.search([('active', '=', True)])
            projects = Project.search([('active', '=', True)])
        else:
            sites = GuardSite.browse(allowed_ids).filtered('active')
            projects = self.site_ids | sites.mapped('project_id')
        options = []
        for project in projects.sorted(lambda p: p.name or ''):
            project_sites = sites.filtered(
                lambda s, pid=project.id: s.project_id.id == pid
            ).sorted(lambda s: s.name or '')
            options.append({
                'key': 'p:%s' % project.id,
                'type': 'project',
                'id': project.id,
                'name': project.name,
                'project_name': project.name,
                'label': project.name,
                'site_ids': project_sites.ids,
            })
            for site in project_sites:
                options.append({
                    'key': 's:%s' % site.id,
                    'type': 'site',
                    'id': site.id,
                    'name': site.name,
                    'project_name': project.name,
                    'label': '%s - %s' % (project.name, site.name),
                    'site_ids': [site.id],
                })
        return options

    def guardpro_ensure_mobile_context(self):
        """Current mobile location from session, defaulting to the first allowed."""
        self.ensure_one()
        options = self.guardpro_mobile_locations()
        key = None
        try:
            key = request.session.get('gp_mobile_loc_key')
        except Exception:
            key = None
        current = next((opt for opt in options if opt['key'] == key), None)
        if not current and options:
            current = options[0]
            try:
                request.session['gp_mobile_loc_key'] = current['key']
            except Exception:
                pass
        return current

    def guardpro_mobile_record_domain(self, model_name, project_field='site_id',
                                      guard_site_field='guard_site_id'):
        """Domain limiting records to the selected mobile site/project.

        Project selected → all assigned sites under that project (plus untagged).
        Site selected → only records tagged to that site.
        """
        self.ensure_one()
        ctx = self.guardpro_ensure_mobile_context()
        if not ctx:
            return []
        Model = self.env[model_name]
        has_guard_site = (
            '.' in (guard_site_field or '')
            or (guard_site_field in Model._fields)
        )
        if ctx['type'] == 'project':
            project_id = ctx['id']
            assigned_ids = ctx.get('site_ids') or []
            if not has_guard_site:
                return [(project_field, '=', project_id)]
            if assigned_ids:
                return [
                    '&',
                    (project_field, '=', project_id),
                    '|',
                    (guard_site_field, 'in', assigned_ids),
                    (guard_site_field, '=', False),
                ]
            return [(project_field, '=', project_id)]
        site = self.env['guard.site'].sudo().browse(ctx['id'])
        if not site.exists():
            return [('id', '=', False)]
        if not has_guard_site:
            return [('id', '=', False)]
        return [
            (project_field, '=', site.project_id.id),
            (guard_site_field, '=', site.id),
        ]

    def guardpro_mobile_write_vals(self):
        """site_id / guard_site_id values for records created from the mobile app."""
        self.ensure_one()
        ctx = self.guardpro_ensure_mobile_context()
        if not ctx:
            return {}
        if ctx['type'] == 'site':
            site = self.env['guard.site'].sudo().browse(ctx['id'])
            if not site.exists():
                return {}
            return {
                'site_id': site.project_id.id,
                'guard_site_id': site.id,
            }
        return {'site_id': ctx['id']}

    def guardpro_zone_access_domain(self, zone_field='zone_id', site_field='site_id'):
        """Domain for zone-aware models (incidents, tours, checkpoints, etc.)."""
        self.ensure_one()
        if self.has_group('guardpro.group_guardpro_admin'):
            return []
        if self.guardpro_has_zone_restrictions():
            return [(zone_field, 'in', self.zone_ids.ids)]
        if self.site_ids:
            return [(site_field, 'in', self.site_ids.ids)]
        return [('id', '=', False)]

    def _auto_assign_client_sites(self):
        """Automatically assign sites to client users based on partner relationship."""
        self.ensure_one()

        if not self.partner_id:
            return

        partner = self.partner_id
        sites = self.env['client.site'].search([
            ('client_id', '=', partner.id),
        ])
        if partner.parent_id and partner.parent_id.is_company:
            parent_sites = self.env['client.site'].search([
                ('client_id', '=', partner.parent_id.id),
            ])
            sites |= parent_sites

        if sites:
            # Sync exactly to partner-linked sites (add missing, drop stale).
            to_set = [(6, 0, sites.ids)]
            if set(self.site_ids.ids) != set(sites.ids):
                self.write({'site_ids': to_set})
                _logger.info(
                    'Synced site assignment for client user %s (ID: %s) to %d site(s)',
                    self.name, self.id, len(sites),
                )

    def action_refresh_site_assignments(self):
        """Manually refresh site assignments for client users."""
        client_users = self.filtered(
            lambda u: u.has_group('guardpro.group_guardpro_client_user')
        )
        for user in client_users:
            user._auto_assign_client_sites()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Project Assignments Refreshed'),
                'message': _(
                    'Project assignments have been refreshed for %d user(s).',
                    len(client_users),
                ),
                'type': 'success',
                'sticky': False,
            },
        }
