# -*- coding: utf-8 -*-
"""Physical Sites that belong under a Project (client.site)."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GuardSite(models.Model):
    """A physical site location within a security project."""

    _name = 'guard.site'
    _description = 'Project Site'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'project_id, name'

    name = fields.Char(
        string='Site Name',
        required=True,
        tracking=True,
        index=True,
    )
    code = fields.Char(
        string='Site Code',
        required=True,
        copy=False,
        tracking=True,
        index=True,
    )
    project_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True,
        ondelete='cascade',
        tracking=True,
        index=True,
        help='Parent project this site belongs to (e.g. NSHAMA).',
    )
    client_id = fields.Many2one(
        related='project_id.client_id',
        string='Client',
        store=True,
        readonly=True,
    )
    active = fields.Boolean(string='Active', default=True)
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ], string='Status', default='active', required=True, tracking=True)

    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one('res.country', string='Country')

    latitude = fields.Float(string='Latitude', digits=(10, 7))
    longitude = fields.Float(string='Longitude', digits=(10, 7))

    notes = fields.Text(string='Notes')
    color = fields.Integer(string='Color Index', default=0)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Site code must be unique!'),
        ('name_project_unique', 'unique(name, project_id)',
         'Site name must be unique within a project!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = (
                    self.env['ir.sequence'].next_by_code('guard.site') or '/'
                )
        return super().create(vals_list)

    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        for record in self:
            if record.latitude and not (-90 <= record.latitude <= 90):
                raise ValidationError(_('Latitude must be between -90 and 90!'))
            if record.longitude and not (-180 <= record.longitude <= 180):
                raise ValidationError(_('Longitude must be between -180 and 180!'))
