# -*- coding: utf-8 -*-

from odoo import models, fields


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

    def action_deny_access(self):
        """Deny visitor access."""
        self.ensure_one()
        self.visitor_id.write({
            'state': 'denied',
            'denied_reason': self.reason
        })
        return {'type': 'ir.actions.act_window_close'}
