# -*- coding: utf-8 -*-
"""Ordered checkpoint lines for security tours."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SecurityTourCheckpointLine(models.Model):
    """Links a checkpoint to a tour with an explicit patrol sequence."""

    _name = 'security.tour.checkpoint.line'
    _description = 'Tour Checkpoint Sequence'
    _order = 'sequence, id'
    _rec_name = 'checkpoint_id'

    tour_id = fields.Many2one(
        'security.tour',
        string='Tour',
        required=True,
        ondelete='cascade',
        index=True,
    )
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        store=True,
        index=True,
        help='Site for filtering checkpoints (from tour or parent form context).',
    )
    checkpoint_id = fields.Many2one(
        'checkpoint',
        string='Checkpoint',
        required=True,
        ondelete='restrict',
        index=True,
    )
    sequence = fields.Integer(
        string='Serial #',
        default=10,
        help='Patrol order for this checkpoint within the tour (lower numbers first).',
    )

    # Related fields for list / form (shown after checkpoint is selected)
    name = fields.Char(
        related='checkpoint_id.name',
        string='Checkpoint Name',
        readonly=True,
    )
    code = fields.Char(related='checkpoint_id.code', readonly=True)
    scan_type = fields.Selection(related='checkpoint_id.scan_type', readonly=True)
    requires_photo = fields.Boolean(related='checkpoint_id.requires_photo', readonly=True)
    requires_note = fields.Boolean(related='checkpoint_id.requires_note', readonly=True)

    def _resolve_site_id(self, tour_id=None, site_id=None):
        """Site for checkpoint domain — line, parent form context, then tour."""
        if site_id:
            return site_id
        ctx_site = self.env.context.get('default_site_id')
        if ctx_site:
            return ctx_site
        tid = tour_id or self.env.context.get('default_tour_id')
        if tid:
            tour = self.env['security.tour'].browse(tid)
            if tour.site_id:
                return tour.site_id.id
        return False

    @api.model
    def default_get(self, fields_list):
        """Link new lines to the tour and site open in the form."""
        res = super().default_get(fields_list)
        if not res.get('tour_id'):
            tour_id = (
                self.env.context.get('default_tour_id')
                or (
                    self.env.context.get('active_id')
                    if self.env.context.get('active_model') == 'security.tour'
                    else None
                )
            )
            if tour_id:
                res['tour_id'] = tour_id
        if not res.get('site_id'):
            res['site_id'] = self._resolve_site_id(
                tour_id=res.get('tour_id'),
            )
        return res

    @api.onchange('tour_id')
    def _onchange_tour_id_site(self):
        site_id = self._resolve_site_id(tour_id=self.tour_id.id if self.tour_id else None)
        if site_id:
            self.site_id = site_id

    @api.onchange('site_id', 'tour_id')
    def _onchange_checkpoint_id_domain(self):
        """Keep checkpoint dropdown filtered even before the line is saved."""
        site_id = self._resolve_site_id(
            tour_id=self.tour_id.id if self.tour_id else None,
            site_id=self.site_id.id if self.site_id else None,
        )
        if site_id:
            return {'domain': {'checkpoint_id': [('site_id', '=', site_id)]}}
        return {'domain': {'checkpoint_id': [('id', '=', False)]}}

    @api.model_create_multi
    def create(self, vals_list):
        """Assign sequence and site when adding a checkpoint to a tour."""
        Line = self.env['security.tour.checkpoint.line']
        for vals in vals_list:
            if not vals.get('site_id'):
                vals['site_id'] = self._resolve_site_id(
                    tour_id=vals.get('tour_id'),
                )
            if vals.get('sequence'):
                continue
            tour_id = vals.get('tour_id')
            if tour_id:
                existing = Line.search([('tour_id', '=', tour_id)])
                vals['sequence'] = (max(existing.mapped('sequence') or [0]) + 10)
            else:
                vals['sequence'] = 10
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('tour_id') and 'site_id' not in vals:
            vals['site_id'] = self._resolve_site_id(tour_id=vals['tour_id'])
        return super().write(vals)

    _sql_constraints = [
        (
            'checkpoint_unique_per_tour',
            'unique(tour_id, checkpoint_id)',
            'Each checkpoint can only appear once per tour.',
        ),
    ]

    @api.constrains('checkpoint_id', 'tour_id')
    def _check_checkpoint_site(self):
        """Checkpoint should belong to the same site as the tour when site is set."""
        for line in self:
            if (
                line.checkpoint_id
                and line.tour_id
                and line.tour_id.site_id
                and line.checkpoint_id.site_id
                and line.checkpoint_id.site_id != line.tour_id.site_id
            ):
                raise ValidationError(_(
                    'Checkpoint "%s" belongs to site "%s" but tour "%s" is for site "%s".'
                ) % (
                    line.checkpoint_id.name,
                    line.checkpoint_id.site_id.name,
                    line.tour_id.name,
                    line.tour_id.site_id.name,
                ))
