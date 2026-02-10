# -*- coding: utf-8 -*-
"""CCTV Viewer Wizard - Site and Camera Selection."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class CCTVViewerWizard(models.TransientModel):
    """Wizard for selecting site and camera to view."""

    _name = 'cctv.viewer.wizard'
    _description = 'CCTV Viewer Wizard'

    # Step 1: Site Selection
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True,
        help='Select a site to view its CCTV cameras'
    )

    # Step 2: Camera Selection (computed based on site)
    camera_ids = fields.Many2many(
        'cctv.camera',
        string='Available Cameras',
        compute='_compute_camera_ids',
        readonly=True,
        help='Cameras available at the selected site'
    )
    camera_id = fields.Many2one(
        'cctv.camera',
        string='Select Camera',
        domain="[('id', 'in', camera_ids), ('is_active', '=', True), ('status', '=', 'online')]",
        help='Select a camera to view'
    )

    # Camera Info (read-only)
    camera_name = fields.Char(
        related='camera_id.name',
        readonly=True
    )
    camera_code = fields.Char(
        related='camera_id.code',
        readonly=True
    )
    stream_url = fields.Char(
        related='camera_id.stream_url',
        readonly=True
    )
    stream_type = fields.Selection(
        related='camera_id.stream_type',
        readonly=True
    )
    camera_status = fields.Selection(
        related='camera_id.status',
        readonly=True
    )

    @api.depends('site_id')
    def _compute_camera_ids(self):
        """Compute available cameras for selected site."""
        for wizard in self:
            if wizard.site_id:
                cameras = self.env['cctv.camera'].search([
                    ('site_id', '=', wizard.site_id.id),
                    ('is_active', '=', True)
                ])
                wizard.camera_ids = cameras
            else:
                wizard.camera_ids = False

    @api.onchange('site_id')
    def _onchange_site_id(self):
        """Reset camera selection when site changes."""
        self.camera_id = False

    def action_view_camera(self):
        """Open camera stream viewer."""
        self.ensure_one()
        if not self.camera_id:
            raise ValidationError(_('Please select a camera to view.'))
        
        if self.camera_id.status != 'online':
            raise ValidationError(_('Selected camera is not online. Please select an online camera.'))
        
        # Return action to open stream viewer in new window
        return {
            'type': 'ir.actions.act_url',
            'url': f'/guardpro/cctv/view/{self.camera_id.id}',
            'target': 'new',
        }








