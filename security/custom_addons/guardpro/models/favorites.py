# -*- coding: utf-8 -*-
"""Favorites System (Quick Win)."""

from odoo import models, fields, api, _


class UserFavorite(models.Model):
    """User favorites for quick access."""
    
    _name = 'user.favorite'
    _description = 'User Favorite'
    _order = 'sequence, create_date desc'
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        default=lambda self: self.env.user,
        ondelete='cascade'
    )
    
    model_name = fields.Char(
        string='Model',
        required=True
    )
    
    record_id = fields.Integer(
        string='Record ID',
        required=True
    )
    
    record_name = fields.Char(
        string='Name',
        required=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    icon = fields.Char(
        string='Icon',
        default='fa-star'
    )
    
    color = fields.Integer(
        string='Color',
        default=0
    )
    
    notes = fields.Text(
        string='Notes'
    )
    
    _sql_constraints = [
        ('user_model_record_unique', 'unique(user_id, model_name, record_id)',
         'This item is already in your favorites!'),
    ]
    
    def action_open_record(self):
        """Open the favorited record."""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.model_name,
            'res_id': self.record_id,
            'view_mode': 'form',
            'target': 'current'
        }


class GuardProfile(models.Model):
    """Add favorite functionality to guard profile."""
    
    _inherit = 'guard.profile'
    
    is_favorite = fields.Boolean(
        string='Favorite',
        compute='_compute_is_favorite',
        inverse='_inverse_is_favorite'
    )
    
    def _compute_is_favorite(self):
        """Check if guard is in favorites."""
        for record in self:
            record.is_favorite = bool(self.env['user.favorite'].search([
                ('user_id', '=', self.env.user.id),
                ('model_name', '=', 'guard.profile'),
                ('record_id', '=', record.id)
            ], limit=1))
    
    def _inverse_is_favorite(self):
        """Toggle favorite status."""
        for record in self:
            favorite = self.env['user.favorite'].search([
                ('user_id', '=', self.env.user.id),
                ('model_name', '=', 'guard.profile'),
                ('record_id', '=', record.id)
            ], limit=1)
            
            if record.is_favorite and not favorite:
                self.env['user.favorite'].create({
                    'model_name': 'guard.profile',
                    'record_id': record.id,
                    'record_name': record.name,
                    'icon': 'fa-user'
                })
            elif not record.is_favorite and favorite:
                favorite.unlink()


class ClientSite(models.Model):
    """Add favorite functionality to client site."""
    
    _inherit = 'client.site'
    
    is_favorite = fields.Boolean(
        string='Favorite',
        compute='_compute_is_favorite',
        inverse='_inverse_is_favorite'
    )
    
    def _compute_is_favorite(self):
        """Check if site is in favorites."""
        for record in self:
            record.is_favorite = bool(self.env['user.favorite'].search([
                ('user_id', '=', self.env.user.id),
                ('model_name', '=', 'client.site'),
                ('record_id', '=', record.id)
            ], limit=1))
    
    def _inverse_is_favorite(self):
        """Toggle favorite status."""
        for record in self:
            favorite = self.env['user.favorite'].search([
                ('user_id', '=', self.env.user.id),
                ('model_name', '=', 'client.site'),
                ('record_id', '=', record.id)
            ], limit=1)
            
            if record.is_favorite and not favorite:
                self.env['user.favorite'].create({
                    'model_name': 'client.site',
                    'record_id': record.id,
                    'record_name': record.name,
                    'icon': 'fa-building'
                })
            elif not record.is_favorite and favorite:
                favorite.unlink()

