# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class VisitorDenyWizard(models.TransientModel):
    """Wizard to deny visitor access"""
    _name = 'visitor.deny.wizard'
    _description = 'Deny Visitor Access'

    visitor_id = fields.Many2one(
        'visitor.management',
        string='Visitor',
        required=True
    )
    reason = fields.Text(
        string='Reason for Denial',
        required=True,
        help='Provide detailed reason for denying access'
    )
    add_to_watchlist = fields.Boolean(
        string='Add to Watchlist',
        default=True,
        help='Add this visitor to the watchlist'
    )
    watchlist_category = fields.Selection([
        ('security_threat', 'Security Threat'),
        ('previous_incident', 'Previous Incident'),
        ('legal_issue', 'Legal Issue'),
        ('banned', 'Permanently Banned'),
        ('temporary', 'Temporary Restriction'),
        ('other', 'Other')
    ], string='Watchlist Category', default='other')

    def action_deny_access(self):
        """Deny visitor access and optionally add to watchlist"""
        self.ensure_one()
        
        # Update visitor status
        self.visitor_id.write({
            'state': 'denied',
            'denied_reason': self.reason
        })
        
        # Add to watchlist if requested (scoped to the visitor's site)
        if self.add_to_watchlist:
            site_cmd = []
            if self.visitor_id.site_id:
                site_cmd = [(6, 0, [self.visitor_id.site_id.id])]
            self.env['visitor.watchlist'].create({
                'name': self.visitor_id.name,
                'id_number': self.visitor_id.id_number,
                'reason': self.reason,
                'category': self.watchlist_category,
                'photo': self.visitor_id.visitor_photo,
                'site_ids': site_cmd,
            })
        
        return {'type': 'ir.actions.act_window_close'}

